"""Shared helpers of the generate tests: the corpus models, the generated
set of one model, and the ``src/<label>_impl.c`` the compile check needs
(the scaffold)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from mmt_plugin.codegen import Generation, GenerationError, generate, scaffold
from mmt_plugin.diagnostics import Diagnostic
from mmt_plugin.pdl import PdlSyntaxError, parse
from mmt_plugin.sdk import Profile, get_bundled
from mmt_plugin.semantics import analyse

REPO = Path(__file__).resolve().parents[3]
CORPUS = REPO / "tests" / "corpus" / "models"
GOLDEN = Path(__file__).with_name("golden")

#: Regenerate the goldens: ``MMT_UPDATE_GOLDEN=1 uv run pytest tests/unit/generate``.
UPDATE_ENV = "MMT_UPDATE_GOLDEN"


#: The profile of the goldens.
GOLDEN_PROFILE = "1.10.2"


def profile(version: str = GOLDEN_PROFILE) -> Profile:
    found = get_bundled(version)
    assert found is not None, f"no bundled SDK profile {version}"
    return found


def corpus_models() -> list[str]:
    """Every corpus model, by directory name."""
    return sorted(d.name for d in CORPUS.iterdir() if (d / "model.pdl").is_file())


@dataclass(frozen=True)
class Outcome:
    """What the pipeline does with one corpus model: a generated set, or the
    diagnostics that stop it."""

    generation: Generation | None
    diagnostics: tuple[Diagnostic, ...]


def model_path(name: str) -> Path:
    return CORPUS / name / "model.pdl"


def source_text(name: str) -> str:
    return model_path(name).read_text(encoding="utf-8")


@cache
def run_model(name: str, version: str = GOLDEN_PROFILE) -> Outcome:
    """Parse, analyse (no SDK conflicts allowed, as ``generate`` does) and
    generate one corpus model with the SDK profile ``version``; a
    ``GenerationError`` adds its diagnostics."""
    filename = f"tests/corpus/models/{name}/model.pdl"
    try:
        model = parse(source_text(name), filename=filename)
    except PdlSyntaxError as exc:
        return Outcome(None, exc.diagnostics)
    analysed, diagnostics = analyse(model, profile=profile(version))
    if analysed is None:
        return Outcome(None, tuple(diagnostics))
    try:
        generation = generate(analysed, profile(version))
    except GenerationError as exc:
        return Outcome(None, (*diagnostics, *exc.diagnostics))
    return Outcome(generation, tuple(diagnostics))


def generate_text(text: str, *, filename: str = "t.pdl") -> Generation:
    """Generate a model given as PDL text; it must analyse without errors."""
    analysed, diagnostics = analyse(parse(text, filename=filename), profile=profile())
    assert analysed is not None, [d.message for d in diagnostics]
    return generate(analysed, profile())


def impl_stub(generation: Generation) -> str:
    """The scaffold ``src/<label>_impl.c`` of ``generation``, which defines
    every hook of the header."""
    return scaffold(generation, profile(generation_profile(generation))).text


def generation_profile(generation: Generation) -> str:
    """The SDK profile version a generation was made with (its header says)."""
    header = generation.file(generation.header).text
    found = re.search(r"\(SDK profile ([0-9.]+)\)", header)
    assert found is not None, generation.header
    return found.group(1)
