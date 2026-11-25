"""``mmt-plugin-agent eval``: a model drafts every case of the skill's evals,
and run_evals.py's checks judge it; the per-model table is written (AC8).
The real mmt-plugin runs, without an SDK (validate and generate)."""

from __future__ import annotations

import json
import os
import re
import shlex
import sys
from pathlib import Path
from typing import Any

import pytest

from mmt_plugin_agent import run_model_evals
from mmt_plugin_agent.evals import load_run_evals

from .fakes import ScriptedModel, call, step

_APPLY = (
    "import sys; from pathlib import Path; sys.path.insert(0, sys.argv[1]); import run_evals; "
    "c = Path(sys.argv[2]); case = run_evals.load_case(c); "
    "[run_evals.apply_edits(r['edits'], c, Path(sys.argv[3])) for r in case['runs']]"
)


def _script(skills: Path, case_dir: Path, project: Path) -> list[Any]:
    """What a model that gets every case right does: the entry commands, the
    case's edits (run_evals.apply_edits), then the loop without an SDK."""
    rev = load_run_evals(skills)
    case = rev.load_case(case_dir)
    blocks = rev.skill_blocks(rev.SKILL_MD.read_text("utf-8"))
    values = {k: str(v).replace("{case}", str(case_dir)) for k, v in case["params"].items()}
    values.update(project=str(project), profile="1.10.2")

    def command(args: list[str]) -> list[dict[str, Any]] | str:
        filled = [re.sub(r"<(\w+)>", lambda m: values[m.group(1)], a) for a in args]
        return step(call("execute", command=shlex.join(["mmt-plugin", *filled])))

    evals = str(skills / "mmt-plugin-generator" / "evals")
    apply = shlex.join([sys.executable, "-c", _APPLY, evals, str(case_dir), str(project)])
    return [
        *(command(a) for a in blocks[f"entry {case['entry']}"]),
        step(call("execute", command=apply)),
        *(command(a) for a in blocks["loop no-sdk"]),
        "DONE",
    ]


@pytest.fixture
def mmt_plugin_on_path(monkeypatch: pytest.MonkeyPatch) -> None:
    bin_dir = Path(sys.executable).parent
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")


@pytest.mark.usefixtures("mmt_plugin_on_path")
def test_every_case_with_a_model_that_drafts_them_right(tmp_path: Path, skills_copy: Path) -> None:
    cases = skills_copy / "mmt-plugin-generator" / "evals" / "cases"
    root = tmp_path / "evals"
    scripts = {}
    for case_dir in sorted(p for p in cases.iterdir() if (p / "case.json").is_file()):
        case = json.loads((case_dir / "case.json").read_text())
        where = "check/telem" if case["entry"] == "update" else "agent/project"
        project = root / "ScriptedModel" / case_dir.name / where
        scripts[f"{case_dir}/"] = _script(skills_copy, case_dir, project)
    model = ScriptedModel(scripts=scripts)
    out = tmp_path / "results.md"
    report = run_model_evals([model], out=out, skills_dir=skills_copy, work_root=root)
    rows = {o.case: o for o in report.outcomes}
    assert sorted(rows) == ["pcap-demo", "pdl-rfc1006", "spec-telem", "telem-update"]
    for outcome in report.outcomes:
        assert outcome.problems == [], outcome.case
        assert outcome.green, outcome.case
    assert report.ok
    table = out.read_text()
    for case in rows:
        assert f"| ScriptedModel | {case} | PASS | yes |" in table
    assert "- ScriptedModel: 4 of 4 cases pass" in table
    assert json.loads(out.with_suffix(".json").read_text())["ok"] is True


@pytest.mark.usefixtures("mmt_plugin_on_path")
def test_a_model_that_does_nothing_fails_every_case(tmp_path: Path, skills_copy: Path) -> None:
    out = tmp_path / "results.md"
    model = ScriptedModel(scripts={"": ["DONE"]})
    report = run_model_evals(
        [model],
        out=out,
        skills_dir=skills_copy,
        work_root=tmp_path / "evals",
        cases=["spec-telem", "telem-update"],
    )
    assert [(o.case, o.ok) for o in report.outcomes] == [
        ("spec-telem", False),
        ("telem-update", False),
    ]
    spec, update = report.outcomes
    assert any(p.startswith("error: FileNotFoundError") for p in spec.problems)
    assert "green: the update adds or changes no packet test" in update.problems
    assert "| ScriptedModel | spec-telem | FAIL | no |" in out.read_text()
    assert report.ok is False
