"""``mmt_plugin.pcap.layers``: the parents and keys ``scaffold`` decodes,
and the payloads it slices from each link type and stack, with the reason
of every frame it skips."""

from __future__ import annotations

import struct

import pytest

from mmt_plugin.commands.init import parse_selector
from mmt_plugin.diagnostics import CliError
from mmt_plugin.pcap import Frame, Parent, parent_of, slice_payloads

from . import samples

PAYLOAD = b"\x01\x02payload"


def _parent(text: str) -> Parent:
    selector = parse_selector(text)
    return parent_of(selector.text, selector.proto, selector.keys)


def _frame(data: bytes, linktype: int = samples.ETHERNET, original: int | None = None) -> Frame:
    return Frame(1, linktype, data, len(data) if original is None else original)


def _one(frame: Frame, text: str) -> tuple[bytes | None, tuple[str, ...], str]:
    """The payload, its path and the skip reason ('' when kept)."""
    slicing = slice_payloads([frame], _parent(text), 20)
    if slicing.payloads:
        (payload,) = slicing.payloads
        return payload.data, payload.path, ""
    (reason,) = [k for k, v in slicing.skipped.items() if v]
    return None, (), reason


def test_parent_of_reads_numbers_in_decimal_and_hex() -> None:
    assert _parent("udp:port=4433").keys == (("port", 4433),)
    assert _parent("ethernet:ethertype=0x88b5").keys == (("ethertype", 0x88B5),)
    assert _parent("tcp:sport=1,dport=2").keys == (("sport", 1), ("dport", 2))
    assert _parent("ip").keys == ()


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("sctp:port=1", "not sctp"),
        ("udp:ethertype=1", "udp has no key 'ethertype'"),
        ("udp:port=65536", "port=65536 is not a number from 0 to 0xffff"),
        ("ip:proto=x1", "proto=x1 is not a number"),
        ("ip:proto=0x100", "is not a number from 0 to 0xff"),
    ],
)
def test_parent_of_refuses_what_it_does_not_decode(text: str, message: str) -> None:
    with pytest.raises(CliError, match=message) as info:
        _parent(text)
    assert info.value.code == "usage.invalid-value"


@pytest.mark.parametrize(
    ("data", "linktype", "text", "path"),
    [
        (
            samples.udp4(1, 4433, PAYLOAD),
            samples.ETHERNET,
            "udp:port=4433",
            ("ethernet", "ip", "udp"),
        ),
        (
            samples.udp4(4433, 1, PAYLOAD),
            samples.ETHERNET,
            "udp:port=4433",
            ("ethernet", "ip", "udp"),
        ),
        (
            samples.udp4(1, 4433, PAYLOAD),
            samples.ETHERNET,
            "udp:dport=4433",
            ("ethernet", "ip", "udp"),
        ),
        (samples.udp4(1, 4433, PAYLOAD), samples.ETHERNET, "udp", ("ethernet", "ip", "udp")),
        (
            samples.udp4(1, 4433, PAYLOAD),
            samples.ETHERNET,
            "ip:proto=17",
            ("ethernet", "ip"),
        ),
        (
            samples.ethernet(0x88B5, PAYLOAD),
            samples.ETHERNET,
            "ethernet:ethertype=0x88b5",
            ("ethernet",),
        ),
        (
            samples.vlan(10, 0x88B5, PAYLOAD),
            samples.ETHERNET,
            "ethernet:ethertype=0x88b5",
            ("ethernet", "8021q"),
        ),
        (
            samples.vlan(10, 0x0800, samples.ipv4(6, samples.tcp(102, 5000, PAYLOAD))),
            samples.ETHERNET,
            "tcp:port=102",
            ("ethernet", "8021q", "ip", "tcp"),
        ),
        (
            samples.ethernet(
                0x0800,
                samples.ipv4(
                    6, samples.tcp(5000, 102, PAYLOAD, options=bytes(12)), options=bytes(8)
                ),
            ),
            samples.ETHERNET,
            "tcp:dport=102",
            ("ethernet", "ip", "tcp"),
        ),
        (
            samples.ethernet(0x86DD, samples.ipv6(17, samples.udp(1, 4433, PAYLOAD))),
            samples.ETHERNET,
            "udp:port=4433",
            ("ethernet", "ipv6", "udp"),
        ),
        (
            # hop-by-hop options, then an atomic fragment header, then UDP
            samples.ethernet(
                0x86DD,
                samples.ipv6(
                    0,
                    samples.udp(1, 4433, PAYLOAD),
                    extensions=bytes([44, 0]) + bytes(6) + bytes([17, 0]) + bytes(6),
                ),
            ),
            samples.ETHERNET,
            "udp:port=4433",
            ("ethernet", "ipv6", "udp"),
        ),
        (
            samples.ethernet(0x86DD, samples.ipv6(253, PAYLOAD)),
            samples.ETHERNET,
            "ipv6:proto=253",
            ("ethernet", "ipv6"),
        ),
        (
            samples.ipv4(17, samples.udp(1, 4433, PAYLOAD)),
            samples.RAW,
            "udp:port=4433",
            ("ip", "udp"),
        ),
        (
            samples.ipv6(17, samples.udp(1, 4433, PAYLOAD)),
            229,
            "udp:port=4433",
            ("ipv6", "udp"),
        ),
        (
            bytes(14) + b"\x08\x00" + samples.ipv4(17, samples.udp(1, 4433, PAYLOAD)),
            samples.SLL,
            "udp:port=4433",
            ("ip", "udp"),
        ),
        (
            b"\x86\xdd" + bytes(18) + samples.ipv6(17, samples.udp(1, 4433, PAYLOAD)),
            276,
            "udp:port=4433",
            ("ipv6", "udp"),
        ),
        (
            struct.pack("<I", 2) + samples.ipv4(17, samples.udp(1, 4433, PAYLOAD)),
            samples.NULL,
            "udp:port=4433",
            ("ip", "udp"),
        ),
        (
            struct.pack(">I", 30) + samples.ipv6(17, samples.udp(1, 4433, PAYLOAD)),
            108,
            "udp:port=4433",
            ("ipv6", "udp"),
        ),
    ],
)
def test_payloads_under_each_parent_and_link(
    data: bytes, linktype: int, text: str, path: tuple[str, ...]
) -> None:
    payload, got_path, reason = _one(_frame(data, linktype), text)
    assert reason == ""
    assert got_path == path
    # Under ip, the payload is the UDP datagram; everywhere else PAYLOAD.
    assert payload == (samples.udp(1, 4433, PAYLOAD) if path[-1] == "ip" else PAYLOAD)


def test_the_ip_and_udp_lengths_cut_the_ethernet_padding() -> None:
    frame = samples.udp4(1, 4433, b"ab") + bytes(20)
    assert _one(_frame(frame), "udp:port=4433")[0] == b"ab"


@pytest.mark.parametrize(
    ("data", "linktype", "text", "reason"),
    [
        (samples.udp4(1, 53, PAYLOAD), samples.ETHERNET, "udp:port=4433", "no-match"),
        (samples.ethernet(0x0806, bytes(28)), samples.ETHERNET, "udp", "no-match"),
        (samples.udp4(1, 4433, b""), samples.ETHERNET, "udp:port=4433", "empty"),
        (
            samples.ethernet(
                0x0800, samples.ipv4(17, samples.udp(1, 4433, PAYLOAD), flags_frag=0x2000)
            ),
            samples.ETHERNET,
            "udp",
            "fragment",
        ),
        (
            samples.ethernet(0x0800, samples.ipv4(17, PAYLOAD, flags_frag=0x0010)),
            samples.ETHERNET,
            "ip",
            "fragment",
        ),
        (
            samples.ethernet(
                0x86DD, samples.ipv6(44, PAYLOAD, extensions=bytes([17, 0, 0, 8]) + bytes(4))
            ),
            samples.ETHERNET,
            "udp",
            "fragment",
        ),
        (samples.udp4(1, 4433, PAYLOAD)[:20], samples.ETHERNET, "udp", "malformed"),
        (samples.ethernet(0x0800, b"\x45" + bytes(10)), samples.ETHERNET, "udp", "malformed"),
        (
            samples.ethernet(0x0800, samples.ipv4(17, b"\0\1\0\2\0\5\0\0")),
            samples.ETHERNET,
            "udp",
            "malformed",
        ),
        (
            samples.ethernet(0x0800, samples.ipv4(6, bytes(12) + b"\x40" + bytes(7))),
            samples.ETHERNET,
            "tcp",
            "malformed",
        ),
        (samples.ethernet(0x86DD, bytes(40)), samples.ETHERNET, "ipv6", "malformed"),
        (b"\x00", samples.RAW, "ip", "malformed"),
        (b"\x00" * 3, samples.NULL, "ip", "malformed"),
        (samples.udp4(1, 4433, PAYLOAD), 147, "udp", "unsupported-link"),
    ],
)
def test_skip_reasons(data: bytes, linktype: int, text: str, reason: str) -> None:
    assert _one(_frame(data, linktype), text) == (None, (), reason)


def test_a_frame_cut_by_the_capture() -> None:
    frame = samples.udp4(1, 4433, PAYLOAD)
    # The UDP length says more than was captured.
    cut = _frame(frame[:-3], original=len(frame))
    assert _one(cut, "udp:port=4433") == (None, (), "truncated")
    # Under Ethernet there is no length: any cut frame is truncated.
    eth = samples.ethernet(0x88B5, PAYLOAD)
    assert _one(_frame(eth, original=len(eth) + 1), "ethernet")[2] == "truncated"
    # A cut padding leaves the UDP payload whole.
    padded = _frame(frame, original=len(frame) + 10)
    assert _one(padded, "udp:port=4433")[0] == PAYLOAD


def test_slicing_stops_at_the_limit() -> None:
    frames = [
        Frame(i + 1, samples.ETHERNET, samples.udp4(1, 4433 if i % 2 else 53, bytes([i])), 50)
        for i in range(10)
    ]
    slicing = slice_payloads(iter(frames), _parent("udp:port=4433"), 3)
    assert [p.frame for p in slicing.payloads] == [2, 4, 6]
    assert slicing.frames == 6
    assert slicing.skipped["no-match"] == 3
