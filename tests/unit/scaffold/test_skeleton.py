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
        ("tcp:dport=102", None),
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
