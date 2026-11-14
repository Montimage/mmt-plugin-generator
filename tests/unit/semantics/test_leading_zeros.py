"""Leading-zero decimal literals (#12; review of #47, N2).

``IntLiteral.value`` is base 10 (``010`` is 10), as the Java tool computed
where it folded a literal: ``id``, bit widths and simple expressions. Where
it copied the literal into the C as text, a leading zero meant octal (``010``
is 8) or did not compile (``08``). Each such position gets
``model.leading-zero``; the folded positions do not.
"""

from __future__ import annotations

import pytest

from mmt_plugin.semantics.model import Const

from .conftest import build, classify, covered, ok, run, u8

#: Copied as text by the Java tool: each one is diagnosed.
TEXT_POSITIONS = {
    "define value": build(u8("a", "0"), defines="\tdefine X = 010\n"),
    "case label": build(u8("a", "0"), classify=classify("\t\t\tcase 010: break")),
    "nextencaps value": build(
        u8("a", "0"), classify=classify("\t\t\tcase 1: nextencaps = 0960 break")
    ),
    "non-folded offset": build(u8("a", "0") + u8("b", "val(a) + 010")),
    "non-folded data_len": build(u8("a", "0") + u8("b", "0", length="val(a) * 02")),
    "non-folded nextoffset": build(
        u8("a", "0"), classify=classify("\t\t\tcase 1: nextoffset = val(a) + 010 break")
    ),
    "if condition, even folded": build(
        u8("a", "0") + "\t\tif (010 == 8) {\n" + u8("c", "1") + "\t\t}\n"
    ),
}


def _switch_on(subject: str) -> str:
    text = build(u8("a", "0"), classify=classify("\t\t\tcase 1: break"))
    return text.replace("switch(1)", f"switch({subject})")


TEXT_POSITIONS["switch subject"] = _switch_on("val(a) + 07")

LITERALS = {
    "define value": "010",
    "case label": "010",
    "nextencaps value": "0960",
    "non-folded offset": "010",
    "non-folded data_len": "02",
    "non-folded nextoffset": "010",
    "if condition, even folded": "010",
    "switch subject": "07",
}


@pytest.mark.parametrize("where", sorted(TEXT_POSITIONS))
def test_a_leading_zero_copied_as_text_is_an_error(where: str) -> None:
    text = TEXT_POSITIONS[where]
    analysed, diagnostics = run(text)
    assert analysed is None
    leading = [d for d in diagnostics if d.code == "model.leading-zero"]
    assert len(leading) == 1, [d.code for d in diagnostics]
    assert covered(text, leading[0].location) == LITERALS[where]
    assert leading[0].severity.value == "error"


def test_the_message_says_how_c_reads_it() -> None:
    octal = run(build(u8("a", "0"), defines="\tdefine X = 010\n"))[1][0]
    assert "is 10 in PDL" in octal.message and "which C reads as octal 8" in octal.message
    assert octal.hint == "write 10 (or 0xA) to say which you mean"
    invalid = run(build(u8("a", "0"), defines="\tdefine X = 08\n"))[1][0]
    assert "is 8 in PDL" in invalid.message and "does not compile" in invalid.message
    negative = run(build(u8("a", "0"), defines="\tdefine X = -010\n"))[1][0]
    assert "`-010`" in negative.message and "octal 8" in negative.message


def test_folded_positions_are_base_ten() -> None:
    # The Java tool folded these with Integer.parseInt: base 10, no octal.
    model = ok(
        build(
            "\t\tstruct h {\n\t\t\tuint16_t a:010, b:06;\n\t\t}\n"
            + u8("c", "010")
            + u8("d", "0", length="01"),
            properties='label = "p"\n\t\tid = "0960"',
        )
    )
    assert model.protocol.id == 960
    bitfield = model.attribute("a").bitfield
    assert bitfield is not None and bitfield.bit_width == 10
    c = model.attribute("c").declared_offset
    assert isinstance(c, Const) and c.value == 10 and c.text == "010"
    assert model.attribute("d").length_value == 1


def test_zero_hex_and_plain_literals_are_fine() -> None:
    ok(
        build(
            u8("a", "0") + u8("b", "val(a) + 0x010 + 0 + 10"),
            defines="\tdefine X = 0\n\tdefine Y = 0x08\n",
        )
    )
