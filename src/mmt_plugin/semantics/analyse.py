"""The semantic passes: names, types, layout, folding and validation.

``analyse(model, profile=...)`` walks a parsed PDL model once, in source
order, and returns the analysed model (``mmt_plugin.semantics.model``) with
the diagnostics it found. It reads no file and detects no SDK: what it needs
from mmt-dpi (``Max_Alias_Len``, ``PROTO_MAX_IDENTIFIER``, the ids and names
the SDK's protocols take) comes from the profile passed in.

The rules are those of ``tests/corpus/README.md`` (Semantics, Decided rules)
and plan decisions 5 and 8 (``docs/design/workflow-redesign.md``); each
inventory bug fixed here is cited as "bug N" (``docs/legacy/
java-generator-inventory.md``, section 5).

Recursion: expressions are walked with an explicit stack, so their depth does
not matter. Statement blocks recurse once per nested ``if``, which the parser
caps at ``mmt_plugin.pdl.parser.MAX_DEPTH`` (64).
"""

from __future__ import annotations

import dataclasses
import difflib
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType

from mmt_plugin.diagnostics import Diagnostic, Related, Severity, sorted_diagnostics
from mmt_plugin.pdl import model as pdl
from mmt_plugin.pdl.model import BinaryOperator, DataType, Encoding, Scope, Span
from mmt_plugin.sdk.profile import Profile, SdkProtocol
from mmt_plugin.semantics.model import (
    AnalysedAttribute,
    AnalysedCase,
    AnalysedConditional,
    AnalysedDefault,
    AnalysedDefine,
    AnalysedModel,
    AnalysedStruct,
    AnalysedSwitch,
    AttributeKind,
    Binary,
    Bitfield,
    BitfieldRun,
    ByteOrder,
    Const,
    Element,
    Expr,
    FieldKind,
    Guard,
    LengthRef,
    NextProto,
    OffsetRef,
    Protocol,
    SetNextOffset,
    SetNextProto,
    SizeOfType,
    Statement,
    StructField,
    Swap,
    ValueRef,
)
from mmt_plugin.semantics.types import (
    BITFIELD_TYPES,
    FIXED_WIDTHS,
    INTEGER_TYPES,
    CStorage,
    c_storage,
)

__all__ = ["HINTS", "SDK_CONFLICT_CODES", "THIRD_PARTY_IDS", "analyse"]

#: The protocol ids reserved for third-party plugins (plan decision 5; asked
#: of mmt-dpi in Montimage/mmt-dpi#73). An id outside it is a warning.
THIRD_PARTY_IDS = range(950, 1000)

#: Errors that depend on the SDK, not on the model alone: the id or the name
#: is already an SDK protocol's. ``analyse`` still returns the analysed model
#: with them, so that tools comparing outputs (T1.6) can generate it; every
#: command fails on them like on any error.
SDK_CONFLICT_CODES = frozenset({"model.id-taken", "model.name-taken"})

#: The largest offset or length the SDK's ``attribute_metadata_t`` (an ``int``)
#: holds.
_INT_MAX = 2**31 - 1

#: The default hint of each code this module emits.
HINTS: Mapping[str, str] = MappingProxyType(
    {
        "model.duplicate-name": "rename one of the two; names are case-insensitive, since the "
        "generated C lower-cases aliases",
        "model.unknown-name": "define the name before it is used, or use a number",
        "model.unknown-attribute": "declare the attribute before the expression that uses it",
        "model.unknown-struct": "define the struct before the field or sizeof that uses it",
        "model.use-before-definition": "move the definition before its first use",
        "model.conditional-reference": "use it inside the branch that declares it, or declare "
        "it outside the if",
        "model.not-an-integer": "val() reads integer attributes only (MMT_U8_DATA to "
        "MMT_U64_DATA, MMT_DATA_CHAR, MMT_DATA_PORT)",
        "model.missing-length": "give data_len, or use a type with a fixed width",
        "model.no-fixed-width": "use a fixed-width type (MMT_U8_DATA ... MMT_U64_DATA, "
        "MMT_DATA_MAC_ADDR, MMT_DATA_IP_ADDR, MMT_DATA_IP6_ADDR, ...) or a plain attribute "
        "with a data_len",
        "model.invalid-bitfield": "give a width from 1 to the unit's bits, on an integer type",
        "model.bitfield-overflow": "split the run over two declarations, or use a wider type",
        "model.division-by-zero": "fix the divisor",
        "model.out-of-range": "fix the expression",
        "model.duplicate-case": "remove one of the two cases",
        "model.leading-zero": "write the number without its leading zeros (or in hex)",
        "model.alias-too-long": "shorten the name",
        "model.id-out-of-range": "use an id from 950 to 999, the third-party range",
        "model.id-taken": "use a free id from 950 to 999, the third-party range",
        "model.name-taken": "choose another label: an SDK protocol already registers this name",
        "model.id-outside-reserved-range": "use an id from 950 to 999, the range reserved for "
        "third-party plugins",
        "model.default-scope": 'add scope="SCOPE_PACKET" (or SCOPE_SESSION) to say which you mean',
        "model.pointer-field": "prefer an MMT_U32_DATA or byte-array field: a pointer field "
        "only gives its offset",
        "model.hook-reference": "give the attribute an offset and a data_len, or do not use "
        "offset() or len() of it",
        "model.branch-offset-mismatch": "give the attribute an offset that does not depend on "
        "the if/else, or make both branches the same length",
    }
)

_ARITHMETIC = frozenset({BinaryOperator.ADD, BinaryOperator.SUB, BinaryOperator.MUL})


def analyse(
    model: pdl.Model, *, profile: Profile
) -> tuple[AnalysedModel | None, list[Diagnostic]]:
    """Analyse a parsed PDL model against an SDK profile.

    Returns the analysed model and every diagnostic, sorted. The model is
    ``None`` when there is an error, except for the SDK conflicts of
    ``SDK_CONFLICT_CODES``. Warnings never withhold it (``--strict`` is the
    caller's).
    """
    analyser = _Analyser(model, profile)
    result = analyser.run()
    diagnostics = sorted_diagnostics(analyser.diagnostics)
    blocking = any(
        d.severity is Severity.ERROR and d.code not in SDK_CONFLICT_CODES for d in diagnostics
    )
    return (None if blocking else result), diagnostics


# --- small helpers -----------------------------------------------------------


def _nodes(expr: pdl.Expr) -> Iterator[pdl.Expr]:
    """Every node of an expression, without recursion."""
    stack: list[pdl.Expr] = [expr]
    while stack:
        node = stack.pop()
        yield node
        if isinstance(node, pdl.BinaryOp):
            stack.append(node.right)
            stack.append(node.left)


def _literal_only(expr: pdl.Expr) -> bool:
    """Whether an expression is *constant* for alignment (corpus README):
    literals, ``ntohs``/``ntohl`` and ``+ - * /`` only. ``val``, ``sizeof``,
    ``offset()``, ``len()``, comparisons and ``AND``/``OR`` are not (the Java
    tool marked all of them non-simple)."""
    for node in _nodes(expr):
        if isinstance(node, pdl.BinaryOp):
            if node.op not in _ARITHMETIC and node.op is not BinaryOperator.DIV:
                return False
        elif not isinstance(node, (pdl.IntLiteral, pdl.ByteSwap)):
            return False
    return True


def _literals(expr: pdl.Expr) -> Iterator[pdl.IntLiteral]:
    for node in _nodes(expr):
        if isinstance(node, pdl.IntLiteral):
            yield node
        elif isinstance(node, pdl.ByteSwap):
            yield node.operand


def _has_leading_zero(literal: pdl.IntLiteral) -> bool:
    digits = literal.text.lstrip("-")
    return not literal.is_hex and len(digits) > 1 and digits.startswith("0")


def _c_div(a: int, b: int) -> int:
    """C division: truncates toward zero."""
    q = abs(a) // abs(b)
    return q if (a < 0) == (b < 0) else -q


def _fold(op: BinaryOperator, a: int, b: int) -> int:
    """``a op b`` with C semantics; ``b`` is not 0 for ``/``."""
    if op is BinaryOperator.ADD:
        return a + b
    if op is BinaryOperator.SUB:
        return a - b
    if op is BinaryOperator.MUL:
        return a * b
    if op is BinaryOperator.DIV:
        return _c_div(a, b)
    if op is BinaryOperator.EQ:
        return int(a == b)
    if op is BinaryOperator.NE:
        return int(a != b)
    if op is BinaryOperator.GT:
        return int(a > b)
    if op is BinaryOperator.LT:
        return int(a < b)
    if op is BinaryOperator.GE:
        return int(a >= b)
    if op is BinaryOperator.LE:
        return int(a <= b)
    if op is BinaryOperator.AND:
        return int(a != 0 and b != 0)
    return int(a != 0 or b != 0)  # OR


def _swap(width: int, value: int) -> int:
    return int.from_bytes(value.to_bytes(width // 8, "big"), "little")


def _did_you_mean(word: str, choices: Iterable[str]) -> str:
    by_key = {c.lower(): c for c in choices}
    close = difflib.get_close_matches(word.lower(), list(by_key), n=1, cutoff=0.6)
    return f" (did you mean `{by_key[close[0]]}`?)" if close else ""


def _end(offset: int | None) -> str:
    return "an unaligned offset" if offset is None else str(offset)


_BYTE_ORDERS = {
    Encoding.NETWORK: ByteOrder.BIG,
    Encoding.HOST: ByteOrder.LITTLE,
}


# --- the walk ----------------------------------------------------------------


@dataclass(frozen=True)
class _Mismatch:
    """An if/else whose branches end with a different running offset (an
    end of ``None`` means alignment is off there)."""

    span: Span
    then_end: int | None
    else_end: int | None


@dataclass(frozen=True)
class _State:
    """The running offset R, the alignment state and the if/else mismatches
    the next aligned element would depend on."""

    offset: int
    aligned: bool
    pending: tuple[_Mismatch, ...] = ()


@dataclass(frozen=True)
class _TypeInfo:
    kind: FieldKind
    data_type: DataType
    width: int
    storage: CStorage


@dataclass
class _Run:
    index: int
    offset: int
    info: _TypeInfo
    used: int
    fields: list[str]
    span: Span


class _Analyser:
    def __init__(self, model: pdl.Model, profile: Profile) -> None:
        self.model = model
        self.profile = profile
        self.diagnostics: list[Diagnostic] = []
        self.max_alias = self._constant("Max_Alias_Len")
        self.max_id = self._constant("PROTO_MAX_IDENTIFIER")
        # Every protocol the SDK registers: the plugins' (parents.ids) and
        # the core's pseudo-protocols (constants of group protocol_id).
        plugins = profile.parents.protocols()
        core = [
            SdkProtocol(c.name, c.value, c.header, None)
            for c in profile.constants
            if c.group == "protocol_id" and c.value is not None
        ]
        protocols = [*plugins, *core]
        self.sdk_by_macro: dict[str, SdkProtocol] = {p.macro: p for p in protocols}
        self.sdk_by_id: dict[int, SdkProtocol] = {p.id: p for p in protocols}
        self.sdk_by_alias: dict[str, SdkProtocol] = {
            p.alias.lower(): p for p in protocols if p.alias is not None
        }
        # The protocol macros a model may name: those the generated C sees,
        # from the parents' header (which includes declared_in) and the core.
        self.sdk_names: dict[str, int] = {
            p.macro: p.id
            for p in (*plugins, *core)
            if p in core or p.header == profile.parents.declared_in
        }
        # Every name the model declares, first occurrence, to tell a later
        # definition from none at all.
        self.declared_attrs: dict[str, pdl.Name] = {}
        self.declared_structs: dict[str, pdl.Name] = {}
        self.declared_defines: dict[str, pdl.Name] = {
            d.name.text.lower(): d.name for d in reversed(model.defines)
        }
        self._prescan(model.attributes.elements)
        # What is defined so far, in source order.
        self.defines: dict[str, AnalysedDefine] = {}
        self.attrs: dict[str, AnalysedAttribute] = {}
        self.attr_names: dict[str, pdl.Name] = {}
        self.attr_list: list[AnalysedAttribute] = []
        self.structs: dict[str, AnalysedStruct] = {}
        self.struct_names: dict[str, pdl.Name] = {}
        self.struct_list: list[AnalysedStruct] = []
        self.conditionals: list[AnalysedConditional] = []
        self.conditional_count = 0
        self.helper_names: set[str] = set(self.declared_structs)
        # Struct fields left out after an error of their own: a reference to
        # one is not reported again.
        self.dropped: set[str] = set()
        self.reported: set[Span] = set()
        self.defining: dict[str, str] = {}  # kind ("define", ...) -> key

    # -- diagnostics --

    def _emit(
        self,
        severity: Severity,
        code: str,
        message: str,
        span: Span,
        hint: str | None = None,
        related: Sequence[Related] = (),
    ) -> None:
        self.diagnostics.append(
            Diagnostic(severity, code, message, hint or HINTS[code], span.location(), related)
        )

    def error(
        self,
        code: str,
        message: str,
        span: Span,
        hint: str | None = None,
        related: Sequence[Related] = (),
    ) -> None:
        self._emit(Severity.ERROR, code, message, span, hint, related)

    def warning(
        self,
        code: str,
        message: str,
        span: Span,
        hint: str | None = None,
        related: Sequence[Related] = (),
    ) -> None:
        self._emit(Severity.WARNING, code, message, span, hint, related)

    def _constant(self, name: str) -> int | None:
        try:
            return self.profile.constant(name).value
        except KeyError:
            return None

    def _prescan(self, elements: Sequence[pdl.AttributeElement]) -> None:
        for el in elements:
            if isinstance(el, pdl.Attribute):
                self.declared_attrs.setdefault(el.alias.text.lower(), el.alias)
            elif isinstance(el, pdl.Struct):
                self.declared_structs.setdefault(el.name.text.lower(), el.name)
                for element in el.elements:
                    for field in element.fields:
                        self.declared_attrs.setdefault(field.name.text.lower(), field.name)
            else:
                self._prescan(el.then_branch)
                self._prescan(el.else_branch or ())

    # -- the whole model --

    def run(self) -> AnalysedModel:
        protocol = self._properties(self.model.properties)
        defines = tuple(self._define(d) for d in self.model.defines)
        elements, _ = self._elements(self.model.attributes.elements, (), _State(0, True))
        switch = None
        if self.model.classify_next is not None:
            switch = self._switch(self.model.classify_next.switch)
        return AnalysedModel(
            protocol=protocol,
            defines=defines,
            elements=elements,
            attributes=tuple(self.attr_list),
            structs=tuple(self.struct_list),
            conditionals=tuple(sorted(self.conditionals, key=lambda c: c.index)),
            classify_next=switch,
            source=self.model,
        )

    # -- Properties (bug 23) --

    def _properties(self, p: pdl.Properties) -> Protocol:
        label = p.label.text
        self._check_alias(p.label, "protocol label")
        pid = p.id.value
        in_range = pid >= 1 and (self.max_id is None or pid < self.max_id)
        if not in_range:
            limit = "" if self.max_id is None else f" and below {self.max_id}"
            self.error(
                "model.id-out-of-range",
                f"protocol id {pid} is out of range: an id is positive{limit} "
                "(PROTO_MAX_IDENTIFIER)",
                p.id.span,
            )
        taken = self.sdk_by_id.get(pid)
        if in_range and taken is not None:
            self.error(
                "model.id-taken",
                f"protocol id {pid} is already {taken.macro}'s in mmt-dpi {self.profile.version}",
                p.id.span,
                related=[
                    Related(
                        f"{taken.macro} = {pid} in the SDK profile {self.profile.version} "
                        f"({taken.header})"
                    )
                ],
            )
        elif in_range and pid not in THIRD_PARTY_IDS:
            self.warning(
                "model.id-outside-reserved-range",
                f"protocol id {pid} is outside {THIRD_PARTY_IDS.start}-{THIRD_PARTY_IDS.stop - 1},"
                " the range reserved for third-party plugins",
                p.id.span,
            )
        # The generated C defines PROTO_<LABEL>, and the SDK finds a protocol
        # by its registered name (PROTO_<X>_ALIAS) case-insensitively: a
        # label that clashes with either is taken.
        macro = self.profile.parents.id_for(label)
        by_macro = self.sdk_by_macro.get(macro)
        by_alias = self.sdk_by_alias.get(label.lower())
        if by_macro is not None:
            self.error(
                "model.name-taken",
                f"protocol name {label.upper()} is already an SDK protocol's: {macro} = "
                f"{by_macro.id} in mmt-dpi {self.profile.version}",
                p.label.span,
            )
        elif by_alias is not None:
            self.error(
                "model.name-taken",
                f'protocol name "{label}" is already an SDK protocol\'s: {by_alias.macro} '
                f'({by_alias.id}) registers "{by_alias.alias}" in mmt-dpi {self.profile.version}',
                p.label.span,
            )
        encoding = None if p.encoding is None else p.encoding.value
        return Protocol(
            label=label,
            name=label.upper(),
            id=pid,
            context=bool(p.context and p.context.value),
            session_context=bool(p.session_context and p.session_context.value),
            session=bool(p.session and p.session.value),
            encapsulation=bool(p.encapsulation and p.encapsulation.value),
            encoding=encoding,
            byte_order=ByteOrder.UNSPECIFIED
            if encoding is None
            else _BYTE_ORDERS.get(encoding, ByteOrder.UNSPECIFIED),
            span=p.span,
        )

    def _check_alias(self, name: pdl.Name, what: str) -> None:
        size = len(name.text.encode("utf-8"))
        if self.max_alias is not None and size > self.max_alias:
            self.error(
                "model.alias-too-long",
                f"{what} `{name.text}` is {size} bytes long; the SDK's aliases hold at most "
                f"{self.max_alias} (Max_Alias_Len)",
                name.span,
            )

    # -- defines and names --

    def _define(self, d: pdl.Define) -> AnalysedDefine:
        key = d.name.text.lower()
        first = self.defines.get(key)
        if first is not None:
            self._duplicate("define", d.name, first.span)
        value = 0
        alias_of = None
        if isinstance(d.value, pdl.IntLiteral):
            self._leading_zero(d.value, "a define value")
            value = d.value.value
        else:
            self.defining["define"] = key
            resolved = self._resolve_name(d.value)
            del self.defining["define"]
            if resolved is not None:
                value, alias_of = resolved
        analysed = AnalysedDefine(d.name.text, value, alias_of, d.name.span)
        self.defines.setdefault(key, analysed)
        return analysed

    def _duplicate(self, what: str, name: pdl.Name, first: Span) -> None:
        self.error(
            "model.duplicate-name",
            f"{what} name `{name.text}` is already used (names are case-insensitive)",
            name.span,
            related=[Related("first defined here", first.location())],
        )

    def _resolve_name(self, name: pdl.Name) -> tuple[int, str] | None:
        """A define (case-insensitively) or an SDK protocol macro."""
        key = name.text.lower()
        define = self.defines.get(key)
        if define is not None and key != self.defining.get("define"):
            return define.value, define.name
        if name.text in self.sdk_names:
            return self.sdk_names[name.text], name.text
        later = self.declared_defines.get(key)
        if later is not None:
            self._used_too_early("define", name, later, key == self.defining.get("define"))
            return None
        self.error(
            "model.unknown-name",
            f"`{name.text}` is no define and no SDK protocol"
            + _did_you_mean(name.text, [d.name for d in self.defines.values()]),
            name.span,
        )
        return None

    def _used_too_early(
        self, what: str, use: pdl.Name, definition: pdl.Name, itself: bool
    ) -> None:
        message = (
            f"{what} `{use.text}` refers to itself"
            if itself
            else f"{what} `{use.text}` is used before its definition"
        )
        self.error(
            "model.use-before-definition",
            message,
            use.span,
            related=[Related("defined here", definition.span.location())],
        )

    def _leading_zero(self, literal: pdl.IntLiteral, where: str) -> None:
        """Diagnose ``010`` or ``08`` where the Java tool copied the literal
        into the C as text (review of #47, N2)."""
        if not _has_leading_zero(literal):
            return
        digits = literal.text.lstrip("-")
        if any(c in "89" for c in digits):
            reading = (
                "which is not a valid C literal (a leading 0 means octal), so it does not compile"
            )
        else:
            reading = f"which C reads as octal {int(digits, 8)}"
        self.error(
            "model.leading-zero",
            f"`{literal.text}` in {where} is {literal.value} in PDL, but the Java tool copied it "
            f"into the C as text, {reading}",
            literal.span,
            hint=f"write {literal.value} (or 0x{abs(literal.value):X}) to say which you mean",
        )

    def _leading_zeros(self, expr: pdl.Expr, where: str) -> None:
        for literal in _literals(expr):
            self._leading_zero(literal, where)

    # -- expressions (bugs 5, 6, 7, 19) --

    def _expr(self, expr: pdl.Expr, guards: tuple[Guard, ...]) -> Expr:
        """The typed, folded form of an expression (post-order, no recursion)."""
        stack: list[tuple[pdl.Expr, bool]] = [(expr, False)]
        out: list[Expr] = []
        while stack:
            node, expanded = stack.pop()
            if not isinstance(node, pdl.BinaryOp):
                out.append(self._leaf(node, guards))
            elif expanded:
                right = out.pop()
                left = out.pop()
                out.append(self._binary(node, left, right))
            else:
                stack.append((node, True))
                stack.append((node.right, False))
                stack.append((node.left, False))
        return out.pop()

    def _binary(self, node: pdl.BinaryOp, left: Expr, right: Expr) -> Binary:
        value = None
        if left.value is not None and right.value is not None:
            if node.op is BinaryOperator.DIV and right.value == 0:
                self.error(
                    "model.division-by-zero",
                    "this expression divides by zero",
                    node.span,
                )
            else:
                value = _fold(node.op, left.value, right.value)
        return Binary(node.op, left, right, value, node.span)

    def _leaf(self, node: pdl.Expr, guards: tuple[Guard, ...]) -> Expr:
        if isinstance(node, pdl.IntLiteral):
            return Const(node.value, node.text, node.span)
        if isinstance(node, pdl.ValueOf):
            target = self._reference(node.attribute, guards, "val")
            if target is not None and target.data_type not in INTEGER_TYPES:
                self.error(
                    "model.not-an-integer",
                    f"val({node.attribute.text}) reads an integer, but `{target.name}` is "
                    f"{target.data_type.value}",
                    node.attribute.span,
                    related=[Related("declared here", target.span.location())],
                )
            return ValueRef(node.attribute.text.lower(), node.span)
        if isinstance(node, pdl.OffsetOf):
            target = self._reference(node.attribute, guards, "offset")
            if target is not None and target.offset is None:
                self._hook_reference(node.attribute, target, "offset")
            value = None if target is None else target.offset_value
            return OffsetRef(node.attribute.text.lower(), value, node.span)
        if isinstance(node, pdl.LengthOf):
            target = self._reference(node.attribute, guards, "len")
            if target is not None and target.length is None:
                self._hook_reference(node.attribute, target, "data_len")
            value = None if target is None else target.length_value
            return LengthRef(node.attribute.text.lower(), value, node.span)
        if isinstance(node, pdl.SizeOf):
            info = self._element_type(node.type, "sizeof")
            return SizeOfType(node.type, 0 if info is None else info.width, node.span)
        if isinstance(node, pdl.ByteSwap):
            operand = node.operand.value
            limit = 1 << node.width
            name = "ntohs" if node.width == 16 else "ntohl"
            if not 0 <= operand < limit:
                self.error(
                    "model.out-of-range",
                    f"{name}({node.operand.text}) swaps a {node.width}-bit value, from 0 to "
                    f"{limit - 1}",
                    node.operand.span,
                )
                return Swap(node.width, operand, 0, node.span)
            return Swap(node.width, operand, _swap(node.width, operand), node.span)
        raise AssertionError(f"not an expression leaf: {node!r}")  # pragma: no cover

    def _hook_reference(self, name: pdl.Name, target: AnalysedAttribute, key: str) -> None:
        function = "offset" if key == "offset" else "len"
        self.error(
            "model.hook-reference",
            f"{function}({name.text}) has no value: `{target.name}` has no {key}, so its "
            "extraction is a user hook",
            name.span,
            related=[Related("declared here", target.span.location())],
        )

    def _reference(
        self, name: pdl.Name, guards: tuple[Guard, ...], function: str
    ) -> AnalysedAttribute | None:
        """The attribute ``val()``, ``offset()`` or ``len()`` names (bug 12)."""
        key = name.text.lower()
        target = self.attrs.get(key)
        if target is None and key in self.dropped:
            return None  # already reported where it is declared
        if target is None:
            later = self.declared_attrs.get(key)
            if later is not None:
                self._used_too_early(
                    "attribute", name, later, key == self.defining.get("attribute")
                )
            else:
                self.error(
                    "model.unknown-attribute",
                    f"{function}({name.text}) names no attribute"
                    + _did_you_mean(name.text, [n.text for n in self.declared_attrs.values()]),
                    name.span,
                )
            return None
        inner = [(g.conditional, g.holds) for g in target.guards]
        if inner != [(g.conditional, g.holds) for g in guards[: len(inner)]]:
            outer = target.guards[-1]
            self.error(
                "model.conditional-reference",
                f"{function}({name.text}) is used outside the branch that declares "
                f"`{target.name}`, which exists only when its if condition is "
                f"{'true' if outer.holds else 'false'}",
                name.span,
                related=[
                    Related("declared here", self.attr_names[key].span.location()),
                    Related("inside this if", outer.span.location()),
                ],
            )
            return None
        return target

    def _check_range(self, expr: Expr | None, low: int, what: str) -> None:
        if expr is None or expr.value is None:
            return
        if not low <= expr.value <= _INT_MAX:
            self.error(
                "model.out-of-range",
                f"{what} folds to {expr.value}; it must be from {low} to {_INT_MAX}",
                expr.span,
            )

    # -- element types and sizeof (bug 7) --

    def _element_type(self, t: pdl.ElementType, where: str) -> _TypeInfo | None:
        if isinstance(t, pdl.CType):
            dt = t.data_type
            kind = FieldKind.POINTER if t.pointer else FieldKind.INTEGER
            return _TypeInfo(kind, dt, FIXED_WIDTHS[dt], c_storage(dt))
        if isinstance(t, pdl.MmtType):
            width = FIXED_WIDTHS.get(t.type)
            if width is None:
                self.error(
                    "model.no-fixed-width",
                    f"{t.type.value} has no fixed width, so it cannot be {where}",
                    t.span,
                )
                return None
            return _TypeInfo(FieldKind.MMT, t.type, width, c_storage(t.type))
        key = t.name.text.lower()
        struct = self.structs.get(key)
        if struct is None:
            later = self.declared_structs.get(key)
            if later is not None:
                self._used_too_early("struct", t.name, later, key == self.defining.get("struct"))
            else:
                self.error(
                    "model.unknown-struct",
                    f"`struct {t.name.text}` is not defined"
                    + _did_you_mean(t.name.text, [s.name for s in self.struct_list]),
                    t.name.span,
                )
            return None
        storage = CStorage(f"struct {struct.name}", struct.c_size, struct.c_align)
        return _TypeInfo(FieldKind.STRUCT, DataType.MMT_BINARY_DATA, struct.size, storage)

    # -- the Attributes block --

    def _elements(
        self,
        elements: Sequence[pdl.AttributeElement],
        guards: tuple[Guard, ...],
        state: _State,
    ) -> tuple[tuple[Element, ...], _State]:
        out: list[Element] = []
        for el in elements:
            analysed: Element
            if isinstance(el, pdl.Attribute):
                analysed, state = self._attribute(el, guards, state)
            elif isinstance(el, pdl.Struct):
                analysed, state = self._struct(el, guards, state)
            else:
                analysed, state = self._conditional(el, guards, state)
            out.append(analysed)
        return tuple(out), state

    def _register(self, name: pdl.Name, attribute: AnalysedAttribute) -> None:
        self._check_alias(name, "attribute name")
        first = self.attr_names.get(attribute.key)
        if first is not None:
            # Conditional attributes included (bug 12), case-insensitively
            # (bug 16).
            self._duplicate("attribute", name, first.span)
        else:
            self.attrs[attribute.key] = attribute
            self.attr_names[attribute.key] = name
        self.attr_list.append(attribute)

    def _align(self, state: _State, name: pdl.Name) -> None:
        """Warn when R comes from an if/else whose branches disagree on it
        (plan decision 8)."""
        new = [m for m in state.pending if m.span not in self.reported]
        if not new:
            return
        self.reported.update(m.span for m in new)
        self.warning(
            "model.branch-offset-mismatch",
            f"the offset of `{name.text}` adds the running offset left by an if/else whose "
            "branches end at different offsets; PDL keeps the else branch's",
            name.span,
            related=[
                Related(
                    f"its then branch ends at {_end(m.then_end)}, its else branch at "
                    f"{_end(m.else_end)}",
                    m.span.location(),
                )
                for m in new
            ],
        )

    def _attribute(
        self, el: pdl.Attribute, guards: tuple[Guard, ...], state: _State
    ) -> tuple[AnalysedAttribute, _State]:
        """A plain attribute, with the defaults of bug 9 applied."""
        key = el.alias.text.lower()
        self.defining["attribute"] = key
        declared_offset = None if el.offset is None else self._expr(el.offset, guards)
        declared_len = None if el.data_len is None else self._expr(el.data_len, guards)
        del self.defining["attribute"]
        dt = el.data_type.type
        where = f"the offset of `{el.alias.text}`"
        if el.offset is not None and declared_offset is not None:
            if declared_offset.value is None:
                self._leading_zeros(el.offset, where)
            self._check_range(declared_offset, 0, where)
        if el.data_len is not None and declared_len is not None:
            where = f"the data_len of `{el.alias.text}`"
            if declared_len.value is None:
                self._leading_zeros(el.data_len, where)
            self._check_range(declared_len, 1, where)
        length: Expr | None = declared_len
        length_defaulted = False
        if declared_len is None and el.offset is not None:
            width = FIXED_WIDTHS.get(dt)
            if width is None:
                self.error(
                    "model.missing-length",
                    f"`{el.alias.text}` has an offset but no data_len, and {dt.value} has no "
                    "fixed width",
                    el.data_type.span,
                )
            else:
                length = Const(width, str(width), el.data_type.span)
                length_defaulted = True
        if el.scope is None:
            scope = Scope.PACKET
            self.warning(
                "model.default-scope",
                f"`{el.alias.text}` has no scope, so it is packet (SCOPE_PACKET)",
                el.alias.span,
            )
        else:
            scope = el.scope.value
        constant = (
            el.offset is not None
            and el.data_len is not None
            and declared_offset is not None
            and declared_len is not None
            and declared_offset.value is not None
            and declared_len.value is not None
            and _literal_only(el.offset)
            and _literal_only(el.data_len)
        )
        offset = declared_offset
        aligned = False
        if (
            state.aligned
            and constant
            and declared_offset is not None
            and declared_offset.value is not None
            and declared_len is not None
            and declared_len.value is not None
        ):
            self._align(state, el.alias)
            absolute = state.offset + declared_offset.value
            offset = Const(absolute, str(absolute), declared_offset.span)
            aligned = True
            state = _State(state.offset + declared_len.value, True)
        else:
            state = _State(state.offset, False)
        attribute = AnalysedAttribute(
            name=el.alias.text,
            key=key,
            kind=AttributeKind.PLAIN,
            data_type=dt,
            offset=offset,
            length=length,
            declared_offset=declared_offset,
            scope=scope,
            scope_defaulted=el.scope is None,
            length_defaulted=length_defaulted,
            aligned=aligned,
            guards=guards,
            struct=None,
            bitfield=None,
            span=el.span,
        )
        self._register(el.alias, attribute)
        return attribute, state

    def _struct(
        self, el: pdl.Struct, guards: tuple[Guard, ...], state: _State
    ) -> tuple[AnalysedStruct, _State]:
        """A struct's packed layout (bugs 2, 3, 4) and its bitfields (bug 17)."""
        key = el.name.text.lower()
        self.defining["struct"] = key
        fields: list[tuple[pdl.StructField, StructField, CStorage]] = []
        runs: list[_Run] = []
        offset = 0
        for element in el.elements:
            info = self._element_type(element.type, "a struct field")
            if isinstance(element.type, pdl.CType) and element.type.pointer:
                self.warning(
                    "model.pointer-field",
                    "a pointer field is 4 bytes on the wire and reads as MMT_DATA_POINTER, "
                    "whose value is only the field's position",
                    element.type.span,
                )
            run: _Run | None = None
            for f in element.fields:
                if info is None:
                    self.dropped.add(f.name.text.lower())
                    continue
                if f.bit_width is None:
                    run = None
                    fields.append((f, self._field(f, info, offset, None), info.storage))
                    offset += info.width
                    continue
                bitfield, run, offset = self._bitfield(f, info, run, runs, offset)
                if bitfield is None:
                    self.dropped.add(f.name.text.lower())
                else:
                    fields.append(
                        (f, self._field(f, info, bitfield.unit_offset, bitfield), info.storage)
                    )
        del self.defining["struct"]
        laid, c_size, c_align, held = _c_layout(fields)
        aligned = state.aligned
        base = 0
        if aligned:
            self._align(state, el.name)
            base = state.offset
            state = _State(state.offset + offset, True)
        for (source, _, _), sf in zip(fields, laid, strict=True):
            self._register(
                source.name, self._field_attribute(source, sf, el, base, aligned, guards)
            )
        struct = AnalysedStruct(
            name=el.name.text,
            key=key,
            size=offset,
            base_offset=base,
            aligned=aligned,
            fields=laid,
            runs=tuple(self._helper(el, r) for r in runs),
            c_size=c_size,
            c_align=c_align,
            c_padding=c_size - held,
            guards=guards,
            span=el.span,
        )
        first = self.struct_names.get(key)
        if first is not None:
            self._duplicate("struct", el.name, first.span)
        else:
            self.structs[key] = struct
            self.struct_names[key] = el.name
        self.struct_list.append(struct)
        return struct, state

    def _field(
        self, f: pdl.StructField, info: _TypeInfo, offset: int, bitfield: Bitfield | None
    ) -> StructField:
        return StructField(
            name=f.name.text,
            key=f.name.text.lower(),
            kind=info.kind,
            data_type=info.data_type,
            offset=offset,
            width=info.width,
            c_type=info.storage.c_type,
            c_offset=0,
            bitfield=bitfield,
            span=f.span,
        )

    def _bitfield(
        self,
        f: pdl.StructField,
        info: _TypeInfo,
        run: _Run | None,
        runs: list[_Run],
        offset: int,
    ) -> tuple[Bitfield | None, _Run | None, int]:
        """Place one bitfield, MSB first, in the run's storage unit (bugs 2
        and 3: the unit is counted once)."""
        assert f.bit_width is not None
        width = f.bit_width.value
        unit_bits = info.width * 8
        if info.kind is FieldKind.POINTER or info.data_type not in BITFIELD_TYPES:
            self.error(
                "model.invalid-bitfield",
                f"`{f.name.text}` is a bitfield of {info.storage.c_type}, which is not an "
                "integer type",
                f.span,
            )
            return None, run, offset
        if not 1 <= width <= unit_bits:
            self.error(
                "model.invalid-bitfield",
                f"`{f.name.text}` is {width} bits wide; a bitfield of a {unit_bits}-bit unit "
                f"is 1 to {unit_bits} bits",
                f.bit_width.span,
            )
            return None, run, offset
        if run is not None and run.used + width > unit_bits:
            self.error(
                "model.bitfield-overflow",
                f"`{f.name.text}` does not fit in its run's {unit_bits}-bit unit: "
                f"{run.used} bits are used and it needs {width} more",
                f.span,
                related=[Related("the run starts here", run.span.location())],
            )
            return None, run, offset
        if run is None:
            run = _Run(len(runs), offset, info, 0, [], f.span)
            runs.append(run)
            offset += info.width
        bitfield = Bitfield(run.index, run.offset, info.width, run.used, width)
        run.used += width
        run.fields.append(f.name.text)
        return bitfield, run, offset

    def _helper(self, el: pdl.Struct, run: _Run) -> BitfieldRun:
        """A run's helper struct, named uniquely (bug 17)."""
        name = f"{el.name.text}_bits{run.index + 1}"
        while name.lower() in self.helper_names:
            name += "_"
        self.helper_names.add(name.lower())
        return BitfieldRun(
            helper_name=name,
            offset=run.offset,
            width=run.info.width,
            c_type=run.info.storage.c_type,
            fields=tuple(run.fields),
            span=run.span,
        )

    def _field_attribute(
        self,
        f: pdl.StructField,
        sf: StructField,
        el: pdl.Struct,
        base: int,
        aligned: bool,
        guards: tuple[Guard, ...],
    ) -> AnalysedAttribute:
        absolute = base + sf.offset
        return AnalysedAttribute(
            name=sf.name,
            key=sf.key,
            kind=AttributeKind.BITFIELD if sf.bitfield else AttributeKind.FIELD,
            data_type=sf.data_type,
            offset=Const(absolute, str(absolute), f.name.span),
            length=Const(sf.width, str(sf.width), f.name.span),
            declared_offset=Const(sf.offset, str(sf.offset), f.name.span),
            scope=Scope.PACKET,
            scope_defaulted=False,
            length_defaulted=False,
            aligned=aligned,
            guards=guards,
            struct=el.name.text.lower(),
            bitfield=sf.bitfield,
            span=f.span,
        )

    def _conditional(
        self, el: pdl.Conditional, guards: tuple[Guard, ...], state: _State
    ) -> tuple[AnalysedConditional, _State]:
        """``if``/``else``: R and alignment come out of the else branch, or
        from before the if without one (decided rule)."""
        index = self.conditional_count
        self.conditional_count += 1
        condition = self._expr(el.condition, guards)
        # A condition is copied into the C as text, folded or not.
        self._leading_zeros(el.condition, "an if condition")
        then_guards = (*guards, Guard(index, condition, True, el.span))
        then_branch, then_state = self._elements(el.then_branch, then_guards, state)
        if el.else_branch is None:
            else_branch = None
            else_state = state
        else:
            else_guards = (*guards, Guard(index, condition, False, el.span))
            else_branch, else_state = self._elements(el.else_branch, else_guards, state)
        then_end = then_state.offset if then_state.aligned else None
        else_end = else_state.offset if else_state.aligned else None
        after = else_state
        if then_end != else_end:
            after = _State(
                else_state.offset,
                else_state.aligned,
                (*else_state.pending, _Mismatch(el.span, then_end, else_end)),
            )
        conditional = AnalysedConditional(index, condition, then_branch, else_branch, el.span)
        self.conditionals.append(conditional)
        return conditional, after

    # -- classifynext --

    def _switch(self, sw: pdl.Switch) -> AnalysedSwitch:
        subject = self._expr(sw.subject, ())
        self._leading_zeros(sw.subject, "the switch subject")
        seen: dict[int, Span] = {}
        cases = []
        for case in sw.cases:
            label, alias_of = self._number(case.label, "a case label")
            if label is not None:
                first = seen.get(label)
                if first is not None:
                    self.error(
                        "model.duplicate-case",
                        f"case {label} is already handled",
                        case.label.span,
                        related=[Related("first handled here", first.location())],
                    )
                else:
                    seen[label] = case.label.span
            cases.append(
                AnalysedCase(
                    label=0 if label is None else label,
                    alias_of=alias_of,
                    statements=self._statements(case.statements),
                    has_break=case.has_break,
                    span=case.span,
                )
            )
        default = None
        if sw.default is not None:
            default = AnalysedDefault(
                self._statements(sw.default.statements), sw.default.has_break, sw.default.span
            )
        return AnalysedSwitch(subject, tuple(cases), default, sw.span)

    def _number(
        self, value: pdl.IntLiteral | pdl.Name, where: str
    ) -> tuple[int | None, str | None]:
        if isinstance(value, pdl.IntLiteral):
            self._leading_zero(value, where)
            return value.value, None
        resolved = self._resolve_name(value)
        if resolved is None:
            return None, None
        return resolved

    def _statements(self, statements: Sequence[pdl.Statement]) -> tuple[Statement, ...]:
        out: list[Statement] = []
        for st in statements:
            if isinstance(st, pdl.NextEncaps):
                pid, alias_of = self._number(st.value, "a nextencaps value")
                if pid is not None and not (
                    pid >= 1 and (self.max_id is None or pid < self.max_id)
                ):
                    self.error(
                        "model.id-out-of-range",
                        f"nextencaps names protocol id {pid}, which no protocol can have",
                        st.value.span,
                    )
                out.append(SetNextProto(NextProto(pid or 0, alias_of, st.value.span), st.span))
            else:
                offset = self._expr(st.value, ())
                if offset.value is None:
                    self._leading_zeros(st.value, "a nextoffset value")
                self._check_range(offset, 0, "nextoffset")
                out.append(SetNextOffset(offset, st.span))
        return tuple(out)


def _c_layout(
    fields: Sequence[tuple[pdl.StructField, StructField, CStorage]],
) -> tuple[tuple[StructField, ...], int, int, int]:
    """The natural C layout of a struct (LP64): one slot per plain field or
    bitfield unit, each at the next multiple of its alignment.

    Returns the fields with their ``c_offset``, the C size and alignment, and
    the bytes the slots hold (the padding is the size minus that).
    """
    laid: list[StructField] = []
    run_offsets: dict[int, int] = {}
    cursor = 0
    align = 1
    held = 0
    for _, sf, storage in fields:
        if sf.bitfield is not None and sf.bitfield.run in run_offsets:
            laid.append(dataclasses.replace(sf, c_offset=run_offsets[sf.bitfield.run]))
            continue
        cursor = -(-cursor // storage.align) * storage.align
        if sf.bitfield is not None:
            run_offsets[sf.bitfield.run] = cursor
        laid.append(dataclasses.replace(sf, c_offset=cursor))
        cursor += storage.size
        held += storage.size
        align = max(align, storage.align)
    return tuple(laid), -(-cursor // align) * align, align, held
