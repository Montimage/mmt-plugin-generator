"""One regression test per inventory bug that T1.3 fixes (#12).

Bug numbers are those of docs/legacy/java-generator-inventory.md, section 5.
Where the fix reports a diagnostic, the test asserts its code.
"""

from __future__ import annotations

from mmt_plugin.diagnostics import Severity
from mmt_plugin.pdl.model import DataType, Scope
from mmt_plugin.semantics.model import Binary, Const, LengthRef, OffsetRef, ValueRef

from .conftest import attr, build, codes, covered, errors, ok, run, u8


def struct(name: str, *lines: str) -> str:
    body = "".join(f"\t\t\t{line}\n" for line in lines)
    return f"\t\tstruct {name} {{\n{body}\t\t}}\n"


def test_bug_2_fields_after_a_bitfield_line_are_not_double_counted() -> None:
    # Java kept previous_chuncked across lines: c came out at 4, not 2.
    model = ok(struct("h", "uint16_t a:4, b:12;", "uint16_t c;", "uint8_t d;"))
    assert [(a.name, a.offset_value) for a in model.attributes] == [
        ("a", 0),
        ("b", 0),
        ("c", 2),
        ("d", 4),
    ]
    assert model.struct("h").size == 5


def test_bug_3_the_running_offset_counts_a_bitfield_unit_once() -> None:
    # Java added each member's full type width to R: next came out at 2.
    model = ok(struct("h", "uint8_t hi:4, lo:4;") + u8("next", "0"))
    assert model.attribute("next").offset_value == 1
    assert model.attribute("next").aligned


def test_bug_4_struct_layout_is_packed_and_records_the_c_padding() -> None:
    # Fields are packed on the wire (no C padding); the C layout a compiler
    # would give the emitted struct is recorded, so a generator knows it must
    # pack it.
    model = ok(
        struct("h", "uint8_t a;", "uint32_t b;", "uint16_t c;") + u8("n", "sizeof(struct h)")
    )
    h = model.struct("h")
    assert [(f.name, f.offset, f.c_type, f.c_offset) for f in h.fields] == [
        ("a", 0, "uint8_t", 0),
        ("b", 1, "uint32_t", 4),
        ("c", 5, "uint16_t", 8),
    ]
    assert (h.size, h.c_size, h.c_align, h.c_padding) == (7, 12, 4, 5)
    assert h.needs_packing
    assert model.attribute("n").offset_value == 7  # sizeof is the packed size
    unpadded = ok(struct("g", "uint32_t a;", "uint16_t b, c;")).struct("g")
    assert (unpadded.size, unpadded.c_size, unpadded.needs_packing) == (8, 8, False)


def test_bug_5_simplicity_is_decided_by_every_operand() -> None:
    # Java folded val(x) - 4 to -4, because its last operand is a literal.
    model = ok(
        u8("x", "0") + u8("y", "val(x) - 4") + u8("z", "4 - val(x)") + u8("w", "(1 + 2) * 3")
    )
    y = model.attribute("y").offset
    assert isinstance(y, Binary) and y.value is None
    assert isinstance(y.left, ValueRef) and y.left.attribute == "x"
    assert model.attribute("z").offset_value is None
    w = model.attribute("w").declared_offset
    assert isinstance(w, Binary) and w.value == 9


def test_bug_6_comparisons_fold_with_their_own_meaning() -> None:
    # Java folded > < >= <= as !=, so 3 < 2 was 1.
    cases = {
        "3 > 2": 1, "2 > 3": 0, "3 < 2": 0, "2 < 3": 1,
        "2 >= 2": 1, "1 >= 2": 0, "2 <= 2": 1, "3 <= 2": 0,
    }  # fmt: skip
    for text, value in cases.items():
        model = ok(u8("x", "0") + f"\t\tif ({text}) {{\n{u8('c', '1')}\t\t}}\n")
        assert model.conditionals[0].condition.value == value, text


def test_bug_7_sizeof_char_is_one() -> None:
    # Java emitted sizeof(MMT_U8_DATA), which is 4.
    types = ("char", "short", "int", "long", "uint8_t*", "MMT_U16_DATA", "MMT_DATA_MAC_ADDR")
    model = ok(
        struct("in2", "uint8_t a, b;")
        + "".join(
            u8(f"s{i}", "0", length=f"sizeof({t})") for i, t in enumerate((*types, "struct in2"))
        )
    )
    lengths = [model.attribute(f"s{i}").length_value for i in range(8)]
    assert lengths == [1, 2, 4, 4, 4, 2, 6, 2]


def test_bug_9_omitted_scope_offset_and_data_len_get_the_plan_defaults() -> None:
    # Java emitted the text null for each.
    text = build(
        attr('alias="no_scope" data_type="MMT_U8_DATA" data_len="1" offset="0"')
        + attr('alias="no_len" data_type="MMT_U16_DATA" offset="1" scope="packet"')
        + attr('alias="hook" data_type="MMT_BINARY_DATA" scope="packet"')
    )
    model, diagnostics = run(text)
    assert model is not None
    assert codes(diagnostics) == ["model.default-scope"]
    assert diagnostics[0].severity is Severity.WARNING
    assert covered(text, diagnostics[0].location) == "no_scope"
    no_scope = model.attribute("no_scope")
    assert (no_scope.scope, no_scope.scope_defaulted) == (Scope.PACKET, True)
    no_len = model.attribute("no_len")
    assert (no_len.length_value, no_len.length_defaulted, no_len.aligned) == (2, True, False)
    hook = model.attribute("hook")
    assert hook.is_hook and hook.offset is None and hook.length is None
    # No fixed width, an offset and no data_len: an error, not a guess.
    found = errors(build(attr('alias="b" data_type="MMT_BINARY_DATA" offset="0" scope="packet"')))
    assert codes(found) == ["model.missing-length"]


def test_bug_12_conditional_attributes_are_duplicate_checked_and_usable_in_val() -> None:
    # arp declares ar_pro in its struct and again in an else branch.
    text = build(
        u8("ar_pro", "0")
        + "\t\tif (val(ar_pro) == 1) {\n"
        + u8("inner", "1")
        + "\t\t\tif (val(inner) > 2) {\n"
        + u8("deep", "val(inner)")
        + "\t\t\t}\n"
        + "\t\t} else {\n"
        + u8("AR_PRO", "1")
        + "\t\t}\n"
    )
    found = errors(text)
    assert codes(found) == ["model.duplicate-name"]
    assert covered(text, found[0].location) == "AR_PRO"
    first = found[0].related[0].location
    assert covered(text, first) == "ar_pro" and first is not None and first.line == 7
    model = ok(build(text.split("\t\t} else {")[0].split("\tAttributes {\n", 1)[1] + "\t\t}\n"))
    deep = model.attribute("deep").offset
    assert isinstance(deep, ValueRef) and deep.attribute == "inner"
    assert [g.holds for g in model.attribute("deep").guards] == [True, True]


def test_bug_16_names_are_checked_case_insensitively() -> None:
    # Aliases are lower-cased in the C, so len and LEN collide there.
    found = errors(build(u8("len", "0") + u8("LEN", "1")))
    assert codes(found) == ["model.duplicate-name"]
    assert "case-insensitive" in found[0].message


def test_bug_17_bitfield_helper_struct_names_are_unique() -> None:
    model = ok(
        struct("s_bits1", "uint8_t p;")
        + struct("s", "uint8_t a:4, b:4;", "uint8_t c:2, d:6;")
        + struct("t", "uint8_t e:4, f:4;")
    )
    names = [r.helper_name for s in model.structs for r in s.runs]
    assert names == ["s_bits1_", "s_bits2", "t_bits1"]
    users = {s.key for s in model.structs}
    assert len({n.lower() for n in names}) == 3 and not users & {n.lower() for n in names}


def test_bug_19_offset_and_len_are_the_attribute_s() -> None:
    # Java emitted calls to offset() and len() C functions that do not exist.
    model = ok(
        u8("n", "0")
        + u8("x", "4", length="2")
        + u8("y", "offset(x) + len(x)")
        + attr('alias="v" data_type="MMT_BINARY_DATA" data_len="val(n)" offset="8" scope="packet"')
        + u8("z", "len(v)")
    )
    y = model.attribute("y").offset
    assert isinstance(y, Binary) and y.value == 7
    assert isinstance(y.left, OffsetRef) and (y.left.attribute, y.left.value) == ("x", 5)
    assert isinstance(y.right, LengthRef) and (y.right.attribute, y.right.value) == ("x", 2)
    z = model.attribute("z").offset
    assert isinstance(z, LengthRef) and z.attribute == "v" and z.value is None


def test_bug_23_ids_are_validated() -> None:
    def outcome(pid: str, label: str = "p") -> list[str]:
        _, diagnostics = run(
            build(u8("a", "0"), properties=f'label = "{label}"\n\t\tid = "{pid}"')
        )
        return codes(diagnostics)

    assert outcome("960") == []
    assert outcome("999") == []
    assert outcome("0") == ["model.id-out-of-range"]
    assert outcome("-5") == ["model.id-out-of-range"]
    assert outcome("1000") == ["model.id-out-of-range"]
    assert outcome("1") == ["model.id-taken"]  # PROTO_META
    assert outcome("637") == ["model.id-taken"]  # PROTO_TPKT
    assert outcome("900") == ["model.id-outside-reserved-range"]
    assert outcome("960", "tcp") == ["model.name-taken"]
    assert outcome("960", "Meta") == ["model.name-taken"]
    model, diagnostics = run(build(u8("a", "0"), properties='label = "tpkt"\n\t\tid = "637"'))
    # The SDK conflicts are errors, but the model is still analysed (T1.6).
    assert model is not None and model.protocol.id == 637
    assert {d.severity for d in diagnostics} == {Severity.ERROR}


def test_struct_field_types_and_scopes() -> None:
    # Not a Java bug: struct X fields are MMT_BINARY_DATA of sizeof(struct X)
    # bytes and T* fields MMT_DATA_POINTER of 4 (decided rules).
    text = build(
        struct("in2", "uint8_t a, b;")
        + struct("o", "struct in2 i;", "char* p;", "MMT_DATA_IP6_ADDR v6;")
    )
    model, diagnostics = run(text)
    assert model is not None and codes(diagnostics) == ["model.pointer-field"]
    assert [
        (a.name, a.data_type, a.offset_value, a.length_value, a.scope)
        for a in model.attributes[2:]
    ] == [
        ("i", DataType.MMT_BINARY_DATA, 2, 2, Scope.PACKET),
        ("p", DataType.MMT_DATA_POINTER, 4, 4, Scope.PACKET),
        ("v6", DataType.MMT_DATA_IP6_ADDR, 8, 16, Scope.PACKET),
    ]
    assert isinstance(model.attribute("i").offset, Const)
