"""A plugin.yaml project against a real mmt-dpi SDK: the generated parent
classification classifies the protocol.

The project's plugin.yaml declares Ethernet as a parent, with a generated
classification that needs one more byte than the ``test`` harness's own
(EtherType 0x88b5, then 0xee) and starts the protocol two bytes later. With
weight 0 it runs before the harness's (weight 1), so the packet test passes
only if the generated function classified the packet; with weight 9 the
harness's runs first, and the same test fails. ``validate`` finds the parent
in the SDK.

A second project is classified above TCP by port, with a match on the
payload (#100): its ``through`` packet test passes, then whole frames go
through the harness that ``test`` built, with and without the sanitizers:
the protocol starts after the TCP header's options, and a frame with
another port, another first byte, too short a payload or only Ethernet
padding after its TCP header is not classified.

The SDK is an extracted mmt-dpi package, a private prefix (never
``/opt/mmt``)::

    MMT_GOLDEN_SDK=<dir>/opt/mmt MMT_GOLDEN_CC=gcc uv run pytest tests/unit/pluginyaml/test_sdk.py

Without ``MMT_GOLDEN_SDK`` the tests skip, unless
``MMT_REQUIRE_GOLDEN_COMPILE=1`` (CI's "Generated code" job) makes them fail.
"""

from __future__ import annotations

import json
import os
import shutil
import struct
from pathlib import Path
from typing import Any

import pytest

from mmt_plugin.cli import main
from mmt_plugin.codegen import generate, scaffold
from mmt_plugin.pluginyaml import load
from mmt_plugin.sdk.profile import DATA_TYPE_GROUP
from mmt_plugin.semantics import analyse
from mmt_plugin.testing import harness
from mmt_plugin.testing.packets import harness_lengths
from mmt_plugin.testing.packets import load as load_packets

from .corpus import profile

SDK_ENV = "MMT_GOLDEN_SDK"
CC_ENV = "MMT_GOLDEN_CC"
REQUIRE_ENV = "MMT_REQUIRE_GOLDEN_COMPILE"

PLUGIN_YAML = """\
schema: 1
protocol:
  label: yamlpar
  id: 962
  encoding: network
sdk:
  profile: "1.10.2"
parents:
  - protocol: ethernet
    weight: WEIGHT
    classify:
      match:
        - {offset: 12, length: 2, value: 0x88b5}
        - {offset: 14, length: 1, value: 0xee}
      offset: 16
attributes:
  - name: version
    type: MMT_U8_DATA
    offset: 0
  - name: length
    type: MMT_U16_DATA
    offset: 1
  - name: payload
    type: MMT_BINARY_DATA
    offset: 3
    length: val(length)
"""

PACKET = """\
schema: 1
id: "yamlpar/basic"
model: "yamlpar"
summary: "the generated Ethernet classification starts the protocol after 0xee and a byte"
parent:
  kind: "none"
  path: []
  selector: "Ethernet, EtherType 0x88b5, then 0xee"
  source: "model-declared"
bytes:
  - "ee 00 07 00 02 ab cd"
bytes_source: "model-declared: 0xee, a pad byte, then the protocol"
expect:
  protocol: "YAMLPAR"
  proto_id: 962
  next:
    kind: "none"
    source: "model-declared"
  attributes:
    - name: "version"
      type: "MMT_U8_DATA"
      offset: 0
      length: 1
      value: 7
      source: "model-declared"
    - name: "length"
      type: "MMT_U16_DATA"
      offset: 1
      length: 2
      value: 2
      source: "model-declared"
    - name: "payload"
      type: "MMT_BINARY_DATA"
      offset: 3
      length: 2
      value: "ab cd"
      source: "model-declared: length bytes"
"""


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


def _json(capsys: pytest.CaptureFixture[str], *argv: str) -> tuple[int, dict[str, Any]]:
    code = main(["--json", *argv])
    doc: dict[str, Any] = json.loads(capsys.readouterr().out)
    return code, doc


def _project(root: Path, weight: int, text: str = PLUGIN_YAML, packet: str = PACKET) -> Path:
    text = text.replace("WEIGHT", str(weight))
    (root / "src").mkdir(parents=True)
    (root / "tests").mkdir()
    (root / "plugin.yaml").write_text(text)
    (root / "tests" / "basic.yaml").write_text(packet)
    analysed, diagnostics = analyse(load(text, filename="plugin.yaml").model, profile=profile())
    assert analysed is not None, diagnostics
    impl = scaffold(generate(analysed, profile()), profile())
    (root / impl.path).write_text(impl.text)
    return root


@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch) -> tuple[Path, str]:
    sdk, cc = _sdk(), _cc()
    for name in ("MMT_PLUGIN_SDK_PROFILE", "MMT_DPI_PLUGINS_DIR", "MMT_BASE", "CC"):
        monkeypatch.delenv(name, raising=False)
    return sdk, cc


def test_the_generated_parent_classification_classifies_the_protocol(
    env: tuple[Path, str], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    sdk, cc = env
    project = _project(tmp_path / "first", 0)
    tool = ["--sdk", str(sdk), "--cc", cc]
    code, doc = _json(capsys, "-C", str(project), "validate", "--sdk", str(sdk))
    assert code == 0, doc["error"]
    checks = {c["id"]: c for c in doc["result"]["checks"]}
    assert checks["parents-exist"]["status"] == "pass"
    assert checks["schema"]["detail"] == "plugin.yaml, schema 1"
    code, doc = _json(capsys, "-C", str(project), "test", *tool)
    assert code == 0, doc["error"]
    assert doc["context"]["sdk"]["profile_source"] == "plugin.yaml"
    assert [p["status"] for p in doc["result"]["packets"]] == ["pass"]
    sanitize = ["--sanitize", "--fuzz-count", "200"]
    code, doc = _json(capsys, "-C", str(project), "test", *tool, *sanitize)
    assert code == 0, doc["error"]


def test_with_a_later_weight_the_harness_classifies_first(
    env: tuple[Path, str], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    sdk, cc = env
    project = _project(tmp_path / "late", 9)
    code, doc = _json(capsys, "-C", str(project), "test", "--sdk", str(sdk), "--cc", cc)
    assert code == 6
    assert doc["error"]["code"] == "test.packet-failed"


TCP_YAML = """\
schema: 1
protocol:
  label: yamltcp
  id: 963
  encoding: network
sdk:
  profile: "1.10.2"
parents:
  - protocol: tcp
    weight: WEIGHT
    classify:
      port: 4840
      match:
        - {offset: 0, length: 2, value: 0x4845}
attributes:
  - name: magic
    type: MMT_U16_DATA
    offset: 0
  - name: kind
    type: MMT_U8_DATA
    offset: 2
"""

TCP_PACKET = """\
schema: 1
id: "yamltcp/basic"
model: "yamltcp"
summary: "HE, then the kind"
through: "tcp:port=4840"
parent:
  kind: "none"
  path: []
  selector: "TCP port 4840"
  source: "model-declared"
bytes:
  - "48 45 07"
bytes_source: "model-declared: the magic HE, then the kind"
expect:
  protocol: "YAMLTCP"
  proto_id: 963
  next:
    kind: "none"
    source: "model-declared"
  attributes:
    - name: "magic"
      type: "MMT_U16_DATA"
      offset: 0
      length: 2
      value: 18501
      source: "model-declared"
    - name: "kind"
      type: "MMT_U8_DATA"
      offset: 2
      length: 1
      value: 7
      source: "model-declared"
"""

#: Two NOPs and a timestamp option (RFC 7323): a TCP header of 32 bytes.
_OPTIONS = bytes([1, 1, 8, 10]) + bytes(8)


def _checksum(data: bytes) -> int:
    if len(data) % 2:
        data += b"\0"
    total = sum(int(word) for word in struct.unpack(f"!{len(data) // 2}H", data))
    while total >> 16:
        total = (total & 0xFFFF) + (total >> 16)
    return ~total & 0xFFFF


def _frame(
    n: int, sport: int, dport: int, payload: bytes, options: bytes = b"", padding: bytes = b""
) -> bytes:
    """Ethernet, IPv4 (source 198.18.0.n) and TCP (PSH and ACK) around
    ``payload``, then ``padding`` after the IP packet: each ``n`` its own
    session."""
    source, destination = bytes([198, 18, 0, n]), bytes([192, 0, 2, 1])
    words = (20 + len(options)) // 4
    tcp = struct.pack("!HHIIBBHHH", sport, dport, 1, 1, words << 4, 0x18, 65535, 0, 0) + options
    pseudo = source + destination + struct.pack("!BBH", 0, 6, len(tcp) + len(payload))
    check = _checksum(pseudo + tcp + payload)
    tcp = tcp[:16] + struct.pack("!H", check) + tcp[18:]
    total = 20 + len(tcp) + len(payload)
    ip = struct.pack("!BBHHHBBH4s4s", 0x45, 0, total, n, 0x4000, 64, 6, 0, source, destination)
    ip = ip[:10] + struct.pack("!H", _checksum(ip)) + ip[12:]
    ethernet = bytes.fromhex("020000000002020000000001") + struct.pack("!H", 0x0800)
    return ethernet + ip + tcp + payload + padding


def test_a_tcp_parent_classifies_by_port_after_the_header_options(
    env: tuple[Path, str], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    sdk, cc = env
    project = _project(tmp_path / "tcp", 5, TCP_YAML, TCP_PACKET)
    tool = ["--sdk", str(sdk), "--cc", cc]
    code, doc = _json(capsys, "-C", str(project), "validate", "--sdk", str(sdk))
    assert code == 0, doc["error"]
    sanitize = ["--sanitize", "--fuzz-count", "50"]
    code, doc = _json(capsys, "-C", str(project), "test", *tool, *sanitize)
    assert code == 0, (doc["error"], doc["result"] and doc["result"]["packets"])
    assert [(p.get("through"), p["status"]) for p in doc["result"]["packets"]] == [
        (None, "pass"),
        ("tcp:port=4840", "pass"),
    ]

    # (frame, the protocol's offset in it or None when not classified, kind)
    cases: list[tuple[bytes, int | None, int | None]] = [
        (_frame(1, 50000, 4840, b"HE\x07"), 54, 7),
        # The header's options: the protocol starts after them; the port is
        # either one.
        (_frame(2, 4840, 50000, b"HE\x09", _OPTIONS), 66, 9),
        (_frame(3, 5000, 4841, b"HE\x07", _OPTIONS), None, None),
        (_frame(4, 50000, 4840, b"HX\x07", _OPTIONS), None, None),
        (_frame(5, 50000, 4840, b"H"), None, None),
        # A pure ACK padded to 60 bytes, the padding what a match would see:
        # the IP length, not the capture, ends the segment.
        (_frame(6, 50000, 4840, b"", padding=b"HE\x07\0\0\0"), None, None),
    ]
    frames = [f for f, _, _ in cases]
    assert len(frames[5]) == 60
    tests = [load_packets(project / "tests" / "basic.yaml", "basic.yaml", _types())]
    names = [n for n, _ in sorted(harness_lengths(tests, _sizes()).items())]
    packets = tmp_path / "frames.bin"
    harness.write_packets(packets, [harness.Record(f, frame=True) for f in frames])
    build = project / "build"
    for program, plugin in (
        (build / "test" / "harness", build / "mmtp_yamltcp.so"),
        (build / "test" / "harness-sanitize", build / "sanitize" / "mmtp_yamltcp.so"),
    ):
        run = harness.run(program, ["check", str(packets)], plugin, sdk / "plugins", timeout=60)
        assert harness.crash_reason(run, len(frames)) is None, run.stderr
        parsed = harness.parse_check(run.lines, names)
        assert parsed.malformed is None and parsed.error is None, run.lines
        for i, (_, offset, kind) in enumerate(cases):
            observed = parsed.observations[i]
            if offset is None:
                assert observed.index is None, (i, observed)
                continue
            # Directly above TCP: meta, Ethernet, IPv4, TCP, then the plugin.
            assert (observed.index, observed.offset) == (4, offset), (i, observed)
            assert observed.values["kind"].number == kind, (i, observed)
            assert observed.values["magic"].number == 0x4845, (i, observed)


def _types() -> set[str]:
    return {c.name for c in profile().constants if c.group == DATA_TYPE_GROUP}


def _sizes() -> dict[str, int]:
    return {c.name: c.size or 0 for c in profile().constants if c.group == DATA_TYPE_GROUP}
