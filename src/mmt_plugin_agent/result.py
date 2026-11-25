"""What a run returns: the loop as the shell saw it, the work folder's
report, and the events ``PluginAgent.stream()`` yields."""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from mmt_plugin_agent.policy import LOOP_COMMANDS, mmt_plugin_command
from mmt_plugin_agent.questions import Question

__all__ = [
    "AgentEvent",
    "AgentResult",
    "CommandRecord",
    "EventKind",
    "LoopRun",
    "Status",
    "build_result",
    "envelope_of",
    "loop_runs",
]

Status = Literal["done", "incomplete", "eval_failed", "not_green", "blocked", "failed", "waiting"]
EventKind = Literal["step", "command", "envelope", "loop", "question", "done"]


def envelope_of(output: str) -> dict[str, Any] | None:
    """The first JSON object of a command's output that is an mmt-plugin
    envelope (it has ``schema_version`` and ``exit_code``)."""
    decoder = json.JSONDecoder()
    start = output.find("{")
    while start != -1:
        try:
            value, _ = decoder.raw_decode(output, start)
        except ValueError:
            value = None
        if isinstance(value, dict) and "schema_version" in value and "exit_code" in value:
            return value
        start = output.find("{", start + 1)
    return None


@dataclass
class CommandRecord:
    """One shell command the agent ran, or that its shell refused."""

    command: str
    exit_code: int | None
    output: str
    refused: str | None = None

    @property
    def mmt_command(self) -> str | None:
        found = mmt_plugin_command(self.command)
        return found[0] if found else None

    @property
    def project(self) -> str | None:
        found = mmt_plugin_command(self.command)
        return found[1] if found else None

    @property
    def envelope(self) -> dict[str, Any] | None:
        return None if self.mmt_command is None else envelope_of(self.output)

    def to_json(self) -> dict[str, Any]:
        env = self.envelope
        return {
            "command": self.command,
            "mmt_command": self.mmt_command,
            "exit_code": self.exit_code,
            "refused": self.refused,
            "error_code": ((env or {}).get("error") or {}).get("code"),
        }


@dataclass
class LoopRun:
    """One loop run (SKILL.md, Step 4): the loop commands from a ``validate``
    on, each with its exit code, and whether it is green."""

    number: int
    commands: list[CommandRecord] = field(default_factory=list)
    project: str | None = None

    def exit_codes(self) -> dict[str, int | None]:
        return {c.mmt_command or "": c.exit_code for c in self.commands}

    def test_summary(self) -> dict[str, Any] | None:
        for record in self.commands:
            if record.mmt_command == "test":
                env = record.envelope or {}
                summary = (env.get("result") or {}).get("summary")
                return summary if isinstance(summary, dict) else None
        return None

    def green(self, with_sdk: bool) -> bool:
        need = LOOP_COMMANDS if with_sdk else LOOP_COMMANDS[:2]
        codes = self.exit_codes()
        if any(codes.get(name) != 0 for name in need):
            return False
        if not with_sdk:
            return True
        summary = self.test_summary() or {}
        total = summary.get("total", 0)
        return isinstance(total, int) and total >= 1 and summary.get("passed") == total

    def to_json(self, with_sdk: bool) -> dict[str, Any]:
        return {
            "number": self.number,
            "project": self.project,
            "commands": self.exit_codes(),
            "test_summary": self.test_summary(),
            "green": self.green(with_sdk),
        }


def loop_runs(records: Sequence[CommandRecord]) -> list[LoopRun]:
    """The loop runs among ``records``: each ``validate`` starts one."""
    runs: list[LoopRun] = []
    for record in records:
        name = record.mmt_command
        if name not in LOOP_COMMANDS or record.refused:
            continue
        if name == "validate" or not runs:
            runs.append(LoopRun(len(runs) + 1, project=record.project))
        runs[-1].commands.append(record)
    return runs


@dataclass
class AgentResult:
    """A run's outcome, what ``mmt-plugin-agent --json`` prints as ``result``
    (``schemas/v1/result.json``)."""

    status: Status
    thread_id: str
    work: Path
    project: Path | None = None
    loop: LoopRun | None = None
    loop_runs: int = 0
    with_sdk: bool = False
    evaluation: str = "not_done"
    drift: int | None = None
    unchecked: list[str] = field(default_factory=list)
    report_path: Path | None = None
    questions_path: Path | None = None
    question: Question | None = None
    skills_modified: list[str] = field(default_factory=list)
    commands: list[CommandRecord] = field(default_factory=list)
    message: str = ""

    @property
    def ok(self) -> bool:
        return self.status in ("done", "incomplete")

    def to_json(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "thread_id": self.thread_id,
            "work": str(self.work),
            "project": None if self.project is None else str(self.project),
            "loop": None if self.loop is None else self.loop.to_json(self.with_sdk),
            "loop_runs": self.loop_runs,
            "evaluation": self.evaluation,
            "drift": self.drift,
            "unchecked": list(self.unchecked),
            "report_path": None if self.report_path is None else str(self.report_path),
            "questions_path": None if self.questions_path is None else str(self.questions_path),
            "question": None if self.question is None else self.question.to_json(),
            "skills_modified": list(self.skills_modified),
            "commands": [c.to_json() for c in self.commands],
            "message": self.message,
        }


@dataclass
class AgentEvent:
    """One event of ``PluginAgent.stream()``: a tool call the model made
    (``step``), a shell command that ran (``command``) and its mmt-plugin
    envelope (``envelope``), a finished loop run (``loop``), a question
    waiting for an answer (``question``), and the result (``done``)."""

    kind: EventKind
    message: str
    data: dict[str, Any] = field(default_factory=dict)
    result: AgentResult | None = None


def _manifest(work: Path) -> dict[str, Any]:
    path = work / "manifest.json"
    try:
        value = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def build_result(
    *,
    thread_id: str,
    work: Path,
    project: Path | None,
    records: Sequence[CommandRecord],
    with_sdk: bool,
    no_eval: bool,
    message: str,
    question: Question | None = None,
    skills_modified: Sequence[str] = (),
) -> AgentResult:
    """The result of a run from what its shell ran and its work folder."""
    runs = loop_runs(records)
    last = runs[-1] if runs else None
    if project is None and last is not None and last.project is not None:
        candidate = Path(last.project)
        project = candidate if candidate.is_absolute() else work / candidate
    info = _manifest(work).get("eval")
    evaluation_info: dict[str, Any] = info if isinstance(info, dict) else {}
    verdict = str(evaluation_info.get("verdict") or "").lower()
    if verdict in ("pass", "fail"):
        evaluation = verdict
    elif no_eval:
        evaluation = "skipped"
    else:
        evaluation = "not_done"
    drift_info = evaluation_info.get("drift")
    drift = drift_info.get("open") if isinstance(drift_info, dict) else None
    unchecked = []
    if not with_sdk:
        unchecked.append("build and test: no SDK")
    if evaluation == "not_done":
        default = "no SDK" if not with_sdk else "no capture, and no leave for a synthetic one"
        unchecked.append(f"evaluation: not done ({evaluation_info.get('reason') or default})")
    if isinstance(drift_info, dict) and drift_info.get("checked") is False:
        unchecked.append("drift: not checked (no tshark)")
    report = work / "REPORT.md"
    questions = work / "questions.md"
    green = last is not None and last.green(with_sdk)
    report_text = report.read_text("utf-8") if report.is_file() else ""
    status: Status
    if skills_modified:
        status = "failed"
    elif question is not None:
        status = "waiting"
    elif "BLOCKED" in report_text or message.strip().endswith("BLOCKED"):
        status = "blocked"
    elif not green:
        status = "not_green"
    elif evaluation == "fail" or (isinstance(drift, int) and drift > 0):
        status = "eval_failed"
    elif evaluation == "not_done" and with_sdk:
        status = "incomplete"
    else:
        status = "done"
    return AgentResult(
        status=status,
        thread_id=thread_id,
        work=work,
        project=project,
        loop=last,
        loop_runs=len(runs),
        with_sdk=with_sdk,
        evaluation=evaluation,
        drift=drift if isinstance(drift, int) else None,
        unchecked=unchecked,
        report_path=report if report.is_file() else None,
        questions_path=questions if questions.is_file() else None,
        question=question,
        skills_modified=list(skills_modified),
        commands=list(records),
        message=message,
    )
