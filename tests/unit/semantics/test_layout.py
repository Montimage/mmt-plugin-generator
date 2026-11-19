"""The computed layout against the corpus fixtures (bugs 2, 3 and 4).

For every corpus model the parser accepts, every attribute of every packet
fixture is checked against the analysed model: the fixture's offset, length
and bit position, the branch that makes a conditional attribute present or
absent, and (for integer types) the value. Offsets that depend on ``val()``
are evaluated over the fixture's bytes, as a generated plugin would.

The fixtures' values come from the protocol specifications and the corpus
rules, not from the Java tool (tests/corpus/README.md), so this is the
layout's ground truth.
"""

from __future__ import annotations

import dataclasses
import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from mmt_plugin.pdl import PdlSyntaxError, parse
from mmt_plugin.pdl import model as pdl
from mmt_plugin.semantics import SDK_CONFLICT_CODES, AnalysedModel, analyse
from mmt_plugin.semantics.types import INTEGER_TYPES

from .conftest import Packet, profile

ROOT = Path(__file__).parents[3]
CORPUS = ROOT / "tests" / "corpus"

#: Corpus models the parser rejects (tests/corpus/README.md, the invalid
#: examples): no layout to check.
UNPARSED = {
    "ethernet": "sizeof (mac_addr_t) is not a PDL type",
    "mongodb": 'offset = "POSITION_NOT_KNOWN" is not an expression',
}


def _validator() -> ModuleType:
    spec = importlib.util.spec_from_file_location("corpus_validate", CORPUS / "validate.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_VALIDATOR = _validator()
_INDEX: dict[str, Any] = _VALIDATOR.load_yaml(CORPUS / "index.yaml")


def _without_second_ar_pro(model: pdl.Model) -> pdl.Model:
    """arp without its duplicate ``ar_pro`` (bug 12): the fixtures give no
    value for it, and every other declaration keeps its meaning."""
    elements = []
    for el in model.attributes.elements:
        if isinstance(el, pdl.Conditional) and el.else_branch is not None:
            branch = tuple(
                e
                for e in el.else_branch
                if not (isinstance(e, pdl.Attribute) and e.alias.text == "ar_pro")
            )
            el = dataclasses.replace(el, else_branch=branch)
        elements.append(el)
    attributes = dataclasses.replace(model.attributes, elements=tuple(elements))
    return dataclasses.replace(model, attributes=attributes)


def _analysed(name: str) -> AnalysedModel:
    entry = next(m for m in _INDEX["models"] if m["name"] == name)
    path = CORPUS / entry["model"]
    model = parse(path.read_text(encoding="utf-8"), filename=str(path))
    if name == "arp":
        model = _without_second_ar_pro(model)
    # Most examples collide with the SDK (test_models.py); lay them out anyway.
    analysed, diagnostics = analyse(model, profile=profile(), allow_sdk_conflicts=True)
    blocking = [d.code for d in diagnostics if d.severity.value == "error"]
    assert set(blocking) <= SDK_CONFLICT_CODES, blocking
    assert analysed is not None
    return analysed


def _packets() -> list[tuple[str, Path]]:
    found = []
    for entry in _INDEX["models"]:
        if entry["name"] in UNPARSED:
            continue
        for stem in entry["packets"]:
            found.append(
                (entry["name"], CORPUS / "models" / entry["name"] / "packets" / f"{stem}.yaml")
            )
    return found


def test_the_unparsed_models_are_the_invalid_ones() -> None:
    for name in UNPARSED:
        entry = next(m for m in _INDEX["models"] if m["name"] == name)
        assert entry["valid"] is False
        with pytest.raises(PdlSyntaxError):
            parse((CORPUS / entry["model"]).read_text(encoding="utf-8"), filename=name)


@pytest.mark.parametrize(
    ("name", "path"), _packets(), ids=lambda v: str(v) if isinstance(v, str) else v.stem
)
def test_fixture_layout(name: str, path: Path) -> None:
    fixture = _VALIDATOR.load_yaml(path)
    model = _analysed(name)
    data = bytes.fromhex("".join(fixture["bytes"]))
    packet = Packet(model, data)
    assert model.protocol.id == fixture["expect"]["proto_id"]
    assert model.protocol.name == fixture["expect"]["protocol"]
    checked = 0
    for expected in fixture["expect"]["attributes"]:
        attribute = model.attribute(expected["name"])
        where = f"{fixture['id']} {expected['name']}"
        assert attribute.data_type.value == expected["type"], where
        status = expected.get("status", "value")
        if status == "absent":
            assert attribute.guards, where
            assert not packet.present(attribute), where
            continue
        if status == "undefined":
            assert attribute.is_hook, where  # radius and pdl_scopes no_off
            continue
        assert packet.present(attribute), where
        assert packet.offset(attribute) == expected["offset"], where
        assert packet.length(attribute) == expected["length"], where
        if "bit_offset" in expected:
            assert attribute.bitfield is not None, where
            assert attribute.bitfield.bit_offset == expected["bit_offset"], where
            assert attribute.bitfield.bit_width == expected["bit_width"], where
        else:
            assert attribute.bitfield is None, where
        if attribute.data_type in INTEGER_TYPES:
            assert packet.value(attribute) == expected["value"], where
        elif attribute.data_type is pdl.DataType.MMT_DATA_POINTER:
            assert expected["value"] == expected["offset"], where  # T2.4's convention
        if "scope" in expected:
            assert attribute.scope.value == f"SCOPE_{expected['scope'].upper()}", where
        checked += 1
    assert checked, f"{fixture['id']}: no attribute with a value"


def test_every_parsed_corpus_model_has_a_layout_test() -> None:
    tested = {name for name, _ in _packets()}
    assert tested == {m["name"] for m in _INDEX["models"]} - set(UNPARSED)
    assert len(tested) == 30


# --- the layouts the inventory gets wrong, spelled out ------------------------


def test_dns_header() -> None:
    # Bug 2: Java puts qdcount at 6; RFC 1035 at 4.
    dns = _analysed("dns")
    assert [(a.name, a.offset_value) for a in dns.attributes if a.bitfield is None] == [
        ("tid", 0),
        ("qdcount", 4),
        ("ancount", 6),
        ("nscount", 8),
        ("arcount", 10),
    ]
    bits = [
        (a.name, a.bitfield.bit_offset, a.bitfield.bit_width) for a in dns.attributes if a.bitfield
    ]
    assert bits == [
        ("qr", 0, 1),
        ("opcode", 1, 4),
        ("aa", 5, 1),
        ("tc", 6, 1),
        ("rd", 7, 1),
        ("ra", 8, 1),
        ("z", 9, 1),
        ("ans_auth", 10, 1),
        ("data_auth", 11, 1),
        ("rcode", 12, 4),
    ]
    assert dns.struct("dnshdr").size == 12


def test_tcp_struct() -> None:
    # Bug 2: Java puts seq at 14; the declared layout at 12. Two runs on one
    # line, each one 16-bit unit (bug 3).
    tcp = _analysed("tcp")
    offsets = {a.name: a.offset_value for a in tcp.attributes}
    assert offsets == {
        "source": 0, "dest": 2, "a": 4, "b": 6, "c": 6, "d": 6, "e": 8,
        "f": 10, "g": 10, "h": 10, "seq": 12, "ack_seq": 16, "flags": 20,
        "window": 22, "check": 24, "urg_ptr": 26,
    }  # fmt: skip
    struct = tcp.struct("tcphdr")
    assert struct.size == 28
    assert [(r.offset, r.width, r.fields) for r in struct.runs] == [
        (6, 2, ("b", "c", "d")),
        (10, 2, ("f", "g", "h")),
    ]


def test_pdl_alignment_offsets() -> None:
    # The index's note: a0 0, a1 1, s0 3, s1 4, c_if 6, c_else 6, cs0 8,
    # cs1 9, a2 10; stop, lit and t0 literal (3, 11, 0).
    model = _analysed("pdl_alignment")
    offsets = {a.name: (a.offset_value, a.aligned) for a in model.attributes}
    assert offsets == {
        "a0": (0, True), "a1": (1, True), "s0": (3, True), "s1": (4, True),
        "c_if": (6, True), "c_else": (6, True), "cs0": (8, True), "cs1": (9, True),
        "a2": (10, True), "stop": (3, False), "lit": (11, False), "t0": (0, False),
    }  # fmt: skip
