"""The host harness of ``mmt-plugin test``: rendering, compiling and
running it.

``harness_source`` renders ``templates/harness.c.j2`` for one plugin (its
protocol id and name) and the attributes the packet tests name;
``baseline_source`` renders ``templates/baseline.c.j2``, the empty plugin
``--bench`` compares with. Both take every SDK name the plugin side uses
from the profile (the classification names of the scaffold's example,
``mmt_plugin.codegen.scaffold.classification_names``).

``run`` runs a compiled harness on a packet file with one plugin: in a
temporary directory, a plugin directory holds the SDK's ``libmmt_tcpip.so``
and the plugin, and ``MMT_DPI_PLUGINS_DIR`` names it (never the host's
plugin directory); the current directory is an empty one, since mmt-dpi
also loads ``./plugins``. The harness runs in its own process group, killed
on a timeout or any exception (SIGINT included). With the sanitizers,
``ASAN_OPTIONS`` and ``UBSAN_OPTIONS`` make the first error end the run with
``SANITIZER_EXIT``; leak detection is off (mmt-dpi keeps its tables until
exit).

``parse_check`` reads the output of ``harness check`` into one
``mmt_plugin.testing.packets.Observation`` per packet.
"""

from __future__ import annotations

import contextlib
import os
import re
import shlex
import signal
import subprocess
import tempfile
import threading
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

import jinja2

from mmt_plugin.codegen import Generation
from mmt_plugin.codegen.scaffold import classification_names
from mmt_plugin.sdk.profile import DATA_TYPE_GROUP, Profile
from mmt_plugin.testing.packets import Observation, ObservedValue

__all__ = [
    "ETHERTYPE",
    "SANITIZER_EXIT",
    "TCPIP",
    "HarnessRun",
    "ParsedCheck",
    "baseline_source",
    "crash_reason",
    "harness_source",
    "parse_check",
    "run",
    "write_packets",
]

#: The EtherType the harness attaches the protocol under (IEEE 802 local
#: experimental, as in the scaffold's example).
ETHERTYPE = 0x88B5
#: The exit status of a harness a sanitizer stopped.
SANITIZER_EXIT = 99
#: The exit status of a harness whose setup failed (an ``error`` line).
SETUP_EXIT = 3
#: The SDK plugin the plugin under test loads after (its parents).
TCPIP = "libmmt_tcpip.so"

_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.PackageLoader("mmt_plugin.testing", "templates"),
    undefined=jinja2.StrictUndefined,
    autoescape=False,
    trim_blocks=True,
    lstrip_blocks=True,
    keep_trailing_newline=True,
    newline_sequence="\n",
    auto_reload=False,
)

_SANITIZER_REPORT = re.compile(
    r"ERROR: AddressSanitizer|runtime error:|ERROR: UndefinedBehaviorSanitizer"
)
#: ASan's first line, ``==PID==ERROR: AddressSanitizer: KIND on address ...``:
#: the kind is kept, the pid and the addresses (different on every run) are not.
_ASAN = re.compile(r"ERROR: AddressSanitizer: ([\w-]+)")
#: UBSan's, ``FILE:LINE:COL: runtime error: MESSAGE``.
_UBSAN = re.compile(r"([^\s:]+):([0-9]+(?::[0-9]+)?): runtime error: (.*)$")
_ADDRESS = re.compile(r"0x[0-9a-f]+")


def _report(line: str) -> str:
    """A sanitizer's report line, without what changes from run to run."""
    asan = _ASAN.search(line)
    if asan is not None:
        return f"AddressSanitizer: {asan.group(1)}"
    ubsan = _UBSAN.search(line)
    if ubsan is not None:
        file, position, message = ubsan.groups()
        line = f"{os.path.basename(file)}:{position}: runtime error: {message}"
    return _ADDRESS.sub("0x...", line.strip())


@dataclass(frozen=True)
class _Attribute:
    name: str
    length: int


def harness_source(
    generation: Generation, profile: Profile, attributes: Sequence[tuple[str, int]]
) -> str:
    """The harness of ``generation``'s protocol; ``attributes`` are the
    names it reads and the bytes it prints for a type with no integer or
    binary form."""
    names, includes = classification_names(profile)
    types = [c.name for c in profile.constants if c.group == DATA_TYPE_GROUP]
    headers = [*includes]
    extra = (profile.constant(types[0]).header, profile.struct("attribute_metadata_t").header)
    for header in extra:
        if header not in headers:
            headers.append(header)
    return _ENVIRONMENT.get_template("harness.c.j2").render(
        name=generation.name,
        proto_id=generation.proto_id,
        profile=profile.version,
        ethertype=ETHERTYPE,
        includes=headers,
        types=types,
        attributes=[_Attribute(n, length) for n, length in attributes],
        sdk=names,
    )


def baseline_source(generation: Generation, profile: Profile) -> str:
    """The empty plugin of ``generation``'s protocol: its id and name, no
    attribute."""
    init_struct = profile.function("init_protocol_struct_for_registration")
    register = profile.function("register_protocol")
    used = {init_struct.header, register.header}
    for t in profile.types:
        if t.name == "protocol_t":
            used.add(t.header)
    return _ENVIRONMENT.get_template("baseline.c.j2").render(
        name=generation.name,
        proto_id=generation.proto_id,
        profile=profile.version,
        includes=[h.name for h in profile.headers if h.name in used],
        protocol_t="protocol_t",
        init_struct=init_struct.name,
        register_protocol=register.name,
    )


def write_packets(path: Path, packets: Sequence[bytes]) -> None:
    """The packet file of the harness: a 4-byte little-endian length, then
    the bytes, per packet."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"".join(len(p).to_bytes(4, "little") + p for p in packets))


@dataclass
class HarnessRun:
    """One harness run: its exit status (negative: the signal that killed
    it), its stdout lines, its stderr, and whether it timed out."""

    returncode: int
    lines: list[str] = field(default_factory=list)
    stderr: str = ""
    timed_out: bool = False


def crash_reason(run: HarnessRun) -> str | None:
    """Why the harness crashed, or ``None`` when it ended normally (0, or
    the setup error ``SETUP_EXIT``)."""
    if run.timed_out:
        return "timed out"
    lines = run.stderr.splitlines()
    report = next((_report(x) for x in lines if _SANITIZER_REPORT.search(x)), None)
    if run.returncode == SANITIZER_EXIT or report is not None:
        return report or "a sanitizer stopped the harness"
    if run.returncode < 0:
        with contextlib.suppress(ValueError):
            return f"killed by {signal.Signals(-run.returncode).name}"
        return f"killed by signal {-run.returncode}"
    if run.returncode not in (0, SETUP_EXIT):
        return f"exit status {run.returncode}"
    return None


def _kill(proc: subprocess.Popen[str]) -> None:
    """Kill the harness's process group (as ``build`` kills the compiler's)."""
    with contextlib.suppress(ProcessLookupError, PermissionError):
        os.killpg(proc.pid, signal.SIGKILL)
    with contextlib.suppress(Exception):
        proc.wait()


def run(
    harness: Path,
    args: Sequence[str],
    plugin: Path,
    sdk_plugins: Path,
    *,
    timeout: float,
    on_line: Callable[[str], None] | None = None,
    log: Callable[[str], None] | None = None,
    env: Mapping[str, str] | None = None,
) -> HarnessRun:
    """Run ``harness args`` with the plugin directory ``{libmmt_tcpip.so,
    plugin}`` (``sdk_plugins`` is the SDK's plugin directory); ``on_line``
    sees each stdout line as it arrives."""
    with tempfile.TemporaryDirectory(prefix="mmt-plugin-test-") as tmp:
        root = Path(tmp)
        plugins = root / "plugins"
        plugins.mkdir()
        (plugins / TCPIP).symlink_to(os.path.realpath(sdk_plugins / TCPIP))
        (plugins / plugin.name).symlink_to(os.path.realpath(plugin))
        cwd = root / "run"
        cwd.mkdir()
        environment = {
            **(os.environ if env is None else env),
            "MMT_DPI_PLUGINS_DIR": str(plugins),
            "LC_ALL": "C",
            "ASAN_OPTIONS": f"detect_leaks=0:halt_on_error=1:exitcode={SANITIZER_EXIT}",
            "UBSAN_OPTIONS": f"halt_on_error=1:print_stacktrace=1:exitcode={SANITIZER_EXIT}",
        }
        argv = [str(harness), *args]
        if log is not None:
            log(f"MMT_DPI_PLUGINS_DIR={plugins} {shlex.join(argv)}")
        stderr_path = root / "stderr"
        with stderr_path.open("w+", encoding="utf-8", errors="replace") as stderr:
            proc = subprocess.Popen(
                argv,
                cwd=cwd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=stderr,
                text=True,
                errors="replace",
                env=environment,
                start_new_session=True,
            )
            timed_out = threading.Event()

            def expire() -> None:
                timed_out.set()
                _kill(proc)

            timer = threading.Timer(timeout, expire)
            timer.start()
            lines: list[str] = []
            try:
                assert proc.stdout is not None
                for raw in proc.stdout:
                    line = raw.rstrip("\n")
                    lines.append(line)
                    if on_line is not None:
                        on_line(line)
                proc.wait()
            except BaseException:
                _kill(proc)
                raise
            finally:
                timer.cancel()
            stderr.seek(0)
            text = stderr.read()
        return HarnessRun(proc.returncode, lines, text, timed_out.is_set())


@dataclass
class ParsedCheck:
    """``harness check`` output: the protocol the plugin registered (id and
    name), the setup error, each packet's observation (by its index in the
    file), and the packet being processed when the output ends early."""

    plugin: tuple[int, str] | None = None
    error: str | None = None
    observations: dict[int, Observation] = field(default_factory=dict)
    unfinished: int | None = None


def _value(words: list[str]) -> ObservedValue:
    """``attr N missing`` / ``attr N TYPE absent|int V|ptr V|hex H``, after ``N``."""
    if words[0] == "missing":
        return ObservedValue("missing")
    type_name, kind = words[0], words[1] if len(words) > 1 else "absent"
    if kind == "absent":
        return ObservedValue("absent", type_name)
    if kind in ("int", "ptr"):
        return ObservedValue(kind, type_name, number=int(words[2]))
    return ObservedValue("hex", type_name, data=bytes.fromhex(words[2] if len(words) > 2 else ""))


def parse_check(lines: Sequence[str], names: Sequence[str]) -> ParsedCheck:
    """Read ``harness check`` output; ``names`` are the harness's attributes,
    in order."""
    parsed = ParsedCheck()
    current: int | None = None
    index: int | None = None
    next_id: int | None = None
    next_offset: int | None = None
    values: dict[str, ObservedValue] = {}
    for line in lines:
        words = line.split(" ")
        head = words[0]
        if head == "protocol" and len(words) >= 3:
            parsed.plugin = (int(words[1]), " ".join(words[2:]))
        elif head == "error":
            parsed.error = line.partition(" ")[2]
        elif head == "packet":
            current, index, next_id, next_offset, values = int(words[1]), None, None, None, {}
        elif head == "proto" and current is not None:
            index = None if words[1] == "none" else int(words[1])
        elif head == "next" and current is not None and words[1] != "none":
            next_id, next_offset = int(words[1]), int(words[2])
        elif head == "attr" and current is not None:
            values[names[int(words[1])]] = _value(words[2:])
        elif head == "done" and current is not None:
            parsed.observations[current] = Observation(index, next_id, next_offset, values)
            current = None
    parsed.unfinished = current
    return parsed
