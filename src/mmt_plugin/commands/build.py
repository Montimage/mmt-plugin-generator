"""``mmt-plugin build [MODEL]`` (``docs/design/cli.md``, sections 4, 5, 6, 8).

Compiles the plugin ``<build-dir>/mmtp_<label>.so`` (``<project>/build/`` by
default) from the generated sources (``<project>/generated/``) and the user
code (every ``<project>/src/*.c``, the scaffold ``src/<label>_impl.c`` among
them), against an installed mmt-dpi SDK.

Stages, each stopping the run with its class's exit code, reported in
``result.stages`` (``ran``, ``up-to-date``, ``would-run``, ``failed``,
``stale`` or ``skipped`` when an earlier stage stopped the run):

0. read the model (a file: ``build`` compares hashes, so not stdin), find the
   SDK (``--sdk``, ``MMT_BASE``, ``mmt-dpi.pc``, ``/opt/mmt``; none is exit 4),
   its ``libmmt_core`` (``mmt_plugin.sdk.registry.core_library``) and the
   compiler (``--cc`` > ``CC`` > ``gcc``; missing is ``sdk.cc-not-found``,
   exit 4), choose the SDK profile, and generate the model in memory
   (exit 3); ``--strict`` fails on any warning;
1. ``generate``: when the generated files or ``plugin.lock`` are stale
   (``mmt-plugin generate --check``, hash-based), run ``generate``; with
   ``--no-deps``, stale is ``state.stale`` (exit 7) instead. A generated file
   edited by hand is ``state.modified`` (exit 7), as for ``generate``;
2. ``compile``: each source to an object in ``<build-dir>/obj/`` with the
   fixed flags (``CFLAGS``, plus the profile's ``-std``); the compiler's
   messages become ``build.cc`` diagnostics (file:line:col relative to the
   project); a failure is ``build.compile-failed`` (exit 5);
3. ``hooks``: every hook the generated header declares must be defined by
   the user objects (``mmt_plugin.codegen.hooks``), else
   ``build.missing-hook`` (exit 5);
4. ``link``: the objects and ``libmmt_core`` into a temporary
   ``<build-dir>/.mmtp_<label>.so.tmp`` with ``LDFLAGS``, renamed over the
   plugin only once the link succeeded; a failure is ``build.link-failed``
   (exit 5). A failed or interrupted build never leaves a broken plugin.

The inputs (the sources' and headers' sha256, the SDK headers and
``libmmt_core``, the flags, the compiler and its version, the profile and
the tool version) hash into ``<build-dir>/.mmtp_<label>.build.json``: when
it matches and the plugin is the one it records, the build is a no-op
(``up_to_date``) unless ``--rebuild``. ``--dry-run`` writes nothing and
reports the compiler command lines (``result.commands``) it would run.

The compiler runs in its own process group, with ``LC_ALL=C`` so its
messages parse; SIGINT kills that group, removes the temporary plugin and
exits 130.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import shlex
import shutil
import signal
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from mmt_plugin import __version__
from mmt_plugin.codegen import Generation
from mmt_plugin.codegen.hooks import (
    ObjectFormatError,
    missing_hook_error,
    missing_hooks,
)
from mmt_plugin.codegen.scaffold import impl_name
from mmt_plugin.commands import Context, Outcome, Subparsers
from mmt_plugin.commands.generate import DEFAULT_OUTPUT, USER_DIR, GenerateCommand, make_generation
from mmt_plugin.commands.modelio import FORMATS, absolute, read_model, show_path
from mmt_plugin.diagnostics import CliError, Diagnostic, Location, Severity
from mmt_plugin.exitcodes import ExitCode
from mmt_plugin.fsio import sha256_bytes, sha256_file, write_atomic
from mmt_plugin.sdk.detect import DEFAULT_PREFIX, Sdk, require_sdk
from mmt_plugin.sdk.registry import core_library
from mmt_plugin.sdk.resolve import ENV_PROFILE, ProfileChoice, resolve_profile, sdk_context
from mmt_plugin.ui import style
from mmt_plugin.ui.streams import StreamStyle

__all__ = [
    "CFLAGS",
    "DIAGNOSTIC_CODES",
    "LDFLAGS",
    "BuildCommand",
    "Compiler",
    "find_compiler",
    "kill_group",
    "parse_compiler_output",
    "require_core_library",
    "run_compiler",
]

#: The codes this command reports itself (besides generate's, the hooks'
#: ``build.missing-hook`` and the SDK's).
DIAGNOSTIC_CODES = (
    "build.cc",
    "build.compile-failed",
    "build.link-failed",
    "sdk.cc-not-found",
)

#: The compile flags, after the profile's ``-std=``: optimised position
#: independent code, hardened (stack protector, fortified libc calls; the
#: ``-U`` drops a distribution's own ``_FORTIFY_SOURCE`` level first, which
#: would otherwise be redefined, an error with ``-Werror``), and every
#: warning of ``-Wall -Wextra`` an error.
CFLAGS = (
    "-O2",
    "-fPIC",
    "-fstack-protector-strong",
    "-U_FORTIFY_SOURCE",
    "-D_FORTIFY_SOURCE=2",
    "-Wall",
    "-Wextra",
    "-Werror",
)
#: The link flags: a shared object with full RELRO, and ``-z defs`` so every
#: symbol resolves at link time (against ``libmmt_core``): a misspelt SDK
#: function fails the build, not the load.
LDFLAGS = ("-shared", "-Wl,-z,relro", "-Wl,-z,now", "-Wl,-z,defs")

DEFAULT_BUILD_DIR = "build"
OBJECT_DIR = "obj"
STAGES = ("generate", "compile", "hooks", "link")
#: The stamp format; a stamp of another version is ignored (rebuild).
STAMP_VERSION = 2
#: The environment variables gcc and clang read that change what they
#: compile or link; part of the input hash.
COMPILER_ENV = (
    "CPATH",
    "C_INCLUDE_PATH",
    "GCC_EXEC_PREFIX",
    "COMPILER_PATH",
    "LIBRARY_PATH",
    "SOURCE_DATE_EPOCH",
)
#: How long ``cc --version`` may take.
_VERSION_TIMEOUT = 30

#: One message of gcc or clang: ``file:line[:column]: severity: message``.
_CC_LINE = re.compile(
    r"^(?P<file>[^:\n]+):(?P<line>[0-9]+):(?:(?P<column>[0-9]+):)?"
    r" (?P<severity>fatal error|error|warning|note): (?P<message>.*)$"
)
_SEVERITIES = {
    "fatal error": Severity.ERROR,
    "error": Severity.ERROR,
    "warning": Severity.WARNING,
    "note": Severity.NOTE,
}
#: A message with no location that still says what failed (the linker's).
#: A line of gcc's source excerpt under a message (`` 73 | int x;``, ``    |   ^``).
_CARET = re.compile(r"^\s*[0-9]*\s*\|")
#: A warning with no location (the linker's ``ld: warning: ...``).
_LOOSE_WARNING = re.compile(r"\bwarning: ")
_LOCATIONLESS = re.compile(r"\berror\b|undefined reference|multiple definition", re.IGNORECASE)

_LEVELS = {
    "ran": style.Level.OK,
    "up-to-date": style.Level.OK,
    "would-run": style.Level.SKIP,
    "skipped": style.Level.SKIP,
    "stale": style.Level.FAIL,
    "failed": style.Level.FAIL,
}


def _plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def parse_compiler_output(
    output: str, project: Path, cwd: Path, *, failed: bool
) -> list[Diagnostic]:
    """The ``build.cc`` diagnostics of one compiler run's output.

    Each ``file:line:col: severity: message`` line is one diagnostic located
    relative to ``project`` (a relative ``file`` is taken from ``cwd``). When
    the run ``failed``, a line with no location that names an error (the
    linker's ``undefined reference``) is an error with no location, and so is
    the output's last line when nothing else was found, so a failure always
    says something.
    """
    found: list[Diagnostic] = []
    loose: list[str] = []
    warnings: list[str] = []
    for raw in output.splitlines():
        line = raw.rstrip()
        match = _CC_LINE.match(line)
        if match is None:
            if _CARET.match(line):  # gcc's source excerpt: "  73 | code"
                continue
            if failed and line.strip() and _LOCATIONLESS.search(line):
                loose.append(line.strip())
            elif _LOOSE_WARNING.search(line):
                warnings.append(line.strip())
            continue
        path = absolute(cwd / match.group("file"))
        column = match.group("column")
        found.append(
            Diagnostic(
                _SEVERITIES[match.group("severity")],
                "build.cc",
                match.group("message"),
                location=Location(
                    show_path(path, project),
                    int(match.group("line")),
                    None if column is None else int(column),
                ),
            )
        )
    found += [Diagnostic(Severity.ERROR, "build.cc", m) for m in loose]
    found += [Diagnostic(Severity.WARNING, "build.cc", m) for m in warnings]
    if failed and not any(d.severity is Severity.ERROR for d in found):
        last = next((x.strip() for x in reversed(output.splitlines()) if x.strip()), "")
        found.append(
            Diagnostic(Severity.ERROR, "build.cc", last or "the compiler failed with no message")
        )
    return found


@dataclass(frozen=True)
class Compiler:
    """The compiler: as asked for, its absolute path and the first line of
    its ``--version``."""

    name: str
    path: str
    version: str


@dataclass
class _Run:
    """What one build reports, filled in stage by stage."""

    stages: dict[str, str] = field(default_factory=lambda: dict.fromkeys(STAGES, "skipped"))
    commands: list[list[str]] = field(default_factory=list)
    diagnostics: list[Diagnostic] = field(default_factory=list)
    artifact: dict[str, str] | None = None
    up_to_date: bool = False


def find_compiler(cli: str | None, env: Mapping[str, str]) -> Compiler:
    if cli == "":
        raise CliError("usage.invalid-value", "--cc is empty", "pass gcc or clang, or a path")
    name = cli or env.get("CC", "") or "gcc"
    path = shutil.which(name)
    hint = (
        "install gcc or clang, or name the compiler with --cc or CC (one program name or"
        " path, no arguments)"
    )
    if path is None:
        raise CliError("sdk.cc-not-found", f"compiler {name} not found", hint)
    try:
        proc = subprocess.run(
            [path, "--version"],
            capture_output=True,
            text=True,
            errors="replace",
            stdin=subprocess.DEVNULL,
            env={**env, "LC_ALL": "C"},
            timeout=_VERSION_TIMEOUT,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise CliError("sdk.cc-not-found", f"cannot run {name} --version: {exc}", hint) from None
    lines = [x.strip() for x in proc.stdout.splitlines() if x.strip()]
    if proc.returncode != 0 or not lines:
        raise CliError("sdk.cc-not-found", f"{name} --version failed: not a compiler", hint)
    return Compiler(name, os.path.abspath(path), lines[0])


def require_core_library(sdk: Sdk) -> Path:
    """The SDK's ``libmmt_core`` shared object (``mmt_plugin.sdk.registry``),
    linked into the plugin so ``-z defs`` resolves the SDK functions."""
    core = core_library(sdk)
    if core is None:
        raise CliError(
            "sdk.invalid-prefix",
            f"{sdk.prefix}/dpi/lib has no libmmt_core shared object: the plugin cannot be linked",
            "pass the prefix of a complete mmt-dpi install with --sdk or MMT_BASE",
        )
    return Path(core)


def kill_group(proc: subprocess.Popen[str]) -> None:
    """Kill the compiler's process group (the driver and what it started)."""
    with contextlib.suppress(ProcessLookupError, PermissionError):
        os.killpg(proc.pid, signal.SIGKILL)
    with contextlib.suppress(Exception):
        proc.wait()


def run_compiler(argv: Sequence[str], cwd: Path, ctx: Context) -> tuple[int, str]:
    """Run one compiler command in its own process group: its exit code and
    its output (stdout and stderr). Any exception, SIGINT included, kills
    the group before it propagates."""
    ctx.log(shlex.join(argv))
    proc = subprocess.Popen(
        list(argv),
        cwd=cwd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        errors="replace",
        env={**os.environ, "LC_ALL": "C"},
        start_new_session=True,
    )
    try:
        output, _ = proc.communicate()
    except BaseException:
        kill_group(proc)
        raise
    if output and ctx.verbose:
        ctx.stderr.write(output if output.endswith("\n") else output + "\n")
        ctx.stderr.flush()
    return proc.returncode, output


def _sdk_headers(sdk: Sdk) -> dict[str, str]:
    include = Path(sdk.include_dir)
    return {
        p.relative_to(include).as_posix(): sha256_file(p) or ""
        for p in sorted(include.rglob("*.h"))
        if p.is_file()
    }


def _read_depfile(path: Path, cwd: Path) -> list[Path]:
    """The files a ``-MD -MF`` dependency file lists (absolute), after the
    target; empty when it cannot be read."""
    try:
        text = path.read_text(encoding="utf-8", errors="surrogateescape")
    except OSError:
        return []
    text = text.replace("\\\n", " ")
    _, sep, rest = text.partition(": ")
    if not sep:
        return []
    words = re.split(r"(?<!\\)\s+", rest.strip())
    found = []
    for word in words:
        word = word.replace("\\ ", " ").replace("\\#", "#").replace("$$", "$")
        if word and not word.endswith(":"):
            found.append(Path(os.path.normpath(os.path.join(cwd, word))))
    return found


def _dependencies_unchanged(
    stamp: Mapping[str, Any], generation: Generation, generated_dir: Path
) -> bool:
    """Whether every file the last build's compiler read (its dependency
    files: user headers anywhere, the SDK's and the system's) still has the
    sha256 recorded then. The generated files are compared with what this
    run generates, since a dry run does not write them."""
    recorded = stamp.get("dependencies")
    if not isinstance(recorded, dict) or not recorded:
        return False
    generated = {str(generated_dir / f.name): sha256_bytes(f.data) for f in generation.files}
    for path, sha in recorded.items():
        current = generated[path] if path in generated else sha256_file(Path(path))
        if current is None or current != sha:
            return False
    return True


def _read_stamp(path: Path) -> dict[str, Any] | None:
    try:
        stamp = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(stamp, dict) or stamp.get("stamp_version") != STAMP_VERSION:
        return None
    return stamp


class BuildCommand:
    """``mmt-plugin build [MODEL]``: compile ``<build-dir>/mmtp_<label>.so``.

    ``pkg_config_dirs`` and ``default_prefix`` are passed to SDK detection
    (tests point them at temporary directories). ``cflags`` and ``ldflags``
    replace ``CFLAGS`` and ``LDFLAGS`` (``test --sanitize`` builds with the
    sanitizers into another build directory); they are part of the input
    hash, like the defaults."""

    name = "build"
    exit_codes: tuple[ExitCode, ...] = (
        ExitCode.MODEL,
        ExitCode.SDK,
        ExitCode.BUILD,
        ExitCode.STATE,
    )

    def __init__(
        self,
        *,
        pkg_config_dirs: Sequence[str] | None = None,
        default_prefix: str = DEFAULT_PREFIX,
        cflags: Sequence[str] = CFLAGS,
        ldflags: Sequence[str] = LDFLAGS,
    ) -> None:
        self.pkg_config_dirs = pkg_config_dirs
        self.default_prefix = default_prefix
        self.cflags = tuple(cflags)
        self.ldflags = tuple(ldflags)

    def register(self, subparsers: Subparsers) -> argparse.ArgumentParser:
        parser = subparsers.add_parser(
            self.name,
            help="compile build/mmtp_<label>.so",
            description=(
                "Compile the plugin <build-dir>/mmtp_<label>.so from the generated sources\n"
                "(<project>/generated/, regenerated first when stale) and the user code\n"
                "(<project>/src/*.c), against an installed mmt-dpi SDK, with fixed hardened\n"
                "flags and -Wall -Wextra -Werror. Every hook the generated header declares\n"
                "must be defined in src/. A build whose inputs are unchanged is a no-op."
            ),
            epilog=(
                "examples:\n"
                "  mmt-plugin build model.pdl --sdk $HOME/mmt/opt/mmt\n"
                "  mmt-plugin build model.pdl --dry-run   # print the compiler commands"
            ),
        )
        parser.add_argument(
            "model",
            nargs="?",
            metavar="MODEL",
            help="a PDL v1 model file (default: <project>/plugin.yaml, which needs #24)",
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
            help="the mmt-dpi prefix to build against (default: MMT_BASE, mmt-dpi.pc, /opt/mmt)",
        )
        parser.add_argument(
            "--sdk-profile",
            metavar="VERSION",
            help=(f"the SDK profile, e.g. 1.10.2 (default: {ENV_PROFILE}, else the SDK's own)"),
        )
        parser.add_argument(
            "--cc", metavar="CC", help="the compiler, gcc or clang (default: CC, else gcc)"
        )
        parser.add_argument(
            "--build-dir",
            metavar="DIR",
            help="the output directory of mmtp_<label>.so (default: <project>/build/)",
        )
        parser.add_argument(
            "--rebuild", action="store_true", help="compile even when the inputs are unchanged"
        )
        parser.add_argument(
            "--no-deps",
            action="store_true",
            help="do not regenerate stale generated files: exit 7 instead",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="print the compiler command lines, write nothing",
        )
        parser.add_argument(
            "--strict", action="store_true", help="fail on warnings, with their class's code"
        )
        return parser

    # --- stages ---

    def _setup(
        self, args: argparse.Namespace, ctx: Context
    ) -> tuple[Sdk, ProfileChoice, Path, Compiler]:
        env = os.environ
        sdk = require_sdk(
            args.sdk, env, pkg_config_dirs=self.pkg_config_dirs, default_prefix=self.default_prefix
        )
        choice = resolve_profile(args.sdk_profile, env, None, sdk)
        ctx.log(f"SDK {sdk.prefix} ({sdk.source.value}), profile {choice.profile.version}")
        core = require_core_library(sdk)
        cc = find_compiler(args.cc, env)
        ctx.log(f"compiler {cc.path}: {cc.version}")
        return sdk, choice, core, cc

    def _generate(
        self,
        args: argparse.Namespace,
        ctx: Context,
        sdk: Sdk,
        choice: ProfileChoice,
        run: _Run,
    ) -> CliError | None:
        """The ``generate`` stage: ``generate --check``, then ``generate``
        when stale (not with ``--no-deps`` or ``--dry-run``)."""
        command = GenerateCommand(
            pkg_config_dirs=self.pkg_config_dirs, default_prefix=self.default_prefix
        )

        def generate(check: bool) -> Outcome:
            ns = argparse.Namespace(
                model=args.model,
                output=None,
                model_format=args.model_format,
                sdk=sdk.prefix,
                sdk_profile=choice.profile.version,
                check=check,
                dry_run=False,
                force=False,
                strict=False,
            )
            outcome = command.run(ns, ctx)
            # The model's own diagnostics are build's already; keep the
            # state ones (state.kept, state.modified, ...).
            run.diagnostics += [d for d in outcome.diagnostics if d.code.startswith("state.")]
            return outcome

        checked = generate(check=True)
        if checked.error is None:
            run.stages["generate"] = "up-to-date"
            return None
        if checked.error.code != "state.stale":
            run.stages["generate"] = "failed"
            return checked.error
        if args.no_deps:
            run.stages["generate"] = "stale"
            return CliError(
                "state.stale",
                "the generated files or plugin.lock are not up to date (--no-deps)",
                "run mmt-plugin generate first, or build without --no-deps",
            )
        if args.dry_run:
            run.stages["generate"] = "would-run"
            return None
        run.diagnostics = [d for d in run.diagnostics if not d.code.startswith("state.")]
        generated = generate(check=False)
        if generated.error is not None:
            run.stages["generate"] = "failed"
            return generated.error
        ctx.log("generated files updated")
        run.stages["generate"] = "ran"
        return None

    def run(self, args: argparse.Namespace, ctx: Context) -> Outcome:
        project = absolute(ctx.project)
        if args.model == "-":
            raise CliError(
                "usage.invalid-value",
                "build reads MODEL from a file, not stdin: it compares the generated files"
                " with it",
                "pass the model file as MODEL",
            )
        model = read_model(args.model, args.model_format, project)
        sdk, choice, core, cc = self._setup(args, ctx)
        context = {"sdk": sdk_context(sdk, choice)}
        run = _Run(diagnostics=list(choice.diagnostics))
        cflags = [f"-std={choice.profile.c_std}", *self.cflags]
        ldflags = list(self.ldflags)
        build_dir = (
            absolute(args.build_dir) if args.build_dir is not None else project / DEFAULT_BUILD_DIR
        )

        generation, found, error = make_generation(model.name, model.data, choice)
        run.diagnostics += found
        label = generation.label.lower() if generation is not None else None

        def outcome(error: CliError | None) -> Outcome:
            commands = [shlex.join(c) for c in run.commands]
            result: dict[str, Any] = {
                "model": model.name,
                "profile": choice.profile.version,
                "build_dir": show_path(build_dir, project),
                "stages": [{"name": n, "status": s} for n, s in run.stages.items()],
                "artifact": run.artifact,
                "cc": {"path": cc.path, "version": cc.version},
                "cflags": cflags,
                "ldflags": ldflags,
                "commands": commands,
                "up_to_date": run.up_to_date,
                "dry_run": bool(args.dry_run),
            }
            records: list[tuple[str, ...]] = [(n, s) for n, s in run.stages.items()]
            if run.artifact is not None:
                records.append(("artifact", run.artifact["path"], run.artifact["sha256"]))
            if args.dry_run:
                records += [("command", c) for c in commands]
            size = None
            if run.artifact is not None:
                with contextlib.suppress(OSError):
                    size = (project / run.artifact["path"]).stat().st_size

            def view(st: StreamStyle) -> str:
                return _view(label or "?", result, size, st)

            return Outcome(
                result=result,
                records=records,
                view=view,
                diagnostics=run.diagnostics,
                error=error,
                context=context,
            )

        if error is not None or generation is None:
            run.stages["generate"] = "failed"
            return outcome(error)
        warnings = [d for d in run.diagnostics if d.severity is Severity.WARNING]
        if args.strict and warnings:
            first = warnings[0]
            return outcome(
                CliError(
                    first.code,
                    f"--strict: {_plural(len(warnings), 'warning')} ({first.code})",
                    "fix the warnings, or run without --strict",
                )
            )

        error = self._generate(args, ctx, sdk, choice, run)
        if error is not None:
            return outcome(error)
        return outcome(
            self._compile_and_link(
                args,
                ctx,
                project,
                build_dir,
                generation,
                sdk,
                choice.profile.version,
                core,
                cc,
                cflags,
                ldflags,
                run,
            )
        )

    def _compile_and_link(
        self,
        args: argparse.Namespace,
        ctx: Context,
        project: Path,
        build_dir: Path,
        generation: Generation,
        sdk: Sdk,
        profile: str,
        core: Path,
        cc: Compiler,
        cflags: list[str],
        ldflags: list[str],
        run: _Run,
    ) -> CliError | None:
        label = generation.label.lower()
        generated_dir = project / DEFAULT_OUTPUT
        user_dir = project / USER_DIR
        artifact = build_dir / f"mmtp_{label}.so"
        stamp_path = build_dir / f".mmtp_{label}.build.json"
        temporary = build_dir / f".mmtp_{label}.so.tmp"
        object_dir = build_dir / OBJECT_DIR

        generated = [
            (generated_dir / f.name, f.data) for f in generation.files if f.name.endswith(".c")
        ]
        user = sorted(p for p in user_dir.glob("*.c") if p.is_file()) if user_dir.is_dir() else []
        user_headers = (
            sorted(p for p in user_dir.glob("*.h") if p.is_file()) if user_dir.is_dir() else []
        )
        sources = [
            (path, object_dir / "generated" / f"{path.stem}.o") for path, _ in generated
        ] + [(path, object_dir / USER_DIR / f"{path.stem}.o") for path in user]
        includes = ["-I", str(generated_dir), "-I", str(user_dir), "-I", sdk.include_dir]
        compile_commands = [
            [
                cc.path,
                *cflags,
                *includes,
                "-MD",
                "-MF",
                str(obj.with_suffix(".d")),
                "-c",
                str(src),
                "-o",
                str(obj),
            ]
            for src, obj in sources
        ]
        link_command = [
            cc.path,
            *ldflags,
            *(str(obj) for _, obj in sources),
            str(core),
            "-o",
            str(temporary),
        ]

        # The input hash: what the plugin is a function of.
        files = {
            show_path(generated_dir / f.name, project): sha256_bytes(f.data)
            for f in generation.files
        }
        for p in [*user, *user_headers]:
            files[show_path(p, project)] = sha256_file(p) or ""
        inputs = {
            "tool": __version__,
            "cc": {"path": cc.path, "version": cc.version},
            "cflags": cflags,
            "ldflags": ldflags,
            "profile": profile,
            "sdk": {
                "prefix": sdk.prefix,
                "version": sdk.version,
                "core": {"path": str(core), "sha256": sha256_file(core)},
                "headers": _sdk_headers(sdk),
            },
            "files": files,
            "commands": [*compile_commands, link_command],
            "env": {k: os.environ.get(k) for k in COMPILER_ENV},
        }
        digest = sha256_bytes(json.dumps(inputs, sort_keys=True).encode("utf-8"))
        current = sha256_file(artifact) if artifact.is_file() else None
        stamp = _read_stamp(stamp_path)
        if (
            not args.rebuild
            and current is not None
            and stamp is not None
            and stamp.get("inputs") == digest
            and stamp.get("artifact_sha256") == current
            and run.stages["generate"] != "would-run"
            and _dependencies_unchanged(stamp, generation, generated_dir)
        ):
            for name in ("compile", "hooks", "link"):
                run.stages[name] = "up-to-date"
            run.up_to_date = True
            run.artifact = {"path": show_path(artifact, project), "sha256": current}
            ctx.log(f"{show_path(artifact, project)} is up to date")
            return None

        if args.dry_run:
            run.commands = [*compile_commands, link_command]
            for name in ("compile", "hooks", "link"):
                run.stages[name] = "would-run"
            return None

        header = show_path(generated_dir / generation.header, project)
        try:
            with ctx.progress(f"compiling mmtp_{label}.so"):
                return self._compile_link_steps(
                    ctx,
                    project,
                    generation,
                    sources,
                    user,
                    compile_commands,
                    link_command,
                    temporary,
                    artifact,
                    stamp_path,
                    digest,
                    header,
                    run,
                )
        finally:
            temporary.unlink(missing_ok=True)

    def _compile_link_steps(
        self,
        ctx: Context,
        project: Path,
        generation: Generation,
        sources: list[tuple[Path, Path]],
        user: list[Path],
        compile_commands: list[list[str]],
        link_command: list[str],
        temporary: Path,
        artifact: Path,
        stamp_path: Path,
        digest: str,
        header: str,
        run: _Run,
    ) -> CliError | None:
        failed: list[str] = []
        for (src, obj), command in zip(sources, compile_commands, strict=True):
            obj.parent.mkdir(parents=True, exist_ok=True)
            obj.unlink(missing_ok=True)
            run.commands.append(command)
            code, output = run_compiler(command, project, ctx)
            run.diagnostics += parse_compiler_output(output, project, project, failed=code != 0)
            if code != 0:
                failed.append(show_path(src, project))
        if failed:
            run.stages["compile"] = "failed"
            return CliError(
                "build.compile-failed",
                f"cannot compile {', '.join(failed)}",
                "fix the errors in the diagnostics, then re-run build",
            )
        run.stages["compile"] = "ran"

        user_objects = [obj for src, obj in sources if src in user]
        impl = impl_name(generation.label)
        try:
            missing = missing_hooks(generation.hooks, user_objects)
        except (ObjectFormatError, OSError) as exc:
            run.stages["hooks"] = "failed"
            return CliError(
                "build.compile-failed",
                f"cannot read the symbols of the compiled user code: {exc}",
                f"check that --cc builds ELF objects; {impl} holds the hooks",
            )
        if missing:
            run.stages["hooks"] = "failed"
            error, found = missing_hook_error(missing, impl, header)
            if not user:
                error = CliError(
                    error.code,
                    f"{error.message}: there is no {USER_DIR}/*.c",
                    f"create {impl} (mmt-plugin init writes a scaffold that defines every hook)",
                )
            run.diagnostics += found
            return error
        run.stages["hooks"] = "ran"

        temporary.parent.mkdir(parents=True, exist_ok=True)
        temporary.unlink(missing_ok=True)
        run.commands.append(link_command)
        code, output = run_compiler(link_command, project, ctx)
        run.diagnostics += parse_compiler_output(output, project, project, failed=code != 0)
        if code != 0 or not temporary.is_file():
            run.stages["link"] = "failed"
            return CliError(
                "build.link-failed",
                f"cannot link {show_path(artifact, project)}",
                "fix the errors in the diagnostics, then re-run build",
            )
        os.replace(temporary, artifact)
        sha = sha256_file(artifact) or ""
        dependencies: dict[str, str] = {}
        for _, obj in sources:
            for dep in _read_depfile(obj.with_suffix(".d"), project):
                # A file the compiler read but that cannot be hashed (a path
                # misparsed) never matches: an extra rebuild, never a false
                # no-op.
                dependencies[str(dep)] = sha256_file(dep) or "unreadable"
        stamp = {
            "stamp_version": STAMP_VERSION,
            "inputs": digest,
            "artifact_sha256": sha,
            "dependencies": dependencies,
        }
        write_atomic(stamp_path, json.dumps(stamp, sort_keys=True, indent=2) + "\n")
        run.stages["link"] = "ran"
        run.artifact = {"path": show_path(artifact, project), "sha256": sha}
        return None


def _view(label: str, result: Mapping[str, Any], size: int | None, st: StreamStyle) -> str:
    """The styled output: a box ``build <label>`` with the stages, then the
    artifact, its size, the compiler and the flags."""
    rows = [
        [s["name"], style.status(s["status"], _LEVELS[s["status"]], style=st)]
        for s in result["stages"]
    ]
    table = style.table(["stage", "status"], rows, style=st, width=st.width - 4)
    facts: list[list[str]] = []
    artifact = result["artifact"]
    if artifact is not None:
        facts.append(["artifact", artifact["path"]])
        facts.append(["sha256", artifact["sha256"]])
        if size is not None:
            facts.append(["size", f"{size} bytes"])
    facts.append(["cc", f"{result['cc']['path']} ({result['cc']['version']})"])
    facts.append(["cflags", " ".join(result["cflags"])])
    facts.append(["ldflags", " ".join(result["ldflags"])])
    facts += [["command", c] for c in result["commands"] if result["dry_run"]]
    body = [*table, "", *style.table(None, facts, style=st, width=st.width - 4)]
    if result["up_to_date"]:
        footer = "up to date"
    elif result["dry_run"]:
        footer = (
            f"dry run{style.glyphs(st).separator}{_plural(len(result['commands']), 'command')}"
        )
    elif artifact is not None:
        footer = "built"
    else:
        failed = [s["name"] for s in result["stages"] if s["status"] in ("failed", "stale")]
        footer = f"{failed[0]} failed" if failed else "not built"
    return style.box(f"build {label}", body, style=st, footer=footer)
