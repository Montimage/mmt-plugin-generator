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

from mmt_plugin_agent import evals, run_model_evals
from mmt_plugin_agent.evals import load_run_evals
from mmt_plugin_agent.policy import LOOP_COMMANDS, mmt_plugin_command
from mmt_plugin_agent.result import AgentResult, CommandRecord

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


def _diag_script(skills: Path, case_dir: Path, agent: Path, project: Path) -> list[Any]:
    """The live telem-update run (L8): the entry check saved in run-0, a
    heredoc that names validate, the loop as one shell for-loop over ``$c``
    (no command name in its text), run-0's files then moved into run-1, the
    edits, and the loop again into run-2."""
    runs = agent / "runs"
    p = shlex.quote(str(project))

    def loop(n: int) -> list[dict[str, Any]] | str:
        dest = shlex.quote(str(runs / f"run-{n}"))
        return step(
            call(
                "execute",
                command=(
                    f"mkdir -p {dest} && for c in 'validate --no-sdk --sdk-profile 1.10.2' "
                    "'generate --sdk-profile 1.10.2'; do n=${c%% *}; "
                    f"mmt-plugin -C {p} --json $c > {dest}/$n.json; echo $n $?; done"
                ),
            )
        )

    run0 = shlex.quote(str(runs / "run-0"))
    run1 = shlex.quote(str(runs / "run-1"))
    notes = shlex.quote(str(agent / "plan.md"))
    evals_dir = str(skills / "mmt-plugin-generator" / "evals")
    apply = shlex.join([sys.executable, "-c", _APPLY, evals_dir, str(case_dir), str(project)])
    return [
        step(
            call(
                "execute",
                command=f"mkdir -p {run0} && mmt-plugin -C {p} --json validate --no-sdk "
                f"> {run0}/validate-nosdk.json",
            )
        ),
        step(call("execute", command=f"cat > {notes} <<'EOF'\nvalidate, then generate\nEOF")),
        loop(1),
        step(call("execute", command=f"mv {run0}/validate-nosdk.json {run1}/ && rmdir {run0}")),
        step(call("execute", command=apply)),
        loop(2),
        "DONE",
    ]


@pytest.mark.usefixtures("mmt_plugin_on_path")
def test_the_runs_are_the_work_folders_whatever_the_shell_text(
    tmp_path: Path, skills_copy: Path
) -> None:
    case_dir = skills_copy / "mmt-plugin-generator" / "evals" / "cases" / "telem-update"
    root = tmp_path / "evals"
    work = root / "ScriptedModel" / "telem-update"
    script = _diag_script(skills_copy, case_dir, work / "agent", work / "check" / "telem")
    model = ScriptedModel(scripts={f"{case_dir}/": script})
    report = run_model_evals(
        [model],
        out=tmp_path / "r.md",
        skills_dir=skills_copy,
        work_root=root,
        cases=["telem-update"],
    )
    (outcome,) = report.outcomes
    runs = work / "agent" / "runs"
    assert sorted(p.name for p in runs.iterdir()) == ["run-1", "run-2"]
    assert (runs / "run-1" / "validate-nosdk.json").is_file()
    assert outcome.problems == []
    assert outcome.ok
    records = [json.loads(line) for line in (work / "commands.jsonl").read_text().splitlines()]
    assert len(records) == 6
    assert set(records[0]) == {
        "command",
        "mmt_command",
        "exit_code",
        "mmt_exit_code",
        "refused",
        "started_ns",
        "ended_ns",
    }
    assert records[0]["mmt_command"] == "validate"
    assert all(isinstance(r["started_ns"], int) for r in records)


def _envelope(command: str, code: int = 0, line: int = 3) -> dict[str, Any]:
    failed = code != 0
    return {
        "schema_version": 1,
        "tool": {"name": "mmt-plugin", "version": "0"},
        "command": command,
        "ok": not failed,
        "exit_code": code,
        "error": (
            {"class": "model", "code": "model.unknown-attribute", "message": "no msgtype"}
            if failed
            else None
        ),
        "diagnostics": (
            [
                {
                    "severity": "error",
                    "code": "model.unknown-attribute",
                    "message": "no msgtype",
                    "location": {"file": "plugin.yaml", "line": line},
                }
            ]
            if failed
            else []
        ),
        "context": {"project": ".", "sdk": {"prefix": None}},
        "result": None if failed else {},
    }


_T0 = 1_700_000_000 * 10**9
_MODEL = "a\nb\nc: val(msgtype) == 3\nd\n"


def _work_case(
    tmp_path: Path, skills_copy: Path, runs: dict[str, dict[str, dict[str, Any]]]
) -> tuple[evals._Case, AgentResult]:
    """spec-telem's checks on a work folder holding ``runs`` (directory:
    file: envelope), ``run-<n>/validate.json`` written at ``_T0 + n`` s."""
    rev = load_run_evals(skills_copy)
    case_dir = skills_copy / "mmt-plugin-generator" / "evals" / "cases" / "spec-telem"
    work = tmp_path / "case"
    case = evals._Case(
        rev,
        case_dir,
        work,
        sdk=None,
        cc="gcc",
        cli=[sys.executable, "-m", "mmt_plugin"],
        timeout=60,
    )
    for directory, files in runs.items():
        n = int(directory.split("-")[1])
        for name, env in files.items():
            path = case.agent_work / "runs" / directory / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(env, indent=2) + "\n")
            when = _T0 + n * 10**9 - (10**8 if name != "validate.json" else 0)
            os.utime(path, ns=(when, when))
    result = AgentResult(status="done", thread_id="t", work=case.agent_work)
    return case, result


def _project(case: evals._Case, files: dict[str, str]) -> dict[str, str]:
    for rel, text in files.items():
        path = case.project / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    return dict(files)


def _problems(case: evals._Case) -> list[str]:
    return [*case.runner.result.problems, *case.problems]


def test_an_entry_check_next_to_the_loop_is_checked_as_its_own(
    tmp_path: Path, skills_copy: Path
) -> None:
    """L7 and L8: run-1 holds the entry check (validate-nosdk.json, run-0's,
    moved) and the loop's envelopes; shell records that name no command."""
    ok = {"validate.json": _envelope("validate"), "generate.json": _envelope("generate")}
    case, result = _work_case(
        tmp_path,
        skills_copy,
        {"run-1": {**ok, "validate-nosdk.json": _envelope("validate")}, "run-2": ok},
    )
    state = _project(case, {"plugin.yaml": _MODEL})
    result.commands = [
        CommandRecord('for c in "validate" "generate"; do mmt-plugin --json $c; done', 0, "")
    ]
    case.check_runs(result, [(_T0, state)])
    assert _problems(case) == []
    # An entry check that breaks the contract is reported at its file.
    bad = case.agent_work / "runs/run-1/validate-nosdk.json"
    bad.write_text(json.dumps({**_envelope("validate"), "ok": False}))
    case.check_runs(result, [(_T0, state)])
    assert _problems(case) == [
        "runs/run-1/validate-nosdk.json: ok is False with exit_code 0",
    ]


def test_a_failed_runs_fix_must_touch_what_it_reported(tmp_path: Path, skills_copy: Path) -> None:
    ok = {"validate.json": _envelope("validate"), "generate.json": _envelope("generate")}
    failed = {"validate.json": _envelope("validate", 3, line=3)}
    before = {"plugin.yaml": _MODEL}
    elsewhere = {"plugin.yaml": _MODEL.replace("a\n", "z\n")}
    fixed = {"plugin.yaml": _MODEL.replace("msgtype", "msg_type")}
    case, result = _work_case(tmp_path, skills_copy, {"run-1": failed, "run-2": ok})
    # Snapshots: before run 1 (at _T0 + 0.5 s), then before run 2.
    _project(case, elsewhere)
    case.check_runs(result, [(_T0, before), (_T0 + 15 * 10**8, elsewhere)])
    assert _problems(case) == [
        "run 2: the edits do not touch plugin.yaml:3 (model.unknown-attribute)"
    ]
    case, result = _work_case(tmp_path / "fixed", skills_copy, {"run-1": failed, "run-2": ok})
    _project(case, fixed)
    case.check_runs(result, [(_T0, before), (_T0 + 15 * 10**8, fixed)])
    assert _problems(case) == []


def test_a_loop_command_without_its_envelope_is_a_problem(
    tmp_path: Path, skills_copy: Path
) -> None:
    case, result = _work_case(
        tmp_path,
        skills_copy,
        {
            "run-1": {"validate.json": _envelope("validate")},
            "run-2": {
                "validate.json": _envelope("validate"),
                "generate.json": _envelope("validate"),
            },
        },
    )
    state = _project(case, {"plugin.yaml": _MODEL})
    case.check_runs(result, [(_T0, state)])
    assert _problems(case) == [
        "runs/run-2/generate.json: command is 'validate', not 'generate'",
        "runs/run-1: generate: no envelope (generate.json)",
    ]


def test_a_rewritten_packet_test_is_a_problem(tmp_path: Path, skills_copy: Path) -> None:
    ok = {"validate.json": _envelope("validate"), "generate.json": _envelope("generate")}
    case, result = _work_case(tmp_path, skills_copy, {"run-1": ok})
    seed = skills_copy / "mmt-plugin-generator/evals/cases/telem-update/project"
    reading = (seed / "tests/telem-reading.yaml").read_text()
    model = (seed / "plugin.yaml").read_text()
    before = {"plugin.yaml": model, "tests/telem-reading.yaml": reading}
    _project(case, {**before, "tests/telem-reading.yaml": reading.replace("value: 2", "value: 7")})
    case.check_runs(result, [(_T0, before)])
    problems = _problems(case)
    assert len(problems) == 1
    assert problems[0].startswith("run 1: ")
    assert problems[0].endswith(" in tests/telem-reading.yaml")


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
