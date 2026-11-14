"""``mmt-plugin generate [MODEL]`` (``docs/design/cli.md``, sections 4, 5, 6, 8).

Generates the plugin's C header and source from a PDL v1 model into the
output directory (``<project>/generated/`` by default), and records them in
``plugin.lock`` (``mmt_plugin.lock``): at the project root, or in the output
directory for a model outside a project (no ``plugin.yaml`` in the project).

Stages, each stopping the run with its class's exit code:

1. read the model (``-`` is stdin, named ``<stdin>``); ``plugin.yaml`` waits
   for #24 and is ``model.unsupported-format`` (exit 3);
2. choose the SDK profile: ``--sdk-profile``, ``MMT_PLUGIN_SDK_PROFILE``, the
   detected SDK's version, else the newest bundled profile with a warning.
   Generation needs a profile, not an installed SDK: with a pinned profile
   and no ``--sdk``, no SDK is looked for (exit 4 on an SDK or profile error);
3. parse, analyse (an SDK id or name conflict is an error) and render the
   whole set in memory (exit 3, nothing written); ``--strict`` fails on any
   warning;
4. plan every write against the files on disk and the lock: an unchanged
   file is not rewritten (its mtime is kept); a file whose sha256 is neither
   the new one nor the lock's was edited by hand, and is not overwritten or
   removed without ``--force`` (``state.modified``, exit 7, nothing written);
   a file the lock lists that is no longer generated is removed when it is
   unmodified and inside the output directory;
5. write each file atomically (``mmt_plugin.fsio``), then remove the old
   ones, then write ``plugin.lock`` last. An interrupted run leaves the old
   lock, against which the next run (or ``--check``) sees what changed.

``--check`` and ``--dry-run`` write nothing and report ``would-*`` actions;
``--check`` exits 7 (``state.stale``) when any file or the lock would change.
Nothing is ever written under ``<project>/src/``, which holds user code.
"""

from __future__ import annotations

import argparse
import os
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from mmt_plugin import __version__
from mmt_plugin.codegen import Generation, GenerationError, generate
from mmt_plugin.commands import Context, Outcome, Subparsers
from mmt_plugin.commands.modelio import (
    FORMATS,
    PROJECT_FILE,
    ModelInput,
    absolute,
    decode_model,
    inside,
    read_model,
    show_path,
)
from mmt_plugin.diagnostics import CliError, Diagnostic, Location, Severity
from mmt_plugin.exitcodes import ExitCode
from mmt_plugin.fsio import sha256_bytes, sha256_file, write_atomic
from mmt_plugin.lock import LOCK_NAME, Lock, LockedFile, LockError, read_lock
from mmt_plugin.pdl import PdlSyntaxError, parse
from mmt_plugin.sdk.detect import DEFAULT_PREFIX, Sdk, find_sdk
from mmt_plugin.sdk.resolve import ENV_PROFILE, ProfileChoice, resolve_profile, sdk_context
from mmt_plugin.semantics import analyse
from mmt_plugin.ui import style
from mmt_plugin.ui.streams import StreamStyle

__all__ = ["DIAGNOSTIC_CODES", "GenerateCommand"]

#: The codes this command reports itself (besides the parser's, the
#: semantic passes', generation's and the SDK's).
DIAGNOSTIC_CODES = (
    "model.unreadable",
    "model.unsupported-format",
    "state.stale",
    "state.modified",
    "state.invalid-lock",
    "state.kept",
)

DEFAULT_OUTPUT = "generated"
USER_DIR = "src"

#: Each action word, and how the styled view shows it.
_LEVELS = {
    "created": style.Level.OK,
    "unchanged": style.Level.OK,
    "updated": style.Level.WARN,
    "removed": style.Level.WARN,
    "would-create": style.Level.SKIP,
    "would-update": style.Level.SKIP,
    "would-remove": style.Level.SKIP,
}
_WOULD = {"created": "would-create", "updated": "would-update", "removed": "would-remove"}
_ORDER = (
    "created",
    "updated",
    "removed",
    "unchanged",
    "would-create",
    "would-update",
    "would-remove",
)


@dataclass
class _Paths:
    """Absolute paths of one run, and how to show a path."""

    project: Path
    output: Path
    lock_dir: Path
    user_dir: Path

    def show(self, path: Path) -> str:
        """Relative to the project when inside it (POSIX), absolute otherwise."""
        return show_path(path, self.project)

    def in_lock(self, path: Path) -> str:
        """Relative to the lock's directory, POSIX: the lock's key of ``path``."""
        return Path(os.path.relpath(path, self.lock_dir)).as_posix()


@dataclass
class _Planned:
    """One file of the plan."""

    path: Path
    shown: str
    action: str  # created, updated, unchanged or removed (what a real run does)
    sha256: str
    data: bytes | None  # None for a removal
    refused: bool = False


def _plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


class GenerateCommand:
    """``mmt-plugin generate [MODEL]``: write the generated C sources and
    plugin.lock.

    ``pkg_config_dirs`` and ``default_prefix`` are passed to SDK detection
    (tests point them at temporary directories)."""

    name = "generate"
    exit_codes: tuple[ExitCode, ...] = (ExitCode.MODEL, ExitCode.SDK, ExitCode.STATE)

    def __init__(
        self,
        *,
        pkg_config_dirs: Sequence[str] | None = None,
        default_prefix: str = DEFAULT_PREFIX,
    ) -> None:
        self.pkg_config_dirs = pkg_config_dirs
        self.default_prefix = default_prefix

    def register(self, subparsers: Subparsers) -> argparse.ArgumentParser:
        parser = subparsers.add_parser(
            self.name,
            help="write the generated C sources and plugin.lock",
            description=(
                "Generate the plugin's C header and source from MODEL into the output\n"
                "directory, and record them in plugin.lock: at the project root, or in\n"
                "the output directory for a model outside a project (no plugin.yaml in\n"
                "--project). A generated file edited by hand is not overwritten without\n"
                "--force. Nothing is written under <project>/src/. Generation needs an\n"
                "SDK profile, not an installed SDK."
            ),
            epilog=(
                "examples:\n"
                "  mmt-plugin generate plugins/tpkt_plugin -o /tmp/tpkt-out --sdk-profile 1.10.2\n"
                "  mmt-plugin generate model.pdl --check   # exit 7 if generated/ is stale"
            ),
        )
        parser.add_argument(
            "model",
            nargs="?",
            metavar="MODEL",
            help=(
                "a PDL v1 model file, or - for stdin (default: <project>/plugin.yaml, which"
                " needs #24)"
            ),
        )
        parser.add_argument(
            "-o",
            "--output",
            metavar="DIR",
            help="the output directory (default: <project>/generated/)",
        )
        parser.add_argument(
            "--model-format",
            choices=FORMATS,
            default="auto",
            help="the model format (default: auto: .yaml/.yml is YAML, anything else PDL)",
        )
        parser.add_argument(
            "--sdk",
            metavar="PREFIX",
            help="an mmt-dpi prefix, only used to pick the SDK profile (default: detected)",
        )
        parser.add_argument(
            "--sdk-profile",
            metavar="VERSION",
            help=(
                f"the SDK profile, e.g. 1.10.2 (default: {ENV_PROFILE}, else the detected"
                " SDK's, else the newest bundled one)"
            ),
        )
        parser.add_argument(
            "--check",
            action="store_true",
            help="write nothing; exit 7 if a generated file or plugin.lock would change",
        )
        parser.add_argument(
            "--dry-run", action="store_true", help="report every action, write nothing"
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="overwrite or remove a generated file that was edited by hand",
        )
        parser.add_argument(
            "--strict", action="store_true", help="fail on warnings, with their class's code"
        )
        return parser

    # --- stages ---

    def _profile(self, args: argparse.Namespace, ctx: Context) -> tuple[Sdk | None, ProfileChoice]:
        env = os.environ
        pinned = args.sdk_profile is not None or bool(env.get(ENV_PROFILE, ""))
        sdk = None
        if args.sdk is not None or not pinned:
            sdk = find_sdk(
                args.sdk,
                env,
                pkg_config_dirs=self.pkg_config_dirs,
                default_prefix=self.default_prefix,
            )
        choice = resolve_profile(args.sdk_profile, env, None, sdk)
        ctx.log(f"SDK profile {choice.profile.version} ({choice.source.value})")
        return sdk, choice

    def _generation(
        self, name: str, data: bytes, choice: ProfileChoice
    ) -> tuple[Generation | None, list[Diagnostic], CliError | None]:
        try:
            text = decode_model(ModelInput(name, "pdl", data))
        except CliError as error:
            return None, [], error
        try:
            model = parse(text, filename=name)
        except PdlSyntaxError as exc:
            return None, list(exc.diagnostics), _model_error(name, exc.diagnostics)
        analysed, diagnostics = analyse(model, profile=choice.profile, allow_sdk_conflicts=False)
        if analysed is None:
            return None, diagnostics, _model_error(name, diagnostics)
        try:
            generation = generate(analysed, choice.profile)
        except GenerationError as exc:
            diagnostics += exc.diagnostics
            return None, diagnostics, _model_error(name, exc.diagnostics)
        return generation, [*diagnostics, *generation.diagnostics], None

    def _paths(self, args: argparse.Namespace, ctx: Context) -> _Paths:
        project = absolute(ctx.project)
        output = absolute(args.output) if args.output is not None else project / DEFAULT_OUTPUT
        user_dir = project / USER_DIR
        real_out, real_user = Path(os.path.realpath(output)), Path(os.path.realpath(user_dir))
        if inside(output, user_dir) or inside(real_out, real_user):
            raise CliError(
                "usage.invalid-value",
                f"--output {show_path(output, project)} is under {USER_DIR}/, which holds your"
                " code: generate never writes there",
                f"pick another output directory (default: {DEFAULT_OUTPUT}/)",
            )
        lock_dir = project if (project / PROJECT_FILE).is_file() else output
        return _Paths(project, output, lock_dir, user_dir)

    def _old_lock(self, paths: _Paths, force: bool) -> tuple[Lock | None, list[Diagnostic]]:
        lock_path = paths.lock_dir / LOCK_NAME
        try:
            return read_lock(lock_path, paths.show(lock_path)), []
        except LockError as exc:
            if not force:
                raise CliError(
                    "state.invalid-lock",
                    str(exc),
                    "fix or delete plugin.lock, or re-run with --force to regenerate every"
                    " file and the lock",
                ) from None
            note = Diagnostic(
                Severity.WARNING,
                "state.invalid-lock",
                f"{exc}: ignored (--force)",
                location=Location(paths.show(lock_path)),
            )
            return None, [note]

    def _plan(
        self,
        generation: Generation,
        paths: _Paths,
        old: Lock | None,
        force: bool,
    ) -> tuple[list[_Planned], list[Diagnostic]]:
        planned: list[_Planned] = []
        diagnostics: list[Diagnostic] = []
        produced: set[str] = set()
        hint = (
            f"move the change into {USER_DIR}/{generation.label.lower()}_impl.c, or re-run"
            " with --force to discard it"
        )
        for f in generation.files:
            path = paths.output / f.name
            key = paths.in_lock(path)
            produced.add(key)
            data = f.data
            new = sha256_bytes(data)
            current = None if path.is_symlink() else sha256_file(path)
            locked = None if old is None else old.file(key)
            refused = False
            if current is None and not os.path.lexists(path):
                action = "created"
            elif current == new:
                action = "unchanged"
            else:
                action = "updated"
                if locked is None or current != locked.sha256:
                    refused = not force
                    why = (
                        "exists and is not in plugin.lock"
                        if locked is None
                        else "was edited since generate wrote it"
                    )
                    diagnostics.append(
                        Diagnostic(
                            Severity.ERROR if refused else Severity.WARNING,
                            "state.modified",
                            why + (": not overwritten" if refused else ": overwritten (--force)"),
                            hint=hint if refused else None,
                            location=Location(paths.show(path)),
                        )
                    )
            planned.append(_Planned(path, paths.show(path), action, new, data, refused))
        for entry in () if old is None else old.files:
            if entry.path in produced:
                continue
            path = Path(os.path.normpath(paths.lock_dir / entry.path))
            if not os.path.lexists(path):
                continue
            real = Path(os.path.realpath(path))
            shown = paths.show(path)
            if (
                path.is_symlink()
                or not path.is_file()
                or not inside(real, Path(os.path.realpath(paths.output)))
                or inside(real, Path(os.path.realpath(paths.user_dir)))
            ):
                diagnostics.append(
                    Diagnostic(
                        Severity.WARNING,
                        "state.kept",
                        "no longer generated, but not a regular file of the output directory:"
                        " kept",
                        hint="delete it yourself if you no longer need it",
                        location=Location(shown),
                    )
                )
                continue
            current = sha256_file(path)
            refused = False
            if current != entry.sha256:
                refused = not force
                diagnostics.append(
                    Diagnostic(
                        Severity.ERROR if refused else Severity.WARNING,
                        "state.modified",
                        "no longer generated, and edited since generate wrote it:"
                        + (" not removed" if refused else " removed (--force)"),
                        hint=hint if refused else None,
                        location=Location(shown),
                    )
                )
            planned.append(
                _Planned(path, shown, "removed", current or entry.sha256, None, refused)
            )
        planned.sort(key=lambda p: p.shown)
        return planned, diagnostics

    def run(self, args: argparse.Namespace, ctx: Context) -> Outcome:
        paths = self._paths(args, ctx)
        model = read_model(args.model, args.model_format, paths.project)
        name, fmt, data = model.name, model.format, model.data
        sdk, choice = self._profile(args, ctx)
        context = {"sdk": sdk_context(sdk, choice)}
        diagnostics: list[Diagnostic] = list(choice.diagnostics)
        generation, found, error = self._generation(name, data, choice)
        diagnostics += found
        if error is not None or generation is None:
            return Outcome(diagnostics=diagnostics, error=error, context=context)
        warnings = [d for d in diagnostics if d.severity is Severity.WARNING]
        if args.strict and warnings:
            first = warnings[0]
            strict = CliError(
                first.code,
                f"--strict: {_plural(len(warnings), 'warning')} ({first.code})",
                "fix the warnings, or run without --strict",
            )
            return Outcome(diagnostics=diagnostics, error=strict, context=context)

        old, lock_notes = self._old_lock(paths, args.force)
        diagnostics += lock_notes
        planned, plan_notes = self._plan(generation, paths, old, args.force)
        diagnostics += plan_notes
        lock = Lock(
            generator="mmt-plugin",
            generator_version=__version__,
            sdk_profile=choice.profile.version,
            model_format=fmt,
            model_sha256=sha256_bytes(data),
            files=tuple(
                LockedFile(paths.in_lock(p.path), p.sha256)
                for p in planned
                if p.action != "removed"
            ),
        )
        lock_data = lock.dumps().encode("ascii")
        lock_path = paths.lock_dir / LOCK_NAME
        lock_sha = sha256_bytes(lock_data)
        if old is None and not os.path.lexists(lock_path):
            lock_action = "created"
        elif not lock_path.is_symlink() and sha256_file(lock_path) == lock_sha:
            lock_action = "unchanged"
        else:
            lock_action = "updated"
        refused = [p for p in planned if p.refused]
        drift = [p for p in planned if p.action != "unchanged"] or lock_action != "unchanged"
        writes = not (args.check or args.dry_run or refused)

        error = None
        if refused:
            error = CliError(
                "state.modified",
                f"{_plural(len(refused), 'generated file')} edited by hand: nothing written",
                f"move your changes into {USER_DIR}/, or re-run with --force to discard them",
            )
        elif args.check and drift:
            error = CliError(
                "state.stale",
                "the generated files or plugin.lock are not up to date",
                "run mmt-plugin generate (without --check) and commit the result",
            )

        if writes:
            for p in planned:
                if p.data is not None:
                    written = write_atomic(p.path, p.data)
                    p.action = written.action.value
            for p in planned:
                if p.data is None:
                    p.path.unlink()
            lock_action = write_atomic(lock_path, lock_data).action.value
        else:
            for p in planned:
                p.action = _WOULD.get(p.action, p.action)
            lock_action = _WOULD.get(lock_action, lock_action)

        files = [{"path": p.shown, "action": p.action, "sha256": p.sha256} for p in planned]
        lock_entry = {"path": paths.show(lock_path), "action": lock_action, "sha256": lock_sha}
        result = {
            "model": name,
            "format": fmt,
            "profile": choice.profile.version,
            "output": paths.show(paths.output),
            "files": files,
            "lock": lock_entry,
            "check": bool(args.check),
            "dry_run": bool(args.dry_run),
        }
        records = [(f["action"], f["path"]) for f in files] + [(lock_action, lock_entry["path"])]
        label = generation.label.lower()
        stale = bool(args.check)

        def view(st: StreamStyle) -> str:
            return _view(label, files, lock_entry, stale, st)

        return Outcome(
            result=result,
            records=records,
            view=view,
            diagnostics=diagnostics,
            error=error,
            context=context,
        )


def _model_error(name: str, diagnostics: Sequence[Diagnostic]) -> CliError:
    errors = [d for d in diagnostics if d.severity is Severity.ERROR]
    first = errors[0] if errors else diagnostics[0]
    return CliError(
        first.code,
        f"{_plural(len(errors), 'error')} in {name}: nothing generated",
        "fix the errors in the diagnostics, then re-run generate",
    )


def _view(
    label: str,
    files: Sequence[dict[str, str]],
    lock: dict[str, str],
    check: bool,
    st: StreamStyle,
) -> str:
    """The styled output: a box ``generate <label>`` with the files table."""
    rows = []
    counts: dict[str, int] = {}
    for entry in [*files, lock]:
        action = entry["action"]
        counts[action] = counts.get(action, 0) + 1
        if check and action.startswith("would-"):
            shown = style.status("stale", style.Level.FAIL, style=st)
        else:
            shown = style.status(action, _LEVELS.get(action, style.Level.OK), style=st)
        rows.append([shown, entry["path"]])
    table = style.table(["action", "file"], rows, style=st, width=st.width - 4)
    separator = style.glyphs(st).separator
    parts = [_plural(len(files) + 1, "file")]
    parts += [
        f"{counts[a]} {a}"
        for a in _ORDER
        if a in counts and not (check and a.startswith("would-"))
    ]
    if check:
        stale = sum(v for k, v in counts.items() if k.startswith("would-"))
        parts.append("up to date" if not stale else f"{stale} stale")
    return style.box(f"generate {label}", table, style=st, footer=separator.join(parts))
