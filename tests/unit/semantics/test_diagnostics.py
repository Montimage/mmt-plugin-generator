"""One test per semantic diagnostic code: its severity, the text it points
at, its message and its related locations. Then the registry: every code is
registered in ``mmt_plugin.diagnostics.CODES``, in one block after the
``model.syntax.*`` codes, has a default hint and a case here."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from mmt_plugin.diagnostics import CODES, Severity
from mmt_plugin.exitcodes import ExitCode, for_class
from mmt_plugin.semantics import HINTS

from .conftest import attr, build, classify, covered, run, u8, whole

E, W = Severity.ERROR, Severity.WARNING


@dataclass(frozen=True)
class Case:
    text: str
    points_at: str
    message: str
    severity: Severity = E
    #: (message fragment, the text the related location points at or None)
    related: tuple[tuple[str, str | None], ...] = field(default=())


def struct(name: str, *lines: str) -> str:
    body = "".join(f"\t\t\t{line}\n" for line in lines)
    return f"\t\tstruct {name} {{\n{body}\t\t}}\n"


def cond(condition: str, then: str, otherwise: str | None = None) -> str:
    text = f"\t\tif ({condition}) {{\n{then}\t\t}}"
    if otherwise is not None:
        text += f" else {{\n{otherwise}\t\t}}"
    return text + "\n"


BINARY = 'alias="blob" data_type="MMT_BINARY_DATA" data_len="4" offset="0" scope="packet"'
LONG = "a" * 65

CASES: dict[str, Case] = {
    "duplicate-name": Case(
        struct("Hdr", "uint8_t a;") + struct("hdr", "uint8_t b;"),
        "hdr",
        "struct name `hdr` is already used",
        related=(("first defined here", "Hdr"),),
    ),
    "unknown-name": Case(
        build(u8("a", "0"), classify=classify("\t\t\tcase NOPE: break")),
        "NOPE",
        "`NOPE` is no define and no SDK protocol",
    ),
    "unknown-attribute": Case(
        u8("abc", "0") + u8("b", "val(abd)"),
        "abd",
        "val(abd) names no attribute (did you mean `abc`?)",
    ),
    "unknown-struct": Case(
        u8("a", "sizeof(struct nope)"),
        "nope",
        "`struct nope` is not defined",
    ),
    "use-before-definition": Case(
        u8("a", "val(b)") + u8("b", "0"),
        "b",
        "attribute `b` is used before its definition",
        related=(("defined here", "b"),),
    ),
    "conditional-reference": Case(
        u8("k", "0") + cond("val(k) == 1", u8("c", "1")) + u8("d", "val(c)"),
        "c",
        "val(c) is used outside the branch that declares `c`",
        related=(("declared here", "c"), ("inside this if", None)),
    ),
    "not-an-integer": Case(
        attr(BINARY) + u8("b", "val(blob)"),
        "blob",
        "val(blob) reads an integer, but `blob` is MMT_BINARY_DATA",
        related=(("declared here", None),),
    ),
    "missing-length": Case(
        attr('alias="s" data_type="MMT_STRING_DATA" offset="0" scope="packet"'),
        "MMT_STRING_DATA",
        "`s` has an offset but no data_len, and MMT_STRING_DATA has no fixed width",
    ),
    "no-fixed-width": Case(
        struct("h", "MMT_BINARY_DATA b;"),
        "MMT_BINARY_DATA",
        "MMT_BINARY_DATA has no fixed width, so it cannot be a struct field",
    ),
    "invalid-bitfield": Case(
        struct("h", "uint8_t a:9;"),
        "9",
        "`a` is 9 bits wide; a bitfield of a 8-bit unit is 1 to 8 bits",
    ),
    "bitfield-overflow": Case(
        struct("h", "uint8_t a:4, b:5;"),
        "b:5",
        "`b` does not fit in its run's 8-bit unit: 4 bits are used and it needs 5 more",
        related=(("the run starts here", "a:4"),),
    ),
    "division-by-zero": Case(u8("a", "4 / 0"), "4 / 0", "this expression divides by zero"),
    "out-of-range": Case(
        u8("a", "1 - 2"),
        "1 - 2",
        "the offset of `a` folds to -1; it must be from 0 to 2147483647",
    ),
    "duplicate-case": Case(
        build(
            u8("a", "0"),
            defines="\tdefine ONE = 1\n",
            classify=classify("\t\t\tcase 1: break\n\t\t\tcase ONE: break"),
        ),
        "ONE",
        "case 1 is already handled",
        related=(("first handled here", "1"),),
    ),
    "leading-zero": Case(
        build(u8("a", "0"), defines="\tdefine X = 010\n"),
        "010",
        "`010` in a define value is 10 in PDL, but the Java tool copied it into the C as "
        "text, which C reads as octal 8",
    ),
    "alias-too-long": Case(
        u8(LONG, "0"),
        LONG,
        f"attribute name `{LONG}` is 65 bytes long; the SDK's aliases hold at most 64",
    ),
    "id-out-of-range": Case(
        build(u8("a", "0"), properties='label = "p"\n\t\tid = "1000"'),
        "1000",
        "protocol id 1000 is out of range: an id is positive and below 1000",
    ),
    "id-taken": Case(
        build(u8("a", "0"), properties='label = "p"\n\t\tid = "354"'),
        "354",
        "protocol id 354 is already PROTO_TCP's in mmt-dpi 1.10.2",
        related=(("PROTO_TCP = 354 in the SDK profile 1.10.2", None),),
    ),
    "name-taken": Case(
        build(u8("a", "0"), properties='label = "Udp"\n\t\tid = "960"'),
        "Udp",
        "protocol name UDP is already an SDK protocol's: PROTO_UDP = 376",
    ),
    "id-outside-reserved-range": Case(
        build(u8("a", "0"), properties='label = "p"\n\t\tid = "949"'),
        "949",
        "protocol id 949 is outside 950-999, the range reserved for third-party plugins",
        severity=W,
    ),
    "default-scope": Case(
        attr('alias="a" data_type="MMT_U8_DATA" data_len="1" offset="0"'),
        "a",
        "`a` has no scope, so it is packet (SCOPE_PACKET)",
        severity=W,
    ),
    "pointer-field": Case(
        struct("h", "uint16_t* p;"),
        "uint16_t*",
        "a pointer field is 4 bytes on the wire and reads as MMT_DATA_POINTER",
        severity=W,
    ),
    "branch-offset-mismatch": Case(
        u8("k", "0")
        + cond("val(k) == 1", u8("c", "0"), u8("d", "0", length="2"))
        + u8("after", "0"),
        "after",
        "the offset of `after` adds the running offset left by an if/else whose branches end "
        "at different offsets; PDL keeps the else branch's",
        severity=W,
        related=(("its then branch ends at 2, its else branch at 3", None),),
    ),
}


@pytest.mark.parametrize("name", sorted(CASES))
def test_diagnostic(name: str) -> None:
    case = CASES[name]
    text = whole(case.text)
    analysed, diagnostics = run(text)
    assert [d.code for d in diagnostics] == [f"model.{name}"]
    (d,) = diagnostics
    assert d.severity is case.severity
    assert case.message in d.message
    assert covered(text, d.location) == case.points_at
    assert d.hint
    assert len(d.related) == len(case.related)
    for related, (fragment, points_at) in zip(d.related, case.related, strict=True):
        assert fragment in related.message
        if points_at is not None:
            assert covered(text, related.location) == points_at
    # Warnings and SDK conflicts leave the model; any other error withholds it.
    if case.severity is W or name in ("id-taken", "name-taken"):
        assert analysed is not None
    else:
        assert analysed is None


SEMANTIC = [c for c in CODES if c.startswith("model.") and not c.startswith("model.syntax.")]


def test_every_semantic_code_is_registered_hinted_and_tested() -> None:
    assert set(SEMANTIC) == set(HINTS) == {f"model.{n}" for n in CASES}
    for code in SEMANTIC:
        assert for_class("model") is ExitCode.MODEL, code  # exit code 3
        assert CODES[code], code
    # One contiguous block, right after the syntax codes.
    keys = list(CODES)
    last_syntax = max(i for i, c in enumerate(keys) if c.startswith("model.syntax."))
    assert keys[last_syntax + 1 : last_syntax + 1 + len(SEMANTIC)] == SEMANTIC


def test_warnings_are_registered_as_warnings() -> None:
    warnings = {f"model.{n}" for n, c in CASES.items() if c.severity is W}
    assert warnings == {c for c in SEMANTIC if CODES[c].startswith("warning:")}


@pytest.mark.parametrize(
    ("text", "points_at"),
    [
        (struct("h", "char* p:3;"), "p:3"),
        (struct("h", "MMT_DATA_MAC_ADDR m:3;"), "m:3"),
        (struct("h", "uint16_t a:0;"), "0"),
    ],
)
def test_other_invalid_bitfields(text: str, points_at: str) -> None:
    source = whole(text)
    _, diagnostics = run(source)
    assert [d.code for d in diagnostics if d.severity is E] == ["model.invalid-bitfield"]
    assert covered(source, next(d for d in diagnostics if d.severity is E).location) == points_at


@pytest.mark.parametrize(
    ("text", "points_at", "message"),
    [
        (u8("a", "0", length="0"), "0", "the data_len of `a` folds to 0; it must be from 1"),
        (u8("a", "ntohs(0x10000)"), "0x10000", "ntohs(0x10000) swaps a 16-bit value"),
        (u8("a", "ntohl(-1)"), "-1", "ntohl(-1) swaps a 32-bit value"),
        (
            build(u8("a", "0"), classify=classify("\t\t\tcase 1: nextoffset = 0 - 4 break")),
            "0 - 4",
            "nextoffset folds to -4",
        ),
        (
            build(u8("a", "0"), classify=classify("\t\t\tcase 1: nextencaps = 1000 break")),
            "1000",
            "nextencaps names protocol id 1000",
        ),
    ],
)
def test_other_ranges(text: str, points_at: str, message: str) -> None:
    source = whole(text)
    _, diagnostics = run(source)
    (d,) = diagnostics
    assert d.code in ("model.out-of-range", "model.id-out-of-range")
    assert message in d.message
    assert covered(source, d.location) == points_at


def test_duplicate_defines_and_self_references() -> None:
    text = build(u8("a", "val(a)"), defines="\tdefine X = 1\n\tdefine x = 2\n\tdefine Y = Y\n")
    _, diagnostics = run(text)
    messages = [(d.code, covered(text, d.location), d.message) for d in diagnostics]
    assert messages == [
        (
            "model.duplicate-name",
            "x",
            "define name `x` is already used (names are case-insensitive)",
        ),
        ("model.use-before-definition", "Y", "define `Y` refers to itself"),
        ("model.use-before-definition", "a", "attribute `a` refers to itself"),
    ]


def test_struct_fields_and_struct_types_must_be_defined_first() -> None:
    text = struct("o", "struct i x;", "struct o y;") + struct("i", "uint8_t a;")
    source = whole(text)
    _, diagnostics = run(source)
    assert [(d.code, covered(source, d.location)) for d in diagnostics] == [
        ("model.use-before-definition", "i"),
        ("model.use-before-definition", "o"),
    ]
    assert "refers to itself" in diagnostics[1].message


def test_a_later_struct_named_like_the_attribute_is_not_a_self_reference() -> None:
    text = whole(u8("h", "sizeof(struct h)") + struct("h", "uint8_t f;"))
    _, diagnostics = run(text)
    assert [d.code for d in diagnostics] == ["model.use-before-definition"]
    assert diagnostics[0].message == "struct `h` is used before its definition"
