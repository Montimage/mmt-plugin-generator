"""The field skeleton ``scaffold --from-pcap`` proposes, and the files it
writes: ``plugin.proposed.yaml`` and one packet test per payload.

``propose(payloads)`` looks at the first ``header_length`` bytes, the
shortest payload's length up to ``HEADER_LIMIT``, which every payload has:

1. a length field: when the payloads have at least two lengths, the first
   2-byte (then 1-byte) big-endian integer at an offset ``k`` whose value is
   the payload's length minus the same ``adjust`` in every payload, with
   ``0 <= adjust <= k + width`` (it counts the whole payload, or what follows
   some of the header). It is named ``length``;
2. a 4-byte word at an offset that is a multiple of 4 whose last byte
   differs between payloads is a 4-byte field (an identifier, a counter, a
   sequence number, whose high bytes change less often);
3. every other byte that is the same in every payload is a 1-byte field (a
   version, a type, a flag byte);
4. each other run of bytes that differ is cut into 4-, 2- and 1-byte fields,
   the widest first.

Fields are named ``field_<offset>``, integers in network byte order
(``MMT_U8_DATA``, ``MMT_U16_DATA``, ``MMT_U32_DATA``). The bytes after the
header are not proposed: a comment says what is there. The packet tests
expect what the proposed model extracts from each captured payload, so they
pass once the proposal is the model; they are a draft for the protocol's
specification to correct, not values taken from it.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass

from mmt_plugin.pcap.layers import Parent, Payload
from mmt_plugin.ui.render import escape

__all__ = [
    "HEADER_LIMIT",
    "Field",
    "Skeleton",
    "classifies",
    "packet_test",
    "parent_yaml",
    "propose",
    "proposed_yaml",
]

#: The most header bytes proposed as fields.
HEADER_LIMIT = 16

_TYPES = {1: "MMT_U8_DATA", 2: "MMT_U16_DATA", 4: "MMT_U32_DATA"}
_BYTES_PER_LINE = 16


@dataclass(frozen=True)
class Field:
    """A proposed attribute: ``constant`` when every payload has the same
    value; ``note`` says what was seen."""

    name: str
    offset: int
    length: int
    constant: bool
    note: str

    @property
    def type(self) -> str:
        return _TYPES[self.length]

    def value(self, data: bytes) -> int:
        """Its value in ``data`` (network byte order)."""
        return int.from_bytes(data[self.offset : self.offset + self.length], "big")

    def to_json(self) -> dict[str, object]:
        return {
            "name": self.name,
            "type": self.type,
            "offset": self.offset,
            "length": self.length,
            "constant": self.constant,
        }


@dataclass(frozen=True)
class Skeleton:
    """The proposal: ``fields`` by offset; ``length`` is the length field
    (also in ``fields``) and ``adjust`` what its value lacks of the
    payload's length, or both ``None``; ``shortest`` and ``longest`` are the
    payload lengths."""

    header_length: int
    fields: tuple[Field, ...]
    length: Field | None
    adjust: int | None
    shortest: int
    longest: int

    def to_json(self) -> dict[str, object]:
        return {
            "header_length": self.header_length,
            "fields": [f.to_json() for f in self.fields],
            "length_field": None
            if self.length is None
            else {"name": self.length.name, "adjust": self.adjust},
            "payload_lengths": {"min": self.shortest, "max": self.longest},
        }


def _length_field(payloads: Sequence[bytes], header: int) -> tuple[int, int, int] | None:
    """(offset, width, adjust) of the length field, or ``None``."""
    lengths = [len(p) for p in payloads]
    if len(set(lengths)) < 2:
        return None
    for width in (2, 1):
        for k in range(header - width + 1):
            adjusts = {
                n - int.from_bytes(p[k : k + width], "big")
                for n, p in zip(lengths, payloads, strict=True)
            }
            if len(adjusts) == 1:
                adjust = adjusts.pop()
                if 0 <= adjust <= k + width:
                    return k, width, adjust
    return None


def _same(payloads: Sequence[bytes], offset: int) -> bool:
    """Whether every payload has the same byte at ``offset``."""
    return all(p[offset] == payloads[0][offset] for p in payloads)


def _values_note(values: Sequence[int], width: int) -> str:
    distinct = sorted(set(values))
    if len(distinct) == 1:
        return f"constant {distinct[0]:#0{2 * width + 2}x} in every payload"
    return f"varies: {len(distinct)} values from {distinct[0]} to {distinct[-1]}"


def propose(payloads: Sequence[bytes]) -> Skeleton:
    """The field skeleton of ``payloads`` (at least one, none empty)."""
    shortest = min(len(p) for p in payloads)
    header = min(shortest, HEADER_LIMIT)
    found = _length_field(payloads, header)
    fields: list[Field] = []
    length: Field | None = None
    adjust: int | None = None

    def add(offset: int, width: int, *, name: str | None = None, note: str | None = None) -> Field:
        values = [int.from_bytes(p[offset : offset + width], "big") for p in payloads]
        field = Field(
            name or f"field_{offset}",
            offset,
            width,
            len(set(values)) == 1,
            note or _values_note(values, width),
        )
        fields.append(field)
        return field

    i = 0
    while i < header:
        if found is not None and i == found[0]:
            _, width, adjust = found
            note = "the payload length" + (f" - {adjust}" if adjust else "") + " in every payload"
            length = add(i, width, name="length", note=note)
            i += width
            continue
        end = header if found is None or found[0] < i else found[0]
        if i % 4 == 0 and i + 4 <= end and not _same(payloads, i + 3):
            add(i, 4)
            i += 4
            continue
        if _same(payloads, i):
            add(i, 1)
            i += 1
            continue
        run = i
        while run < end and not _same(payloads, run):
            run += 1
        while i < run:
            width = next(w for w in (4, 2, 1) if i + w <= run)
            add(i, width)
            i += width
    longest = max(len(p) for p in payloads)
    return Skeleton(header, tuple(fields), length, adjust, shortest, longest)


def _quote(text: str) -> str:
    """A double-quoted YAML scalar (JSON escapes, ASCII only)."""
    return json.dumps(text)


def _comment(text: str) -> str:
    """``text`` safe in a ``#`` comment: control characters escaped, and
    what UTF-8 cannot encode (the surrogates of a file name that is not
    UTF-8) as backslash escapes."""
    return escape(text).encode("utf-8", "backslashreplace").decode("utf-8")


def _classify(parent: Parent, tagged: bool) -> list[str] | None:
    """The ``classify`` lines of a parent the generated code can attach
    exactly, or ``None``: an Ethernet type of untagged frames, a UDP source
    or destination port. Every other selector (``port`` matches either, IP
    and TCP headers have options, a tagged frame has 0x8100 at offset 12)
    needs user code."""
    keys = dict(parent.keys)
    if not keys or (parent.proto == "ethernet" and tagged):
        return None
    if parent.proto == "ethernet":
        matches, offset = [(12, 2, f"{keys['ethertype']:#06x}")], 14
    elif parent.proto == "udp" and "port" not in keys:
        where = {"sport": 0, "dport": 2}
        matches, offset = [(where[k], 2, str(v)) for k, v in parent.keys], 8
    else:
        return None
    lines = ["    classify:", "      match:"]
    lines += [f"        - {{offset: {o}, length: {n}, value: {v}}}" for o, n, v in matches]
    lines.append(f"      offset: {offset}")
    return lines


def classifies(parent: Parent, *, tagged: bool = False) -> bool:
    """Whether ``parent_yaml`` gives ``parent`` a generated ``classify``."""
    return _classify(parent, tagged) is not None


def parent_yaml(label: str, parent: Parent, *, tagged: bool = False) -> list[str]:
    """The ``parents`` entry of ``parent`` in a ``plugin.yaml`` of ``label``
    (``init`` and ``scaffold`` write the same one): with ``classify`` when
    the generated code can attach the protocol exactly, else a comment that
    names the hook that must (``<label>_hook_register_parents``)."""
    lc = label.lower()
    classify = _classify(parent, tagged)
    if classify is None:
        return [
            f"  - protocol: {parent.proto}    # {_comment(parent.text)}: attach it in"
            f" {lc}_hook_register_parents (src/{lc}_impl.c)"
        ]
    return [f"  - protocol: {parent.proto}    # {_comment(parent.text)}", *classify]


def proposed_yaml(
    label: str,
    pid: int,
    parent: Parent,
    skeleton: Skeleton,
    pcap: str,
    count: int,
    *,
    tagged: bool = False,
) -> str:
    """``plugin.proposed.yaml``: the protocol of the project's model, the
    parent, and the skeleton's attributes. ``tagged``: a payload came
    through an 802.1Q/802.1ad tag."""
    lines = [
        f"# The fields mmt-plugin scaffold proposes for {label.upper()}, from {count}"
        f" payload{'s' if count != 1 else ''}",
        f"# under {_comment(parent.text)} in {_comment(pcap)}. A draft: rename the fields and"
        " check them",
        "# against the protocol's specification, then copy what you keep into",
        "# plugin.yaml (scaffold never edits it). The packet tests it wrote expect",
        "# what this model extracts.",
        "schema: 1",
        "protocol:",
        f"  label: {_quote(label)}",
        f"  id: {pid}",
        "  encoding: network",
        "parents:",
        *parent_yaml(label, parent, tagged=tagged),
        "attributes:",
    ]
    for field in skeleton.fields:
        lines += [
            f"  - name: {field.name}    # {field.note}",
            f"    type: {field.type}",
            f"    offset: {field.offset}",
        ]
    if skeleton.longest > skeleton.header_length:
        low = skeleton.shortest - skeleton.header_length
        high = skeleton.longest - skeleton.header_length
        size = str(high) if low == high else f"{low} to {high}"
        lines.append(
            f"# Not proposed: the bytes from offset {skeleton.header_length} on ({size} bytes)."
        )
    return "\n".join(lines) + "\n"


def packet_test(
    label: str,
    pid: int,
    test_id: str,
    payload: Payload,
    skeleton: Skeleton,
    pcap: str,
    parent: Parent,
) -> str:
    """One packet test (corpus schema 1, ``tests/corpus/README.md``) of
    ``payload``, expecting the skeleton's values."""
    where = f"frame {payload.frame} of {pcap}"
    data = payload.data
    hexed = [f"{b:02x}" for b in data]
    lines = [
        f"# Packet test {_comment(test_id)}, drafted by mmt-plugin scaffold from"
        f" {_comment(where)}.",
        "# Format: corpus schema 1 (tests/corpus/README.md). The values are what",
        "# plugin.proposed.yaml extracts from the captured bytes: check them against",
        "# the protocol's specification.",
        "schema: 1",
        f"id: {_quote(test_id)}",
        f"summary: {_quote(f'{len(data)} bytes under {parent.text} in {where}')}",
        "parent:",
        '  kind: "stack"',
        "  path: [" + ", ".join(_quote(p) for p in payload.path) + "]",
        f"  selector: {_quote(parent.text)}",
        f"  source: {_quote(where)}",
        "bytes:",
        *(
            f'  - "{" ".join(hexed[i : i + _BYTES_PER_LINE])}"'
            for i in range(0, len(hexed), _BYTES_PER_LINE)
        ),
        f"bytes_source: {_quote(f'captured: {where}')}",
        "expect:",
        f"  protocol: {_quote(label.upper())}",
        f"  proto_id: {pid}",
        "  next:",
        '    kind: "none"',
        "  attributes:",
    ]
    for field in skeleton.fields:
        lines += [
            f"    - name: {_quote(field.name)}",
            f"      type: {_quote(field.type)}",
            f"      offset: {field.offset}",
            f"      length: {field.length}",
            f"      value: {field.value(data)}",
        ]
    return "\n".join(lines) + "\n"
