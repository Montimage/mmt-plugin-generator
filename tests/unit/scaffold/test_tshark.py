"""``scaffold --tshark`` (#125) and ``mmt_plugin.pcap.tshark``: the fields
tshark dissects mapped to attributes, the protocol chosen, and the errors.

tshark is faked: ``data/tshark/dns.pdml`` is what tshark 4.2.2 printed for
``samples.dns_capture()`` (``tshark -n -r dns.pcap -c 4 -T pdml -o
tcp.desegment_tcp_streams:FALSE``) and ``data/tshark/dns-fields.tsv`` the
``dns`` lines of its ``tshark -G fields``. A script named ``tshark`` on
``PATH`` prints them (``fake_tshark``). ``test_sdk.py`` runs the real one.
"""

from __future__ import annotations

import io
import json
import os
import stat
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from mmt_plugin import schemas
from mmt_plugin.cli import main
from mmt_plugin.commands.init import parse_selector
from mmt_plugin.diagnostics import CliError
from mmt_plugin.pcap import parent_of, read, slice_payloads
from mmt_plugin.pcap import tshark as ts
from mmt_plugin.pcap.layers import Payload

from . import samples

DATA = Path(__file__).with_name("data") / "tshark"
PDML = (DATA / "dns.pdml").read_bytes()
FIELDS = (DATA / "dns-fields.tsv").read_text()

MODEL = """schema: 1
protocol:
  label: dnsx
  id: 960
attributes:
  - name: version
    type: MMT_U8_DATA
    offset: 0
"""

FAKE = """#!{python}
import os, sys
log = os.environ["FAKE_TSHARK_LOG"]
with open(log, "a") as f:
    f.write(" ".join(sys.argv[1:]) + "\\n")
sys.stderr.write("Running as user \\"root\\" and group \\"root\\". This could be dangerous.\\n")
if os.environ.get("FAKE_TSHARK_FAIL"):
    sys.stderr.write(os.environ["FAKE_TSHARK_FAIL"] + "\\n")
    sys.exit(1)
name = os.environ["FAKE_TSHARK_FIELDS" if "-G" in sys.argv else "FAKE_TSHARK_PDML"]
with open(name, "rb") as f:
    sys.stdout.buffer.write(f.read())
"""


def _parent(text: str) -> Any:
    selector = parse_selector(text)
    return parent_of(selector.text, selector.proto, selector.keys)


def _payloads() -> list[Payload]:
    capture = read(samples.dns_capture())
    return slice_payloads(capture.frames(), _parent("udp:port=53"), 20).payloads


# --- parsing -------------------------------------------------------------------


def test_parse_fields_reads_types_and_bitmasks() -> None:
    infos = ts.parse_fields(FIELDS, "dns")
    assert infos["dns.id"] == ts.FieldInfo("dns.id", "FT_UINT16", 0)
    assert infos["dns.flags.response"] == ts.FieldInfo("dns.flags.response", "FT_BOOLEAN", 0x8000)
    assert infos["dns.flags.rcode"].bitmask == 0xF
    assert ts.parse_fields(FIELDS, "ip") == {}


def test_parse_fields_finds_the_bitmask_wherever_it_is() -> None:
    """Older tshark put the blurb before the base and the bitmask."""
    old = "F\tOpcode\tx.op\tFT_UINT8\tx\tthe operation\tBASE_DEC\t0x70\n"
    new = "F\tOpcode\tx.op\tFT_UINT8\tx\tBASE_DEC\t0x70\tthe operation\n"
    assert ts.parse_fields(old, "x") == ts.parse_fields(new, "x")
    assert ts.parse_fields(old, "x")["x.op"].bitmask == 0x70
    # Protocol lines (P) and other protocols' fields are not read.
    assert ts.parse_fields("P\tX\tx\nF\ta\ty.a\tFT_UINT8\ty\t\t0x0\t\n", "x") == {}


def test_parse_pdml_finds_the_protocol_at_each_payloads_start() -> None:
    payloads = _payloads()
    assert [p.start for p in payloads] == [42] * 4
    dissection = ts.parse_pdml(io.BytesIO(PDML), payloads)
    assert dissection.protocols == [["dns"]] * 4
    fields = dissection.fields[0]["dns"]
    assert fields["dns.id"] == ts.Occurrence(0, 2, "0x1000", "1000", None)
    assert fields["dns.flags.response"] == ts.Occurrence(2, 2, "False", "0", "0100")
    # The first occurrence of a field, with its offset from the protocol.
    assert fields["dns.qry.type"].offset == 25


def test_parse_pdml_reads_only_the_payloads_frames() -> None:
    payloads = _payloads()[1:2]
    dissection = ts.parse_pdml(io.BytesIO(PDML), payloads)
    assert dissection.protocols == [["dns"]]
    assert dissection.fields[0]["dns"]["dns.flags"].value == "8180"


def test_parse_pdml_refuses_output_that_does_not_parse() -> None:
    with pytest.raises(CliError) as caught:
        ts.parse_pdml(io.BytesIO(b"<pdml><packet>"), _payloads())
    assert caught.value.code == "sdk.tshark-failed"


def test_a_protocol_elsewhere_in_the_frame_is_not_at_the_start() -> None:
    """Under ethernet:ethertype=0x0800 the payload is IP: dns is not at its
    start."""
    capture = read(samples.dns_capture())
    payloads = slice_payloads(capture.frames(), _parent("ethernet:ethertype=0x0800"), 20).payloads
    dissection = ts.parse_pdml(io.BytesIO(PDML), payloads)
    assert dissection.protocols == [["ip"]] * 4


# --- the protocol chosen ---------------------------------------------------------


def _dissection(*names: list[str]) -> tuple[ts.Dissection, list[Payload]]:
    payloads = [Payload(i + 1, ("udp",), b"\x00\x01") for i in range(len(names))]
    out = ts.Dissection([list(n) for n in names], [{k: {} for k in n} for n in names])
    return out, payloads


def test_choose_takes_the_only_protocol_and_its_payloads() -> None:
    dissection, payloads = _dissection(["dns"], ["data"], ["dns"])
    protocol, chosen = ts.choose(dissection, payloads, None, "udp:port=53")
    assert protocol == "dns"
    assert [d.payload.frame for d in chosen] == [1, 3]


def test_choose_asks_which_one_when_there_are_several() -> None:
    dissection, payloads = _dissection(["websocket"], ["http"], ["websocket"])
    with pytest.raises(CliError) as caught:
        ts.choose(dissection, payloads, None, "tcp:port=80")
    assert caught.value.code == "usage.missing-argument"
    assert "websocket (2), http (1)" in str(caught.value)
    protocol, chosen = ts.choose(dissection, payloads, "http", "tcp:port=80")
    assert (protocol, len(chosen)) == ("http", 1)


@pytest.mark.parametrize(
    ("names", "protocol"),
    [([["data"], ["data"]], None), ([["dns"]], "mqtt"), ([["data"]], "data"), ([[], []], None)],
)
def test_choose_without_a_dissector(names: list[list[str]], protocol: str | None) -> None:
    dissection, payloads = _dissection(*names)
    with pytest.raises(CliError) as caught:
        ts.choose(dissection, payloads, protocol, "udp:port=4433")
    assert caught.value.code == "model.no-dissector"
    assert "--decode-as" in (caught.value.hint or "")


# --- the fields mapped -------------------------------------------------------------


def test_the_dns_draft() -> None:
    payloads = _payloads()
    dissection = ts.parse_pdml(io.BytesIO(PDML), payloads)
    protocol, chosen = ts.choose(dissection, payloads, None, "udp:port=53")
    draft = ts.draft(protocol, ts.parse_fields(FIELDS, "dns"), chosen, max_name=64)
    got = [
        (f.name, f.type, f.offset, f.length, f.bit_offset, f.bit_width, f.source, f.expect)
        for f in draft.skeleton.fields
    ]
    u16 = "MMT_U16_DATA"
    assert got == [
        ("id", u16, 0, 2, None, None, "dns.id", True),
        ("flags", u16, 2, 2, None, None, "dns.flags", True),
        ("flags_response", u16, 2, 2, 0, 1, "dns.flags.response", True),
        ("flags_opcode", u16, 2, 2, 1, 4, "dns.flags.opcode", True),
        # authoritative is in the answers only: its bit is not checked.
        ("bits_2_16_b5", u16, 2, 2, 5, 1, None, False),
        ("flags_truncated", u16, 2, 2, 6, 1, "dns.flags.truncated", True),
        ("flags_recdesired", u16, 2, 2, 7, 1, "dns.flags.recdesired", True),
        ("bits_2_16_b8", u16, 2, 2, 8, 1, None, False),
        ("flags_z", u16, 2, 2, 9, 1, "dns.flags.z", True),
        ("bits_2_16_b10", u16, 2, 2, 10, 1, None, False),
        ("flags_checkdisable", u16, 2, 2, 11, 1, "dns.flags.checkdisable", True),
        ("count_queries", u16, 4, 2, None, None, "dns.count.queries", True),
        ("count_answers", u16, 6, 2, None, None, "dns.count.answers", True),
        ("count_auth_rr", u16, 8, 2, None, None, "dns.count.auth_rr", True),
        ("count_add_rr", u16, 10, 2, None, None, "dns.count.add_rr", True),
        ("qry_name", "MMT_BINARY_DATA", 12, 13, None, None, "dns.qry.name", True),
        ("qry_type", u16, 25, 2, None, None, "dns.qry.type", True),
        ("qry_class", u16, 27, 2, None, None, "dns.qry.class", True),
    ]
    skipped = dict(draft.skipped)
    assert skipped["dns.qry.name.len"] == "FT_UINT16 in 13 bytes: tshark computes it"
    assert skipped["dns.flags.rcode"] == "in 2 of 4 payloads"
    assert skipped["dns.a"] == "in 2 of 4 payloads"
    assert draft.skeleton.header_length == 29
    assert (draft.skeleton.shortest, draft.skeleton.longest) == (29, 45)
    # Every value tshark decodes is what the attribute reads.
    for d in chosen:
        for f in draft.skeleton.fields:
            if f.source is not None and f.bit_offset is not None:
                assert f.value(d.payload.data) == int(d.fields[f.source].value, 16)


def _occ(offset: int, size: int, show: str, value: str, unmasked: str | None = None) -> Any:
    return ts.Occurrence(offset, size, show, value, unmasked)


def _draft(
    infos: list[ts.FieldInfo], per_payload: list[tuple[bytes, dict[str, ts.Occurrence]]]
) -> ts.Draft:
    dissected = [
        ts.Dissected(Payload(i + 1, ("udp",), data), fields)
        for i, (data, fields) in enumerate(per_payload)
    ]
    return ts.draft("x", {i.abbrev: i for i in infos}, dissected)


@pytest.mark.parametrize(
    ("info", "occ", "data", "reason"),
    [
        (ts.FieldInfo("x.le", "FT_UINT16", 0), _occ(0, 2, "1", "0100"), b"\x01\x00",
         "tshark's value is not the bytes in network byte order"),
        (ts.FieldInfo("x.s", "FT_INT8", 0), _occ(0, 1, "-1", "ff"), b"\xff",
         "a signed integer: no MMT signed type"),
        (ts.FieldInfo("x.u24", "FT_UINT24", 0), _occ(0, 3, "1", "000001"), b"\x00\x00\x01",
         "a 3-byte integer: no MMT integer type of that width"),
        (ts.FieldInfo("x.m", "FT_UINT8", 0x5), _occ(0, 1, "1", "1", "05"), b"\x05",
         "its bitmask 0x5 is not one run of bits"),
        (ts.FieldInfo("x.m3", "FT_UINT24", 0x10), _occ(0, 3, "1", "1", "000010"),
         b"\x00\x00\x10", "a bit field of a 3-byte unit"),
        (ts.FieldInfo("x.b", "FT_BYTES", 0), _occ(0, 2, "ab:cd", "abcd"), b"\xab\xce",
         "its bytes are not the payload's"),
        (ts.FieldInfo("x.big", "FT_BYTES", 0), _occ(0, 65, "", "00" * 65), bytes(65),
         "65 bytes: more than 64"),
        (ts.FieldInfo("x.n", "FT_NONE", 0), _occ(0, 1, "", "00"), b"\x00", "no value"),
        (ts.FieldInfo("x.g", "FT_UINT16", 0), _occ(0, 0, "4", ""), b"\x00",
         "no bytes: tshark computes it"),
        (ts.FieldInfo("x.out", "FT_UINT16", 0), _occ(1, 2, "4", "0004"), b"\x00\x00",
         "outside the payload"),
        (ts.FieldInfo("x.ip", "FT_IPv4", 0), _occ(0, 4, "10.0.0.1", "0a000002"),
         bytes([10, 0, 0, 2]), "tshark's value is not the bytes"),
    ],
)  # fmt: skip
def test_fields_that_are_not_proposed(
    info: ts.FieldInfo, occ: ts.Occurrence, data: bytes, reason: str
) -> None:
    keep = ts.FieldInfo("x.k", "FT_UINT8", 0)
    draft = _draft(
        [info, keep], [(data, {info.abbrev: occ, "x.k": _occ(0, 1, str(data[0]), data[:1].hex())})]
    )
    assert draft.skipped == ((info.abbrev, reason),)
    assert [f.source for f in draft.skeleton.fields] == ["x.k"]


def test_a_field_at_another_offset_in_one_payload() -> None:
    info = ts.FieldInfo("x.v", "FT_UINT8", 0)
    draft = _draft(
        [info, ts.FieldInfo("x.k", "FT_UINT8", 0)],
        [
            (b"\x01\x02", {"x.v": _occ(0, 1, "1", "01"), "x.k": _occ(1, 1, "2", "02")}),
            (b"\x01\x02", {"x.v": _occ(1, 1, "2", "02"), "x.k": _occ(1, 1, "2", "02")}),
        ],
    )
    assert draft.skipped == (("x.v", "its offset or length varies"),)


def test_addresses_bytes_and_wide_integers() -> None:
    mac, ip4 = bytes.fromhex("020000000001"), bytes([192, 0, 2, 1])
    ip6 = bytes.fromhex("20010db8000000000000000000000001")
    data = mac + ip4 + ip6 + b"abc" + (1 << 40).to_bytes(8, "big")
    infos = [
        ts.FieldInfo("x.mac", "FT_ETHER", 0),
        ts.FieldInfo("x.ip", "FT_IPv4", 0),
        ts.FieldInfo("x.ip6", "FT_IPv6", 0),
        ts.FieldInfo("x.text", "FT_STRING", 0),
        ts.FieldInfo("x.big", "FT_UINT64", 0),
    ]
    occs = {
        "x.mac": _occ(0, 6, "02:00:00:00:00:01", mac.hex()),
        "x.ip": _occ(6, 4, "192.0.2.1", ip4.hex()),
        "x.ip6": _occ(10, 16, "2001:db8::1", ip6.hex()),
        "x.text": _occ(26, 3, "abc", b"abc".hex()),
        "x.big": _occ(29, 8, str(1 << 40), (1 << 40).to_bytes(8, "big").hex()),
    }
    draft = _draft(infos, [(data, occs)])
    assert draft.skipped == ()
    fields = draft.skeleton.fields
    assert [(f.name, f.type, f.length) for f in fields] == [
        ("mac", "MMT_DATA_MAC_ADDR", 6),
        ("ip", "MMT_DATA_IP_ADDR", 4),
        ("ip6", "MMT_DATA_IP6_ADDR", 16),
        ("text", "MMT_BINARY_DATA", 3),
        ("big", "MMT_U64_DATA", 8),
    ]
    assert [f.expected(data) for f in fields] == [
        '"02:00:00:00:00:01"',
        '"192.0.2.1"',
        '"2001:db8::1"',
        '"61 62 63"',
        str(1 << 40),
    ]


def test_two_fields_on_the_same_bits_keep_the_first() -> None:
    infos = [ts.FieldInfo("x.a", "FT_BOOLEAN", 0x40), ts.FieldInfo("x.c", "FT_BOOLEAN", 0x40)]
    occs = {"x.a": _occ(0, 1, "True", "1", "40"), "x.c": _occ(0, 1, "True", "1", "40")}
    draft = _draft(infos, [(b"\x40", occs)])
    assert draft.skipped == (("x.c", "its bits are x.a's"),)
    assert [(f.name, f.bit_offset, f.bit_width, f.expect) for f in draft.skeleton.fields] == [
        ("bits_0_b0", 0, 1, False),
        ("a", 1, 1, True),
    ]


@pytest.mark.parametrize(
    ("abbrev", "name"),
    [
        ("dns.flags.response", "flags_response"),
        ("dns.count.add_rr", "count_add_rr"),
        ("dns", "dns"),
        ("dns.3gpp-x", "f_3gpp_x"),
        ("other.field", "other_field"),
    ],
)
def test_field_names(abbrev: str, name: str) -> None:
    assert ts.field_name(abbrev, "dns") == name


def test_names_are_unique_and_fit_the_alias_length() -> None:
    infos = [ts.FieldInfo("x.a.b", "FT_UINT8", 0), ts.FieldInfo("x.a_b", "FT_UINT8", 0)]
    occs = {"x.a.b": _occ(0, 1, "1", "01"), "x.a_b": _occ(1, 1, "2", "02")}
    dissected = [ts.Dissected(Payload(1, ("udp",), b"\x01\x02"), occs)]
    draft = ts.draft("x", {i.abbrev: i for i in infos}, dissected, max_name=3)
    assert [f.name for f in draft.skeleton.fields] == ["a_b", "a_2"]


# --- the command -------------------------------------------------------------------

Run = Callable[..., tuple[int, dict[str, Any]]]


@pytest.fixture
def fake_tshark(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A ``tshark`` on ``PATH`` that prints the recorded output; returns
    the log of its command lines."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    script = bin_dir / "tshark"
    script.write_text(FAKE.format(python=sys.executable))
    script.chmod(script.stat().st_mode | stat.S_IXUSR)
    log = tmp_path / "tshark.log"
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")
    monkeypatch.setenv("FAKE_TSHARK_LOG", str(log))
    monkeypatch.setenv("FAKE_TSHARK_PDML", str(DATA / "dns.pdml"))
    monkeypatch.setenv("FAKE_TSHARK_FIELDS", str(DATA / "dns-fields.tsv"))
    monkeypatch.delenv("FAKE_TSHARK_FAIL", raising=False)
    return log


@pytest.fixture
def work(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    cwd = tmp_path / "work"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    (cwd / "plugin.yaml").write_text(MODEL)
    (cwd / "dns.pcap").write_bytes(samples.dns_capture())
    return cwd


@pytest.fixture
def scaffold(work: Path, capsys: pytest.CaptureFixture[str]) -> Run:
    envelope = Draft202012Validator(schemas.load_cli_schema(schemas.ENVELOPE))
    result = Draft202012Validator(schemas.result_schema("scaffold"))

    def go(*args: str) -> tuple[int, dict[str, Any]]:
        code = main(["--json", "scaffold", *args])
        out = capsys.readouterr()
        doc: dict[str, Any] = json.loads(out.out)
        envelope.validate(doc)
        assert doc["exit_code"] == code
        if doc["result"] is not None:
            result.validate(doc["result"])
        return code, doc

    return go


ARGS = ("--from-pcap", "dns.pcap", "--parent", "udp:port=53", "--tshark")


def _written(work: Path) -> list[str]:
    return sorted(
        str(p.relative_to(work)) for p in work.rglob("*") if p.is_file() and p.suffix == ".yaml"
    )


def test_scaffold_drafts_from_tshark(scaffold: Run, work: Path, fake_tshark: Path) -> None:
    code, doc = scaffold(*ARGS, "--decode-as", "udp.port==5353,dns")
    assert code == 0, doc["error"]
    result = doc["result"]
    assert result["tshark"]["protocol"] == "dns"
    assert result["tshark"]["decode_as"] == ["udp.port==5353,dns"]
    assert result["tshark"]["dissected"] == 4
    assert {"field": "dns.flags.rcode", "reason": "in 2 of 4 payloads"} in result["tshark"][
        "skipped"
    ]
    assert result["skeleton"]["fields"][0] == {
        "name": "id",
        "type": "MMT_U16_DATA",
        "offset": 0,
        "length": 2,
        "constant": False,
        "tshark_field": "dns.id",
    }
    assert _written(work) == [
        "plugin.proposed.yaml",
        "plugin.yaml",
        *(f"tests/dnsx-pcap-00{n}.yaml" for n in range(1, 5)),
    ]
    proposed = (work / "plugin.proposed.yaml").read_text()
    assert "tshark's dns fields" in proposed
    assert "  - struct: bits_2_16    # bytes 2-3, cut into bit fields" in proposed
    assert "      - type: uint16_t" in proposed
    assert "    length: 13" in proposed
    assert "# Not proposed: dns.flags.rcode: in 2 of 4 payloads." in proposed
    answer = (work / "tests/dnsx-pcap-002.yaml").read_text()
    assert "tshark decodes for its dns fields" in answer
    assert '    - name: "flags"\n      type: "MMT_U16_DATA"\n      offset: 2\n' in answer
    assert "      value: 33152\n" in answer  # 0x8180
    assert '      value: "07 65 78 61 6d 70 6c 65 03 63 6f 6d 00"' in answer
    assert "bits_2_16_b5" not in answer  # bits no field covers are not checked
    # tshark: its fields, then the first 4 frames, TCP reassembly off, -d.
    lines = fake_tshark.read_text().splitlines()
    assert lines[0] == (
        "-n -r " + str(work / "dns.pcap") + " -c 4 -T pdml -o tcp.desegment_tcp_streams:FALSE"
        " -d udp.port==5353,dns"
    )
    assert lines[1] == "-G fields"

    # The proposal generates, and a re-run is a no-op.
    code, doc = scaffold(*ARGS, "--decode-as", "udp.port==5353,dns")
    assert code == 0
    assert {f["action"] for f in doc["result"]["files"]} == {"unchanged"}


def test_without_tshark_nothing_is_written(
    scaffold: Run, work: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))
    code, doc = scaffold(*ARGS)
    assert code == 4
    assert doc["error"]["code"] == "sdk.tshark-not-found"
    assert "install tshark" in doc["error"]["hint"]
    assert _written(work) == ["plugin.yaml"]


def test_tshark_failing_writes_nothing(
    scaffold: Run, work: Path, fake_tshark: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_TSHARK_FAIL", 'tshark: Unknown protocol -- "nosuch"')
    code, doc = scaffold(*ARGS, "--decode-as", "udp.port==53,nosuch")
    assert code == 4
    assert doc["error"]["code"] == "sdk.tshark-failed"
    assert doc["error"]["message"] == (
        'tshark failed dissecting dns.pcap (exit 1): tshark: Unknown protocol -- "nosuch"'
    )
    assert _written(work) == ["plugin.yaml"]


def test_no_dissector_writes_nothing(
    scaffold: Run, work: Path, fake_tshark: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pdml = tmp_path / "data.pdml"
    pdml.write_bytes(PDML.replace(b'<proto name="dns"', b'<proto name="data"'))
    monkeypatch.setenv("FAKE_TSHARK_PDML", str(pdml))
    code, doc = scaffold(*ARGS)
    assert code == 3
    assert doc["error"]["code"] == "model.no-dissector"
    assert "(it dissects: data (4))" in doc["error"]["message"]
    assert _written(work) == ["plugin.yaml"]

    # Asked for a protocol tshark does not dissect there: the same.
    monkeypatch.setenv("FAKE_TSHARK_PDML", str(DATA / "dns.pdml"))
    code, doc = scaffold(*ARGS, "--protocol", "mqtt")
    assert code == 3
    assert doc["error"]["code"] == "model.no-dissector"
    assert "(it dissects: dns (4))" in doc["error"]["message"]
    assert _written(work) == ["plugin.yaml"]


def test_no_field_to_propose_writes_nothing(
    scaffold: Run, work: Path, fake_tshark: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    empty = tmp_path / "fields.tsv"
    empty.write_text("")
    monkeypatch.setenv("FAKE_TSHARK_FIELDS", str(empty))
    code, doc = scaffold(*ARGS)
    assert code == 3
    assert doc["error"]["code"] == "model.no-fields"
    assert _written(work) == ["plugin.yaml"]


@pytest.mark.parametrize(
    "extra",
    [
        ("--protocol", "dns"),
        ("--decode-as", "udp.port==53,dns"),
    ],
)
def test_tshark_options_need_tshark(scaffold: Run, work: Path, extra: tuple[str, ...]) -> None:
    code, doc = scaffold(*ARGS[:-1], *extra)
    assert code == 2
    assert doc["error"]["code"] == "usage.conflicting-options"


def test_skip_until_is_not_with_tshark(scaffold: Run, work: Path) -> None:
    code, doc = scaffold(
        "--from-pcap", "dns.pcap", "--parent", "tcp:port=53", "--tshark", "--skip-until", "0d0a"
    )
    assert code == 2
    assert doc["error"]["code"] == "usage.conflicting-options"


@pytest.mark.parametrize(
    "extra", [("--protocol", "dns;rm"), ("--decode-as", "-x"), ("--decode-as", "udp.port=53")]
)
def test_bad_tshark_option_values(scaffold: Run, work: Path, extra: tuple[str, ...]) -> None:
    code, doc = scaffold(*ARGS, *extra)
    assert code == 2
    assert doc["error"]["class"] == "usage"


def test_a_field_named_as_a_struct_is_renamed() -> None:
    infos = [ts.FieldInfo("x.bits_0", "FT_UINT8", 0), ts.FieldInfo("x.f", "FT_BOOLEAN", 0x80)]
    occs = {"x.bits_0": _occ(0, 1, "128", "80"), "x.f": _occ(0, 1, "True", "1", "80")}
    draft = _draft(infos, [(b"\x80", occs)])
    assert [f.name for f in draft.skeleton.fields] == ["bits_0_2", "f"]


def test_pdml_that_does_not_parse_is_reported_as_such(
    work: Path, fake_tshark: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bad = tmp_path / "bad.pdml"
    bad.write_bytes(b"<pdml><packet>" + b"x" * 200000)
    monkeypatch.setenv("FAKE_TSHARK_PDML", str(bad))
    with pytest.raises(CliError) as caught:
        ts.dissect("tshark", work / "dns.pcap", 4, _payloads())
    assert caught.value.code == "sdk.tshark-failed"
    assert "does not parse" in str(caught.value)


def test_tshark_runs_without_the_users_profile(
    work: Path, fake_tshark: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "user"))
    monkeypatch.setenv("WIRESHARK_CONFIG_DIR", str(tmp_path / "profile"))
    script = tmp_path / "bin" / "tshark"
    script.write_text(
        script.read_text().replace(
            "import os, sys\n",
            "import os, sys\nassert os.environ['HOME'] == os.environ['XDG_CONFIG_HOME']\n"
            "assert 'WIRESHARK_CONFIG_DIR' not in os.environ\n",
        )
    )
    assert ts.dissect("tshark", work / "dns.pcap", 4, _payloads()).protocols == [["dns"]] * 4
