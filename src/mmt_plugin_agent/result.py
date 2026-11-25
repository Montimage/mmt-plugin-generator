"""What a run returns: the loop as the work folder records it (else as the
shell saw it), the work folder's report, and the events
``PluginAgent.stream()`` yields."""

from __future__ import annotations

import json
import re
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
    "work_folder",
    "work_loop",
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
    #: The mmt-plugin command, when known without parsing ``command`` (an
    #: envelope the work folder holds).
    name: str | None = None
    #: When the shell ran it (``time.time_ns()`` before and after).
    started_ns: int | None = None
    ended_ns: int | None = None

    @property
    def mmt_command(self) -> str | None:
        if self.name is not None:
            return self.name
        found = mmt_plugin_command(self.command)
        return found[0] if found else None

    @property
    def project(self) -> str | None:
        found = mmt_plugin_command(self.command)
        return found[1] if found else None

    @property
    def envelope(self) -> dict[str, Any] | None:
        return None if self.mmt_command is None else envelope_of(self.output)

    @property
    def mmt_exit_code(self) -> int | None:
        """mmt-plugin's exit code: its envelope's when the output holds one
        (``mmt-plugin ... | tee FILE`` exits with tee's code, and the
        agent's ``/bin/sh`` has no pipefail), else the shell's."""
        env = self.envelope
        code = None if env is None else env.get("exit_code")
        if isinstance(code, int) and not isinstance(code, bool):
            return code
        return self.exit_code

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
        return {c.mmt_command or "": c.mmt_exit_code for c in self.commands}

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


_RUN_DIR = re.compile(r"run-([0-9]+)")

#: How much older than the run's start an envelope may look: file times
#: come from a coarser clock, on some file systems to 2 seconds.
_CLOCK_SLACK_NS = 2_000_000_000


def work_loop(work: Path, *, since_ns: int | None = None) -> tuple[LoopRun, int] | None:
    """The last loop run the work folder records, and how many it records.

    SKILL.md, Step 4 saves each loop command's envelope as
    ``<work>/runs/run-<n>/<command>.json``. A run counts when it has
    ``validate.json``; its commands are the envelopes in loop order, up to
    the first one missing. With ``since_ns`` (a ``time.time_ns()``), an
    envelope written before it is missing: an earlier run's work folder may
    be reused. None when no run counts."""
    runs: list[tuple[int, LoopRun]] = []
    try:
        dirs = list((work / "runs").iterdir())
    except OSError:
        return None
    for path in dirs:
        found = _RUN_DIR.fullmatch(path.name)
        if found is None or not path.is_dir():
            continue
        number = int(found.group(1))
        records: list[CommandRecord] = []
        for name in LOOP_COMMANDS:
            saved = path / f"{name}.json"
            try:
                stat = saved.stat()
                text = saved.read_text("utf-8")
            except (OSError, UnicodeDecodeError):
                break
            if since_ns is not None and stat.st_mtime_ns < since_ns - _CLOCK_SLACK_NS:
                # Left by an earlier run: as if missing.
                break
            env = envelope_of(text)
            code = None if env is None else env.get("exit_code")
            records.append(
                CommandRecord(str(saved), code if isinstance(code, int) else None, text, name=name)
            )
        if records and records[0].mmt_command == "validate":
            runs.append((number, LoopRun(number, records)))
    if not runs:
        return None
    runs.sort(key=lambda item: item[0])
    return runs[-1][1], len(runs)


def _is_work_folder(path: Path) -> bool:
    return (path / "runs").is_dir() or (path / "manifest.json").is_file()


def work_folder(work: Path) -> Path:
    """The skill's work folder: ``work``, unless it has no ``runs/`` and
    no ``manifest.json`` and exactly one of its subfolders has one (a model
    that made its own ``<label>-plugin/`` in the folder it was given)."""
    if _is_work_folder(work):
        return work
    try:
        found = [p for p in work.iterdir() if p.is_dir() and _is_work_folder(p)]
    except OSError:
        return work
    return found[0] if len(found) == 1 else work


def _project(
    work: Path, given: Path | None, shell: str | None, cwd: Path | None = None
) -> Path | None:
    """The project: the one the run was given, else ``<work>/project``
    (the brief's), else the ``-C`` of the shell's last loop run when it
    names a project (not a shell variable such as ``$P``), relative to
    ``cwd`` (by default ``work``)."""
    if given is not None:
        return given
    if (work / "project" / "plugin.yaml").is_file():
        return work / "project"
    if shell is None or "$" in shell or "`" in shell:
        return None
    return Path(shell) if Path(shell).is_absolute() else (cwd or work) / shell


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
    #: The leave the run had for the evaluation: ``"capture"`` (``--capture``),
    #: ``"synthetic"`` (``--allow-synthetic``), or None.
    eval_leave: str | None = None
    #: Why the shell could read this process's environment, the provider
    #: keys with it (``policy.environ_failure()``): None when it could not,
    #: and off Linux.
    environ_readable: str | None = None

    @property
    def skipped_with_leave(self) -> bool:
        """Green, the evaluation not done although the run had a capture or
        leave for a synthetic one: the model skipped it."""
        return self.status == "incomplete" and self.eval_leave is not None

    @property
    def ok(self) -> bool:
        return self.status in ("done", "incomplete") and not self.skipped_with_leave

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
            "eval_leave": self.eval_leave,
            "environ_readable": self.environ_readable,
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
    since_ns: int | None = None,
    capture: bool = False,
    allow_synthetic: bool = False,
    environ_readable: str | None = None,
) -> AgentResult:
    """The result of a run from its work folder and what its shell ran.

    The loop is the work folder's last run (``work_loop``, the envelopes
    the skill saves), else the shell's: the command text the model wrote
    (variables, ``&&`` chains, loops) is only a fallback. The work folder
    is ``work_folder(work)``, which the result reports as its ``work``.
    ``capture`` and ``allow_synthetic``: the run was given a capture, or
    leave for a synthetic one, so a green run with an SDK whose evaluation
    is not done skipped it (``AgentResult.skipped_with_leave``)."""
    given_work = work
    work = work_folder(given_work)
    runs = loop_runs(records)
    shell_last = runs[-1] if runs else None
    saved = work_loop(work, since_ns=since_ns)
    last, count = saved if saved is not None else (shell_last, len(runs))
    project = _project(
        work, project, None if shell_last is None else shell_last.project, given_work
    )
    if saved is not None and last is not None:
        last.project = None if project is None else str(project)
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
    leave = None
    if not no_eval:
        leave = "capture" if capture else "synthetic" if allow_synthetic else None
    unchecked = []
    if not with_sdk:
        unchecked.append("build and test: no SDK")
    if evaluation == "not_done":
        reason = evaluation_info.get("reason")
        if with_sdk and leave is not None:
            flag = "--capture" if leave == "capture" else "--allow-synthetic"
            why = f"the model skipped the evaluation it had leave for ({flag})"
            unchecked.append(f"evaluation: not done ({why}{f': {reason}' if reason else ''})")
        else:
            default = "no SDK" if not with_sdk else "no capture, and no leave for a synthetic one"
            unchecked.append(f"evaluation: not done ({reason or default})")
    if isinstance(drift_info, dict) and drift_info.get("checked") is False:
        unchecked.append("drift: not checked (no tshark)")
    report = work / "REPORT.md"
    # The ask_user tool writes questions.md in the folder the run was given.
    questions = given_work / "questions.md"
    if not questions.is_file():
        questions = work / "questions.md"
    green = last is not None and last.green(with_sdk)
    status: Status
    if skills_modified:
        status = "failed"
    elif question is not None:
        status = "waiting"
    elif message.strip().upper().startswith("BLOCKED"):
        # The brief's last line: DONE, NOT GREEN or BLOCKED, then the reason.
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
        loop_runs=count,
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
        eval_leave=leave,
        environ_readable=environ_readable,
    )
