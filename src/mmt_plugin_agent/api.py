"""The public API: ``PluginAgent`` runs the mmt-plugin-generator skill
headless on one request and returns its result (``docs/agent-api.md``)."""

from __future__ import annotations

import importlib.util
import os
import sys
import time
import uuid
from collections.abc import AsyncIterator, Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, NoReturn

from mmt_plugin.exitcodes import ExitCode
from mmt_plugin_agent import models
from mmt_plugin_agent.doctor import MIN_PYTHON, DoctorReport, run_doctor
from mmt_plugin_agent.errors import AgentError
from mmt_plugin_agent.graph import DEFAULT_TIMEOUT, RunSettings, compile_graph, request_text
from mmt_plugin_agent.policy import LOOP_COMMANDS, environ_failure, is_system_prefix
from mmt_plugin_agent.questions import Question, Questioner, RunMode
from mmt_plugin_agent.result import AgentEvent, AgentResult, CommandRecord, build_result, loop_runs
from mmt_plugin_agent.skills import (
    digest,
    make_snapshot,
    remove_tree,
    resolve_skills_dir,
    restore,
    tree_files,
)

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel
    from langchain_core.runnables import RunnableConfig
    from langchain_core.tools import BaseTool
    from langgraph.graph.state import CompiledStateGraph
    from langgraph.types import Checkpointer

__all__ = ["RECURSION_LIMIT", "PluginAgent", "extra_missing"]

#: Graph steps per run; each tool call takes two (model, tools).
RECURSION_LIMIT = 2000


def extra_missing() -> str | None:
    """Why the agent cannot run here (Python < 3.11, no agent extra), or None."""
    if sys.version_info[:2] < MIN_PYTHON:
        return f"Python {sys.version_info.major}.{sys.version_info.minor}"
    for name in ("deepagents", "langgraph", "langchain"):
        if importlib.util.find_spec(name) is None:
            return f"no {name}"
    return None


def _require_extra() -> None:
    why = extra_missing()
    if why is not None:
        raise AgentError(
            ExitCode.SDK,
            "agent.needs-extra",
            f"mmt-plugin-agent needs Python 3.11+ and the agent extra ({why})",
            "install it with Python 3.11+: pip install 'mmt-plugin[agent]'",
        )


def _input(path: str | os.PathLike[str] | None, what: str) -> Path | None:
    if path is None:
        return None
    found = Path(path).resolve()
    if not found.is_file():
        raise AgentError(
            ExitCode.MODEL,
            "agent.bad-input",
            f"no {what} file at {path}",
            f"pass the path of an existing {what} file",
        )
    return found


@dataclass
class _Run:
    thread_id: str
    settings: RunSettings
    source: Path
    files: Mapping[str, bytes]
    digest: str
    snapshot: Path
    graph: CompiledStateGraph[Any, Any, Any, Any]
    records: list[CommandRecord] = field(default_factory=list)
    seen: int = 0
    loops: int = 0
    started_ns: int = field(default_factory=time.time_ns)


@dataclass
class _Stream:
    question: Question | None = None
    message: str = ""


class PluginAgent:
    """Runs the mmt-plugin-generator skill on one request.

    ``model`` is a LangChain chat model or a ``provider:model`` string
    (default: ``MMT_PLUGIN_AGENT_MODEL``); ``sdk`` an mmt-dpi prefix
    (default: ``MMT_BASE``). ``mode`` is ``unattended`` (questions go to
    ``questions.md`` with their safe default) or ``interactive`` (the run
    stops at a question with status ``waiting``; ``resume()`` answers it).
    ``on_question`` answers questions itself, in either mode.
    """

    def __init__(
        self,
        model: str | BaseChatModel | None = None,
        *,
        sdk: str | os.PathLike[str] | None = None,
        cc: str | None = None,
        work_dir: str | os.PathLike[str] | None = None,
        mode: RunMode = "unattended",
        capture: str | os.PathLike[str] | None = None,
        allow_synthetic: bool = False,
        no_eval: bool = False,
        skills_dir: str | os.PathLike[str] | None = None,
        extra_skills: Sequence[str | os.PathLike[str]] = (),
        tools: Sequence[BaseTool] = (),
        on_question: Callable[[Question], str] | None = None,
        checkpointer: Checkpointer | None = None,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> None:
        if mode not in ("unattended", "interactive"):
            raise AgentError(
                ExitCode.USAGE,
                "agent.bad-mode",
                f"unknown mode {mode!r}",
                "use unattended or interactive",
            )
        self.model = model
        sdk = sdk if sdk is not None else os.environ.get("MMT_BASE") or None
        self._sdk_given = None if sdk is None else Path(os.path.abspath(sdk))
        # Refused at the run (an SDK prefix under /opt/mmt), and not resolved.
        self.sdk = (
            None
            if self._sdk_given is None
            else self._sdk_given
            if is_system_prefix(self._sdk_given)
            else self._sdk_given.resolve()
        )
        self.cc = cc or os.environ.get("CC") or "gcc"
        self.work_dir = None if work_dir is None else Path(work_dir)
        self.mode: RunMode = mode
        self.capture = _input(capture, "capture")
        self.allow_synthetic = allow_synthetic
        self.no_eval = no_eval
        self.skills_dir = skills_dir
        self.extra_skills = [Path(p).resolve() for p in extra_skills]
        self.tools = list(tools)
        self.on_question = on_question
        self.timeout = timeout
        self._checkpointer = checkpointer
        self._runs: dict[str, _Run] = {}

    # --- requests -------------------------------------------------------

    def new(
        self,
        *,
        spec: str | os.PathLike[str] | None = None,
        pcap: str | os.PathLike[str] | None = None,
        pdl: str | os.PathLike[str] | None = None,
        instructions: str | None = None,
        thread_id: str | None = None,
    ) -> AgentResult:
        """A new plugin from a spec, a capture or a PDL v1 model."""
        return _result(
            self.stream(
                spec=spec, pcap=pcap, pdl=pdl, instructions=instructions, thread_id=thread_id
            )
        )

    def update(
        self,
        project: str | os.PathLike[str],
        *,
        change: str,
        instructions: str | None = None,
        thread_id: str | None = None,
    ) -> AgentResult:
        """Update an existing project; ``change`` is a file or the change's text."""
        return _result(
            self.stream(
                project=project, change=change, instructions=instructions, thread_id=thread_id
            )
        )

    async def anew(
        self,
        *,
        spec: str | os.PathLike[str] | None = None,
        pcap: str | os.PathLike[str] | None = None,
        pdl: str | os.PathLike[str] | None = None,
        instructions: str | None = None,
        thread_id: str | None = None,
    ) -> AgentResult:
        return await _aresult(
            self.astream(
                spec=spec, pcap=pcap, pdl=pdl, instructions=instructions, thread_id=thread_id
            )
        )

    async def aupdate(
        self,
        project: str | os.PathLike[str],
        *,
        change: str,
        instructions: str | None = None,
        thread_id: str | None = None,
    ) -> AgentResult:
        return await _aresult(
            self.astream(
                project=project, change=change, instructions=instructions, thread_id=thread_id
            )
        )

    def stream(
        self,
        *,
        spec: str | os.PathLike[str] | None = None,
        pcap: str | os.PathLike[str] | None = None,
        pdl: str | os.PathLike[str] | None = None,
        project: str | os.PathLike[str] | None = None,
        change: str | None = None,
        instructions: str | None = None,
        thread_id: str | None = None,
    ) -> Iterator[AgentEvent]:
        """Run a request (as ``new``, or ``update`` with ``project``), yielding
        its events; the last one, ``done``, carries the result."""
        run, text = self._start(spec, pcap, pdl, project, change, instructions, thread_id)
        yield from self._drive(run, {"messages": [{"role": "user", "content": text}]})

    async def astream(
        self,
        *,
        spec: str | os.PathLike[str] | None = None,
        pcap: str | os.PathLike[str] | None = None,
        pdl: str | os.PathLike[str] | None = None,
        project: str | os.PathLike[str] | None = None,
        change: str | None = None,
        instructions: str | None = None,
        thread_id: str | None = None,
    ) -> AsyncIterator[AgentEvent]:
        run, text = self._start(spec, pcap, pdl, project, change, instructions, thread_id)
        async for event in self._adrive(run, {"messages": [{"role": "user", "content": text}]}):
            yield event

    def resume(self, thread_id: str, answer: str) -> AgentResult:
        """Answer the question a ``waiting`` run stopped at, and go on."""
        return _result(self.stream_resume(thread_id, answer))

    def stream_resume(self, thread_id: str, answer: str) -> Iterator[AgentEvent]:
        from langgraph.types import Command

        yield from self._drive(self._waiting(thread_id), Command(resume=answer))

    def release(self, thread_id: str) -> None:
        """Forget a ``waiting`` run that will not be resumed: remove its
        skills snapshot. A run that ended is released already."""
        run = self._runs.get(thread_id)
        if run is not None:
            self._release(run)

    def doctor(self) -> DoctorReport:
        """What this machine has of what a run needs."""
        return run_doctor(
            sdk=self.sdk,
            cc=self.cc,
            skills_dir=self.skills_dir,
            model=self.model if isinstance(self.model, str) else None,
            model_object=not isinstance(self.model, (str, type(None))),
        )

    # --- one run --------------------------------------------------------

    def _waiting(self, thread_id: str) -> _Run:
        run = self._runs.get(thread_id)
        if run is None:
            raise AgentError(
                ExitCode.USAGE,
                "agent.unknown-thread",
                f"no run is waiting with thread id {thread_id}",
                "resume a thread this PluginAgent started and that stopped at a question",
            )
        return run

    def _start(
        self,
        spec: str | os.PathLike[str] | None,
        pcap: str | os.PathLike[str] | None,
        pdl: str | os.PathLike[str] | None,
        project: str | os.PathLike[str] | None,
        change: str | None,
        instructions: str | None,
        thread_id: str | None,
    ) -> tuple[_Run, str]:
        _require_extra()
        if self._sdk_given is not None and is_system_prefix(self._sdk_given):
            raise AgentError(
                ExitCode.SDK,
                "agent.system-sdk",
                f"the SDK prefix {self._sdk_given} is under /opt/mmt, which the skill never "
                "uses (SKILL.md, Rule 3): the agent's shell refuses every command that names it",
                "extract the mmt-dpi package into a private prefix and pass it with --sdk "
                "(or MMT_BASE); AGENTS.md, 'A private prefix can also come from the "
                "published package'",
            )
        inputs = [p for p in (spec, pcap, pdl, project) if p is not None]
        if len(inputs) != 1 or (project is not None) != (change is not None):
            raise AgentError(
                ExitCode.USAGE,
                "agent.bad-request",
                "give one of spec, pcap or pdl, or a project with its change",
                "mmt-plugin-agent new --spec FILE | --pcap FILE | --pdl FILE, "
                "or mmt-plugin-agent update PROJECT --change FILE|TEXT",
            )
        found: Path | None = None
        if project is not None:
            found = Path(project).resolve()
            if not (found / "plugin.yaml").is_file():
                raise AgentError(
                    ExitCode.MODEL,
                    "agent.bad-input",
                    f"{project} is not a project: it has no plugin.yaml",
                    "pass a project directory (it holds plugin.yaml), or use new",
                )
        text = request_text(
            spec=_input(spec, "spec"),
            pcap=_input(pcap, "capture"),
            pdl=_input(pdl, "PDL"),
            project=found,
            change=change,
            instructions=instructions,
        )
        thread = thread_id or uuid.uuid4().hex
        if self.work_dir is not None:
            work = self.work_dir.resolve()
        elif found is not None:
            work = found.parent / f"{found.name}-work"
        else:
            work = Path.cwd().resolve() / f"plugin-work-{thread[:8]}"
        source = resolve_skills_dir(self.skills_dir)
        if work == source or source in work.parents:
            raise AgentError(
                ExitCode.USAGE,
                "agent.bad-work",
                f"the work folder {work} is inside the skills directory {source}",
                "pass --work a directory outside the skills",
            )
        model = models.resolve_model(self.model)
        work.mkdir(parents=True, exist_ok=True)
        files = tree_files(source)
        tree_digest = digest(files)
        snapshot = make_snapshot(files, f"{thread}-{tree_digest[:16]}")
        settings = RunSettings(
            work=work,
            project=found,
            sdk=self.sdk,
            cc=self.cc,
            mode=self.mode,
            capture=self.capture,
            allow_synthetic=self.allow_synthetic,
            no_eval=self.no_eval,
            timeout=self.timeout,
        )
        questioner = Questioner(
            mode=self.mode,
            work=work,
            allow_synthetic=self.allow_synthetic,
            on_question=self.on_question,
        )
        if self._checkpointer is None:
            from langgraph.checkpoint.memory import InMemorySaver

            self._checkpointer = InMemorySaver()
        records: list[CommandRecord] = []
        graph = compile_graph(
            model,
            settings,
            skills=snapshot,
            protected=[source],
            questioner=questioner,
            extra_skills=self.extra_skills,
            tools=self.tools,
            checkpointer=self._checkpointer,
            on_command=records.append,
        )
        run = _Run(thread, settings, source, files, tree_digest, snapshot, graph, records)
        self._runs[thread] = run
        return run, text

    def _config(self, run: _Run) -> RunnableConfig:
        return {"configurable": {"thread_id": run.thread_id}, "recursion_limit": RECURSION_LIMIT}

    def _drive(self, run: _Run, graph_input: Any) -> Iterator[AgentEvent]:
        from langgraph.errors import GraphRecursionError

        state = _Stream()
        failure: Exception | None = None
        ended = False
        try:
            for chunk in run.graph.stream(graph_input, self._config(run), stream_mode="updates"):
                yield from self._chunk(run, chunk, state)
            ended = True
        except GraphRecursionError:
            ended = True
            state.message = f"stopped after {RECURSION_LIMIT} graph steps: NOT GREEN"
        except Exception as exc:
            ended = True
            failure = exc
        finally:
            modified = self._check_skills(run)
            self._release_unless_waiting(run, ended, state)
        if failure is not None:
            self._abort(run, failure, modified)
        yield self._finish(run, state, modified)

    async def _adrive(self, run: _Run, graph_input: Any) -> AsyncIterator[AgentEvent]:
        from langgraph.errors import GraphRecursionError

        state = _Stream()
        failure: Exception | None = None
        ended = False
        try:
            async for chunk in run.graph.astream(
                graph_input, self._config(run), stream_mode="updates"
            ):
                for event in self._chunk(run, chunk, state):
                    yield event
            ended = True
        except GraphRecursionError:
            ended = True
            state.message = f"stopped after {RECURSION_LIMIT} graph steps: NOT GREEN"
        except Exception as exc:
            ended = True
            failure = exc
        finally:
            modified = self._check_skills(run)
            self._release_unless_waiting(run, ended, state)
        if failure is not None:
            self._abort(run, failure, modified)
        yield self._finish(run, state, modified)

    def _chunk(self, run: _Run, chunk: Any, state: _Stream) -> list[AgentEvent]:
        from langchain_core.messages import AIMessage

        events: list[AgentEvent] = []
        if not isinstance(chunk, dict):
            return events
        for node, update in chunk.items():
            if node == "__interrupt__":
                for item in update:
                    value = getattr(item, "value", None)
                    if isinstance(value, dict):
                        state.question = Question(**value)
                        events.append(
                            AgentEvent("question", state.question.text, state.question.to_json())
                        )
                continue
            messages = update.get("messages") if isinstance(update, dict) else None
            for message in messages if isinstance(messages, list) else []:
                if not isinstance(message, AIMessage):
                    continue
                if isinstance(message.content, str) and message.content.strip():
                    state.message = message.content.strip()
                for call in message.tool_calls:
                    args = call.get("args") or {}
                    shown = args.get("command") or args.get("file_path") or args.get("path")
                    events.append(
                        AgentEvent(
                            "step",
                            f"{call['name']} {shown or ''}".strip(),
                            {"tool": call["name"], "args": args},
                        )
                    )
        events += self._command_events(run)
        return events

    def _command_events(self, run: _Run) -> list[AgentEvent]:
        events = []
        with_sdk = run.settings.sdk is not None
        last = LOOP_COMMANDS[-1] if with_sdk else LOOP_COMMANDS[1]
        while run.seen < len(run.records):
            record = run.records[run.seen]
            run.seen += 1
            events.append(AgentEvent("command", record.command, record.to_json()))
            envelope = record.envelope
            if envelope is not None:
                error = envelope.get("error") or {}
                events.append(
                    AgentEvent(
                        "envelope",
                        f"{record.mmt_command}: exit {envelope.get('exit_code')}"
                        + (f" {error.get('code')}" if error else ""),
                        {"mmt_command": record.mmt_command, "envelope": envelope},
                    )
                )
            name = record.mmt_command
            if (
                name in LOOP_COMMANDS
                and not record.refused
                and (record.mmt_exit_code != 0 or name == last)
            ):
                runs = loop_runs(run.records[: run.seen])
                if runs and len(runs) > run.loops:
                    run.loops = len(runs)
                    done = runs[-1]
                    events.append(
                        AgentEvent(
                            "loop",
                            f"loop run {done.number}: "
                            + ("green" if done.green(with_sdk) else "not green"),
                            done.to_json(with_sdk),
                        )
                    )
        return events

    def _check_skills(self, run: _Run) -> list[str]:
        """Restore the source skills when the run changed them."""
        if digest(tree_files(run.source)) == run.digest:
            return []
        return restore(run.source, run.files)

    def _release(self, run: _Run) -> None:
        """The run is over: remove its skills snapshot and forget it."""
        remove_tree(run.snapshot)
        self._runs.pop(run.thread_id, None)

    def _release_unless_waiting(self, run: _Run, ended: bool, state: _Stream) -> None:
        """A run left before its end (Ctrl-C, a consumer that stops reading
        the events) is released, unless it stopped at a question, which
        ``resume()`` may still answer. One that ended is released by
        ``_finish`` or ``_abort``."""
        if not ended and state.question is None:
            self._release(run)

    def _abort(self, run: _Run, failure: Exception, modified: Sequence[str]) -> NoReturn:
        """The graph raised (the model's provider, an I/O error): release the
        run, and report a skills change before the failure itself."""
        self._release(run)
        if modified:
            raise AgentError(
                ExitCode.TEST,
                "agent.skills-modified",
                "the run changed the skills directory ("
                + ", ".join(modified)
                + "); it was restored. Then the run failed: "
                + AgentError.unexpected(failure).message,
                "run in the agent container, where the skills are read-only",
            ) from failure
        raise failure

    def _finish(self, run: _Run, state: _Stream, modified: Sequence[str]) -> AgentEvent:
        if state.question is None:
            self._release(run)
        result = build_result(
            thread_id=run.thread_id,
            work=run.settings.work,
            project=run.settings.project,
            records=run.records,
            with_sdk=run.settings.sdk is not None,
            no_eval=run.settings.no_eval,
            message=state.message,
            question=state.question,
            skills_modified=modified,
            since_ns=run.started_ns,
            capture=run.settings.capture is not None,
            allow_synthetic=run.settings.allow_synthetic,
            environ_readable=environ_failure(),
        )
        return AgentEvent("done", result.status, result.to_json(), result)


def _result(events: Iterator[AgentEvent]) -> AgentResult:
    result = None
    for event in events:
        result = event.result or result
    assert result is not None, "a run always ends with its done event"
    return result


async def _aresult(events: AsyncIterator[AgentEvent]) -> AgentResult:
    result = None
    async for event in events:
        result = event.result or result
    assert result is not None, "a run always ends with its done event"
    return result
