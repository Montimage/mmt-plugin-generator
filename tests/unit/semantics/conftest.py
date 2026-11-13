"""Shared helpers for the semantic-pass tests: small models, analysis and an
evaluator of analysed expressions over packet bytes."""

from __future__ import annotations

from collections.abc import Sequence

from mmt_plugin.diagnostics import Diagnostic, Location, Severity
from mmt_plugin.pdl import Model, parse
from mmt_plugin.sdk import Profile, get_bundled
from mmt_plugin.semantics import AnalysedModel, analyse
from mmt_plugin.semantics.analyse import _fold
from mmt_plugin.semantics.model import (
    AnalysedAttribute,
    Binary,
    ByteOrder,
    Const,
    Expr,
    LengthRef,
    OffsetRef,
    SizeOfType,
    Swap,
    ValueRef,
)

#: The name the tests give their inline models.
FILE = "test.pdl"


def profile() -> Profile:
    """The bundled 1.10.2 profile."""
    found = get_bundled("1.10.2")
    assert found is not None
    return found


def build(
    attributes: str = "",
    *,
    defines: str = "",
    properties: str = 'label = "p"\n\t\tid = "960"',
    classify: str = "",
) -> str:
    """A whole model around the given parts, one part per block."""
    return (
        "Protocol {\n"
        f"{defines}"
        f"\tProperties {{\n\t\t{properties}\n\t}}\n"
        f"\tAttributes {{\n{attributes}\n\t}}\n"
        f"{classify}"
        "}\n"
    )


def attr(text: str) -> str:
    """One attribute block."""
    return f"\t\tattribute {{ {text} }}\n"


def u8(name: str, offset: str, *, length: str = "1", scope: str = "packet") -> str:
    """A one-byte attribute with an explicit scope."""
    return attr(
        f'alias="{name}" data_type="MMT_U8_DATA" data_len="{length}" offset="{offset}" '
        f'scope="{scope}"'
    )


def classify(body: str) -> str:
    """A classifynext block around a switch body."""
    return f"\tclassifynext {{\n\t\tswitch(1) {{\n{body}\n\t\t\tdefault: break\n\t\t}}\n\t}}\n"


def parse_model(text: str) -> Model:
    return parse(text, filename=FILE)


def whole(text: str) -> str:
    """``text`` if it is a whole model, else the model around these attributes."""
    return text if text.startswith("Protocol") else build(text)


def run(text: str) -> tuple[AnalysedModel | None, list[Diagnostic]]:
    """Parse and analyse ``text`` (a model, or the attributes of one); every
    diagnostic has a hint and a location."""
    analysed, diagnostics = analyse(parse_model(whole(text)), profile=profile())
    for d in diagnostics:
        assert d.hint, f"{d.code} has no hint"
        assert d.location is not None and d.location.file == FILE
    return analysed, diagnostics


def ok(text: str) -> AnalysedModel:
    """The analysed model of ``text``, which has no error and no warning."""
    analysed, diagnostics = run(text)
    assert diagnostics == [], [d.code for d in diagnostics]
    assert analysed is not None
    return analysed


def codes(diagnostics: Sequence[Diagnostic]) -> list[str]:
    return [d.code for d in diagnostics]


def errors(text: str) -> list[Diagnostic]:
    """The error diagnostics of ``text``, which must not analyse."""
    analysed, diagnostics = run(text)
    assert analysed is None
    found = [d for d in diagnostics if d.severity is Severity.ERROR]
    assert found
    return found


def covered(text: str, location: Location | None) -> str:
    """The text a single-line location covers."""
    assert location is not None and location.line is not None
    assert location.column is not None and location.end_column is not None
    assert location.end_line == location.line
    line = text.splitlines()[location.line - 1]
    return line[location.column - 1 : location.end_column - 1]


# --- evaluating an analysed model over packet bytes ---------------------------


class Packet:
    """Evaluates the analysed expressions of a model over packet bytes, as a
    generated plugin would."""

    def __init__(self, model: AnalysedModel, data: bytes) -> None:
        self.model = model
        self.data = data
        self.order = "little" if model.protocol.byte_order is ByteOrder.LITTLE else "big"

    def eval(self, expr: Expr) -> int:
        if isinstance(expr, (Const, SizeOfType, Swap)):
            return expr.value
        if isinstance(expr, ValueRef):
            return self.value(self.model.attribute(expr.attribute))
        if isinstance(expr, OffsetRef):
            return self.offset(self.model.attribute(expr.attribute))
        if isinstance(expr, LengthRef):
            return self.length(self.model.attribute(expr.attribute))
        assert isinstance(expr, Binary)
        return _fold(expr.op, self.eval(expr.left), self.eval(expr.right))

    def offset(self, attribute: AnalysedAttribute) -> int:
        assert attribute.offset is not None
        return self.eval(attribute.offset)

    def length(self, attribute: AnalysedAttribute) -> int:
        assert attribute.length is not None
        return self.eval(attribute.length)

    def present(self, attribute: AnalysedAttribute) -> bool:
        return all(bool(self.eval(g.condition)) == g.holds for g in attribute.guards)

    def value(self, attribute: AnalysedAttribute) -> int:
        start = self.offset(attribute)
        unit = int.from_bytes(self.data[start : start + self.length(attribute)], self.order)  # type: ignore[arg-type]
        bitfield = attribute.bitfield
        if bitfield is None:
            return unit
        return (unit >> bitfield.shift) & bitfield.mask
