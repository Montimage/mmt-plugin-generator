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
without the user code's parent registration. The optional ``through`` (a
selector, ``mmt_plugin.testing.frames``) runs the packet a second time,
behind the lower layers it names, through mmt-dpi's stack and the plugin's
own parent classification; it names an mmt-dpi protocol, or one of the
plugin parents ``load_doc``'s ``plugins`` gives (#147).

``load_doc(doc, shown, data_types, plugins)`` does the same for a file
already read (``mmt_plugin.testing.session.load_test`` reads a file once
and tells a packet test from a session test).

``check(test, observed, plugin)`` compares one ``Observation`` with the test
and returns its failures, each an attribute, the expected and the actual
value as display strings. Values are compared in the corpus's value kinds:
integers, ``aa:bb:..`` MAC addresses, dotted quads, RFC 5952 IPv6 text, the
offset a pointer points at, and hex pairs for every other type. A
``<protocol>`` failure is a packet the plugin did not classify, or a
protocol id or name other than the test's; ``<next>`` is the next protocol.
With an ``ExpectedParent`` (the run through the parent), ``<parent>`` is the
protocol below the plugin's and the offset the plugin starts at, and
``<next>`` is not checked: mmt-dpi 1.10.2 does not process a layer that a
plugin classified under its TCP or UDP, so that layer's next protocol is
never classified there (``examples/README.md``).
"""

from __future__ import annotations

import ipaddress
import re
from collections.abc import Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from mmt_plugin.diagnostics import Diagnostic, Location, Severity
from mmt_plugin.testing.frames import PluginParent, Through, parse_through
from mmt_plugin.testing.yamlsubset import LoadError, loads

__all__ = [
    "NEXT",
    "PARENT",
    "PROTOCOL",
    "ExpectedAttribute",
    "ExpectedNext",
    "ExpectedParent",
    "Failure",
    "Observation",
    "ObservedValue",
    "PacketTest",
    "PacketTestError",
    "check",
    "display",
    "harness_lengths",
    "load",
    "load_doc",
    "read_doc",
]

#: The pseudo attributes of a failure on the classification.
PROTOCOL = "<protocol>"
NEXT = "<next>"
PARENT = "<parent>"

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
    the packet ``data`` (from the protocol's first byte), what it expects,
    and the parent it also runs ``through`` (``None``: none)."""

    id: str
    file: str
    data: bytes
    protocol: str
    proto_id: int
    next: ExpectedNext
    attributes: tuple[ExpectedAttribute, ...]
    through: Through | None = None

    @property
    def named_attributes(self) -> Iterable[ExpectedAttribute]:
        """Every attribute the test names (what the harness must read)."""
        return self.attributes


@dataclass(frozen=True)
class ExpectedParent:
    """Where the run through the parent expects the plugin: directly above
    the protocol ``proto_id`` (``None``: any; ``name`` shows it), starting
    at ``offset`` in the frame."""

    name: str
    proto_id: int | None
    offset: int


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
    its offset, each attribute by name, and the protocol's ``offset`` in the
    frame and the ``parent_id`` below it (``None``: not reported)."""

    index: int | None
    next_id: int | None
    next_offset: int | None
    values: Mapping[str, ObservedValue]
    offset: int | None = None
    parent_id: int | None = None


@dataclass(frozen=True)
class Failure:
    """One mismatch, as ``result.packets[].failures`` reports it; ``packet``
    is the index of the step of a session test it is in (``None``: a packet
    test)."""

    attribute: str
    expected: str
    actual: str
    packet: int | None = None

    def to_json(self) -> dict[str, str | int]:
        out: dict[str, str | int] = {
            "attribute": self.attribute,
            "expected": self.expected,
            "actual": self.actual,
        }
        if self.packet is not None:
            out["packet"] = self.packet
        return out


def error(shown: str, message: str, line: int | None = None) -> PacketTestError:
    """A ``model.bad-packet-test`` error in the file ``shown``."""
    return PacketTestError(
        Diagnostic(
            Severity.ERROR,
            "model.bad-packet-test",
            message,
            hint="see tests/corpus/README.md, Packet files",
            location=Location(shown, line),
        )
    )


def need(shown: str, where: str, obj: Mapping[str, Any], key: str, kind: type) -> Any:
    value = obj.get(key)
    if key not in obj:
        raise error(shown, f"{where}: missing key {key!r}")
    if not isinstance(value, kind) or (kind is int and isinstance(value, bool)):
        raise error(shown, f"{where}: {key!r} must be {_kind_name(kind)}")
    return value


def _kind_name(kind: type) -> str:
    return {int: "an integer", str: "a string", list: "a list", dict: "a mapping"}.get(
        kind, kind.__name__
    )


def hex_bytes(shown: str, where: str, value: object) -> bytes:
    if not isinstance(value, str) or not _HEX_BYTES.match(value):
        raise error(shown, f"{where}: must be lower-case hex pairs separated by one space")
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
            raise error(shown, f"{where}: a {type_name} value is a non-negative integer")
        return value
    if not isinstance(value, str):
        raise error(shown, f"{where}: a {type_name} value is a string")
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
        raise error(shown, f"{where}: {value!r} is not a {type_name} value") from None
    return display(type_name, hex_bytes(shown, f"{where} value", value))


def attribute(
    shown: str,
    where: str,
    attr: object,
    data_types: Collection[str],
    known: Mapping[str, str] | None = None,
) -> ExpectedAttribute:
    """One entry of ``expect.attributes``. With ``known`` (a session test's
    attributes, name to type), ``offset`` and ``length`` are optional, and
    so is ``type`` for a name ``known`` lists, which must agree with it."""
    if not isinstance(attr, dict):
        raise error(shown, f"{where}: must be a mapping")
    name = need(shown, where, attr, "name", str)
    if not _NAME.match(name):
        raise error(shown, f"{where}: attribute name {name!r} is not a C identifier")
    where = f"{where} ({name})"
    listed = None if known is None else known.get(name)
    if listed is not None and "type" not in attr:
        type_name = listed
    else:
        type_name = need(shown, where, attr, "type", str)
    if type_name not in data_types:
        raise error(shown, f"{where}: {type_name!r} is not a data type of the SDK profile")
    if listed is not None and type_name != listed:
        raise error(shown, f"{where}: type {type_name} but the session lists it as {listed}")
    status = attr.get("status", "value")
    if status not in _STATUSES:
        raise error(shown, f"{where}: status must be value, absent or undefined")
    if status != "value":
        return ExpectedAttribute(name, type_name, status, None, None)
    if known is not None and "offset" not in attr and "length" not in attr:
        if "value" not in attr:
            raise error(shown, f"{where}: missing key 'value'")
        value = _expected_value(shown, where, type_name, attr)
        return ExpectedAttribute(name, type_name, status, value, None)
    offset = need(shown, where, attr, "offset", int)
    length = need(shown, where, attr, "length", int)
    if offset < 0 or length <= 0:
        raise error(shown, f"{where}: offset must be >= 0 and length > 0")
    if "value" not in attr:
        raise error(shown, f"{where}: missing key 'value'")
    return ExpectedAttribute(
        name, type_name, status, _expected_value(shown, where, type_name, attr), length
    )


def _next(shown: str, expect: Mapping[str, Any]) -> ExpectedNext:
    nxt = need(shown, "expect", expect, "next", dict)
    kind = nxt.get("kind")
    if kind not in _NEXT_KINDS:
        raise error(shown, "expect.next: kind must be none, hook or proto")
    if kind != "proto":
        return ExpectedNext(kind)
    proto_id = need(shown, "expect.next", nxt, "proto_id", int)
    offset = need(shown, "expect.next", nxt, "offset", int)
    return ExpectedNext(kind, proto_id, offset)


def read_doc(path: Path, shown: str) -> dict[str, Any]:
    """The top-level mapping of the schema 1 file at ``path``."""
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise error(shown, f"cannot read {shown}: {exc.strerror or exc}") from None
    try:
        doc = loads(raw)
    except LoadError as exc:
        raise error(shown, exc.message, exc.line) from None
    if not isinstance(doc, dict):
        raise error(shown, "the top level must be a mapping")
    if doc.get("schema") != 1:
        raise error(shown, "schema must be 1")
    return doc


def load(path: Path, shown: str, data_types: Collection[str]) -> PacketTest:
    """Read the packet test at ``path`` (``shown`` names it in diagnostics);
    ``data_types`` are the SDK profile's data type names."""
    return load_doc(read_doc(path, shown), shown, data_types)


def load_doc(
    doc: Mapping[str, Any],
    shown: str,
    data_types: Collection[str],
    plugins: Mapping[str, PluginParent] | None = None,
) -> PacketTest:
    """The packet test of ``doc``, a file ``read_doc`` read; its ``through``
    may name one of the plugin parents ``plugins``."""
    if "session" in doc:
        raise error(shown, "a session test (it has 'session'), not a packet test")
    test_id = need(shown, "the test", doc, "id", str)
    chunks = need(shown, "the test", doc, "bytes", list)
    data = b"".join(hex_bytes(shown, f"bytes[{i}]", c) for i, c in enumerate(chunks))
    expect = need(shown, "the test", doc, "expect", dict)
    protocol = need(shown, "expect", expect, "protocol", str)
    proto_id = need(shown, "expect", expect, "proto_id", int)
    nxt = _next(shown, expect)
    items = expect.get("attributes", [])
    if not isinstance(items, list):
        raise error(shown, "expect: 'attributes' must be a list")
    attributes = tuple(
        attribute(shown, f"expect.attributes[{i}]", a, data_types) for i, a in enumerate(items)
    )
    names = [a.name for a in attributes]
    duplicate = next((n for n in names if names.count(n) > 1), None)
    if duplicate is not None:
        raise error(shown, f"expect.attributes: {duplicate!r} is listed twice")
    through = None
    if "through" in doc:
        text = need(shown, "the test", doc, "through", str)
        try:
            through = parse_through(text, plugins)
        except ValueError as exc:
            raise error(shown, f"through: {exc}") from None
    return PacketTest(test_id, shown, data, protocol, proto_id, nxt, attributes, through)


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
    test: PacketTest,
    observed: Observation,
    plugin: tuple[int, str],
    parent: ExpectedParent | None = None,
    names: Mapping[int, str] | None = None,
) -> tuple[list[Failure], int]:
    """The failures of ``test`` given what the harness ``observed``, and the
    number of attributes checked. ``plugin`` is the protocol id and name the
    plugin registered; ``parent`` is given for the run through the parent,
    and ``names`` shows the protocol ids it reports."""
    failures: list[Failure] = []
    pid, name = plugin
    wanted = f"{test.protocol} ({test.proto_id})"
    if (test.proto_id, test.protocol.casefold()) != (pid, name.casefold()):
        return [Failure(PROTOCOL, wanted, f"{name} ({pid})")], 0
    if observed.index is None:
        return [Failure(PROTOCOL, wanted, "not classified")], 0
    if parent is not None:
        want = f"{parent.name} at offset {parent.offset}"
        below = observed.parent_id
        shown = "unknown" if below is None else (names or {}).get(below, str(below))
        got = f"{shown} at offset {observed.offset}"
        if observed.offset != parent.offset or (
            parent.proto_id is not None and below != parent.proto_id
        ):
            failures.append(Failure(PARENT, want, got))
    elif test.next.kind == "proto":
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


class NamesAttributes(Protocol):
    """A packet test or a session test: the attributes it names."""

    @property
    def named_attributes(self) -> Iterable[ExpectedAttribute]: ...


def harness_lengths(tests: Sequence[NamesAttributes], sizes: Mapping[str, int]) -> dict[str, int]:
    """The bytes the harness prints for each attribute the tests name, for a
    type with no integer or binary form: the longest length the tests give,
    within the type's SDK size (``sizes``; 0 or unknown: not capped), else
    that size."""
    out: dict[str, int] = {}
    for test in tests:
        for attr in test.named_attributes:
            size = sizes.get(attr.type, 0)
            length = attr.length if attr.length is not None else size
            if size > 0:
                length = min(length, size)
            out[attr.name] = max(out.get(attr.name, 0), length)
    return out
