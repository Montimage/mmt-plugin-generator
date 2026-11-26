"""Regression tests for the trusted-execution evidence model (R1):
cwd shadowing of ``python -m``, the envelope requirement, the project
the loop targets, and the evaluation script's protected path."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from mmt_plugin_agent.backend import evaluation_script_ok, mmt_plugin_argv
from mmt_plugin_agent.result import CommandRecord, build_result
from mmt_plugin_agent.skills import EvaluationCode


def _real(path: Path) -> Path:
    import os

    return Path(os.path.realpath(path))


def _env(command: str, code: int, summary: dict[str, int] | None = None) -> str:
    env: dict[str, Any] = {"schema_version": 1, "command": command, "exit_code": code}
    if summary is not None:
        env["result"] = {"summary": summary}
    if command == "validate":
        checks = [{"id": "parents-exist", "status": "pass" if code == 0 else "fail"}]
        env["result"] = {**env.get("result", {}), "checks": checks}
    return json.dumps(env) + "\n"


def _green(project: Path, **record_kwargs: Any) -> list[CommandRecord]:
    """A green loop of trusted records targeting ``project``, in the exact
    shapes the backend binds: the run's SDK, its compiler on build and test."""
    passed = {"total": 2, "passed": 2, "failed": 0}
    base = {"trusted": True, **record_kwargs}
    return [
        *(
            CommandRecord(
                f"mmt-plugin -C {project} --json {name} --sdk /sdk"
                + (" --cc gcc" if name in ("build", "test") else ""),
                0,
                _env(name, 0),
                **base,
            )
            for name in ("validate", "generate", "build")
        ),
        CommandRecord(
            f"mmt-plugin -C {project} --json test --sdk /sdk --cc gcc",
            0,
            _env("test", 0, passed),
            **base,
        ),
    ]


def test_python_m_ignores_a_shadowing_package_in_the_workdir(tmp_path: Path) -> None:
    """R1.1: ``python -m`` puts the cwd on sys.path, so a model-written
    ``mmt_plugin`` package in the work folder would replace the trusted
    implementation; the isolated interpreter never looks there."""
    shadow = tmp_path / "mmt_plugin"
    shadow.mkdir()
    (shadow / "__init__.py").write_text("")
    (shadow / "__main__.py").write_text('print("shadowed")\n')
    argv = mmt_plugin_argv()
    assert "-I" in argv
    ran = subprocess.run([*argv, "--help"], cwd=tmp_path, capture_output=True, text=True)
    assert "shadowed" not in ran.stdout + ran.stderr
    # Without isolation the reproduction holds: the shadow wins.
    plain = subprocess.run(
        [sys.executable, "-m", "mmt_plugin"], cwd=tmp_path, capture_output=True, text=True
    )
    assert "shadowed" in plain.stdout


def test_a_trusted_exit_0_without_an_envelope_is_unknown(tmp_path: Path) -> None:
    """R1.2: ``mmt-plugin validate --help`` exits 0 and validates nothing;
    without ``--json`` there is no envelope either. Neither is evidence."""
    work = tmp_path / "work"
    project = work / "project"
    helpful = CommandRecord(f"mmt-plugin -C {project} --json validate --help", 0, "", trusted=True)
    plain = CommandRecord(f"mmt-plugin -C {project} validate", 0, "validate: ok\n", trusted=True)
    for record in (helpful, plain):
        assert record.mmt_exit_code is None
    records = [
        helpful,
        *_green(project)[1:],
    ]
    result = build_result(
        thread_id="t",
        work=work,
        project=None,
        records=records,
        with_sdk=True,
        no_eval=True,
        message="DONE",
    )
    assert result.status == "not_green", result.to_json()


def test_a_trusted_envelope_must_match_the_process_exit_code(tmp_path: Path) -> None:
    """R1.2: the envelope's command and exit code must be the execution's;
    a mismatch is unknown, never a success."""
    work = tmp_path / "work"
    project = work / "project"
    mismatched = CommandRecord(
        f"mmt-plugin -C {project} --json validate", 0, _env("validate", 3), trusted=True
    )
    wrong_command = CommandRecord(
        f"mmt-plugin -C {project} --json validate", 0, _env("generate", 0), trusted=True
    )
    assert mismatched.mmt_exit_code is None
    assert wrong_command.mmt_exit_code is None
    good = CommandRecord(
        f"mmt-plugin -C {project} --json validate", 3, _env("validate", 3), trusted=True
    )
    assert good.mmt_exit_code == 3, "a matching failure envelope is evidence of failure"
    green = CommandRecord(
        f"mmt-plugin -C {project} --json validate", 0, _env("validate", 0), trusted=True
    )
    assert green.mmt_exit_code == 0


def test_a_loop_of_another_project_is_no_evidence(tmp_path: Path) -> None:
    """R1.3: every loop command must target the run's project: a green loop
    of a fixture project elsewhere proves nothing of this one."""
    work = tmp_path / "work"
    (work / "project").mkdir(parents=True)
    other = tmp_path / "other"
    other.mkdir()
    result = build_result(
        thread_id="t",
        work=work,
        project=None,
        records=_green(other),
        with_sdk=True,
        no_eval=True,
        message="DONE",
    )
    assert result.status == "not_green", result.to_json()
    assert result.loop is None
    # The right project, spelled absolutely or relative to the work folder.
    absolute = build_result(
        thread_id="t",
        work=work,
        project=None,
        records=_green(work / "project"),
        with_sdk=True,
        no_eval=True,
        message="DONE",
    )
    assert absolute.status == "done", absolute.to_json()
    relative = [
        CommandRecord(
            r.command.replace(str(work / "project"), "project"),
            r.exit_code,
            r.output,
            trusted=True,
        )
        for r in _green(work / "project")
    ]
    spelled = build_result(
        thread_id="t",
        work=work,
        project=None,
        records=relative,
        with_sdk=True,
        no_eval=True,
        message="DONE",
    )
    assert spelled.status == "done", spelled.to_json()


def test_an_update_enforces_the_given_project(tmp_path: Path) -> None:
    """R1.3: in an update the project is the one the caller gave, wherever
    it is; the default ``<work>/project`` does not count then."""
    work = tmp_path / "work"
    given = tmp_path / "elsewhere"
    given.mkdir()
    wrong = build_result(
        thread_id="t",
        work=work,
        project=given,
        records=_green(work / "project"),
        with_sdk=True,
        no_eval=True,
        message="DONE",
    )
    assert wrong.status == "not_green"
    right = build_result(
        thread_id="t",
        work=work,
        project=given,
        records=_green(given),
        with_sdk=True,
        no_eval=True,
        message="DONE",
    )
    assert right.status == "done", right.to_json()


def test_the_evaluation_script_must_be_the_skills_copy(tmp_path: Path) -> None:
    """R1.4: the strict evaluation runs the skill's own script, resolved
    inside the read-only skills copy; a copy elsewhere is not trusted."""
    protected = tmp_path / "skills-copy"
    script = protected / "mmt-plugin-generator" / "scripts" / "pcap_eval.py"
    script.parent.mkdir(parents=True)
    script.write_text("print(1)\n")
    runner = script.parent / "pcap_eval.c"
    runner.write_text("/* the runner */\n")
    original = EvaluationCode(script=b"print(1)\n", runner=b"/* the runner */\n")
    assert evaluation_script_ok(_real(script), [_real(protected)], original)
    assert not evaluation_script_ok(_real(script), [_real(protected)])
    changed = EvaluationCode(script=b"print(2)\n", runner=b"/* the runner */\n")
    assert not evaluation_script_ok(_real(script), [_real(protected)], changed)
    # So is a changed C runner next to the unchanged script: the script
    # compiles it, so its bytes are as much the evidence as the script's.
    changed_runner = EvaluationCode(script=b"print(1)\n", runner=b"/* planted */\n")
    assert not evaluation_script_ok(_real(script), [_real(protected)], changed_runner)
    runner.unlink()
    assert not evaluation_script_ok(_real(script), [_real(protected)], original)
    runner.write_text("/* the runner */\n")
    outside = tmp_path / "scripts" / "pcap_eval.py"
    outside.parent.mkdir()
    outside.write_text("print(1)\n")
    assert not evaluation_script_ok(_real(outside), [_real(protected)], original)
    # A symlink inside the copy pointing outside resolves outside too.
    link = protected / "mmt-plugin-generator" / "scripts" / "link.py"
    try:
        link.symlink_to(outside)
    except OSError:
        return
    assert not evaluation_script_ok(_real(link), [_real(protected)], original)
