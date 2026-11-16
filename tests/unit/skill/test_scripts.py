"""The mmt-plugin-generator skill's capture scripts, without an SDK.

``scripts/make_pcap.py`` writes a synthetic capture: what ``mmt_plugin.pcap``
slices back out of it under the parent is each payload, byte for byte, and
every checksum holds. ``scripts/pcap_eval.py``'s filters, comparisons and
report are checked on hand-made runs; ``test_sdk.py`` runs it on a built
plugin.
"""

from __future__ import annotations

import struct
from pathlib import Path
from typing import Any

import pytest

import make_pcap
import pcap_eval
from mmt_plugin.pcap import parent_of, read_stream, slice_payloads

SKILL = Path(__file__).resolve().parents[3] / "skills" / "mmt-plugin-generator"


def _slice(path: Path, proto: str, keys: list[tuple[str, str]]) -> list[tuple[int, bytes]]:
    parent = parent_of(f"{proto}:test", proto, keys)
    with path.open("rb") as f:
        sliced = slice_payloads(read_stream(f).frames(), parent, 1000)
    return [(p.frame, p.data) for p in sliced.payloads]


@pytest.mark.parametrize(
    ("selector", "proto", "keys"),
    [
        ("udp:dport=5684", "udp", [("dport", "5684")]),
        ("udp:sport=5684", "udp", [("sport", "5684")]),
        ("ip:proto=253", "ip", [("proto", "253")]),
        ("ipv6:proto=253", "ipv6", [("proto", "253")]),
        ("ethernet:ethertype=0x88b5", "ethernet", [("ethertype", "0x88b5")]),
    ],
)
def test_each_client_payload_comes_back_under_its_parent(
    selector: str, proto: str, keys: list[tuple[str, str]], tmp_path: Path
) -> None:
    out = tmp_path / "c.pcap"
    payloads = ["12 01 00 0c 00 00 00 2a de ad be ef", "0x10:02:00:08", "s:aa bb"]
    args = ["--parent", selector, "--out", str(out)]
    assert make_pcap.main([*args, *(f"--payload={p}" for p in payloads)]) == 0
    got = [data for _, data in _slice(out, proto, keys)]
    wanted = [bytes.fromhex("1201000c0000002adeadbeef"), bytes.fromhex("10020008")]
    if proto in ("ip", "ipv6", "ethernet"):
        wanted.append(bytes.fromhex("aabb"))  # no port: both directions match
    # Ethernet pads short frames to 60 bytes: the payload is a prefix.
    assert len(got) == len(wanted)
    for g, w in zip(got, wanted, strict=True):
        assert g[: len(w)] == w


def test_a_tcp_session_has_its_handshake_and_both_directions(tmp_path: Path) -> None:
    out = tmp_path / "t.pcap"
    lines = tmp_path / "payloads.txt"
    lines.write_text("# a request and its answer\n03 00 00 07 02 f0 80\n\ns:03 00 00 05 aa\n")
    assert (
        make_pcap.main(
            ["--parent", "tcp:port=102", "--out", str(out), "--payloads-file", str(lines)]
        )
        == 0
    )
    with out.open("rb") as f:
        frames = list(read_stream(f).frames())
    # SYN, SYN-ACK, ACK; each payload and its ACK; FIN, FIN, ACK.
    assert len(frames) == 3 + 2 * 2 + 3
    got = _slice(out, "tcp", [("port", "102")])
    assert got == [
        (4, bytes.fromhex("03 00 00 07 02 f0 80")),
        (6, bytes.fromhex("03 00 00 05 aa")),
    ]
    # Sequence numbers follow the bytes sent: the answer's ACK acknowledges 7.
    tcp_of = [fr.data[14 + 20 :] for fr in frames]
    seq4 = struct.unpack("!I", tcp_of[3][4:8])[0]
    ack5 = struct.unpack("!I", tcp_of[4][8:12])[0]
    assert ack5 == seq4 + 7


def test_the_checksums_hold(tmp_path: Path) -> None:
    out = tmp_path / "u.pcap"
    assert (
        make_pcap.main(["--parent", "udp:dport=5684", "--out", str(out), "--payload", "01 02 03"])
        == 0
    )
    with out.open("rb") as f:
        (frame,) = list(read_stream(f).frames())
    ip = frame.data[14:34]
    assert make_pcap.checksum(ip) == 0
    udp = frame.data[34 : 34 + 11]
    pseudo = ip[12:20] + struct.pack("!BBH", 0, 17, len(udp))
    assert make_pcap.checksum(pseudo + udp) == 0


@pytest.mark.parametrize(
    "args",
    [
        ["--parent", "udp", "--payload", "01"],
        ["--parent", "sctp:port=1", "--payload", "01"],
        ["--parent", "udp:port=x", "--payload", "01"],
        ["--parent", "udp:proto=1", "--payload", "01"],
        ["--parent", "udp:port=1", "--payload", "zz"],
        ["--parent", "udp:port=1"],
        ["--parent", "udp:port=1", "--payload", "01", "--repeat", "0"],
    ],
)
def test_a_bad_argument_is_exit_2(args: list[str], tmp_path: Path) -> None:
    assert make_pcap.main([*args, "--out", str(tmp_path / "x.pcap")]) == 2
    assert not (tmp_path / "x.pcap").exists()


# --- pcap_eval.py ------------------------------------------------------------


@pytest.mark.parametrize(
    ("selector", "expect", "scope"),
    [
        ("udp:dport=5684", "udp.port == 5684 && udp.length > 8", "udp.port == 5684"),
        ("tcp:port=0x66", "tcp.port == 102 && tcp.len > 0", "tcp.port == 102"),
        ("ethernet:ethertype=0x88b5", "eth.type == 0x88b5", "eth.type == 0x88b5"),
        ("ip:proto=253", "ip.proto == 253", "ip.proto == 253"),
        ("ipv6:proto=253", "ipv6.nxt == 253", "ipv6.nxt == 253"),
    ],
)
def test_the_default_filters_follow_the_parent(selector: str, expect: str, scope: str) -> None:
    assert pcap_eval.default_filters(selector) == (expect, scope)


@pytest.mark.parametrize("selector", ["tcp", "ethernet", "sctp:port=1"])
def test_a_parent_without_a_default_filter_is_a_usage_error(selector: str) -> None:
    with pytest.raises(pcap_eval.EvalExit) as exc:
        pcap_eval.default_filters(selector)
    assert exc.value.code == pcap_eval.EXIT_USAGE


@pytest.mark.parametrize(
    ("a", "b"),
    [("12", "0x000c"), ("de:ad:be:ef", "deadbeef"), ("DE AD", "dead"), ("text", "text")],
)
def test_values_compare_by_meaning(a: str, b: str) -> None:
    assert pcap_eval.normalize(a) == pcap_eval.normalize(b)


def test_fields_are_compared_on_the_expected_frames_only() -> None:
    dump = [
        {"frame": 1, "path": "x", "attributes": {"length": "12"}},
        {"frame": 2, "path": "x", "attributes": {"length": "9"}},
        {"frame": 3, "path": "x", "attributes": {}},
        {"frame": 4, "path": "x", "attributes": {"length": "1"}},
    ]
    reference = {1: {"length": "0x0c"}, 2: {"length": "8"}, 3: {"length": "5"}, 4: {"length": "7"}}
    rep = pcap_eval.compare_fields(dump, reference, {"length": "x.len"}, expected={1, 2, 3})
    assert rep["length"]["compared"] == 3
    assert rep["length"]["matched"] == 1
    assert rep["length"]["missing_in_plugin"] == 1
    assert [m["frame"] for m in rep["length"]["mismatches"]] == [2, 3]


def test_displaced_names_known_paths_only() -> None:
    baseline = {"paths": {"a.udp.unknown": 5, "a.tcp.http": 4, "a.tcp": 2}}
    plugin = {"paths": {"a.udp.TELEM": 5, "a.tcp.http": 1, "a.tcp": 2, "a.tcp.TELEM": 3}}
    assert pcap_eval.displaced(baseline, plugin, "telem") == {"a.tcp.http": 3}


def _report(**over: Any) -> dict[str, Any]:
    r: dict[str, Any] = {
        "verdict": "PASS",
        "problems": [],
        "warnings": ["synthetic capture"],
        "capture": {"path": "c.pcap", "sha256": "0" * 64, "synthetic": True},
        "plugin": {"path": "p.so", "sha256": "1" * 64, "label": "telem"},
        "parent": "udp:dport=5684",
        "expected": {"source": "tshark", "filter": "udp.port == 5684", "frames": 2},
        "frames": 2,
        "claimed": 2,
        "hit": 2,
        "recall": 1.0,
        "missed_frames": [],
        "foreign_frames": [],
        "fields": {
            "length": {"tshark_field": "x.len", "compared": 2, "matched": 2, "agreement": 1.0}
        },
        "attributes": {"length": {"present": 2, "values": {"12": 2}, "other_values": 0}},
        "paths": {"baseline": {"a.unknown": 2}, "plugin": {"a.TELEM": 2}, "displaced": {}},
    }
    r.update(over)
    return r


def test_the_markdown_report_has_every_section() -> None:
    text = pcap_eval.markdown(_report())
    assert text.startswith("# Capture evaluation: telem — PASS")
    assert "**synthetic**" in text
    for heading in (
        "## Warnings",
        "## Fields against tshark",
        "## Attributes",
        "## Protocol paths",
    ):
        assert heading in text
    assert "| `a.TELEM` | 0 | 2 |" in text
    failed = pcap_eval.markdown(_report(verdict="FAIL", problems=["recall 0%"], missed_frames=[3]))
    assert "## Problems" in failed and "Missed frames (first 50): 3" in failed


def test_the_runner_source_is_shipped_next_to_the_script() -> None:
    assert pcap_eval.RUNNER_SRC == SKILL / "scripts" / "pcap_eval.c"
    assert pcap_eval.RUNNER_SRC.is_file()


def test_the_runner_links_the_core_shared_object_of_an_extracted_package(
    tmp_path: Path,
) -> None:
    """The package's links point to absolute /opt/mmt paths, which dangle in
    an extracted prefix: the runner links the newest libmmt_core.so.<version>
    file, never -lmmt_core (which would fall back to libmmt_core.a), and its
    run path resolves the soname to that file."""
    lib = tmp_path / "sdk" / "dpi" / "lib"
    lib.mkdir(parents=True)
    for name in ("libmmt_core.so.1.10.2", "libmmt_core.so.1.10.10", "libmmt_core.a"):
        (lib / name).write_bytes(b"")
    for name in ("libmmt_core.so", "libmmt_core.so.1"):
        (lib / name).symlink_to("/nonexistent/opt/mmt/dpi/lib/libmmt_core.so.1.10.10")
    core = pcap_eval.core_library(tmp_path / "sdk")
    assert core == lib / "libmmt_core.so.1.10.10"
    run_path = pcap_eval.runtime_dir(core, tmp_path / "out")
    assert run_path == tmp_path / "out" / "lib"
    assert (run_path / "libmmt_core.so.1").resolve() == core
    # Idempotent, and the link follows another core.
    assert pcap_eval.runtime_dir(core, tmp_path / "out") == run_path
    other = lib / "libmmt_core.so.1.10.2"
    pcap_eval.runtime_dir(other, tmp_path / "out")
    assert (run_path / "libmmt_core.so.1").resolve() == other

    plain = tmp_path / "plain" / "dpi" / "lib"
    plain.mkdir(parents=True)
    (plain / "libmmt_core.so").write_bytes(b"")
    assert pcap_eval.core_library(tmp_path / "plain") == plain / "libmmt_core.so"
    assert pcap_eval.runtime_dir(plain / "libmmt_core.so", tmp_path / "o2") == plain
    (tmp_path / "none" / "dpi" / "lib").mkdir(parents=True)
    with pytest.raises(pcap_eval.EvalExit) as exc:
        pcap_eval.core_library(tmp_path / "none")
    assert exc.value.code == pcap_eval.EXIT_ENV


def test_eval_rejects_missing_inputs_before_running_anything(tmp_path: Path) -> None:
    sdk = tmp_path / "sdk"
    (sdk / "dpi" / "include").mkdir(parents=True)
    (sdk / "dpi" / "include" / "mmt_core.h").write_text("")
    (sdk / "plugins").mkdir()
    base = ["--sdk", str(sdk), "--label", "telem", "--parent", "udp:port=1"]
    base += ["--out", str(tmp_path / "out")]
    assert pcap_eval.main([*base, "--plugin", "nope.so", "--capture", "nope.pcap"]) == 2
    so = tmp_path / "mmtp_telem.so"
    so.write_bytes(b"")
    assert pcap_eval.main([*base, "--plugin", str(so), "--capture", "nope.pcap"]) == 2
    cap = tmp_path / "c.pcap"
    cap.write_bytes(b"")
    assert pcap_eval.main([*base, "--plugin", str(so), "--capture", str(cap), "--field", "x"]) == 2
    assert (
        pcap_eval.main(
            ["--sdk", str(tmp_path), *base[2:], "--plugin", str(so), "--capture", str(cap)]
        )
        == 3
    )
