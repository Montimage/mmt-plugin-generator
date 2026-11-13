"""Parse every model of ``plugins/`` and ``tests/corpus/models/``.

What the Java tool did with each ``plugins/*_plugin`` model comes from
``legacy/reference-output/`` (the ``MANIFEST`` status and the stderr lines
``line L:C ...``, with 0-based columns):

- a model it parsed without a syntax error parses here;
- ``ip_plugin``, which it rejected only because ``id`` was a reserved word,
  parses here (keywords are contextual);
- for every other model it rejected, we report a diagnostic at each place it
  did, with the same line and the column one higher (ours are 1-based).

The corpus models are checked against ``tests/corpus/index.yaml``.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from mmt_plugin.pdl import PdlSyntaxError, parse
from mmt_plugin.pdl.model import Encoding

ROOT = Path(__file__).parents[3]
PLUGINS = sorted(p.name for p in (ROOT / "plugins").glob("*_plugin"))
REFERENCE = ROOT / "legacy" / "reference-output"
CORPUS = ROOT / "tests" / "corpus"

#: Models the Java grammar rejected only for a keyword used as a name.
KEYWORD_LIMITED = {"ip_plugin": "no viable alternative at input 'id'"}

_JAVA_ERROR = re.compile(r"^line (\d+):(\d+) (.*)$")


def _java_status(model: str) -> str:
    for line in (REFERENCE / "MANIFEST").read_text(encoding="utf-8").splitlines():
        fields = line.split()
        if fields and fields[0] == model:
            return fields[1]
    raise AssertionError(f"{model} is not in the reference MANIFEST")


def _java_errors(model: str) -> list[tuple[int, int, str]]:
    stderr = (REFERENCE / f"{model}.stderr").read_text(encoding="utf-8")
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


def test_the_reference_covers_every_plugin_model() -> None:
    assert len(PLUGINS) == 16
    statuses = {name: _java_status(name) for name in PLUGINS}
    assert {s for s in statuses.values()} <= {"ok", "parse-errors", "no-output"}


@pytest.mark.parametrize("name", PLUGINS)
def test_plugin_model(name: str) -> None:
    text = (ROOT / "plugins" / name).read_text(encoding="utf-8")
    filename = f"plugins/{name}"
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
        origin = ROOT / entry["origin"]
        assert origin.read_text(encoding="utf-8") == text
        name = origin.name
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
