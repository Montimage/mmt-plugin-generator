"""One test per syntax error, and per case where the Java tool recovered.

Each case is a model text, the code we report, the text the diagnostic points
at and a fragment of its message. ``JAVA`` cases are the inventory's syntax
recovery cases (sections 3 and 5) and the ones the legacy jar showed when
probed; their comment says what the Java tool did.
"""

from __future__ import annotations

import builtins
import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import pytest

from mmt_plugin.diagnostics import CODES
from mmt_plugin.exitcodes import ExitCode, for_class
from mmt_plugin.pdl import STDIN, PdlSyntaxError, parse

from .conftest import FILE, build, errors_of, parse_ok

if TYPE_CHECKING:
    from .conftest import Errors

ATTR = 'alias="x" data_type="MMT_U8_DATA" data_len="1"'


def attr(text: str) -> str:
    return f"\t\tattribute {{ {text} }}\n"


def classify(body: str) -> str:
    return f"\tclassifynext {{\n\t\tswitch(1) {{\n\t\t\t{body}\n\t\t}}\n\t}}\n"


@dataclass(frozen=True)
class Case:
    """A text that does not parse, and the first diagnostic it must give."""

    text: str
    code: str
    at: str
    message: str
    nth: int = 0

    def position(self) -> tuple[int, int]:
        """The 1-based line and code-point column of the ``nth`` ``at``."""
        index = -1
        for _ in range(self.nth + 1):
            index = self.text.index(self.at, index + 1)
        line = self.text.count("\n", 0, index) + 1
        column = index - (self.text.rfind("\n", 0, index) + 1) + 1
        return line, column


CASES = {
    # --- Lexical -------------------------------------------------------------
    # JAVA: the lexer reported the character, skipped it and went on.
    "character": Case(build(attr(ATTR + ' offset="1 @ 2"')), "unexpected-character", "@", "`@`"),
    "character-underscore": Case(
        build("\t\tstruct h { uint8_t _x; }"), "unexpected-character", "_x", "`_`"
    ),
    "character-single-quote": Case(
        build(attr("alias='x' data_type=\"MMT_U8_DATA\"")), "unexpected-character", "'", "`'`"
    ),
    "character-non-ascii": Case(
        build("\t\tstruct h { uint8_t café; }"), "unexpected-character", "é", "U+00E9"
    ),
    # JAVA: a lone carriage return was "mismatched character" (G:876).
    "character-lone-cr": Case(
        'Protocol {\r\tProperties { label = "p" id = "1" } Attributes { } }',
        "unexpected-character",
        "\r",
        "carriage return",
    ),
    # JAVA: `12abc` lexed as 12 then abc; `abc` was dropped ("extraneous input").
    "number-into-word": Case(
        build(attr(ATTR + ' offset="12abc"')), "invalid-number", "12abc", "`12abc`"
    ),
    # JAVA: `0x` lexed as a hex number and crashed parseInt: no output at all.
    "number-hex-no-digit": Case(
        build(attr(ATTR + ' offset="0x"')), "invalid-number", "0x", "`0x`"
    ),
    "number-hex-upper-x": Case(
        build(attr(ATTR + ' offset="0X10"')), "invalid-number", "0X10", "`0X10`"
    ),
    "comment-unclosed": Case(
        build("\t\t/* not closed\n"), "unterminated-comment", "/*", "not closed"
    ),
    # JAVA: there is no comment syntax: `//` was two division tokens.
    # (Comments are accepted: test_constructs.test_comments_are_whitespace.)
    # --- Quoted values -----------------------------------------------------
    # JAVA: a newline inside quotes was "extraneous input" and was dropped.
    "quote-across-lines": Case(
        build(attr('alias="x\n" data_type="MMT_U8_DATA"')), "unterminated-string", '"x', "alias"
    ),
    "quote-missing-at-end-of-line": Case(
        build('\t\tattribute {\n\t\t\talias="x\n\t\t\tdata_type="MMT_U8_DATA"\n\t\t}'),
        "unterminated-string",
        '"x',
        "not closed on its line",
    ),
    # JAVA: "missing '\"' at 'data_type'" and an inserted quote.
    "quote-missing-before-key": Case(
        build(attr('alias="x data_type="MMT_U8_DATA"')),
        "unexpected-token",
        "data_type",
        'expected `"` after the value of `alias`',
    ),
    # An error inside a value whose closing quote is missing stops the parse.
    "quote-error-then-newline": Case(
        build(attr(ATTR + ' offset="BAD\n"')), "invalid-expression", "BAD", "`BAD`"
    ),
    "quote-error-at-end-of-input": Case(
        'Protocol { Properties { label = "p" id = "1" } Attributes { attribute { alias="x" '
        'data_type="MMT_U8_DATA" offset="BAD',
        "invalid-expression",
        "BAD",
        "`BAD`",
    ),
    "quote-spills-into-next-line": Case(
        build(
            '\t\tattribute {\n\t\t\talias="x" data_type="MMT_U8_DATA" offset="1 +\n'
            '\t\t\tscope="packet"\n\t\t}'
        ),
        "unterminated-string",
        '"1',
        "`offset`",
    ),
    "quote-missing-opening": Case(
        build(attr('alias=x data_type="MMT_U8_DATA"')), "unexpected-token", "x ", '`"`'
    ),
    "quote-empty": Case(build(attr(ATTR + ' offset=""')), "unexpected-token", '" }', "expression"),
    # --- Structure -------------------------------------------------------------
    "end-empty": Case("", "unexpected-end", "", "`Protocol`"),
    # JAVA: "mismatched input '<EOF>'"; it still wrote both files.
    "end-truncated": Case(
        'Protocol {\n\tProperties { label = "p" id = "1" }\n\tAttributes {\n',
        "unexpected-end",
        "",
        "end of the input",
    ),
    # JAVA: anything after the closing brace was ignored silently (no EOF anchor).
    "trailing-word": Case(build() + "trailing garbage\n", "trailing-input", "trailing", "after"),
    "trailing-brace": Case(build() + "}\n", "trailing-input", "}\n", "`}`", nth=3),
    "protocol-lower-case": Case(
        'protocol { Properties { label = "p" id = "1" } Attributes { } }',
        "unexpected-token",
        "protocol",
        "`Protocol`",
    ),
    "protocol-no-brace": Case(
        'Protocol Properties { label = "p" id = "1" } Attributes { } }',
        "unexpected-token",
        "Properties",
        "`{`",
    ),
    "define-after-properties": Case(
        build(defines="").replace("\tAttributes", "\tdefine A = 1\n\tAttributes"),
        "out-of-order",
        "define",
        "before `Properties`",
    ),
    "define-after-attributes": Case(
        build().replace("\t}\n}", "\t}\n\tdefine A = 1\n}"),
        "out-of-order",
        "define",
        "before `Properties`",
    ),
    "define-no-equals": Case(build(defines="\tdefine A 1\n"), "unexpected-token", "1", "`=`"),
    "define-bad-value": Case(
        build(defines='\tdefine A = "1"\n'), "unexpected-token", '"1"', "a number or a name"
    ),
    "attributes-before-properties": Case(
        'Protocol { Attributes { } Properties { label = "p" id = "1" } }',
        "out-of-order",
        "Attributes",
        "after `Properties`",
    ),
    "properties-twice": Case(
        'Protocol { Properties { label = "p" id = "1" } Properties { } Attributes { } }',
        "out-of-order",
        "Properties",
        "second `Properties`",
        nth=1,
    ),
    "attributes-twice": Case(
        'Protocol { Properties { label = "p" id = "1" } Attributes { } Attributes { } }',
        "out-of-order",
        "Attributes",
        "second `Attributes`",
        nth=1,
    ),
    "classifynext-twice": Case(
        build(classify=classify("default: break") * 2),
        "unexpected-token",
        "classifynext",
        "the `}` that closes `Protocol`",
        nth=1,
    ),
    # --- Properties keys (G:179) -----------------------------------------------
    # JAVA: keys out of order were "mismatched input"; no files were written.
    "properties-order": Case(
        build(properties='id = "1" label = "p"'), "out-of-order", "label", "before `id`"
    ),
    "properties-duplicate": Case(
        build(properties='label = "p" id = "1" id = "2"'), "duplicate-key", "id", "twice", nth=1
    ),
    "properties-unknown": Case(
        build(properties='lable = "p" id = "1"'), "unknown-key", "lable", "not a `Properties` key"
    ),
    "properties-missing-label": Case(
        build(properties='id = "1"'), "missing-key", "Properties", "no `label`"
    ),
    "properties-missing-id": Case(
        build(properties='label = "p"'), "missing-key", "Properties", "no `id`"
    ),
    "properties-unclosed": Case(
        build(properties='label = "p" id = "1"').replace("\n\t}\n\tAttributes", "\n\tAttributes"),
        "unexpected-token",
        "Attributes",
        "the `}` that closes `Properties`",
    ),
    "properties-no-equals": Case(
        build(properties='label "p" id = "1"'), "unexpected-token", '"p"', "`=`"
    ),
    "properties-not-a-key": Case(
        build(properties='label = "p" id = "1" "x"'), "unexpected-token", '"x"', "key"
    ),
    "label-not-a-word": Case(
        build(properties='label = "1" id = "1"'), "unexpected-token", '1"', "protocol name"
    ),
    "id-hex": Case(
        build(properties='label = "p" id = "0x10"'), "invalid-value", "0x10", "decimal"
    ),
    "id-word": Case(build(properties='label = "p" id = "ten"'), "unexpected-token", "ten", "id"),
    # JAVA: "no viable alternative at input 'yes'", then the default (false).
    "flag-value": Case(
        build(properties='label = "p" id = "1" context = "yes"'),
        "invalid-value",
        "yes",
        "`true` or `false`",
    ),
    "flag-not-a-word": Case(
        build(properties='label = "p" id = "1" session = "1"'),
        "unexpected-token",
        '1"',
        "`true`",
        nth=1,
    ),
    "encoding-value": Case(
        build(properties='label = "p" id = "1" encoding = "ascii"'),
        "invalid-value",
        "ascii",
        "not an encoding",
    ),
    "encoding-not-a-word": Case(
        build(properties='label = "p" id = "1" encoding = "1"'),
        "unexpected-token",
        '1"',
        "encoding",
        nth=1,
    ),
    # --- attribute keys (G:383) ------------------------------------------------
    # JAVA: "mismatched input 'data_type' expecting 'alias'", then `null` in the C.
    "attribute-order": Case(
        build(attr('data_type="MMT_U8_DATA" alias="x"')), "out-of-order", "alias", "before"
    ),
    "attribute-duplicate": Case(
        build(attr(ATTR + ' data_len="2"')), "duplicate-key", "data_len", "twice", nth=1
    ),
    "attribute-unknown": Case(
        build(attr(ATTR + ' size="2"')), "unknown-key", "size", "not a `attribute` key"
    ),
    "attribute-missing-alias": Case(
        build(attr('data_type="MMT_U8_DATA"')), "missing-key", "attribute", "no `alias`"
    ),
    "attribute-missing-type": Case(
        build(attr('alias="x"')), "missing-key", "attribute", "no `data_type`"
    ),
    "attribute-no-brace": Case(build("\t\tattribute alias"), "unexpected-token", "alias", "`{`"),
    "alias-not-a-word": Case(
        build(attr('alias="1" data_type="MMT_U8_DATA"')),
        "unexpected-token",
        '1"',
        "attribute name",
    ),
    "data-type-unknown": Case(
        build(attr('alias="x" data_type="MMT_FOO"')), "unknown-type", "MMT_FOO", "not an MMT_*"
    ),
    "data-type-not-a-word": Case(
        build(attr('alias="x" data_type="1"')), "unexpected-token", '1"', "data type"
    ),
    "scope-value": Case(
        build(attr(ATTR + ' scope="global"')), "invalid-value", "global", "not a scope"
    ),
    "scope-not-a-word": Case(
        build(attr(ATTR + ' scope="1"')), "unexpected-token", '1"', "a scope", nth=1
    ),
    # --- Elements ------------------------------------------------------------
    "element-unknown": Case(build("\t\tfield { }"), "unexpected-token", "field", "`attribute`"),
    "element-else-alone": Case(build("\t\telse { }"), "unexpected-token", "else", "without"),
    # JAVA: "missing '{' at 'if'", then the end of input was missing a brace.
    "element-else-if": Case(
        build("\t\tif (1) { } else if (2) { }"), "unexpected-token", "if", "`else if`", nth=1
    ),
    "if-no-paren": Case(build("\t\tif 1 { }"), "unexpected-token", "1", "`(`"),
    "if-unclosed-paren": Case(build("\t\tif (1 { }"), "unexpected-token", "{ }", "`)`"),
    # --- struct --------------------------------------------------------------
    "struct-no-name": Case(build("\t\tstruct { }"), "unexpected-token", "{ }", "struct name"),
    "struct-quoted-name": Case(
        build('\t\tstruct "h" { }'), "unexpected-token", '"h"', "struct name"
    ),
    "struct-no-semicolon": Case(
        build("\t\tstruct h { uint8_t a uint8_t b; }"), "unexpected-token", "uint8_t b", "`;`"
    ),
    "struct-no-field-name": Case(
        build("\t\tstruct h { uint8_t ; }"), "unexpected-token", ";", "field name"
    ),
    "struct-hex-width": Case(
        build("\t\tstruct h { uint8_t a:0x4; }"), "invalid-value", "0x4", "decimal"
    ),
    "struct-unknown-type": Case(
        build("\t\tstruct h { mac_addr_t m; }"), "unknown-type", "mac_addr_t", "not a PDL type"
    ),
    "struct-void": Case(build("\t\tstruct h { void v; }"), "unknown-type", "void", "pointer"),
    "struct-unsigned-mmt": Case(
        build("\t\tstruct h { unsigned MMT_U8_DATA v; }"),
        "unknown-type",
        "MMT_U8_DATA",
        "`unsigned`",
    ),
    "struct-element-not-a-word": Case(
        build("\t\tstruct h { 1 }"), "unexpected-token", "1 }", "field type"
    ),
    # JAVA: `uint8_t *p` was "no viable alternative at input '*'": no output.
    "struct-pointer-space": Case(
        build("\t\tstruct h { uint8_t *p; }"), "unexpected-token", "*", "no space"
    ),
    "struct-of-nothing": Case(
        build("\t\tstruct h { struct ; }"), "unexpected-token", ";", "struct name"
    ),
    # --- Expressions ----------------------------------------------------------
    # JAVA (mongodb): "no viable alternative at input 'POSITION_NOT_KNOWN'", then `null`.
    "expr-bare-name": Case(
        build(attr(ATTR + ' offset="POSITION_NOT_KNOWN"')),
        "invalid-expression",
        "POSITION_NOT_KNOWN",
        "not an expression",
    ),
    # JAVA (ethernet): "no viable alternative at input 'mac_addr_t'", then `sizeof(null)`.
    "expr-sizeof-unknown": Case(
        build(attr(ATTR.replace('"1"', '"sizeof (mac_addr_t)"') + ' offset="0"')),
        "unknown-type",
        "mac_addr_t",
        "not a PDL type",
    ),
    "expr-unknown-function": Case(
        build(attr(ATTR + ' offset="vals(x)"')), "invalid-expression", "vals", "not a PDL function"
    ),
    "expr-function-no-paren": Case(
        build(attr(ATTR + ' offset="val x"')), "unexpected-token", 'x" }', "`(` after `val`"
    ),
    "expr-val-number": Case(
        build(attr(ATTR + ' offset="val(1)"')), "unexpected-token", "1)", "attribute name"
    ),
    # JAVA: "mismatched input '==' expecting '\"'"; the rest was dropped.
    "expr-chained-comparison": Case(
        build(attr(ATTR + ' offset="1 == 2 == 3"')),
        "invalid-expression",
        "==",
        "chained",
        nth=1,
    ),
    # JAVA: "no viable alternative at input '-'".
    "expr-negate-call": Case(
        build(attr(ATTR + ' offset="-val(x)"')), "invalid-expression", "-", "only a number"
    ),
    "expr-ntohs-call": Case(
        build(attr(ATTR + ' offset="ntohs(val(x))"')), "invalid-expression", "val(x))", "number"
    ),
    "expr-unclosed-paren": Case(
        build(attr(ATTR + ' offset="(1 + 2"')), "unexpected-token", '" }', "`)`"
    ),
    "expr-missing-operand": Case(
        build(attr(ATTR + ' offset="1 +"')), "unexpected-token", '" }', "expression"
    ),
    "expr-sizeof-unclosed": Case(
        build(attr(ATTR + ' offset="sizeof(char"')), "unexpected-token", '" }', "`)`"
    ),
    "expr-operator-word": Case(
        build(attr(ATTR + ' offset="AND"')), "invalid-expression", "AND", "not an expression"
    ),
    # --- classifynext --------------------------------------------------------
    "classify-no-switch": Case(
        build(classify="\tclassifynext { }\n"), "unexpected-token", "}\n}", "`switch`"
    ),
    "classify-two-switches": Case(
        build(classify="\tclassifynext { switch(1) { } switch(2) { } }\n"),
        "unexpected-token",
        "switch(2)",
        "`}`",
    ),
    "switch-no-paren": Case(
        build(classify="\tclassifynext { switch 1 { } }\n"), "unexpected-token", "1 {", "`(`"
    ),
    # JAVA: "mismatched input 'case' expecting '}'".
    "switch-case-after-default": Case(
        build(classify=classify("default: break case 1: break")),
        "out-of-order",
        "case",
        "after `default`",
    ),
    "switch-two-defaults": Case(
        build(classify=classify("default: break default: break")),
        "duplicate-key",
        "default",
        "second `default`",
        nth=1,
    ),
    "switch-statement-after-break": Case(
        build(classify=classify("case 1: break nextencaps = 3")),
        "unexpected-token",
        "nextencaps",
        "`case`",
    ),
    "switch-branch-unknown": Case(
        build(classify=classify("when 1: break")), "unexpected-token", "when", "`case`"
    ),
    "case-no-colon": Case(
        build(classify=classify("case 1 break")), "unexpected-token", "break", "`:`"
    ),
    "case-quoted-label": Case(
        build(classify=classify('case "1": break')), "unexpected-token", '"1"', "case label"
    ),
    "nextencaps-quoted": Case(
        build(classify=classify('case 1: nextencaps = "3"')),
        "unexpected-token",
        '"3"',
        "protocol id",
    ),
    "nextoffset-no-equals": Case(
        build(classify=classify("case 1: nextoffset 3")), "unexpected-token", "3\n", "`=`"
    ),
}


@pytest.mark.parametrize("case", CASES.values(), ids=CASES.keys())
def test_syntax_error(case: Case) -> None:
    first = errors_of(case.text)[0]
    assert first.code == f"model.syntax.{case.code}"
    assert case.message in first.message
    assert first.location is not None
    if case.at:
        assert (first.location.line, first.location.column) == case.position()


def test_every_syntax_code_is_registered_tested_and_a_model_error() -> None:
    syntax_codes = {code for code in CODES if code.startswith("model.syntax.")}
    assert {f"model.syntax.{case.code}" for case in CASES.values()} == syntax_codes
    for code in syntax_codes:
        assert for_class(code.split(".", 1)[0]) is ExitCode.MODEL  # exit code 3


def test_errors_inside_quoted_values_are_all_reported() -> None:
    # As the Java tool did for mongodb: each bad value is reported, and parsing
    # goes on after its closing quote.
    text = build(
        attr('alias="a" data_type="MMT_U8_DATA" data_len="1" offset="BAD_ONE"')
        + attr('alias="b" data_type="MMT_FOO"')
        + attr('alias="c" data_type="MMT_U8_DATA" data_len="sizeof(mac)" offset="val(1)"')
    )
    codes = [(d.code, d.location and d.location.line) for d in errors_of(text)]
    assert codes == [
        ("model.syntax.invalid-expression", 7),
        ("model.syntax.unknown-type", 8),
        ("model.syntax.unknown-type", 9),
        ("model.syntax.unexpected-token", 9),
    ]


def test_an_error_outside_a_quoted_value_stops_the_parse() -> None:
    text = build(attr('alias="a" data_type="MMT_FOO"') + "\t\tfield { }\n" + attr("bad"))
    assert [d.code for d in errors_of(text)] == [
        "model.syntax.unknown-type",
        "model.syntax.unexpected-token",
    ]


def test_a_missing_closing_quote_is_not_recovered() -> None:
    text = build(attr('alias="x data_type="MMT_FOO" offset="1"'))
    assert [d.code for d in errors_of(text)] == ["model.syntax.unexpected-token"]


def test_diagnostics_carry_related_locations() -> None:
    (d,) = errors_of(build(properties='label = "p" id = "1" label = "q"'))
    assert [(r.message, r.location and r.location.line) for r in d.related] == [
        ("first given here", 3)
    ]
    (d,) = errors_of(build(properties='id = "1" label = "p"'))
    assert d.related[0].message == "`id` is here"


def test_hints_suggest_close_spellings(errors: Errors) -> None:
    (d,) = errors(build(properties='lable = "p" id = "1"'))
    assert d.hint is not None and d.hint.startswith("did you mean `label`?")
    (d,) = errors(build(properties='label = "p" id = "1" encoding = "ascii"'))
    assert d.hint is not None and d.hint.startswith("did you mean `ASCII`?")
    (d,) = errors(build(attr('alias="x" data_type="MMT_U8_DTA"')))
    assert d.hint is not None and d.hint.startswith("did you mean `MMT_U8_DATA`?")
    (d,) = errors(build(properties="Label").replace("Protocol", "protocol"))
    assert d.hint is not None and "case-sensitive" in d.hint


def test_the_error_names_the_file_and_counts_the_rest() -> None:
    with pytest.raises(PdlSyntaxError) as caught:
        parse(build(attr(ATTR + ' offset="A"') + attr(ATTR + ' offset="B"')), filename="m.pdl")
    assert str(caught.value) == "m.pdl:7:70: `A` is not an expression (and 1 more)"
    assert [d.location.file for d in caught.value.diagnostics if d.location] == ["m.pdl"] * 2


def test_stdin_is_named_stdin() -> None:
    with pytest.raises(PdlSyntaxError) as caught:
        parse("Protocol {", filename=STDIN)
    (d,) = caught.value.diagnostics
    assert STDIN == "<stdin>"
    assert d.location is not None and str(d.location) == "<stdin>:1:11"
    model = parse(build(), filename=STDIN)
    assert model.span.file == "<stdin>"
    assert model.properties.label.span.location().file == "<stdin>"


def test_parsing_opens_and_writes_nothing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: os.PathLike[str]
) -> None:
    def refuse(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError(f"the parser opened a file: {args!r}")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(builtins, "open", refuse)
    monkeypatch.setattr(os, "open", refuse)
    parse_ok(build(attr(ATTR + ' offset="1"')))
    with pytest.raises(PdlSyntaxError):
        parse(build("bad"), filename=FILE)
    assert os.listdir(tmp_path) == []
