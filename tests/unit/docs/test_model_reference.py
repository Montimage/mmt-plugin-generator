"""``docs/model-reference.md`` is what the model schema generates (#29)."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pytest

from mmt_plugin.pluginyaml import load_schema
from mmt_plugin.pluginyaml.reference import DEFAULT_OUTPUT, main, render

from .mdtext import ROOT

PAGE = ROOT / DEFAULT_OUTPUT


def _section(page: str, title: str) -> str:
    start = page.index(f"\n## `{title}`\n")
    end = page.find("\n## ", start + 1)
    return page[start : end if end != -1 else len(page)]


def test_the_committed_reference_is_current() -> None:
    assert PAGE.read_text(encoding="utf-8") == render(), (
        "docs/model-reference.md is stale: run "
        "uv run python -m mmt_plugin.pluginyaml.reference --write docs/model-reference.md"
    )


def test_check_and_write(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = tmp_path / "ref.md"
    assert main(["--check", str(out)]) == 1
    assert "stale" in capsys.readouterr().err
    assert main(["--write", str(out)]) == 0
    assert out.read_text(encoding="utf-8") == render()
    assert main(["--check", str(out)]) == 0
    assert main(["--check", str(PAGE)]) == 0


def test_a_schema_change_changes_the_page() -> None:
    schema: dict[str, Any] = copy.deepcopy(load_schema())
    schema["$defs"]["protocol"]["properties"]["id"]["description"] = "A new description."
    assert "A new description." in render(schema)
    assert render(schema) != render()


def test_every_key_of_the_schema_is_on_the_page() -> None:
    page = render()

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for key, sub in node.get("properties", {}).items():
                assert f"| `{key}` |" in page, key
                walk(sub)
            for word in ("items", "then", "else", "additionalProperties"):
                walk(node.get(word))
        elif isinstance(node, list):
            for item in node:
                walk(item)

    schema = load_schema()
    walk(schema)
    for name, sub in schema["$defs"].items():
        assert f"\n## `{name}`\n" in page, name
        walk(sub)


def test_the_dispatching_definitions() -> None:
    page = render()
    element = _section(page, "element")
    assert (
        "Type: [`struct`](#struct) when it has `struct`; [`conditional`](#conditional) "
        "when it has `if`; [`attribute`](#attribute) otherwise." in element
    )
    field = _section(page, "field")
    assert "[`bitfields`](#bitfields) when it has `bits`; otherwise a mapping" in field
    assert "| `name` | [`name`](#name) | yes |" in field
    assert "| `type` | [`element_type`](#element_type) | yes |" in field
    conditional = _section(page, "conditional")
    # Keys named if, then and else are keys, not schema keywords.
    assert "| `if` | [`expression`](#expression) | yes |" in conditional
    assert "| `then` | [`elements`](#elements) | yes |" in conditional
    assert "| `else` | [`elements`](#elements) | no |" in conditional
    root = _section(page, "plugin.yaml")
    assert (
        "| `defines` | mapping of name to integer or string | no |  | "
        "each key is a [`name`](#name) |" in root
    )


def test_text_is_escaped() -> None:
    page = render()
    assert "mmtp_&lt;label&gt;.so" in page
    assert "mmtp_<label>" not in page
    # A | in a table cell is escaped; outside a table it is not.
    assert "`^((unsigned )?(int|long" in _section(page, "element_type")
    schema: dict[str, Any] = copy.deepcopy(load_schema())
    schema["$defs"]["protocol"]["properties"]["label"]["description"] = "a | b"
    assert "| a \\| b |" in render(schema)
