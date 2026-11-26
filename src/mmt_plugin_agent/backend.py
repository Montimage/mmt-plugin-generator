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

from mmt_plugin.pluginyaml import protocol_label
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
from mmt_plugin_agent.skills import RUNNER_SOURCE, EvaluationCode

__all__ = ["REFUSED_EXIT", "GuardedShellBackend"]

#: The exit code of a command the guard refused, as a shell's "cannot execute".
REFUSED_EXIT = 126

#: The cache the evaluation script reuses under ``--out`` when nothing asks
#: it to rebuild: the runner binary and the stamp of the compile command.
RUNNER_CACHE = ("bin/pcap_eval", "bin/pcap_eval.cmd")


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
    script: Path, protected: Sequence[Path], expected: EvaluationCode | None = None
) -> bool:
    """Whether ``script`` (resolved) is the skill's own evaluation script:
    inside the read-only skills copy and still byte for byte the one the run
    started with, and so is the C runner next to it, which the script
    compiles. The bytes, not the path or the mode bits, are the proof:
    the copy is only read-only to the file tools, never to a shell the user
    could write with, and a shell could change it back before the end-of-run
    digest check."""
    if expected is None or not any(is_within(script, root) for root in protected):
        return False
    try:
        if script.read_bytes() != expected.script:
            return False
        return (script.parent / RUNNER_SOURCE).read_bytes() == expected.runner
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
        evaluation: EvaluationCode | None = None,
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
        #: The canonical plugin artifact as the last trusted build or test
        #: left it — its real path, its sha256 then and the project label
        #: its name comes from — or None. The capture evaluation's
        #: ``--plugin`` is bound to exactly this file: a sibling ``.so``
        #: the loop never linked, a file the model rewrote afterwards, or
        #: a measurement of another protocol is none of them it.
        self._artifact: tuple[str, str, str] | None = None

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

    def _project_label(self) -> str | None:
        """The label of the run's project as ``plugin.yaml`` says it now,
        or None when it cannot be read — then no artifact binds, and the
        evaluation is never trusted. ``build`` reads the same file for the
        same label, so the canonical artifact ``mmtp_<label>.so`` (its
        lower-case form, as ``build`` names it) is the one the loop's own
        build or test just produced; a file of any other name in ``build/``
        is a sibling the loop never linked."""
        try:
            text = (self._project / "plugin.yaml").read_text("utf-8")
        except (OSError, UnicodeDecodeError):
            return None
        return protocol_label(text)

    def _scan_build(self) -> None:
        """The canonical artifact as it is now: run after a trusted build
        or test, so the capture evaluation's ``--plugin`` is bound to the
        binary the loop left — a file the model rewrote afterwards, one the
        loop never built, or a sibling of another name is not it."""
        self._artifact = None
        label = self._project_label()
        if label is None:
            return
        artifact = self._project / "build" / f"mmtp_{label.lower()}.so"
        try:
            sha256 = hashlib.sha256(artifact.read_bytes()).hexdigest()
        except OSError:
            return
        self._artifact = (os.path.realpath(artifact), sha256, label)

    def _bound_evaluation(self, args: list[str]) -> dict[str, list[str]] | None:
        """The evaluation's arguments when they bind this run: the run's
        SDK, compiler, capture and output (``evaluation_args``), and the
        plugin byte for byte the canonical artifact the last trusted build
        or test left, measuring its own label — or None."""
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
        if parsed is None or self._artifact is None:
            return None
        path, sha256, label = self._artifact
        plugin = realpath_of(parsed["--plugin"][0], self._work)
        if plugin != path:
            return None
        # ``--label`` names the protocol the runner measures: the plugin's
        # own, or the evaluation measures another protocol's classification
        # (an SDK protocol's, say) with the plugin loaded but irrelevant.
        if parsed["--label"][0].casefold() != label.casefold():
            return None
        try:
            current = hashlib.sha256(Path(plugin).read_bytes()).hexdigest()
        except OSError:
            return None
        if current != sha256:
            return None
        return parsed

    def _invalidate_runner_cache(self, parsed: Mapping[str, list[str]]) -> bool:
        """Remove the runner cache of the evaluation's ``--out``: the binary
        and its stamp, so the trusted run compiles the verified C runner
        fresh instead of reusing whatever a model planted there with a
        matching stamp (the script reuses ``bin/pcap_eval`` when its stamp
        names the same compile command, and the stamp is the model's to
        write). False when a file cannot be removed — the cache then stays
        and the execution must not be trusted. A background process can
        still race the compile that follows; that is inherent (the model
        runs as the same user), as docs/agent-api.md says."""
        out = Path(realpath_of(parsed["--out"][0], self._work))
        try:
            for name in RUNNER_CACHE:
                (out / name).unlink(missing_ok=True)
        except OSError:
            return False
        return True

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
            parsed = self._bound_evaluation(args[1:])
            if parsed is None:
                return None
            # The script compiles its C runner into the model-writable
            # --out and reuses a cached one whose stamp matches: remove the
            # cache first, so the binary that runs is compiled now, from
            # the runner verified above — never a preplanted one. When the
            # cache cannot be removed the execution is not trusted either:
            # it could be the planted binary.
            if not self._invalidate_runner_cache(parsed):
                return None
            evaluation = True
            argv = [*evaluation_argv(script), *args[1:]]
        # deepagents passes timeout=None when the model gives none: fall
        # back to the backend's default, as LocalShellBackend.execute does.
        limit = timeout_s or (timeout if timeout is not None else self._default_timeout)
        started = time.time_ns()
        try:
            ran = subprocess.run(
                argv,
                cwd=self._work,
                env=self._agent_env,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=limit,
                check=False,
            )
            exit_code, stdout, stderr = ran.returncode, ran.stdout, ran.stderr
        except subprocess.TimeoutExpired as timed_out:
            exit_code = 124
            out = timed_out.stdout or ""
            err = timed_out.stderr or ""
            stdout = out.decode("utf-8", "replace") if isinstance(out, bytes) else out
            stderr = err.decode("utf-8", "replace") if isinstance(err, bytes) else err
            stderr += f"\ntimed out after {limit}s"
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
