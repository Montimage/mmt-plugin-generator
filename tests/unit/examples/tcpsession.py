"""TCP sessions as whole Ethernet frames, for the session replay of the
WebSocket example (``test_sdk.py``).

A ``Session`` is one TCP connection between a client (an address of
198.18.0.0/15, RFC 2544) and the server 192.0.2.1, whose packets it appends
to a list of frames that several sessions may share: ``open()`` adds the
three-way handshake, ``client(data)`` and ``server(data)`` a segment of
each side (a pure ACK without data), with the sequence and acknowledgment
numbers of a connection without loss; ``seq=`` sends a segment at another
sequence number (a retransmission), ``skip_server()`` loses bytes. Every IPv4 and
TCP checksum is right (RFC 791, RFC 9293), and a frame shorter than 60
bytes gets Ethernet padding, as on the wire, so that only the IP length says
where a segment ends.
"""

from __future__ import annotations

import struct

_MAC_CLIENT = bytes.fromhex("020000000001")
_MAC_SERVER = bytes.fromhex("020000000002")
_SERVER = bytes([192, 0, 2, 1])
_SYN, _ACK, _PSH = 0x02, 0x10, 0x08
#: The shortest Ethernet frame without its FCS (IEEE 802.3).
_MIN_FRAME = 60


def _checksum(data: bytes) -> int:
    """The Internet checksum (RFC 1071)."""
    if len(data) % 2:
        data += b"\0"
    total = sum(int(x) for x in struct.unpack(f">{len(data) // 2}H", data))
    while total >> 16:
        total = (total & 0xFFFF) + (total >> 16)
    return ~total & 0xFFFF


def tcp_frame(
    src: bytes, dst: bytes, sport: int, dport: int, seq: int, ack: int, flags: int, data: bytes
) -> bytes:
    """An Ethernet frame of one IPv4 TCP segment (a 20-byte header)."""
    header = struct.pack(
        ">HHIIBBHHH", sport, dport, seq & 0xFFFFFFFF, ack & 0xFFFFFFFF, 5 << 4, flags, 65535, 0, 0
    )
    pseudo = src + dst + struct.pack(">BBH", 0, 6, len(header) + len(data))
    checksum = _checksum(pseudo + header + data)
    segment = header[:16] + struct.pack(">H", checksum) + header[18:] + data
    ip = struct.pack(">BBHHHBBH4s4s", 0x45, 0, 20 + len(segment), 1, 0x4000, 64, 6, 0, src, dst)
    ip = ip[:10] + struct.pack(">H", _checksum(ip)) + ip[12:]
    mac_dst, mac_src = (_MAC_SERVER, _MAC_CLIENT) if dst == _SERVER else (_MAC_CLIENT, _MAC_SERVER)
    frame = mac_dst + mac_src + b"\x08\x00" + ip + segment
    return frame + bytes(max(0, _MIN_FRAME - len(frame)))


class Session:
    """One TCP connection, the ``n``-th, whose packets go to ``frames``."""

    def __init__(self, frames: list[bytes], n: int, client_port: int, server_port: int) -> None:
        self.client_ip = bytes([198, 18, 0, n])
        self.client_port = client_port
        self.server_port = server_port
        self.client_seq = 1000 * n
        self.server_seq = 500000 + 1000 * n
        self.frames = frames

    def _send(self, from_client: bool, data: bytes, flags: int, seq: int | None) -> int:
        if from_client:
            first = self.client_seq if seq is None else seq
            frame = tcp_frame(
                self.client_ip,
                _SERVER,
                self.client_port,
                self.server_port,
                first,
                self.server_seq,
                flags,
                data,
            )
        else:
            first = self.server_seq if seq is None else seq
            frame = tcp_frame(
                _SERVER,
                self.client_ip,
                self.server_port,
                self.client_port,
                first,
                self.client_seq,
                flags,
                data,
            )
        self.frames.append(frame)
        return len(self.frames) - 1

    def open(self) -> None:
        """SYN, SYN/ACK, ACK (RFC 9293 section 3.5); each SYN takes a sequence number."""
        self._send(True, b"", _SYN, None)
        self.client_seq += 1
        self._send(False, b"", _SYN | _ACK, None)
        self.server_seq += 1
        self._send(True, b"", _ACK, None)

    def client(self, data: bytes = b"", seq: int | None = None) -> int:
        """A segment from the client; its index in the frames."""
        index = self._send(True, data, _PSH | _ACK if data else _ACK, seq)
        if seq is None:
            self.client_seq += len(data)
        return index

    def server(self, data: bytes = b"", seq: int | None = None) -> int:
        """A segment from the server; its index in the frames."""
        index = self._send(False, data, _PSH | _ACK if data else _ACK, seq)
        if seq is None:
            self.server_seq += len(data)
        return index

    def skip_server(self, count: int) -> None:
        """Lose the server's next ``count`` bytes: the capture never has them."""
        self.server_seq += count
