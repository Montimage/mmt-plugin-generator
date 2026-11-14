"""Converting a PDL v1 model to ``plugin.yaml`` (plan task T3.2, #25).

``convert(model, profile)`` analyses a parsed PDL v1 model and writes it as
``plugin.yaml`` text (``mmt_plugin.pluginyaml.dumps``), with a warning on
every construct whose meaning relied on a bug of the Java tool
(``docs/legacy/java-generator-inventory.md``, section 5). Each warning has a
``model.legacy-*`` code (``LEGACY_CODES``) and says what the Java tool did
and what mmt-plugin does instead (``docs/behaviour-changes.md``):

- ``model.legacy-sdk-conflict`` (bug 23): the protocol id or name is the
  SDK's, which the Java tool accepted and ``generate`` refuses;
- ``model.legacy-duplicate-name`` (bugs 12 and 16): a name used twice, which
  the Java tool accepted because the second is conditional or differs only
  in case;
- ``model.legacy-bitfield-order`` (plan decision 8): a bitfield run, whose
  bits are numbered from the most significant bit, not in the C compiler's
  order;
- ``model.legacy-bitfield-offset`` (bugs 2 and 3): a struct field after a
  bitfield line, or an aligned element after a struct with bitfields, which
  the Java tool placed further on;
- ``model.legacy-constant-folding`` (bug 5): an offset, data_len or
  nextoffset that the Java tool folded to a constant (its last operand is a
  literal or ``ntohs``/``ntohl``, and it is no comparison) but is not one, or
  is another number (``ntohs`` and ``ntohl`` it did not swap);
- ``model.legacy-comparison`` (bug 6): such an expression whose value
  changes because the Java tool read ``>``, ``<``, ``>=`` and ``<=`` as
  ``!=``;
- ``model.legacy-sizeof`` (bug 7): ``sizeof`` of a C or MMT type that the
  Java tool wrote into the C (an if condition, the switch subject, an
  expression it did not fold) as ``sizeof(MMT_U8_DATA)``, which is 4;
- ``model.legacy-classifynext`` (bug 21): a classifynext block without
  ``encapsulation = "true"``, which the Java tool dropped;
- ``model.legacy-ip-addr`` (bug 25): an ``MMT_DATA_IP_ADDR`` of a network
  byte order model whose offset or data_len the Java tool did not fold,
  which it byte-swapped.

The model keeps the absolute offsets the analysis computes (the format's
default). An SDK id or name conflict does not stop the conversion. When the
only errors are duplicate names the Java tool accepted, the analysis cannot
place the attributes, so the model is written with ``offsets: running``,
exactly as PDL v1 placed them. Any other error stops it: ``text`` is
``None``. ``model.default-scope`` is dropped, since an omitted ``scope`` is
packet in plugin.yaml without a warning; every other warning of the
analysis is kept.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

from mmt_plugin.diagnostics import Diagnostic, Location, Severity
from mmt_plugin.pdl import model as pdl
from mmt_plugin.pluginyaml.dump import dumps, expression_text
from mmt_plugin.sdk.profile import Profile
from mmt_plugin.semantics import SDK_CONFLICT_CODES, analyse
from mmt_plugin.semantics import model as sem

__all__ = ["LEGACY_CODES", "Conversion", "convert", "legacy_warnings"]

#: The warnings on constructs that relied on Java bugs.
LEGACY_CODES = (
    "model.legacy-sdk-conflict",
    "model.legacy-duplicate-name",
    "model.legacy-bitfield-order",
    "model.legacy-bitfield-offset",
    "model.legacy-constant-folding",
    "model.legacy-comparison",
    "model.legacy-sizeof",
    "model.legacy-classifynext",
    "model.legacy-ip-addr",
)

#: The analysis warning plugin.yaml makes moot: an omitted scope is packet.
_DROPPED = frozenset({"model.default-scope"})

_RELATIONAL = frozenset(
    {
        pdl.BinaryOperator.GT,
        pdl.BinaryOperator.LT,
        pdl.BinaryOperator.GE,
        pdl.BinaryOperator.LE,
    }
)


@dataclass(frozen=True)
class Conversion:
    """A converted model: the ``plugin.yaml`` text (``None`` when an error
    stops the conversion), the offsets it is written with, and every
    diagnostic, the ``model.legacy-*`` warnings included."""

    text: str | None
    offsets: pdl.Offsets
    diagnostics: tuple[Diagnostic, ...]


def _warning(code: str, message: str, hint: str, span: pdl.Span) -> Diagnostic:
    return Diagnostic(Severity.WARNING, code, message, hint=hint, location=span.location())


# --- names ---------------------------------------------------------------------


@dataclass(frozen=True)
class _Named:
    text: str
    kind: str  # attribute, field, struct or define
    conditional: bool


def _key(location: Location | None) -> tuple[int | None, int | None] | None:
    return None if location is None else (location.line, location.column)


def _names(model: pdl.Model) -> dict[tuple[int | None, int | None], _Named]:
    """Every name the model declares, by its line and column."""
    out: dict[tuple[int | None, int | None], _Named] = {}

    def add(name: pdl.Name, kind: str, conditional: bool) -> None:
        out[(name.span.line, name.span.column)] = _Named(name.text, kind, conditional)

    def walk(elements: tuple[pdl.AttributeElement, ...], conditional: bool) -> None:
        for el in elements:
            if isinstance(el, pdl.Attribute):
                add(el.alias, "attribute", conditional)
            elif isinstance(el, pdl.Struct):
                add(el.name, "struct", conditional)
                for element in el.elements:
                    for f in element.fields:
                        add(f.name, "field", conditional)
            else:
                walk(el.then_branch, True)
                walk(el.else_branch or (), True)

    for d in model.defines:
        add(d.name, "define", False)
    walk(model.attributes.elements, False)
    return out


def _java_accepted_duplicate(
    d: Diagnostic, names: dict[tuple[int | None, int | None], _Named]
) -> bool:
    """Whether the Java tool accepted this duplicate attribute name: it did
    not check conditional attributes (bug 12), and compared names with their
    case (bug 16)."""
    second = names.get(_key(d.location) or (None, None))
    first = names.get(_key(d.related[0].location) or (None, None)) if d.related else None
    if first is None or second is None:
        return False
    attributes = {"attribute", "field"}
    if first.kind not in attributes or second.kind not in attributes:
        return False
    return first.conditional or second.conditional or first.text != second.text


# --- the parsed model's expressions ------------------------------------------


def _elements(elements: tuple[pdl.AttributeElement, ...]) -> Iterator[pdl.AttributeElement]:
    """Every attribute, struct and conditional, in source order."""
    for el in elements:
        yield el
        if isinstance(el, pdl.Conditional):
            yield from _elements(el.then_branch)
            yield from _elements(el.else_branch or ())


def _used(model: pdl.Model) -> Iterator[tuple[str, str, pdl.Expr]]:
    """The expressions whose value the Java tool used when it folded them
    (G:779-787 and its attributes): each attribute's offset and data_len, and
    each nextoffset, with what they are and whose."""
    for el in _elements(model.attributes.elements):
        if isinstance(el, pdl.Attribute):
            for what, expr in (("offset", el.offset), ("data_len", el.data_len)):
                if expr is not None:
                    yield what, f"`{el.alias.text}`", expr
    if model.classify_next is not None:
        switch = model.classify_next.switch
        blocks = [c.statements for c in switch.cases]
        if switch.default is not None:
            blocks.append(switch.default.statements)
        for statements in blocks:
            for st in statements:
                if isinstance(st, pdl.NextOffset):
                    yield "nextoffset", "classifynext", st.value


def _texts(model: pdl.Model) -> Iterator[pdl.Expr]:
    """The expressions the Java tool always wrote into the C as text: the
    if conditions and the switch subject."""
    for el in _elements(model.attributes.elements):
        if isinstance(el, pdl.Conditional):
            yield el.condition
    if model.classify_next is not None:
        yield model.classify_next.switch.subject


def _nodes(expr: pdl.Expr) -> Iterator[pdl.Expr]:
    """Every node of ``expr``, in source order."""
    if isinstance(expr, pdl.BinaryOp):
        yield from _nodes(expr.left)
        yield expr
        yield from _nodes(expr.right)
    else:
        yield expr


# --- the Java tool's expressions (G:661-758) -----------------------------------

_COMPARISONS = frozenset({*_RELATIONAL, pdl.BinaryOperator.EQ, pdl.BinaryOperator.NE})

#: The C words of an element type, and the MMT name the Java tool wrote for
#: them (G:638-648).
_JAVA_C_NAMES = {
    "int": "MMT_U32_DATA",
    "long": "MMT_U32_DATA",
    "uint32_t": "MMT_U32_DATA",
    "short": "MMT_U16_DATA",
    "uint16_t": "MMT_U16_DATA",
    "char": "MMT_U8_DATA",
    "u_char": "MMT_U8_DATA",
    "uint8_t": "MMT_U8_DATA",
}

#: The lengths the Java tool gave the MMT types (G:609-631; 0 when it gave none).
_JAVA_MMT_LENGTHS = {
    "MMT_U8_DATA": 1,
    "MMT_U16_DATA": 2,
    "MMT_U32_DATA": 4,
    "MMT_U64_DATA": 8,
    "MMT_DATA_POINTER": 4,
    "MMT_STRING_DATA": 4,
    "MMT_DATA_IP_NET": 4,
    "MMT_DATA_MAC_ADDR": 6,
    "MMT_DATA_IP_ADDR": 4,
    "MMT_DATA_PATH": 68,
    "MMT_DATA_TIMEVAL": 8,
    "MMT_BINARY_DATA": 68,
    "MMT_DATA_IP6_ADDR": 16,
}

#: What ``sizeof`` of an enum constant (``sizeof(MMT_U16_DATA)``) is in C.
_ENUM_SIZE = 4


def _java_simple(expr: pdl.Expr) -> bool:
    """Whether the Java tool folded ``expr``: a literal or ``ntohs``/``ntohl``
    is simple, ``val()``, ``sizeof``, ``offset()`` and ``len()`` are not, a
    comparison never is, and any other operator is as simple as its last
    operand (bug 5)."""
    if isinstance(expr, (pdl.IntLiteral, pdl.ByteSwap)):
        return True
    if isinstance(expr, pdl.BinaryOp):
        return expr.op not in _COMPARISONS and _java_simple(expr.right)
    return False


def _java_value(expr: pdl.Expr) -> int | None:
    """The value the Java tool folded ``expr`` to (``val()``, ``offset()`` and
    ``len()`` are 0, ``ntohs``/``ntohl`` do not swap, every comparison but
    ``==`` is ``!=``, bug 6); ``None`` where it cannot be known (a struct's
    sizeof was a line number, bug 8) or the Java tool failed (a division by
    zero)."""
    if isinstance(expr, pdl.IntLiteral):
        return expr.value
    if isinstance(expr, pdl.ByteSwap):
        return expr.operand.value
    if isinstance(expr, (pdl.ValueOf, pdl.OffsetOf, pdl.LengthOf)):
        return 0
    if isinstance(expr, pdl.SizeOf):
        t = expr.type
        if isinstance(t, pdl.CType):
            return 4 if t.pointer else _JAVA_MMT_LENGTHS[_JAVA_C_NAMES[t.name]]
        if isinstance(t, pdl.MmtType):
            return _JAVA_MMT_LENGTHS.get(t.type.value, 0)
        return None
    left, right = _java_value(expr.left), _java_value(expr.right)
    if left is None or right is None:
        return None
    op = expr.op
    if op is pdl.BinaryOperator.OR:
        return int(left > 0 or right > 0)
    if op is pdl.BinaryOperator.AND:
        return int(left > 0 and right > 0)
    if op is pdl.BinaryOperator.EQ:
        return int(left == right)
    if op in _COMPARISONS:
        return int(left != right)
    if op is pdl.BinaryOperator.ADD:
        return left + right
    if op is pdl.BinaryOperator.SUB:
        return left - right
    if op is pdl.BinaryOperator.MUL:
        return left * right
    if right == 0:
        return None
    quotient = abs(left) // abs(right)
    return quotient if (left < 0) == (right < 0) else -quotient


def _java_sizeof_name(t: pdl.ElementType) -> str | None:
    """The MMT name the Java tool wrote in ``sizeof(...)``; ``None`` for a struct."""
    if isinstance(t, pdl.CType):
        return "MMT_DATA_POINTER" if t.pointer else _JAVA_C_NAMES[t.name]
    if isinstance(t, pdl.MmtType):
        return t.type.value
    return None


def _values(analysed: sem.AnalysedModel | None) -> dict[pdl.Span, int | None]:
    """The value of every analysed expression node (``None`` when it does
    not fold), by its span."""
    out: dict[pdl.Span, int | None] = {}
    if analysed is None:
        return out
    roots: list[sem.Expr] = []
    for a in analysed.attributes:
        if a.kind is sem.AttributeKind.PLAIN:
            roots += [e for e in (a.declared_offset, a.length) if e is not None]
    roots += [c.condition for c in analysed.conditionals]
    switch = analysed.classify_next
    if switch is not None:
        roots.append(switch.subject)
        blocks = [c.statements for c in switch.cases]
        if switch.default is not None:
            blocks.append(switch.default.statements)
        for statements in blocks:
            roots += [st.offset for st in statements if isinstance(st, sem.SetNextOffset)]
    stack = roots
    while stack:
        node = stack.pop()
        out.setdefault(node.span, node.value)
        if isinstance(node, sem.Binary):
            stack += [node.left, node.right]
    return out


# --- the checks ----------------------------------------------------------------


def _bitfields(model: pdl.Model) -> Iterator[Diagnostic]:
    """Bitfield order (plan decision 8), and the first plain field after a
    bitfield line (bug 2: the Java tool did not reset its count there)."""
    for el in _elements(model.attributes.elements):
        if not isinstance(el, pdl.Struct):
            continue
        after_bits = False
        reported = False
        for element in el.elements:
            bits = [f for f in element.fields if f.bit_width is not None]
            plain = [f for f in element.fields if f.bit_width is None]
            if after_bits and not reported and plain:
                f = plain[0]
                reported = True
                yield _warning(
                    "model.legacy-bitfield-offset",
                    f"field `{f.name.text}` of struct `{el.name.text}` follows a bitfield"
                    " line: the Java tool counted that line twice and placed this field and"
                    " the ones after it further on (bug 2)",
                    "check the fields' offsets against the protocol's spec: they now follow"
                    " each other with no gap",
                    f.name.span,
                )
            if bits:
                after_bits = True
                names = ", ".join(f"`{f.name.text}`" for f in bits)
                yield _warning(
                    "model.legacy-bitfield-order",
                    f"bitfields {names} of struct `{el.name.text}` are numbered from the most"
                    " significant bit of their unit; the Java tool declared C bitfields, in"
                    " the compiler's order (least significant bit first with gcc on x86)",
                    "check the order against the protocol's spec: a run written for the Java"
                    " tool lists its fields from the least significant bit, so reverse it"
                    " (ip's `ihl:4, version:4` is `version:4, ihl:4`)",
                    bits[0].name.span,
                )


def _running_offset(analysed: sem.AnalysedModel) -> Iterator[Diagnostic]:
    """An aligned element after an aligned struct with bitfields (bug 3)."""
    pending: list[sem.AnalysedStruct] = []

    def walk(elements: tuple[sem.Element, ...]) -> Iterator[Diagnostic]:
        for el in elements:
            if isinstance(el, sem.AnalysedConditional):
                yield from walk(el.then_branch)
                yield from walk(el.else_branch or ())
                continue
            if el.aligned and pending:
                name = el.name
                for s in pending:
                    yield _warning(
                        "model.legacy-bitfield-offset",
                        f"`{name}` is placed by the running offset after struct `{s.name}`,"
                        " whose bitfields the Java tool counted at their type's full width"
                        f" each, so it placed `{name}` further on (bug 3)",
                        f"`{name}` is now at {s.name}'s end: check it against the protocol's spec",
                        el.span,
                    )
                pending.clear()
            if isinstance(el, sem.AnalysedStruct) and el.aligned and el.runs:
                pending.append(el)

    yield from walk(analysed.elements)


def _folded(model: pdl.Model, values: dict[pdl.Span, int | None]) -> Iterator[Diagnostic]:
    """Offsets, lengths and nextoffsets the Java tool folded to a constant
    that is not what they are now: one that reads the packet (bug 5), or
    another number (a comparison folded as ``!=``, bug 6; an unswapped
    ``ntohs``)."""
    for what, whose, expr in _used(model):
        if not _java_simple(expr):
            continue
        java = _java_value(expr)
        if java is None:
            continue
        if expr.span not in values:
            continue  # not known without the analysis
        ours = values[expr.span]
        nodes = list(_nodes(expr))
        text = expression_text(expr)
        if ours is None:
            yield _warning(
                "model.legacy-constant-folding",
                f"the {what} of {whose}, `{text}`, is not a constant, but the Java tool took"
                f" it for one because its last operand is, and folded it to {java} (bug 5)",
                "it is now computed for each packet: check that this is what the model means",
                expr.span,
            )
        elif ours != java:
            relational = any(isinstance(n, pdl.BinaryOp) and n.op in _RELATIONAL for n in nodes)
            causes = []
            if relational:
                causes.append("it read every comparison but == as != (bug 6)")
            if any(isinstance(n, (pdl.OffsetOf, pdl.LengthOf)) for n in nodes):
                causes.append("it read offset() and len() as 0 (bug 19)")
            if any(isinstance(n, pdl.ByteSwap) for n in nodes):
                causes.append("it did not swap the bytes of ntohs and ntohl")
            yield _warning(
                "model.legacy-comparison" if relational else "model.legacy-constant-folding",
                f"the {what} of {whose}, `{text}`, is {ours}; the Java tool folded it to"
                f" {java}" + (": " + "; ".join(causes) if causes else ""),
                "check that the expression means what the model says",
                expr.span,
            )


def _sizeof(model: pdl.Model, values: dict[pdl.Span, int | None]) -> Iterator[Diagnostic]:
    """``sizeof`` of a C or MMT type where the Java tool wrote it into the C:
    ``sizeof(MMT_U8_DATA)``, an enum constant's size, 4 (bug 7)."""
    texts = list(_texts(model))
    texts += [e for _, _, e in _used(model) if not _java_simple(e)]
    for expr in texts:
        for node in _nodes(expr):
            if not isinstance(node, pdl.SizeOf):
                continue
            name = _java_sizeof_name(node.type)
            if name is None:
                continue
            ours = values.get(node.span)
            if ours is None and isinstance(node.type, pdl.CType):
                ours = 4 if node.type.pointer else _JAVA_MMT_LENGTHS[name]
            if ours is None or ours == _ENUM_SIZE:
                continue
            yield _warning(
                "model.legacy-sizeof",
                f"`{expression_text(node)}` is {ours}; the Java tool wrote it into the C as"
                f" sizeof({name}), the size of an enum constant, {_ENUM_SIZE} (bug 7)",
                "check the offsets, lengths and conditions that use it",
                node.span,
            )


def _classifynext(model: pdl.Model) -> Iterator[Diagnostic]:
    """A classifynext block without ``encapsulation = "true"`` (bug 21)."""
    flag = model.properties.encapsulation
    if model.classify_next is not None and not (flag is not None and flag.value):
        yield _warning(
            "model.legacy-classifynext",
            'classifynext without encapsulation = "true": the Java tool dropped it, so its'
            " plugin never chose a next protocol; generate emits it (bug 21)",
            "set encapsulation: true under protocol, or remove classify_next if the plugin"
            " must not choose a next protocol",
            model.classify_next.span,
        )


def _ip_addr(model: pdl.Model) -> Iterator[Diagnostic]:
    """An ``MMT_DATA_IP_ADDR`` the Java tool read on its complex path (an
    offset or data_len it did not fold), where it byte-swapped it in network
    byte order (bug 25)."""
    encoding = model.properties.encoding
    if encoding is None or encoding.value is not pdl.Encoding.NETWORK:
        return
    for el in _elements(model.attributes.elements):
        if not (
            isinstance(el, pdl.Attribute) and el.data_type.type is pdl.DataType.MMT_DATA_IP_ADDR
        ):
            continue
        if any(e is not None and not _java_simple(e) for e in (el.offset, el.data_len)):
            yield _warning(
                "model.legacy-ip-addr",
                f"`{el.alias.text}` is an MMT_DATA_IP_ADDR whose offset or data_len the Java"
                " tool did not fold: it byte-swapped the address there (bug 25); it is now"
                " copied byte for byte, as everywhere else",
                "check code that reads this attribute: the address is in network byte order",
                el.alias.span,
            )


def legacy_warnings(model: pdl.Model, analysed: sem.AnalysedModel | None) -> list[Diagnostic]:
    """The ``model.legacy-*`` warnings of the constructs of ``model``, apart
    from the SDK conflicts and duplicate names, which come from its analysis.
    Without ``analysed``, the checks that need the layout or the values of
    expressions (bugs 3, 5 and 6) do not run."""
    values = _values(analysed)
    found = [
        *_bitfields(model),
        *_folded(model, values),
        *_sizeof(model, values),
        *_classifynext(model),
        *_ip_addr(model),
    ]
    if analysed is not None:
        found += [*_running_offset(analysed)]
    return found


# --- the conversion --------------------------------------------------------------


def _relabel(d: Diagnostic, code: str, message: str, hint: str) -> Diagnostic:
    return Diagnostic(
        Severity.WARNING, code, message, hint=hint, location=d.location, related=d.related
    )


def convert(model: pdl.Model, profile: Profile) -> Conversion:
    """``model`` (parsed from PDL v1) as ``plugin.yaml``, analysed against
    ``profile``; see the module docstring."""
    analysed, found = analyse(model, profile=profile, allow_sdk_conflicts=True)
    names = _names(model)
    diagnostics: list[Diagnostic] = []
    for d in found:
        if d.code in _DROPPED:
            continue
        if d.severity is Severity.ERROR and d.code in SDK_CONFLICT_CODES:
            diagnostics.append(
                _relabel(
                    d,
                    "model.legacy-sdk-conflict",
                    f"{d.message}: the Java tool accepted any id and name (bug 23)",
                    "generate refuses it: choose a free id from 950 to 999 and a label the"
                    " SDK does not register (mmt-plugin validate checks both)",
                )
            )
        elif (
            d.severity is Severity.ERROR
            and d.code == "model.duplicate-name"
            and _java_accepted_duplicate(d, names)
        ):
            diagnostics.append(
                _relabel(
                    d,
                    "model.legacy-duplicate-name",
                    f"{d.message}: the Java tool accepted it, as it did not check conditional"
                    " attributes (bug 12) and compared names with their case (bug 16)",
                    "rename one of the two, then import again for absolute offsets; until"
                    " then plugin.yaml keeps PDL v1's running offsets",
                )
            )
        else:
            diagnostics.append(d)
    if any(d.severity is Severity.ERROR for d in diagnostics):
        return Conversion(None, pdl.Offsets.ABSOLUTE, tuple(diagnostics))
    diagnostics += legacy_warnings(model, analysed)
    if analysed is not None:
        text = dumps(analysed)
        offsets = pdl.Offsets.ABSOLUTE
    else:
        # Only duplicate names the Java tool accepted withhold the analysis.
        text = dumps(model, offsets=pdl.Offsets.RUNNING)
        offsets = pdl.Offsets.RUNNING
    return Conversion(text, offsets, tuple(diagnostics))
