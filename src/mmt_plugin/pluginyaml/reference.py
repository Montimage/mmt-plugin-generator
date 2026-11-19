"""The ``plugin.yaml`` reference page, generated from the model's JSON Schema.

``render(schema)`` turns ``mmt_plugin/schemas/model/v1/plugin.json`` into the
Markdown of ``docs/model-reference.md``: one section for the document, one
for each mapping written inline in it, and one for each definition of
``$defs``, in schema order, each key with its type, whether it is required,
its default, its constraints and its description. The output depends only on
the schema, so the committed page is stale exactly when the schema changed
(``tests/unit/docs/test_model_reference.py``). Regenerate it with::

    uv run python -m mmt_plugin.pluginyaml.reference --write docs/model-reference.md

``--check FILE`` exits 1 when ``FILE`` is not what ``render`` writes.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from mmt_plugin.pluginyaml.schema import SCHEMA_PATH, load_schema

__all__ = ["DEFAULT_OUTPUT", "main", "render", "slug"]

#: Where the page is committed, from the repository root.
DEFAULT_OUTPUT = "docs/model-reference.md"

_REGENERATE = f"uv run python -m mmt_plugin.pluginyaml.reference --write {DEFAULT_OUTPUT}"


def slug(heading: str) -> str:
    """The anchor GitHub gives a Markdown heading: lower case, punctuation
    other than ``-`` and ``_`` removed, each space a ``-``."""
    return re.sub(r"[^\w\- ]", "", heading.strip().lower()).replace(" ", "-")


def _code(value: object) -> str:
    """``value`` as a Markdown code span (JSON spelling for constants)."""
    if isinstance(value, bool):
        text = "true" if value else "false"
    elif isinstance(value, str):
        text = value
    else:
        text = str(value)
    return f"`{text}`"


def _text(text: str) -> str:
    """Plain ``text`` safe in Markdown: ``<label>`` is not an HTML tag."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _cell(text: str) -> str:
    """``text`` safe inside a table cell."""
    return text.replace("|", "\\|")


class _Page:
    """The sections of the page, in order, and the anchor of each one."""

    def __init__(self, schema: dict[str, Any]) -> None:
        self.schema = schema
        self.defs: dict[str, Any] = schema.get("$defs", {})
        # (title, schema) of every section, in page order.
        self.sections: list[tuple[str, dict[str, Any]]] = []

    def anchor(self, title: str) -> str:
        return slug(f"`{title}`")

    def link(self, title: str) -> str:
        return f"[`{title}`](#{self.anchor(title)})"

    def ref_name(self, ref: str) -> str:
        prefix = "#/$defs/"
        if not ref.startswith(prefix) or ref[len(prefix) :] not in self.defs:
            raise ValueError(f"unsupported $ref {ref!r}")
        return ref[len(prefix) :]

    # -- collecting the sections ------------------------------------------

    def collect(self) -> None:
        self.sections.append(("plugin.yaml", self.schema))
        self._inline("", self.schema)
        for name, sub in self.defs.items():
            self.sections.append((name, sub))
            self._inline(name, sub)

    def _inline(self, path: str, schema: dict[str, Any]) -> None:
        """Add a section for each mapping with keys written inline under ``schema``."""
        for key, sub in schema.get("properties", {}).items():
            title = f"{path}.{key}" if path else key
            self._inline_schema(title, sub)

    def _inline_schema(self, title: str, sub: dict[str, Any]) -> None:
        if "properties" in sub:
            self.sections.append((title, sub))
            self._inline(title, sub)
        elif isinstance(sub.get("items"), dict):
            self._inline_schema(f"{title}[]", sub["items"])

    def inline_title(self, owner: str, key: str) -> str:
        return f"{owner}.{key}" if owner != "plugin.yaml" else key

    # -- describing a schema ------------------------------------------------

    def kind(self, schema: dict[str, Any], title: str) -> str:
        """What a value of ``schema`` is, in a few words with links."""
        if "$ref" in schema:
            return self.link(self.ref_name(schema["$ref"]))
        if "const" in schema:
            return _code(schema["const"])
        if "enum" in schema:
            return "one of " + ", ".join(_code(v) for v in schema["enum"])
        if "if" in schema:
            return self._union(schema, title)
        types = schema.get("type")
        if isinstance(types, list):
            return " or ".join(self._type_word(t) for t in types)
        if types == "array":
            items = schema.get("items")
            if isinstance(items, dict):
                return "list of " + self.kind(items, f"{title}[]")
            return "list"
        if types == "object":
            if "properties" in schema:
                return self.link(title)
            extra = schema.get("additionalProperties")
            if isinstance(extra, dict):
                return "mapping of name to " + self.kind(extra, title)
            return "mapping"
        if isinstance(types, str):
            return self._type_word(types)
        return "any value"

    def _union(self, schema: dict[str, Any], title: str) -> str:
        """An ``if``/``then``/``else`` chain on a required key, as alternatives."""
        parts: list[str] = []
        node: dict[str, Any] | None = schema
        while node is not None and "if" in node:
            required = node["if"].get("required", [])
            if len(required) != 1:
                raise ValueError("unsupported if: one required key expected")
            parts.append(f"{self.kind(node['then'], title)} when it has `{required[0]}`")
            node = node.get("else")
        if node is not None and "properties" in node:
            parts.append("otherwise a mapping of the keys below")
        elif node is not None:
            parts.append(f"{self.kind(node, title)} otherwise")
        return "; ".join(parts)

    @staticmethod
    def _type_word(name: str) -> str:
        return {
            "integer": "integer",
            "string": "string",
            "boolean": "boolean",
            "object": "mapping",
            "array": "list",
            "number": "number",
        }.get(name, name)

    def constraints(self, schema: dict[str, Any]) -> list[str]:
        out: list[str] = []
        if "minimum" in schema and "maximum" in schema:
            out.append(f"{schema['minimum']} to {schema['maximum']}")
        elif "minimum" in schema:
            out.append(f"at least {schema['minimum']}")
        elif "maximum" in schema:
            out.append(f"at most {schema['maximum']}")
        if schema.get("minLength", 0) > 0:
            out.append("a string is not empty")
        if "minItems" in schema:
            out.append(f"at least {schema['minItems']} item(s)")
        if "pattern" in schema:
            out.append(f"a string matches {_code(schema['pattern'])}")
        names = schema.get("propertyNames")
        if isinstance(names, dict):
            out.append("each key is a " + self.kind(names, ""))
        return out

    def description(self, schema: dict[str, Any]) -> str:
        text = schema.get("description")
        if isinstance(text, str):
            return _text(text)
        if "$ref" in schema:
            target = self.defs[self.ref_name(schema["$ref"])]
            ref_text = target.get("description")
            if isinstance(ref_text, str):
                return _text(ref_text)
        return ""

    # -- writing ------------------------------------------------------------

    def section(self, title: str, schema: dict[str, Any]) -> list[str]:
        lines = [f"## `{title}`", ""]
        text = schema.get("description")
        if isinstance(text, str):
            lines += [_text(text), ""]
        if "properties" in schema:
            return lines + self.table(title, schema)
        lines.append(f"Type: {self.kind(schema, title)}.")
        facts = self.constraints(schema)
        if facts:
            lines.append("Constraints: " + "; ".join(facts) + ".")
        if "default" in schema:
            lines.append(f"Default: {_code(schema['default'])}.")
        lines.append("")
        # The last branch of an if/then/else chain, written inline: its keys.
        node: dict[str, Any] = schema
        while "if" in node and isinstance(node.get("else"), dict):
            node = node["else"]
        if node is not schema and "properties" in node:
            lines += self.table(title, node)
        return lines

    def table(self, title: str, schema: dict[str, Any]) -> list[str]:
        """The keys of the mapping ``schema``, as a table."""
        required = schema.get("required", [])
        closed = schema.get("additionalProperties") is False
        lines = [
            "A mapping"
            + (" with only these keys (any other key is an error)." if closed else ".")
            + (" Required: " + ", ".join(_code(k) for k in required) + "." if required else ""),
            "",
            "| Key | Type | Required | Default | Constraints | Description |",
            "|---|---|---|---|---|---|",
        ]
        for key, sub in schema["properties"].items():
            child = self.inline_title(title, key)
            row = [
                _code(key),
                self.kind(sub, child),
                "yes" if key in required else "no",
                _code(sub["default"]) if "default" in sub else "",
                "; ".join(self.constraints(sub)),
                self.description(sub),
            ]
            lines.append("| " + " | ".join(_cell(cell) for cell in row) + " |")
        lines.append("")
        return lines

    def render(self) -> str:
        self.collect()
        title = self.schema.get("title", "plugin.yaml")
        lines = [
            "# plugin.yaml reference",
            "",
            f"<!-- Generated from src/mmt_plugin/{SCHEMA_PATH} by `{_REGENERATE}`."
            " Do not edit: edit the schema and regenerate. -->",
            "",
            f"Every key of `plugin.yaml`, generated from its JSON Schema, "
            f"[`src/mmt_plugin/{SCHEMA_PATH}`](../src/mmt_plugin/{SCHEMA_PATH}) "
            f"({title}). [`plugin-yaml.md`](plugin-yaml.md) explains the format, "
            "with an example, the expressions, the offsets and the YAML subset; "
            "[the user guide](user-guide.md) shows how to write one.",
            "",
            "## Contents",
            "",
        ]
        lines += [f"- {self.link(name)}" for name, _ in self.sections]
        lines.append("")
        for name, schema in self.sections:
            lines += self.section(name, schema)
        return "\n".join(lines).rstrip("\n") + "\n"


def render(schema: dict[str, Any] | None = None) -> str:
    """The reference page of ``schema`` (default: the shipped model schema)."""
    return _Page(load_schema() if schema is None else schema).render()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m mmt_plugin.pluginyaml.reference",
        description="Print, write or check the plugin.yaml reference page.",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--write", metavar="FILE", help="write the page to FILE")
    group.add_argument("--check", metavar="FILE", help="exit 1 if FILE is not the page")
    args = parser.parse_args(argv)
    page = render()
    if args.write:
        Path(args.write).write_text(page, encoding="utf-8", newline="\n")
        return 0
    if args.check:
        path = Path(args.check)
        current = path.read_text(encoding="utf-8") if path.is_file() else None
        if current != page:
            print(f"{path} is stale: run {_REGENERATE}", file=sys.stderr)
            return 1
        return 0
    sys.stdout.write(page)
    return 0


if __name__ == "__main__":
    sys.exit(main())
