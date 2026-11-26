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
from mmt_plugin_agent.skills import EvaluationCode


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
    probe_runner = scripts / "pcap_eval.c"
    probe_runner.write_text("/* probe */\n")
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
        evaluation=EvaluationCode(
            script=probe_script.read_bytes(), runner=probe_runner.read_bytes()
        ),
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
    (project / "plugin.yaml").write_text("schema: 1\nprotocol:\n  label: telem\n  id: 977\n")
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
    rebuild = _green_records(project)  # the loop again, a new validate-delimited run
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


def test_a_rebuild_in_the_same_run_muddies_the_green(tmp_path: Path) -> None:
    """A build or test again inside the same run — no new validate, so no
    new run — makes the run's commands no longer the loop's exact sequence
    (two builds, two tests). Green is the exact sequence, one each: the
    muddled run is not green however honest each exit code, and the model
    must validate again — cheaply — to start a clean one."""
    work = tmp_path / "work"
    project = work / "project"
    project.mkdir(parents=True)
    green = _green_records(project)
    rebuild = _green_records(project)[2:]  # build and test again, no validate
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
    assert result.evaluation == "not_done"
    assert result.status == "not_green"


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


# --- the evaluation binds the canonical artifact and a fresh runner -------


def test_a_sibling_plugin_is_never_the_artifact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A ``mmtp_*.so`` the loop never linked — planted in ``build/`` next to
    the canonical artifact, even byte for byte the same file — is not the
    build the green loop left: the evaluation's ``--plugin`` binds
    ``build/mmtp_<label>.so`` exactly, the name ``build`` itself derives
    from the project's plugin.yaml."""
    backend, work, sdk = _make_backend(tmp_path, monkeypatch)
    records = _records(backend)
    plugin = _build(backend, work, sdk)
    (work / "capture.pcap").write_bytes(b"x")
    sibling = plugin.parent / "mmtp_evil.so"
    sibling.write_bytes(plugin.read_bytes())
    backend.execute(_evaluation(work, sdk, sibling, **{"--label": "evil"}))
    assert records[-1].trusted is False, "a sibling of another name and label"
    backend.execute(_evaluation(work, sdk, sibling))
    assert records[-1].trusted is False, "even measured as the right label"
    backend.execute(_evaluation(work, sdk, plugin))
    assert records[-1].trusted is True, "the canonical artifact binds"


def test_the_label_the_evaluation_measures_is_the_projects(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``--label`` names the protocol the runner measures: another label
    measures another protocol's classification with the plugin loaded but
    irrelevant — or nothing at all."""
    backend, work, sdk = _make_backend(tmp_path, monkeypatch)
    records = _records(backend)
    plugin = _build(backend, work, sdk)
    (work / "capture.pcap").write_bytes(b"x")
    backend.execute(_evaluation(work, sdk, plugin, **{"--label": "http"}))
    assert records[-1].trusted is False
    backend.execute(_evaluation(work, sdk, plugin, **{"--label": "TELEM"}))
    assert records[-1].trusted is True, "case is the registration's, not the evidence's"


def test_a_project_without_a_label_binds_no_artifact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The canonical name comes from plugin.yaml, the same file ``build``
    reads: no readable label, no canonical artifact, no trusted evaluation
    — fail closed."""
    backend, work, sdk = _make_backend(tmp_path, monkeypatch)
    records = _records(backend)
    plugin = _build(backend, work, sdk)
    (work / "capture.pcap").write_bytes(b"x")
    project = work / "project"
    (project / "plugin.yaml").write_text("schema: 1\nprotocol:\n  id: 977\n")
    backend.execute(f"mmt-plugin -C {project} --json build --sdk {sdk} --cc gcc")
    backend.execute(_evaluation(work, sdk, plugin))
    assert records[-1].trusted is False, "no label in plugin.yaml"
    (project / "plugin.yaml").unlink()
    backend.execute(f"mmt-plugin -C {project} --json build --sdk {sdk} --cc gcc")
    backend.execute(_evaluation(work, sdk, plugin))
    assert records[-1].trusted is False, "no plugin.yaml at all"


def test_a_renamed_label_moves_the_canonical_artifact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The binding follows plugin.yaml as it is at the scan, not the file
    that happens to sit in ``build/``: a project whose label is now
    ``other`` has ``mmtp_other.so`` for its canonical artifact, and the
    stale ``mmtp_telem.so`` no longer binds."""
    backend, work, sdk = _make_backend(tmp_path, monkeypatch)
    records = _records(backend)
    plugin = _build(backend, work, sdk)
    (work / "capture.pcap").write_bytes(b"x")
    project = work / "project"
    other = plugin.parent / "mmtp_other.so"
    other.write_bytes(b"the renamed build\n")
    (project / "plugin.yaml").write_text("schema: 1\nprotocol:\n  label: other\n  id: 977\n")
    backend.execute(f"mmt-plugin -C {project} --json build --sdk {sdk} --cc gcc")
    backend.execute(_evaluation(work, sdk, plugin))
    assert records[-1].trusted is False, "mmtp_telem.so is a leftover now"
    backend.execute(_evaluation(work, sdk, other, **{"--label": "other"}))
    assert records[-1].trusted is True, "mmtp_other.so is the canonical artifact"


def test_a_preplanted_runner_cache_is_removed_before_the_evaluation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The script reuses ``<out>/bin/pcap_eval`` when the stamp next to it
    names the same compile command, and both are the model's to write: a
    planted binary with a planted stamp would run instead of the verified C
    runner. The trusted execution removes both first, so what runs is
    compiled now, from the runner whose bytes were checked."""
    backend, work, sdk = _make_backend(tmp_path, monkeypatch)
    records = _records(backend)
    plugin = _build(backend, work, sdk)
    (work / "capture.pcap").write_bytes(b"x")
    cache = work / "eval" / "bin"
    cache.mkdir(parents=True)
    planted = cache / "pcap_eval"
    planted.write_bytes(b"planted runner\n")
    stamp = cache / "pcap_eval.cmd"
    stamp.write_text("the compile command line\n")
    backend.execute(_evaluation(work, sdk, plugin))
    assert records[-1].trusted is True and records[-1].evaluation is True
    assert not planted.exists(), "the planted binary is removed before the run"
    assert not stamp.exists(), "and its stamp with it"


def test_a_runner_cache_that_cannot_be_removed_is_not_trusted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When the cache cannot be removed it may still be the planted binary
    the compile would reuse: the execution falls back to the shell, its
    output the model's say-so — fail closed."""
    backend, work, sdk = _make_backend(tmp_path, monkeypatch)
    records = _records(backend)
    plugin = _build(backend, work, sdk)
    (work / "capture.pcap").write_bytes(b"x")
    cache = work / "eval" / "bin" / "pcap_eval"
    cache.mkdir(parents=True)  # a directory at the cache path: unlink fails
    backend.execute(_evaluation(work, sdk, plugin))
    assert records[-1].trusted is False
    assert records[-1].evaluation is False


def test_a_changed_c_runner_is_never_trusted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The script compiles the C runner next to it, so the runner's bytes
    are as much the evidence as the script's: a rewritten ``pcap_eval.c``
    in the skills copy — the shell writes what the file tools may not —
    makes the evaluation untrusted, the unchanged script notwithstanding."""
    backend, work, sdk = _make_backend(tmp_path, monkeypatch)
    records = _records(backend)
    plugin = _build(backend, work, sdk)
    (work / "capture.pcap").write_bytes(b"x")
    runner = tmp_path / "skills" / "mmt-plugin-generator" / "scripts" / "pcap_eval.c"
    runner.write_text("/* planted */\n")
    backend.execute(_evaluation(work, sdk, plugin))
    assert records[-1].trusted is False
    runner.unlink()
    backend.execute(_evaluation(work, sdk, plugin))
    assert records[-1].trusted is False, "and a missing one is no better"


# --- finding 3: green is the exact ordered sequence, one each -------------


def _sequence_result(tmp_path: Path, names: list[str], with_sdk: bool = True) -> Any:
    """The result of one run of trusted loop commands ``names`` in order,
    each exiting 0, all targeting the project."""
    work = tmp_path / "work"
    project = work / "project"
    project.mkdir(parents=True)
    now = time.time_ns()
    records = []
    for i, name in enumerate(names):
        line = f"mmt-plugin -C {project} --json {name}"
        if with_sdk:
            line += " --sdk /sdk" + (" --cc gcc" if name in ("build", "test") else "")
        else:
            flags = "--no-sdk --sdk-profile" if name == "validate" else "--sdk-profile"
            line += f" {flags} 1.10.2"
        records.append(
            CommandRecord(line, 0, _env(name), trusted=True, started_ns=now + i, ended_ns=now + i)
        )
    return build_result(
        thread_id="t",
        work=work,
        project=None,
        records=records,
        with_sdk=with_sdk,
        no_eval=True,
        message="DONE",
    )


@pytest.mark.parametrize(
    "names",
    [
        ["validate", "generate", "build"],  # no test
        ["validate", "generate", "test"],  # no build
        ["validate", "build", "test"],  # no generate
        ["generate", "build", "test"],  # no validate
    ],
    ids=["no-test", "no-build", "no-generate", "no-validate"],
)
def test_an_omission_is_never_green(tmp_path: Path, names: list[str]) -> None:
    """Presence is not the sequence: a step missing is not the loop, however
    green the exit codes of the others."""
    result = _sequence_result(tmp_path, names)
    assert result.status == "not_green"


@pytest.mark.parametrize(
    "names",
    [
        ["validate", "generate", "test", "build"],
        ["validate", "build", "generate", "test"],
        ["generate", "validate", "build", "test"],
        ["validate", "test", "generate", "build"],
    ],
    ids=["test-before-build", "build-before-generate", "generate-first", "test-second"],
)
def test_a_reordering_is_never_green(tmp_path: Path, names: list[str]) -> None:
    """The loop certifies validate, generate, build, test *in that order*:
    a test before its build measures a stale binary, a build before its
    generate compiles stale sources — scrambled evidence is none."""
    result = _sequence_result(tmp_path, names)
    assert result.status == "not_green"


@pytest.mark.parametrize(
    "names",
    [
        ["validate", "generate", "build", "build", "test"],
        ["validate", "generate", "generate", "build", "test"],
        ["validate", "generate", "build", "test", "test"],
    ],
    ids=["build-twice", "generate-twice", "test-twice"],
)
def test_a_duplicate_is_never_green(tmp_path: Path, names: list[str]) -> None:
    """One each: a step twice inside the run muddies which artifact the
    green is of. The honest iteration starts a new run with validate."""
    result = _sequence_result(tmp_path, names)
    assert result.status == "not_green"


def test_the_exact_sequence_is_green(tmp_path: Path) -> None:
    result = _sequence_result(tmp_path, ["validate", "generate", "build", "test"])
    assert result.status == "done", result.to_json()


def test_a_step_run_untrusted_is_a_step_missing(tmp_path: Path) -> None:
    """A step the shell ran — a pipeline, a loop, an indirect invocation —
    is the model's word, not evidence: filtered out before the sequence is
    read, it leaves the run short of the exact sequence, however green the
    text around it."""
    work = tmp_path / "work"
    project = work / "project"
    project.mkdir(parents=True)
    green = _green_records(project)
    generate = green[1]
    untrusted = CommandRecord(
        generate.command,
        generate.exit_code,
        generate.output,
        trusted=False,  # the same text, run by the shell: no evidence
        started_ns=generate.started_ns,
        ended_ns=generate.ended_ns,
    )
    result = build_result(
        thread_id="t",
        work=work,
        project=None,
        records=[green[0], untrusted, green[2], green[3]],
        with_sdk=True,
        no_eval=True,
        message="DONE",
    )
    assert result.status == "not_green", "validate, build, test without generate"


def test_commands_of_another_project_do_not_break_the_sequence(tmp_path: Path) -> None:
    """A run is this project's evidence: another project's loop commands,
    filtered out before the sequence is read, neither complete it nor
    corrupt it."""
    work = tmp_path / "work"
    project = work / "project"
    project.mkdir(parents=True)
    other = work / "other"
    other.mkdir()
    now = time.time_ns()
    foreign = CommandRecord(
        f"mmt-plugin -C {other} --json build --sdk /sdk --cc gcc",
        0,
        _env("build"),
        trusted=True,
        started_ns=now + 1,
        ended_ns=now + 1,
    )
    green = _green_records(project)
    records = [green[0], green[1], foreign, green[2], green[3]]
    result = build_result(
        thread_id="t",
        work=work,
        project=None,
        records=records,
        with_sdk=True,
        no_eval=True,
        message="DONE",
    )
    assert result.status == "done", result.to_json()


def test_without_an_sdk_the_profiles_must_match(tmp_path: Path) -> None:
    """No-SDK green is validate, generate pinning the *same* profile: a
    model validated against one and generated for another was never checked
    as it generated, and a missing pin is no pin."""
    same = _sequence_result(tmp_path, ["validate", "generate"], with_sdk=False)
    assert same.status == "done", same.to_json()
    work = tmp_path / "w2"
    project = work / "project"
    project.mkdir(parents=True)
    now = time.time_ns()
    records = [
        CommandRecord(
            f"mmt-plugin -C {project} --json validate --no-sdk --sdk-profile 1.10.2",
            0,
            _env("validate"),
            trusted=True,
            started_ns=now,
            ended_ns=now,
        ),
        CommandRecord(
            f"mmt-plugin -C {project} --json generate --sdk-profile 1.9.0",
            0,
            _env("generate"),
            trusted=True,
            started_ns=now + 1,
            ended_ns=now + 1,
        ),
    ]
    result = build_result(
        thread_id="t",
        work=work,
        project=None,
        records=records,
        with_sdk=False,
        no_eval=True,
        message="DONE",
    )
    assert result.status == "not_green", "one profile for validate, another for generate"


def test_a_failed_loop_then_the_exact_sequence_is_green(tmp_path: Path) -> None:
    """Incomplete failing loops are fine: the failed attempt is its own run,
    the fix starts a new one with validate, and green is the exact sequence
    of the last run."""
    work = tmp_path / "work"
    project = work / "project"
    project.mkdir(parents=True)
    now = time.time_ns()
    failed = [
        CommandRecord(
            f"mmt-plugin -C {project} --json {name} --sdk /sdk"
            + (" --cc gcc" if name in ("build", "test") else ""),
            6 if name == "test" else 0,
            _env(name, 6 if name == "test" else 0),
            trusted=True,
            started_ns=now + i,
            ended_ns=now + i,
        )
        for i, name in enumerate(("validate", "generate", "build", "test"))
    ]
    green = _green_records(project)
    result = build_result(
        thread_id="t",
        work=work,
        project=None,
        records=[*failed, *green],
        with_sdk=True,
        no_eval=True,
        message="DONE",
    )
    assert result.status == "done", result.to_json()
    assert result.loop_runs == 2


def test_the_cache_is_gone_when_the_script_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The removal is not a cleanup afterwards: the script itself, asked,
    finds no cache — the binary that runs is the one it compiles now, and
    a planted one is gone before the process even starts."""
    probe = (
        "import os, sys\n"
        "out = sys.argv[sys.argv.index('--out') + 1]\n"
        "gone = not os.path.exists(os.path.join(out, 'bin', 'pcap_eval'))\n"
        "gone = gone and not os.path.exists(os.path.join(out, 'bin', 'pcap_eval.cmd'))\n"
        "sys.exit(0 if gone else 3)\n"
    )
    backend, work, sdk = _make_backend(tmp_path, monkeypatch)
    script = tmp_path / "skills" / "mmt-plugin-generator" / "scripts" / "pcap_eval.py"
    script.write_text(probe)
    runner = tmp_path / "skills" / "mmt-plugin-generator" / "scripts" / "pcap_eval.c"
    backend._evaluation = EvaluationCode(script=probe.encode(), runner=runner.read_bytes())
    records = _records(backend)
    plugin = _build(backend, work, sdk)
    (work / "capture.pcap").write_bytes(b"x")
    cache = work / "eval" / "bin"
    cache.mkdir(parents=True)
    (cache / "pcap_eval").write_bytes(b"planted runner\n")
    (cache / "pcap_eval.cmd").write_text("the compile command line\n")
    backend.execute(_evaluation(work, sdk, plugin))
    assert records[-1].trusted is True
    assert records[-1].exit_code == 0, "the script itself found no cache when it ran"
