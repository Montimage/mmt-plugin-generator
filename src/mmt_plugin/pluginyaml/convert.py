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
- ``model.legacy-constant-folding`` (bug 5): an offset or length that reads
  the packet but ends in a constant, which the Java tool folded;
- ``model.legacy-comparison`` (bug 6): a constant ``>``, ``<``, ``>=`` or
  ``<=`` whose value is not the one of ``!=``, as the Java tool folded it;
- ``model.legacy-sizeof-char`` (bug 7): ``sizeof(char)``, 1 and not 4;
- ``model.legacy-classifynext`` (bug 21): a classifynext block without
  ``encapsulation = "true"``, which the Java tool dropped;
- ``model.legacy-ip-addr`` (bug 25): an ``MMT_DATA_IP_ADDR`` at an offset
  that reads the packet, which the Java tool byte-swapped.

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
    "model.legacy-sizeof-char",
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


def _expressions(model: pdl.Model) -> Iterator[pdl.Expr]:
    """Every expression of the model, in source order."""
    for el in _elements(model.attributes.elements):
        if isinstance(el, pdl.Attribute):
            yield from (e for e in (el.offset, el.data_len) if e is not None)
        elif isinstance(el, pdl.Conditional):
            yield el.condition
    if model.classify_next is not None:
        switch = model.classify_next.switch
        yield switch.subject
        blocks = [c.statements for c in switch.cases]
        if switch.default is not None:
            blocks.append(switch.default.statements)
        for statements in blocks:
            yield from (st.value for st in statements if isinstance(st, pdl.NextOffset))


def _nodes(expr: pdl.Expr) -> Iterator[pdl.Expr]:
    """Every node of ``expr``, in source order."""
    if isinstance(expr, pdl.BinaryOp):
        yield from _nodes(expr.left)
        yield expr
        yield from _nodes(expr.right)
    else:
        yield expr


def _reads_packet(expr: pdl.Expr) -> bool:
    return any(isinstance(n, pdl.ValueOf) for n in _nodes(expr))


def _last_operand(expr: pdl.Expr) -> pdl.Expr:
    while isinstance(expr, pdl.BinaryOp):
        expr = expr.right
    return expr


# --- the checks ----------------------------------------------------------------


def _bitfields(model: pdl.Model) -> Iterator[Diagnostic]:
    """Bitfield order (plan decision 8) and the offsets after a bitfield line
    (bug 2)."""
    for el in _elements(model.attributes.elements):
        if not isinstance(el, pdl.Struct):
            continue
        after_bits = False
        reported = False
        for element in el.elements:
            if after_bits and not reported and element.fields:
                f = element.fields[0]
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
            bits = [f for f in element.fields if f.bit_width is not None]
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


def _folding(model: pdl.Model) -> Iterator[Diagnostic]:
    """Offsets and lengths that read the packet but end in a constant (bug 5)."""
    for el in _elements(model.attributes.elements):
        if not isinstance(el, pdl.Attribute):
            continue
        for what, expr in (("offset", el.offset), ("data_len", el.data_len)):
            if not isinstance(expr, pdl.BinaryOp) or not _reads_packet(expr):
                continue
            last = _last_operand(expr)
            if isinstance(last, (pdl.IntLiteral, pdl.SizeOf, pdl.ByteSwap)):
                yield _warning(
                    "model.legacy-constant-folding",
                    f"the {what} of `{el.alias.text}`, `{expression_text(expr)}`, reads the"
                    " packet but ends in a constant: the Java tool took it for a constant and"
                    " folded it (`val(x) - 4` became -4; bug 5)",
                    "it is now computed for each packet: check that this is what the model means",
                    expr.span,
                )


def _analysed_expressions(analysed: sem.AnalysedModel) -> Iterator[sem.Expr]:
    for a in analysed.attributes:
        if a.kind is sem.AttributeKind.PLAIN:
            yield from (e for e in (a.declared_offset, a.length) if e is not None)
    for c in analysed.conditionals:
        yield c.condition
    switch = analysed.classify_next
    if switch is not None:
        yield switch.subject
        blocks = [c.statements for c in switch.cases]
        if switch.default is not None:
            blocks.append(switch.default.statements)
        for statements in blocks:
            yield from (st.offset for st in statements if isinstance(st, sem.SetNextOffset))


def _comparisons(analysed: sem.AnalysedModel) -> Iterator[Diagnostic]:
    """Constant comparisons whose value is not the one of ``!=`` (bug 6)."""
    seen: set[pdl.Span] = set()
    for expr in _analysed_expressions(analysed):
        stack: list[sem.Expr] = [expr]
        while stack:
            node = stack.pop()
            if not isinstance(node, sem.Binary):
                continue
            stack += [node.right, node.left]
            if node.op not in _RELATIONAL or node.value is None or node.span in seen:
                continue
            left, right = node.left.value, node.right.value
            assert left is not None and right is not None  # node folds
            java = int(left != right)
            if java != node.value:
                seen.add(node.span)
                yield _warning(
                    "model.legacy-comparison",
                    f"`{left} {node.op.value} {right}` is {node.value}; the Java tool folded"
                    f" it as `{left} != {right}`, which is {java} (bug 6)",
                    "check that the comparison means what the model says",
                    node.span,
                )


def _sizeof_char(model: pdl.Model) -> Iterator[Diagnostic]:
    """``sizeof(char)`` (bug 7)."""
    for expr in _expressions(model):
        for node in _nodes(expr):
            if (
                isinstance(node, pdl.SizeOf)
                and isinstance(node.type, pdl.CType)
                and node.type.name == "char"
                and not node.type.pointer
            ):
                yield _warning(
                    "model.legacy-sizeof-char",
                    "`sizeof(char)` is 1; the Java tool wrote sizeof(MMT_U8_DATA), which is"
                    " 4 (bug 7)",
                    "check the offsets and lengths that use it",
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
    """An ``MMT_DATA_IP_ADDR`` at an offset that reads the packet (bug 25)."""
    for el in _elements(model.attributes.elements):
        if (
            isinstance(el, pdl.Attribute)
            and el.data_type.type is pdl.DataType.MMT_DATA_IP_ADDR
            and el.offset is not None
            and _reads_packet(el.offset)
        ):
            yield _warning(
                "model.legacy-ip-addr",
                f"`{el.alias.text}` is an MMT_DATA_IP_ADDR at an offset that reads the packet:"
                " the Java tool byte-swapped it there (bug 25); it is now copied byte for"
                " byte, as at a constant offset",
                "check code that reads this attribute: the address is in network byte order",
                el.alias.span,
            )


def legacy_warnings(model: pdl.Model, analysed: sem.AnalysedModel | None) -> list[Diagnostic]:
    """The ``model.legacy-*`` warnings of the constructs of ``model``, apart
    from the SDK conflicts and duplicate names, which come from its analysis.
    The checks that need the layout (bugs 3 and 6) run only with
    ``analysed``."""
    found = [
        *_bitfields(model),
        *_folding(model),
        *_sizeof_char(model),
        *_classifynext(model),
        *_ip_addr(model),
    ]
    if analysed is not None:
        found += [*_running_offset(analysed), *_comparisons(analysed)]
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
