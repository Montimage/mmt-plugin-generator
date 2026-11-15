"""``mmt_plugin.pcap.reader``: classic pcap and pcapng, in both byte orders,
the files tcpdump and editcap write (``data/``), and the broken files that
are ``PcapError``."""

from __future__ import annotations

import struct
from pathlib import Path

import pytest

from mmt_plugin.pcap import Frame, PcapError, read

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
