"""``mmt_plugin.pcap.reader``: classic pcap and pcapng, in both byte orders,
the files tcpdump and editcap write (``data/``), the broken files that are
``PcapError``, and the streams ``read_stream`` reads record by record: never
past the last frame taken (#71), a pipe as a file, a corrupt length without
an allocation of its size."""

from __future__ import annotations

import io
import re
import struct
from pathlib import Path
from typing import Any

import pytest

from mmt_plugin.commands.init import parse_selector
from mmt_plugin.pcap import Frame, Parent, PcapError, parent_of, read, read_stream, slice_payloads

from . import samples

DATA = Path(__file__).with_name("data")

FRAMES = [samples.udp4(50000, 4433, p) for p in samples.demo_payloads()]


def _frames(data: bytes) -> list[Frame]:
    return list(read(data).frames())


@pytest.mark.parametrize("big_endian", [False, True])
@pytest.mark.parametrize("nanoseconds", [False, True])
def test_pcap_in_both_byte_orders_and_time_resolutions(
    big_endian: bool, nanoseconds: bool
) -> None:
    capture = read(samples.pcap(FRAMES, big_endian=big_endian, nanoseconds=nanoseconds))
    assert capture.format == "pcap"
    frames = list(capture.frames())
    assert [(f.number, f.linktype, f.data, f.original) for f in frames] == [
        (i + 1, 1, frame, len(frame)) for i, frame in enumerate(FRAMES)
    ]
    assert not any(f.truncated for f in frames)


def test_pcap_records_cut_by_the_snap_length_are_truncated() -> None:
    (frame,) = _frames(samples.pcap(FRAMES[:1], snaplen=20))
    assert frame.data == FRAMES[0][:20]
    assert frame.original == len(FRAMES[0])
    assert frame.truncated


def test_pcap_link_type_is_the_low_16_bits() -> None:
    data = bytearray(samples.pcap(FRAMES[:1], samples.RAW))
    data[22:24] = b"\x00\x10"  # FCS bits above the link type
    assert _frames(bytes(data))[0].linktype == samples.RAW


@pytest.mark.parametrize("big_endian", [False, True])
@pytest.mark.parametrize("simple", [False, True])
def test_pcapng_enhanced_and_simple_packet_blocks(big_endian: bool, simple: bool) -> None:
    capture = read(samples.pcapng(FRAMES, big_endian=big_endian, simple=simple))
    assert capture.format == "pcapng"
    assert [(f.number, f.linktype, f.data) for f in capture.frames()] == [
        (i + 1, 1, frame) for i, frame in enumerate(FRAMES)
    ]


def test_pcapng_sections_reset_the_interfaces() -> None:
    first = samples.pcapng(FRAMES[:1])
    second = samples.pcapng(FRAMES[1:], samples.RAW, big_endian=True)
    frames = _frames(first + second)
    assert [(f.number, f.linktype) for f in frames] == [(1, 1), (2, samples.RAW), (3, samples.RAW)]


def test_pcapng_obsolete_packet_block() -> None:
    shb, idb = samples.pcapng([])[:28], samples.pcapng([])[28:48]
    frame = FRAMES[0]
    body = struct.pack("<HHIIII", 0, 0, 0, 0, len(frame), len(frame)) + frame
    body += b"\0" * (-len(body) % 4)
    block = struct.pack("<II", 2, 12 + len(body)) + body + struct.pack("<I", 12 + len(body))
    assert [f.data for f in _frames(shb + idb + block)] == [frame]


@pytest.mark.parametrize(
    ("name", "fmt"), [("demo-tcpdump.pcap", "pcap"), ("demo-editcap.pcapng", "pcapng")]
)
def test_files_written_by_tcpdump_and_editcap(name: str, fmt: str) -> None:
    # data/: the five frames of samples (three demo payloads to UDP port
    # 4433, a DNS and an ARP frame) rewritten by tcpdump -w and editcap -F
    # pcapng, which add their own header options.
    capture = read((DATA / name).read_bytes())
    assert capture.format == fmt
    frames = list(capture.frames())
    assert len(frames) == 5
    assert [f.data for f in frames[:3]] == FRAMES
    assert all(f.linktype == 1 for f in frames)


@pytest.mark.parametrize("big_endian", [False, True])
@pytest.mark.parametrize(("nanoseconds", "unit"), [(False, 1000), (True, 1)])
def test_pcap_time_stamps_are_nanoseconds_since_the_epoch(
    big_endian: bool, nanoseconds: bool, unit: int
) -> None:
    data = bytearray(samples.pcap(FRAMES[:2], big_endian=big_endian, nanoseconds=nanoseconds))
    order = ">" if big_endian else "<"
    struct.pack_into(order + "I", data, 24 + 4, 123456)  # the first record's fraction
    stamps = [f.timestamp for f in _frames(bytes(data))]
    assert stamps == [1700000000 * 10**9 + 123456 * unit, 1700000001 * 10**9]


def _pcapng_stamped(options: bytes, high: int, low: int, order: str = "<") -> bytes:
    """A pcapng section: an interface with ``options`` and one enhanced
    packet block stamped ``high``:``low``."""
    shb = samples.pcapng([], big_endian=order == ">")[:28]
    body = struct.pack(order + "HHI", 1, 0, 0) + options
    idb = (
        struct.pack(order + "II", 1, 12 + len(body))
        + body
        + struct.pack(order + "I", 12 + len(body))
    )
    frame = FRAMES[0]
    epb = struct.pack(order + "IIIII", 0, high, low, len(frame), len(frame)) + frame
    epb += b"\0" * (-len(epb) % 4)
    return (
        shb
        + idb
        + struct.pack(order + "II", 6, 12 + len(epb))
        + epb
        + struct.pack(order + "I", 12 + len(epb))
    )


def _option(code: int, value: bytes, order: str = "<") -> bytes:
    return struct.pack(order + "HH", code, len(value)) + value + b"\0" * (-len(value) % 4)


@pytest.mark.parametrize("order", ["<", ">"])
@pytest.mark.parametrize(
    ("options", "expected"),
    [
        # No if_tsresol: microseconds.
        (b"", 1_700_000_000_123_456_000),
        # if_tsresol 9: nanoseconds; a comment option before it is skipped.
        (b"comment!" + b"tsresol9", 1_700_000_000_123_456_789),
        # if_tsresol 0x83: 2^-3 seconds.
        (b"tsresol-2", 1_700_000_000_125_000_000),
        # if_tsoffset 100 seconds, microseconds.
        (b"tsoffset", 1_700_000_100_123_456_000),
    ],
)
def test_pcapng_time_stamps_follow_the_interface_options(
    order: str, options: bytes, expected: int
) -> None:
    built = b""
    if options.startswith(b"comment!"):
        built += _option(1, b"a comment", order)
    if options.endswith(b"tsresol9"):
        built += _option(9, b"\x09", order)
        stamp = 1_700_000_000_123_456_789
    elif options == b"tsresol-2":
        built += _option(9, b"\x83", order)
        stamp = 1_700_000_000 * 8 + 1
    else:
        stamp = 1_700_000_000_123_456
    if options == b"tsoffset":
        built += _option(14, struct.pack(order + "q", 100), order)
    built += struct.pack(order + "HH", 0, 0)  # opt_endofopt
    data = _pcapng_stamped(built, stamp >> 32, stamp & 0xFFFFFFFF, order)
    assert [f.timestamp for f in _frames(data)] == [expected]


def test_a_simple_packet_block_has_no_time_stamp() -> None:
    assert [f.timestamp for f in _frames(samples.pcapng(FRAMES[:1], simple=True))] == [0]


def test_tcpdump_and_editcap_files_have_the_same_time_stamps() -> None:
    # demo-editcap.pcapng is demo-tcpdump.pcap rewritten by editcap (its
    # interface has no if_tsresol: microseconds, as the pcap's records).
    pcap = [f.timestamp for f in read((DATA / "demo-tcpdump.pcap").read_bytes()).frames()]
    pcapng = [f.timestamp for f in read((DATA / "demo-editcap.pcapng").read_bytes()).frames()]
    assert pcap == pcapng
    assert pcap == [(1_700_000_000 + i) * 10**9 for i in range(5)]


@pytest.mark.parametrize(
    ("data", "message"),
    [
        (b"", "not a pcap or pcapng file"),
        (b"GIF89a" + bytes(40), "not a pcap or pcapng file"),
        (b"\xd4\xc3\xb2\xa1" + bytes(10), "the pcap file header is 24 bytes"),
        (b"\x0a\x0d\x0d\x0a" + bytes(10), "a truncated pcapng section header block"),
        (b"\x0a\x0d\x0d\x0a" + bytes(24), "without its byte-order magic"),
    ],
)
def test_not_a_capture(data: bytes, message: str) -> None:
    with pytest.raises(PcapError, match=message) as info:
        read(data)
    assert info.value.offset == 0


def test_a_truncated_pcap_record_is_an_error_where_it_starts() -> None:
    data = samples.pcap(FRAMES)
    with pytest.raises(PcapError, match="only 10 bytes are left") as info:
        _frames(data[: -(len(FRAMES[2]) - 10)])
    assert info.value.offset == len(data) - len(FRAMES[2]) - 16
    with pytest.raises(PcapError, match="a truncated record header"):
        _frames(data + b"\0\0\0")


def test_records_before_the_break_are_read() -> None:
    frames = read(samples.pcap(FRAMES)[:-5]).frames()
    assert next(frames).number == 1
    assert next(frames).number == 2
    with pytest.raises(PcapError):
        next(frames)


def _epb(frame: bytes, iface: int = 0, caplen: int | None = None) -> bytes:
    body = struct.pack("<IIIII", iface, 0, 0, len(frame) if caplen is None else caplen, len(frame))
    body += frame + b"\0" * (-len(frame) % 4)
    return struct.pack("<II", 6, 12 + len(body)) + body + struct.pack("<I", 12 + len(body))


@pytest.mark.parametrize(
    ("tail", "message"),
    [
        (b"\x06\0\0\0", "a truncated pcapng block"),
        (struct.pack("<II", 6, 13) + bytes(8), "a pcapng block of length 13"),
        (struct.pack("<II", 6, 400) + bytes(8), "a pcapng block of length 400"),
        (struct.pack("<III", 6, 12, 16), "whose two lengths differ"),
        (struct.pack("<III", 6, 12, 12), "a truncated pcapng enhanced packet block"),
        (_epb(FRAMES[0], iface=1), "a packet of interface 1, which no block describes"),
        (_epb(FRAMES[0], caplen=200), "a packet of 200 bytes in a block that holds"),
    ],
)
def test_broken_pcapng_blocks(tail: bytes, message: str) -> None:
    head = samples.pcapng([])
    with pytest.raises(PcapError, match=message) as info:
        _frames(head + tail)
    assert info.value.offset == len(head)


def test_a_simple_packet_block_needs_an_interface() -> None:
    shb = samples.pcapng([])[:28]
    body = struct.pack("<I", 4) + b"abcd"
    block = struct.pack("<II", 3, 12 + len(body)) + body + struct.pack("<I", 12 + len(body))
    with pytest.raises(PcapError, match="before any interface description"):
        _frames(shb + block)


class _Stream(io.RawIOBase):
    """A capture read through ``read_stream``: ``seekable`` or not (a pipe),
    returning at most ``step`` bytes a read, and failing the test on a read
    that would go past byte ``limit`` or ask for more than ``largest``."""

    def __init__(
        self,
        data: bytes,
        *,
        seekable: bool = True,
        step: int | None = None,
        limit: int | None = None,
        largest: int | None = None,
    ) -> None:
        super().__init__()
        self._data = data
        self._seekable = seekable
        self._step = step
        self._limit = len(data) if limit is None else limit
        self._largest = largest
        self.at = 0

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return self._seekable

    def seek(self, offset: int, whence: int = io.SEEK_SET) -> int:
        if not self._seekable:
            raise io.UnsupportedOperation("seek")
        base = {io.SEEK_SET: 0, io.SEEK_CUR: self.at, io.SEEK_END: len(self._data)}[whence]
        self.at = base + offset
        return self.at

    def tell(self) -> int:
        return self.at

    def readinto(self, buffer: Any) -> int:
        n = len(buffer)
        assert self._largest is None or n <= self._largest, f"a read of {n} bytes"
        if self._step is not None:
            n = min(n, self._step)
        chunk = self._data[self.at : self.at + n]
        assert self.at + len(chunk) <= self._limit, f"a read past byte {self._limit}"
        buffer[: len(chunk)] = chunk
        self.at += len(chunk)
        return len(chunk)


def _udp(text: str) -> Parent:
    selector = parse_selector(text)
    return parent_of(selector.text, selector.proto, selector.keys)


@pytest.mark.parametrize("fmt", ["pcap", "pcapng"])
@pytest.mark.parametrize("seekable", [True, False])
def test_slicing_stops_reading_at_the_limit(fmt: str, seekable: bool) -> None:
    # Two payloads to port 4433 around a DNS frame, then frames the reader
    # must never reach: the stream fails the test on a read past the
    # record of the second payload (the end of the third frame).
    frames = [FRAMES[0], samples.udp4(53, 53, b"dns"), FRAMES[1], FRAMES[2]]
    build = samples.pcap if fmt == "pcap" else samples.pcapng
    limit = len(build(frames[:3]))
    data = build(frames) + b"garbage past the limit"
    stream = _Stream(data, seekable=seekable, limit=limit)
    slicing = slice_payloads(read_stream(stream).frames(), _udp("udp:port=4433"), 2)
    assert [p.frame for p in slicing.payloads] == [1, 3]
    assert slicing.frames == 3
    assert stream.at == limit


@pytest.mark.parametrize("seekable", [True, False])
def test_the_stream_is_read_from_its_position(seekable: bool) -> None:
    data = b"prefix" + samples.pcap(FRAMES)
    stream = _Stream(data, seekable=seekable, step=7)
    stream.read(6)
    assert [f.data for f in read_stream(stream).frames()] == FRAMES


@pytest.mark.parametrize("seekable", [True, False])
def test_a_corrupt_length_is_not_read_in_one_allocation(seekable: bool) -> None:
    # A pcap record and a pcapng block claiming almost 4 GiB: with a known
    # size it is an error without a read, otherwise it is read in chunks.
    record = struct.pack("<IIII", 0, 0, 0xFFFFFFF0, 0xFFFFFFF0) + bytes(100)
    data = samples.pcap([]) + record
    with pytest.raises(PcapError, match="a record of 4294967280 bytes, but only 100") as info:
        list(read_stream(_Stream(data, seekable=seekable, largest=1 << 20)).frames())
    assert info.value.offset == 24
    head = samples.pcapng([])
    block = struct.pack("<II", 6, 0xFFFFFFF0) + bytes(100)
    with pytest.raises(PcapError, match=r"length 4294967280 \(108 bytes are left\)") as info:
        list(read_stream(_Stream(head + block, seekable=seekable, largest=1 << 20)).frames())
    assert info.value.offset == len(head)


@pytest.mark.parametrize(
    ("tail", "message"),
    [
        (b"\x06\0\0\0", r"a truncated pcapng block \(4 bytes\)"),
        (struct.pack("<II", 6, 13) + bytes(8), r"a pcapng block of length 13$"),
        (struct.pack("<II", 6, 400) + bytes(8), r"length 400 \(16 bytes are left\)"),
        (struct.pack("<III", 6, 12, 16), "whose two lengths differ"),
        (_epb(FRAMES[0], caplen=200), "a packet of 200 bytes in a block that holds"),
        (b"\x0a\x0d\x0d\x0a" + bytes(20), "a truncated pcapng section header block"),
    ],
)
def test_broken_pcapng_blocks_through_a_pipe(tail: bytes, message: str) -> None:
    # A pipe's size is unknown: a length that is wrong in itself is said
    # without the bytes left, a short block with what was read.
    head = samples.pcapng([])
    stream = _Stream(head + tail, seekable=False, step=5)
    with pytest.raises(PcapError) as info:
        list(read_stream(stream).frames())
    assert re.search(message, info.value.message)
    assert info.value.offset == len(head)


@pytest.mark.parametrize(
    ("data", "message"),
    [
        (b"\xd4\xc3", "not a pcap or pcapng file"),
        (b"\xd4\xc3\xb2\xa1" + bytes(10), "the pcap file header is 24 bytes, the file has 14"),
        (samples.pcap(FRAMES)[:-10], "only "),
    ],
)
def test_broken_pcap_through_a_pipe(data: bytes, message: str) -> None:
    with pytest.raises(PcapError, match=message):
        list(read_stream(_Stream(data, seekable=False, step=3)).frames())


def test_a_section_header_shorter_than_its_fields_is_an_error() -> None:
    shb = samples.pcapng([])[:28]
    short = struct.pack("<III", 0x0A0D0D0A, 24, 0x1A2B3C4D) + bytes(8) + struct.pack("<I", 24)
    with pytest.raises(PcapError, match="a truncated pcapng section header block") as info:
        _frames(shb + short + bytes(8))
    assert info.value.offset == 28


def test_the_frames_of_a_capture_are_read_once() -> None:
    capture = read(samples.pcap(FRAMES))
    assert len(list(capture.frames())) == 3
    with pytest.raises(RuntimeError, match="read once"):
        capture.frames()
