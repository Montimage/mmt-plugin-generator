"""Run inside the agent image, as its user (CI's agent job): the agent's
shell and file tools cannot change the image's skills (P5), can write the
work folder, and cannot read the provider key the agent was given from any
process's ``/proc/<pid>/environ`` (the agent's, PID 1 here, included).

    docker run --rm --network none -e ANTHROPIC_API_KEY=dummy-not-a-real-key-123456 \\
        -v "$PWD/tests/unit/agent/image_guard.py:/tmp/g.py:ro" \\
        mmt-plugin-agent:local /opt/mmt-plugin/bin/python /tmp/g.py

The first argument, when given, is the work folder (default
``~/guard-work``): CI also runs it as the runner's uid, a host folder
mounted at ``/work``, with ``make agent-run``'s flags (``--user``,
``HOME=/tmp``). The second, when given, is ``agent-run``'s input folder
(``/in``), which must hold a ``.env`` with the key: the shell must see the
file and find the key in nothing it can read there, which holds only when
the ``.env`` is masked as ``agent-run`` masks it
(``-v /dev/null:/in/.env:ro``).

Not a pytest module: the image has no pytest. It prints PASS or fails.
"""

from __future__ import annotations

import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage

from mmt_plugin_agent import PluginAgent

SKILLS = Path("/opt/mmt-plugin-skills")
SKILL_MD = SKILLS / "mmt-plugin-generator" / "SKILL.md"


class Model(FakeMessagesListChatModel):
    def bind_tools(self, tools: Any, **kwargs: Any) -> Model:
        return self


def _call(n: int, name: str, **args: Any) -> AIMessage:
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": f"c{n}"}])


#: Each process's environment the shell can read: the lines that set the key.
_ENVIRON = (
    "for f in /proc/[0-9]*/environ; do tr '\\0' '\\n' < \"$f\" 2>/dev/null; done"
    " | grep -c '^ANTHROPIC_API_KEY='; echo environ=done"
)


def main() -> None:
    assert os.geteuid() != 0, "the agent image runs as root"
    assert os.environ.get("ANTHROPIC_API_KEY"), "run it with -e ANTHROPIC_API_KEY=<dummy>"
    # Before the agent: a child reads its parent's key, so the check below means something.
    seen = subprocess.run(
        ["sh", "-c", "tr '\\0' '\\n' < /proc/$PPID/environ"],
        env={"PATH": os.environ["PATH"]},
        capture_output=True,
        text=True,
        check=False,
    )
    assert "ANTHROPIC_API_KEY=" in seen.stdout, "the control does not read /proc/<ppid>/environ"
    before = SKILL_MD.read_bytes()
    shell = (
        f"echo x >> {SKILL_MD}; echo append=$?; touch {SKILLS}/new.md; echo create=$?; "
        f"chmod u+w {SKILL_MD}; echo chmod=$?"
    )
    work = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.home() / "guard-work"
    inputs = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    probe = work / "probe.txt"
    calls = [
        _call(0, "write_file", file_path=str(SKILLS / "new.md"), content="x"),
        _call(1, "execute", command=shell),
        _call(2, "write_file", file_path=str(probe), content="probe\n"),
        _call(3, "execute", command=_ENVIRON),
    ]
    if inputs is not None:
        # What the shell can read under /in: the .env is there, and no file
        # holds the key (the dummy, so naming it in the command is harmless).
        key = shlex.quote(os.environ["ANTHROPIC_API_KEY"])
        listing = f"ls -A {inputs} | grep -cx .env; grep -rlsF -- {key} {inputs}; echo in=done"
        calls.append(_call(4, "execute", command=listing))
    model = Model(responses=[*calls, AIMessage(content="DONE")])
    spec = SKILLS / "mmt-plugin-generator" / "evals" / "cases" / "spec-telem" / "spec.md"
    result = PluginAgent(model, work_dir=work).new(spec=spec)
    record, environ, *rest = result.commands
    assert environ.output.splitlines()[:2] == ["0", "environ=done"], environ.output
    assert os.environ["ANTHROPIC_API_KEY"] not in environ.output
    if inputs is not None:
        (seen_in,) = rest
        lines = seen_in.output.splitlines()
        assert lines[:1] == ["1"], f"the shell sees no {inputs}/.env: {seen_in.output}"
        assert lines[1:2] == ["in=done"], f"the key is readable under {inputs}: {seen_in.output}"
    for step in ("append", "create", "chmod"):
        assert f"{step}=" in record.output and f"{step}=0" not in record.output, record.output
    assert SKILL_MD.read_bytes() == before
    assert not (SKILLS / "new.md").exists()
    assert result.skills_modified == []
    assert probe.read_text("utf-8") == "probe\n", probe
    print(
        f"PASS: uid {os.geteuid()} cannot write {SKILLS}, wrote {probe}, "
        "read no provider key from /proc/*/environ"
        + (f" or under {inputs}" if inputs is not None else "")
    )


if __name__ == "__main__":
    main()
