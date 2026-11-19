"""Reading ``plugin.yaml`` into the typed model of ``mmt_plugin.pdl.model``.

Three passes, each reported with its own diagnostic codes (exit 3):

1. the YAML subset (``mmt_plugin.pluginyaml.nodes``): ``model.yaml``;
2. the JSON Schema (``mmt_plugin.pluginyaml.schema``): ``model.schema``, at
   the offending node, plus the one rule a JSON Schema does not say (a
   struct has no ``offset`` under ``offsets: running``);
3. the expressions and struct field types, written in PDL v1's syntax:
   ``model.syntax.*``, at their place inside the YAML value.

The model it builds is the one the PDL v1 parser builds, so the semantic
passes, code generation and every command read both formats the same way.
Spans point into the YAML: a node's first character to just past its last.
"""

from __future__ import annotations

from dataclasses import dataclass

from mmt_plugin.diagnostics import Diagnostic, Severity, sorted_diagnostics
from mmt_plugin.pdl import model as pdl
from mmt_plugin.pdl.parser import (
    ENCODINGS,
    PdlSyntaxError,
    parse_element_type,
    parse_expression,
)
from mmt_plugin.pluginyaml.nodes import Mapping, Node, Scalar, Sequence, YamlError, parse
from mmt_plugin.pluginyaml.schema import validate

__all__ = ["DIAGNOSTIC_CODES", "PluginYaml", "PluginYamlError", "load", "profile_pin"]

#: The codes of reading plugin.yaml (besides the PDL v1 syntax codes of its
#: expressions), and of what only plugin.yaml says: a classification by
#: TCP port under another parent (``model.classify-port``, which the
#: semantic passes report).
DIAGNOSTIC_CODES = ("model.yaml-syntax", "model.schema", "model.classify-port")

_SCOPES = {"packet": pdl.Scope.PACKET, "session": pdl.Scope.SESSION}


class PluginYamlError(PdlSyntaxError):
    """``plugin.yaml`` cannot be read: ``diagnostics`` (``model.yaml``,
    ``model.schema`` or ``model.syntax.*``), sorted. A ``PdlSyntaxError``, so
    that a caller reading either format catches one exception."""


@dataclass(frozen=True)
class PluginYaml:
    """A read ``plugin.yaml``: the model, and its ``sdk.profile`` pin."""

    model: pdl.Model
    sdk_profile: str | None


def _span(file: str, node: Node) -> pdl.Span:
    return pdl.Span(file, node.line, node.column, node.end_line, node.end_column)


def profile_pin(text: str) -> str | None:
    """``sdk.profile`` of a ``plugin.yaml`` text, or ``None`` when it has
    none or cannot be read (reading the model reports why)."""
    try:
        root = parse(text)
    except YamlError:
        return None
    if not isinstance(root, Mapping):
        return None
    sdk = root.get("sdk")
    if not isinstance(sdk, Mapping):
        return None
    profile = sdk.get("profile")
    if isinstance(profile, Scalar) and isinstance(profile.value, str):
        return profile.value
    return None


class _Builder:
    """Builds the model from nodes that follow the schema."""

    def __init__(self, file: str) -> None:
        self.file = file
        self.errors: list[Diagnostic] = []

    def span(self, node: Node) -> pdl.Span:
        return _span(self.file, node)

    # -- leaves --

    def scalar(self, node: Node | None) -> Scalar:
        assert isinstance(node, Scalar), node
        return node

    def name(self, node: Node | None) -> pdl.Name:
        s = self.scalar(node)
        return pdl.Name(s.text, self.span(s))

    def integer(self, node: Node | None) -> pdl.IntLiteral:
        s = self.scalar(node)
        assert isinstance(s.value, int) and not isinstance(s.value, bool)
        return pdl.IntLiteral(s.value, s.text, self.span(s))

    def number_or_name(self, node: Node | None) -> pdl.IntLiteral | pdl.Name:
        s = self.scalar(node)
        if isinstance(s.value, str):
            return self.name(s)
        return self.integer(s)

    def flag(self, node: Node | None) -> pdl.Flag | None:
        if node is None:
            return None
        s = self.scalar(node)
        assert isinstance(s.value, bool)
        return pdl.Flag(s.value, self.span(s))

    def expr(self, node: Node | None) -> pdl.Expr | None:
        """A number, or a PDL v1 expression; ``None`` (with the error kept)
        when it does not parse."""
        s = self.scalar(node)
        if not isinstance(s.value, str):
            return self.integer(s)
        try:
            return parse_expression(
                s.value, filename=self.file, line=s.line, column=s.value_column
            )
        except PdlSyntaxError as exc:
            self.errors += exc.diagnostics
            return None

    def element_type(self, node: Node | None) -> pdl.ElementType | None:
        s = self.scalar(node)
        assert isinstance(s.value, str)
        try:
            return parse_element_type(
                s.value, filename=self.file, line=s.line, column=s.value_column
            )
        except PdlSyntaxError as exc:
            self.errors += exc.diagnostics
            return None

    # -- the document --

    def model(self, root: Mapping) -> pdl.Model:
        offsets_node = root.get("offsets")
        offsets = pdl.Offsets.ABSOLUTE
        if offsets_node is not None:
            offsets = pdl.Offsets(self.scalar(offsets_node).value)
        self.offsets = offsets
        defines = self.defines(root.get("defines"))
        properties = self.properties(root.get("protocol"))
        attributes_node = root.get("attributes")
        if attributes_node is None:
            attributes = pdl.Attributes((), self.span(root))
        else:
            assert isinstance(attributes_node, Sequence)
            attributes = pdl.Attributes(self.elements(attributes_node), self.span(attributes_node))
        classify = root.get("classify_next")
        parents = root.get("parents")
        return pdl.Model(
            defines=defines,
            properties=properties,
            attributes=attributes,
            classify_next=None if classify is None else self.classify_next(classify),
            span=self.span(root),
            offsets=offsets,
            parents=() if parents is None else self.parents(parents),
        )

    def defines(self, node: Node | None) -> tuple[pdl.Define, ...]:
        if node is None:
            return ()
        assert isinstance(node, Mapping)
        return tuple(
            pdl.Define(
                pdl.Name(k.text, self.span(k)),
                self.number_or_name(v),
                self.span(k).to(self.span(v)),
            )
            for k, v in node.items
        )

    def properties(self, node: Node | None) -> pdl.Properties:
        assert isinstance(node, Mapping)
        encoding = None
        enc = node.get("encoding")
        if enc is not None:
            s = self.scalar(enc)
            assert isinstance(s.value, str)
            encoding = pdl.EncodingValue(ENCODINGS[s.value], s.value, self.span(s))
        return pdl.Properties(
            label=self.name(node.get("label")),
            id=self.integer(node.get("id")),
            context=self.flag(node.get("context")),
            session_context=self.flag(node.get("session_context")),
            session=self.flag(node.get("session")),
            encapsulation=self.flag(node.get("encapsulation")),
            encoding=encoding,
            span=self.span(node),
        )

    def parents(self, node: Node) -> tuple[pdl.Parent, ...]:
        assert isinstance(node, Sequence)
        out = []
        for item in node.items:
            assert isinstance(item, Mapping)
            weight = item.get("weight")
            classify = item.get("classify")
            out.append(
                pdl.Parent(
                    protocol=self.name(item.get("protocol")),
                    weight=None if weight is None else self.integer(weight),
                    classify=None if classify is None else self.parent_classify(classify),
                    span=self.span(item),
                )
            )
        return tuple(out)

    def parent_classify(self, node: Node) -> pdl.ParentClassify:
        assert isinstance(node, Mapping)
        match = node.get("match")
        assert match is None or isinstance(match, Sequence)
        tests = []
        for m in () if match is None else match.items:
            assert isinstance(m, Mapping)
            tests.append(
                pdl.ParentMatch(
                    offset=self.integer(m.get("offset")),
                    length=self.integer(m.get("length")),
                    value=self.integer(m.get("value")),
                    span=self.span(m),
                )
            )
        offset, port, sport, dport = (node.get(k) for k in ("offset", "port", "sport", "dport"))
        return pdl.ParentClassify(
            tuple(tests),
            None if offset is None else self.integer(offset),
            self.span(node),
            port=None if port is None else self.integer(port),
            sport=None if sport is None else self.integer(sport),
            dport=None if dport is None else self.integer(dport),
        )

    # -- attributes --

    def elements(self, node: Node | None) -> tuple[pdl.AttributeElement, ...]:
        assert isinstance(node, Sequence)
        out: list[pdl.AttributeElement] = []
        for item in node.items:
            assert isinstance(item, Mapping)
            if item.key("struct") is not None:
                out.append(self.struct(item))
            elif item.key("if") is not None:
                out.append(self.conditional(item))
            else:
                out.append(self.attribute(item))
        return tuple(out)

    def attribute(self, node: Mapping) -> pdl.Attribute:
        type_node = self.scalar(node.get("type"))
        assert isinstance(type_node.value, str)
        offset = node.get("offset")
        length = node.get("length")
        scope = node.get("scope")
        name = self.name(node.get("name"))
        if scope is None:
            # plugin.yaml's default: no warning, as there is for PDL v1.
            scope_value = pdl.ScopeValue(pdl.Scope.PACKET, "packet", name.span)
        else:
            s = self.scalar(scope)
            assert isinstance(s.value, str)
            scope_value = pdl.ScopeValue(_SCOPES[s.value], s.value, self.span(s))
        return pdl.Attribute(
            alias=name,
            data_type=pdl.DataTypeValue(pdl.DataType(type_node.value), self.span(type_node)),
            data_len=None if length is None else self.expr(length),
            offset=None if offset is None else self.expr(offset),
            scope=scope_value,
            span=self.span(node),
        )

    def struct(self, node: Mapping) -> pdl.Struct:
        offset = node.get("offset")
        if offset is not None and self.offsets is pdl.Offsets.RUNNING:
            key = node.key("offset")
            assert key is not None
            self.errors.append(
                Diagnostic(
                    Severity.ERROR,
                    "model.schema",
                    f"struct {self.scalar(node.get('struct')).text}: a struct has no offset with"
                    " `offsets: running`, where the running offset places it",
                    "drop the offset, or use `offsets: absolute` (the default)",
                    self.span(key).location(),
                )
            )
        fields = node.get("fields")
        assert isinstance(fields, Sequence)
        elements: list[pdl.Element] = []
        for f in fields.items:
            assert isinstance(f, Mapping)
            etype = self.element_type(f.get("type"))
            bits = f.get("bits")
            names: tuple[pdl.StructField, ...]
            if bits is None:
                names = (pdl.StructField(self.name(f.get("name")), None, self.span(f)),)
            else:
                assert isinstance(bits, Sequence)
                names = tuple(
                    pdl.StructField(
                        self.name(b.get("name")), self.integer(b.get("width")), self.span(b)
                    )
                    for b in bits.items
                    if isinstance(b, Mapping)
                )
            if etype is not None:
                elements.append(pdl.Element(etype, names, self.span(f)))
        return pdl.Struct(
            name=self.name(node.get("struct")),
            elements=tuple(elements),
            span=self.span(node),
            offset=None if offset is None else self.integer(offset),
        )

    def conditional(self, node: Mapping) -> pdl.Conditional:
        condition = self.expr(node.get("if"))
        else_node = node.get("else")
        if condition is None:  # its syntax error is kept
            condition = pdl.IntLiteral(0, "0", self.span(node))
        result = pdl.Conditional(
            condition=condition,
            then_branch=self.elements(node.get("then")),
            else_branch=None if else_node is None else self.elements(else_node),
            span=self.span(node),
        )
        return result

    # -- classify_next --

    def statements(self, node: Mapping) -> tuple[tuple[pdl.Statement, ...], bool]:
        out: list[pdl.Statement] = []
        fallthrough = False
        for key, value in node.items:
            if key.text == "next":
                out.append(
                    pdl.NextEncaps(self.number_or_name(value), self.span(key).to(self.span(value)))
                )
            elif key.text == "offset":
                expr = self.expr(value)
                if expr is not None:
                    out.append(pdl.NextOffset(expr, self.span(key).to(self.span(value))))
            elif key.text == "fallthrough":
                v = self.scalar(value).value
                fallthrough = bool(v)
        return tuple(out), not fallthrough

    def classify_next(self, node: Node) -> pdl.ClassifyNext:
        assert isinstance(node, Mapping)
        subject = self.expr(node.get("switch"))
        cases: list[pdl.Case] = []
        cases_node = node.get("cases")
        if cases_node is not None:
            assert isinstance(cases_node, Sequence)
            for c in cases_node.items:
                assert isinstance(c, Mapping)
                statements, has_break = self.statements(c)
                cases.append(
                    pdl.Case(
                        self.number_or_name(c.get("case")), statements, has_break, self.span(c)
                    )
                )
        default = None
        default_node = node.get("default")
        if default_node is not None:
            assert isinstance(default_node, Mapping)
            statements, has_break = self.statements(default_node)
            default = pdl.Default(statements, has_break, self.span(default_node))
        span = self.span(node)
        switch = pdl.Switch(
            subject if subject is not None else pdl.IntLiteral(0, "0", span),
            tuple(cases),
            default,
            span,
        )
        return pdl.ClassifyNext(switch, span)


def _diagnostic(file: str, code: str, message: str, hint: str | None, node: Node) -> Diagnostic:
    return Diagnostic(Severity.ERROR, code, message, hint, _span(file, node).location())


def load(text: str, *, filename: str) -> PluginYaml:
    """Read a ``plugin.yaml`` text; ``filename`` names it in spans and
    diagnostics. Raises ``PluginYamlError`` when it cannot be read: a YAML
    error stops at the first one, the schema and the expressions report all
    of theirs."""
    try:
        root = parse(text)
    except YamlError as exc:
        raise PluginYamlError(
            [
                Diagnostic(
                    Severity.ERROR,
                    "model.yaml-syntax",
                    exc.message,
                    "plugin.yaml is written in a subset of YAML: block mappings and lists, "
                    "one-line [lists] and {mappings} of values, quoted or plain values and "
                    "# comments (docs/plugin-yaml.md)",
                    pdl.Span(filename, exc.line, exc.column, exc.line, exc.column + 1).location(),
                )
            ]
        ) from None
    errors = validate(root)
    if errors:
        raise PluginYamlError(
            sorted_diagnostics(
                [_diagnostic(filename, "model.schema", e.message, e.hint, e.node) for e in errors]
            )
        )
    assert isinstance(root, Mapping)
    builder = _Builder(filename)
    model = builder.model(root)
    if builder.errors:
        raise PluginYamlError(sorted_diagnostics(builder.errors))
    return PluginYaml(model, profile_pin(text))
