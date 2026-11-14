"""The random and truncated packets of ``mmt-plugin test --sanitize``.

``fuzz_packets(seed, test_id, data, count)`` returns ``count`` packets made
from one packet test's bytes: first its truncations (every prefix shorter
than the packet, shortest first, as many as ``count`` allows), then random
packets, each one of three kinds: random bytes of a random length (up to
twice the packet, at least 64 bytes), the packet with one to four bytes
replaced, and a prefix of the packet followed by random bytes.

The generator is seeded from ``seed`` and the test id through SHA-256, and
draws only ``random.Random.getrandbits``, whose output for an integer seed
is the same on every Python version: the same seed gives the same packets,
on every run and every machine.
"""

from __future__ import annotations

import hashlib
import random

__all__ = ["fuzz_packets"]

#: The longest random packet is at least this long.
_MIN_RANDOM = 64


def _below(rng: random.Random, n: int) -> int:
    """An integer in ``[0, n)`` from ``getrandbits`` alone (rejection)."""
    if n <= 1:
        return 0
    bits = (n - 1).bit_length()
    while True:
        value = rng.getrandbits(bits)
        if value < n:
            return value


def _random_bytes(rng: random.Random, n: int) -> bytes:
    return bytes(rng.getrandbits(8) for _ in range(n))


def fuzz_packets(seed: int, test_id: str, data: bytes, count: int) -> list[bytes]:
    """``count`` truncated and random packets for the test ``test_id``."""
    digest = hashlib.sha256(f"{seed}\0{test_id}".encode()).digest()
    rng = random.Random(int.from_bytes(digest[:8], "big"))
    out = [data[:n] for n in range(min(len(data), count))]
    longest = max(_MIN_RANDOM, 2 * len(data))
    while len(out) < count:
        kind = _below(rng, 3)
        if kind == 1 and data:
            packet = bytearray(data)
            for _ in range(1 + _below(rng, 4)):
                packet[_below(rng, len(packet))] = rng.getrandbits(8)
            out.append(bytes(packet))
        elif kind == 2 and data:
            keep = _below(rng, len(data) + 1)
            out.append(data[:keep] + _random_bytes(rng, _below(rng, longest - keep + 1)))
        else:
            out.append(_random_bytes(rng, _below(rng, longest + 1)))
    return out
