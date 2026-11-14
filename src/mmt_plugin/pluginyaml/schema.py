"""The JSON Schema of ``plugin.yaml``, and the validator that enforces it.

The schema, ``mmt_plugin/schemas/model/v1/plugin.json`` (draft 2020-12), is
the published definition of the format: it ships in the package, so in each
release. ``mmt-plugin`` enforces that same file, with this small validator
of the keywords the schema uses, on the positioned nodes of
``mmt_plugin.pluginyaml.nodes``: each error points at the line and column of
the offending node. A unit test checks that ``jsonschema`` agrees with it.
"""

from __future__ import annotations

import difflib
import json
import re
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources
from typing import Any

from mmt_plugin.pluginyaml.nodes import Mapping, Node, Scalar, Sequence

__all__ = ["SCHEMA_PATH", "SchemaError", "load_schema", "validate"]

#: The schema's path inside the package.
SCHEMA_PATH = "schemas/model/v1/plugin.json"

#: Keywords that only annotate.
_ANNOTATIONS = frozenset(
    {"$schema", "$id", "$defs", "$comment", "title", "description", "default", "examples"}
)
#: Keywords the validator checks: the schema may use no other.
KEYWORDS = frozenset(
    {
        "$ref",
        "if",
        "then",
        "else",
        "type",
        "const",
        "enum",
        "minimum",
        "maximum",
        "minLength",
        "pattern",
        "required",
        "properties",
        "additionalProperties",
        "propertyNames",
        "items",
        "minItems",
    }
)

_ARTICLES = {
    "object": "a mapping",
    "array": "a list",
    "string": "a string",
    "integer": "an integer",
    "number": "a number",
    "boolean": "a boolean",
    "null": "nothing (null)",
}


@lru_cache(maxsize=1)
def load_schema() -> dict[str, Any]:
    """The schema, as shipped."""
    text = resources.files("mmt_plugin").joinpath(SCHEMA_PATH).read_text("utf-8")
    schema: dict[str, Any] = json.loads(text)
    return schema


@dataclass(frozen=True)
class SchemaError:
    """One schema violation: ``path`` (``attributes[2].offset``) names the
    node, ``node`` is where it is, ``hint`` says what is expected."""

    path: str
    message: str
    hint: str | None
    node: Node


def _kind(node: Node) -> str:
    if isinstance(node, Mapping):
        return "object"
    if isinstance(node, Sequence):
        return "array"
    value = node.value
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if value is None:
        return "null"
    return "string"


def _show(node: Node) -> str:
    kind = _kind(node)
    if isinstance(node, Scalar) and kind in ("integer", "string", "boolean", "number"):
        shown = node.text if len(node.text) <= 40 else node.text[:37] + "..."
        return f"{_ARTICLES[kind]} (`{shown}`)"
    return _ARTICLES[kind]


def _same(value: object, expected: object) -> bool:
    """JSON equality: ``True`` is not ``1``."""
    return type(value) is type(expected) and value == expected


def _join(path: str, key: str | int) -> str:
    if isinstance(key, int):
        return f"{path}[{key}]"
    return key if not path else f"{path}.{key}"


class _Validator:
    def __init__(self, root: dict[str, Any]) -> None:
        self.root = root
        self.errors: list[SchemaError] = []

    def resolve(self, ref: str) -> dict[str, Any]:
        if not ref.startswith("#/"):
            raise ValueError(f"unsupported $ref {ref!r}")
        target: Any = self.root
        for part in ref[2:].split("/"):
            target = target[part]
        if not isinstance(target, dict):
            raise ValueError(f"$ref {ref!r} is not a schema")
        return target

    def passes(self, node: Node, schema: dict[str, Any], path: str) -> bool:
        probe = _Validator(self.root)
        probe.check(node, schema, path)
        return not probe.errors

    def error(self, path: str, message: str, node: Node, hint: str | None) -> None:
        where = path or "the document"
        self.errors.append(SchemaError(path, f"{where}: {message}", hint, node))

    def check(self, node: Node, schema: dict[str, Any], path: str) -> None:
        unknown = set(schema) - KEYWORDS - _ANNOTATIONS
        if unknown:
            raise ValueError(f"unsupported schema keywords {sorted(unknown)}")
        hint = schema.get("description")
        if "$ref" in schema:
            target = self.resolve(schema["$ref"])
            before = len(self.errors)
            self.check(node, target, path)
            if len(self.errors) > before:
                return
        if "if" in schema:
            branch = "then" if self.passes(node, schema["if"], path) else "else"
            if branch in schema:
                self.check(node, schema[branch], path)
        if "type" in schema:
            types = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
            kind = _kind(node)
            if kind not in types and not (kind == "integer" and "number" in types):
                expected = " or ".join(_ARTICLES[t] for t in types)
                self.error(path, f"expected {expected}, found {_show(node)}", node, hint)
                return
        if "const" in schema and not (
            isinstance(node, Scalar) and _same(node.value, schema["const"])
        ):
            self.error(
                path, f"must be {json.dumps(schema['const'])}, found {_show(node)}", node, hint
            )
            return
        if "enum" in schema and not (
            isinstance(node, Scalar) and any(_same(node.value, e) for e in schema["enum"])
        ):
            choices = ", ".join(str(e) for e in schema["enum"])
            close = ""
            if isinstance(node, Scalar) and isinstance(node.value, str):
                found = difflib.get_close_matches(
                    node.value, [str(e) for e in schema["enum"]], n=1, cutoff=0.6
                )
                close = f" (did you mean `{found[0]}`?)" if found else ""
            self.error(
                path,
                f"{_show(node)} is not one of the allowed values{close}",
                node,
                f"one of: {choices}",
            )
            return
        if isinstance(node, Scalar):
            self.scalar(node, schema, path, hint)
        elif isinstance(node, Mapping):
            self.mapping(node, schema, path)
        else:
            self.sequence(node, schema, path)

    def scalar(self, node: Scalar, schema: dict[str, Any], path: str, hint: str | None) -> None:
        value = node.value
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if "minimum" in schema and value < schema["minimum"]:
                self.error(path, f"{node.text} is below {schema['minimum']}", node, hint)
            if "maximum" in schema and value > schema["maximum"]:
                self.error(path, f"{node.text} is above {schema['maximum']}", node, hint)
        if isinstance(value, str):
            if "minLength" in schema and len(value) < schema["minLength"]:
                self.error(path, "must not be empty", node, hint)
            elif "pattern" in schema and re.search(schema["pattern"], value) is None:
                self.error(path, f"`{value}` is not valid here", node, hint)

    def mapping(self, node: Mapping, schema: dict[str, Any], path: str) -> None:
        properties: dict[str, Any] = schema.get("properties", {})
        for key in schema.get("required", ()):
            if node.key(key) is None:
                self.error(path, f"missing key `{key}`", node, None)
        extra = schema.get("additionalProperties", True)
        for key, value in node.items:
            here = _join(path, key.text)
            if "propertyNames" in schema:
                self.check(key, schema["propertyNames"], here)
            if key.text in properties:
                self.check(value, properties[key.text], here)
            elif extra is False:
                by_lower = {k.lower(): k for k in properties}
                close = difflib.get_close_matches(
                    key.text.lower(), list(by_lower), n=1, cutoff=0.6
                )
                did = f" (did you mean `{by_lower[close[0]]}`?)" if close else ""
                known = ", ".join(properties)
                self.error(
                    here,
                    f"unknown key `{key.text}`{did}",
                    key,
                    f"the keys here are: {known}" if known else None,
                )
            elif isinstance(extra, dict):
                self.check(value, extra, here)

    def sequence(self, node: Sequence, schema: dict[str, Any], path: str) -> None:
        if "minItems" in schema and len(node.items) < schema["minItems"]:
            self.error(
                path,
                f"needs at least {schema['minItems']} item(s), found {len(node.items)}",
                node,
                schema.get("description"),
            )
        if "items" in schema:
            for i, item in enumerate(node.items):
                self.check(item, schema["items"], _join(path, i))


def _position(error: SchemaError) -> tuple[int, int, str]:
    return (error.node.line, error.node.column, error.message)


def validate(node: Node, schema: dict[str, Any] | None = None) -> list[SchemaError]:
    """Every violation of ``schema`` (the plugin.yaml schema by default) in
    ``node``, in document order, each once."""
    root = load_schema() if schema is None else schema
    validator = _Validator(root)
    validator.check(node, root, "")
    seen: set[tuple[int, int, str]] = set()
    out: list[SchemaError] = []
    for error in sorted(validator.errors, key=_position):
        key = _position(error)
        if key not in seen:
            seen.add(key)
            out.append(error)
    return out
