"""The lower layers of a packet test that runs through the plugin's real
parent (its ``through`` key, ``tests/corpus/README.md``, "Packet files").

``parse_through(text)`` reads a ``through`` selector, the grammar of
``mmt-plugin init --parent`` (``<proto>[:<key>=<value>[,...]]``), with the
parents and keys of ``mmt_plugin.pcap.layers.PARENTS``, or raises
``ValueError`` with the reason:

- ``ethernet:ethertype=N``: an Ethernet header with EtherType ``N``;
- ``ip:proto=N``: Ethernet (EtherType 0x0800), then an IPv4 header of
  protocol ``N``;
- ``ipv6:proto=N``: Ethernet (0x86dd), then an IPv6 header whose next
  header is ``N``;
- ``udp`` and ``tcp``, keys ``dport`` (or ``port``, the same) and ``sport``:
  Ethernet, IPv4, then a UDP header or a 20-byte TCP header (flags PSH and
  ACK, no handshake). A port not given is an ephemeral one, 49152 to 65535.

``parse_through(text, plugins)`` also accepts the label of a plugin parent
(#147), one of ``plugins`` (``PluginParent``: a project plugin.yaml's
``plugins`` names), with one optional key, ``test``, the id of one of that
project's packet tests (default: its first). That test must run through an
mmt-dpi protocol: the frame is its lower layers, then its bytes up to its
``expect.next`` offset (all of them when it names no next protocol), the
parent's header, then the packet test's ``data``.

``build_frame(through, data, n)`` puts those layers in front of the packet
test's ``data``. Every length and checksum is right for the frame; the
``n``-th frame of a run gets an IPv4 source address (198.18.0.0/15) and
ephemeral ports of its own, so that no two frames of a run share a session
in mmt-dpi. The plugin's protocol starts at ``through.offset``.
"""

from __future__ import annotations

import re
import struct
from collections.abc import Mapping
from dataclasses import dataclass

from mmt_plugin.pcap.layers import PARENTS

__all__ = ["ParentFrame", "PluginParent", "Through", "build_frame", "parse_through"]

_LABEL = re.compile(r"^[a-z][a-z0-9_]*$")
_KEY = re.compile(r"^[a-z_][a-z0-9_]*$")
_VALUE = re.compile(r"^[A-Za-z0-9_.:/-]+$")

_MAC_DST = bytes.fromhex("020000000002")
_MAC_SRC = bytes.fromhex("020000000001")
_IPV4 = 0x0800
_IPV6 = 0x86DD
_UDP = 17
_TCP = 6
_EPHEMERAL = 49152
#: The source addresses, 198.18.0.0/15 (RFC 2544), and the destination.
_SOURCES = 198 << 24 | 18 << 16
_SOURCE_COUNT = 1 << 17
_DESTINATION = bytes([192, 0, 2, 1])
_IPV6_SOURCE = bytes.fromhex("20010db8000000000000000000000000")
_IPV6_DESTINATION = bytes.fromhex("20010db8000000000000000000000001")

#: The header bytes below the plugin's protocol, per parent.
_OFFSETS = {"ethernet": 14, "ip": 34, "ipv6": 54, "udp": 42, "tcp": 54}
#: The key each parent needs.
_REQUIRED = {"ethernet": "ethertype", "ip": "proto", "ipv6": "proto"}


@dataclass(frozen=True)
class ParentFrame:
    """The lower layers of a plugin parent: the parent's packet test
    ``test`` (its id), which runs ``lower``, through an mmt-dpi protocol;
    ``header``, its bytes before the child's; and the parent plugin's
    protocol id, ``proto_id``."""

    test: str
    lower: Through
    header: bytes
    proto_id: int


@dataclass(frozen=True)
class PluginParent:
    """A plugin parent a selector can name: its ``label``, its protocol id,
    its ``project`` (as diagnostics show it) and the ``tests`` of that
    project that run through an mmt-dpi protocol, in file order (each a
    ``ParentFrame``)."""

    label: str
    proto_id: int
    project: str
    tests: tuple[ParentFrame, ...]


@dataclass(frozen=True)
class Through:
    """A ``through`` selector: the parent ``proto`` (an mmt-dpi protocol
    alias, or a plugin parent's label), its ``keys`` (name, value), the
    plugin parent's frame (``None``: an mmt-dpi protocol), and the
    ``offset`` the plugin's protocol starts at in the built frame."""

    text: str
    proto: str
    keys: tuple[tuple[str, int], ...]
    plugin: ParentFrame | None = None

    @property
    def offset(self) -> int:
        if self.plugin is not None:
            return self.plugin.lower.offset + len(self.plugin.header)
        return _OFFSETS[self.proto]

    def key(self, name: str) -> int | None:
        return next((v for k, v in self.keys if k == name), None)


def parse_through(text: str, plugins: Mapping[str, PluginParent] | None = None) -> Through:
    """The ``Through`` of ``text``, whose parent is an mmt-dpi protocol or
    one of the plugin parents ``plugins`` (by label); ``ValueError`` with the
    reason."""
    proto, sep, rest = text.partition(":")
    items: list[tuple[str, str]] = []
    ok = _LABEL.match(proto) is not None and (not sep or bool(rest))
    for item in rest.split(",") if sep and rest else ():
        key, eq, value = item.partition("=")
        if not (eq and _KEY.match(key) and _VALUE.match(value)):
            ok = False
            break
        items.append((key, value))
    if not ok:
        raise ValueError(
            f"{text!r} is not a selector (<proto>[:<key>=<value>[,...]]),"
            " for example udp:dport=53 or ethernet:ethertype=0x88b5"
        )
    known = PARENTS.get(proto)
    plugin = None if known is not None or plugins is None else plugins.get(proto)
    if plugin is not None:
        return _plugin_through(text, plugin, items)
    if known is None:
        named = f" or a plugin of plugins: ({', '.join(plugins)})" if plugins else ""
        raise ValueError(
            f"{text!r}: the parent is one of {', '.join(PARENTS)}{named}, not {proto}"
        )
    keys: list[tuple[str, int]] = []
    for key, raw in items:
        largest = known.get(key)
        if largest is None:
            raise ValueError(f"{text!r}: {proto} has no key {key!r} (keys: {', '.join(known)})")
        if any(k == key for k, _ in keys):
            raise ValueError(f"{text!r}: {key} is given twice")
        try:
            number = int(raw, 0)
        except ValueError:
            number = -1
        if not 0 <= number <= largest:
            raise ValueError(f"{text!r}: {key}={raw} is not a number from 0 to {largest:#x}")
        keys.append((key, number))
    through = Through(text, proto, tuple(keys))
    required = _REQUIRED.get(proto)
    if required is not None and through.key(required) is None:
        raise ValueError(f"{text!r}: {proto} needs {required}=, for example {proto}:{required}=")
    if through.key("port") is not None and through.key("dport") is not None:
        raise ValueError(f"{text!r}: port is the destination port; give port or dport, not both")
    return through


def _plugin_through(text: str, parent: PluginParent, items: list[tuple[str, str]]) -> Through:
    """The ``Through`` of a plugin parent: its packet test ``test=`` names,
    or its first."""
    wanted: str | None = None
    for key, value in items:
        if key != "test":
            raise ValueError(f"{text!r}: a plugin parent has one key, test, not {key!r}")
        if wanted is not None:
            raise ValueError(f"{text!r}: test is given twice")
        wanted = value
    ids = ", ".join(t.test for t in parent.tests)
    if not parent.tests:
        raise ValueError(
            f"{text!r}: no packet test of {parent.project} runs through an mmt-dpi protocol;"
            " the frame starts with one: give a test of that project through: (its parent's"
            " selector)"
        )
    if wanted is None:
        frame = parent.tests[0]
    else:
        found = next((t for t in parent.tests if t.test == wanted), None)
        if found is None:
            raise ValueError(
                f"{text!r}: {parent.project} has no packet test {wanted!r} that runs through an"
                f" mmt-dpi protocol (tests: {ids})"
            )
        frame = found
    return Through(text, parent.label, (), frame)


def _checksum(data: bytes) -> int:
    """The Internet checksum (RFC 1071) of ``data``."""
    if len(data) % 2:
        data += b"\0"
    total = sum(int(x) for x in struct.unpack(f">{len(data) // 2}H", data))
    while total >> 16:
        total = (total & 0xFFFF) + (total >> 16)
    return ~total & 0xFFFF


def _ethernet(ethertype: int, payload: bytes) -> bytes:
    return _MAC_DST + _MAC_SRC + struct.pack(">H", ethertype) + payload


def _ipv4(proto: int, payload: bytes, source: bytes) -> bytes:
    header = struct.pack(
        ">BBHHHBBH4s4s", 0x45, 0, 20 + len(payload), 1, 0, 64, proto, 0, source, _DESTINATION
    )
    return header[:10] + struct.pack(">H", _checksum(header)) + header[12:] + payload


def _ipv6(next_header: int, payload: bytes) -> bytes:
    header = struct.pack(">IHBB", 0x60000000, len(payload), next_header, 64)
    return header + _IPV6_SOURCE + _IPV6_DESTINATION + payload


def _transport(proto: int, header: bytes, payload: bytes, source: bytes) -> bytes:
    """``header`` (checksum 0) with its checksum over the IPv4 pseudo-header."""
    segment = header + payload
    pseudo = source + _DESTINATION + struct.pack(">BBH", 0, proto, len(segment))
    checksum = _checksum(pseudo + segment)
    if proto == _UDP and checksum == 0:
        checksum = 0xFFFF
    at = 6 if proto == _UDP else 16
    return segment[:at] + struct.pack(">H", checksum) + segment[at + 2 :]


def build_frame(through: Through, data: bytes, n: int = 0) -> bytes:
    """The Ethernet frame of ``data`` under ``through``; ``n`` numbers the
    frame in its run (its addresses and ephemeral ports)."""
    if through.plugin is not None:
        return build_frame(through.plugin.lower, through.plugin.header + data, n)
    source = struct.pack(">I", _SOURCES + 1 + n % (_SOURCE_COUNT - 2))
    if through.proto == "ethernet":
        return _ethernet(through.key("ethertype") or 0, data)
    if through.proto == "ipv6":
        return _ethernet(_IPV6, _ipv6(through.key("proto") or 0, data))
    if through.proto == "ip":
        return _ethernet(_IPV4, _ipv4(through.key("proto") or 0, data, source))
    sport = through.key("sport")
    dport = through.key("dport")
    if dport is None:
        dport = through.key("port")
    if sport is None:
        sport = _EPHEMERAL + n % 16384
    if dport is None:
        dport = _EPHEMERAL + (n + 8192) % 16384
    if through.proto == "udp":
        header = struct.pack(">HHHH", sport, dport, 8 + len(data), 0)
        segment = _transport(_UDP, header, data, source)
        return _ethernet(_IPV4, _ipv4(_UDP, segment, source))
    header = struct.pack(">HHIIBBHHH", sport, dport, 1, 1, 5 << 4, 0x18, 65535, 0, 0)
    segment = _transport(_TCP, header, data, source)
    return _ethernet(_IPV4, _ipv4(_TCP, segment, source))
