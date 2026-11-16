"""A fake capture runner for the ``run`` tests that need no real mmt-dpi
(``test_runner.py``, ``test_command.py``).

The fake is a Python script that reads the runner's records on stdin and
answers like ``templates/runner.c.j2``: the protocols of its arguments (an
id, or a name: ``KNOWN`` gives the registered ones), two attributes of the
plugin's protocol, then per frame a path, and the report. A frame is the
plugin's protocol (``PROTO``) when its UDP destination port (bytes 36-37 of
an Ethernet, IPv4 and UDP frame) is 53; its attribute ``kind`` is then
always extracted, ``size`` only when the frame is longer than 60 bytes.

Environment variables steer it: ``FAKE_RUNNER_LOG`` (write a JSON line:
argv, the plugin directory's names, the cwd, every frame's length and time
stamp), ``FAKE_RUNNER_ERROR`` (a setup error line, exit 3),
``FAKE_RUNNER_CRASH`` (a frame number: "crash N", then SIGSEGV),
``FAKE_RUNNER_SLEEP`` (sleep that long before reading), ``FAKE_RUNNER_NOEND``
(exit 0 without the end line), ``FAKE_RUNNER_STDERR`` (a line per frame on
stderr, as a plugin's printf).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

__all__ = ["DNS", "KNOWN", "PROTO", "SAMPLES", "fake_runner"]


def _samples() -> ModuleType:
    """``tests/unit/scaffold/samples.py``: the capture builders."""
    path = Path(__file__).parents[1] / "scaffold" / "samples.py"
    spec = importlib.util.spec_from_file_location("run_scaffold_samples", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


#: The scaffold tests' capture builders (``samples.udp4``, ``samples.pcap``...).
SAMPLES = _samples()

PROTO = 991
#: Registered protocols by name (lower case).
KNOWN = {"fakeproto": 991, "udp": 354, "other_example": 975}
DNS = (99, 178, 354, PROTO)

_SCRIPT = r"""#!{python}
import json, os, signal, sys, time

KNOWN = {known!r}
NAMES = {{
    99: "ethernet", 178: "ip", 354: "udp", 991: "FAKEPROTO", 975: "OTHER_EXAMPLE", 0: "unknown"
}}
out = os.fdopen(os.dup(1), "w")
os.dup2(2, 1)
args = sys.argv[1:]
if os.environ.get("FAKE_RUNNER_ERROR"):
    out.write("error " + os.environ["FAKE_RUNNER_ERROR"] + "\n")
    out.flush()
    sys.exit(3)
dlt = int(args[0])
protocols = []
for i, name in enumerate(args[1:]):
    pid = int(name) if name.isdigit() else KNOWN.get(name.lower())
    if pid is None:
        out.write(f"unknown {{i}} {{name}}\n")
        protocols.append(None)
        continue
    out.write(f"protocol {{i}} {{pid}} {{NAMES.get(pid, name.upper())}}\n")
    if i == 0:
        out.write(f"attribute 0 2 MMT_U16_DATA size\n")
        out.write(f"attribute 0 1 MMT_U8_DATA kind\n")
    protocols.append(pid)
out.write("ready\n")
out.flush()
if os.environ.get("FAKE_RUNNER_SLEEP"):
    time.sleep(float(os.environ["FAKE_RUNNER_SLEEP"]))
crash = int(os.environ.get("FAKE_RUNNER_CRASH", "0"))
stdin = sys.stdin.buffer
frames = 0
seen = []
paths = {{}}
classified = 0
counts = [0, 0]
while True:
    head = stdin.read(20)
    if not head:
        break
    if len(head) < 20:
        out.write("error a record header cut short on stdin\n")
        sys.exit(3)
    caplen = int.from_bytes(head[0:4], "little")
    data = stdin.read(caplen)
    frames += 1
    seen.append([
        caplen,
        int.from_bytes(head[4:8], "little"),
        int.from_bytes(head[8:16], "little"),
        int.from_bytes(head[16:20], "little"),
    ])
    if os.environ.get("FAKE_RUNNER_STDERR"):
        print(f"plugin says frame {{frames}}")
    if frames == crash:
        out.write(f"crash {{frames}}\n")
        out.flush()
        os.kill(os.getpid(), signal.SIGSEGV)
    if len(data) >= 38 and data[12:14] == b"\x08\x00" and data[36:38] == b"\x00\x35":
        path = (99, 178, 354, 991)
        classified += 1
        counts[1] += 1
        if len(data) > 60:
            counts[0] += 1
    else:
        path = (99, 178, 354, 0) if len(data) >= 38 else (99,)
    paths[path] = paths.get(path, 0) + 1
    if frames % 4 == 0:
        out.write(f"progress {{frames}}\n")
if os.environ.get("FAKE_RUNNER_LOG"):
    with open(os.environ["FAKE_RUNNER_LOG"], "a") as log:
        plugin_dir = os.environ.get("MMT_DPI_PLUGINS_DIR", "")
        log.write(json.dumps({{
            "argv": args,
            "plugins": sorted(os.listdir(plugin_dir)) if plugin_dir else [],
            "cwd": os.listdir("."),
            "frames": seen,
        }}) + "\n")
if os.environ.get("FAKE_RUNNER_NOEND"):
    sys.exit(0)
out.write(f"frames {{frames}} 0\n")
if protocols and protocols[0] is not None:
    out.write(f"classified 0 {{classified}}\n")
    out.write(f"count 0 0 {{counts[0]}}\n")
    out.write(f"count 0 1 {{counts[1]}}\n")
for i, pid in enumerate(protocols[1:], 1):
    if pid is not None:
        out.write(f"classified {{i}} 0\n")
for path, n in paths.items():
    out.write("path " + str(n) + "".join(f" {{p}}" for p in path) + "\n")
out.write("paths_other 0\n")
for pid in sorted({{p for path in paths for p in path}}):
    out.write(f"name {{pid}} {{NAMES[pid]}}\n")
out.write(f"end {{frames}}\n")
out.flush()
"""


def fake_runner(directory: Path) -> Path:
    """Write the fake runner into ``directory``; return its path."""
    directory.mkdir(parents=True, exist_ok=True)
    runner = directory / "fakerunner"
    runner.write_text(_SCRIPT.format(python=sys.executable, known=KNOWN))
    runner.chmod(0o755)
    return runner
