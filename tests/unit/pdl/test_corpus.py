"""Parse every model of ``tests/corpus/models/``.

The 16 example models (``kind: example`` in ``tests/corpus/index.yaml``) are
the models the Java tool shipped as ``plugins/<name>_plugin`` (removed by
#78), byte for byte: the corpus validator checks each one's sha256. What the
Java tool did with each comes from the record of its last run, frozen in
``tests/java-output/`` when it was removed (T5.4, #31): the ``MANIFEST``
status of ``<name>_plugin`` and the stderr lines ``line L:C ...``, with
0-based columns. ``MANIFEST`` holds the sha256 of every model's stderr; the
non-empty ones are kept next to it.

- a model it parsed without a syntax error parses here;
- ``ip_plugin``, which it rejected only because ``id`` was a reserved word,
  parses here (keywords are contextual);
- for every other model it rejected, we report a diagnostic at each place it
  did, with the same line and the column one higher (ours are 1-based).

The corpus models are checked against ``tests/corpus/index.yaml``, and the
validator's example checks against mutated copies of the corpus.
"""

from __future__ import annotations

import hashlib
import importlib.util
import re
import shutil
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from mmt_plugin.pdl import PdlSyntaxError, parse
from mmt_plugin.pdl.model import Encoding

ROOT = Path(__file__).parents[3]
REFERENCE = ROOT / "tests" / "java-output"
CORPUS = ROOT / "tests" / "corpus"

#: Models the Java grammar rejected only for a keyword used as a name.
KEYWORD_LIMITED = {"ip_plugin": "no viable alternative at input 'id'"}

_JAVA_ERROR = re.compile(r"^line (\d+):(\d+) (.*)$")


def _manifest_line(model: str) -> list[str]:
    for line in (REFERENCE / "MANIFEST").read_text(encoding="utf-8").splitlines():
        fields = line.split()
        if fields and fields[0] == model:
            return fields
    raise AssertionError(f"{model} is not in the reference MANIFEST")


def _java_status(model: str) -> str:
    return _manifest_line(model)[1]


def _java_stderr(model: str) -> str:
    hashes = dict(f.split("=", 1) for f in _manifest_line(model)[2:])
    expected = hashes[f"{model}.stderr"]
    if expected == hashlib.sha256(b"").hexdigest():
        assert not (REFERENCE / f"{model}.stderr").exists(), model
        return ""
    data = (REFERENCE / f"{model}.stderr").read_bytes()
    assert hashlib.sha256(data).hexdigest() == expected, model
    return data.decode("utf-8")


def _java_errors(model: str) -> list[tuple[int, int, str]]:
    stderr = _java_stderr(model)
    found = []
    for line in stderr.splitlines():
        match = _JAVA_ERROR.match(line)
        if match:
            found.append((int(match[1]), int(match[2]), match[3]))
    return found


def _load_validator() -> ModuleType:
    spec = importlib.util.spec_from_file_location("corpus_validate", CORPUS / "validate.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _corpus_models() -> list[dict[str, Any]]:
    index = _load_validator().load_yaml(CORPUS / "index.yaml")
    models: list[dict[str, Any]] = index["models"]
    return models


#: The example models, by the name the Java tool's MANIFEST gives them.
EXAMPLES = sorted(f"{e['name']}_plugin" for e in _corpus_models() if e["kind"] == "example")


def _example_path(model: str) -> Path:
    return CORPUS / "models" / model.removesuffix("_plugin") / "model.pdl"


def test_the_reference_covers_every_example_model() -> None:
    assert len(EXAMPLES) == 16
    statuses = {name: _java_status(name) for name in EXAMPLES}
    assert {s for s in statuses.values()} <= {"ok", "parse-errors", "no-output"}


@pytest.mark.parametrize("name", EXAMPLES)
def test_example_model(name: str) -> None:
    path = _example_path(name)
    text = path.read_text(encoding="utf-8")
    filename = str(path.relative_to(ROOT))
    status, java_errors = _java_status(name), _java_errors(name)
    if status == "ok" or name in KEYWORD_LIMITED:
        if name in KEYWORD_LIMITED:
            assert [e[2] for e in java_errors] == [KEYWORD_LIMITED[name]]
        else:
            assert java_errors == []
        model = parse(text, filename=filename)
        assert model.span.file == filename
        return
    assert java_errors, f"{name}: Java rejected it without a located error"
    with pytest.raises(PdlSyntaxError) as caught:
        parse(text, filename=filename)
    ours = [(d.location.line, d.location.column) for d in caught.value.diagnostics if d.location]
    assert ours == [(line, column + 1) for line, column, _ in java_errors]


@pytest.mark.parametrize("entry", _corpus_models(), ids=lambda e: str(e["name"]))
def test_corpus_model(entry: dict[str, Any]) -> None:
    path = CORPUS / entry["model"]
    text = path.read_text(encoding="utf-8")
    if entry["kind"] == "example":
        name = f"{entry['name']}_plugin"
        rejected = _java_status(name) != "ok" and name not in KEYWORD_LIMITED
    else:
        # Targeted models: the Java tool parsed them, except the keyword one.
        assert entry["java"] in ("parses", "no-output")
        rejected = False
    if rejected:
        assert entry["valid"] is False
        with pytest.raises(PdlSyntaxError):
            parse(text, filename=str(path))
        return
    model = parse(text, filename=str(path))
    encoding = model.properties.encoding
    spelled = "default" if encoding is None else encoding.value.value.lower()
    assert spelled == entry["encoding"]
    if encoding is not None and encoding.value is Encoding.HOST:
        assert encoding.spelling in ("host", "little")


def _corpus_copy(tmp_path: Path) -> Path:
    """A copy of the corpus at ``tmp_path/tests/corpus``, next to a copy of
    the Java tool's ``MANIFEST`` (the validator reads it from there)."""
    corpus = tmp_path / "tests" / "corpus"
    shutil.copytree(CORPUS, corpus, ignore=shutil.ignore_patterns("__pycache__"))
    (tmp_path / "tests" / "java-output").mkdir()
    shutil.copy2(REFERENCE / "MANIFEST", tmp_path / "tests" / "java-output" / "MANIFEST")
    return corpus


def _errors(corpus: Path) -> list[str]:
    result = _load_validator().validate(corpus)
    report = result if not isinstance(result, tuple) else result[0]
    errors: list[str] = report.errors
    return errors


def test_the_validator_accepts_an_unchanged_copy(tmp_path: Path) -> None:
    assert _errors(_corpus_copy(tmp_path)) == []


def test_the_validator_rejects_an_example_model_that_changed(tmp_path: Path) -> None:
    corpus = _corpus_copy(tmp_path)
    model = corpus / "models" / "tpkt" / "model.pdl"
    model.write_bytes(model.read_bytes() + b"\n")
    errors = _errors(corpus)
    assert len(errors) == 1, errors
    assert "model tpkt" in errors[0] and "the model the Java tool ran on" in errors[0]


def test_the_validator_rejects_a_targeted_model_with_a_sha256(tmp_path: Path) -> None:
    corpus = _corpus_copy(tmp_path)
    index = corpus / "index.yaml"
    text = index.read_text(encoding="utf-8")
    entry = '    kind: "targeted"\n'
    assert entry in text
    index.write_text(text.replace(entry, entry + f'    sha256: "{"0" * 64}"\n', 1))
    assert any("a targeted model has no sha256" in e for e in _errors(corpus))


@pytest.mark.parametrize(
    ("edit", "expected"),
    [
        (
            lambda lines: [line for line in lines if not line.startswith("tpkt_plugin ")],
            "example tpkt is not a model of tests/java-output/MANIFEST (tpkt_plugin)",
        ),
        (
            lambda lines: [*lines, "http2_plugin ok http2_plugin.exit=0"],
            "the Java tool's model http2_plugin has no example entry",
        ),
    ],
    ids=["missing", "extra"],
)
def test_the_validator_checks_the_examples_against_the_manifest(
    tmp_path: Path, edit: Any, expected: str
) -> None:
    corpus = _corpus_copy(tmp_path)
    manifest = tmp_path / "tests" / "java-output" / "MANIFEST"
    lines = manifest.read_text(encoding="utf-8").splitlines()
    manifest.write_text("\n".join(edit(lines)) + "\n", encoding="utf-8")
    errors = _errors(corpus)
    assert len(errors) == 1, errors
    assert errors[0].endswith(expected), errors
