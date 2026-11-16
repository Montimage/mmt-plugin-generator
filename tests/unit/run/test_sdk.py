"""``mmt-plugin run`` against a real mmt-dpi SDK (#103).

The ported DNS example (``examples/dns``, classified on UDP port 53 by its
generated parent code) runs over captures written here: every frame to port
53 is the plugin's, every other one is not, and each attribute's count is
the plugin's packets (or 0 for its session attributes); a second example,
QUIC (UDP port 443), loads with ``--plugin`` and is counted with
``--protocol``; a file that is not a plugin is ``test.load-failed``; a
capture broken after its header reports the frames before; and the memory
the run takes (the ``mmt-plugin`` process and its runner) is the same for a
capture ten times larger.

The SDK is an extracted mmt-dpi package, a private prefix (never
``/opt/mmt``), as for ``tests/unit/build/test_sdk.py``::

    MMT_GOLDEN_SDK=<dir>/opt/mmt MMT_GOLDEN_CC=gcc uv run pytest tests/unit/run/test_sdk.py

Without ``MMT_GOLDEN_SDK`` the tests skip, unless
``MMT_REQUIRE_GOLDEN_COMPILE=1`` (CI's "Generated code" job) makes them fail.
"""

from __future__ import annotations

import json
import os
import shutil
import struct
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from mmt_plugin.cli import main

from . import fakes

samples = fakes.SAMPLES

SDK_ENV = "MMT_GOLDEN_SDK"
CC_ENV = "MMT_GOLDEN_CC"
REQUIRE_ENV = "MMT_REQUIRE_GOLDEN_COMPILE"
EXAMPLES = Path(__file__).resolve().parents[3] / "examples"

#: A DNS query (RFC 1035): id 0x1234, RD, one question www.example.com A IN.
QUERY = bytes.fromhex("12340100000100000000000003777777076578616d706c6503636f6d0000010001")


def _skip_or_fail(why: str) -> None:
    if os.environ.get(REQUIRE_ENV) == "1":
        pytest.fail(f"{REQUIRE_ENV}=1 but {why}")
    pytest.skip(why)


def _sdk() -> Path:
    prefix = os.environ.get(SDK_ENV, "")
    if not prefix:
        _skip_or_fail(f"{SDK_ENV} is not set (an extracted mmt-dpi prefix)")
    return Path(prefix)


def _cc() -> str:
    cc = os.environ.get(CC_ENV, "gcc")
    if shutil.which(cc) is None:
        _skip_or_fail(f"{cc} is not installed")
    return cc


def _example(name: str, tmp_path: Path) -> Path:
    copy = tmp_path / name
    shutil.copytree(EXAMPLES / name, copy, ignore=shutil.ignore_patterns("build"))
    return copy


def _dns(n: int) -> bytes:
    frame: bytes = samples.udp4(20000 + n % 1000, 53, QUERY)
    return frame


def _quic(n: int) -> bytes:
    frame: bytes = samples.udp4(30000 + n % 1000, 443, bytes([0xC3]) + bytes(40))
    return frame


def _other(n: int) -> bytes:
    frame: bytes = samples.udp4(40000 + n % 1000, 9999, b"not dns")
    return frame


def _run(
    project: Path, capture: Path, *args: str, capsys: pytest.CaptureFixture[str]
) -> tuple[int, dict[str, Any]]:
    argv = ["--json", "-C", str(project), "run", str(capture), "--sdk", str(_sdk())]
    code = main([*argv, "--cc", _cc(), *args])
    doc: dict[str, Any] = json.loads(capsys.readouterr().out)
    assert doc["exit_code"] == code
    return code, doc


def test_the_dns_example_over_a_capture(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    project = _example("dns", tmp_path)
    frames = [_dns(n) if n % 3 else _other(n) for n in range(60)]
    capture = tmp_path / "dns.pcap"
    capture.write_bytes(samples.pcap(frames))
    code, doc = _run(project, capture, "--strict", capsys=capsys)
    assert code == 0, (doc["error"], doc["diagnostics"])
    result = doc["result"]
    stages = {s["name"]: s["status"] for s in result["stages"]}
    assert stages == {"build": "ran", "runner": "ran", "capture": "ran"}
    assert "libmmt_tcpip.so" in result["plugins"] and "mmtp_dns_example.so" in result["plugins"]
    assert result["summary"] == {"frames": 60, "processed": 60, "skipped": 0, "classified": 40}
    paths = {p["path"].lower(): p["packets"] for p in result["paths"]}
    dns = next(k for k in paths if k.endswith(".udp.dns_example"))
    assert dns.split(".")[-4:-1] == ["ethernet", "ip", "udp"]
    assert paths[dns] == 40
    assert sum(paths.values()) == 60
    (protocol,) = result["protocols"]
    assert (protocol["name"], protocol["id"], protocol["packets"]) == ("DNS_EXAMPLE", 982, 40)
    counts = {a["name"]: a["packets"] for a in protocol["attributes"]}
    for name in ("tid", "qr", "opcode", "rd", "qdcount", "ancount"):
        assert counts[name] == 40, name
    ids = [a["id"] for a in protocol["attributes"]]
    assert ids == sorted(ids)

    # A second run builds nothing and counts the same.
    code, again = _run(project, capture, capsys=capsys)
    assert code == 0
    stages = {s["name"]: s["status"] for s in again["result"]["stages"]}
    assert stages == {"build": "up-to-date", "runner": "up-to-date", "capture": "ran"}
    assert again["result"]["protocols"] == result["protocols"]
    assert again["result"]["paths"] == result["paths"]


def test_another_plugin_loads_with_plugin_and_is_counted_with_protocol(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    quic = _example("quic", tmp_path)
    argv = ["-q", "-C", str(quic), "build", "--sdk", str(_sdk()), "--cc", _cc()]
    assert main(argv) == 0
    capsys.readouterr()
    project = _example("dns", tmp_path)
    frames = [_dns(n) for n in range(5)] + [_quic(n) for n in range(7)]
    capture = tmp_path / "two.pcap"
    capture.write_bytes(samples.pcap(frames))
    plugin = quic / "build" / "mmtp_quic_example.so"
    code, doc = _run(
        project, capture, "--plugin", str(plugin), "--protocol", "quic_example", capsys=capsys
    )
    assert code == 0, (doc["error"], doc["diagnostics"])
    result = doc["result"]
    assert "mmtp_quic_example.so" in result["plugins"]
    assert [(p["name"], p["id"], p["packets"]) for p in result["protocols"]] == [
        ("DNS_EXAMPLE", 982, 5),
        ("QUIC_EXAMPLE", 986, 7),
    ]
    assert result["protocols"][1]["attributes"]

    code, doc = _run(project, capture, "--protocol", "quic_example", capsys=capsys)
    assert code == 0
    assert [d["code"] for d in doc["diagnostics"]] == ["test.unknown-protocol"]


def test_a_file_that_is_not_a_plugin_does_not_load(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    project = _example("dns", tmp_path)
    bogus = tmp_path / "bogus" / "mmtp_bogus.so"
    bogus.parent.mkdir()
    bogus.write_text("not a shared object\n")
    capture = tmp_path / "dns.pcap"
    capture.write_bytes(samples.pcap([_dns(1)]))
    code, doc = _run(project, capture, "--plugin", str(bogus), capsys=capsys)
    assert code == 6, doc["result"]
    assert doc["error"]["code"] == "test.load-failed"


def test_a_capture_broken_after_its_header_reports_the_frames_before(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    project = _example("dns", tmp_path)
    data = samples.pcap([_dns(1), _other(2), _dns(3), _dns(4)])
    capture = tmp_path / "cut.pcap"
    capture.write_bytes(data[:-7])
    code, doc = _run(project, capture, capsys=capsys)
    assert code == 3
    assert doc["error"]["code"] == "model.bad-pcap"
    assert doc["result"]["summary"] == {
        "frames": 3,
        "processed": 3,
        "skipped": 0,
        "classified": 2,
    }


_MEASURE = """
import json, resource, sys
from mmt_plugin.cli import main
code = main(sys.argv[1:])
print(json.dumps({
    "code": code,
    "self": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    "children": resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
}), file=sys.stderr)
"""


def _write_capture(path: Path, frames: int) -> None:
    """A pcap of ``frames`` frames of about 1 KB, written one at a time:
    DNS queries and other UDP datagrams from 1000 ports, a millisecond
    apart, so mmt-dpi's sessions stop growing early."""
    padding = bytes(900)
    with path.open("wb") as f:
        f.write(struct.pack("<IHHiIII", 0xA1B2C3D4, 2, 4, 0, 0, 65535, 1))
        for n in range(frames):
            if n % 4 == 3:
                frame = samples.udp4(40000 + n % 1000, 9999, padding)
            else:
                frame = samples.udp4(20000 + n % 1000, 53, QUERY + padding[: n % 800])
            stamp = struct.pack("<II", 1_700_000_000 + n // 1000, (n % 1000) * 1000)
            f.write(stamp + struct.pack("<II", len(frame), len(frame)) + frame)


def _measure(project: Path, capture: Path) -> dict[str, Any]:
    argv = [
        "-q",
        "--json",
        "-C",
        str(project),
        "run",
        str(capture),
        "--sdk",
        str(_sdk()),
        "--cc",
        _cc(),
    ]
    proc = subprocess.run(
        [sys.executable, "-c", _MEASURE, *argv], capture_output=True, text=True, check=False
    )
    measured: dict[str, Any] = json.loads(proc.stderr.strip().splitlines()[-1])
    measured["result"] = json.loads(proc.stdout)["result"]
    return measured


def test_a_capture_ten_times_larger_takes_the_same_memory(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    project = _example("dns", tmp_path)
    small, large = tmp_path / "small.pcap", tmp_path / "large.pcap"
    _write_capture(small, 20_000)  # about 20 MB
    _write_capture(large, 200_000)  # about 200 MB
    # Build the plugin and the runner first: the measured runs only run.
    code, doc = _run(project, small, capsys=capsys)
    assert code == 0, doc["error"]
    first, second = _measure(project, small), _measure(project, large)
    assert first["code"] == second["code"] == 0
    assert first["result"]["summary"]["frames"] == 20_000
    assert second["result"]["summary"]["frames"] == 200_000
    assert second["result"]["summary"]["classified"] == 150_000
    # ru_maxrss is in kilobytes on Linux.
    assert second["children"] <= first["children"] * 1.25 + 8_192, (first, second)
    assert second["self"] <= first["self"] * 1.25 + 8_192, (first, second)
