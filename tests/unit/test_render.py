"""Tests for the plain renderers."""

from __future__ import annotations

import pytest

from mmt_plugin.diagnostics import CliError, Diagnostic, Location, Related, Severity
from mmt_plugin.ui.render import escape, format_diagnostic, format_error, record


@pytest.mark.parametrize(
    ("text", "escaped"),
    [
        ("plain text", "plain text"),
        ("café ☃", "café ☃"),
        ("a\tb", "a\\tb"),
        ("a\nb", "a\\nb"),
        ("a\\b", "a\\\\b"),
        ("\x1b[31mred", "\\x1b[31mred"),
        ("\r\x00\x7f\x9b", "\\x0d\\x00\\x7f\\x9b"),
    ],
)
def test_escape(text: str, escaped: str) -> None:
    assert escape(text) == escaped


def test_a_record_with_esc_and_tab_keeps_its_field_count() -> None:
    line = record(["id\x1b[2J", "a\tb", "c\nd"])
    assert line.endswith("\n") and line.count("\n") == 1
    assert len(line.rstrip("\n").split("\t")) == 3
    assert "\x1b" not in line


def test_compiler_style_diagnostic() -> None:
    d = Diagnostic(
        Severity.ERROR,
        "internal.io",
        'attribute name "LEN" is already used by "len" (names are case-insensitive)',
        hint="rename one of the two attributes",
        location=Location("plugin.yaml", 14, 9),
        related=[Related("first defined here", Location("plugin.yaml", 9, 9))],
    )
    assert format_diagnostic(d, prog="mmt-plugin") == (
        'plugin.yaml:14:9: error: attribute name "LEN" is already used by "len" '
        "(names are case-insensitive) [internal.io]\n"
        "  plugin.yaml:9:9: note: first defined here\n"
        "  hint: rename one of the two attributes\n"
    )


def test_diagnostic_without_location_or_hint() -> None:
    d = Diagnostic(Severity.WARNING, "internal.io", "bad\x1b", related=[Related("why")])
    assert format_diagnostic(d, prog="mmt-plugin") == (
        "mmt-plugin: warning: bad\\x1b [internal.io]\n  mmt-plugin: note: why\n"
    )


def test_error_line() -> None:
    error = CliError("usage.no-command", "no command given", "run 'mmt-plugin --help'")
    assert format_error(error, prog="mmt-plugin") == (
        "mmt-plugin: error: no command given [usage.no-command]\n  hint: run 'mmt-plugin --help'\n"
    )
    assert format_error(CliError("interrupted", "interrupted"), prog="p") == (
        "p: error: interrupted [interrupted]\n"
    )
