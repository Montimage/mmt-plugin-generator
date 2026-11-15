"""Sample captures for the scaffold tests, built byte by byte.

``ethernet``, ``vlan``, ``ipv4``, ``ipv6``, ``udp`` and ``tcp`` build the
headers (checksums are left 0: nothing here checks them); ``pcap`` and
``pcapng`` write a capture file of frames. ``demo_payloads`` is a small
protocol: version 1, a kind, a 2-byte length of the whole payload and a
4-byte sequence number, then a body.
"""

from __future__ import annotations

import struct
from collections.abc import Sequence

ETHERNET = 1
RAW = 101
SLL = 113
NULL = 0

_MAC_DST = bytes.fromhex("020000000002")
_MAC_SRC = bytes.fromhex("020000000001")


def ethernet(ethertype: int, payload: bytes) -> bytes:
    return _MAC_DST + _MAC_SRC + struct.pack(">H", ethertype) + payload


def vlan(vid: int, ethertype: int, payload: bytes) -> bytes:
    """An 802.1Q-tagged Ethernet frame."""
    return _MAC_DST + _MAC_SRC + struct.pack(">HHH", 0x8100, vid, ethertype) + payload


def ipv4(proto: int, payload: bytes, *, flags_frag: int = 0, options: bytes = b"") -> bytes:
    ihl = (20 + len(options)) // 4
    total = 20 + len(options) + len(payload)
    header = struct.pack(
        ">BBHHHBBH4s4s",
        0x40 | ihl,
        0,
        total,
        1,
        flags_frag,
        64,
        proto,
        0,
        bytes([192, 0, 2, 1]),
        bytes([192, 0, 2, 2]),
    )
    return header + options + payload


def ipv6(next_header: int, payload: bytes, *, extensions: bytes = b"") -> bytes:
    body = extensions + payload
    header = struct.pack(">IHBB", 0x60000000, len(body), next_header, 64)
    return (
        header
        + bytes.fromhex("20010db8000000000000000000000001")
        + bytes.fromhex("20010db8000000000000000000000002")
        + body
    )


def udp(sport: int, dport: int, payload: bytes) -> bytes:
    return struct.pack(">HHHH", sport, dport, 8 + len(payload), 0) + payload


def tcp(sport: int, dport: int, payload: bytes, *, options: bytes = b"") -> bytes:
    offset = (20 + len(options)) // 4
    header = struct.pack(">HHIIBBHHH", sport, dport, 1, 0, offset << 4, 0x18, 1024, 0, 0)
    return header + options + payload


def udp4(sport: int, dport: int, payload: bytes) -> bytes:
    """An Ethernet frame of IPv4 and UDP."""
    return ethernet(0x0800, ipv4(17, udp(sport, dport, payload)))


def pcap(
    frames: Sequence[bytes],
    linktype: int = ETHERNET,
    *,
    big_endian: bool = False,
    nanoseconds: bool = False,
    snaplen: int = 65535,
) -> bytes:
    order = ">" if big_endian else "<"
    magic = 0xA1B23C4D if nanoseconds else 0xA1B2C3D4
    out = struct.pack(order + "IHHiIII", magic, 2, 4, 0, 0, 65535, linktype)
    for i, frame in enumerate(frames):
        cut = frame[:snaplen]
        out += struct.pack(order + "IIII", 1700000000 + i, 0, len(cut), len(frame)) + cut
    return out


def _block(order: str, kind: int, body: bytes) -> bytes:
    body += b"\0" * (-len(body) % 4)
    length = 12 + len(body)
    return struct.pack(order + "II", kind, length) + body + struct.pack(order + "I", length)


def pcapng(
    frames: Sequence[bytes],
    linktype: int = ETHERNET,
    *,
    big_endian: bool = False,
    simple: bool = False,
) -> bytes:
    order = ">" if big_endian else "<"
    out = _block(order, 0x0A0D0D0A, struct.pack(order + "IHHq", 0x1A2B3C4D, 1, 0, -1))
    out += _block(order, 1, struct.pack(order + "HHI", linktype, 0, 0))
    out += _block(order, 4, b"\x00\x00\x00\x00")  # a name resolution block: skipped
    for i, frame in enumerate(frames):
        if simple:
            out += _block(order, 3, struct.pack(order + "I", len(frame)) + frame)
        else:
            header = struct.pack(order + "IIIII", 0, 0, i, len(frame), len(frame))
            out += _block(order, 6, header + frame)
    return out


def demo_payload(kind: int, seq: int, body: bytes) -> bytes:
    """version 1, kind, length (of the whole payload), sequence, body."""
    return struct.pack(">BBHI", 1, kind, 8 + len(body), seq) + body


def demo_payloads() -> list[bytes]:
    return [
        demo_payload(2, 1000, b"hello"),
        demo_payload(3, 1001, b"hi"),
        demo_payload(2, 1002, b"how are you"),
    ]
