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
   sequence number, whose high bytes change less often).
   Before it, a byte whose bits vary independently is cut into bit fields
   (``bit_groups``, below);
3. every other byte that is the same in every payload is a 1-byte field (a
   version, a type, a flag byte);
4. each other run of bytes that differ is cut into 4-, 2- and 1-byte fields,
   the widest first (a byte cut into bit fields ends the run).

Fields are named ``field_<offset>``, integers in network byte order
(``MMT_U8_DATA``, ``MMT_U16_DATA``, ``MMT_U32_DATA``); a byte's bit fields
``field_<offset>_b<bit>``, ``bit`` counted from its most significant bit,
in a struct ``bits_<offset>`` of the proposed model.

``bit_groups`` cuts a byte whose value varies into groups of bits, from the
most significant: a bit varies when two payloads differ in it, and a
constant bit between two that vary is taken as varying (a number whose
values did not use it). Each run of varying bits, and each run of constant
ones, is a group; the top bit of a varying run is a group of its own when
it is constant within each direction of the payloads (``Payload.flow``),
the two directions of each connection seen both ways with two payloads or
more (one at least) set it to opposite values, and the rest of the run
takes two values or more within one of those directions (a role flag
beside data that varies: WebSocket's MASK, set by clients only, DNS's QR).
So a byte that is constant within each direction (a per-flow identifier:
RTP's SSRC, a session id), or the payloads of unrelated flows (several
one-way UDP streams), are never cut by this rule. Two
neighbouring varying groups (with the constant ones between them) are
merged back unless they vary independently: one group's value is seen
with two values of the other, and the other way round. A byte left with
fewer than two varying groups, or with fewer than 4 distinct values, is
not cut: a type byte with 7 constant bits stays one field.

The bytes after the header are not proposed: a comment says what is there. The packet tests
expect what the proposed model extracts from each captured payload, so they
pass once the proposal is the model; they are a draft for the protocol's
specification to correct, not values taken from it.
"""

from __future__ import annotations

import itertools
import json
from collections.abc import Sequence
from dataclasses import dataclass

from mmt_plugin.pcap.layers import Flow, Parent, Payload
from mmt_plugin.ui.render import escape

__all__ = [
    "HEADER_LIMIT",
    "Field",
    "Skeleton",
    "bit_groups",
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
#: Each payload's direction (``Payload.flow``), or ``None``.
Flows = Sequence[Flow | None] | None

#: The fewest distinct values of a byte cut into bit fields: fewer are too
#: little evidence (a few random bytes have constant bits by chance).
_BIT_VALUES = 4


@dataclass(frozen=True)
class Field:
    """A proposed attribute: ``constant`` when every payload has the same
    value; ``note`` says what was seen. A bit field (of a 1-byte field) has
    ``bit_offset``, from the byte's most significant bit, and
    ``bit_width``."""

    name: str
    offset: int
    length: int
    constant: bool
    note: str
    bit_offset: int | None = None
    bit_width: int | None = None

    @property
    def type(self) -> str:
        return _TYPES[self.length]

    def value(self, data: bytes) -> int:
        """Its value in ``data`` (network byte order)."""
        whole = int.from_bytes(data[self.offset : self.offset + self.length], "big")
        if self.bit_offset is None or self.bit_width is None:
            return whole
        shift = self.length * 8 - self.bit_offset - self.bit_width
        return (whole >> shift) & ((1 << self.bit_width) - 1)

    def to_json(self) -> dict[str, object]:
        out: dict[str, object] = {
            "name": self.name,
            "type": self.type,
            "offset": self.offset,
            "length": self.length,
            "constant": self.constant,
        }
        if self.bit_offset is not None:
            out["bit_offset"] = self.bit_offset
            out["bit_width"] = self.bit_width
        return out


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


def _bit(value: int, bit: int) -> int:
    """Bit ``bit`` of a byte, counted from its most significant bit."""
    return (value >> (7 - bit)) & 1


def _group_value(value: int, start: int, width: int) -> int:
    return (value >> (8 - start - width)) & ((1 << width) - 1)


def _reverse(flow: Flow) -> Flow:
    net, src, sport, dst, dport = flow
    return (net, dst, dport, src, sport)


def _role_bit(values: Sequence[int], bit: int, end: int, flows: Flows) -> bool:
    """Whether ``bit``, the top bit of the varying run ``bit``..``end - 1``,
    is a role flag (module docstring): constant within each direction, the
    opposite value in the two directions of each connection seen both ways
    with two payloads or more (one at least), and the rest of the run
    taking two values or more within one of those directions."""
    if flows is None:
        return False
    seen: dict[Flow | None, set[int]] = {}
    rest: dict[Flow | None, set[int]] = {}
    counts: dict[Flow | None, int] = {}
    for value, flow in zip(values, flows, strict=True):
        seen.setdefault(flow, set()).add(_bit(value, bit))
        rest.setdefault(flow, set()).add(_group_value(value, bit + 1, end - bit - 1))
        counts[flow] = counts.get(flow, 0) + 1
    if any(len(bits) > 1 for bits in seen.values()):
        return False
    pairs = [
        (f, _reverse(f))
        for f in seen
        if f is not None and counts[f] > 1 and counts.get(_reverse(f), 0) > 1 and f < _reverse(f)
    ]
    if not pairs or any(seen[f] == seen[r] for f, r in pairs):
        return False
    return any(len(rest[f]) > 1 for pair in pairs for f in pair)


def _independent(values: Sequence[int], a: tuple[int, int], b: tuple[int, int]) -> bool:
    """Whether bit groups ``a`` and ``b`` (start, width) vary independently:
    a value of each is seen with two values of the other."""
    pairs = {(_group_value(v, *a), _group_value(v, *b)) for v in values}
    with_a: dict[int, set[int]] = {}
    with_b: dict[int, set[int]] = {}
    for x, y in pairs:
        with_a.setdefault(x, set()).add(y)
        with_b.setdefault(y, set()).add(x)
    return any(len(s) > 1 for s in with_a.values()) and any(len(s) > 1 for s in with_b.values())


def bit_groups(values: Sequence[int], flows: Flows = None) -> list[tuple[int, int, str]] | None:
    """The bit groups of a byte whose payloads have ``values`` (``flows``:
    each payload's direction, or ``None``), as (bit offset from the most
    significant bit, width, kind), kind ``varies``, ``role`` or
    ``constant``; ``None`` when the byte stays whole (module docstring)."""
    if len(set(values)) < _BIT_VALUES:
        return None
    varies = [len({_bit(v, b) for v in values}) > 1 for b in range(8)]
    varies = [varies[b] or (0 < b < 7 and varies[b - 1] and varies[b + 1]) for b in range(8)]
    groups: list[tuple[int, int, str]] = []
    b = 0
    while b < 8:
        end = b
        while end < 8 and varies[end] == varies[b]:
            end += 1
        if not varies[b]:
            groups.append((b, end - b, "constant"))
        elif end - b > 1 and _role_bit(values, b, end, flows):
            groups += [(b, 1, "role"), (b + 1, end - b - 1, "varies")]
        else:
            groups.append((b, end - b, "varies"))
        b = end
    merged = True
    while merged:
        merged = False
        moving = [i for i, g in enumerate(groups) if g[2] == "varies"]
        for i, j in itertools.pairwise(moving):
            a, c = groups[i], groups[j]
            if any(g[2] == "role" for g in groups[i:j]):
                continue
            if not _independent(values, a[:2], c[:2]):
                start, end = a[0], c[0] + c[1]
                groups[i : j + 1] = [(start, end - start, "varies")]
                merged = True
                break
    if sum(1 for g in groups if g[2] != "constant") < 2:
        return None
    return groups


def _bits_note(values: Sequence[int], start: int, width: int, kind: str) -> str:
    where = f"bit {start}" if width == 1 else f"bits {start}-{start + width - 1}"
    if kind == "role":
        return f"{where}: one value per direction, both seen"
    seen = sorted({_group_value(v, start, width) for v in values})
    if len(seen) == 1:
        return f"{where}: constant {seen[0]} in every payload"
    return f"{where}: varies: {len(seen)} values from {seen[0]} to {seen[-1]}"


def propose(payloads: Sequence[bytes], flows: Flows = None) -> Skeleton:
    """The field skeleton of ``payloads`` (at least one, none empty);
    ``flows``, each payload's direction (``Payload.flow``), finds the bit
    flags each direction of a connection sets its own way."""
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

    def bits(offset: int) -> list[tuple[int, int, str]] | None:
        return bit_groups([p[offset] for p in payloads], flows)

    i = 0
    while i < header:
        if found is not None and i == found[0]:
            _, width, adjust = found
            note = "the payload length" + (f" - {adjust}" if adjust else "") + " in every payload"
            length = add(i, width, name="length", note=note)
            i += width
            continue
        groups = bits(i)
        if groups is not None:
            values = [p[i] for p in payloads]
            for start, width, kind in groups:
                fields.append(
                    Field(
                        f"field_{i}_b{start}",
                        i,
                        1,
                        len({_group_value(v, start, width) for v in values}) == 1,
                        _bits_note(values, start, width, kind),
                        start,
                        width,
                    )
                )
            i += 1
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
        while run < end and not _same(payloads, run) and (run == i or bits(run) is None):
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
    """``text`` safe in a ``#`` comment, escaped as plain output is
    (``ui.render.escape``): control and format characters, and each byte of
    a file name that is not UTF-8 as ``\\xNN``; anything else UTF-8 cannot
    encode as a backslash escape."""
    return escape(text).encode("utf-8", "backslashreplace").decode("utf-8")


def _classify(parent: Parent, tagged: bool) -> list[str] | None:
    """The ``classify`` lines of a parent the generated code can attach
    exactly, or ``None``: an Ethernet type of untagged frames, a UDP source
    or destination port, TCP ports (``port``, ``sport``, ``dport``: the
    generated code reads the TCP header's length; not ``port`` with
    ``dport``). Every other selector (UDP ``port`` matches either, IP
    headers have options, a tagged frame has 0x8100 at offset 12) needs
    user code."""
    keys = dict(parent.keys)
    if not keys or (parent.proto == "ethernet" and tagged):
        return None
    if parent.proto == "tcp":
        if "port" in keys and "dport" in keys:  # not a ``through`` selector
            return None
        return ["    classify:"] + [f"      {k}: {v}" for k, v in parent.keys]
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
        if field.bit_offset is not None:
            if field.bit_offset == 0:
                lines += [
                    f"  - struct: bits_{field.offset}"
                    f"    # byte {field.offset}, cut into bit fields",
                    f"    offset: {field.offset}",
                    "    fields:",
                    "      - type: uint8_t",
                    "        bits:",
                ]
            lines.append(
                f"          - {{name: {field.name}, width: {field.bit_width}}}    # {field.note}"
            )
            continue
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
    captured = f"captured: frame {payload.frame} of {pcap}"
    if payload.cut:
        captured = (
            f"captured: the payload of frame {payload.frame} of {pcap}, from byte {payload.cut}"
        )
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
        f"bytes_source: {_quote(captured)}",
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
        if field.bit_offset is not None:
            lines += [
                f"      bit_offset: {field.bit_offset}",
                f"      bit_width: {field.bit_width}",
            ]
    return "\n".join(lines) + "\n"
