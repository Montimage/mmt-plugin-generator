"""What a run returns: the loop as the shell observed it, corroborated by
the envelopes the work folder records, the work folder's report, and the
events ``PluginAgent.stream()`` yields."""

from __future__ import annotations

import json
import os
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from mmt_plugin_agent.policy import LOOP_COMMANDS, mmt_plugin_command, trusted_invocation
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
    "loop_evidence",
    "loop_runs",
    "work_folder",
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
    #: True when the backend itself executed this command, without the
    #: shell (``trusted_invocation``): the executable is the installation's
    #: own, the arguments exactly the parsed tokens, the exit code and the
    #: output the process's own — the only evidence the model cannot forge.
    trusted: bool = False
    #: True when this trusted execution is the skill's capture evaluation,
    #: its arguments bound to the run by the backend (the canonical
    #: ``pcap_eval.py``, the run's SDK and compiler, the project's build
    #: output, the capture, no ``--help``): exit 0 is the evaluation's
    #: PASS, exit 1 its FAIL — never anything ``manifest.json`` says.
    evaluation: bool = False

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
        """mmt-plugin's exit code, when it is known. A trusted record's exit
        code is the process's own — the backend ran it, tee and all, so it
        is authoritative even at 0. Otherwise its envelope's when the output
        holds one, but the shell's text is the model's: an envelope in
        untrusted output is evidence of nothing but failure. Without an
        envelope, a non-zero shell exit code is a failure whoever it belongs
        to, but a zero one is not mmt-plugin's success: the output may be
        redirected to a file, lost in a pipe or written by something else,
        so None (unknown)."""
        if self.trusted:
            # The process's exit code is real, but exit 0 alone is not the
            # loop step's success: ``mmt-plugin validate --help`` exits 0
            # and validates nothing, and without ``--json`` there is no
            # envelope at all. A trusted record is the step's evidence only
            # with a parseable envelope of the same command, whose exit
            # code is the process's; anything else is unknown.
            env = envelope_of(self.output)
            if env is None or env.get("command") != self.mmt_command:
                return None
            code = env.get("exit_code")
            if not isinstance(code, int) or isinstance(code, bool) or code != self.exit_code:
                return None
            return code
        env = self.envelope
        code = None if env is None else env.get("exit_code")
        if isinstance(code, int) and not isinstance(code, bool):
            return code
        return self.exit_code or None

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

    def parents_exist(self) -> str | None:
        """The status of validate's ``parents-exist`` check in this run,
        or None when its envelope does not say."""
        for record in self.commands:
            if record.mmt_command == "validate":
                env = record.envelope or {}
                checks = (env.get("result") or {}).get("checks")
                if not isinstance(checks, list):
                    return None
                for check in checks:
                    if isinstance(check, dict) and check.get("id") == "parents-exist":
                        status = check.get("status")
                        return status if isinstance(status, str) else None
                return None
        return None

    def _sdk_profile(self, record: CommandRecord) -> str | None:
        """The ``--sdk-profile`` value of a no-SDK loop command, from its
        strict invocation (the backend executed exactly these tokens), or
        None when it cannot be read off the command."""
        invocation = trusted_invocation(record.command)
        if invocation is None:
            return None
        _, args, _, _, _ = invocation
        if len(args) >= 2 and args[-2] == "--sdk-profile":
            return args[-1]
        return None

    def green(self, with_sdk: bool) -> bool:
        """Whether this run is green (SKILL.md, Done): the loop's exact
        ordered sequence — ``validate``, ``generate``, ``build``, ``test``
        with an SDK, the first two without — one each, in order, each
        exiting 0. Presence is not enough: a ``test`` before its ``build``,
        a command twice or a step missing proves nothing of the sequence
        the skill certifies, however green each exit code looks. A run that
        stopped short or failed is simply not green. Without an SDK the
        two commands must pin the same profile: a model validated against
        one and generated for another was never checked as it generated."""
        need = list(LOOP_COMMANDS if with_sdk else LOOP_COMMANDS[:2])
        if [c.mmt_command for c in self.commands] != need:
            return False
        codes = self.exit_codes()
        if any(codes.get(name) != 0 for name in need):
            return False
        if not with_sdk:
            profiles = [self._sdk_profile(c) for c in self.commands]
            return profiles[0] is not None and profiles[0] == profiles[1]
        # SKILL.md, Done: validate's parents-exist check is pass.
        if self.parents_exist() != "pass":
            return False
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


def _record_project(record: CommandRecord, cwd: Path) -> str:
    """The real path a trusted loop command targets: its ``-C`` resolved
    against the backend's working directory (the cwd the backend ran it
    with), or that directory when no ``-C`` is given."""
    target = record.project
    if target is None:
        return os.path.realpath(cwd)
    path = target if os.path.isabs(target) else str(cwd / target)
    return os.path.realpath(path)


def loop_evidence(records: Sequence[CommandRecord], cwd: Path, *, project: Path) -> list[LoopRun]:
    """The loop runs of one run of the agent, failing closed.

    The only evidence is the backend's own executions (``CommandRecord``
    ``trusted``): the executable is this installation's ``mmt_plugin``
    module in isolated mode, the arguments exactly the tokens of the strict
    invocation, the exit code and output the process's own, and the output
    holds a parseable envelope of the same command whose exit code is the
    process's — exit 0 alone proves nothing (``--help`` exits 0). Every
    step must target ``project`` (its ``-C``, resolved against ``cwd``):
    a green loop of another project is no evidence of this one's.
    Everything else the shell ran — shell loops, pipelines the backend did
    not execute, redirections, substitutions, envelopes in shell text,
    shadowing executables — is the model's word, and the envelopes in
    ``runs/run-<n>/`` are files the model can write: audit artifacts, never
    proof. Each ``validate`` evidence starts a new run."""
    # The expected path with its parent resolved but the final component
    # lexical: a symlink planted at the project path itself resolves the
    # ``-C`` target away from it, never towards it.
    expected = os.path.join(os.path.realpath(project.parent), project.name)
    runs: list[LoopRun] = []
    for record in records:
        command = record.mmt_command
        if command not in LOOP_COMMANDS or record.refused or not record.trusted:
            continue
        if _record_project(record, cwd) != expected:
            continue
        if command == "validate" or not runs:
            runs.append(LoopRun(len(runs) + 1, project=record.project))
        runs[-1].commands.append(record)
    return runs


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
    capture: bool = False,
    allow_synthetic: bool = False,
    environ_readable: str | None = None,
) -> AgentResult:
    """The result of a run from what its shell ran, corroborated by its
    work folder.

    The loop is ``loop_evidence``'s: only the backend's own executions
    (``CommandRecord`` ``trusted``) are evidence — the work folder is the
    model's to write and shell text can be forged, so artifacts and shell
    envelopes alone never make a step succeed. For the same reason
    ``manifest.json``'s PASS counts only when the backend ran the capture
    evaluation itself (exit 0). The
    work folder is ``work_folder(work)``, which the result reports as its
    ``work``. ``capture`` and ``allow_synthetic``: the run was given a
    capture, or leave for a synthetic one, so a green run with an SDK whose
    evaluation is not done skipped it (``AgentResult.skipped_with_leave``)."""
    given_work = work
    work = work_folder(given_work)
    expected = project if project is not None else work / "project"
    runs = loop_evidence(records, given_work, project=expected)
    last = runs[-1] if runs else None
    count = len(runs)
    project = _project(work, project, None if last is None else last.project, given_work)
    if last is not None:
        last.project = None if project is None else str(project)
    info = _manifest(work).get("eval")
    evaluation_info: dict[str, Any] = info if isinstance(info, dict) else {}
    verdict = str(evaluation_info.get("verdict") or "").lower()
    # The evaluation's verdict is the backend's own executions, never
    # manifest.json (the model's to write: audit only, for the details and
    # the drift). A trusted evaluation counts only after a trusted green
    # loop in the same run and before any later trusted build or test: it
    # is the evaluation *of that build* (SKILL.md, Done), and a rebuild
    # after it is not the binary it measured. The last verdict decides: a
    # FAIL fixed and evaluated again is the PASS.
    positions = {id(record): i for i, record in enumerate(records)}
    green_ends = [
        positions[id(run.commands[-1])] for run in runs if run.commands and run.green(with_sdk)
    ]
    last_build = max(
        (
            i
            for i, record in enumerate(records)
            if record.trusted and not record.refused and record.mmt_command in ("build", "test")
        ),
        default=-1,
    )
    verdicts = [
        record.exit_code
        for i, record in enumerate(records)
        if record.evaluation
        and record.trusted
        and not record.refused
        and any(end < i for end in green_ends)
        and i > last_build
        and record.exit_code in (0, 1)
    ]
    trusted_verdict = verdicts[-1] if verdicts else None
    if trusted_verdict == 0:
        evaluation = "pass"
    elif trusted_verdict == 1 or verdict == "fail":
        evaluation = "fail"
    elif no_eval:
        evaluation = "skipped"
    else:
        evaluation = "not_done"
    eval_backed = trusted_verdict == 0
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
        if verdict == "pass" and not eval_backed:
            unchecked.append(
                "evaluation: not done (manifest.json's PASS is the model's say-so: "
                "no trusted run of the capture evaluation (pcap_eval.py) of the green "
                "build reached exit 0)"
            )
        elif with_sdk and leave is not None:
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
