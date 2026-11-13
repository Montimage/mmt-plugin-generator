"""Typed expressions and constant folding (bugs 5, 6, 7 and 19).

*Foldable* ("simple") means known at generation time: every operand folds.
Literals, ntohs/ntohl, sizeof and offset()/len() of an attribute whose offset
or length folds are foldable; val() never is. Alignment uses a narrower
notion, *constant* (corpus README): literals, ntohs/ntohl and + - * / only.
"""

from __future__ import annotations

import dataclasses

import pytest

from mmt_plugin.pdl import model as pdl
from mmt_plugin.pdl.model import BinaryOperator, Span
from mmt_plugin.semantics import analyse
from mmt_plugin.semantics.analyse import _c_div
from mmt_plugin.semantics.model import Binary, Const, SizeOfType, Swap, ValueRef

from .conftest import FILE, attr, build, ok, parse_model, profile, u8


@pytest.mark.parametrize(
    ("expression", "value"),
    [
        ("7 - 2 - 1", 4),
        ("100 / 10 / 2", 5),
        ("2 + 3 * 4", 14),
        ("(2 + 3) * 4", 20),
        ("7 / 2", 3),
        ("0x10 + 1", 17),
        ("ntohs(0x0300)", 3),
        ("ntohl(0x05000000)", 5),
        ("ntohs(1)", 256),
        ("sizeof(char) + sizeof(struct h)", 4),
        ("offset(x) + len(x)", 7),  # x: R 3 + 3, one byte
        ("1 AND 2", 1),
        ("1 AND 0", 0),
        ("0 OR 0", 0),
        ("0 OR 5", 1),
        ("3 == 3", 1),
        ("3 != 3", 0),
        ("1 < 2 AND 2 < 3", 1),
        ("val(x)", None),
        ("val(x) * 0", None),
        ("4 - val(x)", None),
        ("sizeof(char) + val(x)", None),
    ],
)
def test_folding(expression: str, value: int | None) -> None:
    model = ok(
        "\t\tstruct h {\n\t\t\tuint8_t a, b, c;\n\t\t}\n" + u8("x", "3") + u8("y", expression)
    )
    offset = model.attribute("y").declared_offset
    assert offset is not None
    assert offset.value == value


def test_c_division_truncates_toward_zero() -> None:
    assert [_c_div(7, 2), _c_div(-7, 2), _c_div(7, -2), _c_div(-7, -2)] == [3, -3, -3, 3]


def test_the_typed_tree_keeps_every_reference() -> None:
    model = ok(u8("x", "0") + u8("y", "(val(x) + sizeof(short)) * ntohs(0x0100)"))
    offset = model.attribute("y").offset
    assert isinstance(offset, Binary) and offset.op is BinaryOperator.MUL and offset.value is None
    assert isinstance(offset.left, Binary) and isinstance(offset.left.left, ValueRef)
    assert isinstance(offset.left.right, SizeOfType) and offset.left.right.value == 2
    assert isinstance(offset.right, Swap) and (offset.right.operand, offset.right.value) == (
        256,
        1,
    )


@pytest.mark.parametrize(
    ("offset", "length", "aligned"),
    [
        ("1", "1", True),
        ("1 + 2 * 3", "4 / 2", True),
        ("ntohs(0x0100)", "1", True),
        ("sizeof(char)", "1", False),  # foldable but not constant: alignment stops
        ("1", "sizeof(char)", False),
        ("offset(a)", "1", False),
        ("1", "len(a)", False),
        ("1 == 1", "1", False),
        ("val(a)", "1", False),
    ],
)
def test_constant_attributes_are_aligned(offset: str, length: str, aligned: bool) -> None:
    model = ok(u8("a", "0") + u8("b", offset, length=length) + u8("c", "0"))
    b, c = model.attribute("b"), model.attribute("c")
    assert b.aligned is aligned and c.aligned is aligned
    declared = b.declared_offset
    assert declared is not None
    if aligned:
        # R is 1 after a: b sits at R + its offset, c at R + b's length.
        assert declared.value is not None and b.length_value is not None
        assert b.offset_value == 1 + declared.value
        assert c.offset_value == 1 + b.length_value
    else:
        assert b.offset is declared
        assert c.offset_value == 0


def test_a_constant_offset_after_alignment_stops_is_literal() -> None:
    model = ok(
        u8("a", "0")
        + u8("b", "val(a)")
        + u8("c", "5")
        + "\t\tstruct h {\n\t\t\tuint8_t f;\n\t\t}\n"
    )
    assert [(n, model.attribute(n).offset_value, model.attribute(n).aligned) for n in "abcf"] == [
        ("a", 0, True),
        ("b", None, False),
        ("c", 5, False),
        ("f", 0, False),
    ]
    assert model.struct("h").base_offset == 0 and not model.struct("h").aligned


def test_expressions_are_walked_without_recursion() -> None:
    # The parser caps an expression at 64 operands; a model built by hand
    # (T3.1 may) is not capped, and the walk must not recurse on it.
    text = build(
        u8("x", "0")
        + attr('alias="y" data_type="MMT_U8_DATA" data_len="1" offset="1" scope="packet"')
    )
    model = parse_model(text)
    span = Span(FILE, 1, 1, 1, 2)
    deep: pdl.Expr = pdl.IntLiteral(1, "1", span)
    for _ in range(20_000):
        deep = pdl.BinaryOp(BinaryOperator.ADD, deep, pdl.IntLiteral(1, "1", span), span)
    y = model.attributes.elements[1]
    assert isinstance(y, pdl.Attribute)
    y = pdl.Attribute(y.alias, y.data_type, y.data_len, deep, y.scope, y.span)
    attributes = dataclasses.replace(model.attributes, elements=(model.attributes.elements[0], y))
    analysed, diagnostics = analyse(
        dataclasses.replace(model, attributes=attributes), profile=profile()
    )
    assert diagnostics == []
    assert analysed is not None
    offset = analysed.attribute("y").declared_offset
    assert offset is not None and offset.value == 20_001
    assert isinstance(analysed.attribute("x").offset, Const)
