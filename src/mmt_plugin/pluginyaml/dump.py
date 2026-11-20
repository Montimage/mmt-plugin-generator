"""Writing a model as ``plugin.yaml``.

``to_document`` turns a model (``mmt_plugin.pdl.model``, from either format)
into the plain data of a ``plugin.yaml`` document, which the JSON Schema
validates; ``dumps`` writes it as YAML text in the subset that
``mmt_plugin.pluginyaml.load`` reads, in block style, keys in schema order.

What is written is what the model says, spelled as it was where the format
allows it: numbers keep their spelling (``0x3BC``), expressions are printed
back in PDL v1 syntax with the parentheses their tree needs, names keep their
case. With absolute offsets (the default), a model read with PDL v1's running
offset needs its analysis: an attribute or struct the running offset placed
gets the absolute offset the semantic passes computed for it, so that the
YAML model has the same layout. ``scope`` is written for session attributes
only, and ``length`` only where the model gives one.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from mmt_plugin.pdl import model as pdl
from mmt_plugin.pluginyaml.nodes import Mapping, Scalar, YamlError, parse
from mmt_plugin.semantics.model import AnalysedAttribute, AnalysedModel, AnalysedStruct

__all__ = ["dumps", "expression_text", "to_document"]

#: The integer spellings the loader reads as YAML 1.1 and 1.2 do (no
#: leading zero, which YAML 1.1 reads as octal).
_INT_TEXT = re.compile(r"-?(0|[1-9][0-9]*)|0x[0-9A-Fa-f]+")

_PRECEDENCE = {
    pdl.BinaryOperator.OR: 1,
    pdl.BinaryOperator.AND: 2,
    pdl.BinaryOperator.EQ: 3,
    pdl.BinaryOperator.NE: 3,
    pdl.BinaryOperator.GT: 3,
    pdl.BinaryOperator.LT: 3,
    pdl.BinaryOperator.GE: 3,
    pdl.BinaryOperator.LE: 3,
    pdl.BinaryOperator.ADD: 4,
    pdl.BinaryOperator.SUB: 4,
    pdl.BinaryOperator.MUL: 5,
    pdl.BinaryOperator.DIV: 5,
}
_ATOM = 6


@dataclass(frozen=True)
class _Int:
    """An integer with its spelling."""

    value: int
    text: str


def _int(literal: pdl.IntLiteral) -> _Int:
    text = literal.text if _INT_TEXT.fullmatch(literal.text) else str(literal.value)
    return _Int(literal.value, text)


def _precedence(expr: pdl.Expr) -> int:
    return _PRECEDENCE[expr.op] if isinstance(expr, pdl.BinaryOp) else _ATOM


def element_type_text(t: pdl.ElementType) -> str:
    """A struct field type in PDL v1 syntax."""
    if isinstance(t, pdl.StructType):
        return f"struct {t.name.text}"
    if isinstance(t, pdl.MmtType):
        return t.type.value
    return ("unsigned " if t.unsigned else "") + t.name + ("*" if t.pointer else "")


def expression_text(expr: pdl.Expr) -> str:
    """``expr`` in PDL v1 syntax: it parses back to the same tree."""
    if isinstance(expr, pdl.IntLiteral):
        return expr.text
    if isinstance(expr, pdl.ValueOf):
        return f"val({expr.attribute.text})"
    if isinstance(expr, pdl.OffsetOf):
        return f"offset({expr.attribute.text})"
    if isinstance(expr, pdl.LengthOf):
        return f"len({expr.attribute.text})"
    if isinstance(expr, pdl.SizeOf):
        return f"sizeof({element_type_text(expr.type)})"
    if isinstance(expr, pdl.ByteSwap):
        return f"{'ntohs' if expr.width == 16 else 'ntohl'}({expr.operand.text})"
    p = _PRECEDENCE[expr.op]
    left, right = expression_text(expr.left), expression_text(expr.right)
    # Comparisons do not chain; the other operators associate to the left.
    if _precedence(expr.left) < p or (p == 3 and _precedence(expr.left) == 3):
        left = f"({left})"
    if _precedence(expr.right) <= p:
        right = f"({right})"
    return f"{left} {expr.op.value} {right}"


def _expr(expr: pdl.Expr) -> _Int | str:
    if isinstance(expr, pdl.IntLiteral):
        return _int(expr)
    return expression_text(expr)


def _number_or_name(value: pdl.IntLiteral | pdl.Name) -> _Int | str:
    return value.text if isinstance(value, pdl.Name) else _int(value)


class _Writer:
    def __init__(self, model: pdl.Model, offsets: pdl.Offsets, analysed: AnalysedModel | None):
        self.model = model
        self.convert = model.offsets is pdl.Offsets.RUNNING and offsets is pdl.Offsets.ABSOLUTE
        self.offsets = offsets
        self.attributes: dict[pdl.Span, AnalysedAttribute] = {}
        self.structs: dict[pdl.Span, AnalysedStruct] = {}
        if analysed is not None:
            self.attributes = {a.span: a for a in analysed.attributes}
            self.structs = {s.span: s for s in analysed.structs}

    def document(self, sdk_profile: str | None) -> dict[str, Any]:
        m = self.model
        doc: dict[str, Any] = {"schema": _Int(1, "1"), "protocol": self.protocol(m.properties)}
        if sdk_profile is not None:
            doc["sdk"] = {"profile": sdk_profile}
        if self.offsets is pdl.Offsets.RUNNING:
            doc["offsets"] = "running"
        if m.defines:
            doc["defines"] = {d.name.text: _number_or_name(d.value) for d in m.defines}
        if m.parents:
            doc["parents"] = [self.parent(p) for p in m.parents]
        if m.plugins:
            doc["plugins"] = [p.path for p in m.plugins]
        doc["attributes"] = self.elements(m.attributes.elements)
        if m.classify_next is not None:
            doc["classify_next"] = self.classify_next(m.classify_next.switch)
        return doc

    def protocol(self, p: pdl.Properties) -> dict[str, Any]:
        out: dict[str, Any] = {"label": p.label.text, "id": _int(p.id)}
        for key in ("context", "session_context", "session", "encapsulation"):
            flag = getattr(p, key)
            if flag is not None:
                out[key] = flag.value
        if p.encoding is not None:
            out["encoding"] = p.encoding.spelling
        return out

    def parent(self, p: pdl.Parent) -> dict[str, Any]:
        out: dict[str, Any] = {"protocol": p.protocol.text}
        if p.weight is not None:
            out["weight"] = _int(p.weight)
        if p.classify is not None:
            classify: dict[str, Any] = {k: _int(v) for k, v in p.classify.ports}
            if p.classify.match or p.classify.offset is not None:
                classify["match"] = [
                    {"offset": _int(t.offset), "length": _int(t.length), "value": _int(t.value)}
                    for t in p.classify.match
                ]
            if p.classify.offset is not None:
                classify["offset"] = _int(p.classify.offset)
            out["classify"] = classify
        return out

    def elements(self, elements: tuple[pdl.AttributeElement, ...]) -> list[Any]:
        out: list[Any] = []
        for el in elements:
            if isinstance(el, pdl.Attribute):
                out.append(self.attribute(el))
            elif isinstance(el, pdl.Struct):
                out.append(self.struct(el))
            else:
                cond: dict[str, Any] = {
                    "if": _expr(el.condition),
                    "then": self.elements(el.then_branch),
                }
                if el.else_branch is not None:
                    cond["else"] = self.elements(el.else_branch)
                out.append(cond)
        return out

    def attribute(self, el: pdl.Attribute) -> dict[str, Any]:
        out: dict[str, Any] = {"name": el.alias.text, "type": el.data_type.type.value}
        if el.offset is not None:
            analysed = self.attributes.get(el.span)
            if self.convert and analysed is not None and analysed.aligned:
                value = analysed.offset_value
                assert value is not None
                out["offset"] = _Int(value, str(value))
            else:
                out["offset"] = _expr(el.offset)
        if el.data_len is not None:
            out["length"] = _expr(el.data_len)
        if el.scope is not None and el.scope.value is pdl.Scope.SESSION:
            out["scope"] = "session"
        return out

    def struct(self, el: pdl.Struct) -> dict[str, Any]:
        out: dict[str, Any] = {"struct": el.name.text}
        offset: _Int | None = None if el.offset is None else _int(el.offset)
        if self.convert:
            analysed = self.structs.get(el.span)
            if analysed is not None and analysed.base_offset:
                offset = _Int(analysed.base_offset, str(analysed.base_offset))
        if offset is not None and offset.value:
            out["offset"] = offset
        fields: list[Any] = []
        for element in el.elements:
            etype = element_type_text(element.type)
            run: list[Any] | None = None
            for f in element.fields:
                if f.bit_width is None:
                    run = None
                    fields.append({"name": f.name.text, "type": etype})
                    continue
                if run is None:
                    run = []
                    fields.append({"type": etype, "bits": run})
                run.append({"name": f.name.text, "width": _int(f.bit_width)})
        out["fields"] = fields
        return out

    def statements(self, statements: tuple[pdl.Statement, ...], has_break: bool) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for st in statements:
            # A later statement of the same kind wins, as in the C.
            if isinstance(st, pdl.NextEncaps):
                out.pop("next", None)
                out["next"] = _number_or_name(st.value)
            else:
                out.pop("offset", None)
                out["offset"] = _expr(st.value)
        if not has_break:
            out["fallthrough"] = True
        return out

    def classify_next(self, switch: pdl.Switch) -> dict[str, Any]:
        out: dict[str, Any] = {"switch": _expr(switch.subject)}
        if switch.cases:
            out["cases"] = [
                {"case": _number_or_name(c.label), **self.statements(c.statements, c.has_break)}
                for c in switch.cases
            ]
        if switch.default is not None:
            out["default"] = self.statements(switch.default.statements, switch.default.has_break)
        return out


def _document(
    model: pdl.Model,
    offsets: pdl.Offsets,
    analysed: AnalysedModel | None,
    sdk_profile: str | None,
) -> dict[str, Any]:
    if model.offsets is pdl.Offsets.ABSOLUTE and offsets is pdl.Offsets.RUNNING:
        raise ValueError("a model with absolute offsets cannot be written with running offsets")
    converts = model.offsets is pdl.Offsets.RUNNING and offsets is pdl.Offsets.ABSOLUTE
    if converts and (analysed is None or analysed.source is not model):
        raise ValueError("absolute offsets of a running-offset model need its analysis")
    return _Writer(model, offsets, analysed).document(sdk_profile)


def _plain(value: Any) -> Any:
    if isinstance(value, _Int):
        return value.value
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_plain(v) for v in value]
    return value


def to_document(
    model: pdl.Model | AnalysedModel,
    *,
    offsets: pdl.Offsets = pdl.Offsets.ABSOLUTE,
    sdk_profile: str | None = None,
) -> dict[str, Any]:
    """The ``plugin.yaml`` document of ``model``, as plain data.

    ``model`` is an analysed model, or a parsed one when no offset needs
    converting (its ``offsets`` already are ``offsets``). Raises
    ``ValueError`` for absolute offsets of a running-offset model without
    its analysis, and for running offsets of an absolute model.
    """
    source, analysed = (model.source, model) if isinstance(model, AnalysedModel) else (model, None)
    return dict(_plain(_document(source, offsets, analysed, sdk_profile)))


# --- the YAML text -----------------------------------------------------------


def _plain_ok(text: str) -> bool:
    """Whether ``text`` reads back as the same string written plain, in this
    subset and in YAML 1.1 and 1.2."""
    # A value that starts like a number is quoted: YAML 1.1 reads 1.10.2 as
    # a float, for one.
    if not text or text != text.strip() or text[0] in "#,[]{}\"'+-.0123456789" or "\n" in text:
        return False
    try:
        node = parse(f"k: {text}\n")
    except YamlError:
        return False
    value = node.get("k") if isinstance(node, Mapping) else None
    return isinstance(value, Scalar) and value.value == text


def _scalar(value: Any) -> str:
    if isinstance(value, _Int):
        return value.text
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    assert isinstance(value, str), value
    return value if _plain_ok(value) else json.dumps(value, ensure_ascii=False)


def _key(key: str) -> str:
    return key if _plain_ok(key) else json.dumps(key, ensure_ascii=False)


def _lines(value: Any, indent: int) -> Iterator[str]:
    pad = " " * indent
    if isinstance(value, dict):
        for k, v in value.items():
            if isinstance(v, (dict, list)) and v:
                yield f"{pad}{_key(k)}:"
                yield from _lines(v, indent + 2)
            elif isinstance(v, dict):
                yield f"{pad}{_key(k)}: {{}}"
            elif isinstance(v, list):
                yield f"{pad}{_key(k)}: []"
            else:
                yield f"{pad}{_key(k)}: {_scalar(v)}"
        return
    assert isinstance(value, list)
    for item in value:
        if isinstance(item, dict) and item:
            inner = list(_lines(item, indent + 2))
            yield f"{pad}- {inner[0][indent + 2 :]}"
            yield from inner[1:]
        elif isinstance(item, list) and item:
            yield f"{pad}-"
            yield from _lines(item, indent + 2)
        elif isinstance(item, (dict, list)):
            yield f"{pad}- {'{}' if isinstance(item, dict) else '[]'}"
        else:
            yield f"{pad}- {_scalar(item)}"


def dumps(
    model: pdl.Model | AnalysedModel,
    *,
    offsets: pdl.Offsets = pdl.Offsets.ABSOLUTE,
    sdk_profile: str | None = None,
) -> str:
    """``model`` as ``plugin.yaml`` text, ending in a newline (as
    ``to_document``, which says what ``model`` may be)."""
    source, analysed = (model.source, model) if isinstance(model, AnalysedModel) else (model, None)
    document = _document(source, offsets, analysed, sdk_profile)
    return "\n".join(_lines(document, 0)) + "\n"
