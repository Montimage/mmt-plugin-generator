"""The runnable example of ``docs/agent-api.md`` (the python block after
``<!-- agent-api:run -->``) runs with a scripted model, through the public
API only (AC9)."""

from __future__ import annotations

import contextlib
import io
import re
import shutil
from collections.abc import Callable
from pathlib import Path

import pytest

import mmt_plugin_agent.models

from .fakes import FakeCli, call, done_files, scripted, step

REPO = Path(__file__).resolve().parents[3]
PAGE = REPO / "docs" / "agent-api.md"
SPEC = "skills/mmt-plugin-generator/evals/cases/spec-telem/spec.md"


def _example() -> str:
    found = re.findall(
        r"<!-- agent-api:run -->\n```python\n(.*?)```", PAGE.read_text("utf-8"), re.S
    )
    assert len(found) == 1, "docs/agent-api.md has one runnable example"
    return str(found[0])


def test_the_api_example_runs(
    tmp_path: Path, fake_cli: Callable[..., FakeCli], monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_cli()
    (tmp_path / SPEC).parent.mkdir(parents=True)
    shutil.copy(REPO / SPEC, tmp_path / SPEC)
    work = tmp_path / "telem-work"
    project = work / "project"
    model = scripted(
        [
            step(call("execute", command=f"mmt-plugin -C {project} --json validate --no-sdk")),
            step(call("execute", command=f"mmt-plugin -C {project} --json generate")),
            *done_files(work, None),
            "DONE",
        ]
    )
    asked: list[object] = []

    def resolve(spec: object) -> object:
        asked.append(spec)
        return model

    monkeypatch.setattr(mmt_plugin_agent.models, "resolve_model", resolve)
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        exec(compile(_example(), str(PAGE), "exec"), {})
    assert asked == ["anthropic:claude-sonnet-5-5"]
    assert out.getvalue() == (
        "done telem-work 1\n"
        "not checked: build and test: no SDK\n"
        "not checked: evaluation: not done (no capture)\n"
    )
