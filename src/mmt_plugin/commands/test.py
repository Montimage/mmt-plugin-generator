"""``mmt-plugin test [PACKETS...]`` (``docs/design/cli.md``, sections 4, 5,
6, 8 and 10).

Runs packet tests (corpus schema 1, ``tests/corpus/README.md``) against the
plugin. ``PACKETS`` are files, directories (their ``*.yaml``) or globs;
the default is ``<project>/tests/*.yaml``. The model is ``--model``
(default ``<project>/plugin.yaml``), as ``build``'s ``MODEL``.

Stages, reported in ``result.stages`` (``ran``, ``up-to-date``, ``failed``,
``stale`` or ``skipped``), each stopping the run with its class's exit code:

0. read the model, find the SDK, the compiler and the profile (as
   ``build``), and read every packet test (a bad one is
   ``model.bad-packet-test``, exit 3); no packet test at all is the warning
   ``test.no-packets``;
1. ``build``: ``mmt-plugin build`` (``mmt_plugin.commands.build``), a no-op
   when the plugin is up to date; with ``--no-deps``, a plugin that is not
   up to date is ``state.stale`` (exit 7) and nothing is built. Then the
   other plugins plugin.yaml's ``plugins`` names (``mmt_plugin.plugins``,
   a parent first; a bad entry is ``model.bad-plugin``, exit 3): each
   project's is built the same way, in its own directory (its own
   ``sdk.profile``), and each one is loaded, in that order, before the
   plugin in every harness run (``result.plugins``);
2. ``harness``: the host harness (``mmt_plugin.testing.harness``) is
   generated into ``<build-dir>/test/harness.c`` and compiled against the
   SDK (``build.harness-failed``, exit 5);
3. ``packets``: the harness loads the plugin next to the SDK's
   ``libmmt_tcpip.so`` (and the named plugins), attaches it to Ethernet, and checks each packet's
   classification, next protocol and attribute values. A test with
   ``through`` runs a second time (its own ``result.packets`` entry, with
   ``through``): behind the lower layers its selector names
   (``mmt_plugin.testing.frames``), through mmt-dpi's stack, so the plugin's
   own parent classification must find it, directly above the selector's
   protocol and at the offset those layers end at (``<parent>``); its next
   protocol is not checked there. A session test
   (``mmt_plugin.testing.session``) runs its packets, one TCP connection,
   in order in a harness of its own, so the plugin keeps its session state
   from one packet to the next: one ``result.packets`` entry, with
   ``session`` (its packet count), each failure with the ``packet`` (the
   step) it is in. A mismatch is ``test.packet-failed``, a crash or a
   timeout ``test.crash`` (exit 6); the harness restarts after a crash, so
   every packet is reported (a session test that crashes is not run
   again). ``--fail-fast`` stops at the first failing packet (the rest are
   ``skipped``);
4. ``sanitize`` (``--sanitize``): the plugin is built again with ASan and
   UBSan into ``<build-dir>/sanitize/``, and a sanitized harness runs each
   packet, then its ``--fuzz-count`` truncated and random packets
   (``mmt_plugin.testing.fuzz``, seeded by ``--seed``); a test with
   ``through`` runs them again behind its lower layers. A session test runs
   as it is, then in corrupted copies (``mutate_frames``), each in a
   harness of its own, until they make ``--fuzz-count`` packets. Any
   sanitizer report, crash or timeout is ``test.crash`` (exit 6);
5. ``bench`` (``--bench``): packets per second of the plugin, and of an
   empty plugin with the same id and name (the baseline), in samples, over
   the packet tests (not the session tests). Advisory: a bench that cannot
   run is the warning ``test.bench-failed``, and the exit code never
   changes.

``--strict`` fails on a warning of the model, the build or the tests (not
the bench). Progress (a meter of the packets) shows only on a terminal.
"""

from __future__ import annotations

import argparse
import dataclasses
import glob
import json
import math
import os
import re
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from mmt_plugin.codegen import Generation
from mmt_plugin.commands import Context, Outcome, Subparsers
from mmt_plugin.commands.build import (
    CFLAGS,
    LDFLAGS,
    BuildCommand,
    Compiler,
    find_compiler,
    parse_compiler_output,
    require_core_library,
    run_compiler,
)
from mmt_plugin.commands.generate import make_generation
from mmt_plugin.commands.modelio import (
    FORMATS,
    PROJECT_FILE,
    ModelInput,
    absolute,
    parse_model,
    read_model,
    show_path,
)
from mmt_plugin.diagnostics import CliError, Diagnostic, Location, Severity
from mmt_plugin.exitcodes import ExitCode
from mmt_plugin.fsio import sha256_bytes, write_atomic
from mmt_plugin.pdl import Model
from mmt_plugin.plugins import NamedPlugin, PluginError, resolve
from mmt_plugin.sdk.detect import DEFAULT_PREFIX, Sdk, require_sdk
from mmt_plugin.sdk.profile import DATA_TYPE_GROUP, Profile
from mmt_plugin.sdk.resolve import ENV_PROFILE, ProfileChoice, resolve_profile, sdk_context
from mmt_plugin.testing import harness as harness_mod
from mmt_plugin.testing.frames import build_frame
from mmt_plugin.testing.fuzz import fuzz_packets, mutate_frames
from mmt_plugin.testing.packets import (
    ExpectedParent,
    Failure,
    PacketTest,
    PacketTestError,
    check,
    harness_lengths,
)
from mmt_plugin.testing.session import (
    SessionTest,
    build_frames,
    check_frame,
    load_test,
)
from mmt_plugin.ui import style
from mmt_plugin.ui.streams import StreamStyle

__all__ = [
    "BENCH_PACKETS",
    "BENCH_SAMPLES",
    "DIAGNOSTIC_CODES",
    "SANITIZE_CFLAGS",
    "SANITIZE_LDFLAGS",
    "STAGES",
    "TestCommand",
    "packet_paths",
]

#: The codes this command reports itself.
DIAGNOSTIC_CODES = (
    "model.bad-packet-test",
    "model.bad-plugin",
    "build.harness-failed",
    "test.packet-failed",
    "test.crash",
    "test.load-failed",
    "test.no-packets",
    "test.bench-failed",
)

STAGES = ("build", "harness", "packets", "sanitize", "bench")
TESTS_DIR = "tests"
TEST_DIR = "test"
SANITIZE_DIR = "sanitize"

#: The sanitized build: ASan and UBSan, every UBSan report fatal, with
#: frame pointers and debug lines for the reports; no ``_FORTIFY_SOURCE``
#: (it hides out-of-bounds accesses from ASan). The link has no ``-z defs``:
#: clang leaves the sanitizer runtime to the program that loads the plugin.
SANITIZE = ("-fsanitize=address,undefined", "-fno-sanitize-recover=all")
SANITIZE_CFLAGS = (
    "-O1",
    "-g",
    "-fno-omit-frame-pointer",
    "-fPIC",
    *SANITIZE,
    "-Wall",
    "-Wextra",
    "-Werror",
)
SANITIZE_LDFLAGS = ("-shared", *SANITIZE)
#: The harness's own flags (the plugin's, without -fPIC).
HARNESS_CFLAGS = ("-O2", "-Wall", "-Wextra", "-Werror")
HARNESS_SANITIZE_CFLAGS = ("-O1", "-g", "-fno-omit-frame-pointer", *SANITIZE, "-Wall", "-Wextra")

#: The bench: about this many packets per sample, this many samples.
BENCH_PACKETS = 20000
BENCH_SAMPLES = 10
#: At most this many crashes are reported before the fuzzing stops.
MAX_CRASHES = 10
#: A harness run may take this long, plus this much per packet (seconds).
TIMEOUT = 60.0
TIMEOUT_PER_PACKET = 0.05

_GLOB = re.compile(r"[*?[]")
_SONAME = re.compile(r"^(libmmt_core\.so\.[0-9]+)(\.[0-9]+)+$")

_LEVELS = {
    "pass": style.Level.OK,
    "fail": style.Level.FAIL,
    "crash": style.Level.FAIL,
    "skipped": style.Level.SKIP,
}


def _plural(n: int, word: str, words: str | None = None) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {words or word + 's'}"


def _non_negative(text: str) -> int:
    try:
        value = int(text, 10)
    except ValueError:
        raise argparse.ArgumentTypeError(f"not an integer: {text!r}") from None
    if value < 0:
        raise argparse.ArgumentTypeError(f"must be >= 0: {value}")
    return value


def _positive(text: str) -> int:
    value = _non_negative(text)
    if value == 0:
        raise argparse.ArgumentTypeError("must be >= 1")
    return value


def packet_paths(given: Sequence[str], project: Path) -> list[Path]:
    """The packet test files of ``PACKETS`` (``given``): a file as is, a
    directory's ``*.yaml``, a glob's matches (relative to the current
    directory), in order, each once; with nothing given,
    ``<project>/tests/*.yaml`` (none when it does not exist). A glob that
    matches nothing is a usage error."""
    if not given:
        tests = project / TESTS_DIR
        return sorted(p for p in tests.glob("*.yaml") if p.is_file()) if tests.is_dir() else []
    found: list[Path] = []
    for item in given:
        if _GLOB.search(item):
            matches = sorted(absolute(m) for m in glob.glob(item))
            if not matches:
                raise CliError(
                    "usage.invalid-value",
                    f"PACKETS: no file matches {item}",
                    "pass packet test files, directories or globs that match",
                )
            found += matches
        else:
            path = absolute(item)
            if path.is_dir():
                found += sorted(p for p in path.glob("*.yaml") if p.is_file())
            else:
                found.append(path)
    unique: list[Path] = []
    for path in found:
        if path not in unique:
            unique.append(path)
    return unique


#: A packet test or a session test.
_Test = PacketTest | SessionTest


@dataclass
class _Packet:
    """One packet test's result: the harness's attachment, or the run
    ``through`` the test's parent selector; or one session test's
    (``frames``: its packets)."""

    test: _Test
    through: bool = False
    status: str = "skipped"
    checked: int = 0
    failures: list[Failure] = field(default_factory=list)
    frames: int = 0

    @property
    def session(self) -> SessionTest | None:
        return self.test if isinstance(self.test, SessionTest) else None

    @property
    def name(self) -> str:
        """The id, and the parent of the run through it."""
        if self.through and isinstance(self.test, PacketTest) and self.test.through is not None:
            return f"{self.test.id} through {self.test.through.text}"
        return self.test.id

    def record(self, n: int) -> bytes | harness_mod.Record:
        """The harness record of this run (``n``: its place in the file)."""
        assert isinstance(self.test, PacketTest)
        return _record(self.test, self.through, self.test.data, n)

    def to_json(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "id": self.test.id,
            "file": self.test.file,
            "status": self.status,
            "attributes": self.checked,
            "failures": [f.to_json() for f in self.failures],
        }
        if self.through and isinstance(self.test, PacketTest) and self.test.through is not None:
            out["through"] = self.test.through.text
        if self.session is not None:
            out["session"] = self.frames
        return out

    def detail(self) -> str:
        if self.status == "skipped":
            return "not run"
        if not self.failures:
            return _plural(self.checked, "attribute")
        first = self.failures[0]
        where = "" if first.packet is None else f"packets[{first.packet}] "
        if self.status == "crash":
            text = f"{where}crash: {first.actual}"
        else:
            text = f"{where}{first.attribute}: expected {first.expected}, got {first.actual}"
        more = len(self.failures) - 1
        return f"{text} (+{more} more)" if more else text


def _record(test: PacketTest, through: bool, data: bytes, n: int) -> bytes | harness_mod.Record:
    """``data`` as the harness attaches it, or the ``n``-th frame of a run
    through ``test``'s parent."""
    if through and test.through is not None:
        return harness_mod.Record(build_frame(test.through, data, n), frame=True)
    return data


def _entries(tests: Sequence[_Test]) -> list[_Packet]:
    """The runs of ``tests``: each one, then its run through its parent."""
    out: list[_Packet] = []
    for test in tests:
        out.append(_Packet(test))
        if isinstance(test, PacketTest) and test.through is not None:
            out.append(_Packet(test, through=True))
    return out


def _expected_parent(profile: Profile, packet: _Packet) -> ExpectedParent | None:
    """Where the run through the parent (or a session test's) expects the
    plugin, or ``None``."""
    through = packet.test.through
    if not (packet.through or packet.session is not None) or through is None:
        return None
    parents = profile.parents
    return ExpectedParent(
        through.proto, parents.id_of(parents.id_for(through.proto)), through.offset
    )


@dataclass
class _Run:
    """What one test run reports, filled in stage by stage."""

    stages: dict[str, str] = field(default_factory=lambda: dict.fromkeys(STAGES, "skipped"))
    diagnostics: list[Diagnostic] = field(default_factory=list)
    packets: list[_Packet] = field(default_factory=list)
    sanitize: dict[str, Any] | None = None
    bench: dict[str, Any] | None = None
    build_up_to_date: bool = False
    #: ``result.plugins``: the named plugins, in load order.
    plugins: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class _Toolchain:
    """What compiling and running the harness needs."""

    sdk: Sdk
    profile: Profile
    cc: Compiler
    core: Path
    test_dir: Path
    project: Path
    #: The named plugins (plugin.yaml's ``plugins``), loaded before the plugin.
    extra: tuple[Path, ...] = ()

    @property
    def sdk_plugins(self) -> Path:
        return Path(self.sdk.prefix) / "plugins"

    def runtime_dir(self) -> Path:
        """A directory where ``libmmt_core``'s soname resolves to the SDK's
        library (the package's own links are absolute ``/opt/mmt`` paths)."""
        match = _SONAME.match(self.core.name)
        if match is None:
            return self.core.parent
        lib = self.test_dir / "lib"
        lib.mkdir(parents=True, exist_ok=True)
        link = lib / match.group(1)
        if not (link.is_symlink() and os.readlink(link) == str(self.core)):
            link.unlink(missing_ok=True)
            link.symlink_to(self.core)
        return lib


class TestCommand:
    """``mmt-plugin test [PACKETS...]``: run the packet tests.

    ``pkg_config_dirs`` and ``default_prefix`` are passed to SDK detection
    (tests point them at temporary directories)."""

    # Not a pytest test class, despite its name.
    __test__ = False

    name = "test"
    exit_codes: tuple[ExitCode, ...] = (
        ExitCode.MODEL,
        ExitCode.SDK,
        ExitCode.BUILD,
        ExitCode.TEST,
        ExitCode.STATE,
    )

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
            help="run the packet tests (tests/*.yaml) against the plugin",
            description=(
                "Build the plugin when it is stale, then load it with a generated host\n"
                "harness and check each packet test (corpus schema 1): the classification,\n"
                "the next protocol and every attribute value. --sanitize also runs\n"
                "truncated and random packets under ASan and UBSan; --bench reports packets\n"
                "per second against an empty plugin (advisory)."
            ),
            epilog=(
                "examples:\n"
                "  mmt-plugin test --model model.pdl --sdk $HOME/mmt/opt/mmt\n"
                "  mmt-plugin test --model model.pdl tests/corpus/models/dns/packets\n"
                "  mmt-plugin test --model model.pdl --sanitize --seed 42 --fuzz-count 5000"
            ),
        )
        parser.add_argument(
            "packets",
            nargs="*",
            metavar="PACKETS",
            help="packet test files, directories or globs (default: <project>/tests/*.yaml)",
        )
        parser.add_argument(
            "--model",
            metavar="MODEL",
            help="a plugin.yaml or PDL v1 model file (default: <project>/plugin.yaml)",
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
            help="the mmt-dpi prefix to test against (default: MMT_BASE, mmt-dpi.pc, /opt/mmt)",
        )
        parser.add_argument(
            "--sdk-profile",
            metavar="VERSION",
            help=f"the SDK profile, e.g. 1.10.2 (default: {ENV_PROFILE}, else the SDK's own)",
        )
        parser.add_argument(
            "--cc", metavar="CC", help="the compiler, gcc or clang (default: CC, else gcc)"
        )
        parser.add_argument(
            "--build-dir",
            metavar="DIR",
            help="the build directory of mmtp_<label>.so (default: <project>/build/)",
        )
        parser.add_argument(
            "--sanitize",
            action="store_true",
            help="rebuild with ASan/UBSan and also run truncated and random packets",
        )
        parser.add_argument(
            "--seed",
            type=_non_negative,
            default=0,
            metavar="N",
            help="the seed of the random packets: the same seed, the same packets (default: 0)",
        )
        parser.add_argument(
            "--fuzz-count",
            type=_positive,
            default=1000,
            metavar="N",
            help="truncated and random packets per test with --sanitize (default: 1000)",
        )
        parser.add_argument(
            "--bench",
            action="store_true",
            help="packets per second against an empty plugin (advisory: never fails)",
        )
        parser.add_argument(
            "--fail-fast", action="store_true", help="stop at the first failing packet"
        )
        parser.add_argument(
            "--no-deps",
            action="store_true",
            help="do not build a stale plugin: exit 7 instead",
        )
        parser.add_argument(
            "--strict", action="store_true", help="fail on warnings, with their class's code"
        )
        return parser

    # --- stage 0 ---

    def _load_tests(
        self, args: argparse.Namespace, project: Path, profile: Profile, run: _Run
    ) -> tuple[list[_Test], CliError | None]:
        types = {c.name for c in profile.constants if c.group == DATA_TYPE_GROUP}
        tests: list[_Test] = []
        errors: list[Diagnostic] = []
        for path in packet_paths(args.packets, project):
            try:
                tests.append(load_test(path, show_path(path, project), types))
            except PacketTestError as exc:
                errors.append(exc.diagnostic)
        seen: dict[str, str] = {}
        for test in tests:
            if test.id in seen:
                errors.append(
                    Diagnostic(
                        Severity.ERROR,
                        "model.bad-packet-test",
                        f"packet test id {test.id!r} is also the id of {seen[test.id]}",
                        hint="give each packet test its own id",
                        location=Location(test.file),
                    )
                )
            seen.setdefault(test.id, test.file)
        run.diagnostics += errors
        if errors:
            return tests, CliError(
                "model.bad-packet-test",
                f"{_plural(len(errors), 'packet test')} cannot be read",
                "fix the packet tests in the diagnostics (tests/corpus/README.md, Packet files)",
            )
        if not tests:
            where = "PACKETS" if args.packets else f"{TESTS_DIR}/*.yaml"
            run.diagnostics.append(
                Diagnostic(
                    Severity.WARNING,
                    "test.no-packets",
                    f"no packet test found ({where}): nothing was tested",
                    hint="add packet tests (tests/corpus/README.md, Packet files)",
                )
            )
        return tests, None

    # --- stage 1 ---

    def _build(
        self,
        args: argparse.Namespace,
        ctx: Context,
        sdk: Sdk,
        choice: ProfileChoice,
        cc: Compiler,
        build_dir: Path,
        run: _Run,
        *,
        sanitize: bool = False,
    ) -> CliError | None:
        """``build`` (``sanitize``: the sanitized variant into
        ``<build-dir>/sanitize``); its diagnostics are this run's."""
        if sanitize:
            command = BuildCommand(
                pkg_config_dirs=self.pkg_config_dirs,
                default_prefix=self.default_prefix,
                cflags=SANITIZE_CFLAGS,
                ldflags=SANITIZE_LDFLAGS,
            )
        else:
            command = BuildCommand(
                pkg_config_dirs=self.pkg_config_dirs,
                default_prefix=self.default_prefix,
                cflags=CFLAGS,
                ldflags=LDFLAGS,
            )
        check_only = args.no_deps and not sanitize
        ns = argparse.Namespace(
            model=args.model,
            model_format=args.model_format,
            sdk=sdk.prefix,
            sdk_profile=choice.profile.version,
            cc=cc.path,
            build_dir=str(build_dir / SANITIZE_DIR if sanitize else build_dir),
            rebuild=False,
            no_deps=args.no_deps,
            dry_run=check_only,
            strict=args.strict,
        )
        outcome = command.run(ns, ctx)
        seen = {(d.code, d.message) for d in run.diagnostics}
        run.diagnostics += [d for d in outcome.diagnostics if (d.code, d.message) not in seen]
        if outcome.error is not None:
            return outcome.error
        if check_only and not outcome.result["up_to_date"]:
            run.stages["build"] = "stale"
            return CliError(
                "state.stale",
                "the plugin is not up to date (--no-deps)",
                "run mmt-plugin build first, or test without --no-deps",
            )
        if not sanitize:
            run.build_up_to_date = bool(outcome.result["up_to_date"])
        return None

    def _named(
        self, args: argparse.Namespace, model: ModelInput, project: Path
    ) -> list[NamedPlugin]:
        """The plugins plugin.yaml's ``plugins`` names, in load order
        (``PluginError`` on a bad entry); none for a PDL v1 model."""
        if model.format != "yaml":
            return []
        parsed = parse_model(model)
        if not parsed.plugins:
            return []
        path = project / PROJECT_FILE if args.model is None else absolute(args.model)

        def read(file: Path) -> Model:
            return parse_model(read_model(str(file), "yaml", project))

        return resolve(parsed, path.parent, lambda p: show_path(p, project), read)

    def _build_named(
        self,
        args: argparse.Namespace,
        ctx: Context,
        sdk: Sdk,
        cc: Compiler,
        named: Sequence[NamedPlugin],
        project: Path,
        run: _Run,
    ) -> CliError | None:
        """``build`` each named project, in its own directory, as
        ``mmt-plugin -C <project> build`` would (its diagnostics' paths made
        this project's); with ``--no-deps``, a stale one is ``state.stale``
        and nothing is built. Fills ``result.plugins``."""
        for entry in named:
            record: dict[str, Any] = {
                "path": show_path(entry.plugin, project),
                "project": None if entry.project is None else show_path(entry.project, project),
                "build": None,
            }
            run.plugins.append(record)
            if entry.project is None or entry.model is None:
                continue
            where = record["project"]
            command = BuildCommand(
                pkg_config_dirs=self.pkg_config_dirs,
                default_prefix=self.default_prefix,
                cflags=CFLAGS,
                ldflags=LDFLAGS,
            )
            ns = argparse.Namespace(
                model=str(entry.model),
                model_format="yaml",
                sdk=sdk.prefix,
                sdk_profile=args.sdk_profile,
                cc=cc.path,
                build_dir=None,
                rebuild=False,
                no_deps=args.no_deps,
                dry_run=args.no_deps,
                strict=args.strict,
            )
            try:
                outcome = command.run(ns, dataclasses.replace(ctx, project=entry.project))
            except CliError as exc:
                record["build"] = "failed"
                return CliError(exc.code, f"the plugin of {where}: {exc.message}", exc.hint)
            seen = {(d.code, d.message, d.location) for d in run.diagnostics}
            for d in outcome.diagnostics:
                moved = _rebase(d, entry.project, project)
                if (moved.code, moved.message, moved.location) not in seen:
                    run.diagnostics.append(moved)
            if outcome.error is not None:
                error = outcome.error
                record["build"] = "stale" if error.code == "state.stale" else "failed"
                return CliError(error.code, f"the plugin of {where}: {error.message}", error.hint)
            if args.no_deps and not outcome.result["up_to_date"]:
                record["build"] = "stale"
                return CliError(
                    "state.stale",
                    f"the plugin of {where} is not up to date (--no-deps)",
                    f"run mmt-plugin -C {where} build first, or test without --no-deps",
                )
            record["build"] = "up-to-date" if outcome.result["up_to_date"] else "ran"
        return None

    # --- the harness ---

    def _compile_harness(
        self,
        ctx: Context,
        tools: _Toolchain,
        source: str,
        name: str,
        flags: Sequence[str],
    ) -> tuple[Path | None, bool, list[Diagnostic]]:
        """Write and compile ``<test-dir>/<name>.c``; the program (``None``
        on a failure), whether it was up to date, and the compiler's
        diagnostics."""
        source_path = tools.test_dir / f"{name}.c"
        program = tools.test_dir / name
        stamp = tools.test_dir / f".{name}.json"
        command = [
            tools.cc.path,
            f"-std={tools.profile.c_std}",
            *flags,
            "-I",
            tools.sdk.include_dir,
            str(source_path),
            str(tools.core),
            f"-Wl,-rpath,{tools.runtime_dir()}",
            "-Wl,--disable-new-dtags",
            "-o",
            str(program),
        ]
        digest = sha256_bytes(
            json.dumps(
                {"source": source, "command": command, "cc": tools.cc.version}, sort_keys=True
            ).encode("utf-8")
        )
        try:
            recorded = json.loads(stamp.read_text(encoding="utf-8")).get("inputs")
        except (OSError, ValueError, AttributeError):
            recorded = None
        if recorded == digest and program.is_file():
            return program, True, []
        tools.test_dir.mkdir(parents=True, exist_ok=True)
        # build/test/ is test's own directory: a link there is replaced.
        write_atomic(source_path, source, replace_link=True)
        stamp.unlink(missing_ok=True)
        program.unlink(missing_ok=True)
        code, output = run_compiler(command, tools.project, ctx)
        found = parse_compiler_output(output, tools.project, tools.project, failed=code != 0)
        if code != 0 or not program.is_file():
            return None, False, found
        write_atomic(stamp, json.dumps({"inputs": digest}) + "\n", replace_link=True)
        return program, False, found

    def _harness_failed(self, name: str, tools: _Toolchain) -> CliError:
        return CliError(
            "build.harness-failed",
            f"cannot compile the test harness {show_path(tools.test_dir / name, tools.project)}.c",
            "check the compiler diagnostics; the harness is generated, so this is a bug in"
            " mmt-plugin or an SDK the profile does not describe",
        )

    def run(self, args: argparse.Namespace, ctx: Context) -> Outcome:
        started = time.monotonic()
        project = absolute(ctx.project)
        if args.model == "-":
            raise CliError(
                "usage.invalid-value",
                "test reads the model from a file, not stdin: build compares the generated"
                " files with it",
                "pass the model file with --model",
            )
        model = read_model(args.model, args.model_format, project)
        env = os.environ
        sdk = require_sdk(
            args.sdk, env, pkg_config_dirs=self.pkg_config_dirs, default_prefix=self.default_prefix
        )
        choice = resolve_profile(args.sdk_profile, env, model.profile_pin, sdk)
        core = require_core_library(sdk)
        tcpip = Path(sdk.prefix) / "plugins" / harness_mod.TCPIP
        if not tcpip.is_file():
            raise CliError(
                "sdk.invalid-prefix",
                f"{show_path(tcpip, project)} not found: the harness loads the plugin next to it",
                "pass the prefix of a complete mmt-dpi install with --sdk or MMT_BASE",
            )
        cc = find_compiler(args.cc, env)
        ctx.log(f"SDK {sdk.prefix} ({sdk.source.value}), profile {choice.profile.version}")
        build_dir = absolute(args.build_dir) if args.build_dir is not None else project / "build"
        tools = _Toolchain(sdk, choice.profile, cc, core, build_dir / TEST_DIR, project)
        context = {"sdk": sdk_context(sdk, choice)}
        run = _Run(diagnostics=list(choice.diagnostics))
        generation, _, _ = make_generation(model.name, model.data, choice, model.format)
        label = generation.label.lower() if generation is not None else "?"

        def outcome(error: CliError | None) -> Outcome:
            result = _result(model.name, choice, build_dir, project, run, started)
            details = [p.detail() for p in run.packets]
            records = _records(result, details)

            def view(st: StreamStyle) -> str:
                return _view(label, result, details, st)

            return Outcome(
                result=result,
                records=records,
                view=view,
                diagnostics=run.diagnostics,
                error=error,
                context=context,
            )

        tests, error = self._load_tests(args, project, choice.profile, run)
        run.packets = _entries(tests)
        if error is not None:
            return outcome(error)
        if args.strict:
            warning = next((d for d in run.diagnostics if d.severity is Severity.WARNING), None)
            if warning is not None:
                return outcome(
                    CliError(
                        warning.code,
                        f"--strict: {warning.message}",
                        "fix the warnings, or run without --strict",
                    )
                )

        error = self._build(args, ctx, sdk, choice, cc, build_dir, run)
        if error is not None:
            if run.stages["build"] == "skipped":
                run.stages["build"] = "stale" if error.code == "state.stale" else "failed"
            return outcome(error)
        try:
            named = self._named(args, model, project)
        except PluginError as exc:
            run.diagnostics.append(exc.diagnostic)
            run.stages["build"] = "failed"
            return outcome(
                CliError("model.bad-plugin", exc.diagnostic.message, exc.diagnostic.hint)
            )
        error = self._build_named(args, ctx, sdk, cc, named, project, run)
        if error is not None:
            run.stages["build"] = "stale" if error.code == "state.stale" else "failed"
            return outcome(error)
        fresh = run.build_up_to_date and all(p["build"] != "ran" for p in run.plugins)
        run.stages["build"] = "up-to-date" if fresh else "ran"
        tools = dataclasses.replace(tools, extra=tuple(p.plugin for p in named))
        assert generation is not None  # build generated it
        if not tests:
            return outcome(None)
        return outcome(self._test(args, ctx, tools, generation, build_dir, tests, run, choice))

    def _test(
        self,
        args: argparse.Namespace,
        ctx: Context,
        tools: _Toolchain,
        generation: Generation,
        build_dir: Path,
        tests: list[_Test],
        run: _Run,
        choice: ProfileChoice,
    ) -> CliError | None:
        label = generation.label.lower()
        sizes = {
            c.name: c.size or 0 for c in tools.profile.constants if c.group == DATA_TYPE_GROUP
        }
        attributes = sorted(harness_lengths(tests, sizes).items())
        names = [n for n, _ in attributes]
        source = harness_mod.harness_source(generation, tools.profile, attributes)
        program, fresh, found = self._compile_harness(
            ctx, tools, source, "harness", HARNESS_CFLAGS
        )
        run.diagnostics += found
        if program is None:
            run.stages["harness"] = "failed"
            return self._harness_failed("harness", tools)
        run.stages["harness"] = "up-to-date" if fresh else "ran"

        plugin = build_dir / f"mmtp_{label}.so"
        error = self._packets(args, ctx, tools, program, plugin, names, run)
        if error is not None:
            run.stages["packets"] = "failed"
            return error
        run.stages["packets"] = "ran"

        if args.sanitize:
            error = self._build(
                args, ctx, tools.sdk, choice, tools.cc, build_dir, run, sanitize=True
            )
            if error is None:
                error = self._sanitize(args, ctx, tools, source, build_dir, label, tests, run)
            run.stages["sanitize"] = "failed" if error is not None else "ran"
            if error is not None:
                return error
        if args.bench:
            packet_tests = [t for t in tests if isinstance(t, PacketTest)]
            if packet_tests:
                self._bench(ctx, tools, generation, program, plugin, packet_tests, run)
            else:
                self._bench_failed(
                    "it measures packet tests, and there are only session tests", run
                )
        return None

    # --- stage 3 ---

    def _packets(
        self,
        args: argparse.Namespace,
        ctx: Context,
        tools: _Toolchain,
        program: Path,
        plugin: Path,
        names: list[str],
        run: _Run,
    ) -> CliError | None:
        pending = [n for n, p in enumerate(run.packets) if p.session is None]
        records = {n: run.packets[n].record(k) for k, n in enumerate(pending)}
        sessions = [p for p in run.packets if p.session is not None]
        aliases = {p.id: p.alias or p.macro for p in tools.profile.parents.protocols()}
        packets_file = tools.test_dir / "packets.bin"
        with ctx.progress("packets", total=len(run.packets)) as progress:
            done = 0

            def seen(line: str) -> None:
                nonlocal done
                if line == "done":
                    done += 1
                    progress.update(done)

            while pending:
                harness_mod.write_packets(packets_file, [records[i] for i in pending])
                result = harness_mod.run(
                    program,
                    ["check", str(packets_file)],
                    plugin,
                    tools.sdk_plugins,
                    extra=tools.extra,
                    timeout=TIMEOUT + TIMEOUT_PER_PACKET * len(pending),
                    on_line=seen,
                    log=ctx.log,
                )
                if result.stderr and ctx.verbose:
                    ctx.stderr.write(result.stderr)
                parsed = harness_mod.parse_check(result.lines, names)
                reason = harness_mod.crash_reason(result, len(pending))
                if parsed.malformed is not None:
                    reason = reason or f"unreadable harness output: {parsed.malformed!r}"
                if parsed.error is not None and reason is None:
                    return self._load_failed(parsed.error, result.stderr, run)
                if parsed.plugin is None:
                    return self._load_failed(
                        reason or "the harness printed no protocol", result.stderr, run
                    )
                for k, observation in parsed.observations.items():
                    packet = run.packets[pending[k]]
                    assert isinstance(packet.test, PacketTest)
                    packet.failures, packet.checked = check(
                        packet.test,
                        observation,
                        parsed.plugin,
                        _expected_parent(tools.profile, packet),
                        aliases,
                    )
                    packet.status = "fail" if packet.failures else "pass"
                if reason is None:
                    break
                if parsed.unfinished is None and not parsed.observations:
                    # Before the first packet: the setup, not a packet.
                    return self._load_failed(reason, result.stderr, run)
                crashed = (
                    parsed.unfinished
                    if parsed.unfinished is not None
                    else len(parsed.observations)
                )
                if crashed >= len(pending):
                    return CliError(
                        "test.crash",
                        f"the harness crashed after the last packet: {reason}",
                        "run with -v to see the harness's output",
                    )
                packet = run.packets[pending[crashed]]
                packet.status = "crash"
                packet.failures = [Failure("<harness>", "no crash", reason)]
                done += 1
                progress.update(done)
                if args.fail_fast:
                    break
                pending = pending[crashed + 1 :]
            for packet in sessions:
                # --fail-fast: a session test before the first failure (in
                # file order) still runs; the ones after it are skipped.
                at = run.packets.index(packet)
                failed_before = any(p.status in ("fail", "crash") for p in run.packets[:at])
                if args.fail_fast and failed_before:
                    continue
                error = self._session(ctx, tools, program, plugin, names, packet, aliases, run)
                if error is not None:
                    return error
                done += 1
                progress.update(done)
        if args.fail_fast:
            first = next(
                (n for n, p in enumerate(run.packets) if p.status in ("fail", "crash")), None
            )
            if first is not None:
                for p in run.packets[first + 1 :]:
                    p.status, p.failures, p.checked = "skipped", [], 0
        for p in run.packets:
            if p.status in ("fail", "crash"):
                code = "test.crash" if p.status == "crash" else "test.packet-failed"
                run.diagnostics.append(
                    Diagnostic(
                        Severity.ERROR,
                        code,
                        f"{p.name}: {p.detail()}",
                        location=Location(p.test.file),
                    )
                )
        failed = [p for p in run.packets if p.status in ("fail", "crash")]
        if not failed:
            return None
        crashed_any = any(p.status == "crash" for p in failed)
        return CliError(
            "test.crash" if crashed_any else "test.packet-failed",
            f"{len(failed)} of {_plural(len(run.packets), 'packet')} failed",
            "each failure names the attribute, the expected and the actual value",
        )

    def _session(
        self,
        ctx: Context,
        tools: _Toolchain,
        program: Path,
        plugin: Path,
        names: list[str],
        packet: _Packet,
        aliases: Mapping[int, str],
        run: _Run,
    ) -> CliError | None:
        """Run one session test's packets, in order, in a harness of its own
        (its session state is the plugin's), and check each one; a
        ``test.load-failed`` error, or ``None``."""
        test = packet.session
        assert test is not None
        frames = build_frames(test)
        packet.frames = len(frames)
        packets_file = tools.test_dir / "session.bin"
        harness_mod.write_packets(
            packets_file, [harness_mod.Record(f.frame, frame=True) for f in frames]
        )
        result = harness_mod.run(
            program,
            ["check", str(packets_file)],
            plugin,
            tools.sdk_plugins,
            extra=tools.extra,
            timeout=TIMEOUT + TIMEOUT_PER_PACKET * len(frames),
            log=ctx.log,
        )
        if result.stderr and ctx.verbose:
            ctx.stderr.write(result.stderr)
        parsed = harness_mod.parse_check(result.lines, names)
        reason = harness_mod.crash_reason(result, len(frames))
        if parsed.malformed is not None:
            reason = reason or f"unreadable harness output: {parsed.malformed!r}"
        if parsed.error is not None and reason is None:
            return self._load_failed(parsed.error, result.stderr, run)
        if parsed.plugin is None or (
            reason is not None and parsed.unfinished is None and not parsed.observations
        ):
            return self._load_failed(
                reason or "the harness printed no protocol", result.stderr, run
            )
        parent = _expected_parent(tools.profile, packet)
        assert parent is not None
        failures: list[Failure] = []
        checked = 0
        for k, observation in sorted(parsed.observations.items()):
            found, count = check_frame(
                test, frames[k], observation, parsed.plugin, parent, aliases
            )
            failures += found
            checked += count
        packet.failures, packet.checked = failures, checked
        packet.status = "fail" if failures else "pass"
        if reason is not None:
            crashed = (
                parsed.unfinished if parsed.unfinished is not None else len(parsed.observations)
            )
            step = frames[min(crashed, len(frames) - 1)].step
            packet.status = "crash"
            packet.failures = [Failure("<harness>", "no crash", reason, step), *failures]
        return None

    def _load_failed(self, reason: str, stderr: str, run: _Run) -> CliError:
        last = next((x.strip() for x in reversed(stderr.splitlines()) if x.strip()), "")
        if last:
            run.diagnostics.append(Diagnostic(Severity.NOTE, "test.load-failed", last))
        return CliError(
            "test.load-failed",
            f"the harness cannot run the plugin: {reason}",
            "check that the plugin loads next to libmmt_tcpip.so (mmt-plugin validate), and"
            " that plugins: in plugin.yaml names every plugin it attaches to, parents first",
        )

    # --- stage 4 ---

    def _sanitize(
        self,
        args: argparse.Namespace,
        ctx: Context,
        tools: _Toolchain,
        source: str,
        build_dir: Path,
        label: str,
        tests: list[_Test],
        run: _Run,
    ) -> CliError | None:
        program, _, found = self._compile_harness(
            ctx, tools, source, "harness-sanitize", HARNESS_SANITIZE_CFLAGS
        )
        run.diagnostics += found
        if program is None:
            return self._harness_failed("harness-sanitize", tools)
        plugin = build_dir / SANITIZE_DIR / f"mmtp_{label}.so"
        # Per packet: its test, its index (0: the test's own packet), whether
        # it runs through the test's parent, and its bytes (the payload).
        origin: list[tuple[PacketTest, int, bool, bytes]] = []
        for test in tests:
            if not isinstance(test, PacketTest):
                continue
            fuzzed = fuzz_packets(args.seed, test.id, test.data, args.fuzz_count)
            for through in (False, True) if test.through is not None else (False,):
                for k, packet in enumerate([test.data, *fuzzed]):
                    origin.append((test, k, through, packet))
        packets = [_record(t, through, d, n) for n, (t, _, through, d) in enumerate(origin)]
        crashes: list[dict[str, Any]] = []
        start = 0
        ran = 0
        packets_file = tools.test_dir / "fuzz.bin"
        with ctx.progress("packets under the sanitizers", total=len(packets)) as progress:

            def seen(line: str) -> None:
                at = harness_mod.at_index(line)
                if at is not None:
                    progress.update(start + at + 1)

            while start < len(packets) and len(crashes) < MAX_CRASHES:
                harness_mod.write_packets(packets_file, packets[start:])
                result = harness_mod.run(
                    program,
                    ["fuzz", str(packets_file)],
                    plugin,
                    tools.sdk_plugins,
                    extra=tools.extra,
                    timeout=TIMEOUT + TIMEOUT_PER_PACKET * (len(packets) - start),
                    on_line=seen,
                    log=ctx.log,
                )
                reason = harness_mod.crash_reason(result, len(packets) - start)
                error = next((x for x in result.lines if x.startswith("error ")), None)
                if reason is None and error is not None:
                    return self._load_failed(error[6:], result.stderr, run)
                at_lines = [x for x in result.lines if x.startswith("at")]
                indices = [harness_mod.at_index(x) for x in at_lines]
                bad = next((x for x in at_lines if harness_mod.at_index(x) is None), None)
                if reason is None and bad is not None:
                    reason = f"unreadable harness output: {bad!r}"
                last = next((i for i in reversed(indices) if i is not None), None)
                if last is not None and start + last >= len(packets):
                    last = None
                if reason is None:
                    ran = len(packets)
                    break
                if last is None:
                    return self._load_failed(reason, result.stderr, run)
                index = start + last
                test, k, through, data = origin[index]
                crash: dict[str, Any] = {
                    "test": test.id,
                    "index": k,
                    "length": len(data),
                    "reason": reason,
                    "bytes": data.hex(" "),
                }
                where = ""
                if through and test.through is not None:
                    crash["through"] = test.through.text
                    where = f" through {test.through.text}"
                crashes.append(crash)
                run.diagnostics.append(
                    Diagnostic(
                        Severity.ERROR,
                        "test.crash",
                        f"{test.id}: {'the packet' if k == 0 else f'random packet {k}'}{where}"
                        f" ({_plural(len(data), 'byte')}, --seed {args.seed}): {reason}",
                        hint="mmt-plugin test --sanitize -v shows the sanitizer's report",
                        location=Location(test.file),
                    )
                )
                if result.stderr and ctx.verbose:
                    ctx.stderr.write(result.stderr)
                ran = index + 1
                start = index + 1
                if args.fail_fast:
                    break
            for session in tests:
                if not isinstance(session, SessionTest):
                    continue
                if len(crashes) >= MAX_CRASHES or (args.fail_fast and crashes):
                    break
                failed, count = self._sanitize_session(
                    args, ctx, tools, program, plugin, session, crashes, run
                )
                if failed is not None:
                    return failed
                ran += count
        run.sanitize = {"seed": args.seed, "count": ran, "crashes": crashes}
        if crashes:
            return CliError(
                "test.crash",
                f"{_plural(len(crashes), 'crash', 'crashes')} under the sanitizers"
                f" (--seed {args.seed})",
                "each crash names its packet; the same --seed reproduces it",
            )
        return None

    def _sanitize_session(
        self,
        args: argparse.Namespace,
        ctx: Context,
        tools: _Toolchain,
        program: Path,
        plugin: Path,
        test: SessionTest,
        crashes: list[dict[str, Any]],
        run: _Run,
    ) -> tuple[CliError | None, int]:
        """Run a session test under the sanitizers, as it is (copy 0), then
        in corrupted copies until they make ``--fuzz-count`` packets, each
        in a harness of its own; its crashes go to ``crashes``. A
        ``test.load-failed`` error, or ``None``, and the packets run."""
        frames = build_frames(test)
        start = test.through.offset
        copies = 1 + math.ceil(args.fuzz_count / len(frames))
        packets_file = tools.test_dir / "fuzz-session.bin"
        ran = 0
        for copy in range(copies):
            if len(crashes) >= MAX_CRASHES:
                break
            data = (
                [f.frame for f in frames]
                if copy == 0
                else mutate_frames(args.seed, test.id, copy, [f.frame for f in frames], start)
            )
            harness_mod.write_packets(
                packets_file, [harness_mod.Record(d, frame=True) for d in data]
            )
            result = harness_mod.run(
                program,
                ["fuzz", str(packets_file)],
                plugin,
                tools.sdk_plugins,
                extra=tools.extra,
                timeout=TIMEOUT + TIMEOUT_PER_PACKET * len(data),
                log=ctx.log,
            )
            reason = harness_mod.crash_reason(result, len(data))
            error = next((x for x in result.lines if x.startswith("error ")), None)
            if reason is None and error is not None:
                return self._load_failed(error[6:], result.stderr, run), ran
            indices = [harness_mod.at_index(x) for x in result.lines if x.startswith("at")]
            if reason is None and any(i is None for i in indices):
                reason = "unreadable harness output"
            if reason is None:
                ran += len(data)
                continue
            last = next((i for i in reversed(indices) if i is not None and i < len(data)), None)
            if last is None:
                return self._load_failed(reason, result.stderr, run), ran
            ran += last + 1
            frame = frames[last]
            # The TCP payload, without Ethernet padding (the IPv4 length is intact).
            payload = data[last][start : 14 + int.from_bytes(data[last][16:18], "big")]
            crashes.append(
                {
                    "test": test.id,
                    "index": copy,
                    "packet": frame.step,
                    "length": len(payload),
                    "reason": reason,
                    "bytes": payload.hex(" "),
                }
            )
            which = "the session" if copy == 0 else f"corrupted copy {copy}"
            run.diagnostics.append(
                Diagnostic(
                    Severity.ERROR,
                    "test.crash",
                    f"{test.id}: {which}, packets[{frame.step}]"
                    f" ({_plural(len(payload), 'byte')}, --seed {args.seed}): {reason}",
                    hint="mmt-plugin test --sanitize -v shows the sanitizer's report",
                    location=Location(test.file),
                )
            )
            if result.stderr and ctx.verbose:
                ctx.stderr.write(result.stderr)
            if args.fail_fast:
                break
        return None, ran

    # --- stage 5 ---

    def _bench(
        self,
        ctx: Context,
        tools: _Toolchain,
        generation: Generation,
        program: Path,
        plugin: Path,
        tests: list[PacketTest],
        run: _Run,
    ) -> None:
        """Advisory: any failure is a warning and ``bench`` stays ``null``."""
        try:
            self._bench_run(ctx, tools, generation, program, plugin, tests, run)
        except (OSError, ValueError, CliError) as exc:
            self._bench_failed(str(exc), run)

    def _bench_run(
        self,
        ctx: Context,
        tools: _Toolchain,
        generation: Generation,
        program: Path,
        plugin: Path,
        tests: list[PacketTest],
        run: _Run,
    ) -> None:
        label = generation.label.lower()
        baseline_dir = tools.test_dir / "baseline"
        baseline_dir.mkdir(parents=True, exist_ok=True)
        source = baseline_dir / f"mmtp_{label}.c"
        baseline = baseline_dir / f"mmtp_{label}.so"
        write_atomic(
            source, harness_mod.baseline_source(generation, tools.profile), replace_link=True
        )
        command = [
            tools.cc.path,
            f"-std={tools.profile.c_std}",
            *CFLAGS,
            *LDFLAGS,
            "-I",
            tools.sdk.include_dir,
            str(source),
            str(tools.core),
            "-o",
            str(baseline),
        ]
        code, output = run_compiler(command, tools.project, ctx)
        if code != 0:
            run.diagnostics += [
                Diagnostic(Severity.WARNING, d.code, d.message, location=d.location)
                for d in parse_compiler_output(output, tools.project, tools.project, failed=True)
                if d.severity is Severity.ERROR
            ]
            return self._bench_failed("cannot compile the empty baseline plugin", run)
        packets_file = tools.test_dir / "bench.bin"
        harness_mod.write_packets(packets_file, [t.data for t in tests])
        rounds = max(1, math.ceil(BENCH_PACKETS / len(tests)))
        measured: dict[str, list[float]] = {}
        with ctx.progress("bench"):
            for name, target in (("plugin", plugin), ("baseline", baseline)):
                result = harness_mod.run(
                    program,
                    ["bench", str(packets_file), str(rounds), str(BENCH_SAMPLES)],
                    target,
                    tools.sdk_plugins,
                    extra=tools.extra,
                    timeout=TIMEOUT * 5,
                    log=ctx.log,
                )
                samples = []
                for line in result.lines:
                    sample = harness_mod.parse_sample(line)
                    if sample is not None and sample[1] > 0:
                        samples.append(sample[0] * 1e9 / sample[1])
                reason = harness_mod.crash_reason(result)
                if reason is not None or len(samples) != BENCH_SAMPLES:
                    return self._bench_failed(
                        f"the {name} run failed: {reason or 'no samples'}", run
                    )
                measured[name] = samples
        pps = _rate(measured["plugin"])
        baseline_pps = _rate(measured["baseline"])
        run.bench = {
            "pps": pps,
            "baseline_pps": baseline_pps,
            "ratio": round(pps / baseline_pps, 3) if baseline_pps else 0.0,
            "samples": [round(s) for s in measured["plugin"]],
        }
        run.stages["bench"] = "ran"

    def _bench_failed(self, why: str, run: _Run) -> None:
        run.stages["bench"] = "failed"
        run.diagnostics.append(
            Diagnostic(
                Severity.WARNING,
                "test.bench-failed",
                f"--bench: {why}; the bench is advisory, the exit code does not change",
            )
        )


def _rebase(d: Diagnostic, root: Path, project: Path) -> Diagnostic:
    """``d``, of a build in ``root`` (its paths relative to ``root`` when
    inside it), with its paths as this project's diagnostics write them."""

    def moved(loc: Location | None) -> Location | None:
        if loc is None or loc.file.startswith("<") or Path(loc.file).is_absolute():
            return loc
        return dataclasses.replace(loc, file=show_path(absolute(root / loc.file), project))

    related = [dataclasses.replace(r, location=moved(r.location)) for r in d.related]
    return dataclasses.replace(d, location=moved(d.location), related=related)


def _rate(samples: Sequence[float]) -> int:
    """The median of the samples, in packets per second."""
    ordered = sorted(samples)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return round(ordered[middle])
    return round((ordered[middle - 1] + ordered[middle]) / 2)


def _result(
    model: str,
    choice: ProfileChoice,
    build_dir: Path,
    project: Path,
    run: _Run,
    started: float,
) -> dict[str, Any]:
    counts = {s: sum(1 for p in run.packets if p.status == s) for s in _LEVELS}
    return {
        "model": model,
        "profile": choice.profile.version,
        "build_dir": show_path(build_dir, project),
        "stages": [{"name": n, "status": s} for n, s in run.stages.items()],
        "summary": {
            "total": len(run.packets),
            "passed": counts["pass"],
            "failed": counts["fail"] + counts["crash"],
            "skipped": counts["skipped"],
        },
        "plugins": run.plugins,
        "packets": [p.to_json() for p in run.packets],
        "sanitize": run.sanitize,
        "bench": run.bench,
        "stats": {"elapsed_ms": round((time.monotonic() - started) * 1000)},
    }


def _packet_name(packet: Mapping[str, Any]) -> str:
    """A ``result.packets`` entry's id, and the parent it ran through."""
    through = packet.get("through")
    return f"{packet['id']} through {through}" if through else str(packet["id"])


def _records(result: Mapping[str, Any], details: Sequence[str]) -> list[tuple[str, ...]]:
    """The plain records: ``packet⇥status⇥detail``, then ``sanitize⇥seed⇥
    count⇥crashes`` and ``bench⇥pps⇥baseline_pps⇥ratio`` when they ran."""
    records: list[tuple[str, ...]] = [
        (_packet_name(p), p["status"], d) for p, d in zip(result["packets"], details, strict=True)
    ]
    sanitize = result["sanitize"]
    if sanitize is not None:
        records.append(
            (
                "sanitize",
                str(sanitize["seed"]),
                str(sanitize["count"]),
                str(len(sanitize["crashes"])),
            )
        )
    bench = result["bench"]
    if bench is not None:
        records.append(
            ("bench", str(bench["pps"]), str(bench["baseline_pps"]), f"{bench['ratio']:g}")
        )
    return records


def _view(label: str, result: Mapping[str, Any], details: Sequence[str], st: StreamStyle) -> str:
    """The styled output: a box ``test <label>`` with the packets table, a
    pass meter, then the sanitizer run and the bench when they ran."""
    sep = style.glyphs(st).separator
    rows = [
        [_packet_name(p), style.status(p["status"], _LEVELS[p["status"]], style=st), d]
        for p, d in zip(result["packets"], details, strict=True)
    ]
    body: list[str] = []
    if rows:
        body += style.table(["packet", "status", "detail"], rows, style=st, width=st.width - 4)
    summary = result["summary"]
    total = summary["total"]
    if total:
        share = summary["passed"] * 100 / total
        body += [
            "",
            style.join(
                "passed   ",
                style.meter(share, style=st, width=20),
                f"   {summary['passed']} of {_plural(total, 'packet')}",
            ),
        ]
    sanitize = result["sanitize"]
    if sanitize is not None:
        body.append(
            f"sanitize   seed {sanitize['seed']}{sep}{_plural(sanitize['count'], 'packet')}"
            f"{sep}{_plural(len(sanitize['crashes']), 'crash', 'crashes')}"
        )
    bench = result["bench"]
    if bench is not None:
        body += [
            style.join(
                "bench    ",
                style.meter(min(100.0, bench["ratio"] * 100), style=st, width=20),
                f"   {bench['pps']:,} pps vs {bench['baseline_pps']:,} empty",
            ),
            style.join("samples  ", style.sparkline(bench["samples"], style=st)),
        ]
    parts = [_plural(total, "packet")]
    if summary["failed"]:
        parts.append(f"{summary['failed']} failed")
    if summary["skipped"]:
        parts.append(f"{summary['skipped']} skipped")
    stages = {s["name"]: s["status"] for s in result["stages"]}
    if stages["build"] == "up-to-date":
        parts.append("build up to date")
    elif stages["build"] == "ran":
        parts.append("built")
    else:
        parts.append(f"build {stages['build']}")
    return style.box(f"test {label}", body, style=st, footer=sep.join(parts))
