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


def tcp(
    sport: int,
    dport: int,
    payload: bytes,
    *,
    options: bytes = b"",
    seq: int = 1,
    flags: int = 0x18,
) -> bytes:
    """A TCP segment (``flags`` 0x18 is PSH and ACK, 0x02 SYN)."""
    offset = (20 + len(options)) // 4
    header = struct.pack(">HHIIBBHHH", sport, dport, seq, 0, offset << 4, flags, 1024, 0, 0)
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


def tcp4(sport: int, dport: int, payload: bytes, *, seq: int, flags: int = 0x18) -> bytes:
    """An Ethernet frame of IPv4 and TCP, from 192.0.2.1 to 192.0.2.2."""
    return ethernet(0x0800, ipv4(6, tcp(sport, dport, payload, seq=seq, flags=flags)))


def ws_frame(opcode: int, payload: bytes, *, fin: bool = True, key: bytes | None = None) -> bytes:
    """A WebSocket frame (RFC 6455, section 5.2): masked with ``key``."""
    head = bytes([(0x80 if fin else 0) | opcode])
    mask = 0x80 if key is not None else 0
    n = len(payload)
    if n < 126:
        head += bytes([mask | n])
    else:
        head += bytes([mask | 126]) + struct.pack(">H", n)
    if key is None:
        return head + payload
    return head + key + bytes(b ^ key[i % 4] for i, b in enumerate(payload))


WS_REQUEST = (
    b"GET /chat HTTP/1.1\r\nHost: server.example\r\nUpgrade: websocket\r\n"
    b"Connection: Upgrade\r\nSec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n"
    b"Sec-WebSocket-Version: 13\r\n\r\n"
)
WS_ANSWER = (
    b"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
    b"Sec-WebSocket-Accept: s3pPLMBiTxaQ9kYGJxo0e/YZzOo=\r\n\r\n"
)
_KEY = bytes.fromhex("37fa213d")


def websocket_client_frames() -> list[bytes]:
    """The client's frames (masked) after the handshake, in stream order."""
    return [
        ws_frame(0x1, b"hello", key=_KEY),
        ws_frame(0x1, b"abc", fin=False, key=_KEY),
        ws_frame(0x0, b"def", key=_KEY),
        ws_frame(0x9, b"", key=_KEY),
        ws_frame(0x2, bytes(range(100)), key=_KEY),
        ws_frame(0x1, b"x" * 200, key=_KEY),
        ws_frame(0x8, b"\x03\xe8", key=_KEY),
    ]


def websocket_server_frames() -> list[bytes]:
    """The server's frames (unmasked) after the handshake, in stream order."""
    return [
        ws_frame(0x1, b"world"),
        ws_frame(0x1, b"gh", fin=False),
        ws_frame(0x0, b"ij"),
        ws_frame(0xA, b""),
        ws_frame(0x2, bytes(125)),
        ws_frame(0x1, b"y" * 300),
        ws_frame(0x8, b"\x03\xe8"),
    ]


def websocket_capture() -> bytes:
    """One WebSocket session over TCP port 80, as a pcap: the handshake
    (SYN, SYN-ACK, the client's upgrade request, the server's 101 answer
    with its first frame in the same segment), then one frame per segment
    each way, with a client segment sent twice and two server segments
    swapped."""
    client, server = 50000, 80
    c_seq, s_seq = 1000, 5000
    frames = [
        tcp4(client, server, b"", seq=c_seq, flags=0x02),
        tcp4(server, client, b"", seq=s_seq, flags=0x12),
    ]
    c_next, s_next = c_seq + 1, s_seq + 1
    frames.append(tcp4(client, server, WS_REQUEST, seq=c_next))
    c_next += len(WS_REQUEST)
    server_frames = websocket_server_frames()
    first = WS_ANSWER + server_frames[0]
    frames.append(tcp4(server, client, first, seq=s_next))
    s_next += len(first)
    client_segments = []
    for f in websocket_client_frames():
        client_segments.append(tcp4(client, server, f, seq=c_next))
        c_next += len(f)
    server_segments = []
    for f in server_frames[1:]:
        server_segments.append(tcp4(server, client, f, seq=s_next))
        s_next += len(f)
    server_segments[1], server_segments[2] = server_segments[2], server_segments[1]
    for i in range(max(len(client_segments), len(server_segments))):
        if i < len(client_segments):
            frames.append(client_segments[i])
            if i == 1:
                frames.append(client_segments[i])  # a retransmission
        if i < len(server_segments):
            frames.append(server_segments[i])
    return pcap(frames)
