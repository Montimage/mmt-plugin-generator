"""Tests for ``mmt_plugin.diagnostics``: the code registry and the data types."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from mmt_plugin import diagnostics
from mmt_plugin.diagnostics import (
    CODE_PATTERN,
    CODES,
    CliError,
    Diagnostic,
    Location,
    Related,
    Severity,
    UnregisteredCodeError,
    sorted_diagnostics,
)
from mmt_plugin.exitcodes import ExitCode, for_class

SRC = Path(diagnostics.__file__).parent

#: Calls whose code argument is checked, and the position of that argument.
_CODE_ARGS = {"CliError": 0, "UsageError": 0, "Diagnostic": 1}


@pytest.mark.parametrize("code", sorted(CODES))
def test_registered_codes_are_dotted_slugs_of_a_class(code: str) -> None:
    assert CODE_PATTERN.match(code), code
    assert for_class(code.split(".", 1)[0]) is not ExitCode.SUCCESS
    assert CODES[code], f"{code} has no meaning"


def test_an_unregistered_code_fails() -> None:
    with pytest.raises(UnregisteredCodeError, match=r"model\.never-registered"):
        Diagnostic(Severity.ERROR, "model.never-registered", "message")
    with pytest.raises(UnregisteredCodeError, match=r"sdk\.never-registered"):
        CliError("sdk.never-registered", "message")


def _code_literals(tree: ast.AST) -> list[tuple[int, str]]:
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)
        if name not in _CODE_ARGS:
            continue
        arg: ast.expr | None = next((k.value for k in node.keywords if k.arg == "code"), None)
        if arg is None and len(node.args) > _CODE_ARGS[name]:
            arg = node.args[_CODE_ARGS[name]]
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            found.append((node.lineno, arg.value))
    return found


def _returned_literals(tree: ast.AST, function: str) -> list[tuple[int, str]]:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == function:
            return [
                (n.lineno, n.value)
                for n in ast.walk(node)
                if isinstance(n, ast.Constant) and isinstance(n.value, str) and "." in n.value
            ]
    raise AssertionError(f"{function} not found")


def test_every_code_in_the_sources_is_registered() -> None:
    unregistered = []
    count = 0
    for path in sorted(SRC.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        literals = _code_literals(tree)
        if path.name == "cli.py":
            literals += [
                (line, value)
                for line, value in _returned_literals(tree, "_classify")
                if value.startswith("usage.")
            ]
        count += len(literals)
        unregistered += [
            f"{path.relative_to(SRC)}:{line}: {code}"
            for line, code in literals
            if code not in CODES
        ]
    assert count > 0, "the scan found no code at all"
    assert unregistered == []


def test_the_source_scan_catches_an_unregistered_code() -> None:
    tree = ast.parse('raise CliError("model.not-there", "x")\nDiagnostic(s, code="sdk.nope", m=1)')
    assert [code for _, code in _code_literals(tree)] == ["model.not-there", "sdk.nope"]


def test_cli_error_takes_its_class_from_its_code() -> None:
    error = CliError("usage.no-command", "no command given", "run --help")
    assert (error.exit_code, error.error_class) == (ExitCode.USAGE, "usage")
    assert error.to_json() == {
        "class": "usage",
        "code": "usage.no-command",
        "message": "no command given",
        "hint": "run --help",
    }
    assert CliError("interrupted", "interrupted").exit_code is ExitCode.INTERRUPTED


@pytest.mark.parametrize(
    "kwargs",
    [
        {"line": 0},
        {"line": 1, "column": 0},
        {"column": 3},
        {"line": 1, "end_column": 2},
    ],
)
def test_locations_are_one_based(kwargs: dict[str, int]) -> None:
    with pytest.raises(ValueError):
        Location("plugin.yaml", **kwargs)


def test_location_text() -> None:
    assert str(Location("a.yaml")) == "a.yaml"
    assert str(Location("a.yaml", 3)) == "a.yaml:3"
    assert str(Location("a.yaml", 3, 7, 3, 9)) == "a.yaml:3:7"


def test_diagnostic_json_has_every_key_in_order() -> None:
    d = Diagnostic(
        Severity.WARNING,
        "internal.io",
        "message",
        location=Location("a.yaml", 2, 1),
        related=[Related("here", None)],
    )
    assert d.to_json() == {
        "severity": "warning",
        "code": "internal.io",
        "message": "message",
        "hint": None,
        "location": {
            "file": "a.yaml",
            "line": 2,
            "column": 1,
            "end_line": None,
            "end_column": None,
        },
        "related": [{"message": "here", "location": None}],
    }
    assert list(d.to_json()) == ["severity", "code", "message", "hint", "location", "related"]


def test_diagnostics_sort_by_file_line_column_code() -> None:
    def diag(
        code: str, file: str | None, line: int | None = None, col: int | None = None
    ) -> Diagnostic:
        loc = None if file is None else Location(file, line, col)
        return Diagnostic(Severity.ERROR, code, "m", location=loc)

    items = [
        diag("usage.invalid", "b.yaml", 1, 1),
        diag("usage.invalid", "a.yaml", 10, 1),
        diag("internal.io", "a.yaml", 2, 5),
        diag("usage.invalid", "a.yaml", 2, 5),
        diag("internal.io", "a.yaml"),
        diag("usage.invalid", None),
    ]
    ordered = sorted_diagnostics(items)
    assert [(d.location and str(d.location), d.code) for d in ordered] == [
        (None, "usage.invalid"),
        ("a.yaml", "internal.io"),
        ("a.yaml:2:5", "internal.io"),
        ("a.yaml:2:5", "usage.invalid"),
        ("a.yaml:10:1", "usage.invalid"),
        ("b.yaml:1:1", "usage.invalid"),
    ]
