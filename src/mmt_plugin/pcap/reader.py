"""Reading capture files: classic pcap and pcapng, without a library.

``read_stream(stream)`` checks the file header of a binary stream and
returns a ``Capture`` whose ``frames()`` reads the stream one record (pcap)
or block (pcapng) at a time and yields every packet record in file order,
as a ``Frame``: its 1-based number (as Wireshark numbers frames), its link
type, the captured bytes and the original length. Nothing past the record
of the last frame taken is read, so a caller that stops early (``scaffold``
at its ``--max-packets``-th payload) never reads the rest of the file.
``read(data)`` is the same on bytes already in memory.

A file that is not a capture, or one whose structure is broken (a truncated
record, a block whose lengths disagree, a packet of an interface that was
never described), raises ``PcapError`` with the byte offset where it is
wrong, when ``frames()`` reaches it. Each length is checked against the
bytes left before the record is read: on a stream whose size is known (a
regular file, ``io.BytesIO``; the size when the capture was opened) a
corrupt length is an error without a read, and on another one (a pipe) the
record is read in chunks, so a corrupt length never allocates what it
claims.

Classic pcap: the four magic numbers (microsecond and nanosecond time
stamps, either byte order); the link type is the low 16 bits of the
header's ``network`` field. pcapng: section header, interface description,
enhanced, simple and (obsolete) packet blocks; other blocks are skipped,
and a new section header starts a new list of interfaces. Each frame's
time stamp is in nanoseconds since the epoch: classic pcap's microseconds or
nanoseconds (by its magic number); pcapng's in the units of its interface's
``if_tsresol`` (microseconds by default), plus its ``if_tsoffset`` seconds; a
simple packet block has none (0).
"""

from __future__ import annotations

import io
import struct
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Protocol

__all__ = ["Capture", "Frame", "PcapError", "Readable", "read", "read_stream"]

_PCAP_MAGIC = {
    b"\xd4\xc3\xb2\xa1": "<",  # microseconds, little-endian
    b"\xa1\xb2\xc3\xd4": ">",
    b"\x4d\x3c\xb2\xa1": "<",  # nanoseconds
    b"\xa1\xb2\x3c\x4d": ">",
}
_PCAP_NANO = (b"\x4d\x3c\xb2\xa1", b"\xa1\xb2\x3c\x4d")
_PCAP_HEADER = 24
_PCAP_RECORD = 16

_SHB_MAGIC = b"\x0a\x0d\x0d\x0a"
_SHB_HEADER = 28  # type, length, byte-order magic, version, section length, length
_BLOCK_HEADER = 12  # type, length and the trailing length
_IDB = 0x00000001
_PB = 0x00000002
_SPB = 0x00000003
_EPB = 0x00000006
_BYTE_ORDER_MAGIC = 0x1A2B3C4D
#: Interface description block options: the time stamp resolution and offset.
_OPT_END = 0
_IF_TSRESOL = 9
_IF_TSOFFSET = 14
#: Time stamp units per second without if_tsresol (microseconds).
_DEFAULT_UNITS = 1_000_000
_NANO = 1_000_000_000

#: The largest single read from a stream.
_CHUNK = 1 << 20


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
    (a LINKTYPE_* value), the captured ``data``, the ``original`` length
    of the packet on the wire (``len(data)`` when it was not cut) and its
    ``timestamp`` in nanoseconds since the epoch (0 when the record has
    none)."""

    number: int
    linktype: int
    data: bytes
    original: int
    timestamp: int = 0

    @property
    def truncated(self) -> bool:
        """Whether the capture cut the packet (its snap length)."""
        return len(self.data) < self.original


class Readable(Protocol):
    """What ``read_stream`` reads: a binary file, ``io.BytesIO``, a pipe.
    ``seekable``, ``tell`` and ``seek`` tell its size when it can seek."""

    def read(self, size: int = -1, /) -> bytes | None: ...
    def seekable(self) -> bool: ...
    def tell(self) -> int: ...
    def seek(self, offset: int, whence: int = 0, /) -> int: ...


class _Short(Exception):
    """Fewer bytes are left than a read needs: ``left`` of them."""

    def __init__(self, left: int) -> None:
        super().__init__(left)
        self.left = left


class _Source:
    """A binary stream read in exact amounts; ``pos`` is the offset of the
    next byte from where the stream was when the capture was opened."""

    def __init__(self, stream: Readable) -> None:
        self._stream = stream
        self._end = _size(stream)
        self.pos = 0

    def left(self) -> int | None:
        """The bytes left, ``None`` when the stream's size is unknown."""
        return None if self._end is None else self._end - self.pos

    def take(self, n: int) -> bytes:
        """The next ``n`` bytes; ``_Short`` when fewer are left (then, with a
        known size, nothing is read)."""
        left = self.left()
        if left is not None and n > left:
            raise _Short(left)
        chunks = []
        got = 0
        while got < n:
            chunk = self._stream.read(min(n - got, _CHUNK))
            if not chunk:
                break
            chunks.append(chunk)
            got += len(chunk)
        self.pos += got
        if got < n:
            raise _Short(got)
        return chunks[0] if len(chunks) == 1 else b"".join(chunks)


def _size(stream: Readable) -> int | None:
    """The bytes from the stream's position to its end, when it can seek."""
    try:
        if not stream.seekable():
            return None
        here = stream.tell()
        end = stream.seek(0, io.SEEK_END)
        stream.seek(here)
    except (OSError, ValueError):
        return None
    return max(end - here, 0)


class Capture:
    """A capture file: ``format`` is ``pcap`` or ``pcapng``. It reads its
    stream, which must stay open until ``frames()`` is consumed."""

    def __init__(self, fmt: str, source: _Source, header: bytes) -> None:
        self.format = fmt
        self._source = source
        self._header = header
        self._started = False

    def frames(self) -> Iterator[Frame]:
        """Every packet record, in file order; ``PcapError`` on a broken one.
        It reads the stream: a capture's frames can be taken once."""
        if self._started:
            raise RuntimeError("the frames of a capture can be read once")
        self._started = True
        if self.format == "pcap":
            return _pcap_frames(self._source, self._header)
        return _pcapng_frames(self._source, self._header)


def read(data: bytes) -> Capture:
    """The capture of ``data``; ``PcapError`` when it is neither format."""
    return read_stream(io.BytesIO(data))


def read_stream(stream: Readable) -> Capture:
    """The capture of a binary ``stream``, from its position; ``PcapError``
    when it is neither format. Only the file header is read here."""
    source = _Source(stream)
    try:
        magic = source.take(4)
    except _Short:
        raise PcapError("not a pcap or pcapng file (unknown magic number)", 0) from None
    if magic in _PCAP_MAGIC:
        try:
            rest = source.take(_PCAP_HEADER - 4)
        except _Short as short:
            raise PcapError(
                f"the pcap file header is {_PCAP_HEADER} bytes, the file has {4 + short.left}", 0
            ) from None
        return Capture("pcap", source, magic + rest)
    if magic == _SHB_MAGIC:
        header = _section_header(source, magic, 0)
        return Capture("pcapng", source, header)
    raise PcapError("not a pcap or pcapng file (unknown magic number)", 0)


def _pcap_frames(source: _Source, header: bytes) -> Iterator[Frame]:
    order = _PCAP_MAGIC[header[:4]]
    linktype = struct.unpack_from(order + "I", header, 20)[0] & 0xFFFF
    fraction = 1 if header[:4] in _PCAP_NANO else 1000  # nanoseconds per unit
    number = 0
    while True:
        pos = source.pos
        try:
            record = source.take(_PCAP_RECORD)
        except _Short as short:
            if short.left == 0:
                return
            raise PcapError(
                f"a truncated record header ({short.left} of {_PCAP_RECORD} bytes)", pos
            ) from None
        seconds, units, caplen, original = struct.unpack_from(order + "IIII", record, 0)
        try:
            data = source.take(caplen)
        except _Short as short:
            raise PcapError(
                f"a record of {caplen} bytes, but only {short.left} bytes are left", pos
            ) from None
        number += 1
        yield Frame(
            number, linktype, data, max(original, caplen), seconds * _NANO + units * fraction
        )


def _section_header(source: _Source, head: bytes, pos: int) -> bytes:
    """The first ``_SHB_HEADER`` bytes of the section header block at
    ``pos``, of which ``head`` was read; its byte order is checked."""
    try:
        head += source.take(_SHB_HEADER - len(head))
    except _Short:
        raise PcapError("a truncated pcapng section header block", pos) from None
    _section_order(head, pos)
    return head


def _section_order(head: bytes, pos: int) -> str:
    """The byte order of the section header block starting with ``head``."""
    for order in ("<", ">"):
        if struct.unpack_from(order + "I", head, 8)[0] == _BYTE_ORDER_MAGIC:
            return order
    raise PcapError("a pcapng section header block without its byte-order magic", pos)


def _pcapng_frames(source: _Source, first: bytes) -> Iterator[Frame]:
    order = "<"
    # Per interface; reset by each section header.
    interfaces: list[_Interface] = []
    number = 0
    pos, head = 0, first  # the section header that read_stream checked
    while True:
        if head[:4] == _SHB_MAGIC:
            order = _section_order(head, pos)
            interfaces = []
        kind, length = struct.unpack_from(order + "II", head, 0)
        left = source.left()
        whole = None if left is None else left + len(head)  # from the block's start
        if length < _BLOCK_HEADER or length % 4 or (whole is not None and length > whole):
            raise PcapError(_bad_length(length, whole), pos)
        if length < len(head):
            # A section header block shorter than its fixed fields.
            raise PcapError("a truncated pcapng section header block", pos)
        try:
            block = head + source.take(length - len(head))
        except _Short as short:
            raise PcapError(_bad_length(length, len(head) + short.left), pos) from None
        if struct.unpack_from(order + "I", block, length - 4)[0] != length:
            raise PcapError("a pcapng block whose two lengths differ", pos)
        body = block[8:-4]
        if kind == _IDB:
            if len(body) < 8:
                raise PcapError("a truncated pcapng interface description block", pos)
            linktype, _, snaplen = struct.unpack_from(order + "HHI", body, 0)
            units, offset = _time_options(body[8:], order)
            interfaces.append(_Interface(linktype, snaplen, units, offset))
        elif kind in (_EPB, _PB, _SPB):
            number += 1
            yield _packet(kind, body, order, interfaces, number, pos)
        pos = source.pos
        next_head = _block_head(source, pos)
        if next_head is None:
            return
        head = next_head


def _block_head(source: _Source, pos: int) -> bytes | None:
    """The start of the block at ``pos``: its type and length and 4 more
    bytes (all of a section header's fixed fields), ``None`` at the end."""
    try:
        head = source.take(_BLOCK_HEADER)
    except _Short as short:
        if short.left == 0:
            return None
        raise PcapError(f"a truncated pcapng block ({short.left} bytes)", pos) from None
    if head[:4] == _SHB_MAGIC:
        head = _section_header(source, head, pos)
    return head


def _bad_length(length: int, left: int | None) -> str:
    if left is None:
        return f"a pcapng block of length {length}"
    return f"a pcapng block of length {length} ({left} bytes are left)"


@dataclass(frozen=True)
class _Interface:
    """A pcapng interface: its link type, snap length, time stamp units per
    second and time stamp offset (seconds)."""

    linktype: int
    snaplen: int
    units: int = _DEFAULT_UNITS
    offset: int = 0

    def nanoseconds(self, stamp: int) -> int:
        """A time stamp of this interface, in nanoseconds since the epoch."""
        return self.offset * _NANO + stamp * _NANO // self.units


def _time_options(options: bytes, order: str) -> tuple[int, int]:
    """``if_tsresol`` (as units per second) and ``if_tsoffset`` of an
    interface description block's options; the defaults when absent. An
    option list cut short ends there (the options are not needed to read
    the packets)."""
    units, offset = _DEFAULT_UNITS, 0
    at = 0
    while at + 4 <= len(options):
        code, length = struct.unpack_from(order + "HH", options, at)
        value = options[at + 4 : at + 4 + length]
        if code == _OPT_END or len(value) < length:
            break
        if code == _IF_TSRESOL and length >= 1:
            exponent = value[0] & 0x7F
            units = 2**exponent if value[0] & 0x80 else 10**exponent
        elif code == _IF_TSOFFSET and length >= 8:
            offset = struct.unpack_from(order + "q", value, 0)[0]
        at += 4 + (length + 3) // 4 * 4
    return max(units, 1), offset


def _packet(
    kind: int, body: bytes, order: str, interfaces: list[_Interface], number: int, pos: int
) -> Frame:
    if kind == _SPB:
        if len(body) < 4:
            raise PcapError("a truncated pcapng simple packet block", pos)
        iface = 0
        original = struct.unpack_from(order + "I", body, 0)[0]
        start = 4
        if not interfaces:
            raise PcapError("a simple packet block before any interface description", pos)
        snaplen = interfaces[0].snaplen
        stamp = None
        caplen = min(original, len(body) - start)
        if snaplen:
            caplen = min(caplen, snaplen)
    else:
        if kind == _EPB:
            if len(body) < 20:
                raise PcapError("a truncated pcapng enhanced packet block", pos)
            iface, high, low, caplen, original = struct.unpack_from(order + "IIIII", body, 0)
        else:
            if len(body) < 20:
                raise PcapError("a truncated pcapng packet block", pos)
            iface, _, high, low, caplen, original = struct.unpack_from(order + "HHIIII", body, 0)
        start = 20
        stamp = high << 32 | low
        if iface >= len(interfaces):
            raise PcapError(f"a packet of interface {iface}, which no block describes", pos)
        if caplen > len(body) - start:
            raise PcapError(
                f"a packet of {caplen} bytes in a block that holds {len(body) - start}", pos
            )
    interface = interfaces[iface]
    return Frame(
        number,
        interface.linktype,
        body[start : start + caplen],
        max(original, caplen),
        0 if stamp is None else interface.nanoseconds(stamp),
    )
