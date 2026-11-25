"""The agent's tests need the agent extra (Python 3.11+, ``uv sync --extra
agent``); without it they are not collected, so plain ``uv run pytest`` stays
green. ``tests/unit/test_agent_extra.py`` checks the console script then."""

from __future__ import annotations

import importlib.util
import shutil
import sys
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from .fakes import FakeCli

collect_ignore_glob: list[str] = []
if sys.version_info < (3, 11) or importlib.util.find_spec("deepagents") is None:
    collect_ignore_glob = ["test_*.py", "fakes.py"]

REPO = Path(__file__).resolve().parents[3]


@pytest.fixture(autouse=True)
def _isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Snapshots in the test's cache, default work folders in its directory,
    no model from the environment."""
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    monkeypatch.delenv("MMT_PLUGIN_AGENT_MODEL", raising=False)
    monkeypatch.delenv("MMT_PLUGIN_AGENT_NUM_CTX", raising=False)
    monkeypatch.delenv("MMT_PLUGIN_SKILLS", raising=False)
    monkeypatch.delenv("MMT_BASE", raising=False)
    monkeypatch.chdir(tmp_path)


@pytest.fixture
def skills_copy(tmp_path: Path) -> Path:
    """A copy of the repository's skills, which a test may change."""
    target = tmp_path / "skills"
    shutil.copytree(REPO / "skills", target, ignore=shutil.ignore_patterns("__pycache__"))
    return target


@pytest.fixture
def fake_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Callable[..., FakeCli]:
    """A fake mmt-plugin on PATH, with a plan of exit codes per command."""
    from .fakes import FakeCli

    def make(plan: dict[str, list[int]] | None = None) -> FakeCli:
        cli = FakeCli(tmp_path / "fake-cli", plan)
        for name, value in cli.env().items():
            monkeypatch.setenv(name, value)
        return cli

    return make
