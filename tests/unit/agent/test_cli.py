"""``mmt-plugin-agent``: its envelope against the shipped schemas, the
doctor (AC7), the CLI against the API (AC9), interactive answers on the
terminal, and that it calls only the public API (AC11)."""

from __future__ import annotations

import ast
import io
import json
from collections.abc import Callable, Generator
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

import mmt_plugin_agent
import mmt_plugin_agent.models
from mmt_plugin_agent import PluginAgent
from mmt_plugin_agent import cli as agent_cli

from .fakes import FakeCli, ScriptedModel, call, done_files, loop, scripted, step

PACKAGE = Path(mmt_plugin_agent.__file__).resolve().parent
SCHEMAS = PACKAGE / "schemas" / "v1"
SPEC = Path(__file__).resolve().parents[3] / (
    "skills/mmt-plugin-generator/evals/cases/spec-telem/spec.md"
)


def _schema(name: str) -> Draft202012Validator:
    return Draft202012Validator(json.loads((SCHEMAS / name).read_text("utf-8")))


def _main(args: list[str], capsys: pytest.CaptureFixture[str]) -> tuple[int, dict[str, Any]]:
    code = agent_cli.main(["--json", *args])
    out = capsys.readouterr().out
    envelope = json.loads(out)
    _schema("envelope.json").validate(envelope)
    assert envelope["exit_code"] == code
    return code, envelope


def _use(monkeypatch: pytest.MonkeyPatch, model: ScriptedModel) -> None:
    """The boundary: the provider string resolves to the scripted model."""
    real = mmt_plugin_agent.models.resolve_model
    monkeypatch.setattr(
        "mmt_plugin_agent.models.resolve_model",
        lambda spec: model if isinstance(spec, str) else real(spec),
    )


def _script(work: Path, sdk: Path) -> list[Any]:
    return [*loop(work / "project", sdk), *done_files(work), "DONE: green"]


def test_new_prints_its_result_in_one_envelope(
    tmp_path: Path,
    fake_cli: Callable[..., FakeCli],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    fake_cli()
    work, sdk = tmp_path / "w", tmp_path / "sdk"
    _use(monkeypatch, scripted(_script(work, sdk)))
    args = ["new", "--spec", str(SPEC), "--sdk", str(sdk), "--work", str(work)]
    code, envelope = _main([*args, "--model", "anthropic:any", "--unattended"], capsys)
    assert code == 0
    assert envelope["command"] == "new"
    _schema("result.json").validate(envelope["result"])
    assert envelope["result"]["status"] == "done"
    assert envelope["context"] == {"work": str(work), "thread_id": envelope["result"]["thread_id"]}


def test_the_cli_and_the_api_give_the_same_result(
    tmp_path: Path,
    fake_cli: Callable[..., FakeCli],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    fake_cli()
    sdk = tmp_path / "sdk"
    cli_work, api_work = tmp_path / "cli", tmp_path / "api"
    _use(monkeypatch, scripted(_script(cli_work, sdk)))
    args = ["new", "--spec", str(SPEC), "--sdk", str(sdk), "--work", str(cli_work)]
    _, envelope = _main([*args, "--model", "x:y", "--thread-id", "t1"], capsys)
    api = PluginAgent(scripted(_script(api_work, sdk)), sdk=sdk, work_dir=api_work)
    result = api.new(spec=SPEC, thread_id="t1").to_json()
    from_cli = json.loads(json.dumps(envelope["result"]).replace(str(cli_work), "<work>"))
    from_api = json.loads(json.dumps(result).replace(str(api_work), "<work>"))
    assert from_cli == from_api


@pytest.mark.parametrize(
    ("status_plan", "status", "code", "error"),
    [
        ({"test": [6]}, "not_green", 6, "agent.not-green"),
        ({}, "incomplete", 0, None),
    ],
)
def test_the_exit_code_follows_the_status(
    tmp_path: Path,
    fake_cli: Callable[..., FakeCli],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    status_plan: dict[str, list[int]],
    status: str,
    code: int,
    error: str | None,
) -> None:
    fake_cli(status_plan)
    work, sdk = tmp_path / "w", tmp_path / "sdk"
    _use(monkeypatch, scripted([*loop(work / "project", sdk), *done_files(work, None), "x"]))
    args = ["new", "--spec", str(SPEC), "--sdk", str(sdk), "--work", str(work), "--model", "a:b"]
    got, envelope = _main(args, capsys)
    assert (got, envelope["result"]["status"]) == (code, status)
    assert (envelope["error"] or {}).get("code") == error
    warnings = [d["code"] for d in envelope["diagnostics"]]
    assert warnings == (["agent.evaluation-not-done"] if status == "incomplete" else [])


def test_a_shell_that_could_read_the_agents_environment_is_a_warning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("mmt_plugin_agent.api.environ_failure", lambda: "prctl failed")
    work = tmp_path / "w"
    _use(monkeypatch, scripted(["NOT GREEN: nothing done"]))
    _, envelope = _main(
        ["new", "--spec", str(SPEC), "--work", str(work), "--model", "a:b"], capsys
    )
    assert envelope["result"]["environ_readable"] == "prctl failed"
    assert "agent.environ-readable" in [d["code"] for d in envelope["diagnostics"]]


@pytest.mark.parametrize(
    ("flag", "leave"), [("--allow-synthetic", "synthetic"), ("--capture", "capture")]
)
def test_a_green_run_that_skipped_the_evaluation_it_had_leave_for_fails(
    tmp_path: Path,
    fake_cli: Callable[..., FakeCli],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    flag: str,
    leave: str,
) -> None:
    """N6: with --capture or --allow-synthetic, a green run whose evaluation
    is not done is the model's skip, not a missing capture."""
    fake_cli()
    work, sdk = tmp_path / "w", tmp_path / "sdk"
    capture = tmp_path / "telem.pcap"
    capture.write_bytes(b"")
    _use(monkeypatch, scripted([*loop(work / "project", sdk), *done_files(work, None), "x"]))
    args = ["new", "--spec", str(SPEC), "--sdk", str(sdk), "--work", str(work), "--model", "a:b"]
    args += [flag, str(capture)] if flag == "--capture" else [flag]
    got, envelope = _main(args, capsys)
    result = envelope["result"]
    assert (got, result["status"], result["eval_leave"]) == (6, "incomplete", leave)
    assert envelope["error"]["code"] == "agent.evaluation-skipped"
    assert flag in envelope["error"]["message"]
    assert "--capture or --allow-synthetic" not in json.dumps(envelope)
    assert envelope["diagnostics"] == []
    assert result["unchecked"] == [
        f"evaluation: not done (the model skipped the evaluation it had leave for ({flag}): "
        "no capture)"
    ]


def test_interactive_reads_the_answer_on_the_terminal(
    tmp_path: Path,
    fake_cli: Callable[..., FakeCli],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    fake_cli()
    work, sdk = tmp_path / "w", tmp_path / "sdk"
    ask = step(call("ask_user", question="capture?", recommended="synthetic", kind="capture"))
    model = scripted([ask, *_script(work, sdk)])
    _use(monkeypatch, model)
    monkeypatch.setattr("sys.stdin", io.StringIO("use /data/t.pcap\n"))
    args = ["new", "--spec", str(SPEC), "--work", str(work), "--sdk", str(sdk)]
    args += ["--model", "a:b", "--interactive"]
    code = agent_cli.main(args)
    captured = capsys.readouterr()
    assert code == 0
    assert "capture?\nRecommended: synthetic" in captured.err
    assert model.tool_results()[0] == "use /data/t.pcap"


@pytest.mark.parametrize(
    ("args", "code", "error"),
    [
        (["new"], 2, "agent.usage"),
        (["new", "--spec", "a", "--pdl", "b"], 2, "agent.usage"),
        (["new", "--spec", "missing.md", "--model", "a:b"], 3, "agent.bad-input"),
        (["new", "--spec", str(SPEC)], 2, "agent.no-model"),
        (["new", "--spec", str(SPEC), "--model", "noprovider"], 2, "agent.bad-model"),
        (["update", "nowhere", "--change", "x", "--model", "a:b"], 3, "agent.bad-input"),
        (["new", "--spec", str(SPEC), "--model", "a:b", "--skills", "nowhere"], 4, None),
    ],
)
def test_each_failure_has_its_class_and_code(
    args: list[str], code: int, error: str | None, capsys: pytest.CaptureFixture[str]
) -> None:
    got, envelope = _main(args, capsys)
    assert got == code
    assert envelope["error"]["code"] == (error or "agent.skills-not-found")
    assert envelope["error"]["hint"]


def test_the_version_needs_no_run(capsys: pytest.CaptureFixture[str]) -> None:
    code, envelope = _main(["--version"], capsys)
    assert code == 0
    assert envelope["result"]["version"] == mmt_plugin_agent.__version__
    assert envelope["result"]["agent_extra"] is True


def test_doctor_reports_each_missing_dependency_with_a_hint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    empty = tmp_path / "empty-bin"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))
    monkeypatch.delenv("CYBERLAB_DIR", raising=False)
    code, envelope = _main(["doctor", "--skills", str(tmp_path / "none")], capsys)
    assert code == 4
    assert envelope["error"]["code"] == "agent.doctor-failed"
    checks = {c["id"]: c for c in envelope["result"]["checks"]}
    failed = {i for i, c in checks.items() if c["status"] == "fail"}
    assert failed == {"mmt-plugin", "skills", "model"}
    warned = {i for i, c in checks.items() if c["status"] == "warn"}
    assert {"tshark", "capinfos", "editcap", "mergecap", "libpcap", "cyberlab", "docker"} <= warned
    for check in checks.values():
        if check["status"] != "pass":
            assert check["hint"], check


def test_doctor_passes_its_own_checks_with_what_it_needs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for tool in ("mmt-plugin", "gcc"):
        (bin_dir / tool).write_text("#!/bin/sh\nexit 0\n")
        (bin_dir / tool).chmod(0o755)
    monkeypatch.setenv("PATH", str(bin_dir))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "not-printed")
    code, envelope = _main(["doctor", "--model", "anthropic:m"], capsys)
    checks = {c["id"]: c for c in envelope["result"]["checks"]}
    assert code == 0, checks
    assert checks["model"] == {
        "id": "model",
        "status": "pass",
        "detail": "anthropic:m",
        "hint": None,
    }
    assert "not-printed" not in json.dumps(envelope)
    assert checks["sdk"]["status"] == "warn"


def test_the_cli_imports_only_the_public_api() -> None:
    tree = ast.parse((PACKAGE / "cli.py").read_text("utf-8"))
    public = set(mmt_plugin_agent.__all__)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            if node.module.startswith("mmt_plugin_agent"):
                assert node.module == "mmt_plugin_agent", node.module
                assert {a.name for a in node.names} <= public
            elif node.module.startswith("mmt_plugin"):
                assert node.module == "mmt_plugin.exitcodes", node.module
        elif isinstance(node, ast.Import):
            assert not any(a.name.startswith("mmt_plugin") for a in node.names)


KEY = "your-key-placeholder-0123456789"


def _snapshots(tmp_path: Path) -> list[Path]:
    root = tmp_path / "cache" / "mmt-plugin-agent"
    return list(root.iterdir()) if root.is_dir() else []


def test_a_provider_error_is_still_one_envelope(
    tmp_path: Path,
    fake_cli: Callable[..., FakeCli],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    fake_cli()
    monkeypatch.setenv("ANTHROPIC_API_KEY", KEY)
    work, sdk = tmp_path / "w", tmp_path / "sdk"
    _use(monkeypatch, scripted([], fail=f"401 invalid x-api-key {KEY}"))
    args = ["new", "--spec", str(SPEC), "--sdk", str(sdk), "--work", str(work)]
    code = agent_cli.main(["--json", *args, "--model", "anthropic:any"])
    out = capsys.readouterr().out
    envelope = json.loads(out)
    _schema("envelope.json").validate(envelope)
    assert code == envelope["exit_code"] == 1
    assert envelope["error"]["class"] == "internal"
    assert envelope["error"]["code"] == "agent.unexpected"
    assert envelope["error"]["message"].startswith("RuntimeError: 401 invalid x-api-key")
    assert KEY not in out
    assert _snapshots(tmp_path) == []


def test_a_skills_change_is_reported_when_the_model_then_fails(
    tmp_path: Path,
    skills_copy: Path,
    fake_cli: Callable[..., FakeCli],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    fake_cli()
    skill = skills_copy / "mmt-plugin-generator/SKILL.md"
    before = skill.read_bytes()
    change = step(call("execute", command=f"echo changed >> {skill}"))
    _use(monkeypatch, scripted([change], fail="rate limited"))
    args = ["new", "--spec", str(SPEC), "--work", str(tmp_path / "w"), "--skills"]
    code, envelope = _main([*args, str(skills_copy), "--model", "a:b"], capsys)
    assert code == 6
    assert envelope["error"]["code"] == "agent.skills-modified"
    assert "mmt-plugin-generator/SKILL.md" in envelope["error"]["message"]
    assert "RuntimeError: rate limited" in envelope["error"]["message"]
    assert skill.read_bytes() == before
    assert _snapshots(tmp_path) == []


@pytest.mark.parametrize("given", ["flag", "env"])
def test_an_sdk_under_opt_mmt_is_refused_before_the_run(
    tmp_path: Path,
    fake_cli: Callable[..., FakeCli],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    given: str,
) -> None:
    fake_cli()
    model = scripted(["DONE"])
    _use(monkeypatch, model)
    args = ["new", "--spec", str(SPEC), "--work", str(tmp_path / "w"), "--model", "a:b"]
    if given == "flag":
        args += ["--sdk", "/opt/mmt"]
    else:
        monkeypatch.setenv("MMT_BASE", "/opt/mmt/dpi/..")
    code, envelope = _main(args, capsys)
    assert code == 4, envelope["error"]
    assert envelope["error"]["code"] == "agent.system-sdk"
    assert "private prefix" in envelope["error"]["hint"]
    assert model.seen == []


def test_doctor_fails_an_sdk_under_opt_mmt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for tool in ("mmt-plugin", "gcc"):
        (bin_dir / tool).write_text("#!/bin/sh\nexit 0\n")
        (bin_dir / tool).chmod(0o755)
    monkeypatch.setenv("PATH", str(bin_dir))
    code, envelope = _main(["doctor", "--sdk", "/opt/mmt", "--model", "a:b"], capsys)
    assert code == 4, envelope
    checks = {c["id"]: c for c in envelope["result"]["checks"]}
    assert checks["sdk"]["status"] == "fail"
    assert "private prefix" in checks["sdk"]["hint"]


def test_json_without_a_command_is_one_usage_envelope(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code, envelope = _main([], capsys)
    assert code == 2
    assert envelope["error"]["code"] == "agent.usage"
    assert envelope["error"]["message"] == "no command given"
    assert envelope["error"]["hint"] == "mmt-plugin-agent --help"


def test_stdin_ending_at_a_question_releases_the_run(
    tmp_path: Path,
    fake_cli: Callable[..., FakeCli],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    fake_cli()
    work = tmp_path / "w"
    ask = step(call("ask_user", question="capture?", recommended="synthetic", kind="capture"))
    _use(monkeypatch, scripted([ask, "DONE"]))
    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    args = ["new", "--spec", str(SPEC), "--work", str(work), "--model", "a:b", "--interactive"]
    code, envelope = _main(args, capsys)
    assert code == 2
    assert envelope["error"]["code"] == "agent.no-answer"
    assert _snapshots(tmp_path) == []


class _Interrupted(ScriptedModel):
    """Ctrl-C while the model's provider answers."""

    def _generate(self, *args: Any, **kwargs: Any) -> Any:
        raise KeyboardInterrupt


def test_ctrl_c_releases_the_run(
    tmp_path: Path,
    fake_cli: Callable[..., FakeCli],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    fake_cli()
    _use(monkeypatch, _Interrupted(scripts={"": []}))
    args = ["new", "--spec", str(SPEC), "--work", str(tmp_path / "w"), "--model", "a:b"]
    code, envelope = _main(args, capsys)
    assert code == 130
    assert envelope["error"]["code"] == "interrupted"
    assert _snapshots(tmp_path) == []


def test_a_consumer_that_stops_reading_releases_the_run(
    tmp_path: Path, fake_cli: Callable[..., FakeCli]
) -> None:
    fake_cli()
    model = scripted([step(call("execute", command="true")), "DONE"])
    agent = PluginAgent(model, work_dir=tmp_path / "w")
    events = agent.stream(spec=SPEC)
    assert isinstance(events, Generator)
    assert next(events).kind == "step"
    assert len(_snapshots(tmp_path)) == 1
    events.close()
    assert _snapshots(tmp_path) == []
    assert agent._runs == {}


def test_release_forgets_a_waiting_run(tmp_path: Path, fake_cli: Callable[..., FakeCli]) -> None:
    fake_cli()
    ask = step(call("ask_user", question="capture?", recommended="synthetic", kind="capture"))
    agent = PluginAgent(scripted([ask, "DONE"]), work_dir=tmp_path / "w", mode="interactive")
    result = agent.new(spec=SPEC)
    assert result.status == "waiting"
    assert len(_snapshots(tmp_path)) == 1
    agent.release(result.thread_id)
    assert _snapshots(tmp_path) == []
    assert agent._runs == {}
