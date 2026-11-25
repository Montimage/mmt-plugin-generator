"""The agent's failures: each has an exit class of ``docs/design/cli.md``,
section 5 (``mmt_plugin.exitcodes``), and a stable ``agent.*`` code."""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from typing import Any

from mmt_plugin.exitcodes import ExitCode
from mmt_plugin_agent.policy import is_secret

__all__ = ["AgentError", "redact"]

#: What a provider's key looks like (Anthropic, OpenAI and the like).
_KEY = re.compile(r"\bsk-[A-Za-z0-9_-]{8,}")


def redact(text: str, environ: Mapping[str, str] | None = None) -> str:
    """``text`` without the value of any secret variable of ``environ``
    (``*_API_KEY``, ``*_TOKEN``, ...) and without anything shaped like a key."""
    env = os.environ if environ is None else environ
    for name, value in env.items():
        if is_secret(name) and len(value) >= 8:
            text = text.replace(value, f"<{name}>")
    return _KEY.sub("<key>", text)


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

    @classmethod
    def unexpected(cls, exc: BaseException) -> AgentError:
        """An exception no other error covers (the model's provider: a bad
        key, a rate limit, an endpoint down; an I/O error), as class
        ``internal``, its message without secrets."""
        return cls(
            ExitCode.INTERNAL,
            "agent.unexpected",
            redact(f"{type(exc).__name__}: {exc}"),
            "check the model's provider (its key, its endpoint, its rate limits) with "
            "mmt-plugin-agent doctor, then run again",
        )

    def to_json(self) -> dict[str, Any]:
        return {
            "class": self.exit_code.error_class,
            "code": self.code,
            "message": self.message,
            "hint": self.hint,
        }
