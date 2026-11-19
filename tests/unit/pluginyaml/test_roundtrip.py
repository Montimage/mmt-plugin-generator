"""The round trip of every corpus model through plugin.yaml (plan T3.1:
"a round trip for every corpus model").

Each model the PDL v1 parser reads is written as plugin.yaml, read back and
written again: the two texts are equal, so nothing is lost. With PDL v1's
running offsets the parsed model is enough; with absolute offsets (the
default) the analysis places each attribute. For every model that
analyses, both plugin.yaml forms analyse to the same layout and generate
the same C, byte for byte.
"""

from __future__ import annotations

import pytest

from mmt_plugin.codegen import GenerationError, generate
from mmt_plugin.pdl.model import Offsets
from mmt_plugin.pluginyaml import dumps, load
from mmt_plugin.semantics import AnalysedModel, analyse

from .corpus import analysable, analysed, corpus_models, parsed, profile, readable

MODES = [Offsets.ABSOLUTE, Offsets.RUNNING]


def test_the_corpus_sets() -> None:
    # ethernet and mongodb have PDL v1 syntax errors; arp's id and name are
    # the SDK's, and it defines a name twice.
    assert sorted(set(corpus_models()) - set(readable())) == ["ethernet", "mongodb"]
    assert sorted(set(readable()) - set(analysable())) == ["arp"]
    assert len(analysable()) == 29


@pytest.mark.parametrize("name", readable())
def test_running_offsets_round_trip_the_parsed_model(name: str) -> None:
    model = parsed(name)
    assert model is not None
    text = dumps(model, offsets=Offsets.RUNNING)
    again = load(text, filename="plugin.yaml").model
    assert again.offsets is Offsets.RUNNING
    assert dumps(again, offsets=Offsets.RUNNING) == text
    # The analysis finds the same problems, apart from the omitted scope,
    # which plugin.yaml defaults without a warning.
    _, before = analyse(model, profile=profile(), allow_sdk_conflicts=True)
    _, after = analyse(again, profile=profile(), allow_sdk_conflicts=True)
    assert [d.code for d in before if d.code != "model.default-scope"] == [d.code for d in after]


def _layout(model: AnalysedModel) -> list[tuple[object, ...]]:
    return [
        (a.key, a.kind, a.data_type, a.offset_value, a.length_value, a.scope, a.bitfield)
        for a in model.attributes
    ] + [
        (
            s.key,
            s.base_offset,
            s.size,
            s.c_size,
            tuple(r.helper_name for r in s.runs),
            *((f.key, f.offset, f.width, f.c_type, f.c_offset, f.bitfield) for f in s.fields),
        )
        for s in model.structs
    ]


@pytest.mark.parametrize("mode", MODES, ids=[m.value for m in MODES])
@pytest.mark.parametrize("name", analysable())
def test_both_offset_modes_keep_the_layout_and_the_c(name: str, mode: Offsets) -> None:
    first = analysed(name)
    assert first is not None
    text = dumps(first, offsets=mode, sdk_profile="1.10.2")
    read = load(text, filename="plugin.yaml")
    assert read.sdk_profile == "1.10.2"
    second, diagnostics = analyse(read.model, profile=profile(), allow_sdk_conflicts=True)
    assert second is not None, diagnostics
    assert dumps(second, offsets=mode, sdk_profile="1.10.2") == text
    assert _layout(second) == _layout(first)
    try:
        before = generate(first, profile())
    except GenerationError as exc:
        with pytest.raises(GenerationError) as info:
            generate(second, profile())
        assert [d.code for d in info.value.diagnostics] == [d.code for d in exc.diagnostics]
        return
    after = generate(second, profile())
    assert [f.text for f in after.files] == [f.text for f in before.files]
    assert after.hooks == before.hooks


def test_absolute_offsets_place_what_the_running_offset_placed() -> None:
    model = analysed("pdl_alignment")
    assert model is not None
    text = dumps(model)
    assert "offsets:" not in text  # absolute is the default
    # a1 sat at R = 1 + its declared 0; the struct at R = 3.
    assert "  - name: a1\n    type: MMT_U16_DATA\n    offset: 1\n" in text
    assert "  - struct: pdl_align_s\n    offset: 3\n" in text
    running = dumps(model, offsets=Offsets.RUNNING)
    assert running.startswith("schema: 1\n")
    assert "offsets: running\n" in running
    assert "  - name: a1\n    type: MMT_U16_DATA\n    offset: 0\n" in running


def test_an_absolute_model_cannot_be_written_with_running_offsets() -> None:
    model = analysed("pdl_alignment")
    assert model is not None
    absolute = load(dumps(model), filename="plugin.yaml").model
    with pytest.raises(ValueError, match="cannot be written with running offsets"):
        dumps(absolute, offsets=Offsets.RUNNING)
    source = parsed("pdl_alignment")
    assert source is not None
    with pytest.raises(ValueError, match="need its analysis"):
        dumps(source)
