"""``mmt-plugin run PCAP`` (#103): run the plugin over a capture and count
what it reports.

The model is ``--model`` (default ``<project>/plugin.yaml``), as
``build``'s ``MODEL``. Stages, reported in ``result.stages`` (``ran``,
``up-to-date``, ``failed``, ``stale`` or ``skipped``), each stopping the run
with its class's exit code:

0. read the model, find the SDK, the compiler and the profile (as
   ``build``), check ``--plugin`` and open the capture: a file that is not
   a pcap or pcapng capture is ``model.bad-pcap`` (exit 3);
1. ``build``: ``mmt-plugin build`` (``mmt_plugin.commands.build``), a no-op
   when the plugin is up to date; with ``--no-deps``, a plugin that is not
   up to date is ``state.stale`` (exit 7) and nothing is built;
2. ``runner``: the capture runner (``mmt_plugin.capture.runner``) is
   generated into ``<build-dir>/run/runner.c`` and compiled against the SDK
   (``build.runner-failed``, exit 5), unless it is up to date;
3. ``capture``: the runner loads, from a plugin directory of its own, every
   plugin of the SDK's ``plugins/`` directory, the plugin and each
   ``--plugin`` (one of them replaces an SDK plugin of the same file name),
   opens a handler for the link type of the capture's first frame, and
   processes every frame (up to ``--max-packets``) through mmt-dpi's stack:
   the plugin's own parent classification must find its packets. The
   capture is read one record at a time (``mmt_plugin.pcap.reader``) and
   streamed to the runner, which keeps one frame and bounded counts: the
   run's memory does not grow with the capture. A plugin that does not
   load is ``test.load-failed``, a crash or a ``--timeout``
   ``test.crash`` (exit 6, with the frame); a capture broken after its
   header stops there, ``model.bad-pcap`` (exit 3), with the counts of the
   frames before.

The result counts, per protocol path (the protocol names from Ethernet
up), the packets mmt-dpi gave it, and for the plugin's protocol (and each
``--protocol``) the packets whose path has it and, per attribute, the
packets in which mmt-dpi extracted it. Warnings: ``test.no-match`` (no
packet has the plugin's protocol), ``test.other-linktype`` (frames of
another link type than the first, not processed), ``test.unknown-protocol``
(a ``--protocol`` no plugin registers). ``--strict`` fails on a warning.
``--dry-run`` reads the model and the capture's header, checks whether the
plugin is up to date, and compiles and runs nothing.
"""

from __future__ import annotations

import argparse
import itertools
import json
import os
import re
import time
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO, Any

from mmt_plugin.capture import runner as runner_mod
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
from mmt_plugin.commands.modelio import FORMATS, absolute, read_model, show_path
from mmt_plugin.diagnostics import CliError, Diagnostic, Location, Severity
from mmt_plugin.exitcodes import ExitCode
from mmt_plugin.fsio import sha256_bytes, write_atomic
from mmt_plugin.pcap.reader import Capture, Frame, PcapError, read_stream
from mmt_plugin.sdk.detect import DEFAULT_PREFIX, Sdk, require_sdk
from mmt_plugin.sdk.resolve import ENV_PROFILE, ProfileChoice, resolve_profile, sdk_context
from mmt_plugin.ui import style
from mmt_plugin.ui.streams import StreamStyle

__all__ = ["DIAGNOSTIC_CODES", "RUNNER_CFLAGS", "STAGES", "RunCommand"]

#: The codes this command reports itself.
DIAGNOSTIC_CODES = (
    "model.bad-pcap",
    "model.unsupported-linktype",
    "build.runner-failed",
    "test.crash",
    "test.load-failed",
    "test.no-match",
    "test.other-linktype",
    "test.unknown-protocol",
)

STAGES = ("build", "runner", "capture")
RUN_DIR = "run"
TCPIP = "libmmt_tcpip.so"
#: The runner's own flags.
RUNNER_CFLAGS = ("-O2", "-Wall", "-Wextra", "-Werror")
#: The paths the styled view shows (the result has all of them).
VIEW_PATHS = 12

_SONAME = re.compile(r"^(libmmt_core\.so\.[0-9]+)(\.[0-9]+)+$")


def _plural(n: int, word: str, words: str | None = None) -> str:
    return f"{n:,} {word}" if n == 1 else f"{n:,} {words or word + 's'}"


def _non_negative(text: str) -> int:
    try:
        value = int(text, 10)
    except ValueError:
        raise argparse.ArgumentTypeError(f"not an integer: {text!r}") from None
    if value < 0:
        raise argparse.ArgumentTypeError(f"must be >= 0: {value}")
    return value


def _seconds(text: str) -> float:
    try:
        value = float(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"not a number: {text!r}") from None
    if not value >= 0:
        raise argparse.ArgumentTypeError(f"must be >= 0: {text}")
    return value


@dataclass
class _Run:
    """What one run reports, filled in stage by stage."""

    stages: dict[str, str] = field(default_factory=lambda: dict.fromkeys(STAGES, "skipped"))
    diagnostics: list[Diagnostic] = field(default_factory=list)
    plugins: list[str] = field(default_factory=list)
    capture: dict[str, Any] = field(default_factory=dict)
    summary: dict[str, int] = field(
        default_factory=lambda: {"frames": 0, "processed": 0, "skipped": 0, "classified": 0}
    )
    protocols: list[dict[str, Any]] = field(default_factory=list)
    paths: list[dict[str, Any]] = field(default_factory=list)
    paths_other: int = 0
    build_up_to_date: bool = False


def _limited(frames: Iterable[Frame], limit: int | None) -> Iterable[Frame]:
    """``frames``, at most ``limit`` (``None``: all)."""
    if limit is None:
        return frames
    return (frame for _, frame in zip(range(limit), frames, strict=False))


class RunCommand:
    """``mmt-plugin run PCAP``: the plugin over a capture.

    ``pkg_config_dirs`` and ``default_prefix`` are passed to SDK detection
    (tests point them at temporary directories)."""

    name = "run"
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
            help="run the plugin over a pcap or pcapng capture and count what it reports",
            description=(
                "Build the plugin when it is stale, then run it, with the SDK's plugins and\n"
                "any --plugin, over a capture through mmt-dpi's stack, and report the\n"
                "protocol paths with their packet counts and, per attribute of the plugin's\n"
                "protocol, the packets that have it. The capture is streamed: its size\n"
                "does not change the memory the run takes."
            ),
            epilog=(
                "examples:\n"
                "  mmt-plugin run capture.pcap --sdk $HOME/mmt/opt/mmt\n"
                "  mmt-plugin run big.pcapng --max-packets 100000\n"
                "  mmt-plugin -C examples/ocpp run ocpp.pcap \\\n"
                "      --plugin examples/websocket/build/mmtp_websocket_example.so \\\n"
                "      --protocol websocket_example"
            ),
        )
        parser.add_argument("capture", metavar="PCAP", help="a pcap or pcapng capture file")
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
            help="the mmt-dpi prefix to run against (default: MMT_BASE, mmt-dpi.pc, /opt/mmt)",
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
            "--plugin",
            action="append",
            default=[],
            metavar="FILE",
            help="another plugin to load (a built .so), e.g. a parent; repeatable",
        )
        parser.add_argument(
            "--protocol",
            action="append",
            default=[],
            metavar="NAME",
            help="also count the attributes of this protocol (by name); repeatable",
        )
        parser.add_argument(
            "--max-packets",
            type=_non_negative,
            default=None,
            metavar="N",
            help="stop after the first N frames (default: every frame)",
        )
        parser.add_argument(
            "--timeout",
            type=_seconds,
            default=0.0,
            metavar="SECONDS",
            help="stop the run after this long, a test.crash (default: 0, no limit)",
        )
        parser.add_argument(
            "--no-deps",
            action="store_true",
            help="do not build a stale plugin: exit 7 instead",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="check the inputs and whether the plugin is up to date; run nothing",
        )
        parser.add_argument(
            "--strict", action="store_true", help="fail on warnings, with their class's code"
        )
        return parser

    # --- stage 0 ---

    def _plugins(
        self, args: argparse.Namespace, project: Path, sdk: Sdk, label: str
    ) -> tuple[dict[str, Path], list[Path]]:
        """The ``--plugin`` files by file name, and the SDK's plugins they
        and the plugin leave in (sorted)."""
        own = f"mmtp_{label}.so"
        extra: dict[str, Path] = {}
        for given in args.plugin:
            path = absolute(given)
            if not path.is_file():
                raise CliError(
                    "usage.invalid-value",
                    f"--plugin {given}: not a file",
                    "pass a built plugin (.so), e.g. another project's build/mmtp_<label>.so",
                )
            if path.name == own:
                raise CliError(
                    "usage.invalid-value",
                    f"--plugin {given}: the plugin's own file name, {own}",
                    "run the other project's plugin from its own project",
                )
            if path.name in extra:
                raise CliError(
                    "usage.invalid-value",
                    f"--plugin {given}: two plugins named {path.name}",
                    "mmt-dpi loads plugins by file name: pass each name once",
                )
            extra[path.name] = path
        sdk_dir = Path(sdk.prefix) / "plugins"
        replaced = {own, *extra}
        sdk_plugins = sorted(
            p
            for p in (sdk_dir.glob("*.so") if sdk_dir.is_dir() else [])
            if p.is_file() and p.name not in replaced
        )
        if not any(p.name == TCPIP for p in sdk_plugins) and TCPIP not in extra:
            raise CliError(
                "sdk.invalid-prefix",
                f"{show_path(sdk_dir / TCPIP, project)} not found: the plugin's parents are"
                " registered by it",
                "pass the prefix of a complete mmt-dpi install with --sdk or MMT_BASE",
            )
        return extra, sdk_plugins

    def _open(self, path: Path, shown: str) -> tuple[IO[bytes], Capture]:
        try:
            stream = path.open("rb")
        except OSError as exc:
            raise CliError(
                "model.bad-pcap",
                f"cannot read {shown}: {exc.strerror or exc}",
                "check the PCAP path and its permissions",
            ) from None
        try:
            return stream, read_stream(stream)
        except PcapError as exc:
            stream.close()
            raise CliError(
                "model.bad-pcap",
                f"{shown} is not a readable capture: {exc}",
                "pass a pcap or pcapng file (tcpdump -w, Wireshark, editcap -F pcap)",
            ) from None

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
    ) -> CliError | None:
        command = BuildCommand(
            pkg_config_dirs=self.pkg_config_dirs,
            default_prefix=self.default_prefix,
            cflags=CFLAGS,
            ldflags=LDFLAGS,
        )
        check_only = bool(args.no_deps or args.dry_run)
        ns = argparse.Namespace(
            model=args.model,
            model_format=args.model_format,
            sdk=sdk.prefix,
            sdk_profile=choice.profile.version,
            cc=cc.path,
            build_dir=str(build_dir),
            rebuild=False,
            no_deps=args.no_deps,
            dry_run=check_only,
            strict=args.strict,
        )
        outcome = command.run(ns, ctx)
        seen = {(d.code, d.message) for d in run.diagnostics}
        run.diagnostics += [d for d in outcome.diagnostics if (d.code, d.message) not in seen]
        if outcome.error is not None:
            run.stages["build"] = "stale" if outcome.error.code == "state.stale" else "failed"
            return outcome.error
        run.build_up_to_date = bool(outcome.result["up_to_date"])
        if check_only and not run.build_up_to_date:
            run.stages["build"] = "stale"
            if args.no_deps:
                return CliError(
                    "state.stale",
                    "the plugin is not up to date (--no-deps)",
                    "run mmt-plugin build first, or run without --no-deps",
                )
            return None
        run.stages["build"] = "up-to-date" if run.build_up_to_date else "ran"
        return None

    # --- stage 2 ---

    def _runtime_dir(self, core: Path, run_dir: Path) -> Path:
        """A directory where ``libmmt_core``'s soname resolves to the SDK's
        library (the package's own links are absolute ``/opt/mmt`` paths)."""
        match = _SONAME.match(core.name)
        if match is None:
            return core.parent
        lib = run_dir / "lib"
        lib.mkdir(parents=True, exist_ok=True)
        link = lib / match.group(1)
        if not (link.is_symlink() and os.readlink(link) == str(core)):
            link.unlink(missing_ok=True)
            link.symlink_to(core)
        return lib

    def _compile_runner(
        self,
        ctx: Context,
        sdk: Sdk,
        choice: ProfileChoice,
        cc: Compiler,
        core: Path,
        run_dir: Path,
        project: Path,
        run: _Run,
    ) -> Path | None:
        """Write and compile ``<run-dir>/runner.c`` (a no-op when its source,
        command and compiler are unchanged); the program, ``None`` on a
        failure."""
        source = runner_mod.runner_source(choice.profile)
        source_path = run_dir / "runner.c"
        program = run_dir / "runner"
        stamp = run_dir / ".runner.json"
        run_dir.mkdir(parents=True, exist_ok=True)
        command = [
            cc.path,
            f"-std={choice.profile.c_std}",
            *RUNNER_CFLAGS,
            "-I",
            sdk.include_dir,
            str(source_path),
            str(core),
            f"-Wl,-rpath,{self._runtime_dir(core, run_dir)}",
            "-Wl,--disable-new-dtags",
            "-o",
            str(program),
        ]
        digest = sha256_bytes(
            json.dumps(
                {"source": source, "command": command, "cc": cc.version}, sort_keys=True
            ).encode("utf-8")
        )
        try:
            recorded = json.loads(stamp.read_text(encoding="utf-8")).get("inputs")
        except (OSError, ValueError, AttributeError):
            recorded = None
        if recorded == digest and program.is_file():
            run.stages["runner"] = "up-to-date"
            return program
        # build/run/ is run's own directory: a link there is replaced.
        write_atomic(source_path, source, replace_link=True)
        stamp.unlink(missing_ok=True)
        program.unlink(missing_ok=True)
        code, output = run_compiler(command, project, ctx)
        run.diagnostics += parse_compiler_output(output, project, project, failed=code != 0)
        if code != 0 or not program.is_file():
            run.stages["runner"] = "failed"
            return None
        write_atomic(stamp, json.dumps({"inputs": digest}) + "\n", replace_link=True)
        run.stages["runner"] = "ran"
        return program

    # --- the command ---

    def run(self, args: argparse.Namespace, ctx: Context) -> Outcome:
        started = time.monotonic()
        project = absolute(ctx.project)
        if args.model == "-":
            raise CliError(
                "usage.invalid-value",
                "run reads the model from a file, not stdin: build compares the generated"
                " files with it",
                "pass the model file with --model",
            )
        if args.capture == "-":
            raise CliError(
                "usage.invalid-value",
                "run reads the capture from a file, not stdin",
                "pass the capture file: PCAP",
            )
        model = read_model(args.model, args.model_format, project)
        env = os.environ
        sdk = require_sdk(
            args.sdk, env, pkg_config_dirs=self.pkg_config_dirs, default_prefix=self.default_prefix
        )
        choice = resolve_profile(args.sdk_profile, env, model.profile_pin, sdk)
        core = require_core_library(sdk)
        cc = find_compiler(args.cc, env)
        ctx.log(f"SDK {sdk.prefix} ({sdk.source.value}), profile {choice.profile.version}")
        build_dir = absolute(args.build_dir) if args.build_dir is not None else project / "build"
        context = {"sdk": sdk_context(sdk, choice)}
        run = _Run(diagnostics=list(choice.diagnostics))
        generation, _, _ = make_generation(model.name, model.data, choice, model.format)
        label = generation.label.lower() if generation is not None else "?"
        capture_path = absolute(args.capture)
        shown = show_path(capture_path, project)
        run.capture = {"path": shown, "format": None, "linktype": None}

        def outcome(error: CliError | None) -> Outcome:
            result = _result(model.name, choice, build_dir, project, run, args, started)

            def view(st: StreamStyle) -> str:
                return _view(label, result, st)

            return Outcome(
                result=result,
                records=_records(result),
                view=view,
                diagnostics=run.diagnostics,
                error=error,
                context=context,
            )

        if len(args.protocol) >= runner_mod.MAX_PROTOCOLS:
            raise CliError(
                "usage.invalid-value",
                f"--protocol: at most {runner_mod.MAX_PROTOCOLS - 1} protocols",
                "count fewer protocols in one run",
            )
        extra, sdk_plugins = self._plugins(args, project, sdk, label)
        stream, capture = self._open(capture_path, shown)
        with stream:
            run.capture["format"] = capture.format
            frames = self._first_frame(capture, shown, args.max_packets, run)
            warning = _first_warning(run)
            if args.strict and warning is not None:
                return outcome(_strict(warning))
            error = self._build(args, ctx, sdk, choice, cc, build_dir, run)
            if error is not None or args.dry_run:
                return outcome(error)
            assert generation is not None  # build generated it
            run_dir = build_dir / RUN_DIR
            program = self._compile_runner(ctx, sdk, choice, cc, core, run_dir, project, run)
            if program is None:
                return outcome(
                    CliError(
                        "build.runner-failed",
                        f"cannot compile the capture runner {show_path(run_dir, project)}"
                        "/runner.c",
                        "check the compiler diagnostics; the runner is generated, so this is a"
                        " bug in mmt-plugin or an SDK the profile does not describe",
                    )
                )
            plugins = {p.name: p for p in sdk_plugins}
            plugins[f"mmtp_{label}.so"] = build_dir / f"mmtp_{label}.so"
            plugins.update(extra)
            run.plugins = sorted(plugins, key=lambda n: n.encode("utf-8", "surrogateescape"))
            protocols = [str(generation.proto_id), *args.protocol]
            error = self._capture(args, ctx, program, frames, plugins, protocols, shown, run)
        warning = _first_warning(run)
        if error is None and args.strict and warning is not None:
            error = _strict(warning)
        return outcome(error)

    def _first_frame(
        self, capture: Capture, shown: str, limit: int | None, run: _Run
    ) -> Iterable[Frame]:
        """The capture's frames (at most ``limit``), once the first one is
        read: a broken first record is ``model.bad-pcap`` and a link type
        mmt-dpi does not read ``model.unsupported-linktype``, before anything
        is built."""
        frames = capture.frames()
        try:
            first = next(frames, None) if limit != 0 else None
        except PcapError as exc:
            raise CliError(
                "model.bad-pcap",
                f"{shown} is not a readable capture: {exc}",
                "pass a pcap or pcapng file (tcpdump -w, Wireshark, editcap -F pcap)",
            ) from None
        if first is None:
            return []
        run.capture["linktype"] = first.linktype
        if runner_mod.dlt_of(first.linktype) is None:
            supported = ", ".join(str(k) for k in runner_mod.LINKTYPE_DLT)
            raise CliError(
                "model.unsupported-linktype",
                f"{shown}: its first frame's link type, {first.linktype}, is not one mmt-dpi"
                f" reads (link types {supported}: Ethernet, Linux cooked capture)",
                "convert the capture to Ethernet (e.g. editcap -T ether, or capture on one"
                " interface rather than -i any with SLL2)",
            )
        return _limited(itertools.chain([first], frames), limit)

    # --- stage 3 ---

    def _capture(
        self,
        args: argparse.Namespace,
        ctx: Context,
        program: Path,
        frames: Iterable[Frame],
        plugins: Mapping[str, Path],
        protocols: Sequence[str],
        shown: str,
        run: _Run,
    ) -> CliError | None:
        def echo(text: str) -> None:
            if ctx.verbose:
                ctx.stderr.write(text)

        with ctx.progress("frames") as progress:
            done = runner_mod.run(
                program,
                frames,
                plugins,
                protocols,
                timeout=args.timeout or None,
                log=ctx.log,
                echo=echo,
                on_frames=progress.update,
                errors=(PcapError, OSError),
            )
        report = done.report
        run.capture["linktype"] = done.linktype
        reason = done.crash_reason()
        if reason is None and report.error is not None:
            run.stages["capture"] = "failed"
            return _load_failed(report.error, done.stderr, run)
        if reason is not None and not report.ready:
            run.stages["capture"] = "failed"
            return _load_failed(reason, done.stderr, run)
        if reason is not None and report.frames is None:
            # The runner stopped before its counts: only the frames it
            # reached are known (the batches sent are ahead of it).
            report.frames = report.crash - 1 if report.crash is not None else report.progress
        _fill(run, report, done)
        if reason is not None:
            run.stages["capture"] = "failed"
            frame = report.crash if report.crash is not None else report.progress + 1
            last = _last_line(done.stderr)
            if last:
                run.diagnostics.append(Diagnostic(Severity.NOTE, "test.crash", last))
            where = (
                f" in frame {frame:,} of those sent"
                if report.crash is not None
                else f" after frame {report.progress:,}"
            )
            return CliError(
                "test.crash",
                f"the runner stopped{where}: {reason}",
                "run with -v to see the plugins' output; test the frame's bytes as a packet"
                " test with mmt-plugin test --sanitize",
            )
        run.stages["capture"] = "ran"
        if done.capture_error is not None:
            run.diagnostics.append(
                Diagnostic(
                    Severity.ERROR,
                    "model.bad-pcap",
                    f"{shown}: {done.capture_error}",
                    location=Location(shown),
                )
            )
            return CliError(
                "model.bad-pcap",
                f"{shown} is broken after {_plural(done.sent + done.other_linktype, 'frame')}:"
                " the counts are those of the frames before",
                "repair the capture (editcap, or pcapfix) or cut it before the break",
            )
        _warnings(run, report, done)
        return None


def _first_warning(run: _Run) -> Diagnostic | None:
    return next((d for d in run.diagnostics if d.severity is Severity.WARNING), None)


def _strict(warning: Diagnostic) -> CliError:
    return CliError(
        warning.code, f"--strict: {warning.message}", "fix the warnings, or run without --strict"
    )


def _last_line(stderr: str) -> str:
    return next((x.strip() for x in reversed(stderr.splitlines()) if x.strip()), "")


def _load_failed(reason: str, stderr: str, run: _Run) -> CliError:
    last = _last_line(stderr)
    if last:
        run.diagnostics.append(Diagnostic(Severity.NOTE, "test.load-failed", last))
    return CliError(
        "test.load-failed",
        f"the runner cannot run the plugin: {reason}",
        "check that the plugin and every --plugin load next to the SDK's plugins"
        " (mmt-plugin validate, mmt-plugin doctor)",
    )


def _fill(run: _Run, report: runner_mod.Report, done: runner_mod.CaptureRun) -> None:
    """The result's counts from the runner's report."""
    frames = report.frames if report.frames is not None else done.sent
    # A runner that stopped early (a crash) reached fewer frames than were sent.
    read = done.sent if report.end is not None else frames
    run.summary = {
        "frames": read + done.other_linktype,
        "processed": frames - report.unprocessed,
        "skipped": done.other_linktype + report.unprocessed,
        "classified": report.protocols[0].packets if report.protocols else 0,
    }
    names = report.names

    def path_name(ids: Sequence[int]) -> str:
        return ".".join(names.get(i, str(i)) for i in ids)

    paths = [{"path": path_name(ids), "ids": list(ids), "packets": n} for n, ids in report.paths]
    run.paths = sorted(paths, key=lambda p: (-p["packets"], p["path"], p["ids"]))
    run.paths_other = report.paths_other
    run.protocols = [
        {
            "name": p.name,
            "id": p.id,
            "packets": p.packets,
            "attributes": sorted(
                (
                    {"id": aid, "name": name, "type": kind, "packets": count}
                    for (aid, kind, name), count in zip(p.attributes, p.counts, strict=True)
                ),
                key=lambda a: (a["id"], a["name"]),
            ),
        }
        for p in report.protocols
    ]


def _warnings(run: _Run, report: runner_mod.Report, done: runner_mod.CaptureRun) -> None:
    if done.other_linktype:
        run.diagnostics.append(
            Diagnostic(
                Severity.WARNING,
                "test.other-linktype",
                f"{_plural(done.other_linktype, 'frame')} of another link type than the first"
                f" frame's ({done.linktype}) were not processed",
                hint="split the capture by interface (editcap, tshark -r ... -w) and run each",
            )
        )
    for p in report.protocols[1:]:
        if p.id is None:
            run.diagnostics.append(
                Diagnostic(
                    Severity.WARNING,
                    "test.unknown-protocol",
                    f"--protocol {p.name}: no loaded plugin registers it; it was not counted",
                    hint="check the name (a protocol's label) and pass its plugin with --plugin",
                )
            )
    if report.protocols and report.protocols[0].packets == 0:
        sent = run.summary["frames"]
        why = "the capture has no frame" if sent == 0 else f"none of {_plural(sent, 'frame')}"
        run.diagnostics.append(
            Diagnostic(
                Severity.WARNING,
                "test.no-match",
                f"no packet has the plugin's protocol {report.protocols[0].name} ({why})",
                hint="check the parent's classify (or <label>_hook_register_parents) against"
                " the capture's paths, and that the capture carries the protocol",
            )
        )


def _result(
    model: str,
    choice: ProfileChoice,
    build_dir: Path,
    project: Path,
    run: _Run,
    args: argparse.Namespace,
    started: float,
) -> dict[str, Any]:
    elapsed = time.monotonic() - started
    frames = run.summary["frames"]
    return {
        "model": model,
        "profile": choice.profile.version,
        "build_dir": show_path(build_dir, project),
        "capture": dict(run.capture),
        "dry_run": bool(args.dry_run),
        "stages": [{"name": n, "status": s} for n, s in run.stages.items()],
        "plugins": list(run.plugins),
        "summary": dict(run.summary),
        "protocols": run.protocols,
        "paths": run.paths,
        "paths_other": run.paths_other,
        "stats": {
            "elapsed_ms": round(elapsed * 1000),
            "frames_per_second": round(frames / elapsed) if elapsed > 0 else 0,
        },
    }


def _share(n: int, total: int) -> float:
    return n * 100 / total if total else 0.0


def _records(result: Mapping[str, Any]) -> list[tuple[str, ...]]:
    """The plain records: ``frames⇥frames⇥processed⇥skipped⇥classified``,
    then ``path⇥packets⇥path`` per path (and ``path⇥N⇥<other>`` for the
    paths not kept), then ``attribute⇥protocol⇥name⇥packets`` per attribute
    of each counted protocol."""
    s = result["summary"]
    records: list[tuple[str, ...]] = [
        ("frames", str(s["frames"]), str(s["processed"]), str(s["skipped"]), str(s["classified"]))
    ]
    records += [("path", str(p["packets"]), p["path"]) for p in result["paths"]]
    if result["paths_other"]:
        records.append(("path", str(result["paths_other"]), "<other>"))
    for protocol in result["protocols"]:
        if protocol["id"] is None:
            continue
        records += [
            ("attribute", protocol["name"], a["name"], str(a["packets"]))
            for a in protocol["attributes"]
        ]
    return records


def _view(label: str, result: Mapping[str, Any], st: StreamStyle) -> str:
    """The styled output: a box ``run <label>`` with the busiest paths, then
    each counted protocol's attributes with a meter of the share of its
    packets that have each one."""
    sep = style.glyphs(st).separator
    s = result["summary"]
    body: list[str] = []
    paths = result["paths"]
    if paths:
        rows = [
            [f"{p['packets']:,}", f"{_share(p['packets'], s['processed']):.1f}%", p["path"]]
            for p in paths[:VIEW_PATHS]
        ]
        hidden = len(paths) - VIEW_PATHS
        body += style.table(
            ["packets", "share", "path"], rows, style=st, width=st.width - 4, align=["right"] * 2
        )
        if hidden > 0 or result["paths_other"]:
            text = f"… {_plural(max(hidden, 0), 'more path')}"
            if result["paths_other"]:
                text += f", {result['paths_other']:,} packets of paths not kept"
            body.append(text + " (--json has every path)")
    for protocol in result["protocols"]:
        if protocol["id"] is None:
            continue
        total = protocol["packets"]
        body += ["", f"{protocol['name']} ({protocol['id']}): {_plural(total, 'packet')}"]
        for a in protocol["attributes"]:
            share = _share(a["packets"], total)
            body.append(
                style.join(
                    f"  {a['name']:<20} ",
                    style.meter(share, style=st, width=16),
                    f"  {a['packets']:,}",
                )
            )
    parts = [_plural(s["frames"], "frame")]
    if s["skipped"]:
        parts.append(f"{s['skipped']:,} skipped")
    parts.append(f"{s['classified']:,} {label}")
    stages = {x["name"]: x["status"] for x in result["stages"]}
    if result["dry_run"]:
        parts.append(f"dry run, build {stages['build']}")
    elif stages["build"] == "up-to-date":
        parts.append("build up to date")
    elif stages["build"] == "ran":
        parts.append("built")
    else:
        parts.append(f"build {stages['build']}")
    return style.box(f"run {label}", body, style=st, footer=sep.join(parts))
