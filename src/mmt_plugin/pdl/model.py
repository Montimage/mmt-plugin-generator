"""The typed model of a PDL v1 file, as written.

The parser (``mmt_plugin.pdl.parser``) builds it; nothing here computes
layouts, folds expressions or checks names (T1.3 does). Every node is a frozen
dataclass with the ``Span`` of the text it was parsed from.

The grammar that fixes each construct's meaning is the legacy one,
``legacy/pdl_grammar/PluginGrammar.g`` (``G:<line>`` below), with the decided
rules of ``tests/corpus/README.md``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TypeAlias

from mmt_plugin.diagnostics import Location

__all__ = [
    "C_TYPE_WORDS",
    "MMT_TYPES",
    "Attribute",
    "AttributeElement",
    "Attributes",
    "BinaryOp",
    "BinaryOperator",
    "ByteSwap",
    "CType",
    "Case",
    "ClassifyNext",
    "Conditional",
    "DataType",
    "DataTypeValue",
    "Default",
    "Define",
    "Element",
    "ElementType",
    "Encoding",
    "EncodingValue",
    "Expr",
    "Flag",
    "IntLiteral",
    "LengthOf",
    "MmtType",
    "Model",
    "Name",
    "NextEncaps",
    "NextOffset",
    "OffsetOf",
    "Properties",
    "Scope",
    "ScopeValue",
    "SizeOf",
    "Span",
    "Statement",
    "Struct",
    "StructField",
    "StructType",
    "Switch",
    "ValueOf",
]


@dataclass(frozen=True)
class Span:
    """A range of the source text.

    ``line`` and ``column`` are 1-based and point at the first code point;
    ``end_line`` and ``end_column`` point just past the last one. Columns count
    Unicode code points, so a tab is one column.
    """

    file: str
    line: int
    column: int
    end_line: int
    end_column: int

    def location(self) -> Location:
        """The diagnostics form of this span."""
        return Location(self.file, self.line, self.column, self.end_line, self.end_column)

    def to(self, other: Span) -> Span:
        """The span from the start of ``self`` to the end of ``other``."""
        return Span(self.file, self.line, self.column, other.end_line, other.end_column)

    def __str__(self) -> str:
        return f"{self.file}:{self.line}:{self.column}"


# --- Leaves -----------------------------------------------------------------


@dataclass(frozen=True)
class Name:
    """An identifier as written: a define, struct, field or attribute name."""

    text: str
    span: Span


@dataclass(frozen=True)
class IntLiteral:
    """An integer literal: decimal (``-4``, ``007``) or hex (``0x3BC``).

    ``value`` is the base-10 value of a decimal literal (``010`` is 10) and
    the value of a hex one. That is what the Java tool computed only where it
    folded the literal with ``Integer.parseInt``: ``id``, bit widths and simple
    expressions (G:704-705). Elsewhere (a define value, a case label, a
    ``nextencaps`` value, a literal inside a non-simple expression) it copied
    the literal into the C as text, where a leading zero means octal: ``010``
    is 8 and ``08`` does not compile. ``text`` keeps the spelling, sign
    included, so nothing is lost; the semantic passes (T1.3, #12) diagnose
    leading zeros. Ranges are not checked here.
    """

    value: int
    text: str
    span: Span

    @property
    def is_hex(self) -> bool:
        """Whether the literal is written in hex."""
        return "x" in self.text.lower()


class DataType(str, Enum):
    """The 26 ``MMT_*`` data types of the grammar (G:609-636), by name."""

    MMT_U8_DATA = "MMT_U8_DATA"
    MMT_U16_DATA = "MMT_U16_DATA"
    MMT_U32_DATA = "MMT_U32_DATA"
    MMT_U64_DATA = "MMT_U64_DATA"
    MMT_DATA_POINTER = "MMT_DATA_POINTER"
    MMT_STRING_DATA = "MMT_STRING_DATA"
    MMT_DATA_IP_NET = "MMT_DATA_IP_NET"
    MMT_DATA_MAC_ADDR = "MMT_DATA_MAC_ADDR"
    MMT_DATA_IP_ADDR = "MMT_DATA_IP_ADDR"
    MMT_DATA_PATH = "MMT_DATA_PATH"
    MMT_DATA_TIMEVAL = "MMT_DATA_TIMEVAL"
    MMT_BINARY_DATA = "MMT_BINARY_DATA"
    MMT_DATA_BUFFER = "MMT_DATA_BUFFER"
    MMT_DATA_CHAR = "MMT_DATA_CHAR"
    MMT_DATA_IP6_ADDR = "MMT_DATA_IP6_ADDR"
    MMT_DATA_PORT = "MMT_DATA_PORT"
    MMT_DATA_POINT = "MMT_DATA_POINT"
    MMT_DATA_PORT_RANGE = "MMT_DATA_PORT_RANGE"
    MMT_DATA_DATE = "MMT_DATA_DATE"
    MMT_DATA_TIMEARG = "MMT_DATA_TIMEARG"
    MMT_DATA_STRING_INDEX = "MMT_DATA_STRING_INDEX"
    MMT_DATA_FLOAT = "MMT_DATA_FLOAT"
    MMT_DATA_LAYERID = "MMT_DATA_LAYERID"
    MMT_DATA_FILTER_STATE = "MMT_DATA_FILTER_STATE"
    MMT_DATA_PARENT = "MMT_DATA_PARENT"
    MMT_BINARY_VAR_DATA = "MMT_BINARY_VAR_DATA"


#: The type names, for lookups and hints.
MMT_TYPES: frozenset[str] = frozenset(t.value for t in DataType)


# --- Element types (struct fields and sizeof) --------------------------------


@dataclass(frozen=True)
class CType:
    """A C scalar or pointer element type (G:638-648).

    ``name`` is the base word as written: ``int``, ``long``, ``uint32_t``,
    ``short``, ``uint16_t``, ``char``, ``u_char``, ``uint8_t``, or ``void``
    (pointers only). ``unsigned`` records the optional prefix, which changes
    nothing: every struct integer is unsigned (corpus README, Struct layout).
    """

    name: str
    unsigned: bool
    pointer: bool
    span: Span

    @property
    def data_type(self) -> DataType:
        """The ``MMT_*`` type the grammar reads this as (G:638-648)."""
        if self.pointer:
            return DataType.MMT_DATA_POINTER
        return _C_TYPES[self.name]


#: The C base words and their ``MMT_*`` type (G:862-864); ``void`` is only a
#: pointer base (G:865).
_C_TYPES: dict[str, DataType] = {
    "int": DataType.MMT_U32_DATA,
    "long": DataType.MMT_U32_DATA,
    "uint32_t": DataType.MMT_U32_DATA,
    "short": DataType.MMT_U16_DATA,
    "uint16_t": DataType.MMT_U16_DATA,
    "char": DataType.MMT_U8_DATA,
    "u_char": DataType.MMT_U8_DATA,
    "uint8_t": DataType.MMT_U8_DATA,
}

#: Every word that starts a C element type.
C_TYPE_WORDS: frozenset[str] = frozenset({*_C_TYPES, "void"})


@dataclass(frozen=True)
class MmtType:
    """An ``MMT_*`` type used as an element type or in ``sizeof`` (G:596)."""

    type: DataType
    span: Span


@dataclass(frozen=True)
class StructType:
    """``struct X``: a field typed by another struct (G:597-606)."""

    name: Name
    span: Span


ElementType: TypeAlias = CType | MmtType | StructType


# --- Expressions (G:661-758) -------------------------------------------------


class BinaryOperator(str, Enum):
    """A binary operator, by its PDL spelling."""

    OR = "OR"
    AND = "AND"
    EQ = "=="
    NE = "!="
    GT = ">"
    LT = "<"
    GE = ">="
    LE = "<="
    ADD = "+"
    SUB = "-"
    MUL = "*"
    DIV = "/"


@dataclass(frozen=True)
class BinaryOp:
    """``left op right``. Parentheses are not kept: the tree is the grouping."""

    op: BinaryOperator
    left: Expr
    right: Expr
    span: Span


@dataclass(frozen=True)
class ValueOf:
    """``val(x)``: the value of attribute ``x`` (G:715-730)."""

    attribute: Name
    span: Span


@dataclass(frozen=True)
class SizeOf:
    """``sizeof(T)`` for an element type (G:732-734)."""

    type: ElementType
    span: Span


@dataclass(frozen=True)
class OffsetOf:
    """``offset(x)``: attribute ``x``'s byte offset (G:736-738)."""

    attribute: Name
    span: Span


@dataclass(frozen=True)
class LengthOf:
    """``len(x)``: attribute ``x``'s length (G:740-742)."""

    attribute: Name
    span: Span


@dataclass(frozen=True)
class ByteSwap:
    """``ntohs(n)`` (``width`` 16) or ``ntohl(n)`` (``width`` 32) of a literal.

    An unconditional byte swap (decided rule; G:743-758).
    """

    width: int
    operand: IntLiteral
    span: Span


Expr: TypeAlias = IntLiteral | BinaryOp | ValueOf | SizeOf | OffsetOf | LengthOf | ByteSwap


# --- define and Properties ---------------------------------------------------


@dataclass(frozen=True)
class Define:
    """``define NAME = value`` (G:40-60); the value is a number or a name."""

    name: Name
    value: IntLiteral | Name
    span: Span


@dataclass(frozen=True)
class Flag:
    """A boolean property value, ``"true"`` or ``"false"`` (G:194-244)."""

    value: bool
    span: Span


class Encoding(str, Enum):
    """The ``encoding`` property (G:246-255; corpus README, Decided rules).

    ``ASCII`` and ``UNICODE`` are kept apart although the Java tool maps both
    to UNKNOWN, the same as an omitted key.
    """

    NETWORK = "network"
    HOST = "host"
    ASCII = "ASCII"
    UNICODE = "UNICODE"


@dataclass(frozen=True)
class EncodingValue:
    """An ``encoding`` value; ``spelling`` is ``little`` for the ``host`` alias."""

    value: Encoding
    spelling: str
    span: Span


@dataclass(frozen=True)
class Properties:
    """The ``Properties`` block (G:178-255). Omitted keys are ``None``."""

    label: Name
    id: IntLiteral
    context: Flag | None
    session_context: Flag | None
    session: Flag | None
    encapsulation: Flag | None
    encoding: EncodingValue | None
    span: Span


# --- Attributes --------------------------------------------------------------


@dataclass(frozen=True)
class DataTypeValue:
    """An attribute's ``data_type`` value."""

    type: DataType
    span: Span


class Scope(str, Enum):
    """An attribute scope (G:423-429)."""

    PACKET = "SCOPE_PACKET"
    SESSION = "SCOPE_SESSION"


@dataclass(frozen=True)
class ScopeValue:
    """A ``scope`` value; ``spelling`` is ``SCOPE_PACKET``, ``packet``, ..."""

    value: Scope
    spelling: str
    span: Span


@dataclass(frozen=True)
class Attribute:
    """``attribute { alias data_type [data_len] [offset] [scope] }`` (G:382-421).

    Omitted keys are ``None``; what an omission means is T1.3's business
    (corpus README, Decided rules).
    """

    alias: Name
    data_type: DataTypeValue
    data_len: Expr | None
    offset: Expr | None
    scope: ScopeValue | None
    span: Span


@dataclass(frozen=True)
class StructField:
    """One name of a struct declaration, with its bitfield width if any."""

    name: Name
    bit_width: IntLiteral | None
    span: Span


@dataclass(frozen=True)
class Element:
    """One struct declaration: ``type a, b:4, c:4;`` (G:502-589)."""

    type: ElementType
    fields: tuple[StructField, ...]
    span: Span


@dataclass(frozen=True)
class Struct:
    """``struct N { ... }`` (G:438-500); its fields are packet attributes."""

    name: Name
    elements: tuple[Element, ...]
    span: Span


@dataclass(frozen=True)
class Conditional:
    """``if (expr) { ... } [else { ... }]`` (G:314-380).

    ``else_branch`` is ``None`` when there is no ``else``, and a tuple
    (possibly empty) when there is one.
    """

    condition: Expr
    then_branch: tuple[AttributeElement, ...]
    else_branch: tuple[AttributeElement, ...] | None
    span: Span


AttributeElement: TypeAlias = Struct | Attribute | Conditional


@dataclass(frozen=True)
class Attributes:
    """The ``Attributes`` block (G:263-312), elements in source order."""

    elements: tuple[AttributeElement, ...]
    span: Span


# --- classifynext ------------------------------------------------------------


@dataclass(frozen=True)
class NextEncaps:
    """``nextencaps = N | DEFINE`` (G:760-778)."""

    value: IntLiteral | Name
    span: Span


@dataclass(frozen=True)
class NextOffset:
    """``nextoffset = expr`` (G:779-788)."""

    value: Expr
    span: Span


Statement: TypeAlias = NextEncaps | NextOffset


@dataclass(frozen=True)
class Case:
    """``case N | DEFINE: statements [break]`` (G:122-161)."""

    label: IntLiteral | Name
    statements: tuple[Statement, ...]
    has_break: bool
    span: Span


@dataclass(frozen=True)
class Default:
    """``default: statements [break]`` (G:101-120)."""

    statements: tuple[Statement, ...]
    has_break: bool
    span: Span


@dataclass(frozen=True)
class Switch:
    """``switch(expr) { case* default? }`` (G:76-99)."""

    subject: Expr
    cases: tuple[Case, ...]
    default: Default | None
    span: Span


@dataclass(frozen=True)
class ClassifyNext:
    """``classifynext { switch }``: exactly one switch (G:62-74)."""

    switch: Switch
    span: Span


# --- The whole file ----------------------------------------------------------


@dataclass(frozen=True)
class Model:
    """A PDL v1 file: ``Protocol { define* Properties Attributes classifynext? }``.

    The layout of G:33.
    """

    defines: tuple[Define, ...]
    properties: Properties
    attributes: Attributes
    classify_next: ClassifyNext | None
    span: Span
