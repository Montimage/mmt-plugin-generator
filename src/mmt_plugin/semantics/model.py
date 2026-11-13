"""The analysed model: what the semantic passes compute from a PDL model.

``mmt_plugin.semantics.analyse`` builds it; code generation (T1.5) reads it.
Every node is a frozen dataclass with the ``Span`` of the PDL text it comes
from. Nothing here refers back to a mutable object, and attributes and
structs refer to each other by their lower-case ``key``, so the model is a
tree (``==``, ``repr`` and ``hash`` work on it).

What is resolved here, so that a generator needs no PDL knowledge:

- each attribute's type, byte offset and length, with the PDL defaults
  applied (an omitted scope is packet, an omitted ``data_len`` the type's
  width) and the running offset R added where alignment is on;
- each struct's packed wire layout, each bitfield's position counted from
  the most significant bit of its storage unit, and the natural C layout of
  the struct a generator would emit (``c_offset``, ``c_size``, ``c_align``);
- every expression, typed, with its value when it folds at generation time
  (see ``Expr``) and every ``val()``, ``sizeof``, ``offset()`` and ``len()``
  resolved;
- the guards (enclosing ``if`` conditions) of each conditional attribute;
- the classifynext switch, with each case label and ``nextencaps`` value
  resolved to a number.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TypeAlias

from mmt_plugin.pdl.model import (
    BinaryOperator,
    DataType,
    ElementType,
    Encoding,
    Model,
    Scope,
    Span,
)

__all__ = [
    "AnalysedAttribute",
    "AnalysedCase",
    "AnalysedConditional",
    "AnalysedDefault",
    "AnalysedDefine",
    "AnalysedModel",
    "AnalysedStruct",
    "AnalysedSwitch",
    "AttributeKind",
    "Binary",
    "Bitfield",
    "BitfieldRun",
    "ByteOrder",
    "Const",
    "Element",
    "Expr",
    "FieldKind",
    "Guard",
    "LengthRef",
    "NextProto",
    "OffsetRef",
    "Protocol",
    "SetNextOffset",
    "SetNextProto",
    "SizeOfType",
    "Statement",
    "StructField",
    "Swap",
    "ValueRef",
]


class ByteOrder(str, Enum):
    """How multi-byte integers are read (corpus README, Semantics).

    ``network`` is big-endian; ``host`` (alias ``little``) is fixed
    little-endian, whatever machine runs the plugin (decided rule).
    ``ASCII``, ``UNICODE`` and an omitted encoding give no byte order
    (inventory bug 10 is T1.5's).
    """

    BIG = "big"
    LITTLE = "little"
    UNSPECIFIED = "unspecified"


# --- Expressions -------------------------------------------------------------
#
# Every PDL expression is an integer. ``value`` is the folded value when the
# expression is *foldable*: known at generation time, so a generator emits
# the number. An expression folds when every operand folds, whatever the
# operator or position (inventory bug 5 decided it by the last operand):
#
# - an integer literal, ``ntohs(n)`` and ``ntohl(n)`` fold;
# - ``sizeof(T)`` folds to the PDL width of T (``sizeof(char)`` is 1, bug 7);
# - ``offset(x)`` and ``len(x)`` fold when x's offset or length folds (bug 19:
#   they are x's, not calls to C functions that do not exist);
# - ``val(x)`` never folds: it is read from the packet;
# - ``+ - * /`` fold with C integer semantics (``/`` truncates toward zero),
#   comparisons to 1 or 0 with their own meaning (bug 6 folded them as
#   ``!=``), and ``AND``/``OR`` to 1 or 0, any non-zero operand being true.


@dataclass(frozen=True)
class Const:
    """An integer literal, or a number the passes computed (an aligned offset,
    a defaulted length). ``text`` is the literal as written, or the number in
    decimal when computed."""

    value: int
    text: str
    span: Span


@dataclass(frozen=True)
class Binary:
    """``left op right``; ``value`` is ``None`` unless both operands fold."""

    op: BinaryOperator
    left: Expr
    right: Expr
    value: int | None
    span: Span


@dataclass(frozen=True)
class ValueRef:
    """``val(x)``: attribute ``attribute``'s value, read from the packet."""

    attribute: str
    span: Span

    @property
    def value(self) -> None:
        """``val()`` never folds."""
        return None


@dataclass(frozen=True)
class SizeOfType:
    """``sizeof(T)``: the PDL width of ``type`` (a struct's packed size)."""

    type: ElementType
    value: int
    span: Span


@dataclass(frozen=True)
class OffsetRef:
    """``offset(x)``: attribute ``attribute``'s byte offset, when it folds."""

    attribute: str
    value: int | None
    span: Span


@dataclass(frozen=True)
class LengthRef:
    """``len(x)``: attribute ``attribute``'s length, when it folds."""

    attribute: str
    value: int | None
    span: Span


@dataclass(frozen=True)
class Swap:
    """``ntohs(n)`` (``width`` 16) or ``ntohl(n)`` (32): a byte swap of
    ``operand``, unconditional (decided rule)."""

    width: int
    operand: int
    value: int
    span: Span


Expr: TypeAlias = Const | Binary | ValueRef | SizeOfType | OffsetRef | LengthRef | Swap


# --- Properties and defines --------------------------------------------------


@dataclass(frozen=True)
class Protocol:
    """The Properties block, with the defaults applied (false, no encoding).

    ``name`` is the upper-cased label: the registered name, and ``LABEL`` in
    ``PROTO_<LABEL>``.
    """

    label: str
    name: str
    id: int
    context: bool
    session_context: bool
    session: bool
    encapsulation: bool
    encoding: Encoding | None
    byte_order: ByteOrder
    span: Span


@dataclass(frozen=True)
class AnalysedDefine:
    """``define NAME = value`` with its value resolved. ``alias_of`` is the
    define or SDK macro the value names, ``None`` for a number."""

    name: str
    value: int
    alias_of: str | None
    span: Span


# --- Attributes and structs --------------------------------------------------


class AttributeKind(str, Enum):
    """Where an attribute is declared."""

    PLAIN = "attribute"
    FIELD = "field"
    BITFIELD = "bitfield"


@dataclass(frozen=True)
class Guard:
    """One enclosing ``if``: the attribute exists when ``condition`` is true
    (``holds``) or false (in the ``else`` branch). ``conditional`` numbers the
    ``if`` blocks in source order, from 0."""

    conditional: int
    condition: Expr
    holds: bool
    span: Span


@dataclass(frozen=True)
class Bitfield:
    """A bitfield's place in its storage unit.

    ``bit_offset`` counts from the most significant bit of the
    ``unit_width``-byte unit at ``unit_offset`` (in the struct), read in the
    model's byte order (decided rule). The value is
    ``(unit >> shift) & mask``.
    """

    run: int
    unit_offset: int
    unit_width: int
    bit_offset: int
    bit_width: int

    @property
    def shift(self) -> int:
        """How far to shift the unit right to bring the field to bit 0."""
        return self.unit_width * 8 - self.bit_offset - self.bit_width

    @property
    def mask(self) -> int:
        """The field's mask once shifted."""
        return (1 << self.bit_width) - 1


@dataclass(frozen=True)
class AnalysedAttribute:
    """One attribute: a plain ``attribute``, a struct field or a bitfield.

    - ``key`` is the lower-cased name: the C alias, and the name ``val()``,
      ``offset()`` and ``len()`` look up (names are case-insensitive).
    - ``offset`` is the byte offset from the start of the protocol: a
      ``Const`` for an aligned attribute (R + the declared offset) and a
      struct field, the declared expression otherwise. ``None`` means no
      offset: the extraction is a user hook (corpus README).
    - ``length`` is the length in bytes; ``length_defaulted`` says it is the
      type's width because ``data_len`` was omitted. ``None`` only for a user
      hook without ``data_len``.
    - ``declared_offset`` is the offset as written, before R was added.
    - ``scope_defaulted``: the scope was omitted, so it is packet.
    - ``guards``: the enclosing ``if`` blocks, outermost first.
    - ``struct``: the key of the struct of a field or bitfield.
    """

    name: str
    key: str
    kind: AttributeKind
    data_type: DataType
    offset: Expr | None
    length: Expr | None
    declared_offset: Expr | None
    scope: Scope
    scope_defaulted: bool
    length_defaulted: bool
    aligned: bool
    guards: tuple[Guard, ...]
    struct: str | None
    bitfield: Bitfield | None
    span: Span

    @property
    def is_hook(self) -> bool:
        """Whether the extraction is a user hook (no offset)."""
        return self.offset is None

    @property
    def offset_value(self) -> int | None:
        """The offset, when it folds."""
        return None if self.offset is None else self.offset.value

    @property
    def length_value(self) -> int | None:
        """The length, when it folds."""
        return None if self.length is None else self.length.value


class FieldKind(str, Enum):
    """A struct field's element type."""

    INTEGER = "integer"
    POINTER = "pointer"
    MMT = "mmt"
    STRUCT = "struct"


@dataclass(frozen=True)
class StructField:
    """A struct field's layout.

    ``offset`` and ``width`` are its wire place in the struct (packed, no
    padding: bug 4). ``c_type`` is the C type a generator declares it with,
    and ``c_offset`` its offset in that C struct with natural alignment. All
    fields of one bitfield run share the run's unit.
    """

    name: str
    key: str
    kind: FieldKind
    data_type: DataType
    offset: int
    width: int
    c_type: str
    c_offset: int
    bitfield: Bitfield | None
    span: Span


@dataclass(frozen=True)
class BitfieldRun:
    """A run of consecutive bitfields of one declaration line: one storage
    unit. ``helper_name`` is unique in the model (bug 17) and is no struct's
    name."""

    helper_name: str
    offset: int
    width: int
    c_type: str
    fields: tuple[str, ...]
    span: Span


@dataclass(frozen=True)
class AnalysedStruct:
    """A struct, its wire layout and its natural C layout.

    - ``size`` is the packed wire size, which is also ``sizeof(struct X)``.
    - ``base_offset`` is the byte offset of its first field from the start of
      the protocol: R when ``aligned``, 0 otherwise (literal in-struct
      offsets, corpus README).
    - ``c_size``, ``c_align`` and ``c_padding`` describe the struct a C
      compiler lays out from the fields' ``c_type`` with natural alignment
      (LP64). ``needs_packing`` is true when that layout differs from the wire
      one, so an emitted struct must be packed to match it (bug 4).
    """

    name: str
    key: str
    size: int
    base_offset: int
    aligned: bool
    fields: tuple[StructField, ...]
    runs: tuple[BitfieldRun, ...]
    c_size: int
    c_align: int
    c_padding: int
    guards: tuple[Guard, ...]
    span: Span

    @property
    def needs_packing(self) -> bool:
        """Whether the natural C layout differs from the wire layout."""
        return self.c_size != self.size or any(f.c_offset != f.offset for f in self.fields)


@dataclass(frozen=True)
class AnalysedConditional:
    """``if (condition) { ... } [else { ... }]``; ``index`` is the
    ``Guard.conditional`` of its attributes."""

    index: int
    condition: Expr
    then_branch: tuple[Element, ...]
    else_branch: tuple[Element, ...] | None
    span: Span


Element: TypeAlias = AnalysedAttribute | AnalysedStruct | AnalysedConditional


# --- classifynext ------------------------------------------------------------


@dataclass(frozen=True)
class NextProto:
    """A protocol id, as a number or through a define or SDK macro
    (``alias_of``)."""

    id: int
    alias_of: str | None
    span: Span


@dataclass(frozen=True)
class SetNextProto:
    """``nextencaps = ...``: the next protocol, and it is classified."""

    proto: NextProto
    span: Span


@dataclass(frozen=True)
class SetNextOffset:
    """``nextoffset = expr``: the next protocol's offset."""

    offset: Expr
    span: Span


Statement: TypeAlias = SetNextProto | SetNextOffset


@dataclass(frozen=True)
class AnalysedCase:
    """``case label: ...``; ``label`` is resolved, ``alias_of`` names the
    define it came through."""

    label: int
    alias_of: str | None
    statements: tuple[Statement, ...]
    has_break: bool
    span: Span


@dataclass(frozen=True)
class AnalysedDefault:
    """``default: ...``."""

    statements: tuple[Statement, ...]
    has_break: bool
    span: Span


@dataclass(frozen=True)
class AnalysedSwitch:
    """The classifynext switch. C semantics: a case without break falls
    through."""

    subject: Expr
    cases: tuple[AnalysedCase, ...]
    default: AnalysedDefault | None
    span: Span


# --- The whole model ---------------------------------------------------------


@dataclass(frozen=True)
class AnalysedModel:
    """A PDL model, analysed.

    ``elements`` keeps the Attributes block's structure; ``attributes`` lists
    every attribute (struct fields included) and ``structs`` every struct,
    both in declaration order. ``source`` is the parsed model.
    """

    protocol: Protocol
    defines: tuple[AnalysedDefine, ...]
    elements: tuple[Element, ...]
    attributes: tuple[AnalysedAttribute, ...]
    structs: tuple[AnalysedStruct, ...]
    conditionals: tuple[AnalysedConditional, ...]
    classify_next: AnalysedSwitch | None
    source: Model

    def attribute(self, name: str) -> AnalysedAttribute:
        """An attribute by name, case-insensitively; ``KeyError`` if none."""
        key = name.lower()
        for attribute in self.attributes:
            if attribute.key == key:
                return attribute
        raise KeyError(name)

    def struct(self, name: str) -> AnalysedStruct:
        """A struct by name, case-insensitively; ``KeyError`` if none."""
        key = name.lower()
        for struct in self.structs:
            if struct.key == key:
                return struct
        raise KeyError(name)
