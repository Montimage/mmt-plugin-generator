"""``mmt_plugin.pluginyaml.convert``: a PDL v1 model as plugin.yaml, with a
``model.legacy-*`` warning on each construct that relied on a Java bug
(``docs/legacy/java-generator-inventory.md``, section 5), and none on a model
that relied on none."""

from __future__ import annotations

import pytest

from mmt_plugin.diagnostics import CODES, Diagnostic, Severity
from mmt_plugin.pdl import parse
from mmt_plugin.pdl.model import Offsets
from mmt_plugin.pluginyaml import load
from mmt_plugin.pluginyaml.convert import LEGACY_CODES, Conversion, convert
from mmt_plugin.sdk import Profile, get_bundled

FILE = "test.pdl"


def profile() -> Profile:
    found = get_bundled("1.10.2")
    assert found is not None
    return found


def build(
    attributes: str,
    *,
    properties: str = 'label = "p"\n\t\tid = "960"\n\t\tencoding = "network"',
    classify: str = "",
) -> str:
    return (
        "Protocol {\n"
        f"\tProperties {{\n\t\t{properties}\n\t}}\n"
        f"\tAttributes {{\n{attributes}\t}}\n"
        f"{classify}"
        "}\n"
    )


def attr(name: str, offset: str, *, dtype: str = "MMT_U8_DATA", length: str = "1") -> str:
    return (
        f'\t\tattribute {{ alias="{name}" data_type="{dtype}" data_len="{length}"'
        f' offset="{offset}" scope="packet" }}\n'
    )


def struct(name: str, *lines: str) -> str:
    body = "".join(f"\t\t\t{line}\n" for line in lines)
    return f"\t\tstruct {name} {{\n{body}\t\t}}\n"


def run(text: str) -> Conversion:
    return convert(parse(text, filename=FILE), profile())


def legacy(conversion: Conversion) -> list[str]:
    return [d.code for d in conversion.diagnostics if d.code.startswith("model.legacy-")]


def covered(text: str, d: Diagnostic) -> str:
    """The source text a diagnostic points at (one line)."""
    loc = d.location
    assert loc is not None and loc.line is not None and loc.column is not None
    line = text.splitlines()[loc.line - 1]
    assert loc.end_column is not None
    return line[loc.column - 1 : loc.end_column - 1]


def only(conversion: Conversion, code: str) -> Diagnostic:
    (found,) = [d for d in conversion.diagnostics if d.code == code]
    assert found.severity is Severity.WARNING
    return found


def test_every_legacy_code_is_a_registered_warning() -> None:
    for code in LEGACY_CODES:
        assert CODES[code].startswith("warning: import:"), code


def test_a_model_that_relied_on_no_java_bug_has_no_warning() -> None:
    text = build(
        struct("h", "uint8_t a;", "uint16_t b;")
        + attr("c", "0")
        + attr("v", "val(c)", length="val(c)", dtype="MMT_BINARY_DATA")
        + attr("ip", "4", dtype="MMT_DATA_IP_ADDR", length="4")
        + "\t\tif (1 != 2) {\n"
        + attr("d", "sizeof(uint16_t)")
        + "\t\t}\n"
    )
    conversion = run(text)
    assert conversion.diagnostics == ()
    assert conversion.offsets is Offsets.ABSOLUTE
    assert conversion.text is not None
    assert load(conversion.text, filename="plugin.yaml").model.offsets is Offsets.ABSOLUTE


def test_bug_23_an_sdk_id_or_name_is_a_warning_and_the_model_is_converted() -> None:
    conversion = run(build(attr("a", "0"), properties='label = "tpkt"\n\t\tid = "637"'))
    assert legacy(conversion) == ["model.legacy-sdk-conflict"] * 2
    assert all("(bug 23)" in d.message for d in conversion.diagnostics)
    assert conversion.text is not None and "label: tpkt\n  id: 637\n" in conversion.text


@pytest.mark.parametrize(
    "attributes",
    [
        # A conditional attribute named like an earlier one (arp's ar_pro, bug 12).
        attr("ar_pro", "0") + "\t\tif (val(ar_pro) == 1) {\n" + attr("AR_PRO", "1") + "\t\t}\n",
        # Two names that differ only in case (bug 16).
        attr("len", "0") + attr("LEN", "1"),
        # A struct field named like a later attribute in an else branch (bug 12).
        struct("s", "uint8_t k;")
        + "\t\tif (val(k) == 1) {\n"
        + attr("x", "1")
        + "\t\t} else {\n"
        + attr("k", "2")
        + "\t\t}\n",
    ],
    ids=["conditional", "case", "field"],
)
def test_bugs_12_and_16_duplicates_the_java_tool_accepted_keep_running_offsets(
    attributes: str,
) -> None:
    text = build(attributes)
    conversion = run(text)
    d = only(conversion, "model.legacy-duplicate-name")
    assert "(bug 12)" in d.message and "(bug 16)" in d.message
    assert d.related and d.related[0].message == "first defined here"
    assert conversion.offsets is Offsets.RUNNING
    assert conversion.text is not None
    assert "offsets: running\n" in conversion.text
    # Nothing is lost: the YAML is the model as written.
    again = load(conversion.text, filename="plugin.yaml").model
    assert again.offsets is Offsets.RUNNING


def test_a_duplicate_the_java_tool_refused_too_stops_the_conversion() -> None:
    conversion = run(build(attr("len", "0") + attr("len", "1")))
    assert conversion.text is None
    assert [(d.severity, d.code) for d in conversion.diagnostics] == [
        (Severity.ERROR, "model.duplicate-name")
    ]


def test_any_other_model_error_stops_the_conversion() -> None:
    conversion = run(build(attr("a", "val(nope)")))
    assert conversion.text is None
    assert [d.code for d in conversion.diagnostics] == ["model.unknown-attribute"]


def test_decision_8_and_bug_2_bitfield_order_and_the_offsets_after_a_bitfield_line() -> None:
    text = build(struct("h", "uint16_t a:4, b:12;", "uint16_t c;", "uint8_t d:2, e:6;"))
    conversion = run(text)
    assert legacy(conversion) == [
        "model.legacy-bitfield-order",
        "model.legacy-bitfield-offset",
        "model.legacy-bitfield-order",
    ]
    order, offset, second = conversion.diagnostics
    assert covered(text, order) == "a" and "`a`, `b`" in order.message
    assert covered(text, offset) == "c" and "(bug 2)" in offset.message
    assert covered(text, second) == "d"


def test_bug_3_an_aligned_element_after_a_struct_with_bitfields() -> None:
    text = build(struct("h", "uint8_t hi:4, lo:4;") + attr("next", "0") + attr("more", "0"))
    conversion = run(text)
    assert legacy(conversion) == ["model.legacy-bitfield-order", "model.legacy-bitfield-offset"]
    d = only(conversion, "model.legacy-bitfield-offset")
    assert "(bug 3)" in d.message and "`next`" in d.message
    assert (
        conversion.text is not None
        and "  - name: next\n    type: MMT_U8_DATA\n    offset: 1\n" in (conversion.text)
    )
    # Not after an attribute at a literal offset (alignment stopped).
    stopped = run(
        build(
            attr("n", "0")
            + attr("v", "val(n)", dtype="MMT_BINARY_DATA", length="val(n)")
            + struct("h", "uint8_t hi:4, lo:4;")
            + attr("later", "0")
        )
    )
    assert legacy(stopped) == ["model.legacy-bitfield-order"]


def test_bug_5_an_offset_or_length_that_reads_the_packet_but_ends_in_a_constant() -> None:
    text = build(
        attr("x", "0")
        + attr("y", "val(x) - 4")
        + attr("z", "4 - val(x)")
        + attr("w", "(1 + 2) * 3")
        + attr("b", "8", dtype="MMT_BINARY_DATA", length="val(x) * sizeof(uint16_t)")
    )
    conversion = run(text)
    assert legacy(conversion) == ["model.legacy-constant-folding"] * 2
    first, second = conversion.diagnostics
    assert covered(text, first) == "val(x) - 4" and "the offset of `y`" in first.message
    assert "the data_len of `b`" in second.message


def test_bug_6_a_constant_comparison_whose_value_is_not_the_one_of_ne() -> None:
    text = build(
        attr("x", "0")
        + "\t\tif (3 < 2) {\n"
        + attr("c", "1")
        + "\t\t}\n"
        + "\t\tif (3 > 2) {\n"
        + attr("d", "1")
        + "\t\t}\n"
        + "\t\tif (2 >= 2) {\n"
        + attr("e", "1")
        + "\t\t}\n"
    )
    conversion = run(text)
    # 3 > 2 is 1 either way; 3 < 2 and 2 >= 2 are not.
    assert legacy(conversion) == ["model.legacy-comparison"] * 2
    first, second = [d for d in conversion.diagnostics if d.code == "model.legacy-comparison"]
    assert covered(text, first) == "3 < 2"
    assert first.message == (
        "`3 < 2` is 0; the Java tool folded it as `3 != 2`, which is 1 (bug 6)"
    )
    assert covered(text, second) == "2 >= 2"


def test_bug_7_sizeof_char() -> None:
    text = build(attr("a", "sizeof(char)") + attr("b", "sizeof(unsigned char) + sizeof(char*)"))
    conversion = run(text)
    assert legacy(conversion) == ["model.legacy-sizeof-char"] * 2
    assert [covered(text, d) for d in conversion.diagnostics] == [
        "sizeof(char)",
        "sizeof(unsigned char)",
    ]


def test_bug_21_classifynext_without_encapsulation() -> None:
    classify = (
        "\tclassifynext {\n\t\tswitch(1) {\n\t\t\tcase 1: nextencaps = 30 break\n"
        "\t\t\tdefault: break\n\t\t}\n\t}\n"
    )
    conversion = run(build(attr("a", "0"), classify=classify))
    assert legacy(conversion) == ["model.legacy-classifynext"]
    encapsulated = run(
        build(
            attr("a", "0"),
            properties='label = "p"\n\t\tid = "960"\n\t\tencapsulation = "true"\n'
            '\t\tencoding = "network"',
            classify=classify,
        )
    )
    assert legacy(encapsulated) == []


def test_bug_25_an_ip_address_at_an_offset_that_reads_the_packet() -> None:
    text = build(
        attr("hlen", "0")
        + attr("fixed", "1", dtype="MMT_DATA_IP_ADDR", length="4")
        + attr("moved", "val(hlen)", dtype="MMT_DATA_IP_ADDR", length="4")
    )
    conversion = run(text)
    d = only(conversion, "model.legacy-ip-addr")
    assert covered(text, d) == "moved"


def test_the_default_scope_warning_is_dropped_and_others_are_kept() -> None:
    text = build(
        '\t\tattribute { alias="a" data_type="MMT_U8_DATA" data_len="1" offset="0" }\n',
        properties='label = "p"\n\t\tid = "949"\n\t\tencoding = "network"',
    )
    conversion = run(text)
    assert [d.code for d in conversion.diagnostics] == ["model.id-outside-reserved-range"]
