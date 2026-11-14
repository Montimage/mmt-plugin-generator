"""``mmt-plugin init LABEL`` (``docs/design/cli.md``, sections 4, 5, 6, 8).

Creates a plugin project that builds and tests green out of the box, in
``--dir`` (default ``./<LABEL>``, relative to the current directory):

- ``model.pdl``: a PDL v1 model of a 4-byte header (``version``, ``kind``,
  ``length``). The canonical ``plugin.yaml`` waits for #24, and ``build`` and
  ``test`` read a PDL v1 model today (``--model model.pdl``);
- ``src/<label>_impl.c``: the user code scaffold
  (``mmt_plugin.codegen.scaffold``), which defines every hook;
- ``tests/<label>-basic.yaml``: one packet test (corpus schema 1) of that
  header, which ``mmt-plugin test`` runs;
- ``.gitignore``: ``build/``.

The generated sources are not created: ``build`` and ``test`` generate them.

Stages, each stopping the run with its class's exit code:

1. check ``LABEL`` (``[a-z][a-z0-9_]*``), ``--name`` and ``--parent``
   (usage, exit 2; a parent that the profile does not know is
   ``model.unknown-parent``, exit 3; no parent is the warning
   ``model.no-parent``);
2. choose the profile (``--sdk-profile``, ``MMT_PLUGIN_SDK_PROFILE``, the
   detected SDK's, else the newest bundled one with a warning). The SDK is
   looked for only when it is needed: no ``--id`` (to pick one), ``--sdk``,
   or no pinned profile;
3. the id: ``--id``, else the id of an existing ``model.pdl`` of the same
   label (so a re-run keeps it), else the lowest id from 950 to 999 that
   neither the profile nor the installed plugins (``mmt_plugin.sdk.registry``, the
   project's own ``mmtp_<label>.so`` excluded) take. Without an SDK, only
   the profile is checked (the warning ``sdk.id-unchecked``). The installed
   plugins also check an explicit ``--id`` and the name when an SDK is
   found (``model.id-taken``, ``model.name-taken``, exit 3);
4. render every file in memory, and generate the model as ``build`` will
   (``mmt_plugin.commands.generate.make_generation``): a model error, a
   taken id or name among them, is exit 3 and nothing is written;
5. plan the writes: a file with the same content is ``unchanged``; one with
   other content (or not a regular file) is ``state.file-differs`` (exit 7,
   nothing written) unless ``--force``, which replaces it (never a
   directory). A file or a symbolic link where a directory of the project
   goes (``src``, ``tests``) is ``state.file-differs`` even with ``--force``,
   so nothing is written outside ``--dir``. A ``--dir`` that holds more than ``.git`` but no
   ``model.pdl`` is not a project: ``state.not-a-project`` (exit 7) unless
   ``--force``;
6. write each file atomically (``mmt_plugin.fsio``). Re-running on the same
   arguments is a no-op.

``--dry-run`` writes nothing and reports ``would-*`` actions.
``result.next`` is the command line that tests the new project.
"""

from __future__ import annotations

import argparse
import os
import re
import shlex
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from mmt_plugin.codegen import scaffold
from mmt_plugin.commands import Context, Outcome, Subparsers
from mmt_plugin.commands.generate import make_generation
from mmt_plugin.commands.modelio import absolute, show_path
from mmt_plugin.diagnostics import CliError, Diagnostic, Location, Severity
from mmt_plugin.exitcodes import ExitCode
from mmt_plugin.fsio import sha256_bytes, write_atomic
from mmt_plugin.pdl import PdlSyntaxError, parse
from mmt_plugin.sdk.detect import DEFAULT_PREFIX, Sdk, find_sdk
from mmt_plugin.sdk.profile import Profile
from mmt_plugin.sdk.registry import Registry, RegistryError, read_registry
from mmt_plugin.sdk.resolve import ENV_PROFILE, ProfileChoice, resolve_profile, sdk_context
from mmt_plugin.semantics import THIRD_PARTY_IDS
from mmt_plugin.ui import style
from mmt_plugin.ui.streams import StreamStyle

__all__ = [
    "DIAGNOSTIC_CODES",
    "MODEL_FILE",
    "InitCommand",
    "parse_selector",
    "project_files",
]

#: The codes this command reports itself (besides the model's and the SDK's).
DIAGNOSTIC_CODES = (
    "model.no-parent",
    "model.unknown-parent",
    "model.id-taken",
    "model.name-taken",
    "sdk.id-unchecked",
    "sdk.registry-unavailable",
    "state.file-differs",
    "state.not-a-project",
)

#: The project's model, until ``plugin.yaml`` (#24).
MODEL_FILE = "model.pdl"
GITIGNORE = ".gitignore"

_LABEL = re.compile(r"^[a-z][a-z0-9_]*$")
_KEY = re.compile(r"^[a-z_][a-z0-9_]*$")
_VALUE = re.compile(r"^[A-Za-z0-9_.:/-]+$")

#: The starter header: (name, C type, MMT type, length, value in the packet).
_FIELDS = (
    ("version", "uint8_t", "MMT_U8_DATA", 1, 1),
    ("kind", "uint8_t", "MMT_U8_DATA", 1, 2),
    ("length", "uint16_t", "MMT_U16_DATA", 2, 4),
)

_LEVELS = {
    "created": style.Level.OK,
    "unchanged": style.Level.OK,
    "updated": style.Level.WARN,
    "would-create": style.Level.SKIP,
    "would-update": style.Level.SKIP,
}
_WOULD = {"created": "would-create", "updated": "would-update"}
_ORDER = ("created", "updated", "unchanged", "would-create", "would-update")


def _plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


@dataclass(frozen=True)
class Selector:
    """A parsed ``SELECTOR``: ``<proto>[:<key>=<value>[,<key>=<value>...]]``."""

    text: str
    proto: str
    keys: tuple[tuple[str, str], ...]


def parse_selector(text: str) -> Selector:
    """Parse ``--parent``; ``CliError`` ``usage.invalid-value`` when malformed."""
    proto, sep, rest = text.partition(":")
    keys: list[tuple[str, str]] = []
    ok = _LABEL.match(proto) is not None and (not sep or bool(rest))
    for item in rest.split(",") if sep and rest else ():
        key, eq, value = item.partition("=")
        if not (eq and _KEY.match(key) and _VALUE.match(value)):
            ok = False
            break
        keys.append((key, value))
    if not ok:
        raise CliError(
            "usage.invalid-value",
            f"--parent {text!r} is not a selector (<proto>[:<key>=<value>[,...]])",
            "for example --parent ethernet:ethertype=0x88b5 or --parent udp:port=4433",
        )
    return Selector(text, proto, tuple(keys))


def _model_text(label: str, pid: int, parent: Selector | None) -> str:
    """The starter model, PDL v1."""
    lc = label.lower()
    if parent is None:
        where = "no parent yet: attach it in"
    else:
        where = f"parent {parent.text}: attach it in"
    lines = [
        f"// The {label.upper()} protocol plugin's model, created by mmt-plugin init.",
        f"// {where} src/{lc}_impl.c, {lc}_hook_register_parents().",
        "Protocol {",
        "\tProperties {",
        f'\t\tlabel = "{label}"',
        f'\t\tid = "{pid}"',
        '\t\tencoding = "network"',
        "\t}",
        "\tAttributes {",
        f"\t\tstruct {lc}_hdr {{",
        *(f"\t\t\t{ctype} {name};" for name, ctype, _, _, _ in _FIELDS),
        "\t\t}",
        "\t}",
        "}",
    ]
    return "\n".join(lines) + "\n"


def _test_text(label: str, pid: int) -> str:
    """The starter packet test (corpus schema 1, ``tests/corpus/README.md``)."""
    lc = label.lower()
    data: list[str] = []
    for _, _, _, length, value in _FIELDS:
        data += [f"{b:02x}" for b in value.to_bytes(length, "big")]
    lines = [
        f"# Packet test {lc}/basic, created by mmt-plugin init. Format: corpus schema 1",
        "# (tests/corpus/README.md). Run it with mmt-plugin test.",
        "schema: 1",
        f'id: "{lc}/basic"',
        f'summary: "One {label.upper()} header: version 1, kind 2, length 4"',
        "bytes:",
        f'  - "{" ".join(data)}"',
        "expect:",
        f'  protocol: "{label.upper()}"',
        f"  proto_id: {pid}",
        "  next:",
        '    kind: "none"',
        "  attributes:",
    ]
    offset = 0
    for name, _, mmt_type, length, value in _FIELDS:
        lines += [
            f'    - name: "{name}"',
            f'      type: "{mmt_type}"',
            f"      offset: {offset}",
            f"      length: {length}",
            f"      value: {value}",
        ]
        offset += length
    return "\n".join(lines) + "\n"


def _project_id(target: Path, label: str) -> int | None:
    """The id of ``<target>/model.pdl`` when it parses and has ``label``, so
    that re-running ``init`` without ``--id`` keeps the project's id."""
    try:
        text = (target / MODEL_FILE).read_text("utf-8")
        props = parse(text, filename=MODEL_FILE).properties
    except (OSError, UnicodeDecodeError, PdlSyntaxError):
        return None
    if props.label.text.lower() != label.lower() or props.id is None:
        return None
    return int(props.id.value)


def project_files(
    label: str, pid: int, parent: Selector | None, choice: ProfileChoice
) -> tuple[list[tuple[str, bytes]], list[Diagnostic], CliError | None]:
    """Every file of a new project, by path relative to it, sorted; the
    model's diagnostics; and the model error that stops the run, if any."""
    model = _model_text(label, pid, parent).encode("utf-8")
    generation, diagnostics, error = make_generation(MODEL_FILE, model, choice)
    if generation is None:
        assert error is not None
        return [], diagnostics, error
    impl = scaffold(generation, choice.profile)
    files = [
        (GITIGNORE, b"build/\n"),
        (MODEL_FILE, model),
        (impl.path, impl.data),
        (f"tests/{label.lower()}-basic.yaml", _test_text(label, pid).encode("utf-8")),
    ]
    return sorted(files), diagnostics, None


#: A reader of the run-time registry (tests replace it).
RegistryReader = Callable[..., Registry]


@dataclass
class _Planned:
    path: Path
    shown: str
    action: str
    sha256: str
    data: bytes


class InitCommand:
    """``mmt-plugin init LABEL``: create a plugin project.

    ``pkg_config_dirs``, ``default_prefix`` and ``registry_reader`` replace
    the SDK search path and the run-time registry (tests replace them)."""

    name = "init"
    exit_codes: tuple[ExitCode, ...] = (ExitCode.MODEL, ExitCode.SDK, ExitCode.STATE)

    def __init__(
        self,
        *,
        pkg_config_dirs: Sequence[str] | None = None,
        default_prefix: str = DEFAULT_PREFIX,
        registry_reader: RegistryReader = read_registry,
    ) -> None:
        self.pkg_config_dirs = pkg_config_dirs
        self.default_prefix = default_prefix
        self.registry_reader = registry_reader

    def register(self, subparsers: Subparsers) -> argparse.ArgumentParser:
        parser = subparsers.add_parser(
            self.name,
            help="create a plugin project that builds and tests green",
            description=(
                "Create a plugin project in --dir: model.pdl (a PDL v1 model; plugin.yaml\n"
                "needs #24), the user code scaffold src/<label>_impl.c, the packet test\n"
                "tests/<label>-basic.yaml and a .gitignore. build and test generate the C\n"
                "sources. Re-running is a no-op; a file with other content is not replaced\n"
                "without --force."
            ),
            epilog=(
                "examples:\n"
                "  mmt-plugin init demo\n"
                "  mmt-plugin init demo --id 960 --parent ethernet:ethertype=0x88b5\n"
                "  mmt-plugin -C demo test --model demo/model.pdl"
            ),
        )
        parser.add_argument(
            "label",
            metavar="LABEL",
            help="the protocol label, [a-z][a-z0-9_]* (names mmtp_<label>.so)",
        )
        parser.add_argument(
            "--dir",
            metavar="DIR",
            help="where to create the project (default: ./<LABEL>; . when empty or a project)",
        )
        parser.add_argument(
            "--id",
            type=int,
            metavar="N",
            help="the protocol id (default: the lowest id from 950 to 999 free in the SDK)",
        )
        parser.add_argument(
            "--name",
            metavar="NAME",
            help="the registered protocol name (default and only value until #24: LABEL"
            " upper-cased)",
        )
        parser.add_argument(
            "--parent",
            metavar="SELECTOR",
            help="the parent protocol, e.g. ethernet:ethertype=0x88b5 (default: none, a warning)",
        )
        parser.add_argument(
            "--sdk",
            metavar="PREFIX",
            help="an mmt-dpi prefix, for the free ids and the profile (default: detected)",
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
            "--dry-run", action="store_true", help="report every action, write nothing"
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="replace a project file that has other content",
        )
        return parser

    # --- stages ---

    def _arguments(self, args: argparse.Namespace) -> Selector | None:
        label = args.label
        if not _LABEL.match(label):
            raise CliError(
                "usage.invalid-value",
                f"LABEL {label!r} is not a protocol label ([a-z][a-z0-9_]*)",
                "use lower-case letters, digits and _, starting with a letter",
            )
        if args.name is not None and args.name != label.upper():
            raise CliError(
                "usage.invalid-value",
                f"--name {args.name!r}: the registered name of a PDL v1 model is its label"
                f" upper-cased, {label.upper()}",
                "omit --name, or pass a LABEL whose upper case is the name (a separate"
                " name needs plugin.yaml, #24)",
            )
        return None if args.parent is None else parse_selector(args.parent)

    def _registry(
        self, sdk: Sdk, profile: Profile, label: str, diagnostics: list[Diagnostic]
    ) -> Registry | None:
        try:
            value = profile.constant("PROTO_MAX_IDENTIFIER").value
        except KeyError:  # pragma: no cover - every bundled profile has it
            value = None
        try:
            return self.registry_reader(
                sdk,
                env=os.environ,
                max_id=1000 if value is None else value,
                exclude=f"mmtp_{label.lower()}.so",
            )
        except RegistryError as exc:
            diagnostics.append(
                Diagnostic(
                    Severity.WARNING,
                    "sdk.registry-unavailable",
                    f"{exc}: the id and the name are checked against the SDK profile"
                    f" {profile.version} only",
                    hint="check that the SDK's plugins load (init_extraction()), or pass --id",
                )
            )
            return None

    def _id(
        self,
        args: argparse.Namespace,
        target: Path,
        profile: Profile,
        sdk: Sdk | None,
        registry: Registry | None,
        diagnostics: list[Diagnostic],
    ) -> int:
        label = args.label
        if registry is not None:
            hit = registry.by_name(label)
            if hit is not None:
                raise CliError(
                    "model.name-taken",
                    f"protocol name {label.upper()} is already registered by an installed"
                    f" plugin of {registry.plugin_dir} (id {hit.id})",
                    "choose another LABEL",
                )
        pid = args.id if args.id is not None else _project_id(target, label)
        if pid is not None:
            if registry is not None:
                hit = registry.by_id(pid)
                if hit is not None:
                    raise CliError(
                        "model.id-taken",
                        f"protocol id {pid} is already {hit.name}'s, registered by an"
                        f" installed plugin of {registry.plugin_dir}",
                        "use a free id from 950 to 999",
                    )
            return int(pid)
        taken = {p.id for p in profile.parents.protocols()}
        if registry is not None:
            taken |= {p.id for p in registry.protocols}
        free = [i for i in THIRD_PARTY_IDS if i not in taken]
        if not free:
            raise CliError(
                "model.id-taken",
                f"every protocol id from {THIRD_PARTY_IDS.start} to {THIRD_PARTY_IDS.stop - 1}"
                " is taken in the SDK",
                "pass a free id with --id",
            )
        if sdk is None:
            diagnostics.append(
                Diagnostic(
                    Severity.WARNING,
                    "sdk.id-unchecked",
                    f"no SDK found: id {free[0]} is free in the SDK profile {profile.version},"
                    " but the installed plugins were not checked",
                    hint="pass --sdk PREFIX (or MMT_BASE), or choose the id with --id",
                )
            )
        return free[0]

    def _plan(
        self, target: Path, files: Sequence[tuple[str, bytes]], force: bool, project: Path
    ) -> tuple[list[_Planned], list[Diagnostic]]:
        planned: list[_Planned] = []
        diagnostics: list[Diagnostic] = []
        for rel, data in files:
            path = target / rel
            shown = show_path(path, project)
            new = sha256_bytes(data)
            action = "created"
            problem = None
            between = [d for d in path.parents if d != target and target in d.parents]
            blocked = next(
                (
                    d
                    for d in reversed(between)
                    if d.is_symlink() or (d.exists() and not d.is_dir())
                ),
                None,
            )
            if blocked is not None:
                # A file or a symbolic link where a directory goes: never
                # replaced, so nothing is written through it.
                planned.append(_Planned(path, shown, "created", new, data))
                diagnostics.append(
                    Diagnostic(
                        Severity.ERROR,
                        "state.file-differs",
                        f"{show_path(blocked, project)} is not a directory"
                        + (" (a symbolic link)" if blocked.is_symlink() else "")
                        + ": nothing written into it",
                        hint="move it away",
                        location=Location(shown),
                    )
                )
                continue
            if path.is_symlink():
                action, problem = "updated", "is a symbolic link"
            elif path.is_dir():
                action, problem = "updated", "is a directory"
            elif path.exists():
                try:
                    same = path.read_bytes() == data
                except OSError as exc:
                    raise CliError(
                        "internal.io",
                        f"cannot read {shown}: {exc.strerror or exc}",
                        "check its permissions",
                    ) from None
                if same:
                    action = "unchanged"
                else:
                    action, problem = "updated", "exists with other content"
            if problem is not None:
                refused = not force or (path.is_dir() and not path.is_symlink())
                diagnostics.append(
                    Diagnostic(
                        Severity.ERROR if refused else Severity.WARNING,
                        "state.file-differs",
                        f"{problem}: " + ("not replaced" if refused else "replaced (--force)"),
                        hint=(
                            "move it away, or re-run with --force to replace it"
                            if refused and not path.is_dir()
                            else "move it away"
                            if refused
                            else None
                        ),
                        location=Location(shown),
                    )
                )
            planned.append(_Planned(path, shown, action, new, data))
        return planned, diagnostics

    def run(self, args: argparse.Namespace, ctx: Context) -> Outcome:
        project = absolute(ctx.project)
        parent = self._arguments(args)
        label = args.label
        target = absolute(args.dir if args.dir is not None else label)
        env = os.environ
        pinned = args.sdk_profile is not None or bool(env.get(ENV_PROFILE, ""))
        sdk = None
        if args.sdk is not None or args.id is None or not pinned:
            sdk = find_sdk(
                args.sdk,
                env,
                pkg_config_dirs=self.pkg_config_dirs,
                default_prefix=self.default_prefix,
            )
        choice = resolve_profile(args.sdk_profile, env, None, sdk)
        profile = choice.profile
        context = {"sdk": sdk_context(sdk, choice)}
        ctx.log(f"SDK profile {profile.version} ({choice.source.value})")
        diagnostics: list[Diagnostic] = list(choice.diagnostics)

        if parent is None:
            diagnostics.append(
                Diagnostic(
                    Severity.WARNING,
                    "model.no-parent",
                    "no --parent: nothing hands the plugin packets until"
                    f" {label}_hook_register_parents() in src/{label}_impl.c attaches it",
                    hint="pass --parent SELECTOR, or fill in the example in that hook"
                    " (mmt-plugin test attaches the plugin to Ethernet itself)",
                )
            )
        elif profile.parents.id_of(profile.parents.id_for(parent.proto)) is None:
            raise CliError(
                "model.unknown-parent",
                f"parent protocol {parent.proto!r} is not in the SDK profile {profile.version}",
                "use a protocol of the SDK, e.g. ethernet, ip, tcp or udp",
            )

        for d in (target, *target.parents):
            if d.exists() and not d.is_dir():
                raise CliError(
                    "state.not-a-project",
                    f"--dir {show_path(target, project)}: {show_path(d, project)} exists and is"
                    " not a directory",
                    "pass another --dir",
                )

        registry = None
        if sdk is not None:
            registry = self._registry(sdk, profile, label, diagnostics)
        pid = self._id(args, target, profile, sdk, registry, diagnostics)
        ctx.log(f"protocol {label.upper()}, id {pid}")

        files, model_diagnostics, model_error = project_files(label, pid, parent, choice)
        diagnostics += model_diagnostics
        if model_error is not None:
            first = next((d for d in model_diagnostics if d.severity is Severity.ERROR), None)
            why = "" if first is None else f" ({first.message})"
            stop = CliError(
                model_error.code,
                f"the project of {label} (id {pid}) does not generate{why}: nothing written",
                first.hint if first is not None and first.hint else "choose another LABEL or --id",
            )
            return Outcome(diagnostics=diagnostics, error=stop, context=context)

        error: CliError | None = None
        try:
            entries = [] if not target.is_dir() else os.listdir(target)
        except OSError as exc:
            raise CliError(
                "internal.io",
                f"cannot list {show_path(target, project)}: {exc.strerror or exc}",
                "check its permissions",
            ) from None
        # A new repository (only .git) counts as empty.
        foreign = bool(set(entries) - {".git"}) and not os.path.lexists(target / MODEL_FILE)
        if foreign:
            note = Diagnostic(
                Severity.WARNING if args.force else Severity.ERROR,
                "state.not-a-project",
                f"not empty and has no {MODEL_FILE}: "
                + ("written into it (--force)" if args.force else "nothing written"),
                hint=None if args.force else "pass an empty or new --dir, or re-run with --force",
                location=Location(show_path(target, project)),
            )
            diagnostics.append(note)
            if not args.force:
                error = CliError(
                    "state.not-a-project",
                    f"--dir {show_path(target, project)} is not empty and is not a plugin project",
                    "pass an empty or new --dir, or re-run with --force",
                )
        planned, plan_notes = self._plan(target, files, args.force, project)
        diagnostics += plan_notes
        refused = [d for d in plan_notes if d.severity is Severity.ERROR]
        if refused and error is None:
            error = CliError(
                "state.file-differs",
                f"{_plural(len(refused), 'project file')} with other content: nothing written",
                "move them away, or re-run with --force to replace them",
            )

        if error is None and not args.dry_run:
            for p in planned:
                if p.action != "unchanged":
                    p.action = write_atomic(p.path, p.data).action.value
        else:
            for p in planned:
                p.action = _WOULD.get(p.action, p.action)

        cwd = absolute(".")
        next_argv = ["mmt-plugin", "-C", show_path(target, cwd)]
        next_argv += ["test", "--model", show_path(target / MODEL_FILE, cwd)]
        if args.sdk is not None:
            next_argv += ["--sdk", args.sdk]
        if args.sdk_profile is not None:
            next_argv += ["--sdk-profile", profile.version]
        files_out = [{"path": p.shown, "action": p.action, "sha256": p.sha256} for p in planned]
        result = {
            "project": show_path(target, project),
            "protocol": {"label": label, "name": label.upper(), "id": pid},
            "parent": None if parent is None else parent.text,
            "profile": profile.version,
            "model": show_path(target / MODEL_FILE, project),
            "files": files_out,
            "next": next_argv,
            "dry_run": bool(args.dry_run),
        }
        records = [(f["action"], f["path"]) for f in files_out]

        def view(st: StreamStyle) -> str:
            return _view(label, pid, files_out, next_argv, st)

        return Outcome(
            result=result,
            records=records,
            view=view,
            diagnostics=diagnostics,
            error=error,
            context=context,
        )


def _view(
    label: str,
    pid: int,
    files: Sequence[dict[str, str]],
    next_argv: Sequence[str],
    st: StreamStyle,
) -> str:
    """The styled output: a box ``init <label>`` with the files table, then
    the command that tests the project."""
    rows = []
    counts: dict[str, int] = {}
    for entry in files:
        action = entry["action"]
        counts[action] = counts.get(action, 0) + 1
        shown = style.status(action, _LEVELS.get(action, style.Level.OK), style=st)
        rows.append([shown, entry["path"]])
    table = style.table(["action", "file"], rows, style=st, width=st.width - 4)
    separator = style.glyphs(st).separator
    parts = [f"id {pid}", _plural(len(files), "file")]
    parts += [f"{counts[a]} {a}" for a in _ORDER if a in counts]
    body: list[str | style.Section] = [*table, style.Section([f"next: {shlex.join(next_argv)}"])]
    return style.box(f"init {label}", body, style=st, footer=separator.join(parts))
