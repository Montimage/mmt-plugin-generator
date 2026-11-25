"""The questions the skill asks (SKILL.md, Run modes): the ``ask_user`` tool
and the leave for ``--force``."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

__all__ = [
    "CAPTURE_SKIP",
    "CAPTURE_SYNTHETIC",
    "Question",
    "QuestionKind",
    "Questioner",
    "RunMode",
    "is_yes",
]

RunMode = Literal["unattended", "interactive"]
QuestionKind = Literal["capture", "force", "other"]

#: The unattended answers to the capture question (SKILL.md, Step 1).
CAPTURE_SYNTHETIC = "allow a synthetic capture (the request grants it)"
CAPTURE_SKIP = "skip the evaluation; it is reported as not done"


@dataclass(frozen=True)
class Question:
    """One question: ``kind`` is ``capture`` for the capture question,
    ``force`` for leave to run a command with ``--force``."""

    id: str
    kind: QuestionKind
    text: str
    recommended: str

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


def is_yes(answer: str) -> bool:
    return answer.strip().lower() in {"y", "yes", "ok", "allow", "run it"}


class Questioner:
    """Puts a question to whoever can answer: ``on_question`` when given,
    else the user through a LangGraph interrupt (interactive), else
    ``<work>/questions.md`` and the safe default (unattended)."""

    def __init__(
        self,
        *,
        mode: RunMode,
        work: Path,
        allow_synthetic: bool,
        on_question: Callable[[Question], str] | None = None,
    ) -> None:
        self.mode = mode
        self.work = work
        self.allow_synthetic = allow_synthetic
        self.on_question = on_question

    @property
    def questions_path(self) -> Path:
        return self.work / "questions.md"

    def default(self, kind: QuestionKind, recommended: str) -> str:
        if kind == "capture":
            return CAPTURE_SYNTHETIC if self.allow_synthetic else CAPTURE_SKIP
        if kind == "force":
            return "no: --force is never used unattended"
        return recommended

    def ask(self, text: str, recommended: str, kind: QuestionKind = "other") -> str:
        """The answer to one question. An interrupt re-runs the tool that
        asked on resume, so nothing is written before it."""
        ident = "q-" + hashlib.sha256(f"{kind}\0{text}".encode()).hexdigest()[:12]
        question = Question(ident, kind, text, recommended)
        if self.on_question is not None:
            return self.on_question(question)
        if self.mode == "interactive":
            from langgraph.types import interrupt

            return str(interrupt(question.to_json()))
        taken = self.default(kind, recommended)
        self.work.mkdir(parents=True, exist_ok=True)
        number = 1
        if self.questions_path.exists():
            lines = self.questions_path.read_text("utf-8").splitlines()
            number += sum(1 for line in lines if line.startswith("## Q"))
        with self.questions_path.open("a", encoding="utf-8") as out:
            out.write(f"## Q{number}: {text}\nRecommended: {recommended}\nTaken: {taken}\n\n")
        return (
            f"No user can answer (unattended): recorded in {self.questions_path}. Taken: {taken}"
        )
