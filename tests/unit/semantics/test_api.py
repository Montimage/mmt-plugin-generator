"""The public API: ``analyse(model, profile=...)`` and the analysed model."""

from __future__ import annotations

import builtins
import dataclasses
import os
from pathlib import Path
from typing import Any

import pytest

from mmt_plugin.diagnostics import Severity
from mmt_plugin.pdl.model import Encoding
from mmt_plugin.semantics import analyse
from mmt_plugin.semantics.model import (
    ByteOrder,
    FieldKind,
    SetNextOffset,
    SetNextProto,
)

from .conftest import build, classify, ok, parse_model, profile, run, u8

ROOT = Path(__file__).parents[3]


def test_analysis_opens_and_writes_nothing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    model = parse_model(build(u8("a", "0") + u8("b", "val(a)")))
    sdk = profile()  # loaded before open() is refused

    def refuse(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError(f"the analysis opened a file: {args!r}")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(builtins, "open", refuse)
    monkeypatch.setattr(os, "open", refuse)
    analysed, _ = analyse(model, profile=sdk)
    assert analysed is not None
    assert os.listdir(tmp_path) == []


def test_the_analysed_model_is_frozen_hashable_and_deterministic() -> None:
    text = (ROOT / "tests/corpus/models/pdl_conditionals/model.pdl").read_text(encoding="utf-8")
    first, d1 = analyse(parse_model(text), profile=profile())
    second, d2 = analyse(parse_model(text), profile=profile())
    assert first is not None and first == second and d1 == d2
    assert hash(first) == hash(second)
    with pytest.raises(dataclasses.FrozenInstanceError):
        first.attributes[0].name = "x"  # type: ignore[misc]


def test_diagnostics_are_sorted_and_warnings_keep_the_model() -> None:
    text = build(
        '\t\tattribute { alias="b" data_type="MMT_U8_DATA" data_len="1" offset="0" }\n'
        '\t\tattribute { alias="a" data_type="MMT_U8_DATA" data_len="1" offset="1" }\n',
        properties='label = "p"\n\t\tid = "900"',
    )
    analysed, diagnostics = run(text)
    assert analysed is not None
    assert [(d.code, d.location and d.location.line) for d in diagnostics] == [
        ("model.id-outside-reserved-range", 4),
        ("model.default-scope", 7),
        ("model.default-scope", 8),
    ]
    assert {d.severity for d in diagnostics} == {Severity.WARNING}


def test_lookups_are_case_insensitive() -> None:
    model = ok("\t\tstruct Hdr {\n\t\t\tuint8_t Kind;\n\t\t}\n" + u8("Next", "val(KIND)"))
    assert model.attribute("kind").name == "Kind"
    assert model.attribute("NEXT").key == "next"
    assert model.struct("HDR").name == "Hdr"
    with pytest.raises(KeyError):
        model.attribute("nothing")
    with pytest.raises(KeyError):
        model.struct("nothing")


@pytest.mark.parametrize(
    ("encoding", "value", "order"),
    [
        ('encoding = "network"', Encoding.NETWORK, ByteOrder.BIG),
        ('encoding = "host"', Encoding.HOST, ByteOrder.LITTLE),
        ('encoding = "little"', Encoding.HOST, ByteOrder.LITTLE),
        ('encoding = "ASCII"', Encoding.ASCII, ByteOrder.UNSPECIFIED),
        ('encoding = "UNICODE"', Encoding.UNICODE, ByteOrder.UNSPECIFIED),
        ("", None, ByteOrder.UNSPECIFIED),
    ],
)
def test_properties_defaults_and_byte_order(
    encoding: str, value: Encoding | None, order: ByteOrder
) -> None:
    model = ok(build(u8("a", "0"), properties=f'label = "Pq"\n\t\tid = "960"\n\t\t{encoding}'))
    p = model.protocol
    assert (p.label, p.name, p.id, p.encoding, p.byte_order) == ("Pq", "PQ", 960, value, order)
    assert not (p.context or p.session_context or p.session or p.encapsulation)


def test_classifynext_is_resolved() -> None:
    model = ok(
        build(
            u8("t", "0"),
            defines="\tdefine A = 951\n\tdefine B = A\n\tdefine TCP = PROTO_TCP\n",
            classify=classify(
                "\t\t\tcase 1: nextencaps = B nextoffset = val(t) * 4 break\n"
                "\t\t\tcase 0x02: nextencaps = PROTO_UDP\n"
                "\t\t\tcase A: nextencaps = TCP nextoffset = sizeof(short) break"
            ),
            properties='label = "p"\n\t\tid = "960"\n\t\tencapsulation = "true"',
        )
    )
    assert [(d.name, d.value, d.alias_of) for d in model.defines] == [
        ("A", 951, None),
        ("B", 951, "A"),
        ("TCP", 354, "PROTO_TCP"),
    ]
    switch = model.classify_next
    assert switch is not None and switch.subject.value == 1
    assert [(c.label, c.alias_of, c.has_break) for c in switch.cases] == [
        (1, None, True),
        (2, None, False),
        (951, "A", True),
    ]
    first, second, third = (c.statements for c in switch.cases)
    assert isinstance(first[0], SetNextProto) and (first[0].proto.id, first[0].proto.alias_of) == (
        951,
        "B",
    )
    assert isinstance(first[1], SetNextOffset) and first[1].offset.value is None
    assert isinstance(second[0], SetNextProto) and second[0].proto.id == 376
    assert isinstance(third[1], SetNextOffset) and third[1].offset.value == 2
    assert switch.default is not None and switch.default.has_break


def test_the_sdk_facts_come_from_the_profile() -> None:
    model = parse_model(build(u8("abcdef", "0"), properties='label = "tpkt"\n\t\tid = "637"'))
    sdk = profile()
    _, diagnostics = analyse(model, profile=sdk)
    assert [d.code for d in diagnostics] == ["model.name-taken", "model.id-taken"]
    # A profile that records no ids and a shorter Max_Alias_Len.
    constants = tuple(
        dataclasses.replace(c, value=5) if c.name == "Max_Alias_Len" else c
        for c in sdk.constants
        if c.group != "protocol_id"
    )
    other = dataclasses.replace(
        sdk, constants=constants, parents=dataclasses.replace(sdk.parents, ids=())
    )
    _, diagnostics = analyse(model, profile=other)
    assert [d.code for d in diagnostics] == [
        "model.id-outside-reserved-range",
        "model.alias-too-long",
    ]


def test_the_c_layout_of_every_field_kind() -> None:
    text = (ROOT / "tests/corpus/models/pdl_struct_types/model.pdl").read_text(encoding="utf-8")
    model, _ = analyse(parse_model(text), profile=profile())
    assert model is not None
    hdr = model.struct("pdl_types_hdr")
    by_name = {f.name: (f.kind, f.offset, f.width, f.c_type, f.c_offset) for f in hdr.fields}
    # Wire offsets are packed; the C ones align uint32_t fields to 4.
    assert by_name["f_uint"] == (FieldKind.INTEGER, 19, 4, "uint32_t", 20)
    assert by_name["f_ptr"] == (FieldKind.POINTER, 28, 4, "uint32_t", 32)
    assert by_name["f_mac"] == (FieldKind.MMT, 32, 6, "uint8_t[6]", 36)
    assert by_name["f_inner"] == (FieldKind.STRUCT, 42, 2, "struct pdl_inner", 46)
    assert (hdr.size, hdr.c_size, hdr.c_align, hdr.needs_packing) == (45, 52, 4, True)
    assert hdr.c_padding == hdr.c_size - sum(f.width for f in hdr.fields)
    assert hdr.base_offset == 2 and hdr.aligned  # after pdl_inner's 2 bytes
