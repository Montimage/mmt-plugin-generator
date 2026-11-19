"""The ``--json`` envelope (``docs/design/cli.md``, section 6).

With ``--json`` every run prints exactly one envelope on stdout, whatever the
outcome. Its JSON Schema ships as ``mmt_plugin/schemas/cli/v1/envelope.json``.
``dumps`` is deterministic: the same envelope always gives the same bytes.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from importlib import resources
from typing import Any

from mmt_plugin import __version__
from mmt_plugin.diagnostics import CliError, Diagnostic, check_code, sorted_diagnostics
from mmt_plugin.exitcodes import ExitCode

__all__ = ["SCHEMA_VERSION", "TOOL_NAME", "build", "dumps", "load_schema"]

#: Bumped only on a breaking change; new keys are additive.
SCHEMA_VERSION = 1
TOOL_NAME = "mmt-plugin"

#: The schema's path inside the package.
SCHEMA_RESOURCE = "schemas/cli/v1/envelope.json"


def build(
    *,
    command: str | None,
    error: CliError | None = None,
    diagnostics: Sequence[Diagnostic] = (),
    context: Mapping[str, Any] | None = None,
    result: Any = None,
) -> dict[str, Any]:
    """Return the envelope of one run, keys in schema order.

    ``exit_code`` and ``ok`` follow from ``error``. A usage error has a null
    ``result``. ``context`` defaults to an unknown project and no SDK.
    """
    if error is not None:
        check_code(error.code)
    exit_code = ExitCode.SUCCESS if error is None else error.exit_code
    if exit_code is ExitCode.USAGE:
        result = None
    ctx: dict[str, Any] = {"project": None, "sdk": None}
    if context is not None:
        ctx.update(context)
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": {"name": TOOL_NAME, "version": __version__},
        "command": command,
        "ok": exit_code is ExitCode.SUCCESS,
        "exit_code": int(exit_code),
        "error": None if error is None else error.to_json(),
        "diagnostics": [d.to_json() for d in sorted_diagnostics(diagnostics)],
        "context": ctx,
        "result": result,
    }


def dumps(envelope: Mapping[str, Any]) -> str:
    """Serialize an envelope: ASCII-only JSON, 2-space indent, one final newline.

    Keys keep their insertion (schema) order. Non-ASCII text is escaped, so
    the bytes are the same whatever the stream encoding. NaN and infinities
    are refused: they are not JSON.
    """
    return json.dumps(envelope, ensure_ascii=True, indent=2, allow_nan=False) + "\n"


def load_schema() -> dict[str, Any]:
    """Return the envelope's JSON Schema, as shipped in the package."""
    path = resources.files("mmt_plugin").joinpath(SCHEMA_RESOURCE)
    schema: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return schema
