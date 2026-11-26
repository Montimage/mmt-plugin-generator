"""The agent cannot write under the skills (AC6): its file tools refuse it,
the skills it reads are a read-only copy, a run that changes the source
tree by any route is failed and the tree restored (P6), and an unattended
``--force`` never reaches the shell (P10)."""

from __future__ import annotations

import asyncio
import os
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

from mmt_plugin_agent import PluginAgent
from mmt_plugin_agent.backend import REFUSED_EXIT, GuardedShellBackend
from mmt_plugin_agent.questions import Questioner
from mmt_plugin_agent.result import CommandRecord
from mmt_plugin_agent.skills import EvaluationCode

from .fakes import FakeCli, call, done_files, loop, scripted, step

SPEC = Path(__file__).resolve().parents[3] / (
    "skills/mmt-plugin-generator/evals/cases/spec-telem/spec.md"
)
SKILL_MD = "mmt-plugin-generator/SKILL.md"


def _backend(
    work: Path,
    skills: Path,
    writable: Path | None = None,
    sdk: Path | None = None,
    capture: Path | None = None,
    allow_synthetic: bool = False,
) -> GuardedShellBackend:
    questioner = Questioner(mode="unattended", work=work, allow_synthetic=allow_synthetic)
    return GuardedShellBackend(
        work=work,
        writable=[writable or work],
        protected=[skills],
        questioner=questioner,
        env={"PATH": os.environ["PATH"]},
        timeout=30,
        sdk=sdk,
        capture=capture,
    )


@pytest.fixture
def setup(tmp_path: Path, skills_copy: Path) -> tuple[Path, Path, GuardedShellBackend]:
    work = tmp_path / "work"
    work.mkdir()
    return work, skills_copy, _backend(work, skills_copy)


def test_the_file_tools_refuse_the_skills(
    setup: tuple[Path, Path, GuardedShellBackend],
) -> None:
    work, skills, backend = setup
    skill = skills / SKILL_MD
    before = skill.read_bytes()
    assert backend.write(str(skills / "new.md"), "x").error is not None
    assert backend.edit(str(skill), "name:", "nam:").error is not None
    assert backend.delete(str(skill)).error is not None
    responses = backend.upload_files([(str(skills / "up.md"), b"x"), (str(work / "ok"), b"y")])
    assert [r.error for r in responses] == ["permission_denied", None]
    assert skill.read_bytes() == before
    assert not (skills / "new.md").exists() and not (skills / "up.md").exists()
    assert (work / "ok").read_bytes() == b"y"
    error = backend.write(str(skills / "new.md"), "x").error
    assert error == f"permission denied: {skills / 'new.md'} is read-only for the agent"


def test_the_async_file_tools_refuse_the_skills(
    setup: tuple[Path, Path, GuardedShellBackend],
) -> None:
    _, skills, backend = setup
    skill = skills / SKILL_MD

    async def go() -> list[str | None]:
        return [
            (await backend.awrite(str(skills / "a.md"), "x")).error,
            (await backend.aedit(str(skill), "name:", "nam:")).error,
            (await backend.adelete(str(skill))).error,
            (await backend.aupload_files([(str(skills / "b.md"), b"x")]))[0].error,
        ]

    assert all(e is not None for e in asyncio.run(go()))
    assert skill.is_file() and not (skills / "a.md").exists()


def test_a_link_or_a_dot_dot_does_not_get_past_the_guard(
    setup: tuple[Path, Path, GuardedShellBackend],
) -> None:
    work, skills, backend = setup
    (work / "link").symlink_to(skills / "mmt-plugin-generator")
    assert backend.write(str(work / "link" / "SKILL.md"), "x").error is not None
    assert backend.write("link/x.md", "x").error is not None
    assert backend.write(str(work / ".." / "skills" / "x.md"), "x").error is not None
    assert backend.write(str(work / ".." / "outside.md"), "x").error is not None
    assert backend.write(str(work / "inside.md"), "x").error is None
    assert backend.write("relative.md", "x").error is None
    assert (work / "relative.md").read_text() == "x"


def test_the_skills_stay_read_only_under_a_writable_root(
    tmp_path: Path, skills_copy: Path
) -> None:
    # The system temp dir is writable, and a skills copy may live below it.
    backend = _backend(tmp_path / "work", skills_copy, writable=tmp_path)
    assert backend.write(str(skills_copy / "x.md"), "x").error is not None
    assert backend.write(str(tmp_path / "x.md"), "x").error is None


@pytest.mark.skipif(os.geteuid() == 0, reason="root writes read-only files")
def test_a_run_reads_a_read_only_copy_of_the_skills(
    tmp_path: Path, skills_copy: Path, fake_cli: Callable[..., FakeCli]
) -> None:
    fake_cli()
    work = tmp_path / "work"
    cache = tmp_path / "cache" / "mmt-plugin-agent"
    # A redirection target is not globbed by a non-interactive sh: name the
    # snapshot first, so each write reaches the real read-only copy.
    write = (
        f"set -- {cache}/skills-*; d=$1; "
        f'test -f "$d/{SKILL_MD}"; echo found=$?; '
        f'echo x >> "$d/{SKILL_MD}"; echo append=$?; '
        f'touch "$d/mmt-plugin-generator/new.md"; echo create=$?'
    )
    model = scripted(
        [step(call("ls", path=str(cache))), step(call("execute", command=write)), "DONE"]
    )
    result = PluginAgent(model, work_dir=work, skills_dir=skills_copy).new(spec=SPEC)
    listing, wrote = model.tool_results()[:2]
    assert "skills-" in listing
    assert "found=0" in wrote, wrote
    assert "append=" in wrote and "create=" in wrote, wrote
    assert "append=0" not in wrote and "create=0" not in wrote, wrote
    assert "Permission denied" in wrote and "No such file" not in wrote, wrote
    assert result.skills_modified == []
    assert not any(cache.iterdir()), "the copy is removed at the end"


def test_the_skill_path_the_model_reads_is_the_copy(
    tmp_path: Path, skills_copy: Path, fake_cli: Callable[..., FakeCli]
) -> None:
    fake_cli()
    model = scripted(["DONE"])
    PluginAgent(model, work_dir=tmp_path / "w", skills_dir=skills_copy).new(spec=SPEC)
    system = str(model.seen[0][0].content)
    assert str(tmp_path / "cache" / "mmt-plugin-agent") in system
    assert str(skills_copy) not in system


def test_a_run_that_changes_the_skills_fails_and_restores_them(
    tmp_path: Path, skills_copy: Path, fake_cli: Callable[..., FakeCli]
) -> None:
    fake_cli()
    work = tmp_path / "work"
    skill = skills_copy / SKILL_MD
    before = skill.read_bytes()
    model = scripted(
        [
            step(
                call(
                    "execute",
                    command=f"echo changed >> {skill} && echo new > {skills_copy}/added.md "
                    f"&& rm {skills_copy}/mmt-plugin-generator/references/evals.md",
                )
            ),
            *loop(work / "project", tmp_path / "sdk"),
            *done_files(work),
            "DONE",
        ]
    )
    agent = PluginAgent(model, sdk=tmp_path / "sdk", work_dir=work, skills_dir=skills_copy)
    result = agent.new(spec=SPEC)
    assert result.status == "failed"
    assert result.skills_modified == [
        "added.md",
        SKILL_MD,
        "mmt-plugin-generator/references/evals.md",
    ]
    assert skill.read_bytes() == before
    assert not (skills_copy / "added.md").exists()
    assert (skills_copy / "mmt-plugin-generator/references/evals.md").is_file()


def test_a_link_planted_in_the_skills_is_undone_without_writing_through_it(
    tmp_path: Path, skills_copy: Path, fake_cli: Callable[..., FakeCli]
) -> None:
    fake_cli()
    skill = skills_copy / SKILL_MD
    before = skill.read_bytes()
    outside = tmp_path / "outside.txt"
    outside.write_text("the user's file\n")
    refs = skills_copy / "mmt-plugin-generator" / "references"
    plant = (
        f"rm {skill} && ln -s {outside} {skill} && mv {refs} {tmp_path}/refs "
        f"&& ln -s {tmp_path}/refs {refs} && ln -s /etc {skills_copy}/etc"
    )
    model = scripted([step(call("execute", command=plant)), "DONE"])
    agent = PluginAgent(model, work_dir=tmp_path / "work", skills_dir=skills_copy)
    result = agent.new(spec=SPEC)
    assert result.status == "failed"
    assert "etc" in result.skills_modified and SKILL_MD in result.skills_modified
    assert outside.read_text() == "the user's file\n"
    assert not skill.is_symlink() and skill.read_bytes() == before
    assert not refs.is_symlink() and (refs / "capture.md").is_file()
    assert not (skills_copy / "etc").exists() and not (skills_copy / "etc").is_symlink()


def test_a_subagent_shares_the_guarded_backend(
    tmp_path: Path, skills_copy: Path, fake_cli: Callable[..., FakeCli]
) -> None:
    fake_cli()
    target = skills_copy / "mmt-plugin-generator" / "by-subagent.md"
    model = scripted(
        [
            step(call("task", description="SUBTASK write it", subagent_type="general-purpose")),
            "DONE",
        ],
        SUBTASK=[step(call("write_file", file_path=str(target), content="x")), "written?"],
    )
    PluginAgent(model, work_dir=tmp_path / "w", skills_dir=skills_copy).new(spec=SPEC)
    assert not target.exists()
    assert any("read-only for the agent" in r for r in model.tool_results())


def test_unattended_force_never_reaches_the_shell(
    tmp_path: Path, fake_cli: Callable[..., FakeCli]
) -> None:
    cli = fake_cli()
    work = tmp_path / "work"
    model = scripted(
        [
            step(call("execute", command=f"mmt-plugin -C {work}/project --json generate --force")),
            "BLOCKED",
        ]
    )
    result = PluginAgent(model, work_dir=work).new(spec=SPEC)
    assert cli.calls() == []
    (record,) = result.commands
    assert record.exit_code == REFUSED_EXIT
    assert record.refused == "--force is never used unattended (SKILL.md, Rule 4)"
    assert model.tool_results()[0].startswith("refused by mmt-plugin-agent, not run")


def test_sudo_and_the_system_prefix_never_reach_the_shell(
    tmp_path: Path, fake_cli: Callable[..., FakeCli]
) -> None:
    cli = fake_cli()
    model = scripted(
        [
            step(call("execute", command="sudo mmt-plugin --json install")),
            step(call("execute", command="mmt-plugin --json validate --sdk /opt/mmt")),
            "DONE",
        ]
    )
    result = PluginAgent(model, work_dir=tmp_path / "w").new(spec=SPEC)
    assert cli.calls() == []
    assert [r.exit_code for r in result.commands] == [REFUSED_EXIT, REFUSED_EXIT]


def test_only_ask_user_writes_questions_md(
    setup: tuple[Path, Path, GuardedShellBackend],
) -> None:
    work, _, backend = setup
    error = backend.write(str(work / "questions.md"), "## Q1: capture?\n").error
    assert error is not None and "ask_user" in error
    assert not (work / "questions.md").exists()
    backend.questioner.ask("capture?", "synthetic", "capture")
    assert backend.edit(str(work / "questions.md"), "capture?", "x").error is not None
    assert (work / "questions.md").read_text().count("## Q") == 1


def test_a_large_tool_result_is_offloaded_in_the_work_folder(
    tmp_path: Path, fake_cli: Callable[..., FakeCli]
) -> None:
    fake_cli()
    work = tmp_path / "work"
    # Over deepagents' threshold (20000 tokens, 4 characters each), under the
    # shell's 100000-byte cap.
    model = scripted([step(call("execute", command="yes x | head -c 90000")), "DONE"])
    PluginAgent(model, work_dir=work).new(spec=SPEC)
    offloaded = work.resolve() / ".agent" / "large_tool_results"
    files = list(offloaded.iterdir())
    assert len(files) == 1 and files[0].read_text().count("x") >= 40000
    assert str(offloaded) in model.tool_results()[0]


def _records(backend: GuardedShellBackend) -> list[CommandRecord]:
    """Collect the backend's command records."""
    seen: list[CommandRecord] = []
    backend.on_command = seen.append
    return seen


def test_a_strict_evaluation_inside_the_skills_is_trusted_outside_is_not(
    tmp_path: Path, skills_copy: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """R1.4/R2: the backend itself runs the strict evaluation form when the
    script resolves inside the protected skills copy and its arguments bind
    the run; the same strict text naming a copy outside, or arguments of
    another run, falls back to the shell, untrusted."""
    work = tmp_path / "work"
    work.mkdir()
    sdk = tmp_path / "sdk"
    backend = _backend(work, skills_copy, sdk=sdk, allow_synthetic=True)
    probe = skills_copy / "mmt-plugin-generator" / "scripts" / "pcap_eval.py"
    probe.write_text("import sys; print('probe ran'); sys.exit(0)\n")
    runner = skills_copy / "mmt-plugin-generator" / "scripts" / "pcap_eval.c"
    backend._evaluation = EvaluationCode(script=probe.read_bytes(), runner=runner.read_bytes())
    # The project the loop builds: the canonical artifact's name comes
    # from its plugin.yaml's label.
    (work / "project").mkdir(exist_ok=True)
    (work / "project" / "plugin.yaml").write_text("schema: 1\nprotocol:\n  label: telem\n")
    # The plugin the evaluation names is the one a trusted build leaves:
    # the backend scans <project>/build after each trusted build or test.
    monkeypatch.setattr(
        "mmt_plugin_agent.backend.mmt_plugin_argv",
        lambda: [sys.executable, "-c", "import sys; sys.exit(0)"],
    )
    project = work / "project"
    plugin = project / "build" / "mmtp_telem.so"
    plugin.parent.mkdir(parents=True)
    plugin.write_bytes(b"fake plugin\n")
    capture = work / "capture.pcap"
    capture.write_bytes(b"x")
    records = _records(backend)
    backend.execute(f"mmt-plugin -C {project} --json build --sdk {sdk} --cc gcc")
    assert records[-1].trusted is True

    def evaluation(script: Path) -> str:
        return (
            f"python3 {script} --sdk {sdk} --plugin {plugin} --label telem --parent tcp "
            f"--capture {capture} --out {work}/eval --cc gcc"
        )

    response = backend.execute(evaluation(probe))
    assert response.exit_code == 0 and "probe ran" in response.output
    assert records[-1].trusted is True and records[-1].evaluation is True
    probe.write_text("import sys; print('changed ran'); sys.exit(0)\n")
    before = len(records)
    backend.execute(evaluation(probe))
    assert len(records) == before + 1
    changed = records[-1]
    assert changed.trusted is False, "a changed copy is the shell's, untrusted"
    probe.write_bytes(backend._evaluation.script)
    outside = work / "pcap_eval.py"
    outside.write_text("import sys; print('outside ran'); sys.exit(0)\n")
    before = len(records)
    response = backend.execute(evaluation(outside))
    assert len(records) == before + 1
    outer = records[-1]
    assert outer.trusted is False, "a copy outside the skills is the shell's, untrusted"


def test_a_strict_mmt_plugin_is_the_backends_own_execution(
    setup: tuple[Path, Path, GuardedShellBackend], monkeypatch: pytest.MonkeyPatch
) -> None:
    """R1.1/R1.2: the strict form is executed by the backend, not the shell:
    the argv is the isolated module, tee is the backend's own write, and a
    shadowing package in the work folder cannot replace it."""
    work, _skills, backend = setup
    ran: list[list[str]] = []

    def probe(argv: list[str]) -> list[str]:
        ran.append(argv)
        return argv

    monkeypatch.setattr(
        "mmt_plugin_agent.backend.mmt_plugin_argv",
        lambda: probe(
            [sys.executable, "-I", "-c", "import sys; print('{}'); sys.exit(3)".format("real")]
        ),
    )
    shadow = work / "mmt_plugin"
    shadow.mkdir()
    (shadow / "__init__.py").write_text("")
    (shadow / "__main__.py").write_text('print("shadowed")\n')
    records = _records(backend)
    response = backend.execute(
        "mmt-plugin -C project --json validate --no-sdk --sdk-profile 1.10.2"
        " | tee runs/run-1/validate.json"
    )
    assert response.exit_code == 3
    assert records[-1].trusted is True and records[-1].name == "validate"
    assert "shadowed" not in response.output
    assert (work / "runs/run-1/validate.json").is_file(), "the backend tees stdout itself"
    assert "-I" in ran[0] or "-I" in (ran[0][1:3] if ran else []), ran


def test_a_shell_loop_shape_is_not_trusted(
    setup: tuple[Path, Path, GuardedShellBackend],
) -> None:
    """R1: ``for c in ...; done``, ``&&``, redirections and substitutions
    run in the shell for utility, but the records are never trusted."""
    _work, _skills, backend = setup
    records = _records(backend)
    backend.execute("for c in validate test; do echo $c; done")
    backend.execute("echo hi > out.txt")
    backend.execute("echo $(echo nested)")
    assert all(not r.trusted for r in records)
