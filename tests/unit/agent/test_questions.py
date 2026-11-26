"""The capture question and the leave for ``--force``: unattended runs
record them and take the safe default (AC4), interactive runs stop and
resume with the answer (AC5), ``on_question`` answers them (AC10)."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from pathlib import Path

import pytest

from mmt_plugin_agent import PluginAgent, Question

from .fakes import FakeCli, call, done_files, evaluate, loop, scripted, step

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
    model = scripted(
        [_ask(), *loop(work / "project", sdk), evaluate(work, sdk), *done_files(work), "DONE"]
    )
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


def test_a_finished_run_deletes_its_thread_checkpoints(
    tmp_path: Path, fake_cli: Callable[..., FakeCli]
) -> None:
    """R3: the shared checkpointer does not accumulate every run's state:
    a run that ends deletes its thread; a waiting one keeps it."""
    from langgraph.checkpoint.memory import InMemorySaver

    fake_cli()
    checkpointer = InMemorySaver()
    ask = step(call("ask_user", question="capture?", recommended="synthetic", kind="capture"))
    agent = PluginAgent(
        scripted([ask, "DONE"]),
        work_dir=tmp_path / "w",
        mode="interactive",
        checkpointer=checkpointer,
    )
    from langchain_core.runnables import RunnableConfig

    first = agent.new(spec=SPEC)
    assert first.status == "waiting"
    thread = first.thread_id
    config = RunnableConfig(configurable={"thread_id": thread})
    assert checkpointer.get_tuple(config) is not None, "a waiting run keeps its checkpoints"
    agent.release(thread)
    assert checkpointer.get_tuple(config) is None
    work = tmp_path / "w2"
    model = scripted([step(call("execute", command="true")), "DONE"])
    done_agent = PluginAgent(model, work_dir=work, checkpointer=checkpointer)
    result = done_agent.new(spec=SPEC)
    ended = RunnableConfig(configurable={"thread_id": result.thread_id})
    assert checkpointer.get_tuple(ended) is None, "a run that ends deletes them"


def test_a_duplicate_active_thread_id_is_a_usage_error(
    tmp_path: Path, fake_cli: Callable[..., FakeCli]
) -> None:
    """R3: two active runs never share one thread (its checkpoints would
    mix); a released run's id is free again."""
    from mmt_plugin_agent import AgentError

    fake_cli()
    ask = step(call("ask_user", question="capture?", recommended="synthetic", kind="capture"))
    agent = PluginAgent(scripted([ask, "DONE"]), work_dir=tmp_path / "w", mode="interactive")
    first = agent.new(spec=SPEC)
    assert first.status == "waiting"
    with pytest.raises(AgentError, match="still active") as caught:
        agent.new(spec=SPEC, thread_id=first.thread_id)
    assert caught.value.code == "agent.duplicate-thread"
    agent.release(first.thread_id)
    again = agent.new(spec=SPEC, thread_id=first.thread_id)
    assert again.thread_id == first.thread_id


@pytest.mark.parametrize(
    "thread_id",
    ["../escape", "a/b", "/abs", ".", "..", ".hidden", "a b", "a;rm", "", "x" * 129],
)
def test_a_path_shaped_thread_id_is_a_usage_error(
    tmp_path: Path, fake_cli: Callable[..., FakeCli], thread_id: str
) -> None:
    """R4: the thread id is part of the snapshot's directory name: it is
    one safe file-name component, never a path."""
    from mmt_plugin_agent import AgentError

    fake_cli()
    agent = PluginAgent(scripted(["DONE"]), work_dir=tmp_path / "w")
    with pytest.raises(AgentError, match="not a safe name") as caught:
        agent.new(spec=SPEC, thread_id=thread_id)
    assert caught.value.code == "agent.bad-thread"
    assert agent._runs == {}


@pytest.mark.parametrize("thread_id", ["run-1", "my.run_2", "abc123", "x" * 128])
def test_a_simple_thread_id_is_accepted(
    tmp_path: Path, fake_cli: Callable[..., FakeCli], thread_id: str
) -> None:
    fake_cli()
    agent = PluginAgent(scripted(["DONE"]), work_dir=tmp_path / "w")
    assert agent.new(spec=SPEC, thread_id=thread_id).thread_id == thread_id


def test_the_pcap_entry_is_the_evaluations_capture_by_default(
    tmp_path: Path, fake_cli: Callable[..., FakeCli]
) -> None:
    """R5: ``new --pcap X`` gives a capture of the protocol: the brief does
    not say none was given, and the run has leave for the evaluation."""
    fake_cli()
    pcap = tmp_path / "telem.pcap"
    pcap.write_bytes(b"not a real capture")
    model = scripted(["DONE"])
    result = PluginAgent(model, work_dir=tmp_path / "w").new(pcap=pcap)
    system = str(model.seen[0][0].content)
    assert f"the user gave one: {pcap.resolve()}" in system
    assert "ask the capture question" not in system
    assert result.eval_leave == "capture"
    # An explicit capture still wins.
    other = tmp_path / "other.pcap"
    other.write_bytes(b"")
    model2 = scripted(["DONE"])
    PluginAgent(model2, work_dir=tmp_path / "w2", capture=other).new(pcap=pcap)
    assert f"the user gave one: {other.resolve()}" in str(model2.seen[0][0].content)
