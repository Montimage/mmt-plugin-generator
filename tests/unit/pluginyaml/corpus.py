"""The corpus models, parsed and analysed, for the plugin.yaml tests."""

from __future__ import annotations

from functools import cache
from pathlib import Path

from mmt_plugin.pdl import Model, PdlSyntaxError, parse
from mmt_plugin.sdk import Profile, get_bundled
from mmt_plugin.semantics import AnalysedModel, analyse

REPO = Path(__file__).resolve().parents[3]
CORPUS = REPO / "tests" / "corpus" / "models"


def profile() -> Profile:
    found = get_bundled("1.10.2")
    assert found is not None
    return found


def corpus_models() -> list[str]:
    """Every corpus model, by directory name."""
    return sorted(d.name for d in CORPUS.iterdir() if (d / "model.pdl").is_file())


def source(name: str) -> str:
    return f"tests/corpus/models/{name}/model.pdl"


@cache
def parsed(name: str) -> Model | None:
    """The corpus model ``name``, or ``None`` when it is not PDL v1."""
    try:
        return parse((REPO / source(name)).read_text(encoding="utf-8"), filename=source(name))
    except PdlSyntaxError:
        return None


@cache
def analysed(name: str) -> AnalysedModel | None:
    """The corpus model ``name`` analysed (SDK conflicts allowed, as for the
    tcp and ip examples), or ``None`` when it does not analyse."""
    model = parsed(name)
    if model is None:
        return None
    return analyse(model, profile=profile(), allow_sdk_conflicts=True)[0]


def readable() -> list[str]:
    """The corpus models the PDL v1 parser reads."""
    return [n for n in corpus_models() if parsed(n) is not None]


def analysable() -> list[str]:
    """The corpus models that analyse."""
    return [n for n in corpus_models() if analysed(n) is not None]
