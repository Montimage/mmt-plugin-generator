"""Shared fixtures: the test-only ``dummy`` command, a clean environment for
subprocesses, and the envelope schema validator."""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from collections.abc import Callable, Iterator, Mapping, Sequence
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from mmt_plugin import diagnostics
from mmt_plugin.commands import Command
from mmt_plugin.envelope import load_schema

DUMMY_SCRIPT = Path(__file__).with_name("dummy_command.py")

#: Variables that change colors, widths or locales; unset for subprocesses.
_STYLE_VARS = (
    "FORCE_COLOR",
    "NO_COLOR",
    "CLICOLOR_FORCE",
    "COLORTERM",
    "COLUMNS",
    "LC_ALL",
    "LC_CTYPE",
    "PYTHON_COLORS",
)


def _load_dummy() -> ModuleType:
    spec = importlib.util.spec_from_file_location("dummy_command", DUMMY_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_DUMMY = _load_dummy()


@pytest.fixture
def dummy(monkeypatch: pytest.MonkeyPatch) -> Iterator[Command]:
    """The ``dummy`` command, with its test-only codes registered."""
    monkeypatch.setattr(diagnostics, "CODES", _DUMMY.codes_with_test_codes())
    command: Command = _DUMMY.DummyCommand()
    yield command


@pytest.fixture
def validate_envelope() -> Callable[[Any], None]:
    """Validate a parsed envelope against the shipped schema."""
    validator = Draft202012Validator(load_schema())

    def check(doc: Any) -> None:
        validator.validate(doc)

    return check


def _clean_env(**overrides: str) -> dict[str, str]:
    """``os.environ`` without the style variables, plus ``overrides``."""
    env = {k: v for k, v in os.environ.items() if k not in _STYLE_VARS}
    env.update({"TERM": "xterm-256color", "LANG": "C.UTF-8"})
    env.update(overrides)
    return env


@pytest.fixture
def clean_env() -> Callable[..., dict[str, str]]:
    """Build a subprocess environment: no style variables, ``TERM=xterm-256color``,
    ``LANG=C.UTF-8``, plus the keyword overrides."""
    return _clean_env


@pytest.fixture
def run_cli() -> Callable[..., subprocess.CompletedProcess[bytes]]:
    """Run the CLI with the ``dummy`` command in a subprocess; bytes in and out."""

    def run(
        args: Sequence[str],
        *,
        env: Mapping[str, str] | None = None,
        module: bool = False,
        timeout: float = 60,
    ) -> subprocess.CompletedProcess[bytes]:
        prefix = ["-m", "mmt_plugin"] if module else [str(DUMMY_SCRIPT)]
        return subprocess.run(
            [sys.executable, *prefix, *args],
            capture_output=True,
            stdin=subprocess.DEVNULL,
            env=_clean_env() if env is None else dict(env),
            timeout=timeout,
            check=False,
        )

    return run
