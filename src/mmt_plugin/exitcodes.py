"""Exit codes of ``mmt-plugin`` (``docs/design/cli.md``, section 5).

Every failure belongs to one class, and the class fixes the exit code. The
class name is also the first part of every diagnostic code
(``model.duplicate-name`` is class ``model``, exit 3).
"""

from __future__ import annotations

from enum import IntEnum

__all__ = ["ExitCode", "for_class"]


class ExitCode(IntEnum):
    """The exit codes. ``error_class`` is the class name used in ``error.class``."""

    SUCCESS = 0
    INTERNAL = 1
    USAGE = 2
    MODEL = 3
    SDK = 4
    BUILD = 5
    TEST = 6
    STATE = 7
    INTERRUPTED = 130

    @property
    def error_class(self) -> str:
        """The class name (``"model"`` for 3); ``"success"`` for 0."""
        return self.name.lower()

    @property
    def meaning(self) -> str:
        """One line for ``--help``."""
        return _MEANINGS[self]


_MEANINGS: dict[ExitCode, str] = {
    ExitCode.SUCCESS: "success (warnings allowed unless --strict)",
    ExitCode.INTERNAL: "internal error: a bug, or an I/O error with no better class",
    ExitCode.USAGE: "usage error: bad arguments or option combination",
    ExitCode.MODEL: "model error: the input model or data is wrong",
    ExitCode.SDK: "SDK error: SDK, toolchain or install prefix problem",
    ExitCode.BUILD: "build error: the compiler or linker failed",
    ExitCode.TEST: "test error: a packet test failed, or a crash",
    ExitCode.STATE: "state error: files on disk are not what the command needs",
    ExitCode.INTERRUPTED: "interrupted (SIGINT)",
}


def for_class(error_class: str) -> ExitCode:
    """Return the exit code of a failure class (``"sdk"`` -> 4).

    Raises ``ValueError`` for an unknown class or for ``"success"``.
    """
    try:
        code = ExitCode[error_class.upper()]
    except KeyError:
        raise ValueError(f"unknown error class {error_class!r}") from None
    if code is ExitCode.SUCCESS:
        raise ValueError("'success' is not an error class")
    return code
