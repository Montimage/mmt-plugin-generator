"""The agent's failures: each has an exit class of ``docs/design/cli.md``,
section 5 (``mmt_plugin.exitcodes``), and a stable ``agent.*`` code."""

from __future__ import annotations

from typing import Any

from mmt_plugin.exitcodes import ExitCode

__all__ = ["AgentError"]


class AgentError(Exception):
    """A failure the CLI reports as its envelope's ``error``."""

    def __init__(
        self, exit_code: ExitCode, code: str, message: str, hint: str | None = None
    ) -> None:
        super().__init__(message)
        self.exit_code = exit_code
        self.code = code
        self.message = message
        self.hint = hint

    def to_json(self) -> dict[str, Any]:
        return {
            "class": self.exit_code.error_class,
            "code": self.code,
            "message": self.message,
            "hint": self.hint,
        }
