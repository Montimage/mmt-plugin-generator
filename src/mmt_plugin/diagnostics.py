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
        # SDK detection and profiles (mmt_plugin.sdk, #13).
        "sdk.not-found": "no mmt-dpi SDK prefix was found (--sdk, MMT_BASE, mmt-dpi.pc, /opt/mmt)",
        "sdk.invalid-prefix": "an SDK prefix has no dpi/include/mmt_log.h",
        "sdk.invalid-pkg-config": "the mmt-dpi.pc pkg-config file cannot be read, or its "
        "includedir is not an absolute <prefix>/dpi/include",
        "sdk.profile-not-found": "an explicitly requested SDK profile is not bundled",
        "sdk.profile-fallback": "warning: no profile is bundled for the detected SDK version "
        "(or it is unknown); the nearest bundled one is used",
        "sdk.profile-default": "warning: no SDK found and no profile pinned; the newest bundled "
        "profile is used",
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
        # Semantic checks (mmt_plugin.semantics, #12).
        "model.duplicate-name": "an attribute, struct or define name is already used "
        "(names are case-insensitive)",
        "model.unknown-name": "a define value, case label or nextencaps value names no define "
        "and no SDK protocol",
        "model.unknown-attribute": "val(), offset() or len() names no attribute",
        "model.unknown-struct": "`struct X` or `sizeof(struct X)` names no struct",
        "model.use-before-definition": "a name is used before (or inside) its own definition",
        "model.conditional-reference": "val(), offset() or len() of a conditional attribute, "
        "outside the branch that declares it",
        "model.not-an-integer": "val() of an attribute whose type is not an integer",
        "model.hook-reference": "offset() or len() of an attribute without an offset or "
        "data_len (a user hook)",
        "model.missing-length": "data_len is omitted for a type without a fixed width",
        "model.no-fixed-width": "an MMT_* type without a fixed width as a struct field or in "
        "sizeof",
        "model.invalid-bitfield": "a bitfield width outside 1 to its unit's bits, or a bitfield "
        "of a type that is not an integer",
        "model.bitfield-overflow": "a run of bitfields is wider than its storage unit",
        "model.division-by-zero": "a folded expression divides by zero",
        "model.out-of-range": "a folded offset, length or byte-swap operand is outside its range",
        "model.duplicate-case": "two classifynext cases have the same value",
        "model.leading-zero": "a decimal literal with a leading zero where the C would read it "
        "as octal (or reject it)",
        "model.alias-too-long": "a protocol label or attribute name is longer than the SDK's "
        "Max_Alias_Len",
        "model.id-out-of-range": "a protocol id that is not positive and below the SDK's "
        "PROTO_MAX_IDENTIFIER",
        "model.id-taken": "the protocol id is already an SDK protocol's",
        "model.name-taken": "the protocol name is already an SDK protocol's",
        "model.id-outside-reserved-range": "warning: the protocol id is outside the "
        "third-party range 950-999",
        "model.default-scope": "warning: an attribute has no scope, so it is packet",
        "model.pointer-field": "warning: a `T*` struct field (4 bytes, read as MMT_DATA_POINTER)",
        "model.branch-offset-mismatch": "warning: an aligned attribute follows an if/else whose "
        "branches advance the running offset differently",
        # Code generation and `generate` (mmt_plugin.codegen, mmt_plugin.commands.generate, #14).
        "model.unreadable": "the model file cannot be read, or is not UTF-8 text",
        "model.unsupported-format": "the model is plugin.yaml, which generate and validate "
        "read only once #24 lands",
        "model.name-collision": "two names of the generated C are the same identifier, or a "
        "model define would replace a name the generated C uses",
        "model.hook-value": "val(), or len() computed per packet, of an attribute without an "
        "offset (a user hook): the generated code cannot compute it",
        "model.integer-length": "an integer attribute's constant data_len is not 1 to 8 bytes, "
        "or is wider than the integer type stores",
        "model.variable-length": "an attribute of an SDK type with no variable-length form has "
        "a data_len known only per packet",
        "model.type-size": "an attribute's type has no size in the SDK (mmt-dpi registers it "
        "only with data_len 0), or its constant data_len is above the type's SDK size",
        "model.default-byte-order": "warning: the model has no byte order (no encoding, ASCII "
        "or UNICODE); multi-byte integers are read in network byte order",
        "model.classifynext-without-encapsulation": "warning: a classifynext block with "
        'encapsulation "false"; it is generated',
        "state.stale": "generate --check: a generated file or plugin.lock is not what generate "
        "would write",
        "state.modified": "a generated file was edited since generate wrote it (its sha256 is "
        "not plugin.lock's); it is not overwritten or removed without --force",
        "state.invalid-lock": "plugin.lock cannot be read, or is not a lock this mmt-plugin knows",
        "state.kept": "warning: a file generate no longer writes is kept, not removed",
        # `validate` (mmt_plugin.commands.validate, mmt_plugin.sdk.registry, #17).
        "model.unknown-parent": "a parent protocol of the model is not in the SDK profile and "
        "not registered by the installed plugins",
        "model.load-order": "the plugin file name does not sort after libmmt_tcpip.so (C "
        "locale or LC_COLLATE), so its parents are not registered when it loads",
        "sdk.registry-unavailable": "warning: the protocols the installed plugins register "
        "could not be read; only the SDK profile was checked",
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
