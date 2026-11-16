"""Reading plugin.yaml into the typed model (``mmt_plugin.pluginyaml.load``):
expressions and field types in PDL v1 syntax at their place in the YAML,
absolute offsets, struct offsets, parents and their generated
classification, and the profile pin."""

from __future__ import annotations

import pytest

from mmt_plugin.codegen import generate
from mmt_plugin.pdl.model import Offsets, Scope
from mmt_plugin.pluginyaml import PluginYamlError, dumps, load, profile_pin
from mmt_plugin.semantics import AnalysedModel, analyse

from .corpus import REPO, profile

HEAD = "schema: 1\nprotocol:\n  label: p\n  id: 960\n  encoding: network\n"


def _errors(text: str) -> list[tuple[str, int, int]]:
    with pytest.raises(PluginYamlError) as info:
        load(text, filename="plugin.yaml")
    return [
        (d.code, d.location.line or 0, d.location.column or 0)
        for d in info.value.diagnostics
        if d.location is not None
    ]


def _analyse(text: str) -> AnalysedModel:
    model = load(text, filename="plugin.yaml").model
    analysed, diagnostics = analyse(model, profile=profile())
    assert analysed is not None, diagnostics
    assert not diagnostics, diagnostics
    return analysed


def test_an_expression_error_is_at_its_place_in_the_yaml() -> None:
    text = HEAD + "attributes:\n  - name: a\n    type: MMT_U8_DATA\n    offset: val(a) +\n"
    assert _errors(text) == [("model.syntax.unexpected-end", 9, 21)]
    quoted = text.replace("offset: val(a) +", 'offset: "1 2"')
    assert _errors(quoted) == [("model.syntax.unexpected-token", 9, 16)]


def test_every_expression_error_is_reported() -> None:
    text = (
        HEAD + "attributes:\n  - name: a\n    type: MMT_U8_DATA\n    offset: x\n"
        "  - name: b\n    type: MMT_U8_DATA\n    offset: 0\n    length: 1 1\n"
        "  - if: (1\n    then: []\n"
    )
    assert [code for code, _, _ in _errors(text)] == [
        "model.syntax.invalid-expression",
        "model.syntax.unexpected-token",
        "model.syntax.unexpected-end",
    ]


def test_a_struct_offset_needs_absolute_offsets() -> None:
    text = (
        HEAD + "offsets: running\nattributes:\n  - struct: s\n    offset: 2\n    fields:\n"
        "      - name: f\n        type: uint8_t\n"
    )
    assert _errors(text) == [("model.schema", 9, 5)]


def test_absolute_offsets_read_every_offset_from_the_start() -> None:
    text = (
        HEAD + "attributes:\n"
        "  - name: a\n    type: MMT_U8_DATA\n    offset: 0\n    length: 1\n"
        "  - name: b\n    type: MMT_U16_DATA\n    offset: 0\n"
        "  - struct: s\n    offset: 5\n    fields:\n      - name: f\n        type: uint8_t\n"
        "      - type: uint8_t\n        bits:\n          - {name: hi, width: 4}\n"
        "          - {name: lo, width: 4}\n"
        "  - name: tail\n    type: MMT_U8_DATA\n    offset: 1\n    length: 1\n"
    )
    model = _analyse(text)
    assert [(a.name, a.offset_value, a.aligned) for a in model.attributes] == [
        ("a", 0, False),
        ("b", 0, False),
        ("f", 5, False),
        ("hi", 6, False),
        ("lo", 6, False),
        ("tail", 1, False),
    ]
    assert model.attribute("b").length_value == 2  # the type's width
    assert model.struct("s").base_offset == 5
    assert model.attribute("lo").bitfield is not None
    # With PDL v1's running offset, a is aligned, and b, which has no length,
    # stops the alignment: its offset and the struct's are literal.
    running = _analyse(
        text.replace("    offset: 5\n", "").replace(HEAD, HEAD + "offsets: running\n")
    )
    assert [(a.name, a.offset_value, a.aligned) for a in running.attributes][:3] == [
        ("a", 0, True),
        ("b", 0, False),
        ("f", 0, False),
    ]
    aligned = _analyse(
        text.replace("    offset: 5\n", "")
        .replace(HEAD, HEAD + "offsets: running\n")
        .replace("MMT_U16_DATA\n    offset: 0\n", "MMT_U16_DATA\n    offset: 0\n    length: 2\n")
    )
    assert [(a.name, a.offset_value) for a in aligned.attributes][:3] == [
        ("a", 0),
        ("b", 1),
        ("f", 3),
    ]


def test_the_scope_defaults_to_packet_without_a_warning() -> None:
    text = HEAD + "attributes:\n  - name: a\n    type: MMT_U8_DATA\n    offset: 0\n"
    model = _analyse(text)
    assert model.attribute("a").scope is Scope.PACKET
    session = _analyse(text + "    scope: session\n")
    assert session.attribute("a").scope is Scope.SESSION
    assert "scope: session" in dumps(session)


def test_a_variable_length_attribute() -> None:
    text = (
        HEAD + "attributes:\n  - name: len\n    type: MMT_U8_DATA\n    offset: 0\n"
        "  - name: data\n    type: MMT_BINARY_DATA\n    offset: 1\n    length: val(len) - 1\n"
    )
    model = _analyse(text)
    data = model.attribute("data")
    assert data.length is not None and data.length_value is None
    source = generate(model, profile()).file("p_mmt_plugin.c").text
    assert "p_place_data" in source


def test_defines_and_classify_next_keep_their_spelling() -> None:
    text = (
        "schema: 1\nprotocol:\n  label: p\n  id: 960\n  encapsulation: true\n"
        "  encoding: network\ndefines:\n  KIND_A: 0x01\n  NEXT_A: 955\n  NEXT_B: NEXT_A\n"
        "attributes:\n  - name: kind\n    type: MMT_U8_DATA\n    offset: 0\n"
        "classify_next:\n  switch: val(kind)\n  cases:\n"
        "    - case: KIND_A\n      next: NEXT_B\n      offset: 1\n"
        "    - case: 2\n      fallthrough: true\n    - case: 3\n      offset: 2\n"
        "  default:\n    next: 959\n"
    )
    model = _analyse(text)
    assert [(d.name, d.value, d.alias_of) for d in model.defines] == [
        ("KIND_A", 1, None),
        ("NEXT_A", 955, None),
        ("NEXT_B", 955, "NEXT_A"),
    ]
    switch = model.classify_next
    assert switch is not None
    assert [(c.label, c.has_break) for c in switch.cases] == [(1, True), (2, False), (3, True)]
    assert dumps(model) == text


def test_parents_and_their_classification() -> None:
    text = (
        HEAD + "parents:\n"
        "  - protocol: Ethernet\n    weight: 1\n    classify:\n"
        "      match:\n        - {offset: 12, length: 2, value: 0x88b5}\n"
        "        - {offset: 14, length: 1, value: 7}\n      offset: 16\n"
        "  - protocol: udp\n"
        "  - protocol: udp\n    classify:\n"
        "      match:\n        - {offset: 2, length: 2, value: 4433}\n      offset: 8\n"
        "attributes:\n  - name: a\n    type: MMT_U8_DATA\n    offset: 0\n"
    )
    model = _analyse(text)
    eth, udp, udp2 = model.parents
    assert (eth.name, eth.macro, eth.weight, eth.offset) == ("Ethernet", "PROTO_ETHERNET", 1, 16)
    assert eth.match is not None and [(m.offset, m.length, m.value) for m in eth.match] == [
        (12, 2, 0x88B5),
        (14, 1, 7),
    ]
    assert (udp.macro, udp.weight, udp.match, udp.offset) == ("PROTO_UDP", 5, None, None)
    assert udp2.match is not None
    source = generate(model, profile()).file("p_mmt_plugin.c").text
    # One classification function per classified parent, registered by the
    # init before the user's register_parents hook.
    assert "static mmt_classify_verdict_t p_classify_after_ethernet_1(" in source
    assert "static mmt_classify_verdict_t p_classify_after_udp_2(" in source
    assert "p_classify_after_udp(" not in source
    assert "(((uint64_t) p[12] << 8) | (uint64_t) p[13]) != 0x88b5u" in source
    assert "(uint64_t) p[14] != 0x7u" in source
    assert "if (start < 0 || start > caplen - 15) {" in source
    assert "next.offset = 16;" in source
    register = (
        "register_classification_function_with_parent_protocol(99 /* PROTO_ETHERNET */,"
        " p_classify_after_ethernet_1, 1)"
    )
    assert register in source
    assert source.index(register) < source.index("if (!p_hook_register_parents(protocol_struct))")
    assert dumps(_analyse(dumps(model))) == dumps(model)
    assert "        - offset: 12\n          length: 2\n          value: 0x88b5\n" in dumps(model)


def test_a_classified_parent_must_be_in_the_profile_and_its_values_must_fit() -> None:
    text = (
        HEAD + "parents:\n  - protocol: nope\n  - protocol: other\n    classify:\n"
        "      match:\n        - {offset: 0, length: 1, value: 256}\n      offset: 1\n"
    )
    model = load(text, filename="plugin.yaml").model
    analysed, diagnostics = analyse(model, profile=profile())
    assert analysed is None
    assert [(d.code, d.location.line if d.location else 0) for d in diagnostics] == [
        ("model.unknown-parent", 8),
        ("model.out-of-range", 11),
    ]


def test_a_tcp_parent_classified_by_port() -> None:
    text = (
        HEAD + "parents:\n  - protocol: TCP\n    classify:\n"
        "      port: 4840\n      sport: 0x10\n"
        "      match:\n        - {offset: 1, length: 2, value: 0x454c}\n"
        "attributes:\n  - name: a\n    type: MMT_U8_DATA\n    offset: 0\n"
    )
    model = _analyse(text)
    (tcp,) = model.parents
    assert (tcp.name, tcp.macro, tcp.offset) == ("TCP", "PROTO_TCP", None)
    assert tcp.ports == (("port", 4840), ("sport", 16))
    assert tcp.match is not None and [(m.offset, m.length, m.value) for m in tcp.match] == [
        (1, 2, 0x454C)
    ]
    source = generate(model, profile()).file("p_mmt_plugin.c").text
    function = source.split("static mmt_classify_verdict_t p_classify_after_tcp(", 2)[2]
    function = function.split("\n}\n", 1)[0]
    # The port is either one; every port must hold.
    assert (
        "if ((((uint64_t) p[0] << 8) | (uint64_t) p[1]) != 0x12e8u"
        " && (((uint64_t) p[2] << 8) | (uint64_t) p[3]) != 0x12e8u) {"
    ) in function
    assert "if ((((uint64_t) p[0] << 8) | (uint64_t) p[1]) != 0x10u) {" in function
    # The payload starts after the header's data offset, which the
    # protocol's offset is; the segment ends with the IP packet.
    assert "header = (int64_t) (p[12] >> 4) * 4;" in function
    assert "if (header < 20 || header > caplen - start) {" in function
    assert "length = (int64_t) ((unsigned) q[2] << 8 | q[3]);" in function
    assert "if (end - start <= header || end - start - header < 3) {" in function
    assert function.index("p += header;") < function.index(
        "(uint64_t) p[1] << 8) | (uint64_t) p[2]"
    )
    assert "next.offset = (uint16_t) header;" in function
    assert (
        "register_classification_function_with_parent_protocol(354 /* PROTO_TCP */,"
        " p_classify_after_tcp, 5)"
    ) in source
    assert dumps(model).endswith(
        "parents:\n  - protocol: TCP\n    classify:\n      port: 4840\n      sport: 0x10\n"
        "      match:\n        - offset: 1\n          length: 2\n          value: 0x454c\n"
        + dumps(model).split("      value: 0x454c\n", 1)[1]
    )
    assert dumps(_analyse(dumps(model))) == dumps(model)


def test_a_tcp_port_without_payload_matches() -> None:
    text = (
        HEAD + "parents:\n  - protocol: tcp\n    classify:\n      dport: 102\n"
        "attributes:\n  - name: a\n    type: MMT_U8_DATA\n    offset: 0\n"
    )
    model = _analyse(text)
    (tcp,) = model.parents
    assert (tcp.ports, tcp.match) == ((("dport", 102),), ())
    source = generate(model, profile()).file("p_mmt_plugin.c").text
    assert "if ((((uint64_t) p[2] << 8) | (uint64_t) p[3]) != 0x66u) {" in source
    assert "if (end - start <= header) {" in source
    assert "p += header;" not in source
    assert "    classify:\n      dport: 102\n" in dumps(model)
    assert "match" not in dumps(model)


@pytest.mark.parametrize("key", ["port", "sport", "dport"])
def test_a_port_classifies_only_under_tcp(key: str) -> None:
    text = (
        HEAD + f"parents:\n  - protocol: udp\n    classify:\n      {key}: 53\n"
        "  - protocol: nope\n    classify:\n      port: 1\n"
    )
    model = load(text, filename="plugin.yaml").model
    analysed, diagnostics = analyse(model, profile=profile())
    assert analysed is None
    got = [
        (d.code, d.location.line or 0, d.location.column or 0) for d in diagnostics if d.location
    ]
    # At the port's value; an unknown parent is that error only.
    assert got == [("model.classify-port", 9, 9 + len(key)), ("model.unknown-parent", 10, 15)]
    assert diagnostics[0].hint is not None and "protocol: tcp" in diagnostics[0].hint


def test_a_parent_offset_must_fit_the_sdk_field() -> None:
    text = (
        HEAD + "parents:\n  - protocol: udp\n    classify:\n"
        "      match:\n        - {offset: 0, length: 1, value: 1}\n      offset: 70000\n"
    )
    model = _analyse(text)
    from mmt_plugin.codegen import GenerationError

    with pytest.raises(GenerationError) as info:
        generate(model, profile())
    assert [d.code for d in info.value.diagnostics] == ["model.out-of-range"]


def test_the_profile_pin() -> None:
    assert profile_pin(HEAD + "sdk:\n  profile: '1.10.2'\n") == "1.10.2"
    assert profile_pin(HEAD) is None
    assert profile_pin("not: [yaml\n") is None
    assert profile_pin("- a\n") is None
    assert profile_pin(HEAD + "sdk: 3\n") is None
    assert profile_pin(HEAD + "sdk:\n  profile: 3\n") is None
    read = load(HEAD + "sdk:\n  profile: '1.10.2'\n", filename="plugin.yaml")
    assert read.sdk_profile == "1.10.2"
    assert read.model.offsets is Offsets.ABSOLUTE


def test_the_example_of_the_format_page_generates() -> None:
    page = (REPO / "docs" / "plugin-yaml.md").read_text(encoding="utf-8")
    example = page.split("```yaml\n", 1)[1].split("```\n", 1)[0]
    model = _analyse(example)
    assert [p.name for p in model.parents] == ["ethernet", "udp"]
    assert model.attribute("payload").length_value is None
    generation = generate(model, profile())
    assert "demo_classify_after_ethernet" in generation.file("demo_mmt_plugin.c").text
    assert [h.role for h in generation.hooks] == ["attribute_extraction", "register_parents"]
    # The page's error example is what the loader reports.
    error = page.split("```\nplugin.yaml:", 1)[1].split("\n", 1)[0]
    bad = HEAD.replace("id: 960", "id: '960'")
    with pytest.raises(PluginYamlError) as info:
        load(bad, filename="plugin.yaml")
    (first,) = info.value.diagnostics
    assert error == f"4:7: error: {first.message} [{first.code}]"
