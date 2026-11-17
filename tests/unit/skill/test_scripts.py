"""The mmt-plugin-generator skill's capture scripts, without an SDK.

``scripts/make_pcap.py`` writes a synthetic capture: what ``mmt_plugin.pcap``
slices back out of it under the parent is each payload, byte for byte, and
every checksum holds. ``scripts/pcap_eval.py``'s filters, comparisons,
drift against tshark and report are checked on hand-made runs (a drift case
and a no-drift case through ``main`` with the runner and tshark faked);
``test_sdk.py`` runs it on a built plugin.
"""

from __future__ import annotations

import json
import shutil
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
        ["--parent", "udp:port=70000", "--payload", "01"],
        ["--parent", "tcp:sport=-1", "--payload", "01"],
        ["--parent", "ip:proto=256", "--payload", "01"],
        ["--parent", "ethernet:ethertype=0x10000", "--payload", "01"],
        ["--parent", "udp:port=1", "--payload", "00" * (65535 - 42 + 1)],
        ["--parent", "ethernet:ethertype=0x88b5", "--payload", "00" * (65535 - 14 + 1)],
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
        "drift": {
            "reference": "tshark",
            "checked": True,
            "open": 0,
            "accepted": 0,
            "items": [],
            "file": "drift.jsonl",
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
        "## Drift against tshark",
        "## Attributes",
        "## Protocol paths",
    ):
        assert heading in text
    assert "| `a.TELEM` | 0 | 2 |" in text
    failed = pcap_eval.markdown(_report(verdict="FAIL", problems=["recall 0%"], missed_frames=[3]))
    assert "## Problems" in failed and "Missed frames (first 50): 3" in failed
    assert "None: the plugin agrees with tshark" in text
    item = {
        "key": "length",
        "kind": "field",
        "tshark_field": "x.len",
        "frames": 2,
        "first_frames": [1, 2],
        "status": "accepted",
        "reason": "x.len counts the trailer",
    }
    drifted = _report(
        drift={**_report()["drift"], "accepted": 1, "items": [item]},
    )
    md = pcap_eval.markdown(drifted)
    assert "0 open (defects), 1 accepted; every frame in `drift.jsonl`." in md
    assert "| length | field | 2 | 1, 2 | accepted | x.len counts the trailer |" in md
    unchecked = _report(drift={**_report()["drift"], "checked": False, "reference": None})
    assert "Not checked: no tshark" in pcap_eval.markdown(unchecked)


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


def test_the_largest_payload_fits_the_snap_length(tmp_path: Path) -> None:
    out = tmp_path / "x.pcap"
    args = ["--parent", "udp:port=1", "--payload", "00" * (65535 - 42), "--out", str(out)]
    assert make_pcap.main(args) == 0
    with out.open("rb") as f:
        (frame,) = list(read_stream(f).frames())
    assert len(frame.data) == 65535


def test_the_plugin_directories_never_write_into_the_sdk(tmp_path: Path) -> None:
    """An SDK whose plugins/ holds an installed copy of the plugin: the copy
    of the new build goes into the run's directory, not through a link into
    the SDK, and the baseline runs without either."""
    sdk_plugins = tmp_path / "sdk" / "plugins"
    sdk_plugins.mkdir(parents=True)
    (sdk_plugins / "libmmt_tcpip.so").write_bytes(b"tcpip")
    (sdk_plugins / "mmtp_telem.so").write_bytes(b"installed")
    build = tmp_path / "build" / "mmtp_telem.so"
    build.parent.mkdir()
    build.write_bytes(b"new build")
    sdk, out = tmp_path / "sdk", tmp_path / "out"
    base = pcap_eval.plugins_dir(sdk, build, out / "baseline-plugins", with_plugin=False)
    for _ in range(2):  # a second evaluation in the same --out
        plugins = pcap_eval.plugins_dir(sdk, build, out / "plugins", with_plugin=True)
    assert (sdk_plugins / "mmtp_telem.so").read_bytes() == b"installed"
    assert sorted(p.name for p in base.iterdir()) == ["libmmt_tcpip.so"]
    assert (base / "libmmt_tcpip.so").resolve() == (sdk_plugins / "libmmt_tcpip.so").resolve()
    assert not (plugins / "mmtp_telem.so").is_symlink()
    assert (plugins / "mmtp_telem.so").read_bytes() == b"new build"
    assert sorted(p.name for p in plugins.iterdir()) == ["libmmt_tcpip.so", "mmtp_telem.so"]


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


# --- pcap_eval.py: drift against tshark ---------------------------------------


def test_no_difference_is_no_drift() -> None:
    assert pcap_eval.drift_items({"length": []}, {"length": "x.len"}, [], [], {}) == []
    assert pcap_eval.drift_lines({"length": []}, [], None) == []


def test_each_difference_is_a_defect_until_accepted() -> None:
    rows: dict[str, list[dict[str, Any]]] = {
        "length": [{"frame": 2, "tshark": "8", "plugin": "9"}],
        "kind": [{"frame": f, "tshark": "1", "plugin": None} for f in range(1, 8)],
    }
    fields = {"length": "x.len", "kind": "x.kind"}
    items = pcap_eval.drift_items(rows, fields, [5, 6], [9], {"kind": "x.kind is masked"})
    assert [(d["key"], d["kind"], d["frames"], d["status"]) for d in items] == [
        ("length", "field", 1, "defect"),
        ("kind", "field", 7, "accepted"),
        ("missed", "classification", 2, "defect"),
        ("foreign", "classification", 1, "defect"),
    ]
    assert items[1]["reason"] == "x.kind is masked" and items[0]["reason"] is None
    assert items[1]["first_frames"] == [1, 2, 3, 4, 5]
    assert items[0]["tshark_field"] == "x.len"
    # drift.jsonl keeps every frame, not only the first ones.
    lines = pcap_eval.drift_lines(rows, [5, 6], [9])
    assert len(lines) == 1 + 7 + 2 + 1
    assert lines[0] == {"key": "length", "frame": 2, "tshark": "8", "plugin": "9"}
    assert lines[-1] == {"key": "foreign", "frame": 9}


def test_the_full_mismatch_list_is_not_capped() -> None:
    dump = [{"frame": f, "path": "x", "attributes": {"length": "1"}} for f in range(1, 21)]
    reference = {f: {"length": "2"} for f in range(1, 21)}
    _, rows = pcap_eval.field_mismatches(dump, reference, {"length": "x.len"}, set(range(1, 21)))
    assert len(rows["length"]) == 20
    rep = pcap_eval.compare_fields(dump, reference, {"length": "x.len"}, set(range(1, 21)))
    assert len(rep["length"]["mismatches"]) == 5 and rep["length"]["agreement"] == 0.0


@pytest.mark.parametrize(
    "items",
    [
        ["length"],
        ["length="],
        ["length=  "],
        ["=why"],
        ["lenght=a typo"],
        ["length=a", "length=b"],
    ],
)
def test_a_bad_accept_is_a_usage_error(items: list[str]) -> None:
    with pytest.raises(pcap_eval.EvalExit) as exc:
        pcap_eval.parse_accept(items, {"length": "x.len"})
    assert exc.value.code == pcap_eval.EXIT_USAGE


def test_accept_takes_attributes_and_the_classification_keys() -> None:
    got = pcap_eval.parse_accept(
        ["length=x.len counts the trailer", "missed = the capture starts mid-session"],
        {"length": "x.len"},
    )
    assert got == {
        "length": "x.len counts the trailer",
        "missed": "the capture starts mid-session",
    }


def _fake_eval(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, tshark: bool, plugin_length: str
) -> list[str]:
    """``main``'s arguments for an evaluation whose runner and tshark are
    faked: 3 frames, frames 1 and 2 expected (and claimed, with the
    attribute ``length``), frame 3 outside the scope. tshark's ``x.len`` is
    12 in both; the plugin's ``plugin_length`` in frame 2."""
    sdk = tmp_path / "sdk"
    (sdk / "dpi" / "include").mkdir(parents=True)
    (sdk / "dpi" / "include" / "mmt_core.h").write_text("")
    (sdk / "plugins").mkdir()
    so = tmp_path / "mmtp_telem.so"
    so.write_bytes(b"so")
    cap = tmp_path / "c.pcap"
    cap.write_bytes(b"pcap")

    def runner(
        binary: Path, capture: Path, label: str, plugins: Path, dump: Path | None
    ) -> dict[str, Any]:
        result: dict[str, Any] = {"frames": 3, "registered": True, "paths": {}, "attributes": {}}
        if dump is not None:
            rows = [(1, "12"), (2, plugin_length)]
            dump.write_text(
                "".join(
                    json.dumps({"frame": f, "path": "x.TELEM", "attributes": {"length": v}}) + "\n"
                    for f, v in rows
                )
            )
            result["attributes"] = {
                "length": {"id": 1, "present": 2, "values": {"12": 1}, "other_values": 1}
            }
            result["paths"] = {"x.TELEM": 2}
        return {**result, "crashed": False}

    real_which = shutil.which
    monkeypatch.setattr(
        shutil,
        "which",
        lambda name: (
            ("/usr/bin/tshark" if tshark else None) if name == "tshark" else real_which(name)
        ),
    )
    monkeypatch.setattr(pcap_eval, "compile_runner", lambda sdk, cc, out: out / "bin" / "x")
    monkeypatch.setattr(pcap_eval, "run_runner", runner)
    monkeypatch.setattr(pcap_eval, "tshark_frames", lambda capture, flt, decode: {1, 2})
    monkeypatch.setattr(
        pcap_eval,
        "tshark_fields",
        lambda capture, fields, decode: {1: {"length": "12"}, 2: {"length": "0x0c"}},
    )
    monkeypatch.setattr(pcap_eval, "fallback_frames", lambda capture, selector: {1, 2})
    args = ["--sdk", str(sdk), "--plugin", str(so), "--label", "telem"]
    return [*args, "--parent", "udp:port=1", "--capture", str(cap), "--out", str(tmp_path / "out")]


def _read(tmp_path: Path) -> dict[str, Any]:
    report: dict[str, Any] = json.loads((tmp_path / "out" / "report.json").read_text("utf-8"))
    return report


def test_no_drift_passes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    args = _fake_eval(tmp_path, monkeypatch, tshark=True, plugin_length="12")
    assert pcap_eval.main([*args, "--field", "length=x.len"]) == 0
    report = _read(tmp_path)
    assert report["verdict"] == "PASS", report["problems"]
    assert report["drift"] == {
        "reference": "tshark",
        "checked": True,
        "open": 0,
        "accepted": 0,
        "items": [],
        "file": "drift.jsonl",
    }
    assert (tmp_path / "out" / "drift.jsonl").read_text("utf-8") == ""
    assert "None: the plugin agrees with tshark" in (tmp_path / "out" / "report.md").read_text()


def test_an_open_drift_fails_and_an_accepted_one_passes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    args = _fake_eval(tmp_path, monkeypatch, tshark=True, plugin_length="20")
    args += ["--field", "length=x.len"]
    assert pcap_eval.main(args) == 1
    report = _read(tmp_path)
    assert report["verdict"] == "FAIL"
    assert report["drift"]["open"] == 1
    (item,) = report["drift"]["items"]
    assert (item["key"], item["status"], item["first_frames"]) == ("length", "defect", [2])
    assert any(p.startswith("drift length: field length differs") for p in report["problems"])
    lines = (tmp_path / "out" / "drift.jsonl").read_text("utf-8").splitlines()
    assert [json.loads(line) for line in lines] == [
        {"key": "length", "frame": 2, "tshark": "0x0c", "plugin": "20"}
    ]

    reason = "x.len is the payload length, the attribute the whole message"
    assert (
        pcap_eval.main(
            [
                *args,
                "--accept",
                f"length={reason}",
                "--accept",
                "missed=the capture starts mid-session",
            ]
        )
        == 0
    )
    report = _read(tmp_path)
    assert report["verdict"] == "PASS", report["problems"]
    assert (report["drift"]["open"], report["drift"]["accepted"]) == (0, 1)
    assert report["drift"]["items"][0]["reason"] == reason
    assert "--accept missed: no such drift on this capture" in report["warnings"]
    assert f"| accepted | {reason} |" in (tmp_path / "out" / "report.md").read_text()


def test_without_tshark_the_drift_is_not_checked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    args = _fake_eval(tmp_path, monkeypatch, tshark=False, plugin_length="20")
    assert pcap_eval.main([*args, "--field", "length=x.len"]) == 3
    assert pcap_eval.main([*args, "--field", "missed=x.len"]) == 2
    assert pcap_eval.main([*args, "--accept", "missed=why"]) == 0
    report = _read(tmp_path)
    assert report["verdict"] == "PASS"
    assert report["drift"]["checked"] is False and report["drift"]["reference"] is None
    assert any("drift against a reference tool not checked" in w for w in report["warnings"])
    assert any("(--accept ignored)" in w for w in report["warnings"])
    assert not (tmp_path / "out" / "drift.jsonl").exists()


def test_each_field_is_compared_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    args = _fake_eval(tmp_path, monkeypatch, tshark=True, plugin_length="20")
    calls: list[set[str]] = []
    real = pcap_eval.field_mismatches

    def counted(
        dump: list[dict[str, Any]],
        reference: dict[int, dict[str, str]],
        fields: dict[str, str],
        expected: set[int],
    ) -> tuple[dict[str, int], dict[str, list[dict[str, Any]]]]:
        calls.append(set(fields))
        return real(dump, reference, fields, expected)

    monkeypatch.setattr(pcap_eval, "field_mismatches", counted)
    assert pcap_eval.main([*args, "--field", "length=x.len"]) == 1
    assert calls == [{"length"}]
    report = _read(tmp_path)
    assert report["fields"]["length"]["compared"] == 2
    assert report["fields"]["length"]["mismatches"] == [
        {"frame": 2, "tshark": "0x0c", "plugin": "20"}
    ]
    assert report["drift"]["items"][0]["first_frames"] == [2]


@pytest.mark.parametrize(
    ("text", "cell"),
    [
        ("plain", "plain"),
        ("a | b", "a \\| b"),
        ("one\ntwo\r\nthree\rfour", "one two three four"),
        ("x|y\nz", "x\\|y z"),
    ],
)
def test_a_table_cell_keeps_one_line_and_escapes_pipes(text: str, cell: str) -> None:
    assert pcap_eval.table_cell(text) == cell


def test_an_accepted_reason_with_a_pipe_or_a_newline_stays_in_its_cell(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    args = _fake_eval(tmp_path, monkeypatch, tshark=True, plugin_length="20")
    reason = "x.len | the payload length\nthe attribute: the whole message"
    args += ["--field", "length=x.len", "--accept", f"length={reason}"]
    assert pcap_eval.main(args) == 0
    assert _read(tmp_path)["drift"]["items"][0]["reason"] == reason
    md = (tmp_path / "out" / "report.md").read_text("utf-8")
    row = (
        "| length | field | 1 | 2 | accepted"
        " | x.len \\| the payload length the attribute: the whole message |"
    )
    assert row in md.splitlines()
    assert "the payload length\n" not in md
