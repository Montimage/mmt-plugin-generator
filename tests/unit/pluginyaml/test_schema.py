"""The JSON Schema of plugin.yaml (``schemas/model/v1/plugin.json``) and the
validator that enforces it: a valid draft 2020-12 schema, shipped in the
package; every corpus model's plugin.yaml follows it; ``jsonschema`` and the
package's validator agree on valid and invalid documents; each error is a
``model.schema`` diagnostic at its node's line and column."""

from __future__ import annotations

import json
from importlib import resources
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from mmt_plugin.pdl.model import Offsets
from mmt_plugin.pluginyaml import SCHEMA_PATH, PluginYamlError, load, load_schema, to_document
from mmt_plugin.pluginyaml.nodes import parse, to_data
from mmt_plugin.pluginyaml.schema import KEYWORDS, validate

from .corpus import analysable, analysed, parsed, readable

VALIDATOR = Draft202012Validator(load_schema())

MINIMAL = "schema: 1\nprotocol:\n  label: p\n  id: 960\n"


def test_the_schema_is_a_draft_2020_12_schema_shipped_in_the_package() -> None:
    schema = load_schema()
    Draft202012Validator.check_schema(schema)
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["title"] == "mmt-plugin plugin.yaml, schema 1"
    shipped = resources.files("mmt_plugin").joinpath(SCHEMA_PATH).read_text("utf-8")
    assert json.loads(shipped) == schema


def _keywords(node: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(node, dict):
        for key, value in node.items():
            if key in ("properties", "$defs"):
                for sub in value.values():
                    found |= _keywords(sub)
                found.add(key)
            else:
                found.add(key)
                found |= _keywords(value)
    elif isinstance(node, list):
        for item in node:
            found |= _keywords(item)
    return found


def test_the_schema_uses_only_the_keywords_the_validator_checks() -> None:
    annotations = {"$schema", "$id", "$defs", "title", "description", "default"}
    assert _keywords(load_schema()) - annotations <= KEYWORDS


def test_the_minimal_model_is_valid_and_loads() -> None:
    assert VALIDATOR.is_valid(to_data(parse(MINIMAL)))
    model = load(MINIMAL, filename="plugin.yaml").model
    assert model.properties.label.text == "p"
    assert model.attributes.elements == () and model.offsets is Offsets.ABSOLUTE


@pytest.mark.parametrize("name", readable())
def test_every_corpus_model_follows_the_schema(name: str) -> None:
    documents = []
    model = parsed(name)
    assert model is not None
    documents.append(to_document(model, offsets=Offsets.RUNNING))
    full = analysed(name)
    if full is not None:
        documents.append(to_document(full, sdk_profile="1.10.2"))
    for document in documents:
        VALIDATOR.validate(document)


def test_every_construct_is_in_the_corpus_documents() -> None:
    # The corpus exercises every key of the schema except parents, which
    # PDL v1 has no syntax for (tested in test_load.py).
    seen: set[str] = set()

    def keys(value: Any) -> None:
        if isinstance(value, dict):
            seen.update(value)
            for v in value.values():
                keys(v)
        elif isinstance(value, list):
            for v in value:
                keys(v)

    for name in analysable():
        full = analysed(name)
        assert full is not None
        keys(to_document(full, sdk_profile="1.10.2"))
        keys(to_document(full.source, offsets=Offsets.RUNNING))
    expected = {
        "schema", "protocol", "sdk", "offsets", "defines", "attributes", "classify_next",
        "label", "id", "context", "session_context", "session", "encapsulation", "encoding",
        "profile", "name", "type", "offset", "length", "scope", "struct", "fields", "bits",
        "width", "if", "then", "else", "switch", "cases", "default", "case", "next",
        "fallthrough",
    }  # fmt: skip
    assert expected <= seen


#: Invalid documents: the error's line and column, and part of its message.
INVALID = [
    ("", 1, 1, "model.yaml-syntax", "empty"),
    ("- 1\n", 1, 1, "model.schema", "expected a mapping"),
    ("schema: 2\nprotocol: {label: p, id: 960}\n", 1, 9, "model.schema", "must be 1"),
    ("protocol: {label: p, id: 960}\n", 1, 1, "model.schema", "missing key `schema`"),
    (MINIMAL + "attribute: []\n", 5, 1, "model.schema", "unknown key `attribute`"),
    (MINIMAL + "  ID: 3\n", 5, 3, "model.schema", "did you mean `id`?"),
    (MINIMAL.replace("id: 960", "id: 0"), 4, 7, "model.schema", "below 1"),
    (MINIMAL.replace("id: 960", "id: true"), 4, 7, "model.schema", "found a boolean"),
    (MINIMAL.replace("label: p", "label: 1p"), 3, 10, "model.schema", "`1p` is not valid"),
    (MINIMAL + "  encoding: Network\n", 5, 13, "model.schema", "did you mean `network`?"),
    (MINIMAL + "sdk:\n  prefix: /opt/mmt\n", 6, 3, "model.schema", "unknown key `prefix`"),
    (MINIMAL + "sdk:\n  profile: '1.x'\n", 6, 12, "model.schema", "`1.x` is not valid"),
    (MINIMAL + "cc: gcc\n", 5, 1, "model.schema", "unknown key `cc`"),
    (MINIMAL + "offsets: relative\n", 5, 10, "model.schema", "not one of the allowed"),
    (
        MINIMAL + "attributes:\n  - name: a\n    type: MMT_U8\n",
        7,
        11,
        "model.schema",
        "attributes[0].type",
    ),
    (MINIMAL + "attributes:\n  - name: a\n", 6, 5, "model.schema", "missing key `type`"),
    (
        MINIMAL + "attributes:\n  - name: a\n    type: MMT_U8_DATA\n    length: 0\n",
        8,
        13,
        "model.schema",
        "below 1",
    ),
    (
        MINIMAL + "attributes:\n  - name: a\n    type: MMT_U8_DATA\n    offset: ''\n",
        8,
        13,
        "model.schema",
        "must not be empty",
    ),
    (MINIMAL + "attributes:\n  - struct: s\n", 6, 5, "model.schema", "missing key `fields`"),
    (
        MINIMAL + "attributes:\n  - struct: s\n    fields: []\n",
        7,
        13,
        "model.schema",
        "at least 1",
    ),
    (
        MINIMAL
        + "attributes:\n  - struct: s\n    fields:\n      - name: f\n        type: float\n",
        9,
        15,
        "model.schema",
        "`float` is not valid",
    ),
    (
        MINIMAL + "attributes:\n  - struct: s\n    fields:\n      - type: uint8_t\n"
        "        bits:\n          - name: f\n",
        10,
        13,
        "model.schema",
        "missing key `width`",
    ),
    (MINIMAL + "attributes:\n  - if: 1\n", 6, 5, "model.schema", "missing key `then`"),
    (MINIMAL + "attributes:\n  - 3\n", 6, 5, "model.schema", "expected a mapping"),
    (MINIMAL + "defines:\n  1X: 3\n", 6, 3, "model.schema", "`1X` is not valid"),
    (MINIMAL + "defines:\n  X: a b\n", 6, 6, "model.schema", "`a b` is not valid"),
    (MINIMAL + "parents:\n  - weight: 1\n", 6, 5, "model.schema", "missing key `protocol`"),
    (
        MINIMAL + "parents:\n  - protocol: udp\n    weight: 101\n",
        7,
        13,
        "model.schema",
        "above 100",
    ),
    (
        MINIMAL + "parents:\n  - protocol: udp\n    classify:\n      offset: 8\n",
        8,
        7,
        "model.schema",
        "missing key `match`",
    ),
    (
        MINIMAL + "parents:\n  - protocol: udp\n    classify:\n      offset: 8\n"
        "      match:\n        - {offset: 2, length: 9, value: 1}\n",
        10,
        31,
        "model.schema",
        "above 8",
    ),
    (MINIMAL + "classify_next:\n  cases: []\n", 6, 3, "model.schema", "missing key `switch`"),
    (
        MINIMAL + "classify_next:\n  switch: 1\n  cases:\n    - next: 3\n",
        8,
        7,
        "model.schema",
        "missing key `case`",
    ),
    (
        MINIMAL + "classify_next:\n  switch: 1\n  default:\n    fallthrough: 1\n",
        8,
        18,
        "model.schema",
        "expected a boolean",
    ),
]


@pytest.mark.parametrize(("text", "line", "column", "code", "message"), INVALID)
def test_an_invalid_document_is_an_error_at_its_node(
    text: str, line: int, column: int, code: str, message: str
) -> None:
    with pytest.raises(PluginYamlError) as info:
        load(text, filename="plugin.yaml")
    first = info.value.diagnostics[0]
    assert first.code == code
    assert first.location is not None and first.location.file == "plugin.yaml"
    assert (first.location.line, first.location.column) == (line, column), first.message
    assert message in first.message
    if code == "model.schema":
        # jsonschema agrees that the document is invalid.
        assert not VALIDATOR.is_valid(to_data(parse(text)))


def test_every_schema_error_is_reported_in_document_order() -> None:
    text = (
        "schema: 1\nprotocol:\n  label: p\n  id: x\n  colour: red\nattributes:\n"
        "  - name: a\n    type: MMT_U9_DATA\n"
    )
    with pytest.raises(PluginYamlError) as info:
        load(text, filename="plugin.yaml")
    found = [(d.location.line, d.location.column) for d in info.value.diagnostics if d.location]
    assert found == [(4, 7), (5, 3), (8, 11)]
    assert all(d.code == "model.schema" for d in info.value.diagnostics)
    errors = sorted(VALIDATOR.iter_errors(to_data(parse(text))), key=lambda e: list(e.path))
    assert len(errors) == 3


def test_validate_takes_another_schema() -> None:
    errors = validate(parse("a: 1\n"), {"type": "object", "required": ["b"]})
    assert [e.message for e in errors] == ["the document: missing key `b`"]
    with pytest.raises(ValueError, match="unsupported schema keywords"):
        validate(parse("a: 1\n"), {"oneOf": []})
