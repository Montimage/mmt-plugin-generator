"""The capture runner of ``mmt-plugin run``: rendering it, and running it
over a capture in constant memory.

``runner_source`` renders ``templates/runner.c.j2`` for an SDK profile (the
names of its data types). ``record`` encodes one frame as the runner reads
it on stdin: the captured length and the length on the wire, the time stamp
(seconds and nanoseconds), then the bytes.

``run`` starts a compiled runner with a plugin directory of its own
(``MMT_DPI_PLUGINS_DIR``, symbolic links to the given plugin files; never
the host's plugin directory) and an empty current directory (mmt-dpi also
loads ``./plugins``), in its own process group, and streams the frames of a
capture to its stdin in batches, while two threads read its stdout (the
report, parsed as it arrives into a ``Report`` whose size does not depend
on the number of frames) and its stderr (only its last lines are kept;
``echo`` sees every one). Frames of another link type than the first
frame's are not sent: mmt-dpi reads one link type per handler. A frame
iterator that fails (``PcapError``) stops the stream at the last whole
record, so the runner still reports what it saw. The runner is killed on a
timeout or any exception (SIGINT included).
"""

from __future__ import annotations

import contextlib
import os
import signal
import subprocess
import tempfile
import threading
from collections import deque
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

import jinja2

from mmt_plugin.pcap.reader import Frame
from mmt_plugin.sdk.profile import DATA_TYPE_GROUP, Profile

__all__ = [
    "LINKTYPE_DLT",
    "SETUP_EXIT",
    "CaptureRun",
    "ProtocolReport",
    "Report",
    "dlt_of",
    "record",
    "run",
    "runner_source",
]

#: The exit status of a runner whose setup failed (an ``error`` line).
SETUP_EXIT = 3
#: The runner keeps at most this many protocol paths (``RUNNER_PATHS``).
MAX_PATHS = 1024
#: Bytes written to the runner's stdin at once.
BATCH = 1 << 20
#: The stderr lines kept for a failure's message.
STDERR_TAIL = 20

#: A pcap LINKTYPE_* whose libpcap DLT_* value differs on Linux:
#: LINKTYPE_RAW (101) is DLT_RAW (12). Every other one is the same number.
LINKTYPE_DLT: Mapping[int, int] = {101: 12}

_NANO = 1_000_000_000

_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.PackageLoader("mmt_plugin.capture", "templates"),
    undefined=jinja2.StrictUndefined,
    autoescape=False,
    trim_blocks=True,
    lstrip_blocks=True,
    keep_trailing_newline=True,
    newline_sequence="\n",
    auto_reload=False,
)


def runner_source(profile: Profile) -> str:
    """The runner's C source for ``profile``."""
    types = [c.name for c in profile.constants if c.group == DATA_TYPE_GROUP]
    return _ENVIRONMENT.get_template("runner.c.j2").render(profile=profile.version, types=types)


def dlt_of(linktype: int) -> int:
    """The DLT_* value mmt-dpi's handler takes for a capture's LINKTYPE_*."""
    return LINKTYPE_DLT.get(linktype, linktype)


def record(frame: Frame) -> bytes:
    """``frame`` as the runner reads it on stdin."""
    seconds, nanos = divmod(max(frame.timestamp, 0), _NANO)
    return (
        len(frame.data).to_bytes(4, "little")
        + min(frame.original, 0xFFFFFFFF).to_bytes(4, "little")
        + min(seconds, (1 << 63) - 1).to_bytes(8, "little")
        + nanos.to_bytes(4, "little")
        + frame.data
    )


@dataclass
class ProtocolReport:
    """One protocol the runner counts: its name as asked, its id (``None``:
    not registered), its attributes (id, type, name, in order), the packets
    whose path has it and, per attribute, the packets that have it."""

    name: str
    id: int | None = None
    attributes: list[tuple[int, str, str]] = field(default_factory=list)
    packets: int = 0
    counts: list[int] = field(default_factory=list)


@dataclass
class Report:
    """The runner's output, read line by line (``feed``)."""

    protocols: list[ProtocolReport] = field(default_factory=list)
    error: str | None = None
    ready: bool = False
    progress: int = 0
    crash: int | None = None
    frames: int | None = None
    unprocessed: int = 0
    paths: list[tuple[int, tuple[int, ...]]] = field(default_factory=list)
    paths_other: int = 0
    names: dict[int, str] = field(default_factory=dict)
    end: int | None = None
    malformed: str | None = None

    def feed(self, line: str) -> None:
        """Read one line; the first one it cannot read is ``malformed``
        and every later one is ignored."""
        if self.malformed is not None:
            return
        words = line.split(" ")
        head = words[0]
        try:
            if head == "error":
                self.error = line.partition(" ")[2]
            elif head == "protocol" and len(words) >= 4:
                self._protocol(int(words[1]), " ".join(words[3:])).id = int(words[2])
            elif head == "unknown" and len(words) >= 3:
                self._protocol(int(words[1]), " ".join(words[2:]))
            elif head == "attribute" and len(words) >= 5:
                protocol = self.protocols[int(words[1])]
                protocol.attributes.append((int(words[2]), words[3], " ".join(words[4:])))
                protocol.counts.append(0)
            elif head == "ready":
                self.ready = True
            elif head == "progress":
                self.progress = int(words[1])
            elif head == "crash":
                self.crash = int(words[1])
            elif head == "frames":
                self.frames, self.unprocessed = int(words[1]), int(words[2])
            elif head == "classified":
                self.protocols[int(words[1])].packets = int(words[2])
            elif head == "count":
                self.protocols[int(words[1])].counts[int(words[2])] = int(words[3])
            elif head == "path" and len(words) >= 2:
                if len(self.paths) >= MAX_PATHS:
                    raise ValueError("too many paths")
                self.paths.append((int(words[1]), tuple(int(w) for w in words[2:])))
            elif head == "paths_other":
                self.paths_other = int(words[1])
            elif head == "name" and len(words) >= 3:
                self.names[int(words[1])] = " ".join(words[2:])
            elif head == "end":
                self.end = int(words[1])
            else:
                raise ValueError(line)
        except (ValueError, IndexError):
            self.malformed = line

    def _protocol(self, index: int, name: str) -> ProtocolReport:
        if index != len(self.protocols):
            raise ValueError(f"protocol {index} out of order")
        protocol = ProtocolReport(name)
        self.protocols.append(protocol)
        return protocol


@dataclass
class CaptureRun:
    """One runner run: its exit status (negative: the signal that killed
    it), its report, the last lines of its stderr, the frames sent, the
    frames of another link type (not sent), the DLT the handler read, why
    the capture stopped early (``capture_error``), and whether it timed
    out."""

    returncode: int
    report: Report
    stderr: str = ""
    sent: int = 0
    other_linktype: int = 0
    dlt: int | None = None
    linktype: int | None = None
    capture_error: Exception | None = None
    timed_out: bool = False

    def crash_reason(self) -> str | None:
        """Why the runner failed, or ``None`` when it ended normally (with
        its ``end`` line, or its setup error)."""
        if self.timed_out:
            return "timed out"
        if self.returncode < 0:
            with contextlib.suppress(ValueError):
                return f"killed by {signal.Signals(-self.returncode).name}"
            return f"killed by signal {-self.returncode}"
        if self.report.malformed is not None:
            return f"unreadable runner output: {self.report.malformed!r}"
        if self.returncode == SETUP_EXIT and self.report.error is not None:
            return None
        if self.returncode != 0:
            return f"exit status {self.returncode}"
        if self.report.end is None:
            return "the runner exited before the end (exit status 0)"
        return None


def _kill(proc: subprocess.Popen[bytes]) -> None:
    with contextlib.suppress(ProcessLookupError, PermissionError):
        os.killpg(proc.pid, signal.SIGKILL)
    with contextlib.suppress(Exception):
        proc.wait()


def _peek(frames: Iterator[Frame]) -> tuple[Frame | None, Exception | None]:
    """The first frame, or the error reading it."""
    try:
        return next(frames, None), None
    except Exception as exc:  # the reader's PcapError, or an OSError
        return None, exc


def run(
    runner: Path,
    frames: Iterable[Frame],
    plugins: Mapping[str, Path],
    protocols: Sequence[str],
    *,
    timeout: float | None = None,
    log: Callable[[str], None] | None = None,
    echo: Callable[[str], None] | None = None,
    on_frames: Callable[[int], None] | None = None,
    env: Mapping[str, str] | None = None,
    errors: tuple[type[Exception], ...] = (Exception,),
) -> CaptureRun:
    """Run ``runner`` over ``frames`` with the plugin directory ``plugins``
    (file name to plugin file), counting ``protocols`` (the plugin's
    first). ``errors`` are the exceptions of ``frames`` that stop the
    stream (``capture_error``) instead of propagating. ``on_frames`` sees the
    number of frames sent, after each batch."""
    iterator = iter(frames)
    first, error = _peek(iterator)
    if error is not None and not isinstance(error, errors):
        raise error
    linktype = first.linktype if first is not None else None
    dlt = dlt_of(linktype) if linktype is not None else dlt_of(1)
    with tempfile.TemporaryDirectory(prefix="mmt-plugin-run-") as tmp:
        root = Path(tmp)
        plugin_dir = root / "plugins"
        plugin_dir.mkdir()
        for name, target in plugins.items():
            (plugin_dir / name).symlink_to(os.path.realpath(target))
        cwd = root / "run"
        cwd.mkdir()
        inherited = {
            k: v
            for k, v in (os.environ if env is None else env).items()
            if k not in ("LD_LIBRARY_PATH", "LD_PRELOAD")
        }
        environment = {**inherited, "MMT_DPI_PLUGINS_DIR": str(plugin_dir), "LC_ALL": "C"}
        argv = [str(runner), str(dlt), *protocols]
        if log is not None:
            log(f"MMT_DPI_PLUGINS_DIR={plugin_dir} {' '.join(argv)} < frames")
        proc = subprocess.Popen(
            argv,
            cwd=cwd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=environment,
            start_new_session=True,
        )
        report = Report()
        tail: deque[str] = deque(maxlen=STDERR_TAIL)

        def read_stdout() -> None:
            assert proc.stdout is not None
            for raw in proc.stdout:
                report.feed(raw.decode("utf-8", "replace").rstrip("\n"))

        def read_stderr() -> None:
            assert proc.stderr is not None
            for raw in proc.stderr:
                text = raw.decode("utf-8", "replace")
                tail.append(text)
                if echo is not None:
                    echo(text)

        readers = [
            threading.Thread(target=read_stdout, daemon=True),
            threading.Thread(target=read_stderr, daemon=True),
        ]
        for reader in readers:
            reader.start()
        timed_out = threading.Event()

        def expire() -> None:
            timed_out.set()
            _kill(proc)

        timer = threading.Timer(timeout, expire) if timeout else None
        if timer is not None:
            timer.start()
        sent = other = 0
        try:
            assert proc.stdin is not None
            batch = bytearray()
            pending = first
            with contextlib.suppress(BrokenPipeError):
                while pending is not None:
                    if pending.linktype == linktype:
                        batch += record(pending)
                        sent += 1
                    else:
                        other += 1
                    if len(batch) >= BATCH:
                        proc.stdin.write(batch)
                        batch.clear()
                        if on_frames is not None:
                            on_frames(sent)
                    try:
                        pending = next(iterator, None)
                    except errors as exc:
                        error, pending = exc, None
                if batch:
                    proc.stdin.write(batch)
                    if on_frames is not None:
                        on_frames(sent)
            with contextlib.suppress(BrokenPipeError, OSError):
                proc.stdin.close()
            proc.wait()
            for reader in readers:
                reader.join()
        except BaseException:
            _kill(proc)
            raise
        finally:
            if timer is not None:
                timer.cancel()
        return CaptureRun(
            proc.returncode,
            report,
            "".join(tail),
            sent,
            other,
            dlt,
            linktype,
            error,
            timed_out.is_set(),
        )
