"""The agent's LangGraph graph: deepagents' ``create_deep_agent`` with the
mmt-plugin-generator skill, the guarded shell and the ``ask_user`` tool.

``build_graph()`` returns the compiled graph, which another LangGraph
application can call as a subgraph: its input is ``{"messages": [...]}``,
the request in a user message (``request_text()`` writes one).
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from mmt_plugin_agent.policy import shell_env
from mmt_plugin_agent.questions import Question, Questioner, QuestionKind, RunMode
from mmt_plugin_agent.result import CommandRecord
from mmt_plugin_agent.skills import (
    SKILL_NAME,
    digest,
    make_snapshot,
    resolve_skills_dir,
    tree_files,
)

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel
    from langchain_core.tools import BaseTool
    from langgraph.graph.state import CompiledStateGraph
    from langgraph.types import Checkpointer

__all__ = ["DEFAULT_TIMEOUT", "RunSettings", "build_graph", "compile_graph", "request_text"]

#: Seconds a shell command may run: ``build`` and ``test --sanitize`` take a while.
DEFAULT_TIMEOUT = 900


@dataclass
class RunSettings:
    """What a run is given (the flags of ``mmt-plugin-agent new``)."""

    work: Path
    project: Path | None = None
    sdk: Path | None = None
    cc: str = "gcc"
    mode: RunMode = "unattended"
    capture: Path | None = None
    allow_synthetic: bool = False
    no_eval: bool = False
    timeout: int = DEFAULT_TIMEOUT


def system_prompt(settings: RunSettings, skills: Path) -> str:
    """The run brief: the skill, the mode, the flags and the paths."""
    s = settings
    skill_md = skills / SKILL_NAME / "SKILL.md"
    if s.mode == "unattended":
        mode = (
            "unattended: no user can answer. Follow SKILL.md's Run modes for unattended "
            "runs. Put every question to the ask_user tool: it records it in "
            f"{s.work / 'questions.md'} and returns the default to take. Never wait for input."
        )
    else:
        mode = (
            "interactive: a user answers. Put every question to the ask_user tool and "
            "use its answer."
        )
    if s.capture is not None:
        capture = f"the user gave one: {s.capture}"
    elif s.allow_synthetic:
        capture = "none given; a synthetic capture is allowed (the capture question's answer)"
    else:
        capture = "none given; no leave for a synthetic capture: ask the capture question"
    if s.sdk is not None:
        sdk = f"{s.sdk}: pass --sdk {s.sdk} to every command that takes it"
    else:
        sdk = "none: stop after generate (SKILL.md, What you need)"
    project = (
        f"the existing project {s.project} (update it in place)"
        if s.project is not None
        else f"{s.work / 'project'} (a new plugin)"
    )
    lines = [
        f"You run the {SKILL_NAME} skill headless, inside mmt-plugin-agent.",
        f"Read {skill_md} first, then the references it names when you reach them,",
        "and follow it exactly. Decide every step from the --json envelopes.",
        "",
        f"- Mode: {mode}",
        f"- Work folder (SKILL.md's <work>): {s.work}. It is yours; use it as given.",
        f"- Project: {project}.",
        f"- SDK prefix: {sdk}.",
        f"- Compiler: {s.cc}.",
        f"- Capture: {capture}.",
        "- Evaluation: "
        + ("skip it: the user passed --no-eval." if s.no_eval else "do it (SKILL.md, Step 6)."),
        f"- The skill's files ({skills}) are read-only: read them, never write there.",
        "- Run commands with the execute tool. Its shell refuses sudo, --system, any path",
        "  under /opt/mmt, and --force unless the user allows it.",
        "- mmt-plugin is on PATH. Save each loop envelope with tee, as SKILL.md says.",
        "- At the end write REPORT.md, manifest.json and README.md in the work folder",
        "  (SKILL.md, Done), then reply with one line: DONE, NOT GREEN or BLOCKED,",
        "  and the reason.",
    ]
    return "\n".join(lines)


def request_text(
    *,
    spec: Path | None = None,
    pcap: Path | None = None,
    pdl: Path | None = None,
    project: Path | None = None,
    change: str | None = None,
    instructions: str | None = None,
) -> str:
    """The user message of a run: what to build or change."""
    if project is not None:
        given = Path(change) if change is not None else None
        what = (
            f"the change described in {given.resolve()}"
            if given is not None and given.is_file()
            else f"this change: {change}"
        )
        text = f"Update the existing mmt-dpi plugin project {project} with {what}."
    elif spec is not None:
        text = f"Write a new mmt-dpi plugin from the protocol specification {spec}."
    elif pcap is not None:
        text = f"Write a new mmt-dpi plugin from the capture {pcap} (the pcap entry)."
    elif pdl is not None:
        text = f"Write a new mmt-dpi plugin from the legacy PDL v1 model {pdl}."
    else:
        raise ValueError("a request needs spec, pcap, pdl or project")
    if instructions:
        text += f"\n\n{instructions}"
    return text


def _ask_user_tool(questioner: Questioner) -> BaseTool:
    from langchain_core.tools import StructuredTool

    def ask_user(question: str, recommended: str, kind: QuestionKind = "other") -> str:
        """Ask the user a question the skill needs answered, with your
        recommended answer. kind is "capture" for the capture question of
        SKILL.md, Step 1, else "other". Unattended, it records the question in
        questions.md and returns the default to take."""
        return questioner.ask(question, recommended, kind)

    return StructuredTool.from_function(ask_user)


def compile_graph(
    model: BaseChatModel,
    settings: RunSettings,
    *,
    skills: Path,
    protected: Sequence[Path],
    questioner: Questioner,
    extra_skills: Sequence[Path] = (),
    tools: Sequence[BaseTool] = (),
    checkpointer: Checkpointer | None = None,
    on_command: Callable[[CommandRecord], None] | None = None,
) -> CompiledStateGraph[Any, Any, Any, Any]:
    """The graph of one run, whose skills are ``skills`` (a read-only copy)."""
    from deepagents import create_deep_agent

    from mmt_plugin_agent.backend import GuardedShellBackend

    writable = [settings.work, Path(tempfile.gettempdir())]
    if settings.project is not None:
        writable.append(settings.project)
    backend = GuardedShellBackend(
        work=settings.work,
        writable=writable,
        protected=[skills, *extra_skills, *protected],
        questioner=questioner,
        env=shell_env(os.environ),
        timeout=settings.timeout,
        on_command=on_command,
    )
    return create_deep_agent(
        model,
        [_ask_user_tool(questioner), *tools],
        system_prompt=system_prompt(settings, skills),
        skills=[f"{skills}/", *(f"{p}/" for p in extra_skills)],
        backend=backend,
        checkpointer=checkpointer,
        name="mmt-plugin-agent",
    )


def build_graph(
    model: str | BaseChatModel | None = None,
    *,
    work_dir: str | os.PathLike[str],
    project: str | os.PathLike[str] | None = None,
    sdk: str | os.PathLike[str] | None = None,
    cc: str = "gcc",
    mode: RunMode = "unattended",
    capture: str | os.PathLike[str] | None = None,
    allow_synthetic: bool = False,
    no_eval: bool = False,
    skills_dir: str | os.PathLike[str] | None = None,
    extra_skills: Sequence[str | os.PathLike[str]] = (),
    tools: Sequence[BaseTool] = (),
    on_question: Callable[[Question], str] | None = None,
    checkpointer: Checkpointer | None = None,
) -> CompiledStateGraph[Any, Any, Any, Any]:
    """The compiled agent graph, to call directly or as a subgraph.

    The skills come from a read-only copy of ``skills_dir`` (resolved as
    ``mmt-plugin-agent --skills``). An interactive graph needs a
    ``checkpointer`` to resume after a question. ``PluginAgent`` adds the
    end-of-run check that the skills were not changed.
    """
    from mmt_plugin_agent.models import resolve_model

    work = Path(work_dir).resolve()
    work.mkdir(parents=True, exist_ok=True)
    settings = RunSettings(
        work=work,
        project=None if project is None else Path(project).resolve(),
        sdk=None if sdk is None else Path(sdk).resolve(),
        cc=cc,
        mode=mode,
        capture=None if capture is None else Path(capture).resolve(),
        allow_synthetic=allow_synthetic,
        no_eval=no_eval,
    )
    source = resolve_skills_dir(skills_dir)
    files = tree_files(source)
    snapshot = make_snapshot(files, f"graph-{digest(files)[:16]}")
    questioner = Questioner(
        mode=mode, work=work, allow_synthetic=allow_synthetic, on_question=on_question
    )
    return compile_graph(
        resolve_model(model),
        settings,
        skills=snapshot,
        protected=[source],
        questioner=questioner,
        extra_skills=[Path(p).resolve() for p in extra_skills],
        tools=tools,
        checkpointer=checkpointer,
    )
