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
from mmt_plugin_agent.policy import mmt_plugin_command
from mmt_plugin_agent.result import AgentResult, loop_runs
from mmt_plugin_agent.skills import SKILL_NAME, resolve_skills_dir

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel

__all__ = ["CaseOutcome", "ModelEvalReport", "load_run_evals", "run_model_evals"]

_PROFILE = re.compile(r'^\s*profile: "([^"]+)"', re.MULTILINE)


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

    def drive(self, agent: PluginAgent) -> tuple[AgentResult, list[dict[str, str]]]:
        """Run the agent; the project before each of its loop runs."""
        snapshots: list[dict[str, str]] = []
        result = None
        for event in agent.stream(**self.request()):
            if event.kind == "step" and event.data.get("tool") == "execute":
                found = mmt_plugin_command(str(event.data["args"].get("command", "")))
                if found is not None and found[0] == "validate":
                    snapshots.append(_snapshot(self.rev, self.project))
            result = event.result or result
        assert result is not None
        return result, snapshots

    def check_runs(self, result: AgentResult, snapshots: list[dict[str, str]]) -> set[str]:
        """The agent's loop runs; the packet tests they protect."""
        rev, runner = self.rev, self.runner
        contract = runner.contract
        basic = f"tests/{self.case['params']['label']}-basic.yaml"
        protected: set[str] = set()
        if runner.seed is not None:
            protected = {p for p in runner.seed if p.startswith("tests/")}
        final = _snapshot(rev, self.project)
        states = [*snapshots, final]
        runs = loop_runs(result.commands)
        for n, run in enumerate(runs, 1):
            for record in run.commands:
                env = record.envelope
                if env is None:
                    self.problems.append(
                        f"run {n}: {record.mmt_command}: no envelope in its output"
                    )
                    continue
                _, found = rev.check_envelope(
                    json.dumps(env) + "\n",
                    "",
                    record.mmt_exit_code,
                    record.mmt_command,
                    contract,
                    sdk=self.sdk is not None,
                )
                self.problems += [f"run {n}: {record.mmt_command}: {p}" for p in found]
            failed = next((r for r in run.commands if r.mmt_exit_code != 0), None)
            if failed is not None and n < len(states):
                step = rev.Step(
                    n, [], failed.mmt_command, failed.mmt_exit_code, "", "", failed.envelope
                )
                self.problems += rev.fix_problems(step, states[n - 1], states[n], n + 1)
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
    dirs = [d for d in rev.case_dirs(case_root) if not cases or d.name in cases]
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
                cli=cli or [sys.executable, "-m", "mmt_plugin"],
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
                    status, runs = result.status, result.loop_runs
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
