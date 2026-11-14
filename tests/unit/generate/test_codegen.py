"""Unit tests of ``mmt_plugin.codegen``: the Java bugs it fixes (named
``test_bug_<N>_...`` after ``docs/legacy/java-generator-inventory.md``,
section 5), determinism, the template policy and the generation errors."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from importlib import resources

import jinja2
import pytest

from mmt_plugin.codegen import (
    DIAGNOSTIC_CODES,
    ENVIRONMENT,
    TEMPLATES,
    GenerationError,
    c_int,
    c_name,
    generate,
)
from mmt_plugin.diagnostics import CODES
from mmt_plugin.pdl import parse
from mmt_plugin.pdl.model import DataType
from mmt_plugin.semantics import analyse

from .helpers import REPO, corpus_models, generate_text, profile, run_model
from .test_golden import ACCEPTED


def model(body: str, *, props: str = 'encoding = "network"', label: str = "t") -> str:
    """A PDL model with id 990 (third-party range) and ``body`` as its Attributes."""
    return (
        "Protocol {\n"
        f'  Properties {{ label = "{label}" id = "990" {props} }}\n'
        f"  Attributes {{\n{body}\n  }}\n"
        "}\n"
    )


def attr(alias: str, offset: str | None, *, dtype: str = "MMT_U8_DATA", length: str = "1") -> str:
    off = "" if offset is None else f' offset="{offset}"'
    return (
        f'    attribute {{ alias="{alias}" data_type="{dtype}" data_len="{length}"{off}'
        ' scope="packet" }'
    )


def files(text: str, label: str = "t") -> tuple[str, str]:
    g = generate_text(text)
    return g.file(f"{label}_mmt_plugin.h").text, g.file(f"{label}_mmt_plugin.c").text


def function(source: str, name: str) -> str:
    """The definition of a function of ``source``, from its name to its ``}``."""
    match = re.search(rf"^\S[^\n;]*\b{name}\([^;]*?\)\n\{{\n.*?^\}}$", source, re.M | re.S)
    assert match, f"no definition of {name}"
    return match.group(0)


def table_functions(source: str) -> list[str]:
    return re.findall(r"\.extraction_function = (\w+)\}", source)


# --- the Java bugs -----------------------------------------------------------


def test_bug_1_extraction_functions_never_use_the_table_before_its_definition() -> None:
    _, source = files(model(attr("a", "0") + "\n" + attr("b", "val(a)") + "\n" + attr("c", None)))
    table = source.index("static attribute_metadata_t t_attributes_metadata[")
    assert "t_attributes_metadata" not in source[:table]
    # Extraction functions compute their own offsets: the table is only
    # registered, never read back.
    after = source[table:]
    assert after.count("t_attributes_metadata[i]") == 2  # register, and the error message


@pytest.mark.parametrize(
    "encoding",
    [
        'encoding = "network"',
        'encoding = "host"',
        'encoding = "ASCII"',
        'encoding = "UNICODE"',
        "",
    ],
)
def test_bug_10_every_table_function_is_defined_whatever_the_encoding(encoding: str) -> None:
    body = "\n".join(
        [
            attr("a", "0"),
            attr("b", "1", dtype="MMT_U16_DATA", length="2"),
            attr("c", "3", dtype="MMT_BINARY_DATA", length="4"),
            attr("d", "7", dtype="MMT_DATA_IP_ADDR", length="4"),
            attr("e", None),
        ]
    )
    header, source = files(model(body, props=encoding))
    names = table_functions(source)
    assert len(names) == 5
    for name in names:
        defined = re.search(rf"^static int {name}\(", source, re.M) is not None
        declared = re.search(rf"^int {name}\(", header, re.M) is not None
        assert defined or declared, name
    # No encoding gives no byte order: network order, with a warning.
    g = generate_text(model(body, props=encoding))
    warned = [d.code for d in g.diagnostics] == ["model.default-byte-order"]
    assert warned == (encoding not in ('encoding = "network"', 'encoding = "host"'))


def test_bug_11_val_of_an_attribute_at_an_expression_offset_reads_that_offset() -> None:
    _, source = files(model(attr("hlen", "0") + "\n" + attr("x", "val(hlen)") + "\n"
                            + attr("y", "val(x) + 1")))  # fmt: skip
    place_x = function(source, "t_place_x")
    assert "*offset = t_val_hlen(packet, proto_index, &ok);" in place_x
    val_x = function(source, "t_val_x")
    assert "t_get_x(packet, proto_index, &value)" in val_x
    assert "t_add(t_val_x(packet, proto_index, &ok), 1, &ok)" in function(source, "t_place_y")
    assert "-2" not in source
    # x's table position is unknown, not a sentinel offset.
    assert ".position_in_packet = POSITION_NOT_KNOWN" in source


def test_bug_13_a_conditional_attribute_is_absent_when_no_branch_holds() -> None:
    body = (
        attr("k", "0")
        + "\n    if (val(k) == 1) {\n"
        + attr("one", "1")
        + "\n    } else {\n"
        + attr("other", "1")
        + "\n    }"
    )
    _, source = files(model(body))
    assert "if (!((t_val_k(packet, proto_index, &ok) == 1)) || !ok) {\n        return 0;" in (
        function(source, "t_place_one")
    )
    assert "if (((t_val_k(packet, proto_index, &ok) == 1)) || !ok) {\n        return 0;" in (
        function(source, "t_place_other")
    )
    # The extraction stores nothing unless the place and the bytes are known.
    extraction = function(source, "t_other_extraction")
    assert extraction.index("return 0;") < extraction.index("extracted_data->data")


def test_bug_14_a_conditional_attribute_without_offset_calls_its_hook() -> None:
    body = attr("k", "0") + "\n    if (val(k) == 2) {\n" + attr("opt", None) + "\n    }"
    header, source = files(model(body))
    assert "TODO" not in header + source
    assert (
        "int t_hook_extract_opt(const ipacket_t *packet, mmt_proto_index_t proto_index,"
        " attribute_t *extracted_data);" in header
    )
    wrapper = function(source, "t_opt_extraction")
    guard = wrapper.index("t_val_k(packet, proto_index, &ok) == 2")
    assert guard < wrapper.index("return t_hook_extract_opt(packet, proto_index, extracted_data);")
    assert "t_opt_extraction" in table_functions(source)


def test_bug_14_an_unconditional_hook_is_the_table_function_itself() -> None:
    _, source = files(model(attr("opt", None)))
    assert table_functions(source) == ["t_hook_extract_opt"]
    assert "t_opt_extraction" not in source


def test_bug_15_an_attribute_named_h_does_not_collide_with_the_include_guard() -> None:
    header, _ = files(model(attr("h", "0")))
    assert "#ifndef MMT_PLUGIN_T_H\n#define MMT_PLUGIN_T_H\n" in header
    assert "    T_H = 1,\n" in header
    assert "#define T_H_ALIAS " in header


def test_bug_15_a_name_that_still_collides_is_a_model_error() -> None:
    # T_ATTRIBUTES_NB is the attribute count; an attribute attributes_nb would
    # get the same enum constant.
    text = model(attr("attributes_nb", "0"))
    analysed, _ = analyse(parse(text, filename="t.pdl"), profile=profile())
    assert analysed is not None
    with pytest.raises(GenerationError) as exc:
        generate(analysed, profile())
    (d,) = exc.value.diagnostics
    assert d.code == "model.name-collision"
    assert "T_ATTRIBUTES_NB" in d.message


def test_bug_18_structs_are_emitted_in_declaration_order() -> None:
    body = "\n".join(
        f"    struct {name} {{ uint8_t {name}_a; }}" for name in ("zeta", "alpha", "mid", "beta")
    )
    header, source = files(model(body))
    tags = re.findall(r"^struct (\w+) \{", header, re.M)
    assert tags == ["zeta", "alpha", "mid", "beta"]
    asserts = re.findall(r"_Static_assert\(sizeof\(struct (\w+)\)", source)
    assert asserts == tags


def test_bug_20_session_callbacks_are_hooks_with_the_profile_signatures() -> None:
    header, source = files(model(attr("a", "0"), props='session = "true" encoding = "network"'))
    p = profile()
    for role, name in (
        ("sessionizer", "t_hook_sessionizer"),
        ("session_context_cleanup", "t_hook_session_cleanup"),
        ("session_key_comparison", "t_hook_session_compare"),
    ):
        cb = p.callback(role)
        sep = "" if cb.returns.endswith("*") else " "
        args = ", ".join(x.declaration for x in cb.params)
        assert f"{cb.returns}{sep}{name}({args});" in header
        # Declared for the user, never defined (or stubbed) by the generator.
        assert not re.search(rf"\b{name}\([^;]*\)\n\{{", source)
    assert (
        "register_sessionizer_function(protocol_struct, t_hook_sessionizer,"
        " t_hook_session_cleanup, t_hook_session_compare);" in source
    )


def test_bug_20_every_generated_function_returns_a_value() -> None:
    # gcc -Werror=return-type in the compile check covers every golden; this
    # also holds without the SDK: no generated non-void function falls off.
    for name in ACCEPTED:
        generation = run_model(name).generation
        assert generation is not None
        source = next(f.text for f in generation.files if f.name.endswith(".c"))
        for body in re.findall(r"^(?:static )?(?!void)\w[^\n;(]*\([^;]*?\)\n\{\n(.*?)^\}$",
                               source, re.M | re.S):  # fmt: skip
            assert body.rstrip().splitlines()[-1].strip().startswith("return "), (name, body)


def test_bug_21_classifynext_is_generated_without_encapsulation() -> None:
    text = (
        "Protocol {\n"
        '  Properties { label = "t" id = "990" encoding = "network" }\n'
        f"  Attributes {{\n{attr('k', '0')}\n  }}\n"
        "  classifynext { switch(val(k)) { case 1: nextencaps = 991 nextoffset = 1 break"
        " default: break } }\n"
        "}\n"
    )
    g = generate_text(text)
    source = g.file("t_mmt_plugin.c").text
    assert "static mmt_classify_verdict_t t_classify_next(ipacket_t *ipacket," in source
    assert "register_classification_function(protocol_struct, t_classify_next)" in source
    assert [d.code for d in g.diagnostics] == ["model.classifynext-without-encapsulation"]


def test_bug_22_register_protocol_stack_is_never_emitted() -> None:
    for name in ACCEPTED:
        generation = run_model(name).generation
        assert generation is not None
        for f in generation.files:
            assert "register_protocol_stack" not in f.text, (name, f.name)
            assert "stack_classification" not in f.text, (name, f.name)


def test_bug_25_an_ip_address_is_copied_byte_for_byte_on_every_path() -> None:
    body = "\n".join(
        [
            attr("hlen", "0"),
            attr("fixed", "1", dtype="MMT_DATA_IP_ADDR", length="4"),
            attr("moved", "val(hlen)", dtype="MMT_DATA_IP_ADDR", length="4"),
        ]
    )
    _, source = files(model(body))
    bodies = [function(source, f"t_{n}_extraction") for n in ("fixed", "moved")]
    for text in bodies:
        assert "memcpy(extracted_data->data, p, n);" in text
        assert "read" not in text and "ntoh" not in text
    # The same code on both paths, apart from the name of the place function.
    assert bodies[0].replace("fixed", "X") == bodies[1].replace("moved", "X")


# --- layout and reading ------------------------------------------------------


def test_bitfields_are_shifted_and_masked_from_the_msb_of_their_unit() -> None:
    generation = run_model("pdl_bitfields").generation
    assert generation is not None
    source = generation.file("pdl_bitfields_mmt_plugin.c").text
    expected = {
        "b_hi": "(pdl_bitfields_read(p, 1) >> 5) & UINT64_C(0x7)",
        "b_lo": "(pdl_bitfields_read(p, 1)) & UINT64_C(0xf)",
        "w_b": "(pdl_bitfields_read(p, 2) >> 4) & UINT64_C(0xff)",
        "d_c": "(pdl_bitfields_read(p, 4) >> 8) & UINT64_C(0xffff)",
    }
    for key, read in expected.items():
        assert f"*value = {read};" in function(source, f"pdl_bitfields_get_{key}")
    # The unit at its packed wire offset (w_a..w_c at byte 3), never a C
    # bitfield overlaid on the packet.
    assert "*offset = 3;\n    *length = 2;" in function(source, "pdl_bitfields_place_w_b")
    header = generation.file("pdl_bitfields_mmt_plugin.h").text
    assert not re.search(r":\s*\d+;", header)
    assert "} __attribute__((packed));" in header


def test_host_encoding_reads_little_endian_on_every_machine() -> None:
    generation = run_model("pdl_encoding_host").generation
    assert generation is not None
    source = generation.file("pdl_host_mmt_plugin.c").text
    assert "value = (value << 8) | p[width - 1 - i];" in source
    assert "ntoh" not in source


def test_c_keywords_get_a_trailing_underscore() -> None:
    generation = run_model("pdl_keyword_names").generation
    assert generation is not None
    header = generation.file("pdl_keywords_mmt_plugin.h").text
    for member in ("sizeof_", "int_", "char_"):
        assert f"    uint8_t {member}; " in header
    assert "uint8_t id;" in header  # a PDL keyword that C allows keeps its name
    assert [c_name(n) for n in ("int", "len", "_Bool", "data")] == [
        "int_",
        "len",
        "_Bool_",
        "data",
    ]


def test_c_int_spells_every_int64_and_refuses_the_rest() -> None:
    assert [c_int(v) for v in (0, 7, -7, 2**31 - 1)] == ["0", "7", "(-7)", "2147483647"]
    assert c_int(2**31) == "INT64_C(2147483648)"
    assert c_int(-(2**40)) == "(-INT64_C(1099511627776))"
    assert c_int(-(2**63)) == "INT64_MIN"
    with pytest.raises(ValueError):
        c_int(2**63)


# --- generation errors and warnings -------------------------------------------


def _generation_error(text: str) -> list[str]:
    analysed, diagnostics = analyse(parse(text, filename="t.pdl"), profile=profile())
    assert analysed is not None, [d.message for d in diagnostics]
    with pytest.raises(GenerationError) as exc:
        generate(analysed, profile())
    return [d.code for d in exc.value.diagnostics]


def test_an_integer_wider_than_8_bytes_is_a_model_error() -> None:
    assert _generation_error(model(attr("w", "0", dtype="MMT_U64_DATA", length="9"))) == [
        "model.integer-length"
    ]


@pytest.mark.parametrize(
    ("dtype", "stored"), [("MMT_U8_DATA", 1), ("MMT_U16_DATA", 2), ("MMT_U32_DATA", 4)]
)
def test_an_integer_wider_than_its_storage_is_a_model_error(dtype: str, stored: int) -> None:
    # Review of #14: the value is stored in `stored` bytes, so a wider
    # data_len would silently lose its high bytes.
    _, source = files(model(attr("x", "0", dtype=dtype, length=str(stored))))
    assert f".data_type = {dtype}, .data_len = {stored}," in source
    assert _generation_error(model(attr("x", "0", dtype=dtype, length=str(stored + 1)))) == [
        "model.integer-length"
    ]


def test_a_narrower_integer_and_a_hook_keep_their_data_len() -> None:
    _, source = files(model(attr("x", "0", dtype="MMT_U32_DATA", length="3")))
    assert "*value = t_read(p, 3);" in function(source, "t_get_x")
    # A user hook stores the value itself: its data_len only places what follows.
    files(model(attr("h", None, length="3")))


def test_a_per_packet_integer_length_is_bounded_by_its_storage() -> None:
    body = attr("k", "0") + "\n" + attr("x", "1", dtype="MMT_U16_DATA", length="val(k)")
    _, source = files(model(body))
    assert "if (length < 1 || length > 2) {" in function(source, "t_get_x")


@pytest.mark.parametrize(
    ("dtype", "length", "checked"),
    [
        ("MMT_U64_DATA", "8", True),
        ("MMT_U64_DATA", "7", False),
        ("MMT_U32_DATA", "4", False),
    ],
)
def test_val_of_a_u64_above_int64_max_fails_the_evaluation(
    dtype: str, length: str, checked: bool
) -> None:
    # Review of #14: expressions compute in int64_t, so (int64_t) of a value
    # of 2^63 or more would be negative; it fails as an overflow does.
    body = attr("v", "0", dtype=dtype, length=length) + "\n" + attr("x", "val(v)")
    _, source = files(model(body))
    val = function(source, "t_val_v")
    assert ("if (value > (uint64_t) INT64_MAX) {" in val) == checked
    assert val.endswith("    return (int64_t) value;\n}")


def test_val_of_a_64_bit_bitfield_is_checked_too() -> None:
    body = "    struct s { MMT_U64_DATA a:64; }\n" + attr("x", "val(a)")
    _, source = files(model(body))
    assert "if (value > (uint64_t) INT64_MAX) {" in function(source, "t_val_a")


def test_a_fixed_size_sdk_type_needs_a_constant_length() -> None:
    body = attr("k", "0") + "\n" + attr("tv", "1", dtype="MMT_DATA_TIMEVAL", length="val(k)")
    assert _generation_error(model(body)) == ["model.variable-length"]


#: A data_len for one attribute of each PDL type, as corpus model pdl_types gives it.
_TYPE_LENGTHS = {
    "MMT_U8_DATA": 1,
    "MMT_U16_DATA": 2,
    "MMT_U32_DATA": 4,
    "MMT_U64_DATA": 8,
    "MMT_DATA_POINTER": 4,
    "MMT_STRING_DATA": 4,
    "MMT_DATA_IP_NET": 4,
    "MMT_DATA_MAC_ADDR": 6,
    "MMT_DATA_IP_ADDR": 4,
    "MMT_DATA_PATH": 8,
    "MMT_DATA_TIMEVAL": 8,
    "MMT_BINARY_DATA": 6,
    "MMT_DATA_BUFFER": 4,
    "MMT_DATA_CHAR": 1,
    "MMT_DATA_IP6_ADDR": 16,
    "MMT_DATA_PORT": 2,
    "MMT_DATA_POINT": 4,
    "MMT_DATA_PORT_RANGE": 4,
    "MMT_DATA_DATE": 4,
    "MMT_DATA_TIMEARG": 4,
    "MMT_DATA_STRING_INDEX": 4,
    "MMT_DATA_FLOAT": 4,
    "MMT_DATA_LAYERID": 1,
    "MMT_DATA_FILTER_STATE": 2,
    "MMT_DATA_PARENT": 2,
    "MMT_BINARY_VAR_DATA": 5,
}

#: The value of each non-literal data_len the generator emits, on LP64 with
#: the mmt-dpi 1.10.2 headers (test_compile.py checks the sizes it registers).
_DATA_LEN_VALUES = {
    "sizeof(mac_addr_t)": 6,
    "IPv6_ALEN": 16,
    "BINARY_64DATA_TYPE_LEN": 68,
    "sizeof(mmt_binary_var_data_t)": 1028,
    "sizeof(void *)": 8,
}


def test_every_pdl_type_has_an_sdk_size_in_the_profile() -> None:
    sized = {c.name for c in profile().constants if c.size is not None}
    assert sized == set(_TYPE_LENGTHS) == {t.value for t in DataType}


@pytest.mark.parametrize("dtype", sorted(_TYPE_LENGTHS))
def test_the_registered_data_len_fits_the_sdk_size_of_its_type(dtype: str) -> None:
    # Review of #14: mmt-dpi 1.10.2 registers an attribute only if its
    # data_len is at most get_data_size_by_data_type() of its type, or 0 when
    # that is 0, and sizes the attribute's buffer from both; a type of size 0
    # has no buffer to extract into, so it is a model error.
    size = profile().data_size(dtype)
    text = model(attr("x", "0", dtype=dtype, length=str(_TYPE_LENGTHS[dtype])))
    if size == 0:
        assert _generation_error(text) == ["model.type-size"]
        return
    _, source = files(text)
    match = re.search(r"\.data_type = (\w+), \.data_len = ([^,]+),", source)
    assert match is not None and match.group(1) == dtype
    data_len = match.group(2)
    value = _DATA_LEN_VALUES[data_len] if data_len in _DATA_LEN_VALUES else int(data_len)
    assert 0 < value <= size, f"{dtype}: data_len {data_len} is not 1 to {size}"


def test_a_type_without_an_sdk_size_names_a_sized_alternative() -> None:
    with pytest.raises(GenerationError) as exc:
        generate_text(model(attr("p", "0", dtype="MMT_DATA_PORT", length="2")))
    (diagnostic,) = exc.value.diagnostics
    assert diagnostic.code == "model.type-size"
    assert diagnostic.hint == "use MMT_U16_DATA instead"
    assert diagnostic.location is not None


@pytest.mark.parametrize(("dtype", "size"), [("MMT_DATA_FLOAT", 4), ("MMT_DATA_TIMEVAL", 16)])
def test_a_constant_length_above_the_sdk_size_is_a_model_error(dtype: str, size: int) -> None:
    _, source = files(model(attr("x", "0", dtype=dtype, length=str(size))))
    assert f".data_type = {dtype}, .data_len = {size}," in source
    assert _generation_error(model(attr("x", "0", dtype=dtype, length=str(size + 1)))) == [
        "model.type-size"
    ]


@pytest.mark.parametrize(
    "use",
    [
        "    if (val(h) == 1) {\n" + attr("x", "1") + "\n    }",
        attr("x", "val(h)"),
        attr("x", "1", length="val(h)", dtype="MMT_BINARY_DATA"),
    ],
)
def test_val_of_a_hook_attribute_is_a_model_error(use: str) -> None:
    # Review of #14: the generated code would call a get function that
    # does not exist, since only the user hook extracts h.
    assert _generation_error(model(attr("h", None) + "\n" + use)) == ["model.hook-value"]


VARIABLE_HOOK = attr("n", "0") + "\n" + attr("h", None, dtype="MMT_BINARY_DATA", length="val(n)")


@pytest.mark.parametrize(
    "use",
    [
        attr("x", "len(h)"),
        attr("x", "1", length="len(h)", dtype="MMT_BINARY_DATA"),
        "    if (len(h) > 2) {\n" + attr("x", "1") + "\n    }",
    ],
)
def test_len_of_a_hook_attribute_computed_per_packet_is_a_model_error(use: str) -> None:
    # Review of #14: len(h) of a hook whose data_len does not fold.
    assert _generation_error(model(VARIABLE_HOOK + "\n" + use)) == ["model.hook-value"]


def test_len_of_a_hook_attribute_with_a_constant_length_folds() -> None:
    _, source = files(model(attr("h", None, length="3") + "\n" + attr("x", "len(h)")))
    assert "*offset = 3;" in function(source, "t_place_x")


def test_len_of_a_hook_attribute_in_classifynext_is_a_model_error() -> None:
    text = model(VARIABLE_HOOK, props='encapsulation = "true" encoding = "network"').replace(
        "  }\n}\n",
        "  }\n  classifynext { switch(val(n)) { case 1: nextencaps = 991 nextoffset = len(h)"
        " break default: break } }\n}\n",
    )
    assert _generation_error(text) == ["model.hook-value"]


def test_val_of_a_hook_attribute_in_classifynext_is_a_model_error() -> None:
    text = model(attr("h", None), props='encapsulation = "true" encoding = "network"').replace(
        "  }\n}\n",
        "  }\n  classifynext { switch(val(h)) { case 1: nextencaps = 991 break default: break } }"
        "\n}\n",
    )
    assert _generation_error(text) == ["model.hook-value"]


def test_a_define_named_like_a_name_of_the_generated_c_is_a_model_error() -> None:
    text = model(attr("a", "0")).replace("Protocol {\n", "Protocol {\n  define data = 1\n")
    assert _generation_error(text) == ["model.name-collision"]


def test_a_folded_condition_is_decided_at_generation() -> None:
    body = "    if (2 > 1) {\n" + attr("always", "0") + "\n    }"
    _, source = files(model(body))
    assert "|| !ok" not in function(source, "t_place_always")


def test_the_generation_codes_are_registered() -> None:
    assert set(DIAGNOSTIC_CODES) <= set(CODES)


# --- determinism and the template policy --------------------------------------


def _digest() -> str:
    digest = hashlib.sha256()
    for name in corpus_models():
        generation = run_model(name).generation
        if generation is not None:
            for f in generation.files:
                digest.update(f.name.encode() + b"\0" + f.data)
    return digest.hexdigest()


def test_generation_is_byte_identical_on_a_rerun() -> None:
    for name in ACCEPTED:
        first = run_model(name).generation
        assert first is not None
        analysed, _ = analyse(
            parse((REPO / f"tests/corpus/models/{name}/model.pdl").read_text(), filename="m"),
            profile=profile(),
        )
        assert analysed is not None
        assert generate(analysed, profile()).files == first.files


_DIGEST_SCRIPT = """
import hashlib, sys
from pathlib import Path
from mmt_plugin.codegen import GenerationError, generate
from mmt_plugin.pdl import parse
from mmt_plugin.sdk import get_bundled
from mmt_plugin.semantics import analyse
profile = get_bundled("1.10.2")
digest = hashlib.sha256()
for d in sorted(Path(sys.argv[1]).iterdir()):
    try:
        model = parse((d / "model.pdl").read_text(encoding="utf-8"),
                      filename=f"tests/corpus/models/{d.name}/model.pdl")
    except Exception:
        continue
    analysed, _ = analyse(model, profile=profile)
    if analysed is None:
        continue
    try:
        generation = generate(analysed, profile)
    except GenerationError:
        continue
    for f in generation.files:
        digest.update(f.name.encode() + b"\\0" + f.data)
print(digest.hexdigest())
"""


@pytest.mark.parametrize("seed", ["0", "4242"])
def test_generation_does_not_depend_on_the_hash_seed(seed: str) -> None:
    proc = subprocess.run(
        [sys.executable, "-c", _DIGEST_SCRIPT, str(REPO / "tests/corpus/models")],
        capture_output=True,
        text=True,
        env={"PYTHONHASHSEED": seed, "PATH": "/usr/bin:/bin"},
        check=True,
    )
    assert proc.stdout.strip() == _digest()


def test_the_output_has_no_path_timestamp_or_version() -> None:
    from mmt_plugin import __version__

    for name in ACCEPTED:
        generation = run_model(name).generation
        assert generation is not None
        for f in generation.files:
            assert str(REPO) not in f.text
            assert "tests/corpus" not in f.text
            assert __version__ not in f.text
            assert not re.search(r"\b20\d\d-\d\d-\d\d\b", f.text)
            assert f.text.isascii() and f.text.endswith("\n") and "\r" not in f.text


def test_the_template_policy() -> None:
    assert ENVIRONMENT.undefined is jinja2.StrictUndefined
    assert ENVIRONMENT.autoescape is False
    assert ENVIRONMENT.trim_blocks and ENVIRONMENT.lstrip_blocks
    assert ENVIRONMENT.keep_trailing_newline
    assert sorted(TEMPLATES.values()) == ["plugin.c.j2", "plugin.h.j2"]
    for name in TEMPLATES.values():
        assert resources.files("mmt_plugin.codegen").joinpath("templates").joinpath(name).is_file()
    with pytest.raises(jinja2.UndefinedError):
        ENVIRONMENT.get_template(TEMPLATES["header"]).render()


def test_no_sdk_name_is_written_in_the_templates() -> None:
    p = profile()
    names = {
        *(t.name for t in p.types),
        *(s.name for s in p.structs),
        *(cb.typedef for cb in p.callbacks),
        *(f.name for f in (*p.registrations, *p.helpers)),
        *(c.name for c in p.constants),
        *(m.name for m in p.macros),
        *(h.name for h in p.headers),
    }
    for template in TEMPLATES.values():
        text = (
            resources.files("mmt_plugin.codegen")
            .joinpath("templates")
            .joinpath(template)
            .read_text()
        )
        words = set(re.findall(r"[A-Za-z_][A-Za-z0-9_.]*", text))
        assert not names & words, (template, sorted(names & words))


def test_the_includes_are_profile_headers() -> None:
    headers = {h.name for h in profile().headers}
    for name in ACCEPTED:
        generation = run_model(name).generation
        assert generation is not None
        for f in generation.files:
            for include in re.findall(r'^#include "([^"]+)"', f.text, re.M):
                assert include in headers or include.endswith("_mmt_plugin.h"), include


def test_hooks_are_reported_for_the_impl_scaffold() -> None:
    generation = run_model("pdl_scopes").generation
    assert generation is not None
    assert [(h.name, h.role, h.attribute) for h in generation.hooks] == [
        ("pdl_scopes_hook_extract_no_off", "attribute_extraction", "no_off"),
        ("pdl_scopes_hook_sessionizer", "sessionizer", None),
        ("pdl_scopes_hook_session_cleanup", "session_context_cleanup", None),
        ("pdl_scopes_hook_session_compare", "session_key_comparison", None),
    ]
    json.dumps([h.declaration for h in generation.hooks])
