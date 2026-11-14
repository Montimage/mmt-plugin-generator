"""Packet tests: the corpus schema 1 fixtures (``tests/corpus/README.md``,
"Packet files") that ``mmt-plugin test`` runs, and how a harness
observation is checked against them.

``load(path, shown, data_types)`` reads one file into a ``PacketTest`` or
raises ``PacketTestError`` (``model.bad-packet-test``, exit 3). Only what
the harness checks is required: ``schema: 1``, ``id``, ``bytes`` and
``expect`` with ``protocol``, ``proto_id``, ``next`` and ``attributes``;
the informational keys (``summary``, ``source``, ``constructs``,
``parent``, ...) are not, and are not read. ``parent`` in particular: the
harness attaches the protocol to Ethernet itself, so a packet is tested
without the user code's parent registration.

``check(test, observed, plugin)`` compares one ``Observation`` with the test
and returns its failures, each an attribute, the expected and the actual
value as display strings. Values are compared in the corpus's value kinds:
integers, ``aa:bb:..`` MAC addresses, dotted quads, RFC 5952 IPv6 text, the
offset a pointer points at, and hex pairs for every other type. A
``<protocol>`` failure is a packet the plugin did not classify, or a
protocol id or name other than the test's; ``<next>`` is the next protocol.
"""

from __future__ import annotations

import ipaddress
import re
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mmt_plugin.diagnostics import Diagnostic, Location, Severity
from mmt_plugin.testing.yamlsubset import LoadError, loads

__all__ = [
    "NEXT",
    "PROTOCOL",
    "ExpectedAttribute",
    "ExpectedNext",
    "Failure",
    "Observation",
    "ObservedValue",
    "PacketTest",
    "PacketTestError",
    "check",
    "display",
    "harness_lengths",
    "load",
]

#: The pseudo attributes of a failure on the classification.
PROTOCOL = "<protocol>"
NEXT = "<next>"

#: The integer types and their widths in bytes.
INT_WIDTH = {
    "MMT_U8_DATA": 1,
    "MMT_U16_DATA": 2,
    "MMT_U32_DATA": 4,
    "MMT_U64_DATA": 8,
    "MMT_DATA_CHAR": 1,
    "MMT_DATA_PORT": 2,
}
#: The address types and their widths in bytes.
ADDR_WIDTH = {
    "MMT_DATA_MAC_ADDR": 6,
    "MMT_DATA_IP_ADDR": 4,
    "MMT_DATA_IP_NET": 4,
    "MMT_DATA_IP6_ADDR": 16,
}
POINTER = "MMT_DATA_POINTER"

_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_HEX_BYTES = re.compile(r"^([0-9a-f]{2})( [0-9a-f]{2})*$")
_STATUSES = ("value", "absent", "undefined")
_NEXT_KINDS = ("none", "hook", "proto")


class PacketTestError(Exception):
    """A packet test file is not a valid fixture; ``diagnostic`` says where."""

    def __init__(self, diagnostic: Diagnostic) -> None:
        super().__init__(diagnostic.message)
        self.diagnostic = diagnostic


@dataclass(frozen=True)
class ExpectedAttribute:
    """One attribute of ``expect.attributes``. ``value`` is in its display
    form (an ``int`` for integers and pointers, else a string), ``None``
    unless ``status`` is ``value``; ``length`` is the bytes it covers."""

    name: str
    type: str
    status: str
    value: int | str | None
    length: int | None


@dataclass(frozen=True)
class ExpectedNext:
    """``expect.next``: ``kind`` is ``none``, ``hook`` (user code decides:
    not checked) or ``proto``, with its ``proto_id`` and ``offset``."""

    kind: str
    proto_id: int | None = None
    offset: int | None = None


@dataclass(frozen=True)
class PacketTest:
    """One packet test: its ``id``, the ``file`` it came from (as shown),
    the packet ``data`` (from the protocol's first byte) and what it expects."""

    id: str
    file: str
    data: bytes
    protocol: str
    proto_id: int
    next: ExpectedNext
    attributes: tuple[ExpectedAttribute, ...]


@dataclass(frozen=True)
class ObservedValue:
    """What the harness printed for one attribute: ``kind`` is ``missing``
    (no such attribute in the plugin), ``absent``, ``int``, ``ptr`` or
    ``hex``; ``type`` is the type it registered with."""

    kind: str
    type: str | None = None
    number: int | None = None
    data: bytes | None = None


@dataclass(frozen=True)
class Observation:
    """What the harness saw for one packet: ``index`` of the protocol in the
    path (``None``: not classified), the next protocol (``None``: none) and
    its offset, and each attribute by name."""

    index: int | None
    next_id: int | None
    next_offset: int | None
    values: Mapping[str, ObservedValue]


@dataclass(frozen=True)
class Failure:
    """One mismatch, as ``result.packets[].failures`` reports it."""

    attribute: str
    expected: str
    actual: str

    def to_json(self) -> dict[str, str]:
        return {"attribute": self.attribute, "expected": self.expected, "actual": self.actual}


def _error(shown: str, message: str, line: int | None = None) -> PacketTestError:
    return PacketTestError(
        Diagnostic(
            Severity.ERROR,
            "model.bad-packet-test",
            message,
            hint="see tests/corpus/README.md, Packet files",
            location=Location(shown, line),
        )
    )


def _need(shown: str, where: str, obj: Mapping[str, Any], key: str, kind: type) -> Any:
    value = obj.get(key)
    if key not in obj:
        raise _error(shown, f"{where}: missing key {key!r}")
    if not isinstance(value, kind) or (kind is int and isinstance(value, bool)):
        raise _error(shown, f"{where}: {key!r} must be {_kind_name(kind)}")
    return value


def _kind_name(kind: type) -> str:
    return {int: "an integer", str: "a string", list: "a list", dict: "a mapping"}.get(
        kind, kind.__name__
    )


def _hex(shown: str, where: str, value: object) -> bytes:
    if not isinstance(value, str) or not _HEX_BYTES.match(value):
        raise _error(shown, f"{where}: must be lower-case hex pairs separated by one space")
    return bytes.fromhex(value)


def display(type_name: str, data: bytes) -> str:
    """The display form of the bytes of a non-integer value of ``type_name``."""
    if type_name == "MMT_DATA_MAC_ADDR":
        return ":".join(f"{b:02x}" for b in data)
    if type_name in ("MMT_DATA_IP_ADDR", "MMT_DATA_IP_NET") and len(data) == 4:
        return str(ipaddress.IPv4Address(data))
    if type_name == "MMT_DATA_IP6_ADDR" and len(data) == 16:
        return str(ipaddress.IPv6Address(data))
    return " ".join(f"{b:02x}" for b in data)


def _expected_value(shown: str, where: str, type_name: str, attr: Mapping[str, Any]) -> int | str:
    value = attr.get("value")
    if type_name in INT_WIDTH or type_name == POINTER:
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise _error(shown, f"{where}: a {type_name} value is a non-negative integer")
        return value
    if not isinstance(value, str):
        raise _error(shown, f"{where}: a {type_name} value is a string")
    try:
        if type_name == "MMT_DATA_MAC_ADDR":
            parts = value.lower().split(":")
            if len(parts) != 6 or not all(re.fullmatch(r"[0-9a-f]{2}", p) for p in parts):
                raise ValueError(value)
            return ":".join(parts)
        if type_name in ("MMT_DATA_IP_ADDR", "MMT_DATA_IP_NET"):
            return str(ipaddress.IPv4Address(value))
        if type_name == "MMT_DATA_IP6_ADDR":
            return str(ipaddress.IPv6Address(value))
    except ValueError:
        raise _error(shown, f"{where}: {value!r} is not a {type_name} value") from None
    return display(type_name, _hex(shown, f"{where} value", value))


def _attribute(
    shown: str, where: str, attr: object, data_types: Collection[str]
) -> ExpectedAttribute:
    if not isinstance(attr, dict):
        raise _error(shown, f"{where}: must be a mapping")
    name = _need(shown, where, attr, "name", str)
    if not _NAME.match(name):
        raise _error(shown, f"{where}: attribute name {name!r} is not a C identifier")
    where = f"{where} ({name})"
    type_name = _need(shown, where, attr, "type", str)
    if type_name not in data_types:
        raise _error(shown, f"{where}: {type_name!r} is not a data type of the SDK profile")
    status = attr.get("status", "value")
    if status not in _STATUSES:
        raise _error(shown, f"{where}: status must be value, absent or undefined")
    if status != "value":
        return ExpectedAttribute(name, type_name, status, None, None)
    offset = _need(shown, where, attr, "offset", int)
    length = _need(shown, where, attr, "length", int)
    if offset < 0 or length <= 0:
        raise _error(shown, f"{where}: offset must be >= 0 and length > 0")
    if "value" not in attr:
        raise _error(shown, f"{where}: missing key 'value'")
    return ExpectedAttribute(
        name, type_name, status, _expected_value(shown, where, type_name, attr), length
    )


def _next(shown: str, expect: Mapping[str, Any]) -> ExpectedNext:
    nxt = _need(shown, "expect", expect, "next", dict)
    kind = nxt.get("kind")
    if kind not in _NEXT_KINDS:
        raise _error(shown, "expect.next: kind must be none, hook or proto")
    if kind != "proto":
        return ExpectedNext(kind)
    proto_id = _need(shown, "expect.next", nxt, "proto_id", int)
    offset = _need(shown, "expect.next", nxt, "offset", int)
    return ExpectedNext(kind, proto_id, offset)


def load(path: Path, shown: str, data_types: Collection[str]) -> PacketTest:
    """Read the packet test at ``path`` (``shown`` names it in diagnostics);
    ``data_types`` are the SDK profile's data type names."""
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise _error(shown, f"cannot read {shown}: {exc.strerror or exc}") from None
    try:
        doc = loads(raw)
    except LoadError as exc:
        raise _error(shown, exc.message, exc.line) from None
    if not isinstance(doc, dict):
        raise _error(shown, "the top level must be a mapping")
    if doc.get("schema") != 1:
        raise _error(shown, "schema must be 1")
    test_id = _need(shown, "the test", doc, "id", str)
    chunks = _need(shown, "the test", doc, "bytes", list)
    data = b"".join(_hex(shown, f"bytes[{i}]", c) for i, c in enumerate(chunks))
    expect = _need(shown, "the test", doc, "expect", dict)
    protocol = _need(shown, "expect", expect, "protocol", str)
    proto_id = _need(shown, "expect", expect, "proto_id", int)
    nxt = _next(shown, expect)
    items = expect.get("attributes", [])
    if not isinstance(items, list):
        raise _error(shown, "expect: 'attributes' must be a list")
    attributes = tuple(
        _attribute(shown, f"expect.attributes[{i}]", a, data_types) for i, a in enumerate(items)
    )
    names = [a.name for a in attributes]
    duplicate = next((n for n in names if names.count(n) > 1), None)
    if duplicate is not None:
        raise _error(shown, f"expect.attributes: {duplicate!r} is listed twice")
    return PacketTest(test_id, shown, data, protocol, proto_id, nxt, attributes)


def _actual(expected: ExpectedAttribute, seen: ObservedValue) -> str:
    if seen.kind == "missing":
        return "not an attribute of the plugin"
    if seen.kind == "absent":
        return "absent"
    if seen.kind in ("int", "ptr"):
        return str(seen.number)
    assert seen.data is not None
    return display(expected.type, seen.data)


def check(
    test: PacketTest, observed: Observation, plugin: tuple[int, str]
) -> tuple[list[Failure], int]:
    """The failures of ``test`` given what the harness ``observed``, and the
    number of attributes checked. ``plugin`` is the protocol id and name the
    plugin registered."""
    failures: list[Failure] = []
    pid, name = plugin
    wanted = f"{test.protocol} ({test.proto_id})"
    if (test.proto_id, test.protocol.casefold()) != (pid, name.casefold()):
        return [Failure(PROTOCOL, wanted, f"{name} ({pid})")], 0
    if observed.index is None:
        return [Failure(PROTOCOL, wanted, "not classified")], 0
    if test.next.kind == "proto":
        want = f"{test.next.proto_id} at offset {test.next.offset}"
        got = (
            "none"
            if observed.next_id is None
            else f"{observed.next_id} at offset {observed.next_offset}"
        )
        if (observed.next_id, observed.next_offset) != (test.next.proto_id, test.next.offset):
            failures.append(Failure(NEXT, want, got))
    elif test.next.kind == "none" and observed.next_id is not None:
        failures.append(
            Failure(NEXT, "none", f"{observed.next_id} at offset {observed.next_offset}")
        )
    checked = 0
    for attr in test.attributes:
        if attr.status == "undefined":
            continue
        checked += 1
        seen = observed.values.get(attr.name, ObservedValue("missing"))
        if seen.kind == "missing":
            failures.append(Failure(attr.name, _shown(attr), "not an attribute of the plugin"))
            continue
        if seen.type != attr.type:
            failures.append(Failure(attr.name, attr.type, str(seen.type)))
            continue
        if attr.status == "absent":
            if seen.kind != "absent":
                failures.append(Failure(attr.name, "absent", _actual(attr, seen)))
            continue
        actual = _actual(attr, seen)
        if seen.kind == "absent" or actual != str(attr.value):
            failures.append(Failure(attr.name, _shown(attr), actual))
    return failures, checked


def _shown(attr: ExpectedAttribute) -> str:
    return "absent" if attr.status == "absent" else str(attr.value)


def harness_lengths(tests: Sequence[PacketTest], sizes: Mapping[str, int]) -> dict[str, int]:
    """The bytes the harness prints for each attribute the tests name, for a
    type with no integer or binary form: the longest length the tests give,
    within the type's SDK size (``sizes``; 0 or unknown: not capped), else
    that size."""
    out: dict[str, int] = {}
    for test in tests:
        for attr in test.attributes:
            size = sizes.get(attr.type, 0)
            length = attr.length if attr.length is not None else size
            if size > 0:
                length = min(length, size)
            out[attr.name] = max(out.get(attr.name, 0), length)
    return out
