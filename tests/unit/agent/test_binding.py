"""Regression tests for the run binding of trusted evidence: the loop's
exact shapes bind the run's project, SDK and compiler (anything else runs
in the shell, untrusted), the capture evaluation's arguments bind its
script, capture, output and the build the green loop left, and green needs
validate's ``parents-exist`` pass."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import pytest

from mmt_plugin_agent.backend import GuardedShellBackend
from mmt_plugin_agent.questions import Questioner
from mmt_plugin_agent.result import CommandRecord, build_result


def _env(command: str, code: int = 0, checks: str | None = "pass") -> str:
    env: dict[str, Any] = {"schema_version": 1, "command": command, "exit_code": code}
    if command == "validate" and checks is not None:
        env["result"] = {"checks": [{"id": "parents-exist", "status": checks}]}
    if command == "test":
        env["result"] = {"summary": {"total": 2, "passed": 2, "failed": 0}}
    return json.dumps(env) + "\n"


def _make_backend(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    capture: Path | None = None,
    project: Path | None = None,
) -> tuple[GuardedShellBackend, Path, Path]:
    """A backend bound to a run: its SDK at ``tmp_path/sdk``, gcc, the
    lexical ``<work>/project`` unless given, synthetic captures allowed.
    mmt-plugin is a probe printing the envelope of its command, exiting 0;
    the evaluation's script is a probe inside the skills copy."""
    work = tmp_path / "work"
    work.mkdir(exist_ok=True)
    skills = tmp_path / "skills"
    scripts = skills / "mmt-plugin-generator" / "scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    probe_script = scripts / "pcap_eval.py"
    probe_script.write_text("import sys\nsys.exit(0)\n")
    sdk = tmp_path / "sdk"
    probe = (
        "import json, sys\n"
        "args = sys.argv[1:]\n"
        "command = next((a for a in args if a in ('validate','generate','build','test')), '')\n"
        "result = {}\n"
        "if command == 'validate':\n"
        "    result = {'checks': [{'id': 'parents-exist', 'status': 'pass'}]}\n"
        "if command == 'test':\n"
        "    result = {'summary': {'total': 2, 'passed': 2, 'failed': 0}}\n"
        "print(json.dumps({'schema_version': 1, 'command': command, 'exit_code': 0,"
        " 'result': result}))\n"
        "sys.exit(0)\n"
    )
    monkeypatch.setattr(
        "mmt_plugin_agent.backend.mmt_plugin_argv",
        lambda: [sys.executable, "-c", probe, *[]],
    )
    monkeypatch.setattr(
        "mmt_plugin_agent.backend.evaluation_argv",
        lambda script: [sys.executable, str(script)],
    )
    questioner = Questioner(mode="unattended", work=work, allow_synthetic=True)
    backend = GuardedShellBackend(
        work=work,
        writable=[work],
        protected=[skills],
        questioner=questioner,
        env={"PATH": os.environ["PATH"]},
        timeout=30,
        evaluation=probe_script.read_bytes(),
        project=project,
        sdk=sdk,
        cc="gcc",
        capture=capture,
    )
    return backend, work, sdk


def _records(backend: GuardedShellBackend) -> list[CommandRecord]:
    seen: list[CommandRecord] = []
    backend.on_command = seen.append
    return seen


def _build(backend: GuardedShellBackend, work: Path, sdk: Path) -> Path:
    """A trusted build over a project holding one plugin binary: the backend
    scans it, so the evaluation's ``--plugin`` can bind. Returns the plugin."""
    project = work / "project"
    plugin = project / "build" / "mmtp_telem.so"
    plugin.parent.mkdir(parents=True, exist_ok=True)
    plugin.write_bytes(b"the build's plugin\n")
    backend.execute(f"mmt-plugin -C {project} --json build --sdk {sdk} --cc gcc")
    return plugin


def _evaluation(work: Path, sdk: Path, plugin: Path, **override: str) -> str:
    args = {
        "--sdk": str(sdk),
        "--plugin": str(plugin),
        "--label": "telem",
        "--parent": "tcp",
        "--capture": str(work / "capture.pcap"),
        "--out": str(work / "eval"),
        "--cc": "gcc",
    }
    args.update(override)
    tail = " ".join(f"{k} {v}" for k, v in args.items())
    # The probe the harness wrote inside the protected skills copy (work is
    # always <tmp>/work here): only a script resolving there is trusted.
    probe = work.parent / "skills" / "mmt-plugin-generator" / "scripts" / "pcap_eval.py"
    return f"python3 {probe} {tail}"


def _loop(project: Path, sdk: Path) -> list[str]:
    return [
        f"mmt-plugin -C {project} --json {name} --sdk {sdk}"
        + (" --cc gcc" if name in ("build", "test") else "")
        for name in ("validate", "generate", "build", "test")
    ]


# --- finding 1: the loop's shapes bind the exact argv and project --------


def test_the_exact_loop_shapes_are_trusted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    backend, work, sdk = _make_backend(tmp_path, monkeypatch)
    records = _records(backend)
    for command in _loop(work / "project", sdk):
        backend.execute(command)
        assert records[-1].trusted is True, command
    assert [r.name for r in records] == ["validate", "generate", "build", "test"]


@pytest.mark.parametrize(
    "mutation",
    [
        "extra -C after the subcommand",
        "a --model",
        "a --dry-run",
        "another --cc",
        "another sdk",
        "a packet selection",
        "an extra positional",
        "the other project's path",
        "no sdk at all",
    ],
)
def test_a_loop_command_off_the_exact_shape_is_not_trusted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutation: str
) -> None:
    backend, work, sdk = _make_backend(tmp_path, monkeypatch)
    records = _records(backend)
    project = work / "project"
    base = f"mmt-plugin -C {project} --json build --sdk {sdk} --cc gcc"
    command = {
        "extra -C after the subcommand": f"{base} -C {project}",
        "a --model": f"{base} --model x",
        "a --dry-run": f"{base} --dry-run",
        "another --cc": f"mmt-plugin -C {project} --json build --sdk {sdk} --cc clang",
        "another sdk": f"mmt-plugin -C {project} --json build --sdk {tmp_path / 'other'} --cc gcc",
        "a packet selection": f"mmt-plugin -C {project} --json test --sdk {sdk} --cc gcc one.yaml",
        "an extra positional": f"{base} extra",
        "the other project's path": (
            f"mmt-plugin -C {tmp_path / 'other'} --json validate --sdk {sdk}"
        ),
        "no sdk at all": f"mmt-plugin -C {project} --json validate",
    }[mutation]
    backend.execute(command)
    assert records[-1].trusted is False, mutation
    assert records[-1].name is None


def test_a_timeout_prefix_and_a_tee_keep_the_exact_shape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    backend, work, sdk = _make_backend(tmp_path, monkeypatch)
    records = _records(backend)
    project = work / "project"
    backend.execute(f"timeout 900 mmt-plugin -C {project} --json validate --sdk {sdk}")
    assert records[-1].trusted is True
    backend.execute(
        f"mmt-plugin -C {project} --json validate --sdk {sdk} | tee {work}/runs/validate.json"
    )
    assert records[-1].trusted is True
    assert (work / "runs" / "validate.json").is_file()


def test_a_relative_project_token_resolves_against_the_work_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    backend, _work, sdk = _make_backend(tmp_path, monkeypatch)
    records = _records(backend)
    backend.execute(f"mmt-plugin -C project --json validate --sdk {sdk}")
    assert records[-1].trusted is True
    backend.execute(f"mmt-plugin -C ./project/../project --json validate --sdk {sdk}")
    assert records[-1].trusted is True
    backend.execute(f"mmt-plugin -C elsewhere --json validate --sdk {sdk}")
    assert records[-1].trusted is False


def test_a_symlink_planted_at_the_project_path_is_not_the_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    backend, work, sdk = _make_backend(tmp_path, monkeypatch)
    records = _records(backend)
    project = work / "project"
    command = f"mmt-plugin -C {project} --json validate --sdk {sdk}"
    backend.execute(command)
    assert records[-1].trusted is True, "no symlink: the lexical path is the project's"
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    try:
        project.symlink_to(elsewhere)
    except OSError:
        pytest.skip("no symlinks")
    backend.execute(command)
    assert records[-1].trusted is False, "the -C resolves through the link, away from the project"


def test_the_no_sdk_shapes_bind_the_profile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    work = tmp_path / "work"
    work.mkdir()
    (tmp_path / "skills").mkdir()
    monkeypatch.setattr(
        "mmt_plugin_agent.backend.mmt_plugin_argv",
        lambda: [sys.executable, "-c", "import sys; sys.exit(0)"],
    )
    questioner = Questioner(mode="unattended", work=work, allow_synthetic=False)
    backend = GuardedShellBackend(
        work=work,
        writable=[work],
        protected=[tmp_path / "skills"],
        questioner=questioner,
        env={"PATH": os.environ["PATH"]},
        timeout=30,
        sdk=None,
    )
    records = _records(backend)
    project = work / "project"
    good = [
        f"mmt-plugin -C {project} --json validate --no-sdk --sdk-profile 1.10.2",
        f"mmt-plugin -C {project} --json generate --sdk-profile 1.10.2",
    ]
    for command in good:
        backend.execute(command)
        assert records[-1].trusted is True, command
    bad = [
        f"mmt-plugin -C {project} --json validate --no-sdk",
        f"mmt-plugin -C {project} --json validate --sdk-profile 1.10.2",
        f"mmt-plugin -C {project} --json generate --no-sdk --sdk-profile 1.10.2",
        f"mmt-plugin -C {project} --json generate",
        f"mmt-plugin -C {project} --json build --no-sdk --sdk-profile 1.10.2",
    ]
    for command in bad:
        backend.execute(command)
        assert records[-1].trusted is False, command


# --- finding 2: the evaluation is correlated with the run -----------------


def test_the_bound_evaluation_is_trusted_and_marked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    backend, work, sdk = _make_backend(tmp_path, monkeypatch)
    records = _records(backend)
    plugin = _build(backend, work, sdk)
    (work / "capture.pcap").write_bytes(b"x")
    backend.execute(_evaluation(work, sdk, plugin))
    assert records[-1].trusted is True and records[-1].evaluation is True


@pytest.mark.parametrize(
    "mutation",
    [
        "--help",
        "capture outside work",
        "out outside work",
        "plugin outside build",
        "wrong sdk",
        "wrong cc",
        "no cc",
        "an unknown option",
    ],
)
def test_an_evaluation_off_the_run_is_not_trusted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutation: str
) -> None:
    backend, work, sdk = _make_backend(tmp_path, monkeypatch)
    records = _records(backend)
    plugin = _build(backend, work, sdk)
    (work / "capture.pcap").write_bytes(b"x")
    command = _evaluation(work, sdk, plugin)
    if mutation == "--help":
        command += " --help"
    elif mutation == "capture outside work":
        outside = tmp_path / "outside.pcap"
        outside.write_bytes(b"x")
        command = _evaluation(work, sdk, plugin, **{"--capture": str(outside)})
    elif mutation == "out outside work":
        command = _evaluation(work, sdk, plugin, **{"--out": str(tmp_path / "eval")})
    elif mutation == "plugin outside build":
        command = _evaluation(work, sdk, plugin, **{"--plugin": str(work / "mmtp_telem.so")})
    elif mutation == "wrong sdk":
        command = _evaluation(work, sdk, plugin, **{"--sdk": str(tmp_path / "other")})
    elif mutation == "wrong cc":
        command = _evaluation(work, sdk, plugin, **{"--cc": "clang"})
    elif mutation == "no cc":
        args = command.rsplit(" --cc gcc", 1)
        command = args[0]
    elif mutation == "an unknown option":
        command += " --turbo"
    backend.execute(command)
    assert records[-1].trusted is False, mutation
    assert records[-1].evaluation is False


def test_the_evaluations_own_options_do_not_break_the_binding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The field mapping, the accepted drifts and --synthetic are the
    evaluation's own configuration (audited in its report), not the run's
    binding: the skill's real invocations carry them."""
    backend, work, sdk = _make_backend(tmp_path, monkeypatch)
    records = _records(backend)
    plugin = _build(backend, work, sdk)
    (work / "capture.pcap").write_bytes(b"x")
    command = _evaluation(work, sdk, plugin)
    command += " --field length=tpkt.length --field type=tpkt.type --synthetic"
    command += " --accept length=zero-is-legal --decode-as tcp.port==1,telem"
    command += " --expect-filter udp.port==5684 --min-recall 0.5"
    backend.execute(command)
    assert records[-1].trusted is True and records[-1].evaluation is True


def test_the_evaluations_plugin_is_the_builds_byte_for_byte(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A file the loop never built, the build's plugin rewritten afterwards,
    and an evaluation before any build are none of them the build the green
    loop left."""
    backend, work, sdk = _make_backend(tmp_path, monkeypatch)
    records = _records(backend)
    (work / "capture.pcap").write_bytes(b"x")
    project = work / "project"
    plugin = project / "build" / "mmtp_telem.so"
    plugin.parent.mkdir(parents=True)
    plugin.write_bytes(b"never built by the loop\n")
    backend.execute(_evaluation(work, sdk, plugin))
    unbuilt = records[-1]
    assert unbuilt.trusted is False, "no trusted build scanned it"
    _build(backend, work, sdk)
    backend.execute(_evaluation(work, sdk, plugin))
    built = records[-1]
    assert built.trusted is True, "the build's own plugin binds"
    plugin.write_bytes(b"rewritten after the build\n")
    backend.execute(_evaluation(work, sdk, plugin))
    rewritten = records[-1]
    assert rewritten.trusted is False, "rewritten after the scan"
    # A rebuild makes the new bytes the build's again.
    backend.execute(f"mmt-plugin -C {project} --json build --sdk {sdk} --cc gcc")
    backend.execute(_evaluation(work, sdk, plugin))
    rebuilt = records[-1]
    assert rebuilt.trusted is True


def test_a_configured_capture_binds_itself_or_its_copy_in_the_work_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    configured = tmp_path / "given.pcap"
    configured.write_bytes(b"the capture\n")
    backend, work, sdk = _make_backend(tmp_path, monkeypatch, capture=configured.resolve())
    records = _records(backend)
    plugin = _build(backend, work, sdk)
    backend.execute(_evaluation(work, sdk, plugin, **{"--capture": str(configured)}))
    assert records[-1].trusted is True, "the configured capture itself"
    copy = work / "capture" / "capture.pcap"
    copy.parent.mkdir(parents=True)
    copy.write_bytes(b"the capture\n")
    backend.execute(_evaluation(work, sdk, plugin, **{"--capture": str(copy)}))
    assert records[-1].trusted is True, "its copy inside the work folder"
    other = work / "capture" / "other.pcap"
    other.write_bytes(b"not it\n")
    backend.execute(_evaluation(work, sdk, plugin, **{"--capture": str(other)}))
    assert records[-1].trusted is False, "another capture, even inside the work folder"


def _green_records(project: Path) -> list[CommandRecord]:
    now = time.time_ns()
    out = []
    for i, command in enumerate(("validate", "generate", "build", "test")):
        line = f"mmt-plugin -C {project} --json {command} --sdk /sdk"
        if command in ("build", "test"):
            line += " --cc gcc"
        out.append(
            CommandRecord(
                line,
                0,
                _env(command),
                trusted=True,
                started_ns=now + i,
                ended_ns=now + i,
            )
        )
    return out


def _eval_record(project: Path, exit_code: int, after: int) -> CommandRecord:
    now = time.time_ns()
    return CommandRecord(
        f"python3 s/pcap_eval.py --plugin {project}/build/mmtp_telem.so",
        exit_code,
        "",
        trusted=True,
        evaluation=True,
        started_ns=now + after,
        ended_ns=now + after,
    )


def test_the_evaluation_counts_only_after_a_green_loop(tmp_path: Path) -> None:
    """R2: an evaluation before the loop it evaluates, however green its
    exit, is no evidence of that build; one after it is, and the last
    verdict decides."""
    work = tmp_path / "work"
    project = work / "project"
    project.mkdir(parents=True)
    green = _green_records(project)
    early = build_result(
        thread_id="t",
        work=work,
        project=None,
        records=[_eval_record(project, 0, 0), *green],
        with_sdk=True,
        no_eval=False,
        message="DONE",
        allow_synthetic=True,
    )
    assert early.evaluation == "not_done", "the evaluation preceded the build it evaluates"
    late = build_result(
        thread_id="t",
        work=work,
        project=None,
        records=[*green, _eval_record(project, 0, 10)],
        with_sdk=True,
        no_eval=False,
        message="DONE",
        allow_synthetic=True,
    )
    assert late.evaluation == "pass"
    assert late.status == "done"
    flip = build_result(
        thread_id="t",
        work=work,
        project=None,
        records=[
            *green,
            _eval_record(project, 1, 10),
            *_green_records(project),
            _eval_record(project, 0, 20),
        ],
        with_sdk=True,
        no_eval=False,
        message="DONE",
        allow_synthetic=True,
    )
    assert flip.evaluation == "pass", "a FAIL fixed and evaluated again is the PASS"


def test_a_rebuild_after_the_evaluation_stales_it(tmp_path: Path) -> None:
    """The evaluation is of *that build* (SKILL.md, Done): a trusted build
    or test after it is not the binary it measured, so its verdict no
    longer counts — pass or fail."""
    work = tmp_path / "work"
    project = work / "project"
    project.mkdir(parents=True)
    green = _green_records(project)
    rebuild = _green_records(project)[2:]  # build and test again
    result = build_result(
        thread_id="t",
        work=work,
        project=None,
        records=[*green, _eval_record(project, 0, 10), *rebuild],
        with_sdk=True,
        no_eval=False,
        message="DONE",
        allow_synthetic=True,
    )
    assert result.evaluation == "not_done", "the PASS measured the previous binary"
    assert result.status == "incomplete"


# --- finding 3: green needs validate's parents-exist pass -----------------


@pytest.mark.parametrize("checks", ["pass", "warn", "fail", None])
def test_green_needs_parents_exist_pass(tmp_path: Path, checks: str | None) -> None:
    work = tmp_path / "work"
    project = work / "project"
    project.mkdir(parents=True)
    now = time.time_ns()
    records = [
        CommandRecord(
            f"mmt-plugin -C {project} --json {name} --sdk /sdk"
            + (" --cc gcc" if name in ("build", "test") else ""),
            0,
            _env(name, checks=checks),
            trusted=True,
            started_ns=now + i,
            ended_ns=now + i,
        )
        for i, name in enumerate(("validate", "generate", "build", "test"))
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
    if checks == "pass":
        assert result.status == "done", result.to_json()
    else:
        assert result.status == "not_green", f"parents-exist {checks}: {result.to_json()}"


# --- finding 4: the eval harness runs the isolated module ------------------


def test_the_eval_harness_runs_python_in_isolated_mode() -> None:
    """Finding 4: the eval harness's default CLI is the isolated module, as
    the backend's is — a shadowing ``mmt_plugin`` package next to the case
    never replaces it."""
    repo = Path(__file__).resolve().parents[3]
    harness = repo / "skills/mmt-plugin-generator/evals/run_evals.py"
    assert '[sys.executable, "-I", "-m", "mmt_plugin"]' in harness.read_text()
    from mmt_plugin_agent import evals

    source = (Path(evals.__file__)).read_text()
    assert '[sys.executable, "-I", "-m", "mmt_plugin"]' in source
