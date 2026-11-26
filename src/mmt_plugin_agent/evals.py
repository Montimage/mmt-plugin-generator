"""``mmt-plugin-agent eval``: each model drafts every case of the skill's
``evals/cases/``, and ``run_evals.py``'s checks judge the result.

Where ``run_evals.py`` plays the agent with a case's scripted edits, here
the model is the agent, so its loop runs need not stop where the script
does. What is checked: every envelope the agent's loop got against the
contract, that each fix touches what the failed run reported, that no
packet test is deleted or rewritten, that the final loop (run again here)
is green, and, for an update, that the project keeps its label, id,
profile, parents and packet tests. The capture evaluation is not run
(``no_eval``). Writes a results table, Markdown and JSON.
"""

from __future__ import annotations

import importlib.util
import itertools
import json
import os
import re
import shutil
import sys
import time
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING, Any

from mmt_plugin.exitcodes import ExitCode
from mmt_plugin_agent.api import PluginAgent
from mmt_plugin_agent.errors import AgentError
from mmt_plugin_agent.graph import DEFAULT_TIMEOUT
from mmt_plugin_agent.policy import LOOP_COMMANDS
from mmt_plugin_agent.result import AgentResult, envelope_of, loop_runs
from mmt_plugin_agent.skills import SKILL_NAME, resolve_skills_dir

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel

__all__ = [
    "CaseOutcome",
    "ModelEvalReport",
    "SavedRun",
    "load_run_evals",
    "run_model_evals",
    "saved_runs",
]

_PROFILE = re.compile(r'^\s*profile: "([^"]+)"', re.MULTILINE)
_RUN_DIR = re.compile(r"run-([0-9]+)")


@dataclass
class SavedRun:
    """One ``runs/run-<n>/`` of the work folder: the envelopes the skill
    saved there (SKILL.md, Step 4). ``loop`` holds each ``<command>.json``
    whose envelope it is; ``others`` the directory's other envelopes, by
    file name (an entry check such as ``validate-nosdk.json``)."""

    number: int
    path: Path
    loop: dict[str, dict[str, Any]] = field(default_factory=dict)
    others: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
    #: When its ``validate.json`` was written (its mtime): the run's start.
    started_ns: int | None = None


def saved_runs(work: Path) -> list[SavedRun]:
    """Every ``<work>/runs/run-<n>/``, in numeric order. A run of the loop
    is one with ``validate.json``, as for ``result.loop_evidence``."""
    try:
        dirs = list((work / "runs").iterdir())
    except OSError:
        return []
    runs = []
    for path in dirs:
        found = _RUN_DIR.fullmatch(path.name)
        if found is None or not path.is_dir():
            continue
        run = SavedRun(int(found.group(1)), path)
        for saved in sorted(path.glob("*.json")):
            try:
                text = saved.read_text("utf-8")
                mtime = saved.stat().st_mtime_ns
            except (OSError, UnicodeDecodeError):
                continue
            env = envelope_of(text)
            if env is None:
                continue
            if saved.stem in LOOP_COMMANDS:
                run.loop[saved.stem] = env
                if saved.stem == "validate":
                    run.started_ns = mtime
            else:
                run.others.append((saved.name, env))
        runs.append(run)
    runs.sort(key=lambda run: run.number)
    return runs


def _state_at(snapshots: Sequence[tuple[int, dict[str, str]]], when: int | None) -> dict[str, str]:
    """The project as the last snapshot taken by ``when`` saw it (the
    first one when none was, or ``when`` is unknown)."""
    if not snapshots:
        return {}
    state = snapshots[0][1]
    for taken, snap in snapshots:
        if when is None or taken > when:
            break
        state = snap
    return state


def load_run_evals(skills: Path) -> ModuleType:
    """The skill's ``evals/run_evals.py``, loaded from its file."""
    path = skills / SKILL_NAME / "evals" / "run_evals.py"
    spec = importlib.util.spec_from_file_location("mmt_plugin_agent_run_evals", path)
    if spec is None or spec.loader is None or not path.is_file():
        raise AgentError(
            ExitCode.SDK,
            "agent.skills-not-found",
            f"no eval runner at {path}",
            f"pass --skills DIR, a directory holding {SKILL_NAME}/evals/run_evals.py",
        )
    module = importlib.util.module_from_spec(spec)
    # Its dataclasses look their module up by name while they are made.
    sys.modules[spec.name] = module
    keep = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = keep
    return module


@dataclass
class CaseOutcome:
    model: str
    case: str
    green: bool
    status: str
    loop_runs: int
    seconds: float
    work: str
    problems: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.green and not self.problems

    def to_json(self) -> dict[str, Any]:
        return {**asdict(self), "ok": self.ok}


@dataclass
class ModelEvalReport:
    outcomes: list[CaseOutcome] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(o.ok for o in self.outcomes)

    def to_json(self) -> dict[str, Any]:
        return {"ok": self.ok, "outcomes": [o.to_json() for o in self.outcomes]}

    def markdown(self) -> str:
        lines = [
            "# mmt-plugin-agent model evals",
            "",
            "| Model | Case | Result | Green | Status | Loop runs | Seconds | Problems |",
            "|---|---|---|---|---|---:|---:|---|",
        ]
        for o in self.outcomes:
            problems = "<br>".join(p.replace("|", "\\|") for p in o.problems) or "none"
            lines.append(
                f"| {o.model} | {o.case} | {'PASS' if o.ok else 'FAIL'} | "
                f"{'yes' if o.green else 'no'} | {o.status} | {o.loop_runs} | "
                f"{o.seconds:.0f} | {problems} |"
            )
        lines.append("")
        for model in dict.fromkeys(o.model for o in self.outcomes):
            mine = [o for o in self.outcomes if o.model == model]
            lines.append(f"- {model}: {sum(o.ok for o in mine)} of {len(mine)} cases pass")
        return "\n".join(lines) + "\n"


def _name(model: str | BaseChatModel) -> str:
    if isinstance(model, str):
        return model
    named = getattr(model, "model", None) or getattr(model, "model_name", None)
    return str(named) if named else type(model).__name__


def _slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", text).strip("-") or "model"


def _snapshot(rev: ModuleType, project: Path) -> dict[str, str]:
    found: dict[str, str] = rev.snapshot(project) if project.is_dir() else {}
    return found


class _Case:
    """One model on one case."""

    def __init__(
        self,
        rev: ModuleType,
        case_dir: Path,
        work: Path,
        *,
        sdk: Path | None,
        cc: str,
        cli: Sequence[str],
        timeout: int,
    ) -> None:
        self.rev = rev
        self.case_dir = case_dir
        self.work = work
        self.sdk = sdk
        self.runner = rev.Runner(
            case_dir, cli=cli, work=work / "check", sdk=sdk, cc=cc, timeout=float(timeout)
        )
        self.case: dict[str, Any] = self.runner.case
        self.update = self.case["entry"] == "update"
        self.agent_work = work / "agent"
        if not self.update:
            self.runner.project = self.agent_work / "project"
        self.runner.values["project"] = str(self.runner.project)
        self.loop = self.runner.blocks["loop sdk" if sdk is not None else "loop no-sdk"]
        self.problems: list[str] = []

    @property
    def project(self) -> Path:
        project: Path = self.runner.project
        return project

    def _pin(self, text: str) -> None:
        found = _PROFILE.search(text)
        if found is not None:
            self.runner.values["profile"] = found.group(1)

    def seed(self) -> bool:
        """An update's project, copied and green before the agent starts."""
        shutil.copytree(self.case_dir / self.case["project"], self.project, symlinks=True)
        self.runner.seed = self.rev.snapshot(self.project)
        self._pin(self.runner.seed.get("plugin.yaml", ""))
        ok: bool = self.runner.baseline(self.loop)
        return ok

    def request(self) -> dict[str, Any]:
        params = self.case["params"]
        inputs = str(self.case_dir / self.case["input"])
        told = (
            f"Use the label {params['label']}, the id {params['id']} and the parent "
            f"{params['selector']}."
        )
        if self.update:
            return {"project": self.project, "change": inputs}
        if self.case["entry"] == "spec":
            return {"spec": inputs, "instructions": told}
        if self.case["entry"] == "pcap":
            pcap = str(params["pcap"]).replace("{case}", str(self.case_dir))
            return {"pcap": pcap, "instructions": f"{told} The notes in {inputs} describe it."}
        pdl = str(params["pdl"]).replace("{case}", str(self.case_dir))
        return {"pdl": pdl, "instructions": told}

    def drive(self, agent: PluginAgent) -> tuple[AgentResult, list[tuple[int, dict[str, str]]]]:
        """Run the agent; the project before each of its tool calls, with
        the ``time.time_ns()`` it was taken at (a step event comes before
        its tool runs)."""
        snapshots: list[tuple[int, dict[str, str]]] = []
        result = None
        for event in agent.stream(**self.request()):
            if event.kind == "step":
                snapshots.append((time.time_ns(), _snapshot(self.rev, self.project)))
            result = event.result or result
        assert result is not None
        return result, snapshots

    def save_commands(self, result: AgentResult) -> None:
        """What the agent's shell ran, one JSON line per command, in
        ``<case work>/commands.jsonl``: to diagnose a failing row."""
        lines = [
            json.dumps(
                {
                    "command": record.command,
                    "mmt_command": record.mmt_command,
                    "exit_code": record.exit_code,
                    "mmt_exit_code": record.mmt_exit_code,
                    "refused": record.refused,
                    "started_ns": record.started_ns,
                    "ended_ns": record.ended_ns,
                }
            )
            + "\n"
            for record in result.commands
        ]
        (self.work / "commands.jsonl").write_text("".join(lines), "utf-8")

    def misplaced(self, result: AgentResult) -> str | None:
        """Why the agent's work folder or project is not where the brief
        puts them, or None."""
        expected = self.project.resolve()
        if result.work.resolve() != self.agent_work.resolve():
            return (
                f"the model nested its work folder at {result.work}; the brief says "
                f"{self.agent_work} is the work folder, with the project at {expected}"
            )
        if result.project is not None and result.project.resolve() != expected:
            return f"the model put the project at {result.project}; the brief says {expected}"
        return None

    def _loop(self, result: AgentResult) -> list[tuple[str, int | None, dict[str, Any], bool]]:
        """The agent's loop runs, each with its label, when it started and
        its envelopes by command and whether the work folder saved them;
        every envelope checked against the contract.

        The work folder's ``runs/run-<n>/`` (``saved_runs``) are the runs,
        each started when its ``validate.json`` was written; each of their
        envelopes is checked, an entry check too. Only when the work folder
        records no run, the shell's (``loop_runs``), with the envelopes in
        the commands' output: shell text (variables, loops) cannot say which
        command ran, so it is only that fallback, and a run there may stop
        short (an entry check is a ``validate`` too)."""
        sdk = self.sdk is not None
        contract = self.runner.contract

        def check(where: str, command: str | None, env: dict[str, Any]) -> None:
            _, found = self.rev.check_envelope(
                json.dumps(env) + "\n", "", env.get("exit_code"), command, contract, sdk=sdk
            )
            self.problems.extend(f"{where}: {p}" for p in found)

        runs: list[tuple[str, int | None, dict[str, Any], bool]] = []
        saved = saved_runs(result.work)
        if any("validate" in run.loop for run in saved):
            for run in saved:
                where = f"runs/{run.path.name}"
                for name, env in run.loop.items():
                    # The file names the command: a generate.json holding
                    # validate's envelope breaks the contract.
                    check(f"{where}/{name}.json", name, env)
                for file_name, env in run.others:
                    check(f"{where}/{file_name}", env.get("command"), env)
                if "validate" in run.loop:
                    runs.append((where, run.started_ns, run.loop, True))
            return runs
        for shell in loop_runs(result.commands):
            where = f"run {shell.number}"
            envelopes: dict[str, Any] = {}
            for record in shell.commands:
                printed = record.envelope
                command = record.mmt_command
                if printed is None:
                    self.problems.append(
                        f"{where}: {command}: no envelope in its output, and the work "
                        "folder's runs/ records no run"
                    )
                    continue
                check(f"{where}: {command}", command, printed)
                envelopes.setdefault(command or "", printed)
            runs.append((where, shell.commands[0].started_ns, envelopes, False))
        return runs

    def check_runs(
        self,
        result: AgentResult,
        snapshots: Sequence[tuple[int, dict[str, str]]],
        *,
        project: bool = True,
    ) -> set[str]:
        """The agent's loop runs (``_loop``); the packet tests they protect.
        A run's loop commands run in order up to the first that exits non-zero
        (its stop); in the work folder, one before it with no envelope is a
        problem. The project
        before a run is the last snapshot taken by its start; each failed
        run's fix is the change to the next run's. Without ``project``, only
        the envelopes are checked."""
        rev, runner = self.rev, self.runner
        names = LOOP_COMMANDS if self.sdk is not None else LOOP_COMMANDS[:2]
        basic = f"tests/{self.case['params']['label']}-basic.yaml"
        protected: set[str] = set()
        if runner.seed is not None:
            protected = {p for p in runner.seed if p.startswith("tests/")}
        runs = self._loop(result)
        final = _snapshot(rev, self.project)
        states = [*(_state_at(snapshots, started) for _, started, _, _ in runs), final]
        for n, (where, _, envelopes, saved) in enumerate(runs, 1):
            failed = None
            for name in names:
                env = envelopes.get(name)
                if env is None:
                    if saved:
                        self.problems.append(f"{where}: {name}: no envelope ({name}.json)")
                    break
                if env.get("exit_code") != 0:
                    failed = name, env
                    break
            if project and failed is not None:
                name, env = failed
                step = rev.Step(n, [], name, env.get("exit_code"), "", "", env)
                self.problems += rev.fix_problems(step, states[n - 1], states[n], n + 1)
        if not project:
            return protected
        for n, (before, after) in enumerate(itertools.pairwise(states), 1):
            if runner.seed is None:
                protected |= {p for p in before if p.startswith("tests/") and p != basic}
            runner.check_tests(n, protected, before, after)
        return protected

    def final(self, protected: set[str]) -> bool:
        """The loop once more, here, on the agent's project: is it green?"""
        runner = self.runner
        self._pin((self.project / "plugin.yaml").read_text("utf-8"))
        steps = []
        failure = None
        for args in self.loop:
            step = runner.execute(99, args)
            steps.append(step)
            if step.returncode != 0:
                failure = step
                break
        if failure is not None:
            runner.result.problems.append(
                f"final: the loop stops at {failure.command} "
                f"({(failure.envelope or {}).get('error')})"
            )
        else:
            runner.check_green(steps, failure, protected)
        runner.finish()
        green: bool = runner.result.green
        return green


def run_model_evals(
    models: Sequence[str | BaseChatModel],
    *,
    out: str | Path,
    sdk: str | Path | None = None,
    cc: str = "gcc",
    cases: Sequence[str] = (),
    cases_dir: str | Path | None = None,
    skills_dir: str | Path | None = None,
    work_root: str | Path | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    cli: Sequence[str] | None = None,
) -> ModelEvalReport:
    """Every case (or those named in ``cases``) with every model; the
    table goes to ``out`` (Markdown) and ``out`` with ``.json``."""
    source = resolve_skills_dir(skills_dir)
    rev = load_run_evals(source)
    out_path = Path(out).resolve()
    root = Path(work_root).resolve() if work_root else out_path.parent / f"{out_path.stem}-work"
    case_root = Path(cases_dir).resolve() if cases_dir else rev.CASES_DIR
    available = {d.name for d in rev.case_dirs(case_root)}
    unmatched = sorted({c for c in cases} - available)
    if unmatched:
        raise AgentError(
            ExitCode.USAGE,
            "agent.bad-case",
            f"no eval case named {', '.join(unmatched)} in {case_root}",
            "pass --case with one of: " + ", ".join(sorted(available) or ["(none)"]),
        )
    dirs = [d for d in rev.case_dirs(case_root) if not cases or d.name in cases]
    # As PluginAgent: MMT_BASE when no sdk is given.
    sdk = sdk if sdk is not None else os.environ.get("MMT_BASE") or None
    prefix = None if sdk is None else Path(sdk).resolve()
    report = ModelEvalReport()
    for model in models:
        for case_dir in dirs:
            work = root / _slug(_name(model)) / case_dir.name
            if work.exists():
                shutil.rmtree(work)
            work.mkdir(parents=True)
            started = time.monotonic()
            case = _Case(
                rev,
                case_dir,
                work,
                sdk=prefix,
                cc=cc,
                cli=cli or [sys.executable, "-I", "-m", "mmt_plugin"],
                timeout=timeout,
            )
            status, runs, green = "failed", 0, False
            try:
                if not case.update or case.seed():
                    agent = PluginAgent(
                        model,
                        sdk=prefix,
                        cc=cc,
                        work_dir=case.agent_work,
                        no_eval=True,
                        skills_dir=source,
                        timeout=timeout,
                    )
                    result, snapshots = case.drive(agent)
                    case.save_commands(result)
                    status, runs = result.status, result.loop_runs
                    misplaced = case.misplaced(result)
                    if misplaced is not None:
                        # The project checks would read a project that is not there.
                        case.problems.append(misplaced)
                        case.check_runs(result, snapshots, project=False)
                    else:
                        protected = case.check_runs(result, snapshots)
                        green = case.final(protected)
            except Exception as exc:
                # One case's failure (the provider, a broken case) is its row
                # of the table; the other cases still run.
                case.problems.append(f"error: {type(exc).__name__}: {exc}")
            report.outcomes.append(
                CaseOutcome(
                    model=_name(model),
                    case=case_dir.name,
                    green=green,
                    status=status,
                    loop_runs=runs,
                    seconds=time.monotonic() - started,
                    work=str(work),
                    problems=[*case.runner.result.problems, *case.problems],
                )
            )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report.markdown(), "utf-8")
    out_path.with_suffix(".json").write_text(
        json.dumps(report.to_json(), indent=2) + "\n", "utf-8"
    )
    return report
