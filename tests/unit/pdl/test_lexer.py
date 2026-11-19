"""The lexer, and the accuracy of lines and columns.

Lines are 1-based; columns are 1-based and count code points, so a tab is
one column and so is a character outside the BMP. Span ends point just past
the last code point.
"""

from __future__ import annotations

import pytest

from mmt_plugin.pdl import PdlSyntaxError, parse
from mmt_plugin.pdl.lexer import Kind, LexError, tokenize
from mmt_plugin.pdl.model import Attribute, BinaryOp, IntLiteral, Struct

from .conftest import build


def kinds(text: str) -> list[tuple[str, str]]:
    return [(t.kind.name, t.text) for t in tokenize(text, "t.pdl")]


def first_error(text: str) -> tuple[str, int, int, int, int]:
    with pytest.raises(PdlSyntaxError) as caught:
        parse(text, filename="t.pdl")
    loc = caught.value.diagnostics[0].location
    assert loc is not None and loc.line and loc.column and loc.end_line and loc.end_column
    return caught.value.diagnostics[0].code, loc.line, loc.column, loc.end_line, loc.end_column


def test_tokens() -> None:
    assert kinds('a_1 = "x" 12 0x1F (val(b)-4) >= <= == != > < , ; : * / +') == [
        ("IDENT", "a_1"),
        ("PUNCT", "="),
        ("PUNCT", '"'),
        ("IDENT", "x"),
        ("PUNCT", '"'),
        ("NUMBER", "12"),
        ("HEX", "0x1F"),
        ("PUNCT", "("),
        ("IDENT", "val"),
        ("PUNCT", "("),
        ("IDENT", "b"),
        ("PUNCT", ")"),
        ("PUNCT", "-"),
        ("NUMBER", "4"),
        ("PUNCT", ")"),
        ("PUNCT", ">="),
        ("PUNCT", "<="),
        ("PUNCT", "=="),
        ("PUNCT", "!="),
        ("PUNCT", ">"),
        ("PUNCT", "<"),
        ("PUNCT", ","),
        ("PUNCT", ";"),
        ("PUNCT", ":"),
        ("PUNCT", "*"),
        ("PUNCT", "/"),
        ("PUNCT", "+"),
        ("EOF", ""),
    ]


def test_words_are_never_reserved() -> None:
    assert {k for k, _ in kinds("Protocol id len offset MMT_U8_DATA uint8_t AND")} == {
        "IDENT",
        "EOF",
    }


def test_comments_and_whitespace_are_skipped() -> None:
    text = "a // one\r\nb /* two\n three */ c\t/**/d // last"
    assert kinds(text) == [("IDENT", w) for w in "abcd"] + [("EOF", "")]
    tokens = tokenize(text, "t.pdl")
    assert [(t.span.line, t.span.column) for t in tokens] == [
        (1, 1),
        (2, 1),
        (3, 11),
        (3, 17),
        (3, 26),
    ]


def test_a_slash_star_inside_a_line_comment_is_not_a_block() -> None:
    assert kinds("a // /* not a block\nb") == [("IDENT", "a"), ("IDENT", "b"), ("EOF", "")]


def test_lex_errors_carry_a_diagnostic() -> None:
    with pytest.raises(LexError) as caught:
        tokenize("a $", "t.pdl")
    d = caught.value.diagnostic
    assert d.code == "model.syntax.unexpected-character"
    assert d.location is not None and (d.location.line, d.location.column) == (1, 3)
    assert d.hint and "comment" in d.hint


def test_control_characters_are_named_by_code_point() -> None:
    code, line, column, _, _ = first_error("Protocol\x0c{")
    assert (code, line, column) == ("model.syntax.unexpected-character", 1, 9)
    with pytest.raises(PdlSyntaxError, match=r"U\+000C"):
        parse("Protocol\x0c{", filename="t.pdl")


# --- Lines and columns -------------------------------------------------------


def test_a_tab_is_one_column() -> None:
    assert first_error("\t\t\t@")[1:3] == (1, 4)
    assert first_error("Protocol {\n\t\t!")[1:3] == (2, 3)


def test_non_ascii_before_the_error_counts_code_points() -> None:
    # 9 code points before `@`: 17 UTF-16 units would give 11, UTF-8 bytes 14.
    assert first_error("/* é😀 */ @")[1:3] == (1, 10)
    text = 'Protocol { // naïve — ünïcode 😀\n\t/* ✓ */\tProperties { label = "p" 42 } }'
    code, line, column, end_line, end_column = first_error(text)
    assert code == "model.syntax.unexpected-token"
    assert (line, column, end_line, end_column) == (2, 35, 2, 37)


def test_crlf_line_endings() -> None:
    text = build('\t\tattribute { alias="x" data_type="MMT_FOO" }').replace("\n", "\r\n")
    code, line, column, _, end_column = first_error(text)
    assert (code, line, column, end_column) == ("model.syntax.unknown-type", 7, 36, 43)


def test_a_byte_order_mark_is_skipped() -> None:
    model = parse("﻿" + build(), filename="t.pdl")
    assert (model.span.line, model.span.column) == (1, 1)
    assert first_error("﻿Protocol @")[1:3] == (1, 10)


def test_lines_inside_block_comments_are_counted() -> None:
    assert first_error("/*\n\n*/ Protocol {\n@")[1:3] == (4, 1)


def test_the_end_of_input_points_past_the_last_character() -> None:
    assert first_error("Protocol {\n\tdefine A")[:3] == ("model.syntax.unexpected-end", 2, 10)
    assert first_error("")[:3] == ("model.syntax.unexpected-end", 1, 1)


def test_node_spans() -> None:
    text = build(
        "\t\tstruct h { uint8_t a, b:4; }\n"
        '\t\tattribute { alias="len" data_type="MMT_U8_DATA" offset="val(a) + -1" }'
    )
    model = parse(text, filename="t.pdl")
    struct, attribute = model.attributes.elements
    assert isinstance(struct, Struct) and isinstance(attribute, Attribute)
    assert str(struct.span) == "t.pdl:7:3"
    assert (struct.span.end_line, struct.span.end_column) == (7, 31)
    element = struct.elements[0]
    assert (element.span.column, element.span.end_column) == (14, 29)
    b = element.fields[1]
    assert (b.span.column, b.span.end_column) == (25, 28)
    assert (b.name.span.column, b.name.span.end_column) == (25, 26)
    assert (attribute.alias.span.line, attribute.alias.span.column) == (8, 22)
    offset = attribute.offset
    assert isinstance(offset, BinaryOp) and isinstance(offset.right, IntLiteral)
    assert (offset.span.column, offset.span.end_column) == (59, 70)
    assert (offset.right.span.column, offset.right.text) == (68, "-1")
    assert offset.span.location().end_column == 70
    assert model.properties.span.to(model.attributes.span).end_line == 9


@pytest.mark.parametrize("kind", list(Kind))
def test_token_kinds_have_a_description(kind: Kind) -> None:
    assert kind.value
