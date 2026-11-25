"""The agent's shell and file tools: deepagents' LocalShellBackend with the
guards of ``policy.py`` (needs the agent extra)."""

from __future__ import annotations

import os
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

from mmt_plugin_agent.policy import check_command, is_within
from mmt_plugin_agent.questions import Questioner, is_yes
from mmt_plugin_agent.result import CommandRecord

__all__ = ["REFUSED_EXIT", "GuardedShellBackend"]

#: The exit code of a command the guard refused, as a shell's "cannot execute".
REFUSED_EXIT = 126


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
    ) -> None:
        super().__init__(root_dir=str(work), virtual_mode=False, timeout=timeout, env=dict(env))
        self.writable = [Path(os.path.realpath(p)) for p in writable]
        self.protected = [Path(os.path.realpath(p)) for p in protected]
        self.questioner = questioner
        self.questions = Path(os.path.realpath(questioner.questions_path))
        self.on_command = on_command

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
        response = super().execute(command, timeout=timeout)
        if self.on_command is not None:
            self.on_command(CommandRecord(command, response.exit_code, response.output))
        return response
