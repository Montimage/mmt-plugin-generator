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

from mmt_plugin_agent import PluginAgent, request_text
from mmt_plugin_agent.result import CommandRecord, build_result, work_folder

from .fakes import FakeCli, ScriptedModel, call, done_files, evaluate, loop, scripted, step

SPEC = Path(__file__).resolve().parents[3] / (
    "skills/mmt-plugin-generator/evals/cases/spec-telem/spec.md"
)


def _agent(model: ScriptedModel, work: Path, sdk: Path) -> PluginAgent:
    return PluginAgent(model, sdk=sdk, work_dir=work, allow_synthetic=True)


def test_a_green_loop_is_done(tmp_path: Path, fake_cli: Callable[..., FakeCli]) -> None:
    cli = fake_cli()
    work, sdk = tmp_path / "work", tmp_path / "sdk"
    project = work / "project"
    model = scripted(
        [*loop(project, sdk), evaluate(work, sdk), *done_files(work), "DONE: green, PASS"]
    )
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
    model = scripted([first, *loop(project, sdk), evaluate(work, sdk), *done_files(work), "DONE"])
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
            step(
                call(
                    "execute",
                    command=f"mmt-plugin -C {project} --json validate "
                    "--no-sdk --sdk-profile 1.10.2",
                )
            ),
            step(
                call(
                    "execute",
                    command=f"mmt-plugin -C {project} --json generate --sdk-profile 1.10.2",
                )
            ),
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
    model = scripted(
        [*loop(work / "project", sdk), evaluate(work, sdk), *done_files(work), "DONE"]
    )
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
    model = scripted(
        [
            *loop(project, sdk),
            evaluate(work, sdk, project=project),
            *done_files(work),
            "DONE",
        ]
    )
    result = PluginAgent(model, sdk=sdk, allow_synthetic=True).update(
        project, change="add a status message"
    )
    assert result.work == work
    assert result.project == project
    assert result.status == "done"
    first = model.seen[0]
    assert any("add a status message" in str(m.content) for m in first)


def test_a_change_text_too_long_for_a_path_is_text(
    tmp_path: Path, fake_cli: Callable[..., FakeCli]
) -> None:
    fake_cli()
    project = tmp_path / "telem"
    project.mkdir()
    (project / "plugin.yaml").write_text("protocol:\n  label: telem\n")
    sdk = tmp_path / "sdk"
    change = "add a status message " * 20
    assert len(change) > 255
    model = scripted(
        [
            *loop(project, sdk),
            evaluate(tmp_path / "telem-work", sdk, project=project),
            *done_files(tmp_path / "telem-work"),
            "DONE",
        ]
    )
    result = PluginAgent(model, sdk=sdk, allow_synthetic=True).update(project, change=change)
    assert result.status == "done"
    assert any(f"this change: {change}" in str(m.content) for m in model.seen[0])
    assert request_text(project=project, change="a\0b").endswith("this change: a\0b.")
    described = tmp_path / "change.md"
    described.write_text("add a status message\n")
    assert f"the change described in {described}" in request_text(
        project=project, change=str(described)
    )


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
    model = scripted(
        [*loop(work / "project", sdk), evaluate(work, sdk), *files, report_step, reply]
    )
    agent = PluginAgent(model, sdk=sdk, work_dir=work, allow_synthetic=True)
    assert agent.new(spec=SPEC).status == status


def _env(command: str, code: int, summary: dict[str, int] | None = None) -> str:
    env: dict[str, Any] = {"schema_version": 1, "command": command, "exit_code": code}
    if summary is not None:
        env["result"] = {"summary": summary}
    if command == "validate":
        checks = [{"id": "parents-exist", "status": "pass" if code == 0 else "fail"}]
        env["result"] = {**env.get("result", {}), "checks": checks}
    return json.dumps(env) + "\n"


def test_a_piped_command_has_mmt_plugins_exit_code() -> None:
    piped = CommandRecord("mmt-plugin --json test | tee t.json", 0, _env("test", 6))
    assert piped.exit_code == 0 and piped.mmt_exit_code == 6
    silent = CommandRecord("mmt-plugin --json test > t.json", 6, "")
    assert silent.mmt_exit_code == 6


def test_without_an_envelope_a_zero_shell_exit_is_unknown_not_success() -> None:
    """The shell's exit 0 is never mmt-plugin's success on its own: the
    envelope may be in a redirected file, lost in a pipe, or the success of
    another command of the chain."""
    redirected = CommandRecord("mmt-plugin --json validate > validate.json", 0, "")
    assert redirected.exit_code == 0 and redirected.mmt_exit_code is None
    piped = CommandRecord("timeout 900 mmt-plugin --json test | tee t.json >/dev/null", 0, "")
    assert piped.mmt_exit_code is None
    plain = CommandRecord("mmt-plugin --json validate", 0, "")
    assert plain.mmt_exit_code is None
    failed = CommandRecord("timeout 900 mmt-plugin --json validate", 124, "")
    assert failed.mmt_exit_code == 124


def test_a_loop_without_envelopes_is_not_green_at_shell_exit_0(
    tmp_path: Path, fake_cli: Callable[..., FakeCli]
) -> None:
    """R2: `timeout ... | tee` with the envelope lost down the pipe: the
    shell's exit 0 is never mmt-plugin's success on its own."""
    fake_cli()
    work, sdk = tmp_path / "work", tmp_path / "sdk"
    project = work / "project"
    model = scripted(
        [
            *(
                step(
                    call(
                        "execute",
                        command=f"timeout 900 mmt-plugin -C {project} --json {name} --sdk {sdk} "
                        "| tee /dev/null >/dev/null",
                    )
                )
                for name in ("validate", "generate", "build", "test")
            ),
            "DONE: green",
        ]
    )
    result = _agent(model, work, sdk).new(spec=SPEC)
    assert result.status == "not_green", result.to_json()
    assert result.loop is None, "untrusted shell evidence counts for nothing"


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
                        command=f"mmt-plugin -C {project} --json {name} --sdk {sdk}"
                        + (" --cc gcc" if name in ("build", "test") else "")
                        + f" | tee {saved / name}.json",
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


def _live_loop(work: Path, sdk: Path, n: int) -> list[list[dict[str, Any]] | str]:
    """A loop run in the strict form the backend executes itself: one simple
    command per step, stdout tee'd to the run's folder (audit artifacts)."""
    project = work / "project"
    return [
        step(
            call(
                "execute",
                command=f"mmt-plugin -C {project} --json {name} --sdk {sdk}"
                + (" --cc gcc" if name in ("build", "test") else "")
                + f" | tee {work}/runs/run-{n}/{name}.json",
            )
        )
        for name in ("validate", "generate", "build", "test")
    ]


def test_the_loop_is_the_work_folders_last_run(
    tmp_path: Path, fake_cli: Callable[..., FakeCli]
) -> None:
    fake_cli({"test": [6, 0]})
    work, sdk = tmp_path / "work", tmp_path / "sdk"
    model_yaml = step(
        call(
            "write_file",
            file_path=str(work / "project/plugin.yaml"),
            content="schema: 1\nprotocol:\n  label: telem\n",
        )
    )
    model = scripted(
        [
            model_yaml,
            *_live_loop(work, sdk, 1),
            *_live_loop(work, sdk, 2),
            evaluate(work, sdk),
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
        call(
            "write_file",
            file_path=str(work / "project/plugin.yaml"),
            content="schema: 1\nprotocol:\n  label: telem\n",
        )
    )
    second = step(
        call(
            "execute",
            command=f"mmt-plugin -C {work}/project --json validate --sdk {sdk} "
            f"| tee {work}/runs/run-2/validate.json",
        )
    )
    model = scripted([model_yaml, *_live_loop(work, sdk, 1), second, "NOT GREEN"])
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


def _shell_green(project: Path) -> list[CommandRecord]:
    """A green loop as the backend's trusted executions record it: each
    command in the strict form, targeting the run's project, its envelope
    in its output."""
    passed = {"total": 2, "passed": 2, "failed": 0}
    return [
        *(
            CommandRecord(
                f"mmt-plugin -C {project} --json {name} --sdk /sdk"
                + (" --cc gcc" if name in ("build", "test") else ""),
                0,
                _env(name, 0),
                trusted=True,
            )
            for name in ("validate", "generate", "build")
        ),
        CommandRecord(
            f"mmt-plugin -C {project} --json test --sdk /sdk --cc gcc",
            0,
            _env("test", 0, passed),
            trusted=True,
        ),
    ]


def _window(command: str, seconds: float = 60.0, evaluation: bool = False) -> CommandRecord:
    """A shell record invoking mmt-plugin, with a window around ``now``."""
    now = time.time_ns()
    return CommandRecord(
        command,
        0,
        "",
        started_ns=now - int(seconds * 10**9),
        ended_ns=now,
        trusted=True,
        evaluation=evaluation,
    )


def test_a_work_folder_one_level_down_is_the_work_folder(tmp_path: Path) -> None:
    work = tmp_path / "run"
    inner = _vllm_shaped(work)
    (work / "questions.md").write_text("# Questions\n")
    assert work_folder(work) == inner
    result = build_result(
        thread_id="t",
        work=work,
        project=None,
        records=[
            *_shell_green(inner / "project"),
            _window("python3 x/pcap_eval.py --out eval", evaluation=True),
        ],
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


def test_artifacts_alone_never_make_a_green_loop(tmp_path: Path) -> None:
    """R1: a model that writes runs/, manifest.json and REPORT.md with the
    file tools, without running mmt-plugin at all, is not done."""
    inner = _vllm_shaped(tmp_path / "run")
    result = build_result(
        thread_id="t",
        work=inner,
        project=None,
        records=[],
        with_sdk=True,
        no_eval=False,
        message="DONE: green, PASS",
    )
    assert result.status == "not_green", result.to_json()
    assert result.loop is None and result.loop_runs == 0
    assert result.evaluation == "not_done"
    assert result.unchecked == [
        "evaluation: not done (manifest.json's PASS is the model's say-so: "
        "no trusted run of the capture evaluation (pcap_eval.py) of the green "
        "build reached exit 0)"
    ]


def test_artifacts_written_by_a_shell_without_mmt_plugin_are_no_evidence(
    tmp_path: Path,
) -> None:
    """R1: envelopes written by echo or heredoc, in a shell that never
    invokes mmt-plugin, corroborate nothing."""
    inner = _vllm_shaped(tmp_path / "run")
    now = time.time_ns()
    forged = CommandRecord(
        "mkdir -p runs/run-1 && cat > runs/run-1/validate.json <<'EOF'\n{}\nEOF",
        0,
        "",
        started_ns=now - 30 * 10**9,
        ended_ns=now,
    )
    result = build_result(
        thread_id="t",
        work=inner,
        project=None,
        records=[forged],
        with_sdk=True,
        no_eval=False,
        message="DONE",
    )
    assert result.status == "not_green"
    assert result.loop is None


def test_artifacts_corroborated_by_an_mmt_plugin_window_are_the_loop(
    tmp_path: Path,
) -> None:
    """R1, the bypass: a shell loop over ``$c`` invokes mmt-plugin while the
    envelopes are written, but it is not the strict form — the backend does
    not execute it, so the artifacts are the model's word, never evidence."""
    inner = _vllm_shaped(tmp_path / "run")
    (inner / "manifest.json").write_text(json.dumps({"schema": 1}))
    window = _window(
        "for c in validate generate build test; do "
        "mmt-plugin -C . --json $c | tee ../runs/run-1/$c.json; done"
    )
    window.trusted = False
    result = build_result(
        thread_id="t",
        work=inner,
        project=None,
        records=[window],
        with_sdk=True,
        no_eval=True,
        message="DONE",
    )
    assert result.status == "not_green", result.to_json()
    assert result.loop is None


def test_a_saved_envelope_the_shell_contradicts_is_never_a_success(
    tmp_path: Path,
) -> None:
    """R1, the forged-overwrite bypass: one shell command runs a real but
    failing validate, then overwrites the envelope with a forged success —
    not the strict form, so neither its text nor the artifacts count."""
    inner = _vllm_shaped(tmp_path / "run")
    shell = CommandRecord(
        "mmt-plugin -C project --json validate --sdk s | tee ../runs/run-1/validate.json; "
        "echo '{\"exit_code\": 0}' > runs/run-1/validate.json",
        0,
        _env("validate", 3),
        started_ns=time.time_ns() - 30 * 10**9,
        ended_ns=time.time_ns(),
    )
    assert shell.trusted is False
    result = build_result(
        thread_id="t",
        work=inner,
        project=None,
        records=[shell],
        with_sdk=True,
        no_eval=False,
        message="DONE",
    )
    assert result.status == "not_green", result.to_json()
    assert result.loop is None


def test_an_envelope_echoed_in_untrusted_shell_text_is_no_evidence(tmp_path: Path) -> None:
    """R1: a model can print any envelope with echo or a heredoc: envelopes
    in untrusted shell output never make a loop green."""
    inner = _vllm_shaped(tmp_path / "run")
    forged = [
        CommandRecord(f"echo x; mmt-plugin --json {name} | tee t", 0, _env(name, 0), trusted=False)
        for name in ("validate", "generate", "build", "test")
    ]
    result = build_result(
        thread_id="t",
        work=inner,
        project=None,
        records=forged,
        with_sdk=True,
        no_eval=True,
        message="DONE",
    )
    assert result.status == "not_green", result.to_json()
    assert result.loop is None


def test_a_shadowing_or_indirect_invocation_is_no_evidence(tmp_path: Path) -> None:
    """R1: the trusted execution never comes from the PATH or the work
    folder: a copied or shadowed ``mmt-plugin`` of the model's is shell
    text, and an indirect ``sh -c`` is not the strict form either."""
    inner = _vllm_shaped(tmp_path / "run")
    shadowed = [
        CommandRecord(f"./mmt-plugin --json {name}", 0, _env(name, 0))
        for name in ("validate", "generate", "build")
    ]
    indirect = CommandRecord("sh -c 'mmt-plugin --json test'", 0, _env("test", 0))
    result = build_result(
        thread_id="t",
        work=inner,
        project=None,
        records=[*shadowed, indirect],
        with_sdk=True,
        no_eval=True,
        message="DONE",
    )
    assert result.status == "not_green"
    assert result.loop is None


def test_a_green_loop_is_done_when_the_evaluation_ran(tmp_path: Path) -> None:
    inner = _vllm_shaped(tmp_path / "run")
    records = [
        *_shell_green(inner / "project"),
        _window("python3 skill/scripts/pcap_eval.py --out eval", evaluation=True),
    ]
    result = build_result(
        thread_id="t",
        work=inner,
        project=None,
        records=records,
        with_sdk=True,
        no_eval=False,
        message="DONE",
    )
    assert result.status == "done" and result.evaluation == "pass", result.to_json()


def test_a_manifest_pass_without_the_evaluation_run_is_not_done(tmp_path: Path) -> None:
    """R1: manifest.json is the model's to write: its PASS needs the shell's
    record of pcap_eval.py passing."""
    inner = _vllm_shaped(tmp_path / "run")
    result = build_result(
        thread_id="t",
        work=inner,
        project=None,
        records=_shell_green(inner / "project"),
        with_sdk=True,
        no_eval=False,
        message="DONE",
        allow_synthetic=True,
    )
    assert result.status == "incomplete", result.to_json()
    assert result.evaluation == "not_done"
    assert result.unchecked == [
        "evaluation: not done (manifest.json's PASS is the model's say-so: "
        "no trusted run of the capture evaluation (pcap_eval.py) of the green "
        "build reached exit 0)"
    ]
    # A trusted evaluation the backend ran to exit 1 is the evaluation's
    # own FAIL verdict — never anything manifest.json says.
    failed = _window("python3 x/pcap_eval.py --out eval", evaluation=True)
    failed.exit_code = 1
    result = build_result(
        thread_id="t",
        work=inner,
        project=None,
        records=[*_shell_green(inner / "project"), failed],
        with_sdk=True,
        no_eval=False,
        message="DONE",
    )
    assert result.evaluation == "fail"
    assert result.status == "eval_failed"


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
        records=_shell_green(inner / "project"),
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
    kwargs: dict[str, Any] = {
        "thread_id": "t",
        "work": inner,
        "project": None,
        "records": _shell_green(inner / "project"),
    }
    result = build_result(**kwargs, with_sdk=True, no_eval=False, message="DONE")
    assert (result.status, result.ok, result.eval_leave) == ("incomplete", True, None)
    reason = "no capture, and no leave for a synthetic one"
    assert result.unchecked == [f"evaluation: not done ({reason})"]
    skipped = build_result(
        **kwargs, with_sdk=True, no_eval=True, message="DONE", allow_synthetic=True
    )
    assert (skipped.status, skipped.ok, skipped.eval_leave) == ("done", True, None)
