"""Plan T3.2's check: every corpus PDL model imports, and both formats
generate identical C.

Every corpus model that the PDL v1 parser reads is imported with
``mmt-plugin import``; the two with PDL v1 syntax errors (ethernet, mongodb)
are exit 3 and write nothing. Then ``mmt-plugin generate`` runs on the PDL
v1 model and on its plugin.yaml: the same exit code and diagnostic codes,
and, when it generates, the same header and source byte for byte. Most
corpus models take an id or a name of the SDK, which ``generate`` refuses,
so code generation also runs with the SDK conflicts allowed (as the parity
test does): the same C from both formats for every model that analyses.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest

from mmt_plugin.cli import main
from mmt_plugin.codegen import GenerationError, generate
from mmt_plugin.pluginyaml import load
from mmt_plugin.semantics import analyse


def _load_corpus() -> Any:
    # The plugin.yaml tests' corpus helpers (tests/unit/pluginyaml/corpus.py).
    spec = importlib.util.spec_from_file_location(
        "import_corpus", Path(__file__).parents[1] / "pluginyaml" / "corpus.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


corpus = _load_corpus()
REPO: Path = corpus.REPO

PROFILE = ["--sdk-profile", "1.10.2"]


def _json(args: list[str], capsys: pytest.CaptureFixture[str]) -> tuple[int, dict[str, Any]]:
    code = main(["--json", *args])
    doc: dict[str, Any] = json.loads(capsys.readouterr().out)
    return code, doc


def _files(directory: Path) -> dict[str, bytes]:
    return {p.name: p.read_bytes() for p in sorted(directory.glob("*_mmt_plugin.[ch]"))}


def test_the_corpus_sets() -> None:
    assert sorted(set(corpus.corpus_models()) - set(corpus.readable())) == ["ethernet", "mongodb"]
    assert len(corpus.readable()) == 30


@pytest.mark.parametrize("name", ["ethernet", "mongodb"])
def test_a_model_with_pdl_syntax_errors_does_not_import(
    name: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output = str(tmp_path / "p.yaml")
    code, doc = _json(["import", str(REPO / corpus.source(name)), "-o", output], capsys)
    assert code == 3
    assert doc["error"]["code"].startswith("model.syntax.")
    assert not (tmp_path / "p.yaml").exists()


@pytest.mark.parametrize("name", corpus.readable())
def test_every_corpus_model_imports_and_both_formats_generate_the_same_c(
    name: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    pdl = REPO / corpus.source(name)
    yaml = tmp_path / "plugin.yaml"
    code, doc = _json(["import", str(pdl), "-o", str(yaml)], capsys)
    assert code == 0, doc["error"]
    assert all(d["severity"] == "warning" for d in doc["diagnostics"])
    assert doc["result"]["offsets"] == ("running" if name == "arp" else "absolute")

    results = []
    found: list[set[str]] = []
    for model, out in ((pdl, tmp_path / "from-pdl"), (yaml, tmp_path / "from-yaml")):
        code, doc = _json(["generate", str(model), "-o", str(out), *PROFILE], capsys)
        errors = sorted(d["code"] for d in doc["diagnostics"] if d["severity"] == "error")
        warnings = {d["code"] for d in doc["diagnostics"] if d["severity"] == "warning"}
        results.append((code, None if doc["error"] is None else doc["error"]["code"], errors))
        found.append(warnings)
    assert results[0] == results[1]
    # The warnings of PDL v1's running offset and omitted scope can go; no
    # other warning comes or goes.
    assert found[0] - found[1] <= {"model.default-scope", "model.branch-offset-mismatch"}
    assert found[1] <= found[0]
    assert _files(tmp_path / "from-pdl") == _files(tmp_path / "from-yaml")
    if results[0][0] == 0:
        assert len(_files(tmp_path / "from-yaml")) == 2

    # With the SDK conflicts allowed, every model that analyses generates.
    first, _ = analyse(corpus.parsed(name), profile=corpus.profile(), allow_sdk_conflicts=True)
    read = load(yaml.read_text(encoding="utf-8"), filename="plugin.yaml").model
    second, _ = analyse(read, profile=corpus.profile(), allow_sdk_conflicts=True)
    assert (first is None) == (second is None)
    if first is None or second is None:
        assert name == "arp"  # its duplicate name, which the Java tool accepted
        return
    try:
        before = generate(first, corpus.profile())
    except GenerationError as exc:
        with pytest.raises(GenerationError) as info:
            generate(second, corpus.profile())
        assert [d.code for d in info.value.diagnostics] == [d.code for d in exc.diagnostics]
        return
    after = generate(second, corpus.profile())
    assert [f.text for f in after.files] == [f.text for f in before.files]
