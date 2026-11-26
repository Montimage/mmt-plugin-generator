"""Boundary fakes for the agent: a scripted chat model and a fake
``mmt-plugin`` on ``PATH`` that prints envelopes and logs its calls."""

from __future__ import annotations

import json
import os
import stat
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field

REPO = Path(__file__).resolve().parents[3]
SKILLS = REPO / "skills"


def call(name: str, **args: Any) -> dict[str, Any]:
    """One tool call of a scripted step."""
    return {"name": name, "args": args}


def step(*calls: dict[str, Any], text: str = "") -> list[dict[str, Any]] | str:
    return list(calls) if calls else text


Script = Sequence[list[dict[str, Any]] | str]


class ScriptedModel(BaseChatModel):
    """Plays a script: step ``n`` is the reply to a history holding ``n`` AI
    messages, so a resumed thread goes on where it stopped. A step is a list
    of tool calls, or the final text. ``scripts`` maps a marker of the first
    user message to its script (a subagent's task has its own); ``""``
    matches any. Every history it saw is kept in ``seen``. With ``fail``,
    a call past the end of the script raises it, as a provider does."""

    scripts: dict[str, list[Any]]
    seen: list[list[BaseMessage]] = Field(default_factory=list)
    fail: str | None = None

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def bind_tools(self, tools: Any, **kwargs: Any) -> ScriptedModel:
        return self

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        self.seen.append(list(messages))
        first = next((str(m.content) for m in messages if isinstance(m, HumanMessage)), "")
        markers = sorted(self.scripts, key=len, reverse=True)
        script = next(self.scripts[k] for k in markers if k in first)
        n = sum(isinstance(m, AIMessage) for m in messages)
        if n >= len(script) and self.fail is not None:
            raise RuntimeError(self.fail)
        reply = script[n] if n < len(script) else "DONE"
        if isinstance(reply, str):
            message = AIMessage(content=reply)
        else:
            message = AIMessage(
                content="",
                tool_calls=[
                    {"name": c["name"], "args": c["args"], "id": f"call-{n}-{i}"}
                    for i, c in enumerate(reply)
                ],
            )
        return ChatResult(generations=[ChatGeneration(message=message)])

    def tool_results(self) -> list[str]:
        """Every tool message content the model was shown, in order, once."""
        out: list[str] = []
        for history in self.seen:
            for m in history:
                if m.type == "tool" and str(m.content) not in out:
                    out.append(str(m.content))
        return out


def scripted(script: Script, *, fail: str | None = None, **more: Script) -> ScriptedModel:
    return ScriptedModel(
        scripts={"": list(script), **{k: list(v) for k, v in more.items()}}, fail=fail
    )


_FAKE_CLI = """#!{python}
import json, os, sys
args = sys.argv[1:]
with open(os.environ["MMT_FAKE_LOG"], "a") as log:
    log.write(json.dumps(args) + "\\n")
plan = json.loads(open(os.environ["MMT_FAKE_PLAN"]).read())
i, command, project = 0, None, None
while i < len(args):
    if args[i] in ("-C", "--project"):
        project = args[i + 1]
        i += 2
    elif args[i].startswith("-"):
        i += 1
    else:
        command = args[i]
        break
counts = plan.setdefault("_counts", {{}})
n = counts.get(command, 0)
counts[command] = n + 1
open(os.environ["MMT_FAKE_PLAN"], "w").write(json.dumps(plan))
codes = plan.get(command, [0])
code = codes[min(n, len(codes) - 1)]
result = {{}}
if command == "test":
    passed = 2 if code == 0 else 1
    result = {{"summary": {{"total": 2, "passed": passed, "failed": 2 - passed}}}}
if command == "validate":
    result = {{"checks": [{{"id": "parents-exist", "status": "pass" if code == 0 else "fail"}}]}}
if command in ("build", "test") and code == 0 and project:
    build = os.path.join(project, "build")
    os.makedirs(build, exist_ok=True)
    with open(os.path.join(build, "mmtp_telem.so"), "wb") as so:
        so.write(b"fake plugin\\n")
error = None
if code:
    failure = "test.packet-failed" if code == 6 else "model.schema"
    error = {{"class": failure.split(".")[0], "code": failure, "message": "fake", "hint": None}}
env = {{
    "schema_version": 1,
    "tool": {{"name": "mmt-plugin", "version": "0.1.0"}},
    "command": command,
    "ok": code == 0,
    "exit_code": code,
    "error": error,
    "diagnostics": [],
    "context": {{"project": None, "sdk": None}},
    "result": result,
}}
print(json.dumps(env, indent=2))
sys.exit(code)
"""


_FAKE_EVAL = """#!{python}
import sys
sys.exit(0)
"""


class FakeCli:
    """A fake ``mmt-plugin`` in ``bin``: each command exits with the next
    code of its list in the plan (the last one repeats), default 0. A fake
    ``pcap_eval.py`` (the capture evaluation, exit 0) is next to it."""

    def __init__(self, root: Path, plan: dict[str, list[int]] | None = None) -> None:
        self.bin = root / "bin"
        self.bin.mkdir(parents=True)
        self.log = root / "mmt-plugin.log"
        self.log.write_text("")
        self.plan = root / "plan.json"
        self.plan.write_text(json.dumps(plan or {}))
        exe = self.bin / "mmt-plugin"
        exe.write_text(_FAKE_CLI.format(python=sys.executable))
        exe.chmod(exe.stat().st_mode | stat.S_IXUSR)
        evaluation = self.bin / "pcap_eval.py"
        evaluation.write_text(_FAKE_EVAL.format(python=sys.executable))
        evaluation.chmod(evaluation.stat().st_mode | stat.S_IXUSR)

    def env(self) -> dict[str, str]:
        return {
            "PATH": f"{self.bin}{os.pathsep}{os.environ.get('PATH', '')}",
            "MMT_FAKE_LOG": str(self.log),
            "MMT_FAKE_PLAN": str(self.plan),
        }

    def calls(self) -> list[list[str]]:
        return [json.loads(line) for line in self.log.read_text().splitlines()]


def loop(project: Path, sdk: Path, cc: str = "gcc") -> list[list[dict[str, Any]] | str]:
    """The four loop commands of SKILL.md, one step each, in the exact form
    the backend executes itself: the run's SDK, and its compiler on build
    and test."""
    steps = []
    for name in ("validate", "generate", "build", "test"):
        command = f"mmt-plugin -C {project} --json {name} --sdk {sdk}"
        if name in ("build", "test"):
            command += f" --cc {cc}"
        steps.append(step(call("execute", command=command)))
    return steps


def evaluate(
    work: Path, sdk: Path, project: Path | None = None, cc: str = "gcc"
) -> list[dict[str, Any]] | str:
    """The capture evaluation of SKILL.md, Step 6, in its strict form: one
    simple command the backend executes itself, its arguments binding the
    run — the run's SDK and compiler, the plugin the fake build left in
    the project, a capture inside the work folder. The path is the skill's
    shape; the fake_cli fixture makes the backend run the fake instead."""
    project = project or work / "project"
    return step(
        call(
            "execute",
            command=(
                "python3 skills/mmt-plugin-generator/scripts/pcap_eval.py "
                f"--sdk {sdk} --plugin {project}/build/mmtp_telem.so "
                f"--label telem --parent tcp --capture {work}/capture.pcap "
                f"--out {work}/eval --cc {cc}"
            ),
        )
    )


def done_files(work: Path, verdict: str | None = "PASS") -> list[list[dict[str, Any]] | str]:
    """The work folder's last files (SKILL.md, Done), one step."""
    manifest: dict[str, Any] = {"schema": 1, "label": "telem"}
    if verdict is not None:
        manifest["eval"] = {"verdict": verdict, "drift": {"checked": True, "open": 0}}
    else:
        manifest["eval"] = {"verdict": "not done", "reason": "no capture"}
    return [
        step(
            call("write_file", file_path=str(work / "REPORT.md"), content="# Report\n"),
            call(
                "write_file", file_path=str(work / "manifest.json"), content=json.dumps(manifest)
            ),
            call("write_file", file_path=str(work / "README.md"), content="telem: green\n"),
        )
    ]
