"""Slicing a capture's payloads under a parent selector.

``parent_of(selector)`` checks a ``SELECTOR`` (``mmt_plugin.commands.init``,
``parse_selector``) against the parents this module decodes, and their keys:

- ``ethernet``, key ``ethertype`` (after any 802.1Q/802.1ad tags): the
  bytes after the Ethernet header and its tags;
- ``ip``, key ``proto`` (the IPv4 protocol number): after the IPv4 header
  and its options, up to its total length;
- ``ipv6``, key ``proto`` (the upper-layer next header): after the IPv6
  header and its extension headers;
- ``udp``, keys ``port`` (source or destination), ``sport``, ``dport``:
  after the UDP header, up to its length;
- ``tcp``, the same keys: after the TCP header and its options, one
  segment's new bytes in its stream's order (``mmt_plugin.pcap.streams``).

Every key given must hold. ``slice_payloads(capture, parent, limit)`` decodes
each frame (link types Ethernet, Linux cooked v1 and v2, BSD loopback and
raw IP) down to UDP or TCP, and keeps the payload of the first layer the
parent matches, until it has ``limit`` of them. A frame is skipped, and
counted under its reason, when the parent does not match (``no-match``),
its payload is empty (``empty``), it is an IP fragment (``fragment``: they
are not reassembled), a header is broken (``malformed``), or the capture
cut it (``truncated``), or its link type is not decoded
(``unsupported-link``); under ``tcp``, also when it carries no new byte
(``retransmission``), comes after bytes the capture lacks (``gap``) or
before the end of ``--skip-until``'s pattern (``skip-until``).
"""

from __future__ import annotations

import struct
from collections.abc import Iterable
from dataclasses import dataclass, field

from mmt_plugin.diagnostics import CliError
from mmt_plugin.pcap.reader import Frame
from mmt_plugin.pcap.streams import TcpStreams

__all__ = [
    "PARENTS",
    "SKIP_REASONS",
    "Flow",
    "Parent",
    "Payload",
    "Slicing",
    "parent_of",
    "slice_payloads",
]

#: The parents decoded, with their keys and each key's largest value.
PARENTS: dict[str, dict[str, int]] = {
    "ethernet": {"ethertype": 0xFFFF},
    "ip": {"proto": 0xFF},
    "ipv6": {"proto": 0xFF},
    "udp": {"port": 0xFFFF, "sport": 0xFFFF, "dport": 0xFFFF},
    "tcp": {"port": 0xFFFF, "sport": 0xFFFF, "dport": 0xFFFF},
}

#: Why a frame gives no payload, in the order the result reports them.
SKIP_REASONS = (
    "no-match",
    "empty",
    "fragment",
    "malformed",
    "truncated",
    "unsupported-link",
    "retransmission",
    "gap",
    "skip-until",
)

_ETHERNET = 1
_NULL = 0
_LOOP = 108
_RAW = (101, 228, 229)
_SLL = 113
_SLL2 = 276
_VLAN_TAGS = (0x8100, 0x88A8, 0x9100)
_IPV4 = 0x0800
_IPV6 = 0x86DD
_UDP = 17
_TCP = 6
_IPV6_OPTIONS = (0, 43, 60)  # hop-by-hop, routing, destination options
_IPV6_FRAGMENT = 44
_IPV6_AH = 51


@dataclass(frozen=True)
class Parent:
    """A decoded parent selector: ``proto`` and ``keys`` (name, value)."""

    text: str
    proto: str
    keys: tuple[tuple[str, int], ...]


def parent_of(text: str, proto: str, keys: Iterable[tuple[str, str]]) -> Parent:
    """The ``Parent`` of a parsed selector; ``CliError``
    ``usage.invalid-value`` for a parent or a key this module does not
    decode, or a value that is not a number in its range."""
    known = PARENTS.get(proto)
    if known is None:
        raise CliError(
            "usage.invalid-value",
            f"--parent {text!r}: scaffold slices payloads under "
            + ", ".join(PARENTS)
            + f" only, not {proto}",
            "pick the lowest of those protocols that carries yours, e.g. --parent udp:port=4433",
        )
    values: list[tuple[str, int]] = []
    for key, raw in keys:
        largest = known.get(key)
        if largest is None:
            raise CliError(
                "usage.invalid-value",
                f"--parent {text!r}: {proto} has no key {key!r} (keys: {', '.join(known)})",
                "for example --parent udp:port=4433 or --parent ethernet:ethertype=0x88b5",
            )
        try:
            value = int(raw, 0)
        except ValueError:
            value = -1
        if not 0 <= value <= largest:
            raise CliError(
                "usage.invalid-value",
                f"--parent {text!r}: {key}={raw} is not a number from 0 to {largest:#x}",
                "write it in decimal or 0x hex",
            )
        values.append((key, value))
    return Parent(text, proto, tuple(values))


#: A UDP or TCP payload's direction: the network layer's name, the source
#: address and port, the destination address and port.
Flow = tuple[str, int, int, int, int]


@dataclass(frozen=True)
class Payload:
    """A sliced payload: its ``frame`` number, the protocol ``path`` down to
    the parent (outermost first) and its bytes. Under UDP or TCP, ``flow``
    is its direction; ``cut`` counts the bytes of the frame's payload
    before ``data`` (a TCP segment's bytes delivered before, or before the
    end of ``--skip-until``'s pattern)."""

    frame: int
    path: tuple[str, ...]
    data: bytes
    flow: Flow | None = None
    cut: int = 0


@dataclass
class Slicing:
    """What ``slice_payloads`` found: the ``frames`` it read, the
    ``payloads`` it kept and the frames it ``skipped``, by reason."""

    frames: int = 0
    payloads: list[Payload] = field(default_factory=list)
    skipped: dict[str, int] = field(default_factory=lambda: dict.fromkeys(SKIP_REASONS, 0))


@dataclass(frozen=True)
class _Layer:
    name: str
    fields: dict[str, int]
    payload: bytes


class _Stop(Exception):
    """Decoding stopped: ``reason`` is ``malformed`` or ``fragment``."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def _u16(data: bytes, offset: int) -> int:
    value: int = struct.unpack_from(">H", data, offset)[0]
    return value


def _ethernet(data: bytes, layers: list[_Layer]) -> None:
    if len(data) < 14:
        raise _Stop("malformed")
    pos = 12
    tags = 0
    while _u16(data, pos) in _VLAN_TAGS:
        if len(data) < pos + 6:
            raise _Stop("malformed")
        pos += 4
        tags += 1
    ethertype = _u16(data, pos)
    layers.append(_Layer("ethernet", {"ethertype": ethertype}, data[pos + 2 :]))
    layers += [_Layer("8021q", {}, b"")] * tags
    _network(ethertype, data[pos + 2 :], layers)


def _network(ethertype: int, data: bytes, layers: list[_Layer]) -> None:
    if ethertype == _IPV4:
        _ipv4(data, layers)
    elif ethertype == _IPV6:
        _ipv6(data, layers)


def _ipv4(data: bytes, layers: list[_Layer]) -> None:
    if len(data) < 20 or data[0] >> 4 != 4:
        raise _Stop("malformed")
    ihl = (data[0] & 0x0F) * 4
    total = _u16(data, 2)
    if ihl < 20 or total < ihl or total > len(data):
        raise _Stop("malformed")
    if _u16(data, 6) & 0x3FFF:  # more fragments, or a fragment offset
        raise _Stop("fragment")
    proto = data[9]
    addresses = {
        "src": int.from_bytes(data[12:16], "big"),
        "dst": int.from_bytes(data[16:20], "big"),
    }
    layers.append(_Layer("ip", {"proto": proto, **addresses}, data[ihl:total]))
    _transport(proto, data[ihl:total], layers)


def _ipv6(data: bytes, layers: list[_Layer]) -> None:
    if len(data) < 40 or data[0] >> 4 != 6:
        raise _Stop("malformed")
    length = _u16(data, 4)
    if length == 0 or 40 + length > len(data):  # 0: a jumbogram
        raise _Stop("malformed")
    proto = data[6]
    addresses = {
        "src": int.from_bytes(data[8:24], "big"),
        "dst": int.from_bytes(data[24:40], "big"),
    }
    rest = data[40 : 40 + length]
    while proto in (*_IPV6_OPTIONS, _IPV6_FRAGMENT, _IPV6_AH):
        if len(rest) < 8:
            raise _Stop("malformed")
        if proto == _IPV6_FRAGMENT:
            if _u16(rest, 2) & 0xFFF9:  # a fragment offset, or more fragments
                raise _Stop("fragment")
            size = 8
        elif proto == _IPV6_AH:
            size = (rest[1] + 2) * 4
        else:
            size = (rest[1] + 1) * 8
        if size > len(rest):
            raise _Stop("malformed")
        proto, rest = rest[0], rest[size:]
    layers.append(_Layer("ipv6", {"proto": proto, **addresses}, rest))
    _transport(proto, rest, layers)


def _transport(proto: int, data: bytes, layers: list[_Layer]) -> None:
    if proto == _UDP:
        if len(data) < 8:
            raise _Stop("malformed")
        length = _u16(data, 4)
        if length < 8 or length > len(data):
            raise _Stop("malformed")
        ports = {"sport": _u16(data, 0), "dport": _u16(data, 2)}
        layers.append(_Layer("udp", ports, data[8:length]))
    elif proto == _TCP:
        if len(data) < 20:
            raise _Stop("malformed")
        offset = (data[12] >> 4) * 4
        if offset < 20 or offset > len(data):
            raise _Stop("malformed")
        fields = {
            "sport": _u16(data, 0),
            "dport": _u16(data, 2),
            "seq": struct.unpack_from(">I", data, 4)[0],
            "flags": data[13],
        }
        layers.append(_Layer("tcp", fields, data[offset:]))


def _link(frame: Frame, layers: list[_Layer]) -> bool:
    """Decode ``frame`` into ``layers``; ``False`` for a link type it does
    not decode."""
    data = frame.data
    if frame.linktype == _ETHERNET:
        _ethernet(data, layers)
    elif frame.linktype == _SLL:
        if len(data) < 16:
            raise _Stop("malformed")
        _network(_u16(data, 14), data[16:], layers)
    elif frame.linktype == _SLL2:
        if len(data) < 20:
            raise _Stop("malformed")
        _network(_u16(data, 0), data[20:], layers)
    elif frame.linktype in (_NULL, _LOOP):
        if len(data) < 4:
            raise _Stop("malformed")
        # The address family, in the capturing host's byte order (NULL) or
        # network order (LOOP): 2 is IPv4, 24, 28 and 30 are IPv6.
        family = {struct.unpack_from("<I", data)[0], struct.unpack_from(">I", data)[0]}
        if 2 in family:
            _ipv4(data[4:], layers)
        elif family & {24, 28, 30}:
            _ipv6(data[4:], layers)
    elif frame.linktype in _RAW:
        if not data:
            raise _Stop("malformed")
        version = data[0] >> 4
        if version == 4:
            _ipv4(data, layers)
        elif version == 6:
            _ipv6(data, layers)
        else:
            raise _Stop("malformed")
    else:
        return False
    return True


def _matches(layer: _Layer, parent: Parent) -> bool:
    if layer.name != parent.proto:
        return False
    for key, value in parent.keys:
        if key == "port":
            if value not in (layer.fields["sport"], layer.fields["dport"]):
                return False
        elif layer.fields[key] != value:
            return False
    return True


@dataclass(frozen=True)
class _Found:
    """A frame's payload under the parent, with its layer's ``fields``."""

    payload: Payload
    fields: dict[str, int]


def _reason(frame: Frame, parent: Parent) -> tuple[str, _Found | None]:
    """Why ``frame`` gives no payload, or ``""`` and its payload. Under a
    ``tcp`` parent, an empty segment is found too: ``TcpStreams`` reads its
    SYN flag, then counts it."""
    layers: list[_Layer] = []
    stopped = None
    try:
        if not _link(frame, layers):
            return "unsupported-link", None
    except _Stop as stop:
        stopped = stop.reason
    for i, layer in enumerate(layers):
        if _matches(layer, parent):
            if parent.proto == "ethernet" and frame.truncated:
                return "truncated", None
            if not layer.payload and parent.proto != "tcp":
                return "empty", None
            # The tags after an Ethernet header are part of its path.
            end = i + 1
            while end < len(layers) and layers[end].name == "8021q":
                end += 1
            path = tuple(x.name for x in layers[:end])
            flow: Flow | None = None
            if layer.name in ("udp", "tcp"):
                net = layers[i - 1]
                flow = (
                    net.name,
                    net.fields["src"],
                    layer.fields["sport"],
                    net.fields["dst"],
                    layer.fields["dport"],
                )
            return "", _Found(Payload(frame.number, path, layer.payload, flow), layer.fields)
    if stopped is None:
        return "no-match", None
    if stopped == "malformed" and frame.truncated:
        return "truncated", None
    return stopped, None


def slice_payloads(
    frames: Iterable[Frame], parent: Parent, limit: int, *, skip_until: bytes | None = None
) -> Slicing:
    """The first ``limit`` payloads under ``parent`` in ``frames``; frames
    are read only until there are ``limit`` of them (``PcapError`` from a
    broken capture propagates). Under a ``tcp`` parent the segments go
    through ``TcpStreams`` (``skip_until``: each direction's bytes up to the
    end of that pattern are skipped); ``skip_until`` needs one."""
    if skip_until is not None and parent.proto != "tcp":
        raise ValueError("skip_until needs a tcp parent")
    out = Slicing()
    streams = TcpStreams(out.skipped, skip_until) if parent.proto == "tcp" else None
    for frame in frames:
        out.frames += 1
        reason, found = _reason(frame, parent)
        if found is None:
            out.skipped[reason] += 1
            continue
        if streams is None:
            out.payloads.append(found.payload)
        else:
            ready = streams.segment(found.payload, found.fields["seq"], found.fields["flags"])
            out.payloads += ready[: limit - len(out.payloads)]
        if len(out.payloads) >= limit:
            break
    if streams is not None:
        streams.finish()
    return out
