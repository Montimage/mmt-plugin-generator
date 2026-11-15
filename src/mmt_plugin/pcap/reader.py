"""Reading capture files: classic pcap and pcapng, without a library.

``read(data)`` checks the file header and returns a ``Capture`` whose
``frames()`` yields every packet record in file order, as a ``Frame``: its
1-based number (as Wireshark numbers frames), its link type, the captured
bytes and the original length. A file that is not a capture, or one whose
structure is broken (a truncated record, a block whose lengths disagree, a
packet of an interface that was never described), raises ``PcapError`` with
the byte offset where it is wrong, when ``frames()`` reaches it.

Classic pcap: the four magic numbers (microsecond and nanosecond time
stamps, either byte order); the link type is the low 16 bits of the
header's ``network`` field. pcapng: section header, interface description,
enhanced, simple and (obsolete) packet blocks; other blocks are skipped,
and a new section header starts a new list of interfaces. Time stamps are
not read: nothing here needs them.
"""

from __future__ import annotations

import struct
from collections.abc import Iterator
from dataclasses import dataclass

__all__ = ["Capture", "Frame", "PcapError", "read"]

_PCAP_MAGIC = {
    b"\xd4\xc3\xb2\xa1": "<",  # microseconds, little-endian
    b"\xa1\xb2\xc3\xd4": ">",
    b"\x4d\x3c\xb2\xa1": "<",  # nanoseconds
    b"\xa1\xb2\x3c\x4d": ">",
}
_PCAP_HEADER = 24
_PCAP_RECORD = 16

_SHB = 0x0A0D0D0A
_IDB = 0x00000001
_PB = 0x00000002
_SPB = 0x00000003
_EPB = 0x00000006
_BYTE_ORDER_MAGIC = 0x1A2B3C4D


class PcapError(Exception):
    """The capture cannot be read: ``message`` says why, ``offset`` where
    (the byte offset in the file, ``None`` for the whole file)."""

    def __init__(self, message: str, offset: int | None = None) -> None:
        super().__init__(message if offset is None else f"{message} (at byte {offset})")
        self.message = message
        self.offset = offset


@dataclass(frozen=True)
class Frame:
    """One packet record: ``number`` (1-based, in file order), ``linktype``
    (a LINKTYPE_* value), the captured ``data`` and the ``original`` length
    of the packet on the wire (``len(data)`` when it was not cut)."""

    number: int
    linktype: int
    data: bytes
    original: int

    @property
    def truncated(self) -> bool:
        """Whether the capture cut the packet (its snap length)."""
        return len(self.data) < self.original


@dataclass(frozen=True)
class Capture:
    """A capture file: ``format`` is ``pcap`` or ``pcapng``."""

    format: str
    data: bytes

    def frames(self) -> Iterator[Frame]:
        """Every packet record, in file order; ``PcapError`` on a broken one."""
        if self.format == "pcap":
            return _pcap_frames(self.data)
        return _pcapng_frames(self.data)


def read(data: bytes) -> Capture:
    """The capture of ``data``; ``PcapError`` when it is neither format."""
    if len(data) >= 4 and data[:4] in _PCAP_MAGIC:
        if len(data) < _PCAP_HEADER:
            raise PcapError(
                f"the pcap file header is {_PCAP_HEADER} bytes, the file has {len(data)}", 0
            )
        return Capture("pcap", data)
    if len(data) >= 4 and data[:4] == b"\x0a\x0d\x0d\x0a":
        _section_order(data, 0)
        return Capture("pcapng", data)
    raise PcapError("not a pcap or pcapng file (unknown magic number)", 0)


def _pcap_frames(data: bytes) -> Iterator[Frame]:
    order = _PCAP_MAGIC[data[:4]]
    linktype = struct.unpack_from(order + "I", data, 20)[0] & 0xFFFF
    pos = _PCAP_HEADER
    number = 0
    while pos < len(data):
        if len(data) - pos < _PCAP_RECORD:
            raise PcapError(
                f"a truncated record header ({len(data) - pos} of {_PCAP_RECORD} bytes)", pos
            )
        caplen, original = struct.unpack_from(order + "II", data, pos + 8)
        start = pos + _PCAP_RECORD
        if caplen > len(data) - start:
            raise PcapError(
                f"a record of {caplen} bytes, but only {len(data) - start} bytes are left", pos
            )
        number += 1
        yield Frame(number, linktype, data[start : start + caplen], max(original, caplen))
        pos = start + caplen


def _section_order(data: bytes, pos: int) -> str:
    """The byte order of the section header block at ``pos``."""
    if len(data) - pos < 28:
        raise PcapError("a truncated pcapng section header block", pos)
    for order in ("<", ">"):
        if struct.unpack_from(order + "I", data, pos + 8)[0] == _BYTE_ORDER_MAGIC:
            return order
    raise PcapError("a pcapng section header block without its byte-order magic", pos)


def _pcapng_frames(data: bytes) -> Iterator[Frame]:
    pos = 0
    order = "<"
    # Per interface: (link type, snap length); reset by each section header.
    interfaces: list[tuple[int, int]] = []
    number = 0
    while pos < len(data):
        if len(data) - pos < 12:
            raise PcapError(f"a truncated pcapng block ({len(data) - pos} bytes)", pos)
        if data[pos : pos + 4] == b"\x0a\x0d\x0d\x0a":
            order = _section_order(data, pos)
            interfaces = []
        kind, length = struct.unpack_from(order + "II", data, pos)
        if length < 12 or length % 4 or length > len(data) - pos:
            raise PcapError(
                f"a pcapng block of length {length} ({len(data) - pos} bytes are left)", pos
            )
        if struct.unpack_from(order + "I", data, pos + length - 4)[0] != length:
            raise PcapError("a pcapng block whose two lengths differ", pos)
        body = data[pos + 8 : pos + length - 4]
        if kind == _IDB:
            if len(body) < 8:
                raise PcapError("a truncated pcapng interface description block", pos)
            linktype, _, snaplen = struct.unpack_from(order + "HHI", body, 0)
            interfaces.append((linktype, snaplen))
        elif kind in (_EPB, _PB, _SPB):
            number += 1
            yield _packet(kind, body, order, interfaces, number, pos)
        pos += length


def _packet(
    kind: int, body: bytes, order: str, interfaces: list[tuple[int, int]], number: int, pos: int
) -> Frame:
    if kind == _SPB:
        if len(body) < 4:
            raise PcapError("a truncated pcapng simple packet block", pos)
        iface = 0
        original = struct.unpack_from(order + "I", body, 0)[0]
        start = 4
        if not interfaces:
            raise PcapError("a simple packet block before any interface description", pos)
        snaplen = interfaces[0][1]
        caplen = min(original, len(body) - start)
        if snaplen:
            caplen = min(caplen, snaplen)
    else:
        if kind == _EPB:
            if len(body) < 20:
                raise PcapError("a truncated pcapng enhanced packet block", pos)
            iface, _, _, caplen, original = struct.unpack_from(order + "IIIII", body, 0)
        else:
            if len(body) < 20:
                raise PcapError("a truncated pcapng packet block", pos)
            iface, _, _, _, caplen, original = struct.unpack_from(order + "HHIIII", body, 0)
        start = 20
        if iface >= len(interfaces):
            raise PcapError(f"a packet of interface {iface}, which no block describes", pos)
        if caplen > len(body) - start:
            raise PcapError(
                f"a packet of {caplen} bytes in a block that holds {len(body) - start}", pos
            )
    return Frame(number, interfaces[iface][0], body[start : start + caplen], max(original, caplen))
