"""The agent's shell and file tools: deepagents' LocalShellBackend with the
guards of ``policy.py`` (needs the agent extra)."""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

from deepagents.backends import LocalShellBackend
from deepagents.backends.protocol import (
    DeleteResult,
    EditResult,
    ExecuteResponse,
    FileUploadResponse,
    WriteResult,
)

from mmt_plugin_agent.policy import (
    TrustedInvocation,
    check_command,
    evaluation_args,
    is_within,
    loop_subcommand,
    realpath_of,
    trusted_invocation,
)
from mmt_plugin_agent.questions import Questioner, is_yes
from mmt_plugin_agent.result import CommandRecord
from mmt_plugin_agent.skills import SKILL_NAME

__all__ = ["REFUSED_EXIT", "GuardedShellBackend"]

#: The exit code of a command the guard refused, as a shell's "cannot execute".
REFUSED_EXIT = 126

#: The evaluation script's path inside the skills directory.
EVALUATION_SCRIPT = f"{SKILL_NAME}/scripts/pcap_eval.py"


def mmt_plugin_argv() -> list[str]:
    """How the backend runs mmt-plugin for a trusted invocation: the module
    of this very installation, never a name the PATH resolves (a model can
    write a shadowing ``mmt-plugin`` anywhere the user can write) — and in
    isolated mode, so neither the model-writable working directory nor the
    environment can put a shadowing ``mmt_plugin`` package on sys.path."""
    return [sys.executable, "-I", "-m", "mmt_plugin"]


def evaluation_argv(script: Path) -> list[str]:
    """How the backend runs the evaluation's script for a trusted
    invocation: in isolated mode, like mmt-plugin's."""
    return [sys.executable, "-I", str(script)]


def evaluation_script_ok(
    script: Path, protected: Sequence[Path], expected: bytes | None = None
) -> bool:
    """Whether ``script`` (resolved) is the skill's own evaluation script:
    inside the read-only skills copy and still byte for byte the one the run
    started with. The bytes, not the path or the mode bits, are the proof:
    the copy is only read-only to the file tools, never to a shell the user
    could write with, and a shell could change it back before the end-of-run
    digest check."""
    if expected is None or not any(is_within(script, root) for root in protected):
        return False
    try:
        return script.read_bytes() == expected
    except OSError:
        return False


class GuardedShellBackend(LocalShellBackend):
    """Real paths (``virtual_mode=False``), shell commands in the work folder.

    The file tools write only under ``writable`` and never under
    ``protected`` (the skills), symbolic links followed, and never
    ``questions.md``, which only the ``ask_user`` tool writes. The shell refuses
    ``sudo``, ``--system`` and ``/opt/mmt``, and runs ``--force`` only with
    leave, which an unattended run never gives. Every command is reported to
    ``on_command``. A shell command can still write anything the user can:
    the container is the sandbox, and the read-only skills copy and the
    end-of-run digest check catch what gets past."""

    def __init__(
        self,
        *,
        work: Path,
        writable: Sequence[Path],
        protected: Sequence[Path],
        questioner: Questioner,
        env: Mapping[str, str],
        timeout: int,
        on_command: Callable[[CommandRecord], None] | None = None,
        evaluation: bytes | None = None,
        project: Path | None = None,
        sdk: Path | None = None,
        cc: str = "gcc",
        capture: Path | None = None,
    ) -> None:
        super().__init__(root_dir=str(work), virtual_mode=False, timeout=timeout, env=dict(env))
        self.writable = [Path(os.path.realpath(p)) for p in writable]
        self.protected = [Path(os.path.realpath(p)) for p in protected]
        self.questioner = questioner
        self.questions = Path(os.path.realpath(questioner.questions_path))
        self.on_command = on_command
        self._agent_env = dict(env)
        self._work = Path(os.path.realpath(work))
        self._evaluation = evaluation
        # The run's own project, SDK, compiler and capture: what a trusted
        # invocation is bound to. ``project`` is already canonical (the
        # caller's resolved update project, or the lexical <work>/project
        # of a new plugin): it is never resolved again, so a symlink
        # planted at the project path does not become the project.
        self._project = project if project is not None else self._work / "project"
        self._sdk = sdk
        self._cc = cc
        self._capture = capture
        #: The sha256 of every ``<project>/build/*.so`` as the last trusted
        #: build or test left it, by real path: the binaries the capture
        #: evaluation is bound to.
        self._so_hashes: dict[str, str] = {}

    def refusal(self, file_path: str) -> str | None:
        """Why the file tools may not write ``file_path``, or None."""
        try:
            real = Path(os.path.realpath(self._resolve_path(file_path)))
        except (ValueError, OSError) as exc:
            return f"permission denied: {file_path}: {exc}"
        if any(is_within(real, root) for root in self.protected) or not any(
            is_within(real, root) for root in self.writable
        ):
            return f"permission denied: {file_path} is read-only for the agent"
        if real == self.questions:
            return (
                f"permission denied: {file_path} is written only by the ask_user tool: "
                "ask the question with ask_user"
            )
        return None

    def write(self, file_path: str, content: str) -> WriteResult:
        if (why := self.refusal(file_path)) is not None:
            return WriteResult(error=why)
        return super().write(file_path, content)

    async def awrite(self, file_path: str, content: str) -> WriteResult:
        if (why := self.refusal(file_path)) is not None:
            return WriteResult(error=why)
        return await super().awrite(file_path, content)

    def edit(
        self,
        file_path: str,
        old_string: str,
        new_string: str,
        replace_all: bool = False,
    ) -> EditResult:
        if (why := self.refusal(file_path)) is not None:
            return EditResult(error=why)
        return super().edit(file_path, old_string, new_string, replace_all)

    async def aedit(
        self,
        file_path: str,
        old_string: str,
        new_string: str,
        replace_all: bool = False,
    ) -> EditResult:
        if (why := self.refusal(file_path)) is not None:
            return EditResult(error=why)
        return await super().aedit(file_path, old_string, new_string, replace_all)

    def delete(self, file_path: str) -> DeleteResult:
        if (why := self.refusal(file_path)) is not None:
            return DeleteResult(error=why)
        return super().delete(file_path)

    async def adelete(self, file_path: str) -> DeleteResult:
        if (why := self.refusal(file_path)) is not None:
            return DeleteResult(error=why)
        return await super().adelete(file_path)

    def _uploads(
        self, files: list[tuple[str, bytes]]
    ) -> tuple[list[tuple[str, bytes]], dict[str, str]]:
        refused = {p: why for p, _ in files if (why := self.refusal(p)) is not None}
        return [(p, d) for p, d in files if p not in refused], refused

    def _merge(
        self,
        files: list[tuple[str, bytes]],
        done: list[FileUploadResponse],
        refused: Mapping[str, str],
    ) -> list[FileUploadResponse]:
        it = iter(done)
        return [
            FileUploadResponse(path=p, error="permission_denied") if p in refused else next(it)
            for p, _ in files
        ]

    def upload_files(self, files: list[tuple[str, bytes]]) -> list[FileUploadResponse]:
        allowed, refused = self._uploads(files)
        return self._merge(files, super().upload_files(allowed) if allowed else [], refused)

    async def aupload_files(self, files: list[tuple[str, bytes]]) -> list[FileUploadResponse]:
        allowed, refused = self._uploads(files)
        done = await super().aupload_files(allowed) if allowed else []
        return self._merge(files, done, refused)

    def _refuse(self, command: str, why: str) -> ExecuteResponse:
        if self.on_command is not None:
            self.on_command(CommandRecord(command, REFUSED_EXIT, "", refused=why))
        return ExecuteResponse(
            output=f"refused by mmt-plugin-agent, not run: {why}", exit_code=REFUSED_EXIT
        )

    def execute(self, command: str, *, timeout: int | None = None) -> ExecuteResponse:
        check = check_command(command)
        if check.refused is not None:
            return self._refuse(command, check.refused)
        if check.force:
            if self.questioner.mode == "unattended":
                return self._refuse(command, "--force is never used unattended (SKILL.md, Rule 4)")
            answer = self.questioner.ask(
                f"Run this command, which overwrites files with --force? {command}",
                "no",
                kind="force",
            )
            if not is_yes(answer):
                return self._refuse(command, f"--force was not allowed (answer: {answer})")
        invocation = trusted_invocation(command)
        if invocation is not None:
            response = self._execute_trusted(command, invocation, timeout)
            if response is not None:
                return response
        started = time.time_ns()
        response = super().execute(command, timeout=timeout)
        if self.on_command is not None:
            self.on_command(
                CommandRecord(
                    command,
                    response.exit_code,
                    response.output,
                    started_ns=started,
                    ended_ns=time.time_ns(),
                )
            )
        return response

    def _scan_build(self) -> None:
        """The sha256 of every ``<project>/build/*.so`` as it is now, by real
        path: run after a trusted build or test, so the capture evaluation's
        ``--plugin`` is bound to the binary the loop left — a file the model
        rewrote afterwards, or one the loop never built, is not it."""
        self._so_hashes = {}
        try:
            entries = list(os.scandir(self._project / "build"))
        except OSError:
            return
        for entry in entries:
            if not entry.name.endswith(".so") or not entry.is_file():
                continue
            try:
                self._so_hashes[os.path.realpath(entry.path)] = hashlib.sha256(
                    Path(entry.path).read_bytes()
                ).hexdigest()
            except OSError:
                continue

    def _evaluation_ok(self, args: list[str]) -> bool:
        """Whether the evaluation's arguments bind this run, and the plugin
        they name is byte for byte the one the last trusted build or test
        left in ``<project>/build``."""
        parsed = evaluation_args(
            args,
            project=self._project,
            sdk=self._sdk,
            cc=self._cc,
            capture=self._capture,
            work=self._work,
            work_capture=(
                self.questioner.allow_synthetic or self.questioner.mode == "interactive"
            ),
            cwd=self._work,
        )
        if parsed is None:
            return False
        plugin = realpath_of(parsed["--plugin"][0], self._work)
        if self._so_hashes.get(plugin) is None:
            return False
        try:
            current = hashlib.sha256(Path(plugin).read_bytes()).hexdigest()
        except OSError:
            return False
        return current == self._so_hashes[plugin]

    def _execute_trusted(
        self, command: str, invocation: TrustedInvocation, timeout: int | None
    ) -> ExecuteResponse | None:
        """Run a strict invocation directly, without the shell: the backend
        chooses the executable (this installation's ``mmt_plugin`` module,
        or the skill's own evaluation script), the arguments are exactly the
        parsed tokens, and the exit code and output are the process's own —
        evidence the model's shell text cannot forge. Tee is performed here,
        after the destination is validated. Returns None to fall back to the
        shell when the invocation is not one the backend can trust: the
        loop's shapes bind the run's project, SDK and compiler exactly
        (``loop_subcommand``), the evaluation's bind its script, capture,
        output and plugin (``evaluation_args``); anything else may still
        run, but proves nothing."""
        kind, args, subcommand, tee, timeout_s = invocation
        evaluation = False
        if kind == "mmt-plugin":
            subcommand = loop_subcommand(
                args, project=self._project, sdk=self._sdk, cc=self._cc, cwd=self._work
            )
            if subcommand is None:
                return None
            argv = [*mmt_plugin_argv(), *args]
        else:
            script = Path(os.path.realpath(self._work / args[0]))
            if not evaluation_script_ok(script, self.protected, self._evaluation):
                return None
            if not self._evaluation_ok(args[1:]):
                return None
            evaluation = True
            argv = [*evaluation_argv(script), *args[1:]]
        started = time.time_ns()
        try:
            ran = subprocess.run(
                argv,
                cwd=self._work,
                env=self._agent_env,
                capture_output=True,
                text=True,
                timeout=timeout_s or timeout,
                check=False,
            )
            exit_code, stdout, stderr = ran.returncode, ran.stdout, ran.stderr
        except subprocess.TimeoutExpired as timed_out:
            exit_code = 124
            out = timed_out.stdout or ""
            err = timed_out.stderr or ""
            stdout = out.decode("utf-8", "replace") if isinstance(out, bytes) else out
            stderr = err.decode("utf-8", "replace") if isinstance(err, bytes) else err
            stderr += f"\ntimed out after {timeout_s or timeout}s"
        except OSError as exc:
            exit_code, stdout, stderr = 126, "", f"cannot execute: {exc}"
        if subcommand in ("build", "test"):
            self._scan_build()
        output = stdout + stderr
        if tee is not None:
            why = self.refusal(tee)
            if why is None:
                target = Path(os.path.realpath(self._work / tee))
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(stdout, "utf-8")
            else:
                output += f"\ntee: {why}"
        response = ExecuteResponse(output=output, exit_code=exit_code)
        if self.on_command is not None:
            self.on_command(
                CommandRecord(
                    command,
                    exit_code,
                    output,
                    started_ns=started,
                    ended_ns=time.time_ns(),
                    trusted=True,
                    name=subcommand if kind == "mmt-plugin" else None,
                    evaluation=evaluation,
                )
            )
        return response
