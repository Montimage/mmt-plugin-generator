"""One test per PDL construct of the inventory (section 1).

The construct ids are those of ``tests/corpus/index.yaml``; a last test checks
that every one of them has a test here. Each test parses a small model and
checks the typed model holds what the construct means (``G:<line>`` is the
grammar rule it follows).
"""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, TypeVar

import pytest

from mmt_plugin.pdl.model import (
    Attribute,
    BinaryOp,
    BinaryOperator,
    ByteSwap,
    Conditional,
    CType,
    DataType,
    Encoding,
    Expr,
    IntLiteral,
    LengthOf,
    MmtType,
    Model,
    Name,
    NextEncaps,
    NextOffset,
    OffsetOf,
    Scope,
    SizeOf,
    Struct,
    StructType,
    ValueOf,
)

if TYPE_CHECKING:
    from .conftest import Build, Parse

INDEX = Path(__file__).parents[2] / "corpus" / "index.yaml"

#: Construct id -> the test that covers it.
COVERED: dict[str, str] = {}

F = TypeVar("F", bound=Callable[..., None])


def covers(*ids: str) -> Callable[[F], F]:
    """Record that the decorated test covers these construct ids."""

    def mark(test: F) -> F:
        for construct in ids:
            assert construct not in COVERED, construct
            COVERED[construct] = test.__name__
        return test

    return mark


def attr(text: str) -> str:
    """An ``attribute { ... }`` block with the given keys."""
    return f"\t\tattribute {{ {text} }}\n"


def only(m: Model) -> Attribute:
    (element,) = m.attributes.elements
    assert isinstance(element, Attribute)
    return element


def struct_of(m: Model, index: int = 0) -> Struct:
    element = m.attributes.elements[index]
    assert isinstance(element, Struct)
    return element


def offset_expr(ok: Parse, model: Build, expr: str) -> Expr:
    m = ok(model(attr(f'alias="x" data_type="MMT_U8_DATA" data_len="1" offset="{expr}"')))
    offset = only(m).offset
    assert offset is not None
    return offset


# --- Lexical and top level --------------------------------------------------


KEYWORDS = [
    "id",
    "len",
    "offset",
    "val",
    "sizeof",
    "label",
    "session",
    "packet",
    "int",
    "char",
    "AND",
    "OR",
    "Protocol",
    "Properties",
    "Attributes",
    "attribute",
    "struct",
    "classifynext",
    "switch",
    "case",
    "break",
    "default",
    "nextencaps",
    "nextoffset",
    "define",
    "if",
    "else",
    "unsigned",
    "alias",
    "data_type",
    "data_len",
    "scope",
    "true",
    "false",
    "network",
    "host",
    "MMT_U8_DATA",
]


@covers("lexical.keyword_names")
def test_keywords_are_contextual(ok: Parse, model: Build) -> None:
    fields = "".join(f"\t\t\tuint8_t {k};\n" for k in KEYWORDS)
    aliases = "".join(
        attr(f'alias="{k}" data_type="MMT_U8_DATA" data_len="1" offset="val({k})"')
        for k in ("id", "len", "offset", "val", "AND", "OR")
    )
    m = ok(model(f"\t\tstruct s {{\n{fields}\t\t}}\n{aliases}", defines="\tdefine id = len\n"))
    names = [f.name.text for e in struct_of(m).elements for f in e.fields]
    assert names == KEYWORDS
    assert [a.alias.text for a in m.attributes.elements[1:]] == [  # type: ignore[union-attr]
        "id",
        "len",
        "offset",
        "val",
        "AND",
        "OR",
    ]
    assert m.defines[0].name.text == "id"
    assert m.defines[0].value == Name("len", m.defines[0].value.span)


@covers("toplevel.layout")
def test_top_level_layout(ok: Parse) -> None:
    # G:33: Protocol { define* Properties Attributes classifynext? }
    text = 'Protocol { define A = 1 Properties { label = "p" id = "1" } Attributes { } }'
    m = ok(text)
    assert [d.name.text for d in m.defines] == ["A"]
    assert m.properties.label.text == "p"
    assert m.attributes.elements == ()
    assert m.classify_next is None
    assert (m.span.line, m.span.column, m.span.end_column) == (1, 1, len(text) + 1)


@covers("toplevel.comments")
def test_comments_are_whitespace(ok: Parse, model: Build) -> None:
    text = model(
        "\t\t// a line comment\n"
        "\t\t/* a block\n\t\t   comment */ struct s { uint8_t a; /* inline */ }\n"
        + attr('alias="x" /* in a key list */ data_type="MMT_U8_DATA" offset="1 /* + 2 */"'),
    )
    m = ok(text + "// a comment after the model\n/* and a block */")
    assert struct_of(m).elements[0].fields[0].name.text == "a"
    attribute = m.attributes.elements[1]
    assert isinstance(attribute, Attribute) and isinstance(attribute.offset, IntLiteral)
    assert attribute.offset.value == 1


# --- define (G:40-60) ---------------------------------------------------------


@covers("define.decimal", "define.hex", "define.alias")
def test_defines(ok: Parse, model: Build) -> None:
    m = ok(model(defines="\tdefine A = 12\n\tdefine B = 0x3BC\n\tdefine C = A\n\tdefine D = -3\n"))
    values = {d.name.text: d.value for d in m.defines}
    assert isinstance(values["A"], IntLiteral) and values["A"].value == 12
    assert isinstance(values["B"], IntLiteral) and (values["B"].value, values["B"].is_hex) == (
        956,
        True,
    )
    assert isinstance(values["C"], Name) and values["C"].text == "A"
    assert isinstance(values["D"], IntLiteral) and values["D"].value == -3


# --- Properties (G:178-255) ---------------------------------------------------


@covers("properties.label", "properties.id")
def test_label_and_id(ok: Parse, model: Build) -> None:
    m = ok(model(properties='label = "TPKT"\n\t\tid = "636"'))
    assert m.properties.label.text == "TPKT"
    assert (m.properties.id.value, m.properties.id.text) == (636, "636")
    # Integer.parseInt: a sign and leading zeros are accepted, ranges are T1.3's.
    m = ok(model(properties='label = "p" id = "-007"'))
    assert m.properties.id.value == -7


@covers(
    "properties.context",
    "properties.session_context",
    "properties.session",
    "properties.encapsulation",
)
def test_boolean_properties(ok: Parse, model: Build) -> None:
    keys = ("context", "session_context", "session", "encapsulation")
    props = 'label = "p" id = "1" ' + " ".join(
        f'{k} = "{v}"' for k, v in zip(keys, "tftf", strict=True)
    )
    props = props.replace('"t"', '"true"').replace('"f"', '"false"')
    m = ok(model(properties=props))
    p = m.properties
    flags = (p.context, p.session_context, p.session, p.encapsulation)
    assert [f.value if f else None for f in flags] == [True, False, True, False]


@covers("properties.optional_omitted", "properties.encoding.default")
def test_optional_properties_omitted(ok: Parse, model: Build) -> None:
    p = ok(model()).properties
    assert (p.context, p.session_context, p.session, p.encapsulation, p.encoding) == (None,) * 5


@pytest.mark.parametrize(
    ("spelling", "encoding"),
    [
        pytest.param("network", Encoding.NETWORK, id="properties.encoding.network"),
        pytest.param("host", Encoding.HOST, id="properties.encoding.host"),
        pytest.param("little", Encoding.HOST, id="host-alias-little"),
        pytest.param("ASCII", Encoding.ASCII, id="properties.encoding.ascii"),
        pytest.param("UNICODE", Encoding.UNICODE, id="properties.encoding.unicode"),
    ],
)
def test_encodings(ok: Parse, model: Build, spelling: str, encoding: Encoding) -> None:
    value = ok(model(properties=f'label = "p" id = "1" encoding = "{spelling}"')).properties
    assert value.encoding is not None
    assert (value.encoding.value, value.encoding.spelling) == (encoding, spelling)


covers(
    "properties.encoding.network",
    "properties.encoding.host",
    "properties.encoding.ascii",
    "properties.encoding.unicode",
)(test_encodings)


# --- struct (G:431-659) -------------------------------------------------------


@covers("struct.plain", "struct.multi_name")
def test_struct_fields(ok: Parse, model: Build) -> None:
    s = struct_of(ok(model("\t\tstruct h {\n\t\t\tuint8_t a;\n\t\t\tuint16_t b, c;\n\t\t}\n")))
    assert s.name.text == "h"
    assert [[f.name.text for f in e.fields] for e in s.elements] == [["a"], ["b", "c"]]
    assert all(f.bit_width is None for e in s.elements for f in e.fields)


@covers("struct.bitfield", "struct.bitfield.mixed_line", "struct.bitfield.followed")
def test_bitfields(ok: Parse, model: Build) -> None:
    s = struct_of(
        ok(model("\t\tstruct h { uint8_t a:3, b:5; uint16_t w, x:4, y:12; uint8_t z; }"))
    )
    widths = [
        [(f.name.text, f.bit_width and f.bit_width.value) for f in e.fields] for e in s.elements
    ]
    assert widths == [[("a", 3), ("b", 5)], [("w", None), ("x", 4), ("y", 12)], [("z", None)]]


@pytest.mark.parametrize(
    ("spelling", "name", "unsigned", "pointer", "data_type"),
    [
        pytest.param("int", "int", False, False, DataType.MMT_U32_DATA, id="struct.type.int"),
        pytest.param("long", "long", False, False, DataType.MMT_U32_DATA, id="struct.type.long"),
        pytest.param(
            "uint32_t", "uint32_t", False, False, DataType.MMT_U32_DATA, id="struct.type.uint32_t"
        ),
        pytest.param(
            "short", "short", False, False, DataType.MMT_U16_DATA, id="struct.type.short"
        ),
        pytest.param(
            "uint16_t", "uint16_t", False, False, DataType.MMT_U16_DATA, id="struct.type.uint16_t"
        ),
        pytest.param("char", "char", False, False, DataType.MMT_U8_DATA, id="struct.type.char"),
        pytest.param(
            "u_char", "u_char", False, False, DataType.MMT_U8_DATA, id="struct.type.u_char"
        ),
        pytest.param(
            "uint8_t", "uint8_t", False, False, DataType.MMT_U8_DATA, id="struct.type.uint8_t"
        ),
        pytest.param(
            "unsigned short",
            "short",
            True,
            False,
            DataType.MMT_U16_DATA,
            id="struct.type.unsigned",
        ),
        pytest.param(
            "uint8_t*", "uint8_t", False, True, DataType.MMT_DATA_POINTER, id="struct.type.pointer"
        ),
        pytest.param("void*", "void", False, True, DataType.MMT_DATA_POINTER, id="void-pointer"),
        pytest.param(
            "unsigned int*", "int", True, True, DataType.MMT_DATA_POINTER, id="unsigned-pointer"
        ),
    ],
)
def test_c_element_types(
    ok: Parse,
    model: Build,
    spelling: str,
    name: str,
    unsigned: bool,
    pointer: bool,
    data_type: DataType,
) -> None:
    element = struct_of(ok(model(f"\t\tstruct h {{ {spelling} f; }}"))).elements[0]
    assert isinstance(element.type, CType)
    t = element.type
    assert (t.name, t.unsigned, t.pointer, t.data_type) == (name, unsigned, pointer, data_type)
    assert t.span.end_column - t.span.column == len(spelling)


covers(
    "struct.type.int",
    "struct.type.long",
    "struct.type.uint32_t",
    "struct.type.short",
    "struct.type.uint16_t",
    "struct.type.char",
    "struct.type.u_char",
    "struct.type.uint8_t",
    "struct.type.unsigned",
    "struct.type.pointer",
)(test_c_element_types)


@covers("struct.type.mmt", "struct.type.nested")
def test_mmt_and_struct_element_types(ok: Parse, model: Build) -> None:
    m = ok(
        model("\t\tstruct a { uint8_t x; }\n\t\tstruct b { MMT_DATA_MAC_ADDR mac; struct a in; }")
    )
    mac, inner = struct_of(m, 1).elements
    assert mac.type == MmtType(DataType.MMT_DATA_MAC_ADDR, mac.type.span)
    assert isinstance(inner.type, StructType) and inner.type.name.text == "a"
    assert inner.fields[0].name.text == "in"


# --- attribute (G:382-429) ----------------------------------------------------


@covers("attribute.full")
def test_attribute_full(ok: Parse, model: Build) -> None:
    a = only(
        ok(
            model(
                '\t\tattribute {\n\t\t\talias = "len"\n\t\t\tdata_type = "MMT_U16_DATA"\n'
                '\t\t\tdata_len = "2"\n\t\t\toffset = "4"\n\t\t\tscope = "SCOPE_SESSION"\n\t\t}'
            )
        )
    )
    assert a.alias.text == "len"
    assert a.data_type.type is DataType.MMT_U16_DATA
    assert a.data_len == IntLiteral(2, "2", a.data_len.span)  # type: ignore[union-attr]
    assert a.offset == IntLiteral(4, "4", a.offset.span)  # type: ignore[union-attr]
    assert a.scope is not None and a.scope.value is Scope.SESSION


@covers(
    "attribute.no_offset_len", "attribute.no_scope", "attribute.no_data_len", "attribute.no_offset"
)
def test_attribute_optional_keys(ok: Parse, model: Build) -> None:
    m = ok(
        model(
            attr('alias="a" data_type="MMT_BINARY_DATA"')
            + attr('alias="b" data_type="MMT_U8_DATA" data_len="1" offset="0"')
            + attr('alias="c" data_type="MMT_U8_DATA" offset="0" scope="packet"')
            + attr('alias="d" data_type="MMT_U8_DATA" data_len="1" scope="packet"')
        )
    )
    a, b, c, d = m.attributes.elements
    assert isinstance(a, Attribute) and (a.data_len, a.offset, a.scope) == (None, None, None)
    assert isinstance(b, Attribute) and b.scope is None and b.offset is not None
    assert isinstance(c, Attribute) and c.data_len is None and c.offset is not None
    assert isinstance(d, Attribute) and d.offset is None and d.data_len is not None


@pytest.mark.parametrize(
    ("spelling", "scope"),
    [
        pytest.param("SCOPE_PACKET", Scope.PACKET, id="scope.SCOPE_PACKET"),
        pytest.param("packet", Scope.PACKET, id="scope.packet"),
        pytest.param("SCOPE_SESSION", Scope.SESSION, id="scope.SCOPE_SESSION"),
        pytest.param("session", Scope.SESSION, id="scope.session"),
    ],
)
def test_scopes(ok: Parse, model: Build, spelling: str, scope: Scope) -> None:
    a = only(ok(model(attr(f'alias="a" data_type="MMT_U8_DATA" scope="{spelling}"'))))
    assert a.scope is not None and (a.scope.value, a.scope.spelling) == (scope, spelling)


covers("scope.SCOPE_PACKET", "scope.packet", "scope.SCOPE_SESSION", "scope.session")(test_scopes)


@pytest.mark.parametrize("data_type", list(DataType), ids=[f"type.{t.value}" for t in DataType])
def test_data_types(ok: Parse, model: Build, data_type: DataType) -> None:
    a = only(ok(model(attr(f'alias="a" data_type="{data_type.value}"'))))
    assert a.data_type.type is data_type


covers(*(f"type.{t.value}" for t in DataType))(test_data_types)


def test_there_are_26_data_types() -> None:
    assert len(DataType) == 26


# --- if / else (G:314-380) ----------------------------------------------------

A1 = attr('alias="a1" data_type="MMT_U8_DATA" data_len="1" offset="0"')
A2 = attr('alias="a2" data_type="MMT_U8_DATA" data_len="1" offset="1"')


@covers("conditional.if", "conditional.no_match")
def test_if_without_else(ok: Parse, model: Build) -> None:
    (c,) = ok(model(f"\t\tif (val(k) == 1) {{\n{A1}\t\t}}")).attributes.elements
    assert isinstance(c, Conditional)
    assert isinstance(c.condition, BinaryOp) and c.condition.op is BinaryOperator.EQ
    assert [a.alias.text for a in c.then_branch] == ["a1"]  # type: ignore[union-attr]
    assert c.else_branch is None


@covers("conditional.if_else")
def test_if_else(ok: Parse, model: Build) -> None:
    (c,) = ok(
        model(f"\t\tif (1) {{\n{A1}\t\t}}\n\t\telse\n\t\t{{\n{A2}\t\t}}")
    ).attributes.elements
    assert isinstance(c, Conditional) and c.else_branch is not None
    assert [a.alias.text for a in c.else_branch] == ["a2"]  # type: ignore[union-attr]
    (empty,) = ok(model("\t\tif (1) { } else { }")).attributes.elements
    assert isinstance(empty, Conditional) and (empty.then_branch, empty.else_branch) == ((), ())


@covers("conditional.nested_if", "conditional.nested_else", "conditional.struct")
def test_nested_conditionals_and_structs(ok: Parse, model: Build) -> None:
    text = (
        f"\t\tif (1) {{ if (2) {{\n{A1}\t\t}} struct s {{ uint8_t f; }} }}"
        f" else {{ if (3) {{\n{A2}\t\t}} }}"
    )
    (c,) = ok(model(text)).attributes.elements
    assert isinstance(c, Conditional) and c.else_branch is not None
    inner, s = c.then_branch
    assert isinstance(inner, Conditional) and isinstance(s, Struct)
    (nested_else,) = c.else_branch
    assert isinstance(nested_else, Conditional)


# --- Expressions (G:661-758) --------------------------------------------------


@covers("expr.literal.decimal", "expr.literal.hex")
def test_literals(ok: Parse, model: Build) -> None:
    for text, value in (("12", 12), ("0x0A", 10), ("0xff", 255), ("-4", -4), ("007", 7)):
        e = offset_expr(ok, model, text)
        assert e == IntLiteral(value, text, e.span)


@pytest.mark.parametrize(
    ("op", "operator"),
    [
        pytest.param("+", BinaryOperator.ADD, id="expr.add"),
        pytest.param("-", BinaryOperator.SUB, id="expr.sub"),
        pytest.param("*", BinaryOperator.MUL, id="expr.mul"),
        pytest.param("/", BinaryOperator.DIV, id="expr.div"),
        pytest.param("==", BinaryOperator.EQ, id="expr.cmp.eq"),
        pytest.param("!=", BinaryOperator.NE, id="expr.cmp.ne"),
        pytest.param(">", BinaryOperator.GT, id="expr.cmp.gt"),
        pytest.param("<", BinaryOperator.LT, id="expr.cmp.lt"),
        pytest.param(">=", BinaryOperator.GE, id="expr.cmp.ge"),
        pytest.param("<=", BinaryOperator.LE, id="expr.cmp.le"),
        pytest.param(" AND ", BinaryOperator.AND, id="expr.and"),
        pytest.param(" OR ", BinaryOperator.OR, id="expr.or"),
    ],
)
def test_binary_operators(ok: Parse, model: Build, op: str, operator: BinaryOperator) -> None:
    # No spaces around symbols: ``val(x)-4`` is a subtraction (the Java lexer
    # read ``-4`` as one number and dropped it).
    e = offset_expr(ok, model, f"val(x){op}4")
    assert isinstance(e, BinaryOp) and e.op is operator
    assert isinstance(e.left, ValueOf) and e.left.attribute.text == "x"
    assert isinstance(e.right, IntLiteral) and e.right.value == 4


covers(
    "expr.add",
    "expr.sub",
    "expr.mul",
    "expr.div",
    "expr.cmp.eq",
    "expr.cmp.ne",
    "expr.cmp.gt",
    "expr.cmp.lt",
    "expr.cmp.ge",
    "expr.cmp.le",
    "expr.and",
    "expr.or",
)(test_binary_operators)


def shape(e: Expr) -> str:
    """The expression as fully parenthesized text."""
    if isinstance(e, BinaryOp):
        return f"({shape(e.left)} {e.op.value} {shape(e.right)})"
    if isinstance(e, IntLiteral):
        return e.text
    if isinstance(e, ValueOf):
        return f"val({e.attribute.text})"
    raise AssertionError(e)


@covers("expr.parens")
def test_precedence_and_parentheses(ok: Parse, model: Build) -> None:
    cases = {
        "1 + 2 * 3": "(1 + (2 * 3))",
        "(1 + 2) * 3": "((1 + 2) * 3)",
        "8 - 4 - 2": "((8 - 4) - 2)",
        "8 / 4 / 2": "((8 / 4) / 2)",
        "1 OR 2 AND 3": "(1 OR (2 AND 3))",
        "1 == 2 AND 3 < 4 + 1": "((1 == 2) AND (3 < (4 + 1)))",
        "(val(a) + 1) * 2": "((val(a) + 1) * 2)",
        "1 - -2": "(1 - -2)",
        "((7))": "7",
    }
    for text, expected in cases.items():
        assert shape(offset_expr(ok, model, text)) == expected, text


@covers("expr.val", "expr.offset_fn", "expr.len_fn")
def test_attribute_functions(ok: Parse, model: Build) -> None:
    e = offset_expr(ok, model, "val(id) + offset(len) + len(offset)")
    assert isinstance(e, BinaryOp) and isinstance(e.left, BinaryOp)
    assert isinstance(e.left.left, ValueOf) and e.left.left.attribute.text == "id"
    assert isinstance(e.left.right, OffsetOf) and e.left.right.attribute.text == "len"
    assert isinstance(e.right, LengthOf) and e.right.attribute.text == "offset"


@covers("expr.sizeof.type", "expr.sizeof.struct", "expr.sizeof.mmt")
def test_sizeof(ok: Parse, model: Build) -> None:
    char = offset_expr(ok, model, "sizeof(char)")
    assert isinstance(char, SizeOf) and isinstance(char.type, CType) and char.type.name == "char"
    s = offset_expr(ok, model, "sizeof( struct hdr )")
    assert isinstance(s, SizeOf) and isinstance(s.type, StructType) and s.type.name.text == "hdr"
    mmt = offset_expr(ok, model, "sizeof(MMT_U16_DATA)")
    assert isinstance(mmt, SizeOf) and mmt.type == MmtType(DataType.MMT_U16_DATA, mmt.type.span)
    ptr = offset_expr(ok, model, "sizeof(unsigned char*)")
    assert isinstance(ptr, SizeOf) and isinstance(ptr.type, CType) and ptr.type.pointer


@covers("expr.ntohs", "expr.ntohl")
def test_byte_swaps(ok: Parse, model: Build) -> None:
    s = offset_expr(ok, model, "ntohs(0x0300)")
    assert isinstance(s, ByteSwap) and (s.width, s.operand.value) == (16, 0x0300)
    lg = offset_expr(ok, model, "ntohl(83886080)")
    assert isinstance(lg, ByteSwap) and (lg.width, lg.operand.value) == (32, 83886080)


# --- Offset and alignment (G:274-311) -----------------------------------------
# The layout itself is T1.3's; the parser keeps what it needs: elements in
# source order, each declared offset and length as written, and the branches.


@covers("layout.align.plain", "layout.align.stop")
def test_layout_inputs_of_plain_attributes(ok: Parse, model: Build) -> None:
    m = ok(
        model(
            attr('alias="a" data_type="MMT_U8_DATA" data_len="1" offset="0"')
            + attr('alias="b" data_type="MMT_U8_DATA" data_len="1" offset="val(a)"')
            + attr('alias="c" data_type="MMT_U8_DATA" data_len="1" offset="3"')
        )
    )
    attrs = [e for e in m.attributes.elements if isinstance(e, Attribute)]
    assert [a.alias.text for a in attrs] == ["a", "b", "c"]
    assert [type(a.offset).__name__ for a in attrs] == ["IntLiteral", "ValueOf", "IntLiteral"]


@covers("layout.align.struct")
def test_layout_inputs_of_structs(ok: Parse, model: Build) -> None:
    m = ok(model(f"{A1}\t\tstruct s {{ uint8_t x; uint16_t y; }}\n{A2}"))
    assert [type(e).__name__ for e in m.attributes.elements] == [
        "Attribute",
        "Struct",
        "Attribute",
    ]


@covers("layout.align.conditional_else", "layout.align.conditional_no_else")
def test_layout_inputs_of_conditionals(ok: Parse, model: Build) -> None:
    m = ok(
        model(f"\t\tif (1) {{\n{A1}\t\t}} else {{\n{A2}\t\t}}\n\t\tif (1) {{\n{A1}\t\t}}\n{A2}")
    )
    first, second, last = m.attributes.elements
    assert isinstance(first, Conditional) and first.else_branch is not None
    assert isinstance(second, Conditional) and second.else_branch is None
    assert isinstance(last, Attribute)


# --- classifynext (G:62-176, 760-788) ------------------------------------------

SWITCH = """\tclassifynext {
\t\tswitch(val(type)) {
\t\t\tcase 1:
\t\t\t\tnextencaps = 955
\t\t\t\tnextoffset = 4
\t\t\t\tbreak
\t\t\tcase 0x02: nextencaps = 0x3BC break
\t\t\tcase NEXT:
\t\t\t\tnextencaps = NEXT
\t\t\tcase -1:
\t\t\t\tnextoffset = val(hlen) * 4
\t\t\tdefault:
\t\t\t\tnextencaps = 959
\t\t\t\tbreak
\t\t}
\t}
"""


@covers(
    "classifynext.switch",
    "classifynext.case.decimal",
    "classifynext.case.hex",
    "classifynext.case.define",
    "classifynext.default",
    "classifynext.nextencaps.number",
    "classifynext.nextencaps.define",
    "classifynext.nextoffset",
    "classifynext.fallthrough",
)
def test_classifynext(ok: Parse, model: Build) -> None:
    m = ok(model(defines="\tdefine NEXT = 957\n", classify=SWITCH))
    assert m.classify_next is not None
    switch = m.classify_next.switch
    assert isinstance(switch.subject, ValueOf) and switch.subject.attribute.text == "type"
    labels = [c.label for c in switch.cases]
    assert [
        (type(x).__name__, getattr(x, "value", None) or getattr(x, "text", None)) for x in labels
    ] == [
        ("IntLiteral", 1),
        ("IntLiteral", 2),
        ("Name", "NEXT"),
        ("IntLiteral", -1),
    ]
    assert [c.has_break for c in switch.cases] == [True, True, False, False]
    first = switch.cases[0].statements
    assert isinstance(first[0], NextEncaps) and first[0].value == IntLiteral(
        955, "955", first[0].value.span
    )
    assert isinstance(first[1], NextOffset) and isinstance(first[1].value, IntLiteral)
    third = switch.cases[2].statements[0]
    assert isinstance(third, NextEncaps) and isinstance(third.value, Name)
    fourth = switch.cases[3].statements[0]
    assert isinstance(fourth, NextOffset) and isinstance(fourth.value, BinaryOp)
    assert switch.default is not None and switch.default.has_break
    assert isinstance(switch.default.statements[0], NextEncaps)


@covers("classifynext.no_match")
def test_switch_without_default_and_empty_branches(ok: Parse, model: Build) -> None:
    # A newline before the switch's `}` without a default was a Java syntax
    # error (G:86-87, 161); newlines are whitespace here.
    m = ok(
        model(
            classify="\tclassifynext {\n\t\tswitch(1) {\n"
            "\t\t\tcase 1:\n\t\t\tcase 2: break\n\t\t}\n\t}\n"
        )
    )
    assert m.classify_next is not None
    switch = m.classify_next.switch
    assert switch.default is None
    assert [(c.statements, c.has_break) for c in switch.cases] == [((), False), ((), True)]
    empty = ok(model(classify="classifynext { switch(1) { } }"))
    assert empty.classify_next is not None and empty.classify_next.switch.cases == ()


# --- Coverage of the inventory ------------------------------------------------


def _index_construct_ids() -> list[str]:
    text = INDEX.read_text(encoding="utf-8")
    section = text.split("\nconstructs:", 1)[1].split("\nmodels:", 1)[0]
    return re.findall(r'^  - id: "([^"]+)"', section, flags=re.MULTILINE)


def test_every_inventory_construct_has_a_test() -> None:
    ids = _index_construct_ids()
    assert len(ids) > 100
    missing = [c for c in ids if c not in COVERED]
    assert missing == []
    extra = sorted(set(COVERED) - set(ids))
    assert extra == ["toplevel.comments", "toplevel.layout"]
