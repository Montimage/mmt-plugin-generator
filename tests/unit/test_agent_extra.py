"""``mmt-plugin-agent`` on an environment without the agent extra (plain
``uv sync``, or Python 3.10): the console script still starts, and says what
a run needs (exit 4) instead of crashing; with the extra it reports it. A
subprocess, so this file never imports ``mmt_plugin_agent``, whose tests
(``tests/unit/agent/``) need the extra."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

SPEC = Path(__file__).resolve().parents[2] / (
    "skills/mmt-plugin-generator/evals/cases/spec-telem/spec.md"
)
HAS_EXTRA = sys.version_info >= (3, 11) and importlib.util.find_spec("deepagents") is not None


def _agent(*args: str) -> tuple[int, dict[str, Any]]:
    code = "import sys; from mmt_plugin_agent.cli import main; sys.exit(main())"
    done = subprocess.run(
        [sys.executable, "-c", code, "--json", *args],
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    envelope: dict[str, Any] = json.loads(done.stdout)
    assert envelope["exit_code"] == done.returncode
    return done.returncode, envelope


@pytest.mark.skipif(HAS_EXTRA, reason="the agent extra is installed")
def test_without_the_extra_a_run_says_what_it_needs() -> None:
    code, envelope = _agent("new", "--spec", str(SPEC), "--model", "anthropic:any")
    assert code == 4
    assert envelope["error"]["code"] == "agent.needs-extra"
    assert "Python 3.11+ and the agent extra" in envelope["error"]["message"]
    assert (
        envelope["error"]["hint"]
        == "install it with Python 3.11+: pip install 'mmt-plugin[agent]'"
    )


@pytest.mark.skipif(HAS_EXTRA, reason="the agent extra is installed")
def test_without_the_extra_doctor_fails_its_extra_check() -> None:
    code, envelope = _agent("doctor")
    assert code == 4
    checks = {c["id"]: c["status"] for c in envelope["result"]["checks"]}
    assert checks["agent-extra"] == "fail"


def test_the_version_reports_whether_the_extra_is_there() -> None:
    code, envelope = _agent("--version")
    assert code == 0
    assert envelope["result"]["agent_extra"] is HAS_EXTRA
