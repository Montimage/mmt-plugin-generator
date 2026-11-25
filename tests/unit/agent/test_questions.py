"""The capture question and the leave for ``--force``: unattended runs
record them and take the safe default (AC4), interactive runs stop and
resume with the answer (AC5), ``on_question`` answers them (AC10)."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from pathlib import Path

import pytest

from mmt_plugin_agent import PluginAgent, Question

from .fakes import FakeCli, call, done_files, loop, scripted, step

SPEC = Path(__file__).resolve().parents[3] / (
    "skills/mmt-plugin-generator/evals/cases/spec-telem/spec.md"
)
CAPTURE_Q = "No capture was given or found. Give a capture, allow a synthetic one, or skip?"


def _ask() -> list[dict[str, object]] | str:
    return step(
        call("ask_user", question=CAPTURE_Q, recommended="a synthetic capture", kind="capture")
    )


class _NoStdin:
    """A stdin that fails the test when read."""

    def read(self, size: int = -1) -> str:
        raise AssertionError("an unattended run read stdin")

    def readline(self, size: int = -1) -> str:
        raise AssertionError("an unattended run read stdin")


def test_unattended_without_a_capture_records_the_question_and_skips_the_evaluation(
    tmp_path: Path, fake_cli: Callable[..., FakeCli], monkeypatch: pytest.MonkeyPatch
) -> None:
    cli = fake_cli()
    monkeypatch.setattr("sys.stdin", _NoStdin())
    work, sdk = tmp_path / "work", tmp_path / "sdk"
    model = scripted([_ask(), *loop(work / "project", sdk), *done_files(work, None), "DONE"])
    result = PluginAgent(model, sdk=sdk, work_dir=work).new(spec=SPEC)
    assert result.status == "incomplete"
    assert result.ok
    assert result.evaluation == "not_done"
    assert "evaluation: not done (no capture)" in result.unchecked
    assert result.questions_path == work / "questions.md"
    assert (work / "questions.md").read_text() == (
        f"## Q1: {CAPTURE_Q}\nRecommended: a synthetic capture\n"
        "Taken: skip the evaluation; it is reported as not done\n\n"
    )
    assert "Taken: skip the evaluation" in model.tool_results()[0]
    assert not any("--force" in " ".join(c) for c in cli.calls())


def test_unattended_with_leave_takes_a_synthetic_capture(
    tmp_path: Path, fake_cli: Callable[..., FakeCli]
) -> None:
    fake_cli()
    work = tmp_path / "work"
    model = scripted([_ask(), _ask(), "DONE"])
    PluginAgent(model, work_dir=work, allow_synthetic=True).new(spec=SPEC)
    text = (work / "questions.md").read_text()
    assert text.count("Taken: allow a synthetic capture (the request grants it)") == 2
    assert "## Q1: " in text and "## Q2: " in text


def test_the_brief_states_the_mode_and_the_flags(
    tmp_path: Path, fake_cli: Callable[..., FakeCli]
) -> None:
    fake_cli()
    model = scripted(["DONE"])
    capture = tmp_path / "c.pcap"
    capture.write_bytes(b"")
    PluginAgent(
        model,
        sdk=tmp_path / "sdk",
        cc="clang",
        work_dir=tmp_path / "w",
        capture=capture,
        no_eval=True,
    ).new(spec=SPEC)
    system = str(model.seen[0][0].content)
    assert "unattended: no user can answer" in system
    assert f"the user gave one: {capture}" in system
    assert f"pass --sdk {tmp_path / 'sdk'}" in system
    assert "Compiler: clang." in system
    assert "skip it: the user passed --no-eval" in system
    assert str(tmp_path / "w") in system
    assert "Never write or edit" in system and "questions.md yourself." in system


@pytest.mark.parametrize("use_async", [False, True], ids=["sync", "async"])
def test_interactive_stops_at_the_capture_question_and_resumes(
    tmp_path: Path, fake_cli: Callable[..., FakeCli], use_async: bool
) -> None:
    fake_cli()
    work, sdk = tmp_path / "work", tmp_path / "sdk"
    model = scripted([_ask(), *loop(work / "project", sdk), *done_files(work), "DONE"])
    agent = PluginAgent(model, sdk=sdk, work_dir=work, mode="interactive")
    first = asyncio.run(agent.anew(spec=SPEC)) if use_async else agent.new(spec=SPEC)
    assert first.status == "waiting"
    assert first.question is not None
    assert (first.question.kind, first.question.text) == ("capture", CAPTURE_Q)
    assert first.commands == []
    assert not (work / "questions.md").exists()
    final = agent.resume(first.thread_id, "use the capture in /data/telem.pcap")
    assert final.thread_id == first.thread_id
    assert final.status == "done"
    assert model.tool_results()[0] == "use the capture in /data/telem.pcap"


def test_resume_of_an_unknown_thread_is_a_usage_error(tmp_path: Path) -> None:
    from mmt_plugin_agent import AgentError

    with pytest.raises(AgentError, match="no run is waiting with thread id nope") as caught:
        PluginAgent(scripted(["DONE"]), work_dir=tmp_path).resume("nope", "yes")
    assert caught.value.code == "agent.unknown-thread"


def test_on_question_answers_the_capture_question(
    tmp_path: Path, fake_cli: Callable[..., FakeCli]
) -> None:
    fake_cli()
    asked: list[Question] = []

    def answer(question: Question) -> str:
        asked.append(question)
        return "allow a synthetic capture"

    model = scripted([_ask(), "DONE"])
    result = PluginAgent(model, work_dir=tmp_path / "w", on_question=answer).new(spec=SPEC)
    assert [(q.kind, q.text, q.recommended) for q in asked] == [
        ("capture", CAPTURE_Q, "a synthetic capture")
    ]
    assert model.tool_results() == ["allow a synthetic capture"]
    assert result.status != "waiting"
    assert not (tmp_path / "w" / "questions.md").exists()


@pytest.mark.parametrize(("answer", "runs"), [("yes", True), ("no", False)])
def test_interactive_force_runs_only_with_leave(
    tmp_path: Path, fake_cli: Callable[..., FakeCli], answer: str, runs: bool
) -> None:
    cli = fake_cli()
    command = "mmt-plugin -C p --json generate --force"
    asked: list[Question] = []

    def leave(question: Question) -> str:
        asked.append(question)
        return answer

    model = scripted([step(call("execute", command=command)), "DONE"])
    agent = PluginAgent(model, work_dir=tmp_path / "w", mode="interactive", on_question=leave)
    agent.new(spec=SPEC)
    assert [q.kind for q in asked] == ["force"]
    assert command in asked[0].text
    assert (cli.calls() == [["-C", "p", "--json", "generate", "--force"]]) is runs
