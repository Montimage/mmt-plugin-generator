"""``mmt-plugin-agent eval``: a model drafts every case of the skill's evals,
and run_evals.py's checks judge it; the per-model table is written (AC8).
The real mmt-plugin runs, without an SDK (validate and generate)."""

from __future__ import annotations

import json
import os
import re
import shlex
import sys
import time
from pathlib import Path
from typing import Any

import pytest

from mmt_plugin_agent import evals, run_model_evals
from mmt_plugin_agent.evals import load_run_evals, saved_envelope
from mmt_plugin_agent.policy import LOOP_COMMANDS, mmt_plugin_command
from mmt_plugin_agent.result import CommandRecord

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


def _redirected(script: list[Any], runs: Path) -> list[Any]:
    """The script with each loop command's envelope written to
    ``runs/run-1/<command>.json`` by a redirect, so its output holds none."""
    out: list[Any] = []
    for item in script:
        if isinstance(item, list) and item[0]["name"] == "execute":
            command = item[0]["args"]["command"]
            found = mmt_plugin_command(command)
            if found is not None and found[0] in LOOP_COMMANDS:
                saved = shlex.quote(str(runs / f"{found[0]}.json"))
                dest = shlex.quote(str(runs))
                command = f"mkdir -p {dest} && {command} > {saved}"
                item = step(call("execute", command=command))
        out.append(item)
    return out


@pytest.mark.usefixtures("mmt_plugin_on_path")
def test_envelopes_redirected_to_the_work_folder_are_checked(
    tmp_path: Path, skills_copy: Path
) -> None:
    case_dir = skills_copy / "mmt-plugin-generator" / "evals" / "cases" / "spec-telem"
    root = tmp_path / "evals"
    agent = root / "ScriptedModel" / "spec-telem" / "agent"
    script = _redirected(_script(skills_copy, case_dir, agent / "project"), agent / "runs/run-1")
    model = ScriptedModel(scripts={f"{case_dir}/": script})
    report = run_model_evals(
        [model],
        out=tmp_path / "r.md",
        skills_dir=skills_copy,
        work_root=root,
        cases=["spec-telem"],
    )
    (outcome,) = report.outcomes
    assert (agent / "runs/run-1/validate.json").is_file()
    assert outcome.problems == []
    assert outcome.ok


def test_a_saved_envelope_counts_only_when_written_while_its_command_ran(
    tmp_path: Path,
) -> None:
    saved = tmp_path / "runs" / "run-1" / "validate.json"
    saved.parent.mkdir(parents=True)
    env = {"schema_version": 1, "exit_code": 0, "command": "validate"}
    saved.write_text(json.dumps(env))
    now = time.time_ns()
    command = "mmt-plugin -C p --json validate > runs/run-1/validate.json"
    record = CommandRecord(command, 0, "", started_ns=now - 10**9, ended_ns=now + 10**9)
    assert saved_envelope(tmp_path, record, 1) == env
    old = CommandRecord(command, 0, "", started_ns=now - 100 * 10**9, ended_ns=now - 90 * 10**9)
    assert saved_envelope(tmp_path, old, 1) is None
    assert saved_envelope(tmp_path, CommandRecord(command, 0, ""), 1) is None


def _saved(path: Path, env: dict[str, Any], mtime_ns: int) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(env))
    os.utime(path, ns=(mtime_ns, mtime_ns))
    return env


def test_an_envelope_saved_under_another_name_is_its_commands(tmp_path: Path) -> None:
    """L7, the live telem-update run: the entry check saved as
    run-1/validate-nosdk.json, the loop's validate 0.2 s later as
    run-1/validate.json; the shell numbers them runs 1 and 2. Each command
    gets its own envelope, a misnamed one too, and none is taken twice."""
    t = time.time_ns()
    runs = tmp_path / "runs"
    env = {"schema_version": 1, "exit_code": 0, "command": "validate"}
    nosdk = _saved(runs / "run-1/validate-nosdk.json", {**env, "context": {"sdk": None}}, t + 50)
    loop = _saved(runs / "run-1/validate.json", {**env, "context": {"sdk": "/sdk"}}, t + 2 * 10**8)
    _saved(runs / "run-1/generate.json", {**env, "command": "generate"}, t + 3 * 10**8)
    first = CommandRecord(
        "mmt-plugin --json validate --no-sdk p > runs/run-1/validate-nosdk.json",
        0,
        "",
        started_ns=t,
        ended_ns=t + 10**8,
    )
    second = CommandRecord(
        'cd p && mmt-plugin --json validate > "$W/runs/run-1/validate.json"',
        0,
        "",
        started_ns=t + 10**8,
        ended_ns=t + 25 * 10**7,
    )
    claimed: set[Path] = set()
    assert saved_envelope(tmp_path, first, 1, claimed=claimed) == nosdk
    assert saved_envelope(tmp_path, second, 2, claimed=claimed) == loop
    assert claimed == {runs / "run-1/validate-nosdk.json", runs / "run-1/validate.json"}
    # No file name in the command (a variable): the one written while it ran.
    command = 'mmt-plugin --json validate --no-sdk p > "$OUT"'
    by_time = CommandRecord(command, 0, "", started_ns=t, ended_ns=t + 10**8)
    assert saved_envelope(tmp_path, by_time, 2) == nosdk
    # Nothing left for a third validate; generate's envelope is not one.
    third = CommandRecord("mmt-plugin --json validate p > /tmp/v", 0, "", started_ns=t, ended_ns=t)
    assert saved_envelope(tmp_path, third, 3, claimed=claimed) is None


def test_without_sdk_the_eval_uses_mmt_base(
    tmp_path: Path, skills_copy: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sdk = tmp_path / "sdk"
    sdk.mkdir()
    monkeypatch.setenv("MMT_BASE", str(sdk))
    seen: dict[str, Any] = {}

    def agent(model: Any, **kwargs: Any) -> Any:
        seen["agent"] = kwargs["sdk"]
        raise RuntimeError("stop here")

    real = evals._Case

    class Case(real):  # type: ignore[valid-type, misc]
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            seen["case"] = kwargs["sdk"]
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(evals, "PluginAgent", agent)
    monkeypatch.setattr(evals, "_Case", Case)
    report = run_model_evals(
        [ScriptedModel(scripts={"": ["DONE"]})],
        out=tmp_path / "r.md",
        skills_dir=skills_copy,
        work_root=tmp_path / "evals",
        cases=["spec-telem"],
    )
    assert seen == {"agent": sdk.resolve(), "case": sdk.resolve()}
    assert report.outcomes[0].problems == ["error: RuntimeError: stop here"]


def test_a_nested_work_folder_is_one_clear_problem(tmp_path: Path, skills_copy: Path) -> None:
    root = tmp_path / "evals"
    nested = root / "ScriptedModel" / "spec-telem" / "agent" / "telem-plugin"
    make = shlex.join(["mkdir", "-p", str(nested / "runs"), str(nested / "project")])
    write = call("write_file", file_path=str(nested / "manifest.json"), content="{}")
    model = ScriptedModel(scripts={"": [step(call("execute", command=make)), step(write), "DONE"]})
    report = run_model_evals(
        [model],
        out=tmp_path / "r.md",
        skills_dir=skills_copy,
        work_root=root,
        cases=["spec-telem"],
    )
    (outcome,) = report.outcomes
    assert not outcome.ok
    assert outcome.work == str(root / "ScriptedModel" / "spec-telem")
    assert outcome.problems == [
        f"the model nested its work folder at {nested.resolve()}; the brief says "
        f"{nested.parent} is the work folder, with the project at "
        f"{(nested.parent / 'project').resolve()}"
    ]
