"""The template context: what the C templates print, computed from the
analysed model and the SDK profile.

``build(model, profile)`` returns a ``Context`` (frozen dataclasses, in model
order, so rendering is deterministic) and the generation warnings, or raises
``GenerationError``. Everything the templates need is computed here; the
templates lay it out. Every SDK name the generated C uses (types, struct
fields, callbacks, registration calls, helpers, constants, the logger) is
looked up in the profile through ``_Sdk``, which also records the header that
declares it, so the ``#include`` lines are the profile's headers of the names
actually used. The templates contain no SDK name.

How the generated code reads a packet (the corpus README, Semantics):

- every attribute with an offset has a *place* function: its guards (the
  enclosing ``if`` conditions), then its offset and length from the start of
  the protocol, each a folded number or a C expression of ``val()``,
  ``offset()`` and ``len()`` of other attributes;
- bytes are read only once they are inside the captured packet
  (``<label>_bytes``). A packet too short, a guard that does not hold, an
  arithmetic overflow or a division by zero makes the attribute absent: the
  extraction returns 0, it never reads out of bounds;
- integers are read byte by byte in the model's byte order, and bitfields
  are shifted and masked out of their storage unit, counted from its most
  significant bit. No C struct is ever overlaid on packet bytes: the model's
  structs are emitted for user code only, each bitfield run as its helper
  struct (``AnalysedStruct``);
- an attribute without an offset is a user hook (plan decision 3), declared
  in the header and defined in ``src/<label>_impl.c``; so are the context,
  session data and sessionizer callbacks, and ``classify_next`` when
  ``encapsulation`` is true without a ``classifynext`` block.

Java bugs fixed here (``docs/legacy/java-generator-inventory.md``, section 5)
are cited as "bug N".
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from mmt_plugin.diagnostics import Diagnostic, Severity
from mmt_plugin.pdl.model import BinaryOperator, DataType, Span
from mmt_plugin.sdk.profile import Callback, Param, Profile
from mmt_plugin.semantics.model import (
    AnalysedAttribute,
    AnalysedModel,
    Binary,
    ByteOrder,
    Expr,
    FieldKind,
    LengthRef,
    OffsetRef,
    SetNextOffset,
    SetNextProto,
    ValueRef,
)
from mmt_plugin.semantics.types import INTEGER_TYPES

__all__ = [
    "C_KEYWORDS",
    "CAttribute",
    "CCall",
    "CCase",
    "CClassify",
    "CDefine",
    "CGuard",
    "CMember",
    "CStruct",
    "Context",
    "GenerationError",
    "Hook",
    "build",
    "c_int",
    "c_name",
    "check_defines",
]

#: C keywords (C11, C23 and GNU): a model name that is one gets a trailing
#: underscore in the generated C (corpus README, "Still open").
C_KEYWORDS = frozenset(
    {
        "alignas", "alignof", "asm", "auto", "bool", "break", "case", "char", "const",
        "constexpr", "continue", "default", "do", "double", "else", "enum", "extern",
        "false", "float", "for", "goto", "if", "inline", "int", "long", "nullptr",
        "register", "restrict", "return", "short", "signed", "sizeof", "static",
        "static_assert", "struct", "switch", "thread_local", "true", "typedef", "typeof",
        "typeof_unqual", "union", "unsigned", "void", "volatile", "while", "_Alignas",
        "_Alignof", "_Atomic", "_BitInt", "_Bool", "_Complex", "_Decimal128", "_Decimal32",
        "_Decimal64", "_Generic", "_Imaginary", "_Noreturn", "_Static_assert",
        "_Thread_local",
    }
)  # fmt: skip

_INT64_MIN = -(1 << 63)
_INT64_MAX = (1 << 63) - 1
_INT_MAX = (1 << 31) - 1

#: The maximum of a stdint type, for the range check before a narrowing store.
_STDINT_MAX = {"uint8_t": "UINT8_MAX", "uint16_t": "UINT16_MAX", "uint32_t": "UINT32_MAX"}

#: How an integer attribute's value is stored in ``attribute_t.data``: the C
#: type and the table's ``data_len``.
_INTEGER_STORAGE = {
    DataType.MMT_U8_DATA: ("uint8_t", 1),
    DataType.MMT_U16_DATA: ("uint16_t", 2),
    DataType.MMT_U32_DATA: ("uint32_t", 4),
    DataType.MMT_U64_DATA: ("uint64_t", 8),
    DataType.MMT_DATA_CHAR: ("char", 1),
    DataType.MMT_DATA_PORT: ("uint16_t", 2),
}

#: The fixed-size byte types, copied byte for byte (bug 25: never swapped).
_BYTE_TYPES = frozenset(
    {
        DataType.MMT_DATA_MAC_ADDR,
        DataType.MMT_DATA_IP_ADDR,
        DataType.MMT_DATA_IP_NET,
        DataType.MMT_DATA_IP6_ADDR,
    }
)

#: What to use instead of a type that mmt-dpi gives no size (a ``size`` of 0
#: in the SDK profile): the sized type of the same value; ``MMT_BINARY_DATA``
#: for any other.
_SIZED_ALTERNATIVE = {
    DataType.MMT_DATA_CHAR: "MMT_U8_DATA",
    DataType.MMT_DATA_PORT: "MMT_U16_DATA",
    DataType.MMT_DATA_IP_NET: "MMT_DATA_IP_ADDR",
}

#: The types stored as a byte count and the bytes (``mmt_binary_data_t``).
_BINARY_TYPES = frozenset(
    {DataType.MMT_BINARY_DATA, DataType.MMT_STRING_DATA, DataType.MMT_BINARY_VAR_DATA}
)

#: Checked ``int64_t`` arithmetic helpers, by operator, in emission order.
_CHECKED = {
    BinaryOperator.ADD: "add",
    BinaryOperator.SUB: "sub",
    BinaryOperator.MUL: "mul",
    BinaryOperator.DIV: "div",
}
_C_OPERATOR = {
    BinaryOperator.EQ: "==",
    BinaryOperator.NE: "!=",
    BinaryOperator.GT: ">",
    BinaryOperator.LT: "<",
    BinaryOperator.GE: ">=",
    BinaryOperator.LE: "<=",
    BinaryOperator.AND: "&&",
    BinaryOperator.OR: "||",
}

_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_ARRAY = re.compile(r"(.+)\[(\d+)\]")


class GenerationError(Exception):
    """The model cannot be generated; ``diagnostics`` says why (``model.*``)."""

    def __init__(self, diagnostics: Sequence[Diagnostic]) -> None:
        self.diagnostics = tuple(diagnostics)
        super().__init__(self.diagnostics[0].message)


def c_name(name: str) -> str:
    """A model name as a C identifier: a C keyword gets a trailing ``_``."""
    return f"{name}_" if name in C_KEYWORDS else name


def c_int(value: int) -> str:
    """An integer as a C constant of type ``int`` or ``int64_t``; raises
    ``ValueError`` outside ``int64_t``."""
    if not _INT64_MIN <= value <= _INT64_MAX:
        raise ValueError(f"{value} does not fit in int64_t")
    if value == _INT64_MIN:
        return "INT64_MIN"
    if -_INT_MAX <= value <= _INT_MAX:
        return str(value) if value >= 0 else f"({value})"
    text = f"INT64_C({abs(value)})"
    return text if value >= 0 else f"(-{text})"


def _declaration(returns: str, name: str, params: Sequence[Param]) -> str:
    sep = "" if returns.endswith("*") else " "
    args = ", ".join(p.declaration for p in params) or "void"
    return f"{returns}{sep}{name}({args})"


# --- the SDK, through the profile --------------------------------------------


class _Sdk:
    """SDK names, looked up in the profile (``KeyError`` for a name it does
    not have); records the headers that declare the names used."""

    def __init__(self, profile: Profile) -> None:
        self.profile = profile
        self.used: set[str] = set()
        self._types: dict[str, str] = {}
        for t in profile.types:
            self._types[t.name] = t.header
        for s in profile.structs:
            self._types[s.name] = s.header
        for cb in profile.callbacks:
            self._types[cb.typedef] = cb.header

    def includes(self, exclude: Iterable[str] = ()) -> tuple[str, ...]:
        """The headers used, in the profile's order, without ``exclude``."""
        skip = set(exclude)
        return tuple(
            h.name for h in self.profile.headers if h.name in self.used and h.name not in skip
        )

    def type_text(self, text: str) -> str:
        """A C type written with SDK type names (``const ipacket_t *``)."""
        for word in _IDENT.findall(text):
            header = self._types.get(word)
            if header is not None:
                self.used.add(header)
        return text

    def type(self, name: str) -> str:
        """An SDK type, struct or callback typedef."""
        if name not in self._types:
            raise KeyError(f"SDK profile {self.profile.version} has no type {name}")
        self.used.add(self._types[name])
        return name

    def field(self, struct: str, name: str) -> tuple[str, str]:
        """A field of an SDK struct: its name and C type."""
        for f in self.profile.struct(struct).fields:
            if f.name == name:
                self.type(struct)
                return f.name, self.type_text(f.type)
        raise KeyError(f"SDK profile {self.profile.version}: {struct} has no field {name}")

    def constant(self, name: str) -> str:
        """An SDK constant (a macro or an enumerator)."""
        self.used.add(self.profile.constant(name).header)
        return name

    def function(self, name: str) -> str:
        """A registration call or helper."""
        fn = self.profile.function(name)
        self.used.add(fn.header)
        return fn.name

    def callback(self, role: str) -> Callback:
        """The callback of a role, its types recorded."""
        cb = self.profile.callback(role)
        self.type_text(cb.returns)
        for p in cb.params:
            self.type_text(p.type)
        return cb

    def logger(self, level: str) -> str:
        """A logger macro: ``error``, ``warn``, ``info`` or ``debug``."""
        lg = self.profile.logger
        self.used.add(lg.header)
        name: str = getattr(lg, level)
        return name


# --- the context the templates print ------------------------------------------


@dataclass(frozen=True)
class Hook:
    """A function the user defines in ``src/<label>_impl.c`` (plan decision 3):
    ``role`` is the profile callback role it implements, ``attribute`` the key
    of the attribute an extraction hook extracts."""

    name: str
    role: str
    returns: str
    params: tuple[Param, ...]
    doc: str
    attribute: str | None = None

    @property
    def declaration(self) -> str:
        """``int name(const ipacket_t *packet, ...)``."""
        return _declaration(self.returns, self.name, self.params)


@dataclass(frozen=True)
class CDefine:
    """A model define, ``#define name value``; ``alias_of`` for a comment."""

    name: str
    value: str
    alias_of: str | None


@dataclass(frozen=True)
class CMember:
    """A struct member, ``type name[array];``, at wire offset ``offset``."""

    type: str
    name: str
    array: str
    offset: int
    comment: str


@dataclass(frozen=True)
class CStruct:
    """A model struct, or the helper struct of a bitfield run."""

    tag: str
    members: tuple[CMember, ...]
    packed: bool
    size: int
    comment: str
    helper: bool


@dataclass(frozen=True)
class CGuard:
    """An enclosing ``if``: ``condition`` (C) must be true (``holds``) or false."""

    condition: str
    holds: bool


@dataclass(frozen=True)
class CAttribute:
    """One attribute: its id, its table row and the functions that extract it.

    ``kind`` picks the extraction template: ``integer``, ``bytes``,
    ``binary``, ``pointer``, ``raw`` or ``hook``. A function name is ``None``
    when that function is not emitted.
    """

    key: str
    id: int
    enum: str
    alias_macro: str
    comment: str
    kind: str
    # The row of the attribute table.
    data_type: str
    data_len: str
    position: str
    scope: str
    extraction: str
    # The guards, then the offset and length (``place``).
    guards: tuple[CGuard, ...]
    place: str | None
    offset: str | None
    length: str | None
    length_checked: bool
    reads_packet: bool
    # Integers: ``get`` reads the value; ``val``, ``offset_fn`` and
    # ``length_fn`` serve the expressions that refer to this attribute.
    get: str | None
    val: str | None
    offset_fn: str | None
    length_fn: str | None
    store_type: str | None
    width: str | None
    # The largest per-packet length (``length_checked``): the bytes of
    # ``store_type``.
    length_max: int
    shift: int
    mask: str | None
    # Bytes, binary and raw values.
    capacity: str | None
    binary_type: str | None
    binary_len: str | None
    binary_len_type: str | None
    binary_data: str | None
    terminate: bool
    # The generated extraction function (``None`` when the table names the
    # user hook itself), and the user hook.
    extract_fn: str | None
    hook: str | None


@dataclass(frozen=True)
class CCase:
    """A classifynext case, or ``default`` (``label`` ``None``)."""

    label: str | None
    comment: str
    proto: str | None
    proto_comment: str
    offset: str | None
    fallthrough: bool
    brk: bool


@dataclass(frozen=True)
class CClassify:
    """The generated classify_next: the classifynext switch."""

    name: str
    declaration: str
    packet: str
    index: str
    subject: str
    cases: tuple[CCase, ...]
    offset_type: str
    offset_max: str


@dataclass(frozen=True)
class CCall:
    """A registration call of ``init_<label>_proto_struct``: ``checked`` when
    it returns a status, with ``failure`` logged when that status is false."""

    text: str
    checked: bool
    failure: str


@dataclass(frozen=True)
class Context:
    """Everything the templates print. ``sdk`` maps the role of each SDK name
    the templates use to that name, resolved in the profile."""

    label: str
    lc: str
    uc: str
    name: str
    id: int
    profile: str
    header: str
    source: str
    guard: str
    proto_macro: str
    proto_alias_macro: str
    nb: str
    metadata: str
    init: str
    init_declaration: str
    init_proto_declaration: str
    h_includes: tuple[str, ...]
    c_includes: tuple[str, ...]
    defines: tuple[CDefine, ...]
    attributes: tuple[CAttribute, ...]
    attributes_by_id: tuple[CAttribute, ...]
    structs: tuple[CStruct, ...]
    hooks: tuple[Hook, ...]
    classify: CClassify | None
    calls: tuple[CCall, ...]
    checked: tuple[str, ...]
    read: str | None
    bytes: str | None
    little_endian: bool
    helper_params: str
    helper_args: str
    extraction_params: str
    extraction_args: str
    packet: str
    index: str
    data: str
    sdk: Mapping[str, str]


# --- expressions -------------------------------------------------------------


class _Expressions:
    """Renders expressions to C, as ``int64_t`` values.

    A run-time expression may fail (an absent attribute, an overflow, a
    division by zero): it then clears the ``ok`` local of the function that
    evaluates it, through the ``&ok`` argument of the calls it makes. A folded
    expression is its number (bug 5, 6, 7 and 19 were folding bugs, T1.3).
    """

    def __init__(self, lc: str, model: AnalysedModel) -> None:
        self.lc = lc
        self.model = model
        self.vals: set[str] = set()
        #: The first run-time reference to each attribute, by key, and its function.
        self.refs: dict[str, tuple[str, Span]] = {}
        self.offsets: set[str] = set()
        self.lengths: set[str] = set()
        self.checked: set[str] = set()
        self.errors: list[Diagnostic] = []

    def number(self, value: int, span: Span) -> str:
        try:
            return c_int(value)
        except ValueError:
            self.errors.append(
                Diagnostic(
                    Severity.ERROR,
                    "model.out-of-range",
                    f"{value} does not fit in the 64-bit signed arithmetic of the generated C",
                    hint="use a value from -2^63 to 2^63-1",
                    location=span.location(),
                )
            )
            return "0"

    def render(self, expr: Expr, packet: str, index: str) -> tuple[str, bool]:
        """The C text, and whether it reads the packet (uses ``packet`` and
        ``index``)."""
        reads = False

        def walk(e: Expr) -> str:
            nonlocal reads
            if e.value is not None:
                return self.number(e.value, e.span)
            if isinstance(e, (ValueRef, OffsetRef, LengthRef)):
                key = self.model.attribute(e.attribute).key
                reads = True
                if isinstance(e, ValueRef):
                    self.vals.add(key)
                    what = "val"
                elif isinstance(e, OffsetRef):
                    self.offsets.add(key)
                    what = "offset"
                else:
                    self.lengths.add(key)
                    what = "length"
                pdl_function = {"val": "val", "offset": "offset", "length": "len"}[what]
                self.refs.setdefault(key, (pdl_function, e.span))
                return f"{self.lc}_{what}_{key}({packet}, {index}, &ok)"
            assert isinstance(e, Binary)  # Const, SizeOfType and Swap always fold
            left, right = walk(e.left), walk(e.right)
            checked = _CHECKED.get(e.op)
            if checked is not None:
                self.checked.add(checked)
                return f"{self.lc}_{checked}({left}, {right}, &ok)"
            return f"({left} {_C_OPERATOR[e.op]} {right})"

        return walk(expr), reads


# --- the builder -------------------------------------------------------------


def _kind(attribute: AnalysedAttribute) -> str:
    dt = attribute.data_type
    if attribute.is_hook:
        return "hook"
    if dt in INTEGER_TYPES:
        return "integer"
    if dt in _BYTE_TYPES:
        return "bytes"
    if dt in _BINARY_TYPES:
        return "binary"
    if dt is DataType.MMT_DATA_POINTER:
        return "pointer"
    return "raw"


def _plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


@dataclass
class _Place:
    guards: tuple[CGuard, ...]
    offset: str | None
    length: str | None
    reads: bool


class _Builder:
    def __init__(self, model: AnalysedModel, profile: Profile) -> None:
        self.model = model
        self.profile = profile
        label = model.protocol.label
        self.lc = label.lower()
        self.uc = label.upper()
        self.h = _Sdk(profile)
        self.c = _Sdk(profile)
        self.exprs = _Expressions(self.lc, model)
        self.warnings: list[Diagnostic] = []
        self.errors: list[Diagnostic] = []
        self.sdk: dict[str, str] = {}
        extraction = self.c.callback("attribute_extraction")
        self.h.callback("attribute_extraction")
        self.extraction = extraction
        self.packet = extraction.params[0].name
        self.index = extraction.params[1].name
        self.data = extraction.params[2].name

    # --- diagnostics ---

    def _diag(
        self, severity: Severity, code: str, message: str, hint: str, span: Span | None
    ) -> Diagnostic:
        location = None if span is None else span.location()
        return Diagnostic(severity, code, message, hint=hint, location=location)

    def error(self, code: str, message: str, hint: str, span: Span | None) -> None:
        self.errors.append(self._diag(Severity.ERROR, code, message, hint, span))

    def warn(self, code: str, message: str, hint: str, span: Span | None) -> None:
        self.warnings.append(self._diag(Severity.WARNING, code, message, hint, span))

    # --- structs (header) ---

    def structs(self) -> tuple[CStruct, ...]:
        tags = {s.key: c_name(s.name) for s in self.model.structs}
        order = (
            "little-endian" if self.model.protocol.byte_order is ByteOrder.LITTLE else "network"
        )
        out: list[CStruct] = []
        for s in self.model.structs:  # declaration order, not a hash order (bug 18)
            members: list[CMember] = []
            for run in s.runs:
                bits = ", ".join(
                    f"{f.name}:{f.bitfield.bit_width}"
                    for f in s.fields
                    if f.bitfield is not None and f.bitfield.unit_offset == run.offset
                )
                out.append(
                    CStruct(
                        tag=run.helper_name,
                        members=(CMember(run.c_type, "unit", "", 0, ""),),
                        packed=False,
                        size=run.width,
                        comment=(
                            f"The storage unit of {bits} in struct {tags[s.key]}, in {order}"
                            " byte order on the wire. Each field counts from the unit's most"
                            " significant bit."
                        ),
                        helper=True,
                    )
                )
            runs = {r.offset: r for r in s.runs}
            for f in s.fields:
                if f.bitfield is not None:
                    run = runs[f.bitfield.unit_offset]
                    if run.fields[0] != f.name:
                        continue
                    members.append(
                        CMember(
                            f"struct {run.helper_name}",
                            run.helper_name,
                            "",
                            run.offset,
                            "bitfields " + ", ".join(run.fields),
                        )
                    )
                    continue
                c_type, array = f.c_type, ""
                match = _ARRAY.fullmatch(c_type)
                if match:
                    c_type, array = match.group(1), match.group(2)
                if f.kind is FieldKind.STRUCT:
                    c_type = f"struct {tags[self.model.struct(c_type.split()[-1]).key]}"
                members.append(CMember(c_type, c_name(f.name), array, f.offset, f.data_type.value))
            layout = "packed: C padding would move its fields" if s.needs_packing else "no padding"
            out.append(
                CStruct(
                    tag=tags[s.key],
                    members=tuple(members),
                    packed=s.needs_packing,
                    size=s.size,
                    comment=f"struct {s.name}: {_plural(s.size, 'byte')} on the wire ({layout}).",
                    helper=False,
                )
            )
        return tuple(out)

    # --- attributes ---

    def place(self, a: AnalysedAttribute) -> _Place:
        reads = False
        guards: list[CGuard] = []
        for g in a.guards:
            value = g.condition.value
            if value is not None:
                # A folded condition: true or false for every packet.
                if (value != 0) == g.holds:
                    continue
                guards.append(CGuard("0" if g.holds else "1", g.holds))
                continue
            text, r = self.exprs.render(g.condition, self.packet, self.index)
            reads = reads or r
            guards.append(CGuard(text, g.holds))
        offset = length = None
        if a.offset is not None:
            offset, r = self.exprs.render(a.offset, self.packet, self.index)
            reads = reads or r
            if a.length is not None:
                length, r = self.exprs.render(a.length, self.packet, self.index)
                reads = reads or r
        return _Place(tuple(guards), offset, length, reads)

    def storage(self, a: AnalysedAttribute, kind: str) -> tuple[str, str | None, str | None]:
        """The table's ``data_len``, and the capacity or the struct of the
        stored value.

        mmt-dpi registers an attribute only if its ``data_len`` is at most
        its type's SDK size, or 0 when that size is 0, and sizes the
        attribute's buffer from both. A type of size 0 would get a 0-byte
        buffer, which no extraction can write: it is a model error, and so
        is a constant length above the size."""
        dt, sdk = a.data_type, self.c
        size = self.profile.data_size(dt.value)
        if size == 0:
            self.error(
                "model.type-size",
                f"attribute {a.name} ({dt.value}) has a type with no size in mmt-dpi"
                f" {self.profile.version}: the SDK registers it only with data_len 0, and"
                " gives it no buffer to extract into",
                f"use {_SIZED_ALTERNATIVE.get(dt, 'MMT_BINARY_DATA')} instead",
                a.span,
            )
            return "0", "0", None
        if dt in _INTEGER_STORAGE:
            return str(_INTEGER_STORAGE[dt][1]), None, None
        if dt is DataType.MMT_DATA_MAC_ADDR:
            cap = f"sizeof({sdk.type('mac_addr_t')})"
            return cap, cap, None
        if dt is DataType.MMT_DATA_IP6_ADDR:
            cap = sdk.constant("IPv6_ALEN")
            return cap, cap, None
        if dt in (DataType.MMT_DATA_IP_ADDR, DataType.MMT_DATA_IP_NET):
            return "4", "4", None
        if dt is DataType.MMT_BINARY_VAR_DATA:
            st = sdk.type("mmt_binary_var_data_t")
            return f"sizeof({st})", None, st
        if dt in _BINARY_TYPES:
            return sdk.constant("BINARY_64DATA_TYPE_LEN"), None, sdk.type("mmt_binary_data_t")
        if dt is DataType.MMT_DATA_POINTER:
            return "sizeof(void *)", None, None
        # Any other type: a copy of a constant number of bytes.
        length = a.length_value
        if length is not None and length > size:
            self.error(
                "model.type-size",
                f"attribute {a.name} ({dt.value}) has data_len {length}, but mmt-dpi"
                f" {self.profile.version} registers this type with at most"
                f" {_plural(size, 'byte')}",
                f"give a data_len of at most {size}, or use MMT_BINARY_DATA",
                a.length.span if a.length is not None else a.span,
            )
            return "0", "0", None
        if length is not None:
            return str(length), str(length), None
        if a.length is None:
            self.error(
                "model.missing-length",
                f"attribute {a.name} ({dt.value}) has no data_len, and its type has no fixed"
                " width",
                "give data_len: mmt-dpi stores a value of that many bytes",
                a.span,
            )
        else:
            self.error(
                "model.variable-length",
                f"attribute {a.name} ({dt.value}) has a data_len known only per packet, but"
                " mmt-dpi stores a value of this type in a buffer of a fixed size",
                "give a constant data_len, or use MMT_BINARY_DATA for bytes of variable length",
                a.length.span,
            )
        return "0", "0", None

    def check_integer(self, a: AnalysedAttribute) -> None:
        length = a.length_value
        if a.data_type not in INTEGER_TYPES or length is None:
            return
        span = a.length.span if a.length is not None else a.span
        if not 1 <= length <= 8:
            self.error(
                "model.integer-length",
                f"attribute {a.name} ({a.data_type.value}) has data_len {length},"
                " but an integer is read from 1 to 8 bytes",
                "give a data_len from 1 to 8, or use MMT_BINARY_DATA for a byte string",
                span,
            )
            return
        stored = _INTEGER_STORAGE[a.data_type][1]
        # A bitfield reads its storage unit and masks its bits, which the
        # semantics keep within the type; a user hook stores the value
        # itself, and its data_len only places what follows.
        if a.bitfield is None and not a.is_hook and length > stored:
            self.error(
                "model.integer-length",
                f"attribute {a.name} ({a.data_type.value}) has data_len {length}, but its"
                f" value is stored in {_plural(stored, 'byte')}: the high bytes would be lost",
                f"give a data_len of at most {stored}, or a wider integer type (MMT_U64_DATA"
                " holds 8 bytes)",
                span,
            )

    def describe(self, a: AnalysedAttribute) -> str:
        if a.is_hook:
            what = "extracted by a user hook (no offset)"
        else:
            off, ln = a.offset_value, a.length_value
            size = "a length computed per packet" if ln is None else _plural(ln, "byte")
            at = "an offset computed per packet" if off is None else f"offset {off}"
            what = f"{size} at {at}"
        bf = a.bitfield
        if bf is not None:
            what += f", bits {bf.bit_offset}-{bf.bit_offset + bf.bit_width - 1}"
        if a.guards:
            what += ", when its conditions hold"
        return f"{a.name}: {a.data_type.value}, {what}"

    def attributes(self) -> tuple[CAttribute, ...]:
        lc, uc, sdk, model = self.lc, self.uc, self.c, self.model
        # Ids as Java gives them (T1.6 parity): unconditional attributes first,
        # then the conditional ones, each in source order.
        ordered = [a for a in model.attributes if not a.guards]
        ordered += [a for a in model.attributes if a.guards]
        ids = {a.key: n for n, a in enumerate(ordered, start=1)}
        places = {a.key: self.place(a) for a in model.attributes}
        out: list[CAttribute] = []
        for a in model.attributes:
            key, kind = a.key, _kind(a)
            has_place = kind != "hook"
            self.check_integer(a)
            data_len, capacity, binary_type = self.storage(a, kind)
            place = places[key]
            integer = kind == "integer"
            hook = f"{lc}_hook_extract_{key}" if kind == "hook" else None
            # An unconditional hook is the table's extraction function itself;
            # a conditional one is called once its guards hold (bug 14).
            extract_fn = None if kind == "hook" and not a.guards else f"{lc}_{key}_extraction"
            width: str | None = None
            shift, mask = 0, None
            bf = a.bitfield
            if integer and bf is not None:
                width, shift = str(bf.unit_width), bf.shift
                mask = "UINT64_MAX" if bf.bit_width == 64 else f"UINT64_C(0x{bf.mask:x})"
            elif integer and a.length_value is not None:
                width = str(a.length_value)
            length_max = _INTEGER_STORAGE[a.data_type][1] if integer else 0
            binary_len = binary_len_type = binary_data = None
            if binary_type is not None:
                binary_len, binary_len_type = sdk.field(binary_type, "len")
                binary_data = sdk.field(binary_type, "data")[0]
            out.append(
                CAttribute(
                    key=key,
                    id=ids[key],
                    enum=f"{uc}_{key.upper()}",
                    alias_macro=f"{uc}_{key.upper()}_ALIAS",
                    comment=self.describe(a),
                    kind=kind,
                    data_type=sdk.constant(a.data_type.value),
                    data_len=data_len,
                    position=(
                        c_int(a.offset_value)
                        if a.offset_value is not None
                        else sdk.constant("POSITION_NOT_KNOWN")
                    ),
                    scope=sdk.constant(a.scope.value),
                    extraction=extract_fn or str(hook),
                    guards=place.guards,
                    place=None if kind == "hook" else f"{lc}_place_{key}",
                    offset=place.offset,
                    length=place.length,
                    length_checked=integer and width is None,
                    reads_packet=place.reads,
                    get=f"{lc}_get_{key}" if integer else None,
                    val=f"{lc}_val_{key}" if integer and key in self.exprs.vals else None,
                    offset_fn=(
                        f"{lc}_offset_{key}" if has_place and key in self.exprs.offsets else None
                    ),
                    length_fn=(
                        f"{lc}_length_{key}" if has_place and key in self.exprs.lengths else None
                    ),
                    store_type=_INTEGER_STORAGE[a.data_type][0] if integer else None,
                    width=width,
                    length_max=length_max,
                    shift=shift,
                    mask=mask,
                    capacity=capacity,
                    binary_type=binary_type,
                    binary_len=binary_len,
                    binary_len_type=binary_len_type,
                    binary_data=binary_data,
                    terminate=a.data_type is DataType.MMT_STRING_DATA,
                    extract_fn=extract_fn,
                    hook=hook,
                )
            )
        return tuple(out)

    def byte_order_warning(self) -> None:
        """No encoding (or ASCII/UNICODE) gives no byte order: multi-byte
        integers are read in network byte order, with a warning (bug 10)."""
        p = self.model.protocol
        if p.byte_order is not ByteOrder.UNSPECIFIED:
            return
        for a in self.model.attributes:
            if a.is_hook or a.data_type not in INTEGER_TYPES:
                continue
            width = a.bitfield.unit_width if a.bitfield is not None else a.length_value
            if width is None or width > 1:
                encoding = "no encoding" if p.encoding is None else f"encoding {p.encoding.value}"
                self.warn(
                    "model.default-byte-order",
                    f"{encoding} gives no byte order: multi-byte integers such as {a.name} are"
                    " read in network byte order (big-endian)",
                    'set encoding = "network" or "host"',
                    a.span,
                )
                return

    # --- hooks (header) and classification ---

    def hook(self, role: str, name: str, doc: str, attribute: str | None = None) -> Hook:
        cb = self.h.callback(role)
        self.c.callback(role)
        return Hook(name, role, cb.returns, cb.params, doc, attribute)

    def hooks(self, attributes: Sequence[CAttribute]) -> tuple[Hook, ...]:
        lc, p = self.lc, self.model.protocol
        out = [
            self.hook(
                "attribute_extraction",
                str(a.hook),
                f"Extracts attribute {a.key}, which has no offset in the model, into"
                f" {self.data}->data; returns 1 when extracted, 0 when absent.",
                a.key,
            )
            for a in attributes
            if a.hook is not None
        ]
        roles: list[tuple[bool, str, str, str]] = [
            (p.context, "proto_context_init", "context_init",
             'Creates the protocol context (context = "true"); returns it.'),
            (p.context, "proto_context_cleanup", "context_cleanup",
             "Frees the protocol context."),
            (p.session_context, "session_data_init", "session_data_init",
             'Creates the session data of a new session (session_context = "true").'),
            (p.session_context, "session_data_cleanup", "session_data_cleanup",
             "Frees the session data of a session."),
            (p.session_context, "session_data_analysis", "session_data_analysis",
             "Updates the session data from a packet."),
            (p.session, "sessionizer", "sessionizer",
             'Finds or creates the session of a packet (session = "true"); sets *is_new.'),
            (p.session, "session_context_cleanup", "session_cleanup",
             "Frees a session when it times out."),
            (p.session, "session_key_comparison", "session_compare",
             "Compares two session keys."),
            (p.encapsulation and self.model.classify_next is None, "classification",
             "classify_next",
             'Classifies the next protocol (encapsulation = "true" without a classifynext'
             " block): record it with set_classified_proto() and return the verdict."),
        ]  # fmt: skip
        for enabled, role, name, doc in roles:
            if enabled:
                out.append(self.hook(role, f"{lc}_hook_{name}", doc))
        return tuple(out)

    def classify(self) -> CClassify | None:
        switch = self.model.classify_next
        p = self.model.protocol
        if switch is None:
            return None
        if not p.encapsulation:
            # Java dropped the block silently (bug 21): it is generated.
            self.warn(
                "model.classifynext-without-encapsulation",
                'the classifynext block is generated although encapsulation is "false"',
                'set encapsulation = "true"',
                switch.span,
            )
        cb = self.c.callback("classification")
        packet, index = cb.params[0].name, cb.params[1].name
        subject, _ = self.exprs.render(switch.subject, packet, index)
        entries: list[tuple[str | None, str, tuple[object, ...], bool]] = [
            (
                self.exprs.number(case.label, case.span),
                "" if case.alias_of is None else case.alias_of,
                case.statements,
                case.has_break,
            )
            for case in switch.cases
        ]
        if switch.default is not None:
            d = switch.default
            entries.append((None, "", d.statements, d.has_break))
        cases: list[CCase] = []
        for n, (label, comment, statements, has_break) in enumerate(entries):
            proto = offset = None
            proto_comment = ""
            for st in statements:
                if isinstance(st, SetNextProto):
                    proto = self.exprs.number(st.proto.id, st.proto.span)
                    proto_comment = st.proto.alias_of or ""
                elif isinstance(st, SetNextOffset):
                    offset, _ = self.exprs.render(st.offset, packet, index)
            # A case with statements and no break falls through to the next
            # label (C semantics); the last one just ends the switch.
            last = n == len(entries) - 1
            has_code = proto is not None or offset is not None
            fallthrough = not has_break and has_code and not last
            cases.append(
                CCase(
                    label,
                    comment,
                    proto,
                    proto_comment,
                    offset,
                    fallthrough=fallthrough,
                    # A label must be followed by a statement, even the last.
                    brk=has_break or last,
                )
            )
        offset_name, offset_type = self.c.field("classified_proto_t", "offset")
        self.sdk["next_offset"] = offset_name
        self.sdk["next_status"] = self.c.field("classified_proto_t", "status")[0]
        self.sdk["next_proto"] = self.c.field("classified_proto_t", "proto_id")[0]
        self.sdk["next_proto_type"] = self.c.field("classified_proto_t", "proto_id")[1]
        self.sdk["classified_proto_t"] = self.c.type("classified_proto_t")
        self.sdk["classified"] = self.c.constant("Classified")
        self.sdk["matched"] = self.c.constant("MMT_CLASSIFY_MATCHED")
        self.sdk["skip"] = self.c.constant("MMT_CLASSIFY_SKIP")
        self.sdk["set_classified_proto"] = self.c.function("set_classified_proto")
        name = f"{self.lc}_classify_next"
        return CClassify(
            name=name,
            declaration=_declaration(cb.returns, name, cb.params),
            packet=packet,
            index=index,
            subject=subject,
            cases=tuple(cases),
            offset_type=offset_type,
            offset_max=_STDINT_MAX.get(offset_type, "UINT16_MAX"),
        )

    # --- registration ---

    def call(self, name: str, args: Mapping[str, str], failure: str) -> CCall:
        """A registration call; each argument is picked by its parameter's
        type (a callback typedef, ``protocol_t *``, ``mmt_opaque_t``...)."""
        fn = self.profile.function(name)
        self.c.function(name)
        values = []
        for param in fn.params:
            if param.type not in args:
                raise KeyError(f"{name}: no argument for parameter {param.name} ({param.type})")
            values.append(args[param.type])
        checked = fn.returns != "void"
        return CCall(f"{fn.name}({', '.join(values)})", checked, failure)

    def calls(self, classify: CClassify | None, hooks: Sequence[Hook]) -> tuple[CCall, ...]:
        p = self.model.protocol
        sdk = self.c
        protocol_t = f"{sdk.type('protocol_t')} *"
        by_role = {h.role: h.name for h in hooks if h.attribute is None}
        typedef = {cb.role: cb.typedef for cb in self.profile.callbacks}
        base = {protocol_t: "protocol_struct", sdk.type("mmt_opaque_t"): "NULL"}
        out: list[CCall] = []
        classifier = classify.name if classify is not None else by_role.get("classification")
        if classifier is not None:
            out.append(
                self.call(
                    "register_classification_function",
                    {**base, sdk.type(typedef["classification"]): classifier},
                    "cannot register the classify_next function",
                )
            )
        groups = (
            (
                p.context,
                "register_proto_context_init_cleanup_function",
                ("proto_context_init", "proto_context_cleanup"),
            ),
            (
                p.session_context,
                "register_session_data_initialization_function",
                ("session_data_init",),
            ),
            (
                p.session_context,
                "register_session_data_cleanup_function",
                ("session_data_cleanup",),
            ),
            (
                p.session_context,
                "register_session_data_analysis_function",
                ("session_data_analysis",),
            ),
            (
                p.session,
                "register_sessionizer_function",
                ("sessionizer", "session_context_cleanup", "session_key_comparison"),
            ),
        )
        for enabled, name, roles in groups:
            if enabled:
                args = dict(base)
                for role in roles:
                    args[sdk.type(typedef[role])] = by_role[role]
                out.append(self.call(name, args, f"{name} failed"))
        return tuple(out)

    # --- names ---

    def collisions(self, ctx: Context) -> None:
        """Two generated C names that are the same identifier (bug 15: an
        attribute ``h`` and the include guard), or a model name that a macro
        of the generated code would replace."""
        names: list[tuple[str, str]] = [
            (ctx.guard, "the include guard"),
            (ctx.proto_macro, "the protocol id macro"),
            (ctx.proto_alias_macro, "the protocol name macro"),
            (ctx.nb, "the attribute count"),
            (ctx.metadata, "the attribute table"),
            (ctx.init, "the init function"),
            (f"{ctx.lc}_attributes", "the attribute enum"),
        ]
        for d in ctx.defines:
            names.append((d.name, f"define {d.name}"))
        for a in ctx.attributes:
            what = f"attribute {a.key}"
            names += [(a.enum, f"the id of {what}"), (a.alias_macro, f"the alias of {what}")]
            for fn in (a.place, a.get, a.val, a.offset_fn, a.length_fn, a.extract_fn, a.hook):
                if fn is not None:
                    names.append((fn, f"a function of {what}"))
        for h in ctx.hooks:
            if h.attribute is None:
                names.append((h.name, f"the {h.role} hook"))
        if ctx.classify is not None:
            names.append((ctx.classify.name, "the classify_next function"))
        for helper in (ctx.read, ctx.bytes):
            if helper is not None:
                names.append((helper, "a byte-reading helper"))
        for checked in ctx.checked:
            names.append((f"{ctx.lc}_{checked}", "an arithmetic helper"))
        seen: dict[str, str] = {}
        for name, what in names:
            first = seen.get(name)
            if first is not None:
                self.error(
                    "model.name-collision",
                    f"{what} and {first} are both named {name} in the generated C",
                    "rename the attribute, struct, define or protocol label",
                    None,
                )
            else:
                seen[name] = what
        # Struct tags and members are other name spaces, but a macro still
        # replaces them.
        macros = {
            ctx.guard,
            ctx.proto_macro,
            ctx.proto_alias_macro,
            *(a.alias_macro for a in ctx.attributes),
            *(d.name for d in ctx.defines),
        }
        tags: dict[str, list[str]] = {}
        for s in ctx.structs:
            tags.setdefault(s.tag, []).append(f"struct {s.tag}")
            members: set[str] = set()
            for m in s.members:
                if m.name in members:
                    self.error(
                        "model.name-collision",
                        f"struct {s.tag} has two members named {m.name} in the generated C",
                        "rename one of the fields (a C keyword gets a trailing _)",
                        None,
                    )
                members.add(m.name)
                if m.name in macros:
                    self.error(
                        "model.name-collision",
                        f"member {m.name} of struct {s.tag} is also a macro of the generated C",
                        "rename the field or the define",
                        None,
                    )
            if s.tag in macros:
                self.error(
                    "model.name-collision",
                    f"struct {s.tag} is also a macro of the generated C",
                    "rename the struct or the define",
                    None,
                )
        for tag, whats in tags.items():
            if len(whats) > 1:
                self.error(
                    "model.name-collision",
                    f"two structs are named {tag} in the generated C",
                    "rename the struct (a C keyword gets a trailing _)",
                    None,
                )

    def define_uses(self, defines: Sequence[CDefine], texts: Sequence[str]) -> None:
        """A model define is a macro of the generated header, so it must not
        be any other identifier the generated code uses (``data``, an SDK
        name, ...)."""
        if not defines:
            return
        tokens: set[str] = set()
        names = {d.name for d in defines}
        for text in texts:
            for line in _strip_comments_and_strings(text).splitlines():
                words = _IDENT.findall(line)
                if len(words) >= 2 and words[0] == "define" and words[1] in names:
                    words = words[2:]
                tokens.update(words)
        for d in defines:
            if d.name in tokens:
                self.error(
                    "model.name-collision",
                    f"define {d.name} is also a name the generated C uses: the macro would"
                    " replace it",
                    "rename the define",
                    None,
                )

    def build(self) -> Context:
        model, lc, uc, sdk = self.model, self.lc, self.uc, self.c
        p = model.protocol
        defines = tuple(
            CDefine(c_name(d.name), self.exprs.number(d.value, d.span), d.alias_of)
            for d in model.defines
        )
        structs = self.structs()
        # The classifynext expressions first: the attributes they read need
        # their val() functions.
        classify = self.classify()
        attributes = self.attributes()
        self.byte_order_warning()
        hooks = self.hooks(attributes)
        calls = self.calls(classify, hooks)
        reads = any(a.kind != "hook" for a in attributes)
        integers = any(a.kind == "integer" for a in attributes)
        init_cb = self.h.callback("init_proto")
        self.c.callback("init_proto")
        # Each SDK name is looked up (and its header included) only when the
        # templates print it.
        names = self.sdk
        if reads:
            names.update(
                ipacket_data=sdk.field("ipacket_t", "data")[0],
                ipacket_header=sdk.field("ipacket_t", "p_hdr")[0],
                caplen=sdk.field("pkthdr_t", "caplen")[0],
                offset_at=sdk.function("get_packet_offset_at_index"),
                attribute_data=sdk.field("attribute_t", "data")[0],
            )
        if attributes:
            names.update(
                register_attribute=sdk.function("register_attribute_with_protocol"),
                metadata_t=sdk.type("attribute_metadata_t"),
            )
            for f in self.profile.struct("attribute_metadata_t").fields:
                names[f"metadata_{f.name}"] = f.name
        names.update(
            id_by_name=sdk.function("get_protocol_id_by_name"),
            init_struct=sdk.function("init_protocol_struct_for_registration"),
            register_protocol=sdk.function("register_protocol"),
            protocol_t=sdk.type("protocol_t"),
            log_error=sdk.logger("error"),
        )
        h_includes = self.h.includes()
        c_includes = sdk.includes(exclude=h_includes)
        helper_params = ", ".join(p.declaration for p in self.extraction.params[:2])
        ctx = Context(
            label=p.label,
            lc=lc,
            uc=uc,
            name=p.name,
            id=p.id,
            profile=self.profile.version,
            header=f"{lc}_mmt_plugin.h",
            source=f"{lc}_mmt_plugin.c",
            guard=f"MMT_PLUGIN_{uc}_H",
            proto_macro=f"PROTO_{uc}",
            proto_alias_macro=f"PROTO_{uc}_ALIAS",
            nb=f"{uc}_ATTRIBUTES_NB",
            metadata=f"{lc}_attributes_metadata",
            init=f"init_{lc}_proto_struct",
            init_declaration=_declaration(init_cb.returns, f"init_{lc}_proto_struct", ()),
            init_proto_declaration=_declaration(init_cb.returns, "init_proto", init_cb.params),
            h_includes=h_includes,
            c_includes=c_includes,
            defines=defines,
            attributes=attributes,
            attributes_by_id=tuple(sorted(attributes, key=lambda a: a.id)),
            structs=structs,
            hooks=hooks,
            classify=classify,
            calls=calls,
            checked=tuple(c for c in _CHECKED.values() if c in self.exprs.checked),
            read=f"{lc}_read" if integers else None,
            bytes=f"{lc}_bytes" if reads else None,
            little_endian=p.byte_order is ByteOrder.LITTLE,
            helper_params=helper_params,
            helper_args=f"{self.packet}, {self.index}",
            extraction_params=", ".join(p.declaration for p in self.extraction.params),
            extraction_args=", ".join(p.name for p in self.extraction.params),
            packet=self.packet,
            index=self.index,
            data=self.data,
            sdk=dict(names),
        )
        self.errors += self.exprs.errors
        for a in model.attributes:
            ref = self.exprs.refs.get(a.key)
            if a.is_hook and ref is not None:
                # Only the user hook knows where a hook attribute is, and its
                # value: the generated code cannot compute either per packet.
                function, span = ref
                self.error(
                    "model.hook-value",
                    f"{function}({a.name}) refers to an attribute without an offset, which only"
                    " its user hook extracts: the generated code cannot compute it",
                    f"give {a.name} an offset (and a constant data_len), or compute it in user"
                    " code",
                    span,
                )
        self.collisions(ctx)
        return ctx


def _strip_comments_and_strings(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.DOTALL)
    text = re.sub(r"//[^\n]*", " ", text)
    return re.sub(r'"(?:[^"\\\n]|\\.)*"', '""', text)


def build(model: AnalysedModel, profile: Profile) -> tuple[Context, list[Diagnostic]]:
    """The template context of ``model`` and the generation warnings; raises
    ``GenerationError`` when the model cannot be generated."""
    builder = _Builder(model, profile)
    ctx = builder.build()
    if builder.errors:
        raise GenerationError(builder.errors)
    return ctx, builder.warnings


def check_defines(
    model: AnalysedModel, profile: Profile, ctx: Context, texts: Sequence[str]
) -> None:
    """Raise ``GenerationError`` if a model define would replace a name the
    rendered ``texts`` use (run after rendering)."""
    builder = _Builder(model, profile)
    builder.define_uses(ctx.defines, texts)
    if builder.errors:
        raise GenerationError(builder.errors)
