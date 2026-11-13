"""Diagnostics, errors and the registry of their codes.

A code is a stable dotted slug whose first part is its class, which fixes the
exit code (``mmt_plugin.exitcodes``): ``model.duplicate-name`` is class
``model``, exit 3. Every code the tool emits is listed in ``CODES``, with what
it means; ``Diagnostic`` and ``CliError`` refuse a code that is not, and a unit
test scans the sources for unlisted codes. A code is never reused for another
meaning. Each command's issue adds the codes it emits.

Locations are 1-based; columns count Unicode code points.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any

from mmt_plugin.exitcodes import ExitCode, for_class

__all__ = [
    "CODES",
    "CODE_PATTERN",
    "CliError",
    "Diagnostic",
    "Location",
    "Related",
    "Severity",
    "UnregisteredCodeError",
    "check_code",
    "sorted_diagnostics",
]

#: Every code the tool emits, with its meaning.
CODES: Mapping[str, str] = MappingProxyType(
    {
        "internal.unexpected": "an unexpected exception: a bug in mmt-plugin",
        "internal.io": "an operating-system or I/O error with no better class",
        "usage.no-command": "no command was given",
        "usage.unknown-command": "the command name is not a known command",
        "usage.unknown-option": "an option that the command does not accept",
        "usage.unexpected-argument": "a positional argument that the command does not take",
        "usage.missing-argument": "a required argument, or an option's value, is missing",
        "usage.invalid-value": "an argument or option value is not valid",
        "usage.conflicting-options": "options that cannot be used together",
        "usage.invalid": "any other command-line error",
        "interrupted": "the run was interrupted (SIGINT)",
        # PDL v1 syntax (mmt_plugin.pdl, #11).
        "model.syntax.unexpected-character": "a PDL file has a character no token starts with",
        "model.syntax.invalid-number": "a PDL number is malformed (`0x`, `12abc`)",
        "model.syntax.unterminated-comment": "a PDL `/*` comment is not closed",
        "model.syntax.unterminated-string": "a PDL quoted value does not end on its line",
        "model.syntax.unexpected-token": "a PDL token that the grammar does not allow there",
        "model.syntax.unexpected-end": "a PDL file ends before the model is complete",
        "model.syntax.trailing-input": "a PDL file has text after the Protocol block",
        "model.syntax.unknown-key": "a PDL key that the Properties or attribute block has not",
        "model.syntax.duplicate-key": "a PDL key or switch default given twice",
        "model.syntax.missing-key": "a required PDL key is missing (label, id, alias, data_type)",
        "model.syntax.out-of-order": "a PDL key, block or branch is not in the grammar's order",
        "model.syntax.invalid-value": "a PDL value outside its set (boolean, encoding, scope, id)",
        "model.syntax.unknown-type": "a PDL data type or element type that does not exist",
        "model.syntax.too-deep": "PDL parentheses or if blocks nest deeper than the parser allows",
        "model.syntax.too-many-operands": "a PDL expression has more operands than the parser "
        "allows",
        "model.syntax.invalid-expression": "a PDL expression is malformed (bare name, unknown "
        "function, chained comparison)",
    }
)

#: The shape of a code: a class, then dot-separated lower-case slugs.
CODE_PATTERN = re.compile(r"^[a-z]+(\.[a-z0-9]+(-[a-z0-9]+)*)*$")


class UnregisteredCodeError(ValueError):
    """A diagnostic or error code that is not in ``CODES``."""


def check_code(code: str) -> str:
    """Return ``code`` if it is registered; raise ``UnregisteredCodeError`` otherwise."""
    if code not in CODES:
        raise UnregisteredCodeError(f"diagnostic code {code!r} is not registered in CODES")
    return code


def _class_of(code: str) -> ExitCode:
    return for_class(code.split(".", 1)[0])


class Severity(str, Enum):
    """How bad a diagnostic is. Only ``--strict`` turns warnings into failures."""

    ERROR = "error"
    WARNING = "warning"
    NOTE = "note"


def _check_position(name: str, value: int | None) -> None:
    if value is not None and value < 1:
        raise ValueError(f"{name} is 1-based, got {value}")


@dataclass(frozen=True)
class Location:
    """Where a diagnostic points: a file, then optionally a 1-based line and column.

    ``file`` is relative to the project when inside it (POSIX separators),
    absolute otherwise, and ``<stdin>`` for standard input.
    """

    file: str
    line: int | None = None
    column: int | None = None
    end_line: int | None = None
    end_column: int | None = None

    def __post_init__(self) -> None:
        for name in ("line", "column", "end_line", "end_column"):
            _check_position(name, getattr(self, name))
        if self.column is not None and self.line is None:
            raise ValueError("a column needs a line")
        if self.end_column is not None and self.end_line is None:
            raise ValueError("an end column needs an end line")

    def to_json(self) -> dict[str, Any]:
        """The envelope form; every key is present."""
        return {
            "file": self.file,
            "line": self.line,
            "column": self.column,
            "end_line": self.end_line,
            "end_column": self.end_column,
        }

    def __str__(self) -> str:
        """``file:line:column``, as far as it is known."""
        parts = [self.file]
        if self.line is not None:
            parts.append(str(self.line))
            if self.column is not None:
                parts.append(str(self.column))
        return ":".join(parts)


@dataclass(frozen=True)
class Related:
    """A secondary location of a diagnostic ("first defined here")."""

    message: str
    location: Location | None = None

    def to_json(self) -> dict[str, Any]:
        """The envelope form."""
        return {
            "message": self.message,
            "location": None if self.location is None else self.location.to_json(),
        }


@dataclass(frozen=True)
class Diagnostic:
    """One finding: an error, a warning or a note, with a registered code."""

    severity: Severity
    code: str
    message: str
    hint: str | None = None
    location: Location | None = None
    related: Sequence[Related] = field(default=())

    def __post_init__(self) -> None:
        check_code(self.code)
        object.__setattr__(self, "related", tuple(self.related))

    @property
    def sort_key(self) -> tuple[str, int, int, str]:
        """Diagnostics are reported sorted by file, line, column and code."""
        loc = self.location
        if loc is None:
            return ("", 0, 0, self.code)
        return (loc.file, loc.line or 0, loc.column or 0, self.code)

    def to_json(self) -> dict[str, Any]:
        """The envelope form, keys in schema order."""
        return {
            "severity": self.severity.value,
            "code": self.code,
            "message": self.message,
            "hint": self.hint,
            "location": None if self.location is None else self.location.to_json(),
            "related": [r.to_json() for r in self.related],
        }


def sorted_diagnostics(diagnostics: Sequence[Diagnostic]) -> list[Diagnostic]:
    """Return the diagnostics in report order."""
    return sorted(diagnostics, key=lambda d: d.sort_key)


class CliError(Exception):
    """The failure that ends a run: a registered code, a message and a hint.

    The code's class gives the exit code (``model.*`` -> 3). Raise it from a
    command, or return it in an ``Outcome`` together with diagnostics.
    """

    def __init__(self, code: str, message: str, hint: str | None = None) -> None:
        check_code(code)
        super().__init__(message)
        self.code = code
        self.message = message
        self.hint = hint
        self.exit_code: ExitCode = _class_of(code)

    @property
    def error_class(self) -> str:
        """The class name (``"usage"``), as in the envelope's ``error.class``."""
        return self.exit_code.error_class

    def to_json(self) -> dict[str, Any]:
        """The envelope's ``error`` object."""
        return {
            "class": self.error_class,
            "code": self.code,
            "message": self.message,
            "hint": self.hint,
        }
