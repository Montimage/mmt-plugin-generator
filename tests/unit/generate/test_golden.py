"""Golden snapshots of the generated C for every corpus model (plan T1.5, Verify).

Every corpus model that ``analyse`` accepts (no SDK conflict allowed, as
``mmt-plugin generate`` runs it) has its header and source checked in under
``golden/<model>/``. Every other model's diagnostics are asserted. After a
deliberate change to the templates or the generator, regenerate with::

    MMT_UPDATE_GOLDEN=1 uv run pytest tests/unit/generate

and review the diff. ``test_compile.py`` compiles these files against the
real mmt-dpi headers.
"""

from __future__ import annotations

import os
import shutil

import pytest

from .helpers import GOLDEN, UPDATE_ENV, corpus_models, run_model

#: The error codes of the corpus models that are not generated. Most real
#: models take an id or a name that mmt-dpi 1.10.2 already has (T1.6
#: generates them with ``allow_sdk_conflicts``); ethernet and mongodb are
#: model bugs that the Java tool recovered from silently (T5.1).
REJECTED = {
    "abb": {"model.id-taken"},
    "arp": {"model.duplicate-name", "model.id-taken", "model.name-taken"},
    "cam": {"model.id-taken"},
    "cotp": {"model.id-taken", "model.name-taken"},
    "cpm": {"model.id-taken"},
    "dns": {"model.id-taken", "model.name-taken"},
    "ethernet": {"model.syntax.unknown-type"},
    "ip": {"model.id-taken", "model.name-taken"},
    "mongodb": {"model.syntax.invalid-expression"},
    "quic": {"model.id-taken", "model.name-taken"},
    "radius": {"model.id-taken", "model.name-taken"},
    "s7com": {"model.id-taken", "model.name-taken"},
    "tcp": {"model.id-taken", "model.name-taken"},
    "topo_ind_sch": {"model.id-taken"},
    "tpkt": {"model.id-taken", "model.name-taken"},
}

ACCEPTED = [m for m in corpus_models() if m not in REJECTED]


def test_the_corpus_splits_into_generated_and_rejected_models() -> None:
    assert set(REJECTED) <= set(corpus_models())
    assert len(ACCEPTED) == 16
    for name in corpus_models():
        assert (run_model(name).generation is not None) == (name in ACCEPTED), name


@pytest.mark.parametrize("name", sorted(REJECTED))
def test_a_rejected_model_reports_its_errors(name: str) -> None:
    outcome = run_model(name)
    assert outcome.generation is None
    errors = {d.code for d in outcome.diagnostics if d.severity.value == "error"}
    assert errors == REJECTED[name]
    assert all(d.location is not None for d in outcome.diagnostics)


@pytest.mark.parametrize("name", ACCEPTED)
def test_the_generated_c_matches_its_golden(name: str) -> None:
    generation = run_model(name).generation
    assert generation is not None
    directory = GOLDEN / name
    if os.environ.get(UPDATE_ENV):
        shutil.rmtree(directory, ignore_errors=True)
        directory.mkdir(parents=True)
        for f in generation.files:
            (directory / f.name).write_bytes(f.data)
    assert sorted(p.name for p in directory.iterdir()) == [f.name for f in generation.files]
    for f in generation.files:
        expected = (directory / f.name).read_bytes()
        assert f.data == expected, f"{name}/{f.name} differs: {UPDATE_ENV}=1 regenerates it"


def test_every_golden_belongs_to_a_generated_model() -> None:
    assert sorted(p.name for p in GOLDEN.iterdir() if p.is_dir()) == ACCEPTED
