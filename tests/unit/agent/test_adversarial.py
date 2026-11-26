"""Focused adversarial tests for the trusted-evidence residuals: the
loop's canonical shapes are exact token sequences in the documented
order, the evaluation's plugin is named like a build output, the verdict
is the backend's own exit 0 — never the manifest's — and an evaluation a
later trusted build or test supersedes is no evidence of the final
build."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import pytest

from mmt_plugin_agent.backend import GuardedShellBackend
from mmt_plugin_agent.policy import evaluation_args, loop_subcommand
from mmt_plugin_agent.questions import Questioner
from mmt_plugin_agent.result import CommandRecord, build_result

WORKDIR = Path(os.environ.get("TMPDIR", "/tmp"))


def _policy_loop(args: list[str], project: Path, sdk: Path | None) -> str | None:
    return loop_subcommand(args, project=project, sdk=sdk, cc="gcc", cwd=WORKDIR)


def test_the_documented_flag_order_is_canonical(tmp_path: Path) -> None:
    """The same flags in another order are not the skill's shape: argparse
    may not care, but only the documented sequence is parsed exactly."""
    project, sdk = tmp_path / "project", tmp_path / "sdk"
    base = ["-C", str(project), "--json"]
    good = [*base, "build", "--sdk", str(sdk), "--cc", "gcc"]
    assert _policy_loop(good, project, sdk) == "build"
    swapped = [*base, "build", "--cc", "gcc", "--sdk", str(sdk)]
    assert _policy_loop(swapped, project, sdk) is None
    cc_first = [*base, "test", "--cc", "gcc", "--sdk", str(sdk)]
    assert _policy_loop(cc_first, project, sdk) is None
    repeated = [*base, "build", "--sdk", str(sdk), "--cc", "gcc", "--cc", "gcc"]
    assert _policy_loop(repeated, project, sdk) is None
    # The no-SDK shapes: validate --no-sdk --sdk-profile, in that order.
    valid = [*base, "validate", "--no-sdk", "--sdk-profile", "1.10.2"]
    assert _policy_loop(valid, project, None) == "validate"
    reordered = [*base, "validate", "--sdk-profile", "1.10.2", "--no-sdk"]
    assert _policy_loop(reordered, project, None) is None
    bare_value = [*base, "validate", "--no-sdk", "--sdk-profile", "--no-sdk"]
    assert _policy_loop(bare_value, project, None) is None
    generate = [*base, "generate", "--sdk-profile", "1.10.2"]
    assert _policy_loop(generate, project, None) == "generate"
    extra = [*base, "generate", "--sdk-profile", "1.10.2", "--force"]
    assert _policy_loop(extra, project, None) is None


def test_a_loop_shape_check_canonicalizes_no_clever_spellings(tmp_path: Path) -> None:
    project, sdk = tmp_path / "project", tmp_path / "sdk"
    base = ["-C", str(project), "--json"]
    inline = [*base, "validate", f"--sdk={sdk}"]
    assert _policy_loop(inline, project, sdk) is None
    long_project = ["--project", str(project), "--json", "validate", "--sdk", str(sdk)]
    assert _policy_loop(long_project, project, sdk) is None
    json_after = ["-C", str(project), "validate", "--json", "--sdk", str(sdk)]
    assert _policy_loop(json_after, project, sdk) is None


def _eval_args(tmp_path: Path, plugin: str) -> list[str]:
    work = tmp_path / "work"
    return [
        "--sdk",
        str(tmp_path / "sdk"),
        "--plugin",
        plugin,
        "--label",
        "telem",
        "--parent",
        "tcp",
        "--capture",
        str(work / "capture.pcap"),
        "--out",
        str(work / "eval"),
        "--cc",
        "gcc",
    ]


def _eval_bound(tmp_path: Path, tokens: list[str]) -> dict[str, list[str]] | None:
    work = tmp_path / "work"
    return evaluation_args(
        tokens,
        project=work / "project",
        sdk=tmp_path / "sdk",
        cc="gcc",
        capture=None,
        work=work,
        work_capture=True,
        cwd=work,
    )


def test_the_evaluations_plugin_is_named_like_a_build_output(tmp_path: Path) -> None:
    """``build`` writes ``mmtp_<label>.so``: a library of any other name in
    the project's build directory is not the plugin the loop certified."""
    project = tmp_path / "work" / "project"
    good = str(project / "build" / "mmtp_telem.so")
    assert _eval_bound(tmp_path, _eval_args(tmp_path, good)) is not None
    for bad in (
        str(project / "build" / "evil.so"),
        str(project / "build" / "mmtp_telem.so.bak"),
        str(project / "build" / "mmtp_telem.dll"),
    ):
        assert _eval_bound(tmp_path, _eval_args(tmp_path, bad)) is None, bad


def test_the_evaluations_correlation_has_no_help_no_missing_required(tmp_path: Path) -> None:
    project = tmp_path / "work" / "project"
    good = _eval_args(tmp_path, str(project / "build" / "mmtp_telem.so"))
    assert _eval_bound(tmp_path, [*good, "--help"]) is None
    assert _eval_bound(tmp_path, ["--help", *good]) is None
    without_out = [t for i, t in enumerate(good) if good[i - 1] != "--out" and t != "--out"]
    assert _eval_bound(tmp_path, without_out) is None


def _env(command: str, code: int = 0) -> str:
    env: dict[str, Any] = {"schema_version": 1, "command": command, "exit_code": code}
    if command == "validate":
        env["result"] = {"checks": [{"id": "parents-exist", "status": "pass"}]}
    if command == "test":
        env["result"] = {"summary": {"total": 2, "passed": 2, "failed": 0}}
    return json.dumps(env) + "\n"


def _green(project: Path) -> list[CommandRecord]:
    now = time.time_ns()
    return [
        CommandRecord(
            f"mmt-plugin -C {project} --json {name} --sdk /sdk"
            + (" --cc gcc" if name in ("build", "test") else ""),
            0,
            _env(name),
            trusted=True,
            started_ns=now,
            ended_ns=now,
        )
        for name in ("validate", "generate", "build", "test")
    ]


def _evaluation(project: Path, exit_code: int) -> CommandRecord:
    return CommandRecord(
        f"python3 s/pcap_eval.py --plugin {project}/build/mmtp_telem.so",
        exit_code,
        "",
        trusted=True,
        evaluation=True,
        started_ns=time.time_ns(),
        ended_ns=time.time_ns(),
    )


def _result(tmp_path: Path, records: list[CommandRecord], **kwargs: Any) -> Any:
    work = tmp_path / "work"
    (work / "project").mkdir(parents=True, exist_ok=True)
    return build_result(
        thread_id="t",
        work=work,
        project=None,
        records=records,
        with_sdk=True,
        no_eval=False,
        message="DONE",
        **kwargs,
    )


def test_a_trusted_evaluation_exit_0_is_the_pass_without_a_manifest(tmp_path: Path) -> None:
    """The verdict is the backend's own execution: no manifest.json at all
    is needed for a pass, and one the model writes never counts either."""
    project = tmp_path / "work" / "project"
    result = _result(tmp_path, [*_green(project), _evaluation(project, 0)])
    assert result.evaluation == "pass"
    assert result.status == "done", result.to_json()


def test_an_evaluation_a_later_loop_supersedes_is_no_evidence(tmp_path: Path) -> None:
    """Green, PASS, then the loop again on a changed plugin: the evaluation
    measured the first build, not the one the last green loop left — it is
    the evaluation of another binary, however green both loops are."""
    project = tmp_path / "work" / "project"
    records = [*_green(project), _evaluation(project, 0), *_green(project)]
    result = _result(tmp_path, records, allow_synthetic=True)
    assert result.loop is not None and result.loop.green(with_sdk=True)
    assert result.evaluation == "not_done", result.to_json()
    assert result.status == "incomplete"
    # Evaluated again after the last green loop, the verdict is the PASS.
    again = _result(tmp_path, [*records, _evaluation(project, 0)], allow_synthetic=True)
    assert again.evaluation == "pass"
    assert again.status == "done", again.to_json()


def test_an_evaluation_before_any_green_loop_is_no_evidence(tmp_path: Path) -> None:
    project = tmp_path / "work" / "project"
    records = [*_green(project)[:2], _evaluation(project, 0), *_green(project)[2:]]
    result = _result(tmp_path, records, allow_synthetic=True)
    assert result.evaluation == "not_done"


@pytest.mark.parametrize("verdict", ["pass", "PASS"])
def test_a_manifest_pass_alone_never_proves_the_evaluation(tmp_path: Path, verdict: str) -> None:
    """manifest.json is the model's to write: a PASS in it, with no trusted
    evaluation at all, is not done — however green the trusted loop is."""
    work = tmp_path / "work"
    (work / "project").mkdir(parents=True)
    (work / "manifest.json").write_text(
        json.dumps({"schema": 1, "eval": {"verdict": verdict, "drift": {"open": 0}}})
    )
    result = build_result(
        thread_id="t",
        work=work,
        project=None,
        records=_green(work / "project"),
        with_sdk=True,
        no_eval=False,
        message="DONE",
    )
    assert result.evaluation == "not_done"
    assert result.status == "incomplete"
    assert any("say-so" in line for line in result.unchecked)


def test_a_noncanonical_command_runs_in_the_shell_untrusted_not_refused(
    tmp_path: Path,
) -> None:
    """Off the canonical shape the command is still run — the shell's,
    for utility, with a real shell exit code — it just proves nothing:
    the record is untrusted, never refused."""
    work = tmp_path / "work"
    work.mkdir()
    skills = tmp_path / "skills"
    skills.mkdir()
    questioner = Questioner(mode="unattended", work=work, allow_synthetic=True)
    backend = GuardedShellBackend(
        work=work,
        writable=[work],
        protected=[skills],
        questioner=questioner,
        env={"PATH": os.environ["PATH"]},
        timeout=30,
        sdk=tmp_path / "sdk",
    )
    seen: list[CommandRecord] = []
    backend.on_command = seen.append
    project = work / "project"
    # The strict form off the canonical shape: the backend does not execute
    # it, but the shell does — the record is untrusted, never refused.
    for command in (
        f"mmt-plugin -C {project} --json validate --sdk {tmp_path}/sdk --dry-run",
        f"mmt-plugin -C {project} --json build --cc gcc --sdk {tmp_path}/sdk",
        f"mmt-plugin -C {project} --json validate --sdk {tmp_path}/sdk -C {project}",
    ):
        backend.execute(command)
        assert seen[-1].refused is None, command
        assert seen[-1].trusted is False, command
        assert seen[-1].exit_code is not None, "the shell ran it"
