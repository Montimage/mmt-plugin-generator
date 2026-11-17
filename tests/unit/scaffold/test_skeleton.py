"""``mmt_plugin.pcap.skeleton``: the field rules, ``plugin.proposed.yaml``
(which generates, with the parent attached by the generated code when the
selector allows it) and the packet tests (corpus schema 1, whose values are
the proposal's)."""

from __future__ import annotations

import os
import struct
from pathlib import Path

import pytest

from mmt_plugin.commands.generate import make_generation
from mmt_plugin.commands.init import parse_selector
from mmt_plugin.pcap import (
    HEADER_LIMIT,
    Parent,
    Payload,
    bit_groups,
    packet_test,
    parent_of,
    propose,
    proposed_yaml,
)
from mmt_plugin.pdl.model import Attribute
from mmt_plugin.pluginyaml import load
from mmt_plugin.sdk.profile import DATA_TYPE_GROUP
from mmt_plugin.sdk.resolve import resolve_profile
from mmt_plugin.testing import packets

from . import samples

CHOICE = resolve_profile("1.10.2", {}, None, None)
TYPES = {c.name for c in CHOICE.profile.constants if c.group == DATA_TYPE_GROUP}


def _parent(text: str) -> Parent:
    selector = parse_selector(text)
    return parent_of(selector.text, selector.proto, selector.keys)


def _fields(payloads: list[bytes]) -> list[tuple[str, int, int, bool]]:
    return [(f.name, f.offset, f.length, f.constant) for f in propose(payloads).fields]


def test_the_demo_protocol() -> None:
    skeleton = propose(samples.demo_payloads())
    assert [(f.name, f.type, f.offset, f.constant) for f in skeleton.fields] == [
        ("field_0", "MMT_U8_DATA", 0, True),  # version
        ("field_1", "MMT_U8_DATA", 1, False),  # kind
        ("length", "MMT_U16_DATA", 2, False),
        ("field_4", "MMT_U32_DATA", 4, False),  # the sequence number
        ("field_8", "MMT_U8_DATA", 8, True),
        ("field_9", "MMT_U8_DATA", 9, False),
    ]
    assert skeleton.header_length == 10
    assert skeleton.length is not None and skeleton.length.name == "length"
    assert skeleton.adjust == 0
    assert (skeleton.shortest, skeleton.longest) == (10, 19)
    assert skeleton.to_json()["length_field"] == {"name": "length", "adjust": 0}


def test_a_length_field_counting_what_follows_it() -> None:
    # A 1-byte type, a 1-byte length of the rest: adjust 2.
    payloads = [bytes([7, n]) + bytes(range(n)) for n in (3, 5, 9)]
    skeleton = propose(payloads)
    assert skeleton.length is not None
    assert (skeleton.length.offset, skeleton.length.length, skeleton.adjust) == (1, 1, 2)
    assert "the payload length - 2" in skeleton.length.note


def test_no_length_field_with_a_single_length() -> None:
    payloads = [bytes([1, 0, 8]) + bytes(5), bytes([1, 0, 8]) + bytes(5)]
    skeleton = propose(payloads)
    assert skeleton.length is None
    assert all(f.constant and f.length == 1 for f in skeleton.fields)


def test_a_length_must_not_count_more_than_it_covers() -> None:
    # The u16 at offset 2 is the length minus 7: too much for a field
    # that ends at 4, so it is no length field.
    payloads = [b"\x01\x01" + struct.pack(">H", n - 7) + bytes(n - 4) for n in (8, 9, 12)]
    assert propose(payloads).length is None


def test_words_and_runs_of_differing_bytes() -> None:
    a = bytes([9, 1, 2, 9, 1, 2, 3])
    b = bytes([9, 2, 3, 9, 2, 3, 4])
    # The word at 0 ends with a constant byte: 0 and 3 are constant bytes,
    # 1-2 a run; the word at 4 does not fit, so 4-6 is a run of 2 + 1.
    assert _fields([a, b]) == [
        ("field_0", 0, 1, True),
        ("field_1", 1, 2, False),
        ("field_3", 3, 1, True),
        ("field_4", 4, 2, False),
        ("field_6", 6, 1, False),
    ]
    # A word whose last byte differs is one field, constant high bytes and all.
    assert _fields([bytes([0, 0, 1, 7]), bytes([0, 0, 1, 8])]) == [("field_0", 0, 4, False)]


def test_the_header_is_at_most_header_limit_bytes() -> None:
    skeleton = propose([bytes(100)])
    assert skeleton.header_length == HEADER_LIMIT
    assert sum(f.length for f in skeleton.fields) == HEADER_LIMIT


def _generates(text: str) -> None:
    generation, diagnostics, error = make_generation(
        "plugin.proposed.yaml", text.encode(), CHOICE, "yaml"
    )
    assert error is None, diagnostics
    assert generation is not None


@pytest.mark.parametrize(
    ("selector", "classify"),
    [
        ("udp:port=4433", None),
        ("udp:dport=4433", ["- {offset: 2, length: 2, value: 4433}"]),
        (
            "udp:sport=1,dport=2",
            ["- {offset: 0, length: 2, value: 1}", "- {offset: 2, length: 2, value: 2}"],
        ),
        ("ethernet:ethertype=0x88b5", ["- {offset: 12, length: 2, value: 0x88b5}"]),
        ("ethernet", None),
        ("tcp:dport=102", []),
        ("tcp", None),
        ("ip:proto=17", None),
        ("ipv6", None),
    ],
)
def test_the_proposal_generates(selector: str, classify: list[str] | None) -> None:
    parent = _parent(selector)
    text = proposed_yaml("demo", 960, parent, propose(samples.demo_payloads()), "a.pcap", 3)
    _generates(text)
    model = load(text, filename="plugin.proposed.yaml").model
    (got,) = model.parents
    assert got.protocol.text == parent.proto
    lines = [line.strip() for line in text.splitlines()]
    if classify is None:
        assert got.classify is None
        assert "attach it in demo_hook_register_parents (src/demo_impl.c)" in text
    else:
        assert got.classify is not None
        assert [m for m in lines if m.startswith("- {offset")] == classify
        if parent.proto == "tcp":
            assert [(k, v.value) for k, v in got.classify.ports] == list(parent.keys)
            assert got.classify.offset is None
    names = [a.alias.text for a in model.attributes.elements if isinstance(a, Attribute)]
    assert names == [
        "field_0",
        "field_1",
        "length",
        "field_4",
        "field_8",
        "field_9",
    ]
    assert "# Not proposed: the bytes from offset 10 on (0 to 9 bytes)." in lines


def test_the_proposal_quotes_its_label_and_escapes_comments() -> None:
    text = proposed_yaml("true", 960, _parent("udp"), propose([b"ab"]), "a\nb.pcap", 1)
    assert '  label: "true"' in text.splitlines()
    assert "a\\nb.pcap" in text
    assert "Not proposed" not in text
    assert load(text, filename="p.yaml").model.properties.label.text == "true"


def test_packet_tests_expect_the_proposal(tmp_path: Path) -> None:
    payloads = samples.demo_payloads()
    skeleton = propose(payloads)
    for n, data in enumerate(payloads, 1):
        payload = Payload(n * 2, ("ethernet", "ip", "udp"), data)
        text = packet_test(
            "demo",
            960,
            f"demo/pcap-{n:03d}",
            payload,
            skeleton,
            'x "y".pcap',
            _parent("udp:port=4433"),
        )
        path = tmp_path / f"t{n}.yaml"
        path.write_text(text)
        test = packets.load(path, path.name, TYPES)
        assert test.id == f"demo/pcap-{n:03d}"
        assert test.data == data
        assert (test.protocol, test.proto_id, test.next.kind) == ("DEMO", 960, "none")
        values = {a.name: a.value for a in test.attributes}
        assert values["field_0"] == 1
        assert values["length"] == len(data)
        assert values["field_4"] == 999 + n
        assert f'source: "frame {n * 2} of x \\"y\\".pcap"' in text


def test_packet_test_bytes_are_16_per_line(tmp_path: Path) -> None:
    data = bytes(range(40))
    skeleton = propose([data])
    text = packet_test(
        "demo",
        960,
        "demo/pcap-001",
        Payload(1, ("ip", "udp"), data),
        skeleton,
        "a.pcap",
        _parent("udp"),
    )
    rows = [line for line in text.splitlines() if line.startswith('  - "')]
    assert [len(r[5:-1].split()) for r in rows] == [16, 16, 8]


def test_tagged_ethernet_frames_are_attached_by_user_code() -> None:
    skeleton = propose(samples.demo_payloads())
    parent = _parent("ethernet:ethertype=0x88b5")
    text = proposed_yaml("demo", 960, parent, skeleton, "a.pcap", 3, tagged=True)
    _generates(text)
    assert "classify:" not in text
    assert "attach it in demo_hook_register_parents" in text
    assert "classify:" in proposed_yaml("demo", 960, parent, skeleton, "a.pcap", 3)


def test_a_file_name_that_is_not_utf8() -> None:
    name = os.fsdecode(b"cap\xff.pcap")
    text = proposed_yaml("demo", 960, _parent("udp"), propose([b"ab"]), name, 1)
    assert "cap\\xff.pcap" in text
    text.encode("utf-8")


# Bit fields (#102).


def _groups(
    values: list[int], flows: list[int] | None = None
) -> list[tuple[int, int, str]] | None:
    return bit_groups(values, flows)


def test_a_byte_with_one_varying_run_stays_whole() -> None:
    assert _groups([2, 3, 2]) is None  # the demo's kind: 7 constant bits
    assert _groups(list(range(21))) is None  # a counter
    assert _groups([0x45] * 3) is None  # constant
    assert _groups([0x81, 0x82, 0x88]) is None  # one opcode run under a constant 0x8_
    # Two runs that do not vary independently are one number: 1 and 8.
    assert _groups([1, 8, 1, 8, 0x21, 0x28]) is None
    # Too few distinct values to tell: 0x81, 0x01, 0x80 would be FIN | opcode.
    assert _groups([0x81, 0x01, 0x80]) is None
    assert _groups([0x81, 0x01, 0x80, 0x00]) == [
        (0, 1, "varies"),
        (1, 6, "constant"),
        (7, 1, "varies"),
    ]


def test_a_few_random_payloads_are_not_cut_into_bits() -> None:
    import random

    rng = random.Random(102)
    for _ in range(500):
        payloads = [rng.randbytes(16) for _ in range(3)]
        assert all(f.bit_offset is None for f in propose(payloads).fields)


def test_flags_and_a_number_that_vary_independently() -> None:
    # FIN, RSV1-3 and the opcode of WebSocket frames; opcode bit 2 (4) never
    # set, so it is a constant bit between varying ones.
    values = [0x81, 0x01, 0x80, 0x89, 0x88, 0x8A, 0x82]
    assert _groups(values) == [(0, 1, "varies"), (1, 3, "constant"), (4, 4, "varies")]


def test_a_role_flag_is_cut_from_its_run() -> None:
    # MASK, set by the client (flow 1) only, then the 7-bit length.
    lengths = [5, 3, 0, 100, 126, 125, 2]
    values = [0x80 | n for n in lengths] + list(lengths)
    flows = [1] * len(lengths) + [2] * len(lengths)
    assert _groups(values, flows) == [(0, 1, "role"), (1, 7, "varies")]
    # Without directions, or with a direction of both values, it is one number.
    assert _groups(values) is None
    assert _groups(values, [1] * len(values)) is None
    # A direction with one payload does not show the other value.
    assert _groups([0x85, 0xFA, 0x05], [1, 1, 2]) is None
    assert _groups([0x85, 0xFA, 0x05, 0x7A], [1, 1, 2, 2]) == [(0, 1, "role"), (1, 7, "varies")]


def test_websocket_frames_propose_fin_opcode_mask_and_length() -> None:
    frames = samples.websocket_client_frames() + samples.websocket_server_frames()
    flows = ["client"] * 7 + ["server"] * 7
    skeleton = propose(frames, flows)
    assert skeleton.header_length == 2
    assert [
        (f.name, f.offset, f.bit_offset, f.bit_width, f.constant) for f in skeleton.fields
    ] == [
        ("field_0_b0", 0, 0, 1, False),  # FIN
        ("field_0_b1", 0, 1, 3, True),  # RSV1-3
        ("field_0_b4", 0, 4, 4, False),  # opcode
        ("field_1_b0", 1, 0, 1, False),  # MASK
        ("field_1_b1", 1, 1, 7, False),  # payload length (7 bits)
    ]
    close = samples.ws_frame(0x8, b"\x03\xe8", key=bytes(4))
    assert [f.value(close) for f in skeleton.fields] == [1, 0, 8, 1, 2]
    assert skeleton.fields[0].to_json() == {
        "name": "field_0_b0",
        "type": "MMT_U8_DATA",
        "offset": 0,
        "length": 1,
        "constant": False,
        "bit_offset": 0,
        "bit_width": 1,
    }
    assert "one value per direction" in skeleton.fields[3].note


def test_a_byte_cut_into_bits_ends_a_run_of_differing_bytes() -> None:
    # Byte 1 has independent flag and number groups; bytes 0 and 2 vary.
    values = [0x01, 0x02, 0x81, 0x82, 0x03]
    payloads = [bytes([i, v, 10 + i]) for i, v in enumerate(values)]
    fields = [(f.name, f.offset, f.length, f.bit_offset) for f in propose(payloads).fields]
    assert fields == [
        ("field_0", 0, 1, None),
        ("field_1_b0", 1, 1, 0),
        ("field_1_b1", 1, 1, 1),
        ("field_1_b6", 1, 1, 6),
        ("field_2", 2, 1, None),
    ]


def test_the_bit_fields_proposal_generates_and_its_tests_expect_it(tmp_path: Path) -> None:
    frames = samples.websocket_client_frames() + samples.websocket_server_frames()
    skeleton = propose(frames, ["c"] * 7 + ["s"] * 7)
    parent = _parent("tcp:port=80")
    text = proposed_yaml("ws", 960, parent, skeleton, "ws.pcap", len(frames))
    _generates(text)
    lines = text.splitlines()
    assert "  - struct: bits_0    # byte 0, cut into bit fields" in lines
    assert "  - struct: bits_1    # byte 1, cut into bit fields" in lines
    assert any(line.startswith("          - {name: field_1_b1, width: 7}") for line in lines)
    model = load(text, filename="plugin.proposed.yaml").model
    assert model.parents[0].protocol.text == "tcp"

    payload = Payload(9, ("ethernet", "ip", "tcp"), frames[6], cut=3)
    test_text = packet_test("ws", 960, "ws/pcap-001", payload, skeleton, "ws.pcap", parent)
    path = tmp_path / "t.yaml"
    path.write_text(test_text)
    test = packets.load(path, path.name, TYPES)
    assert {a.name: a.value for a in test.attributes} == {
        "field_0_b0": 1,
        "field_0_b1": 0,
        "field_0_b4": 8,
        "field_1_b0": 1,
        "field_1_b1": 2,
    }
    assert "      bit_offset: 1" in test_text.splitlines()
    assert 'bytes_source: "captured: the payload of frame 9 of ws.pcap, from byte 3"' in test_text
