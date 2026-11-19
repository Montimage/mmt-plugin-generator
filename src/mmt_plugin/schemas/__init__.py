"""The JSON Schemas shipped in the package, and the registry of ``result`` schemas.

``schemas/cli/v1/envelope.json`` is the ``--json`` envelope
(``mmt_plugin.envelope``). Next to it, each command's ``result`` schema is
``<command>.json``, named after the command (``completion.json``), and each
built-in that has a result has one too (``version.json`` for
``--version --json``). The contract tests validate every envelope's
``result`` against its schema (``docs/design/cli.md``, section 6).
"""

from __future__ import annotations

import json
from importlib import resources
from typing import Any

__all__ = [
    "BUILTIN_RESULTS",
    "CLI_SCHEMA_DIR",
    "ENVELOPE",
    "has_result_schema",
    "load_cli_schema",
    "result_schema",
    "schema_names",
]

#: The directory of the CLI schemas inside the package.
CLI_SCHEMA_DIR = "schemas/cli/v1"

#: The envelope's schema name.
ENVELOPE = "envelope"

#: The results of the built-ins (no command), by schema name: what prints them.
BUILTIN_RESULTS: dict[str, str] = {"version": "--version --json"}


def _dir() -> Any:
    return resources.files("mmt_plugin").joinpath(CLI_SCHEMA_DIR)


def schema_names() -> list[str]:
    """Every schema in ``schemas/cli/v1/``, by name (the file name without ``.json``)."""
    return sorted(
        entry.name[: -len(".json")] for entry in _dir().iterdir() if entry.name.endswith(".json")
    )


def load_cli_schema(name: str) -> dict[str, Any]:
    """Return ``schemas/cli/v1/<name>.json``; ``KeyError`` if it is not shipped."""
    if name not in schema_names():
        raise KeyError(f"no schema {name!r} in {CLI_SCHEMA_DIR}")
    schema: dict[str, Any] = json.loads(_dir().joinpath(f"{name}.json").read_text("utf-8"))
    return schema


def has_result_schema(name: str) -> bool:
    """Whether the command or built-in ``name`` has a ``result`` schema."""
    return name != ENVELOPE and name in schema_names()


def result_schema(name: str) -> dict[str, Any]:
    """The ``result`` schema of the command or built-in ``name``; ``KeyError`` if none."""
    if not has_result_schema(name):
        raise KeyError(f"{name!r} has no result schema in {CLI_SCHEMA_DIR}")
    return load_cli_schema(name)
