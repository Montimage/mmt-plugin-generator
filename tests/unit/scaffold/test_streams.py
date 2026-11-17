"""``mmt_plugin.pcap.streams``: TCP segments in their stream's order, with
retransmissions dropped, gaps given up, sessions restarted on a new SYN and
each direction's first exchange skipped by ``--skip-until`` (#102)."""

from __future__ import annotations

import pytest

from mmt_plugin.commands.init import parse_selector
from mmt_plugin.pcap import SKIP_REASONS, Parent, Payload, parent_of, read, slice_payloads
from mmt_plugin.pcap.streams import MAX_WAITING, TcpStreams

from . import samples

A = ("ip", 1, 50000, 2, 80)
B = ("ip", 2, 80, 1, 50000)
SYN = 0x02
ACK = 0x10


class Run:
    """Segments fed to a ``TcpStreams``: what each frame gave."""

    def __init__(self, skip_until: bytes | None = None) -> None:
        self.skipped = dict.fromkeys(SKIP_REASONS, 0)
        self.streams = TcpStreams(self.skipped, skip_until)
        self.frame = 0
        self.out: list[Payload] = []

    def send(
        self, flow: tuple[str, int, int, int, int], seq: int, data: bytes, flags: int = ACK
    ) -> list[bytes]:
        self.frame += 1
        got = self.streams.segment(Payload(self.frame, ("ip", "tcp"), data, flow), seq, flags)
        self.out += got
        return [p.data for p in got]

    def counts(self) -> dict[str, int]:
        return {k: v for k, v in self.skipped.items() if v}


def test_segments_in_order_from_the_syn() -> None:
    run = Run()
    assert run.send(A, 100, b"", SYN) == []
    assert run.send(A, 101, b"abc") == [b"abc"]
    assert run.send(A, 104, b"de") == [b"de"]
    assert run.counts() == {"empty": 1}
    assert [p.frame for p in run.out] == [2, 3]


def test_out_of_order_segments_wait_for_the_missing_bytes() -> None:
    run = Run()
    run.send(A, 100, b"", SYN)
    assert run.send(A, 104, b"de") == []
    assert run.send(A, 106, b"f") == []
    assert run.send(A, 101, b"abc") == [b"abc", b"de", b"f"]
    assert [p.frame for p in run.out] == [4, 2, 3]
    run.streams.finish()
    assert run.counts() == {"empty": 1}


def test_retransmissions_are_dropped_and_overlaps_cut() -> None:
    run = Run()
    run.send(A, 101, b"abc")  # no SYN: the stream starts here
    assert run.send(A, 101, b"abc") == []
    assert run.send(A, 102, b"bcde") == [b"de"]
    assert run.out[-1].cut == 2
    assert run.send(A, 50, b"old") == []  # before the stream's start
    assert run.counts() == {"retransmission": 2}


def test_directions_are_followed_apart() -> None:
    run = Run()
    run.send(A, 100, b"", SYN)
    run.send(B, 900, b"", SYN | ACK)
    assert run.send(B, 901, b"xy") == [b"xy"]
    assert run.send(A, 101, b"ab") == [b"ab"]
    assert {p.flow for p in run.out} == {A, B}


def test_sequence_numbers_wrap() -> None:
    run = Run()
    run.send(A, 0xFFFFFFFE, b"", SYN)
    assert run.send(A, 0xFFFFFFFF, b"ab") == [b"ab"]
    assert run.send(A, 1, b"cd") == [b"cd"]
    assert run.send(A, 0xFFFFFFFF, b"ab") == []
    assert run.counts() == {"empty": 1, "retransmission": 1}


def test_segments_still_waiting_at_the_end_are_a_gap() -> None:
    run = Run()
    run.send(A, 101, b"ab")
    run.send(A, 200, b"later")
    run.send(A, 300, b"later")
    run.streams.finish()
    assert run.counts() == {"gap": 2}


def test_a_direction_with_too_many_segments_waiting_is_given_up() -> None:
    run = Run()
    run.send(A, 100, b"", SYN)
    for i in range(MAX_WAITING):
        assert run.send(A, 200 + 10 * i, b"x") == []
    assert run.send(A, 5000, b"y") == []
    assert run.send(A, 101, b"too late") == []  # given up until a new SYN
    assert run.counts() == {"empty": 1, "gap": MAX_WAITING + 2}
    run.send(A, 7000, b"", SYN)
    assert run.send(A, 7001, b"new") == [b"new"]


def test_a_new_syn_starts_a_new_session() -> None:
    run = Run(b"\r\n\r\n")
    run.send(A, 100, b"", SYN)
    assert run.send(A, 101, b"GET / HTTP/1.1\r\n\r\nframe") == [b"frame"]
    run.send(A, 200, b"waits")
    assert run.send(A, 100, b"", SYN) == []  # the same SYN again: no new session
    assert run.send(A, 3000, b"", SYN) == []
    assert run.counts() == {"empty": 3, "gap": 1}
    # The new session skips its own first exchange again.
    assert run.send(A, 3001, b"GET") == []
    assert run.send(A, 3004, b" /\r\n") == []
    assert run.send(A, 3008, b"\r\nnext") == [b"next"]
    assert run.out[-1].cut == 2
    assert run.counts() == {"empty": 3, "gap": 1, "skip-until": 2}


@pytest.mark.parametrize("pattern", [b"\n", b"\r\n\r\n", b"--END--"])
def test_skip_until_finds_the_pattern_across_segments(pattern: bytes) -> None:
    stream = b"HELLO" + pattern + b"payload one" + pattern + b"two"
    for size in range(1, len(stream) + 1):
        run = Run(pattern)
        for start in range(0, len(stream), size):
            run.send(A, 1 + start, stream[start : start + size])
        assert b"".join(p.data for p in run.out) == b"payload one" + pattern + b"two", size
        assert all(p.cut + len(p.data) <= size for p in run.out)


def test_a_direction_without_the_pattern_gives_nothing() -> None:
    run = Run(b"\r\n\r\n")
    assert run.send(B, 1, b"no handshake here") == []
    assert run.counts() == {"skip-until": 1}


def test_an_empty_pattern_is_refused() -> None:
    with pytest.raises(ValueError, match="empty"):
        TcpStreams({}, b"")


def _parent(text: str) -> Parent:
    selector = parse_selector(text)
    return parent_of(selector.text, selector.proto, selector.keys)


def test_a_websocket_capture_after_its_handshake() -> None:
    capture = read(samples.websocket_capture())
    slicing = slice_payloads(capture.frames(), _parent("tcp:port=80"), 100, skip_until=b"\r\n\r\n")
    clients = samples.websocket_client_frames()
    servers = samples.websocket_server_frames()
    by_flow: dict[object, list[bytes]] = {}
    for p in slicing.payloads:
        by_flow.setdefault(p.flow, []).append(p.data)
    a, b = 0xC0000201, 0xC0000202  # samples.ipv4's addresses, both ways
    assert by_flow == {("ip", a, 50000, b, 80): clients, ("ip", a, 80, b, 50000): servers}
    assert {k: v for k, v in slicing.skipped.items() if v} == {
        "empty": 2,  # SYN, SYN-ACK
        "retransmission": 1,
        "skip-until": 1,  # the upgrade request
    }
    first = next(p for p in slicing.payloads if p.data == servers[0])
    assert first.cut == len(samples.WS_ANSWER)


def test_skip_until_needs_a_tcp_parent() -> None:
    with pytest.raises(ValueError, match="tcp parent"):
        slice_payloads([], _parent("udp"), 1, skip_until=b"x")


def test_reading_stops_at_the_limit() -> None:
    capture = read(samples.websocket_capture())
    slicing = slice_payloads(capture.frames(), _parent("tcp:port=80"), 3)
    assert len(slicing.payloads) == 3
    assert slicing.frames < 18
