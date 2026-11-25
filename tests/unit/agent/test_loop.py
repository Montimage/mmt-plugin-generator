"""A scripted model drives the skill's loop through the graph against a fake
mmt-plugin: the result is the loop the shell saw, and ``stream()`` yields
events for every loop command (P7)."""

from __future__ import annotations

import asyncio
import json
import os
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from mmt_plugin_agent import PluginAgent
from mmt_plugin_agent.result import CommandRecord, build_result, work_folder

from .fakes import FakeCli, ScriptedModel, call, done_files, loop, scripted, step

SPEC = Path(__file__).resolve().parents[3] / (
    "skills/mmt-plugin-generator/evals/cases/spec-telem/spec.md"
)


def _agent(model: ScriptedModel, work: Path, sdk: Path) -> PluginAgent:
    return PluginAgent(model, sdk=sdk, work_dir=work, allow_synthetic=True)


def test_a_green_loop_is_done(tmp_path: Path, fake_cli: Callable[..., FakeCli]) -> None:
    cli = fake_cli()
    work, sdk = tmp_path / "work", tmp_path / "sdk"
    project = work / "project"
    model = scripted([*loop(project, sdk), *done_files(work), "DONE: green, PASS"])
    events = list(_agent(model, work, sdk).stream(spec=SPEC))
    result = events[-1].result
    assert result is not None
    assert result.status == "done"
    assert result.loop is not None and result.loop.green(with_sdk=True)
    assert result.loop.exit_codes() == {"validate": 0, "generate": 0, "build": 0, "test": 0}
    assert result.loop_runs == 1
    assert result.project == project
    assert result.evaluation == "pass"
    assert result.message == "DONE: green, PASS"
    assert [c[c.index("--json") + 1] for c in cli.calls()] == [
        "validate",
        "generate",
        "build",
        "test",
    ]
    for name in ("validate", "generate", "build", "test"):
        kinds = {e.kind for e in events if name in e.message}
        assert {"step", "command", "envelope"} <= kinds, name
    assert [e.message for e in events if e.kind == "loop"] == ["loop run 1: green"]
    assert events[-1].kind == "done"


def test_a_failed_run_then_a_fix_is_two_loop_runs(
    tmp_path: Path, fake_cli: Callable[..., FakeCli]
) -> None:
    fake_cli({"validate": [3, 0]})
    work, sdk = tmp_path / "work", tmp_path / "sdk"
    project = work / "project"
    first = step(call("execute", command=f"mmt-plugin -C {project} --json validate --sdk {sdk}"))
    model = scripted([first, *loop(project, sdk), *done_files(work), "DONE"])
    events = list(_agent(model, work, sdk).stream(spec=SPEC))
    result = events[-1].result
    assert result is not None and result.status == "done"
    assert result.loop_runs == 2
    assert [e.message for e in events if e.kind == "loop"] == [
        "loop run 1: not green",
        "loop run 2: green",
    ]
    assert result.commands[0].to_json()["error_code"] == "model.schema"


def test_a_loop_that_stays_red_is_not_green(
    tmp_path: Path, fake_cli: Callable[..., FakeCli]
) -> None:
    fake_cli({"test": [6]})
    work, sdk = tmp_path / "work", tmp_path / "sdk"
    model = scripted([*loop(work / "project", sdk), "NOT GREEN: test fails"])
    result = _agent(model, work, sdk).new(spec=SPEC)
    assert result.status == "not_green"
    assert result.loop is not None
    assert result.loop.test_summary() == {"total": 2, "passed": 1, "failed": 1}
    assert result.ok is False


def test_without_an_sdk_validate_and_generate_are_the_loop(
    tmp_path: Path, fake_cli: Callable[..., FakeCli]
) -> None:
    fake_cli()
    work = tmp_path / "work"
    project = work / "project"
    model = scripted(
        [
            step(call("execute", command=f"mmt-plugin -C {project} --json validate --no-sdk")),
            step(call("execute", command=f"mmt-plugin -C {project} --json generate")),
            *done_files(work, verdict=None),
            "DONE without an SDK",
        ]
    )
    result = PluginAgent(model, work_dir=work).new(spec=SPEC)
    assert result.status == "done"
    assert result.unchecked == ["build and test: no SDK", "evaluation: not done (no capture)"]


def test_anew_runs_the_same_loop(tmp_path: Path, fake_cli: Callable[..., FakeCli]) -> None:
    fake_cli()
    work, sdk = tmp_path / "work", tmp_path / "sdk"
    model = scripted([*loop(work / "project", sdk), *done_files(work), "DONE"])
    result = asyncio.run(_agent(model, work, sdk).anew(spec=SPEC))
    assert result.status == "done"
    assert result.loop_runs == 1


def test_an_update_runs_on_the_project_in_place(
    tmp_path: Path, fake_cli: Callable[..., FakeCli]
) -> None:
    fake_cli()
    project = tmp_path / "telem"
    project.mkdir()
    (project / "plugin.yaml").write_text("protocol:\n  label: telem\n")
    sdk = tmp_path / "sdk"
    work = tmp_path / "telem-work"
    model = scripted([*loop(project, sdk), *done_files(work), "DONE"])
    result = PluginAgent(model, sdk=sdk).update(project, change="add a status message")
    assert result.work == work
    assert result.project == project
    assert result.status == "done"
    first = model.seen[0]
    assert any("add a status message" in str(m.content) for m in first)


@pytest.mark.parametrize(
    ("reply", "report", "status"),
    [
        ("BLOCKED: the project's plugin.lock is a directory", "# Report\n", "blocked"),
        ("DONE: green, PASS", "cyberlab: Result: BLOCKED (no Docker), synthetic\n", "done"),
    ],
)
def test_blocked_is_the_final_reply_not_a_word_of_the_report(
    tmp_path: Path, fake_cli: Callable[..., FakeCli], reply: str, report: str, status: str
) -> None:
    fake_cli()
    work, sdk = tmp_path / "work", tmp_path / "sdk"
    files = done_files(work)
    report_step = step(call("write_file", file_path=str(work / "REPORT.md"), content=report))
    model = scripted([*loop(work / "project", sdk), *files, report_step, reply])
    agent = PluginAgent(model, sdk=sdk, work_dir=work, allow_synthetic=True)
    assert agent.new(spec=SPEC).status == status


def _env(command: str, code: int) -> str:
    return json.dumps({"schema_version": 1, "command": command, "exit_code": code}) + "\n"


def test_a_piped_command_has_mmt_plugins_exit_code() -> None:
    piped = CommandRecord("mmt-plugin --json test | tee t.json", 0, _env("test", 6))
    assert piped.exit_code == 0 and piped.mmt_exit_code == 6
    silent = CommandRecord("mmt-plugin --json test > t.json", 6, "")
    assert silent.mmt_exit_code == 6


def test_a_loop_piped_through_tee_is_not_green_when_mmt_plugin_fails(
    tmp_path: Path, fake_cli: Callable[..., FakeCli]
) -> None:
    fake_cli({"test": [6]})
    work, sdk = tmp_path / "work", tmp_path / "sdk"
    project, saved = work / "project", tmp_path / "saved"
    saved.mkdir()
    model = scripted(
        [
            *(
                step(
                    call(
                        "execute",
                        command=f"mmt-plugin -C {project} --json {name} --sdk {sdk} "
                        f"| tee {saved / name}.json",
                    )
                )
                for name in ("validate", "generate", "build", "test")
            ),
            *done_files(work),
            "DONE",
        ]
    )
    events = list(_agent(model, work, sdk).stream(spec=SPEC))
    result = events[-1].result
    assert result is not None
    assert result.status == "not_green"
    assert result.loop is not None
    assert result.loop.exit_codes() == {"validate": 0, "generate": 0, "build": 0, "test": 6}
    assert [e.message for e in events if e.kind == "loop"] == ["loop run 1: not green"]


def _live_loop(work: Path, sdk: Path, n: int) -> list[dict[str, object]] | str:
    """A loop run as a live model wrote it: a variable, cd, a for loop, tee."""
    return step(
        call(
            "execute",
            command=f'P={work}; cd "$P/project" && mkdir -p ../runs/run-{n} && '
            "for c in validate generate build test; do "
            f"mmt-plugin -C . --json $c --sdk {sdk} | tee ../runs/run-{n}/$c.json; done",
        )
    )


def test_the_loop_is_the_work_folders_last_run(
    tmp_path: Path, fake_cli: Callable[..., FakeCli]
) -> None:
    fake_cli({"test": [6, 0]})
    work, sdk = tmp_path / "work", tmp_path / "sdk"
    model_yaml = step(
        call("write_file", file_path=str(work / "project/plugin.yaml"), content="schema: 1\n")
    )
    model = scripted(
        [
            model_yaml,
            _live_loop(work, sdk, 1),
            _live_loop(work, sdk, 2),
            *done_files(work),
            "DONE: green, PASS",
        ]
    )
    result = _agent(model, work, sdk).new(spec=SPEC)
    assert result.status == "done", result.to_json()
    assert result.project == work / "project"
    assert result.loop_runs == 2
    assert result.loop is not None
    assert result.loop.number == 2
    assert result.loop.exit_codes() == {"validate": 0, "generate": 0, "build": 0, "test": 0}
    assert result.loop.test_summary() == {"total": 2, "passed": 2, "failed": 0}
    assert result.to_json()["loop"]["project"] == str(work / "project")


def test_an_earlier_runs_envelopes_do_not_count(
    tmp_path: Path, fake_cli: Callable[..., FakeCli]
) -> None:
    fake_cli({"test": [6]})
    work, sdk = tmp_path / "work", tmp_path / "sdk"
    old = work / "runs" / "run-9"
    old.mkdir(parents=True)
    hour_ago = time.time() - 3600
    for name in ("validate", "generate", "build", "test"):
        (old / f"{name}.json").write_text(_env(name, 0))
        os.utime(old / f"{name}.json", (hour_ago, hour_ago))
    model = scripted([*loop(work / "project", sdk), "NOT GREEN: test fails"])
    result = _agent(model, work, sdk).new(spec=SPEC)
    assert result.status == "not_green"
    assert result.loop is not None and result.loop.exit_codes()["test"] == 6


def test_a_failed_run_over_an_earlier_green_one_is_not_green(
    tmp_path: Path, fake_cli: Callable[..., FakeCli]
) -> None:
    fake_cli({"validate": [0, 3]})
    work, sdk = tmp_path / "work", tmp_path / "sdk"
    old = work / "runs" / "run-2"
    old.mkdir(parents=True)
    hour_ago = time.time() - 3600
    for name in ("validate", "generate", "build", "test"):
        (old / f"{name}.json").write_text(_env(name, 0))
        os.utime(old / f"{name}.json", (hour_ago, hour_ago))
    model_yaml = step(
        call("write_file", file_path=str(work / "project/plugin.yaml"), content="schema: 1\n")
    )
    second = step(
        call(
            "execute",
            command=f'P={work}; cd "$P/project" && mmt-plugin -C . --json validate --sdk {sdk} '
            "| tee ../runs/run-2/validate.json",
        )
    )
    model = scripted([model_yaml, _live_loop(work, sdk, 1), second, "NOT GREEN"])
    result = _agent(model, work, sdk).new(spec=SPEC)
    assert result.status == "not_green"
    assert result.loop is not None
    assert result.loop.number == 2
    assert result.loop.exit_codes() == {"validate": 3}


def _vllm_shaped(root: Path) -> Path:
    """A work folder as a vLLM model left it: everything one level down, in
    the ``<label>-plugin/`` the skill names when no folder is given."""
    inner = root / "telem-plugin"
    run = inner / "runs" / "run-1"
    run.mkdir(parents=True)
    for name in ("validate", "generate", "build"):
        (run / f"{name}.json").write_text(_env(name, 0))
    summary = {"total": 2, "passed": 2, "failed": 0}
    (run / "test.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "command": "test",
                "exit_code": 0,
                "result": {"summary": summary},
            }
        )
    )
    (inner / "project").mkdir()
    (inner / "project" / "plugin.yaml").write_text("schema: 1\n")
    (inner / "REPORT.md").write_text("# Report\n")
    manifest = {"schema": 1, "eval": {"verdict": "PASS", "drift": {"checked": True, "open": 0}}}
    (inner / "manifest.json").write_text(json.dumps(manifest))
    return inner


def test_a_work_folder_one_level_down_is_the_work_folder(tmp_path: Path) -> None:
    work = tmp_path / "run"
    inner = _vllm_shaped(work)
    (work / "questions.md").write_text("# Questions\n")
    assert work_folder(work) == inner
    result = build_result(
        thread_id="t",
        work=work,
        project=None,
        records=[],
        with_sdk=True,
        no_eval=False,
        message="DONE: green",
    )
    assert result.status == "done", result.to_json()
    assert result.work == inner
    assert result.project == inner / "project"
    assert result.report_path == inner / "REPORT.md"
    assert result.questions_path == work / "questions.md"
    assert result.loop is not None and result.loop.green(True)


def test_a_work_folder_is_not_looked_for_below_when_it_is_one_or_ambiguous(
    tmp_path: Path,
) -> None:
    work = tmp_path / "run"
    _vllm_shaped(work)
    (work / "runs").mkdir()
    assert work_folder(work) == work
    other = tmp_path / "two"
    _vllm_shaped(other)
    (other / "second" / "runs").mkdir(parents=True)
    assert work_folder(other) == other
    assert work_folder(tmp_path / "missing") == tmp_path / "missing"
    empty = tmp_path / "empty"
    (empty / "project").mkdir(parents=True)
    assert work_folder(empty) == empty


@pytest.mark.parametrize(
    ("capture", "allow_synthetic", "leave", "flag"),
    [(True, False, "capture", "--capture"), (False, True, "synthetic", "--allow-synthetic")],
)
def test_green_with_leave_and_no_evaluation_is_the_models_skip(
    tmp_path: Path, capture: bool, allow_synthetic: bool, leave: str, flag: str
) -> None:
    """N6: the result knows the run had a capture or leave for a synthetic
    one, so an evaluation not done is not ok and says why."""
    inner = _vllm_shaped(tmp_path / "run")
    (inner / "manifest.json").write_text(json.dumps({"schema": 1}))
    result = build_result(
        thread_id="t",
        work=inner,
        project=None,
        records=[],
        with_sdk=True,
        no_eval=False,
        message="DONE: green",
        capture=capture,
        allow_synthetic=allow_synthetic,
    )
    assert result.status == "incomplete", result.to_json()
    assert result.eval_leave == leave and result.skipped_with_leave
    assert result.ok is False
    assert result.unchecked == [
        f"evaluation: not done (the model skipped the evaluation it had leave for ({flag}))"
    ]
    assert result.to_json()["eval_leave"] == leave


def test_without_leave_no_evaluation_is_still_incomplete_and_ok(tmp_path: Path) -> None:
    inner = _vllm_shaped(tmp_path / "run")
    (inner / "manifest.json").write_text(json.dumps({"schema": 1}))
    kwargs: dict[str, Any] = {"thread_id": "t", "work": inner, "project": None, "records": []}
    result = build_result(**kwargs, with_sdk=True, no_eval=False, message="DONE")
    assert (result.status, result.ok, result.eval_leave) == ("incomplete", True, None)
    reason = "no capture, and no leave for a synthetic one"
    assert result.unchecked == [f"evaluation: not done ({reason})"]
    skipped = build_result(
        **kwargs, with_sdk=True, no_eval=True, message="DONE", allow_synthetic=True
    )
    assert (skipped.status, skipped.ok, skipped.eval_leave) == ("done", True, None)
