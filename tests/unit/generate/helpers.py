"""Shared helpers of the generate tests: the corpus models, the generated
set of one model, and the stub ``src/<label>_impl.c`` the compile check
needs."""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache
from pathlib import Path

from mmt_plugin.codegen import Generation, GenerationError, Hook, generate
from mmt_plugin.diagnostics import Diagnostic
from mmt_plugin.pdl import PdlSyntaxError, parse
from mmt_plugin.sdk import Profile, get_bundled
from mmt_plugin.semantics import analyse

REPO = Path(__file__).resolve().parents[3]
CORPUS = REPO / "tests" / "corpus" / "models"
GOLDEN = Path(__file__).with_name("golden")

#: Regenerate the goldens: ``MMT_UPDATE_GOLDEN=1 uv run pytest tests/unit/generate``.
UPDATE_ENV = "MMT_UPDATE_GOLDEN"


def profile() -> Profile:
    found = get_bundled("1.10.2")
    assert found is not None
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
def run_model(name: str) -> Outcome:
    """Parse, analyse (no SDK conflicts allowed, as ``generate`` does) and
    generate one corpus model; a ``GenerationError`` adds its diagnostics."""
    filename = f"tests/corpus/models/{name}/model.pdl"
    try:
        model = parse(source_text(name), filename=filename)
    except PdlSyntaxError as exc:
        return Outcome(None, exc.diagnostics)
    analysed, diagnostics = analyse(model, profile=profile())
    if analysed is None:
        return Outcome(None, tuple(diagnostics))
    try:
        generation = generate(analysed, profile())
    except GenerationError as exc:
        return Outcome(None, (*diagnostics, *exc.diagnostics))
    return Outcome(generation, tuple(diagnostics))


def generate_text(text: str, *, filename: str = "t.pdl") -> Generation:
    """Generate a model given as PDL text; it must analyse without errors."""
    analysed, diagnostics = analyse(parse(text, filename=filename), profile=profile())
    assert analysed is not None, [d.message for d in diagnostics]
    return generate(analysed, profile())


_RETURNS = {"int": "0", "bool": "false", "mmt_classify_verdict_t": "MMT_CLASSIFY_SKIP"}


def stub(hook: Hook) -> str:
    """A definition of ``hook`` that compiles with ``-Wall -Wextra -Werror``."""
    lines = [hook.declaration, "{"]
    lines += [f"    (void) {p.name};" for p in hook.params]
    if hook.returns.endswith("*"):
        lines.append("    return NULL;")
    elif hook.returns != "void":
        lines.append(f"    return {_RETURNS[hook.returns]};")
    lines.append("}")
    return "\n".join(lines)


def impl_stub(generation: Generation) -> str:
    """A stub ``src/<label>_impl.c`` defining every hook of the header."""
    header = next(f.name for f in generation.files if f.name.endswith(".h"))
    parts = [
        f"/* Test stub: the hooks of {header}. */",
        "#include <stdbool.h>",
        "#include <stddef.h>",
        "",
        f'#include "{header}"',
    ]
    parts += ["", *(stub(h) + "\n" for h in generation.hooks)]
    return "\n".join(parts).rstrip("\n") + "\n"
