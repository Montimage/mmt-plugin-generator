"""A scripted model drives the skill's loop through the graph against a fake
mmt-plugin: the result is the loop the shell saw, and ``stream()`` yields
events for every loop command (P7)."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from pathlib import Path

import pytest

from mmt_plugin_agent import PluginAgent

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
