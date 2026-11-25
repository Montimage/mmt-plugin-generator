"""What the agent's shell and file tools may do (no deepagents needed).

The checks here are defence in depth, not a sandbox: a shell command can
always reach what the user running it can. The container is the sandbox
(``docs/agent-api.md``, "The sandbox").
"""

from __future__ import annotations

import os
import re
import shlex
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

__all__ = [
    "LOOP_COMMANDS",
    "CommandCheck",
    "check_command",
    "is_within",
    "mmt_plugin_command",
    "shell_env",
]

#: The four loop commands of the skill (SKILL.md, Step 4), in order.
LOOP_COMMANDS = ("validate", "generate", "build", "test")

#: mmt-plugin's options that come before the command and take a value.
_GLOBAL_WITH_VALUE = frozenset({"-C", "--project"})

#: The variables the agent's shell inherits, by name or prefix (``*``).
_ENV_ALLOWED = (
    "PATH",
    "HOME",
    "USER",
    "LOGNAME",
    "SHELL",
    "TMPDIR",
    "LANG",
    "LC_*",
    "TERM",
    "CC",
    "DOCKER_HOST",
    "DOCKER_TLS_VERIFY",
    "DOCKER_CERT_PATH",
    "DOCKER_CONFIG",
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "NO_PROXY",
    "http_proxy",
    "https_proxy",
    "no_proxy",
    "SSL_CERT_FILE",
    "SSL_CERT_DIR",
    "REQUESTS_CA_BUNDLE",
    "PKG_CONFIG_*",
    "UV_*",
    "XDG_*",
    "MMT_*",
    "CYBERLAB_DIR",
)

#: Names never passed on, even when allowed above: the model's provider
#: keys and any other credential.
_ENV_SECRET = re.compile(r"_API_KEY$|_TOKEN$|SECRET|PASSWORD|CREDENTIAL", re.IGNORECASE)

#: The system prefix the skill never uses (SKILL.md, Rule 3).
_SYSTEM_PREFIX = PurePosixPath("/opt/mmt")


def shell_env(environ: Mapping[str, str]) -> dict[str, str]:
    """The environment of the agent's shell: the allowed names of
    ``environ``, without secrets, and no byte-code files."""
    out = {}
    for name, value in environ.items():
        allowed = any(
            name.startswith(rule[:-1]) if rule.endswith("*") else name == rule
            for rule in _ENV_ALLOWED
        )
        if allowed and not _ENV_SECRET.search(name):
            out[name] = value
    out["PYTHONDONTWRITEBYTECODE"] = "1"
    return out


def is_within(path: Path, root: Path) -> bool:
    """Whether ``path`` is ``root`` or below it (both already resolved)."""
    return path == root or root in path.parents


@dataclass(frozen=True)
class CommandCheck:
    """The verdict on one shell command: ``refused`` is why it may not run;
    ``force`` is true when it passes ``--force`` (run only with leave)."""

    refused: str | None = None
    force: bool = False


def _under_system_prefix(token: str) -> bool:
    for part in [token, *token.split("=")[1:]]:
        if not part.startswith("/"):
            continue
        path = PurePosixPath(os.path.normpath(part))
        if path == _SYSTEM_PREFIX or _SYSTEM_PREFIX in path.parents:
            return True
    return False


def _tokens(command: str) -> list[str]:
    lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    lexer.commenters = ""
    return list(lexer)


def check_command(command: str) -> CommandCheck:
    """Refuse ``sudo``, ``--system`` and a path under ``/opt/mmt``; flag
    ``--force``. A command that does not parse is refused: the agent can
    always write a simpler one."""
    try:
        tokens = _tokens(command)
    except ValueError as exc:
        return CommandCheck(refused=f"the command does not parse ({exc}): write it plainly")
    for token in tokens:
        if PurePosixPath(token).name == "sudo":
            return CommandCheck(refused="sudo is never used (SKILL.md, Rule 3)")
        if token == "--system" or token.startswith("--system="):
            return CommandCheck(refused="--system is never used (SKILL.md, Rule 3)")
        if _under_system_prefix(token):
            return CommandCheck(
                refused=f"{token} is under /opt/mmt, which is never used (SKILL.md, Rule 3)"
            )
    force = any(t == "--force" or t.startswith("--force=") for t in tokens)
    return CommandCheck(force=force)


def _segments(tokens: Iterable[str]) -> list[list[str]]:
    out: list[list[str]] = [[]]
    for token in tokens:
        if token and all(c in "|&;()<>" for c in token):
            out.append([])
        else:
            out[-1].append(token)
    return [s for s in out if s]


def mmt_plugin_command(command: str) -> tuple[str, str | None] | None:
    """The mmt-plugin command a shell command runs (``validate``, ...) and
    its ``-C`` project, or None when it runs no mmt-plugin command."""
    try:
        tokens = _tokens(command)
    except ValueError:
        return None
    for segment in _segments(tokens):
        for i, token in enumerate(segment):
            name = PurePosixPath(token).name
            if name == "mmt-plugin" or (
                token == "mmt_plugin" and i >= 1 and segment[i - 1] == "-m"
            ):
                rest = segment[i + 1 :]
                break
        else:
            continue
        project = None
        j = 0
        while j < len(rest):
            arg = rest[j]
            if arg in _GLOBAL_WITH_VALUE and j + 1 < len(rest):
                project = rest[j + 1]
                j += 2
            elif arg.startswith("-"):
                j += 1
            else:
                return arg, project
        return None
    return None
