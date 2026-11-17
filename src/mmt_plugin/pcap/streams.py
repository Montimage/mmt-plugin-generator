"""Following TCP streams under a ``tcp`` parent (#102).

``TcpStreams`` takes the segments ``slice_payloads`` finds under a ``tcp``
parent, in capture order, and gives back each segment's new bytes in the
order of its direction's stream (a direction is a source address and port
to a destination address and port), so a payload is one segment's bytes,
never bytes sent twice:

- a segment's place is its sequence number, from the direction's SYN (its
  initial sequence number plus 1) or, when the capture has no SYN for it,
  from the first segment seen; numbers wrap modulo 2**32;
- bytes the stream already delivered are cut off (``Payload.cut`` counts
  them); a segment with no new byte is skipped as ``retransmission``;
- a segment after missing bytes waits until they come. More than
  ``MAX_WAITING`` waiting in a direction gives it up: those segments, and
  every later one of the direction until a new SYN, are skipped as ``gap``
  (where a message starts after lost bytes is unknown), as are the ones
  still waiting when the capture ends;
- a SYN with another initial sequence number starts a new session on the
  same addresses and ports (the old one's waiting segments are ``gap``);
- with ``skip_until`` (a byte pattern), each direction's bytes of each
  session up to the end of the pattern's first occurrence, found across
  segments, are skipped: a segment with no byte after it is skipped as
  ``skip-until``, and the segment where it ends gives the bytes after it.
  A direction that never sends the pattern gives nothing.

A segment with no data (a SYN, an ACK) is skipped as ``empty``. Messages
are not split or joined: a payload is what one segment carries, whatever
the protocol's framing (that needs its length rule).
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mmt_plugin.pcap.layers import Flow, Payload

__all__ = ["MAX_WAITING", "TcpStreams"]

#: The most segments a direction holds after missing bytes.
MAX_WAITING = 64

_MOD = 1 << 32
_HALF = 1 << 31
_SYN = 0x02


@dataclass
class _Waiting:
    start: int
    payload: Payload


@dataclass
class _Direction:
    skipping: bool
    isn: int | None = None
    next: int | None = None
    waiting: list[_Waiting] = field(default_factory=list)
    tail: bytes = b""
    lost: bool = False


class TcpStreams:
    """The streams of a slicing: ``segment`` counts each segment it skips in
    ``skipped`` (by reason) and returns the payloads now in stream order;
    ``finish`` counts the segments still waiting."""

    def __init__(self, skipped: dict[str, int], skip_until: bytes | None = None) -> None:
        if skip_until is not None and not skip_until:
            raise ValueError("skip_until is an empty pattern")
        self._skipped = skipped
        self._skip_until = skip_until
        self._directions: dict[Flow, _Direction] = {}

    def _new(self) -> _Direction:
        return _Direction(skipping=self._skip_until is not None)

    def _drop_waiting(self, direction: _Direction) -> None:
        self._skipped["gap"] += len(direction.waiting)
        direction.waiting.clear()

    def segment(self, payload: Payload, seq: int, flags: int) -> list[Payload]:
        """The payloads ``payload`` (one segment of its ``flow``, at ``seq``
        with the TCP ``flags``) puts in stream order: none, its own new
        bytes, then those of the waiting segments it joins."""
        assert payload.flow is not None
        direction = self._directions.get(payload.flow)
        if direction is None:
            direction = self._directions[payload.flow] = self._new()
        start = seq
        if flags & _SYN:
            if direction.isn != seq:  # the first SYN, or a new session
                self._drop_waiting(direction)
                direction = self._directions[payload.flow] = self._new()
                direction.isn = seq
                direction.next = (seq + 1) % _MOD
            start = (seq + 1) % _MOD
        if not payload.data:
            self._skipped["empty"] += 1
            return []
        if direction.lost:
            self._skipped["gap"] += 1
            return []
        if direction.next is None:
            direction.next = start
        out: list[Payload] = []
        if not self._place(direction, _Waiting(start, payload), out):
            if len(direction.waiting) >= MAX_WAITING:
                self._drop_waiting(direction)
                self._skipped["gap"] += 1
                direction.lost = True
                return out
            direction.waiting.append(_Waiting(start, payload))
            return out
        while True:
            ready = next(
                (
                    w
                    for w in direction.waiting
                    if (w.start - (direction.next or 0)) % _MOD == 0
                    or (w.start - (direction.next or 0)) % _MOD >= _HALF
                ),
                None,
            )
            if ready is None:
                return out
            direction.waiting.remove(ready)
            self._place(direction, ready, out)

    def _place(self, direction: _Direction, segment: _Waiting, out: list[Payload]) -> bool:
        """Deliver ``segment`` if it starts at or before the next byte
        expected (``True``); ``False`` when it must wait."""
        assert direction.next is not None
        payload = segment.payload
        ahead = (segment.start - direction.next) % _MOD
        if 0 < ahead < _HALF:
            return False
        if ahead:  # it starts before the next byte: some were delivered
            overlap = _MOD - ahead
            if overlap >= len(payload.data):
                self._skipped["retransmission"] += 1
                return True
            payload = dataclasses.replace(
                payload, data=payload.data[overlap:], cut=payload.cut + overlap
            )
        direction.next = (direction.next + len(payload.data)) % _MOD
        self._deliver(direction, payload, out)
        return True

    def _deliver(self, direction: _Direction, payload: Payload, out: list[Payload]) -> None:
        pattern = self._skip_until
        if direction.skipping:
            assert pattern is not None
            buffer = direction.tail + payload.data
            at = buffer.find(pattern)
            if at < 0:
                # The bytes a match across the next segment could start with.
                direction.tail = buffer[max(0, len(buffer) - len(pattern) + 1) :]
                self._skipped["skip-until"] += 1
                return
            cut = at + len(pattern) - len(direction.tail)
            direction.skipping = False
            direction.tail = b""
            if cut >= len(payload.data):
                self._skipped["skip-until"] += 1
                return
            payload = dataclasses.replace(payload, data=payload.data[cut:], cut=payload.cut + cut)
        out.append(payload)

    def finish(self) -> None:
        """Count the segments still waiting after missing bytes as ``gap``."""
        for direction in self._directions.values():
            self._drop_waiting(direction)
