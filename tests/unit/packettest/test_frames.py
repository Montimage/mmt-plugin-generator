"""The lower layers of a packet test's ``through`` (``mmt_plugin.testing.frames``):
the selector, and frames that scaffold's own decoder (``mmt_plugin.pcap.layers``)
slices back to the packet, with right lengths and checksums."""

from __future__ import annotations

import struct

import pytest

from mmt_plugin.pcap.layers import parent_of, slice_payloads
from mmt_plugin.pcap.reader import Frame
from mmt_plugin.testing.frames import (
    ParentFrame,
    PluginParent,
    Through,
    build_frame,
    parse_through,
)

PAYLOAD = bytes.fromhex("0300001611e00000000100c1020100c2020102c0010a")


def _sum(data: bytes) -> int:
    if len(data) % 2:
        data += b"\0"
    total = sum(int(x) for x in struct.unpack(f">{len(data) // 2}H", data))
    while total >> 16:
        total = (total & 0xFFFF) + (total >> 16)
    return total


def _sliced(frame: bytes, selector: str) -> list[bytes]:
    """The payloads scaffold's decoder finds in ``frame`` under ``selector``."""
    proto, _, rest = selector.partition(":")
    keys = [tuple(k.split("=")) for k in rest.split(",")] if rest else []
    parent = parent_of(selector, proto, keys)  # type: ignore[arg-type]
    return [p.data for p in slice_payloads([Frame(1, 1, frame, len(frame))], parent, 1).payloads]


@pytest.mark.parametrize(
    ("selector", "offset"),
    [
        ("ethernet:ethertype=0x0806", 14),
        ("ip:proto=6", 34),
        ("ipv6:proto=17", 54),
        ("udp:dport=53", 42),
        ("udp:port=53", 42),
        ("udp:sport=53", 42),
        ("udp", 42),
        ("tcp:dport=102", 54),
        ("tcp:sport=102,dport=4000", 54),
    ],
)
def test_the_frame_slices_back_to_the_packet_at_its_offset(selector: str, offset: int) -> None:
    through = parse_through(selector)
    assert through.offset == offset
    frame = build_frame(through, PAYLOAD, 3)
    assert frame[offset:] == PAYLOAD
    assert frame[:12] == bytes.fromhex("020000000002020000000001")
    assert _sliced(frame, selector) == [PAYLOAD]


def test_the_ports_and_addresses_are_the_selectors_else_one_per_frame() -> None:
    def udp(selector: str, n: int) -> tuple[bytes, int, int]:
        frame = build_frame(parse_through(selector), PAYLOAD, n)
        sport, dport = struct.unpack(">HH", frame[34:38])
        return frame[26:30], sport, dport

    assert udp("udp:dport=53", 0)[2] == udp("udp:port=53", 0)[2] == 53
    assert udp("udp:sport=53", 0)[1] == 53
    first, second = udp("udp", 0), udp("udp", 1)
    assert first[0] == bytes([198, 18, 0, 1]) and second[0] == bytes([198, 18, 0, 2])
    assert all(49152 <= port <= 65535 for port in (*first[1:], *second[1:]))
    assert first[1] != second[1] and first[2] != second[2]
    # The same frame on every run.
    assert build_frame(parse_through("udp"), PAYLOAD, 7) == build_frame(
        parse_through("udp"), PAYLOAD, 7
    )


@pytest.mark.parametrize("selector", ["ip:proto=6", "udp:dport=53", "tcp:dport=102"])
def test_the_ipv4_header_lengths_and_checksums_hold(selector: str) -> None:
    frame = build_frame(parse_through(selector), PAYLOAD, 5)
    ip = frame[14:34]
    assert ip[0] == 0x45 and struct.unpack(">H", ip[2:4])[0] == len(frame) - 14
    assert _sum(ip) == 0xFFFF
    proto = ip[9]
    segment = frame[34:]
    if selector.startswith(("udp", "tcp")):
        pseudo = ip[12:20] + struct.pack(">BBH", 0, proto, len(segment))
        assert _sum(pseudo + segment) == 0xFFFF
    if selector.startswith("udp"):
        assert struct.unpack(">H", segment[4:6])[0] == len(segment)
    if selector.startswith("tcp"):
        assert segment[12] >> 4 == 5 and segment[13] == 0x18  # PSH, ACK


def test_the_ethernet_and_ipv6_layers_name_their_protocol() -> None:
    frame = build_frame(parse_through("ethernet:ethertype=0x8624"), PAYLOAD)
    assert frame[12:14] == b"\x86\x24"
    frame = build_frame(parse_through("ipv6:proto=17"), PAYLOAD)
    assert frame[12:14] == b"\x86\xdd" and frame[14] >> 4 == 6
    assert struct.unpack(">H", frame[18:20])[0] == len(PAYLOAD) and frame[20] == 17


def test_a_selector_keeps_its_text_and_numbers() -> None:
    assert parse_through("tcp:sport=0x66,dport=7") == Through(
        "tcp:sport=0x66,dport=7", "tcp", (("sport", 102), ("dport", 7))
    )


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("", "is not a selector"),
        ("UDP", "is not a selector"),
        ("udp:", "is not a selector"),
        ("udp:dport", "is not a selector"),
        ("udp:dport=5 3", "is not a selector"),
        ("vlan:id=3", "the parent is one of"),
        ("tcp:flags=2", "tcp has no key 'flags'"),
        ("tcp:dport=x", "dport=x is not a number"),
        ("ip:proto=256", "proto=256 is not a number from 0 to 0xff"),
        ("ipv6", "ipv6 needs proto="),
        ("tcp:port=1,dport=1", "give port or dport, not both"),
    ],
)
def test_a_bad_selector_says_why(text: str, message: str) -> None:
    with pytest.raises(ValueError, match=message.replace("(", r"\(")):
        parse_through(text)


# --- a plugin parent (#147) -----------------------------------------------------------

#: A parent plugin above Ethernet (EtherType 0x88b6), whose header is 4 bytes;
#: its second test also carries a payload after it.
_ETHER = parse_through("ethernet:ethertype=0x88b6")
_FIRST = ParentFrame("parentp/basic", _ETHER, bytes.fromhex("01020004"), 970)
_SECOND = ParentFrame("parentp/udp", parse_through("udp:dport=9"), bytes.fromhex("0102"), 970)
PARENTS = {"parentp": PluginParent("parentp", 970, "../parentp", (_FIRST, _SECOND))}


def test_a_plugin_parent_runs_through_its_first_packet_test() -> None:
    through = parse_through("parentp", PARENTS)
    assert through == Through("parentp", "parentp", (), _FIRST)
    assert through.offset == 18
    frame = build_frame(through, PAYLOAD, 3)
    assert frame == build_frame(_ETHER, bytes.fromhex("01020004") + PAYLOAD, 3)
    assert frame[through.offset :] == PAYLOAD


def test_test_picks_the_plugin_parents_packet_test() -> None:
    through = parse_through("parentp:test=parentp/udp", PARENTS)
    assert through.plugin == _SECOND
    assert through.offset == 44
    frame = build_frame(through, PAYLOAD, 5)
    assert _sliced(frame, "udp:dport=9") == [bytes.fromhex("0102") + PAYLOAD]
    assert frame[through.offset :] == PAYLOAD


def test_an_mmt_dpi_protocol_is_never_a_plugin_parent() -> None:
    plugins = {"udp": PluginParent("udp", 970, "../udp", (_FIRST,))}
    assert parse_through("udp:dport=53", plugins) == parse_through("udp:dport=53")


@pytest.mark.parametrize(
    ("text", "message"),
    [
        (
            "other",
            "the parent is one of ethernet, ip, ipv6, udp, tcp or a plugin of plugins:"
            " (parentp), not other",
        ),
        ("parentp:dport=1", "a plugin parent has one key, test, not 'dport'"),
        ("parentp:test=a,test=b", "test is given twice"),
        (
            "parentp:test=parentp/none",
            "../parentp has no packet test 'parentp/none' that runs"
            " through an mmt-dpi protocol (tests: parentp/basic, parentp/udp)",
        ),
        ("bare", "no packet test of ../bare runs through an mmt-dpi protocol"),
    ],
)
def test_a_bad_plugin_parent_selector_says_why(text: str, message: str) -> None:
    plugins = {**PARENTS, "bare": PluginParent("bare", 971, "../bare", ())}
    if text == "other":
        plugins = PARENTS
    with pytest.raises(ValueError) as caught:
        parse_through(text, plugins)
    assert message in str(caught.value)


def test_without_plugins_a_label_is_not_a_parent() -> None:
    with pytest.raises(ValueError, match="the parent is one of ethernet, ip, ipv6, udp, tcp, not"):
        parse_through("parentp")
    with pytest.raises(ValueError, match="the parent is one of ethernet, ip, ipv6, udp, tcp, not"):
        parse_through("parentp", {})
