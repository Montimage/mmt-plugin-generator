"""Tests for the ``--json`` envelope: one envelope per outcome, valid against
the shipped schema, deterministic."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from importlib import resources
from typing import Any

import pytest
from jsonschema import ValidationError

from mmt_plugin import __version__, envelope
from mmt_plugin.cli import main
from mmt_plugin.commands import Command
from mmt_plugin.diagnostics import CliError

Validate = Callable[[Any], None]
RunCli = Callable[..., "subprocess.CompletedProcess[bytes]"]

KEYS = ["schema_version", "tool", "command", "ok", "exit_code", "error", "diagnostics"]
KEYS += ["context", "result"]

#: (argv, exit code, error code or None, command)
OUTCOMES = [
    (["dummy"], 0, None, "dummy"),
    (["dummy", "--warn"], 0, None, "dummy"),
    (["--version"], 0, None, None),
    ([], 2, "usage.no-command", None),
    (["--bogus"], 2, "usage.unknown-option", None),
    (["dummy", "--bogus"], 2, "usage.unknown-option", None),
    (["dummy", "--crash"], 1, "internal.unexpected", "dummy"),
    (["dummy", "--oserror"], 1, "internal.io", "dummy"),
    (["dummy", "--broken-pipe"], 1, "internal.io", "dummy"),
    (["dummy", "--bad-result"], 1, "internal.unexpected", "dummy"),
    (["dummy", "--fail", "model.test-dummy"], 3, "model.test-dummy", "dummy"),
    (["dummy", "--fail", "sdk.test-dummy"], 4, "sdk.test-dummy", "dummy"),
    (["dummy", "--fail", "build.test-dummy"], 5, "build.test-dummy", "dummy"),
    (["dummy", "--return-error", "test.test-dummy", "--warn"], 6, "test.test-dummy", "dummy"),
    (["dummy", "--fail", "state.test-dummy"], 7, "state.test-dummy", "dummy"),
    (["dummy", "--fail", "usage.conflicting-options"], 2, "usage.conflicting-options", "dummy"),
]


@pytest.mark.parametrize(("argv", "exit_code", "code", "command"), OUTCOMES)
@pytest.mark.parametrize("json_after", [False, True])
def test_every_outcome_is_one_valid_envelope(
    dummy: Command,
    validate_envelope: Validate,
    capsys: pytest.CaptureFixture[str],
    argv: list[str],
    exit_code: int,
    code: str | None,
    command: str | None,
    json_after: bool,
) -> None:
    full = [*argv, "--json"] if json_after else ["--json", *argv]
    assert main(full, commands=[dummy]) == exit_code
    captured = capsys.readouterr()
    assert captured.err == ""
    assert captured.out.endswith("}\n") and captured.out.count("\n}\n") == 1
    doc = json.loads(captured.out)
    validate_envelope(doc)
    assert list(doc) == KEYS
    assert (doc["exit_code"], doc["ok"], doc["command"]) == (exit_code, exit_code == 0, command)
    assert (doc["error"] or {}).get("code") == code
    assert doc["tool"] == {"name": "mmt-plugin", "version": __version__}


def test_usage_error_with_json_is_exit_2_one_envelope_and_empty_stderr(
    run_cli: RunCli, validate_envelope: Validate
) -> None:
    proc = run_cli(["--json", "dummy", "--no-such-option"])
    assert proc.returncode == 2
    assert proc.stderr == b""
    doc = json.loads(proc.stdout)
    validate_envelope(doc)
    assert doc["error"]["class"] == "usage"
    assert doc["result"] is None
    assert doc["context"] == {"project": None, "sdk": None}


def test_json_after_double_dash_is_not_json(
    dummy: Command, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["dummy", "--", "--json"], commands=[dummy]) == 0
    assert capsys.readouterr().out == "value\t--json\n"


def test_version_envelope(dummy: Command, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--json", "--version"], commands=[dummy]) == 0
    result = json.loads(capsys.readouterr().out)["result"]
    assert result["version"] == __version__
    assert result["sdk_profiles"] == []
    assert isinstance(result["python"], str)


def test_success_envelope_content(dummy: Command, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--json", "-C", "sub/../proj", "dummy", "--warn"], commands=[dummy]) == 0
    doc = json.loads(capsys.readouterr().out)
    assert doc["context"] == {"project": "proj", "sdk": None}
    assert [d["severity"] for d in doc["diagnostics"]] == ["note", "warning"]
    assert doc["diagnostics"][1]["location"] == {
        "file": "plugin.yaml",
        "line": 14,
        "column": 9,
        "end_line": 14,
        "end_column": 12,
    }


@pytest.mark.parametrize(
    "argv",
    [
        ["--json", "--version"],
        ["--json", "dummy", "café ☃", "--warn"],
        ["--json", "dummy", "--fail", "model.test-dummy"],
        ["--json", "dummy", "--bogus"],
        ["dummy", "x", "--warn"],
    ],
)
def test_reruns_are_byte_identical(run_cli: RunCli, argv: list[str]) -> None:
    first = run_cli(argv)
    second = run_cli(argv)
    assert (first.returncode, first.stdout, first.stderr) == (
        second.returncode,
        second.stdout,
        second.stderr,
    )
    if "--json" in argv:
        assert first.stdout.isascii()
        json.loads(first.stdout)


def test_dumps_is_deterministic_and_ascii() -> None:
    doc = envelope.build(command="x", result={"b": "é", "a": [1, 2]})
    text = envelope.dumps(doc)
    assert text == envelope.dumps(json.loads(text))
    assert text.isascii() and text.endswith("}\n") and not text.endswith("\n\n")
    assert '"b": "\\u00e9"' in text
    with pytest.raises(ValueError):
        envelope.dumps({"x": float("nan")})


def test_usage_errors_have_a_null_result() -> None:
    doc = envelope.build(command=None, error=CliError("usage.invalid", "bad"), result={"x": 1})
    assert doc["result"] is None


def test_schema_ships_in_the_package() -> None:
    path = resources.files("mmt_plugin").joinpath("schemas/cli/v1/envelope.json")
    assert json.loads(path.read_text(encoding="utf-8")) == envelope.load_schema()


@pytest.mark.parametrize(
    "change",
    [
        {"ok": False},
        {"exit_code": 3},
        {"schema_version": 2},
        {"extra": 1},
        {"error": {"class": "model", "code": "model.x", "message": "m", "hint": None}},
    ],
)
def test_schema_rejects_inconsistent_envelopes(
    validate_envelope: Validate, change: dict[str, Any]
) -> None:
    doc = {**envelope.build(command="x"), **change}
    with pytest.raises(ValidationError):
        validate_envelope(doc)


def test_schema_ties_the_error_class_to_the_exit_code(validate_envelope: Validate) -> None:
    doc = envelope.build(command="x", error=CliError("internal.io", "m"))
    validate_envelope(doc)
    doc["exit_code"] = 4
    with pytest.raises(ValidationError):
        validate_envelope(doc)
    doc["exit_code"], doc["error"]["code"] = 1, "sdk.not-internal"
    with pytest.raises(ValidationError):
        validate_envelope(doc)
