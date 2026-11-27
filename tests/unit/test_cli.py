"""Tests for the ``mmt-plugin`` command line."""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import signal
import subprocess
import sys
import time
from collections.abc import Callable
from importlib.metadata import entry_points, version
from pathlib import Path

import pytest

from mmt_plugin import __version__
from mmt_plugin.cli import (
    EXIT_OK,
    EXIT_USAGE,
    UsageError,
    _classify,
    build_parser,
    main,
    parse_args,
)
from mmt_plugin.commands import Command, Context, Outcome
from mmt_plugin.exitcodes import ExitCode

DUMMY_SCRIPT = Path(__file__).with_name("dummy_command.py")


def test_version_comes_from_package_metadata(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == EXIT_OK
    assert __version__ == version("mmt-plugin")
    assert capsys.readouterr().out == f"mmt-plugin {version('mmt-plugin')}\n"


def test_help_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == EXIT_OK
    out = capsys.readouterr().out
    assert out.startswith("usage: mmt-plugin")
    assert "--version" in out


@pytest.mark.parametrize("argv", [[], ["--no-such-option"]])
def test_usage_errors_exit_two(argv: list[str], capsys: pytest.CaptureFixture[str]) -> None:
    code: int | str | None
    try:
        code = main(argv)
    except SystemExit as exc:
        code = exc.code
    assert code == EXIT_USAGE
    assert "usage: mmt-plugin" in capsys.readouterr().err


def test_console_script_points_at_main() -> None:
    (script,) = entry_points(group="console_scripts", name="mmt-plugin")
    assert script.value == "mmt_plugin.cli:main"
    assert script.load() is main


def test_python_dash_m_runs_the_cli() -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "mmt_plugin", "--version"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == EXIT_OK, proc.stderr
    assert proc.stdout == f"mmt-plugin {__version__}\n"


# --- The CLI contract core (#43): parser, streams, exit codes ---------------

GLOBALS = ["--json", "-q", "--no-color", "-v", "-C", "proj"]


def _code(argv: list[str], commands: list[Command]) -> int | str | None:
    try:
        return main(argv, commands=commands)
    except SystemExit as exc:
        return exc.code


def _public(ns: argparse.Namespace) -> dict[str, object]:
    return {k: v for k, v in vars(ns).items() if k != "_command"}


@pytest.mark.parametrize(
    ("before", "after"),
    [
        (GLOBALS, []),
        ([], GLOBALS),
        (["--json", "-v"], ["-q", "--no-color", "-C", "proj"]),
    ],
)
def test_global_options_parse_alike_before_and_after_the_command(
    dummy: Command, before: list[str], after: list[str]
) -> None:
    ns = parse_args([*before, "dummy", "x", *after], [dummy])
    reference = parse_args([*GLOBALS, "dummy", "x"], [dummy])
    assert _public(ns) == _public(reference)
    assert ns._command is dummy
    assert (ns.json, ns.quiet, ns.no_color, ns.verbose, ns.project) == (
        True,
        True,
        True,
        1,
        "proj",
    )


def test_global_options_defaults(dummy: Command) -> None:
    ns = parse_args(["dummy"], [dummy])
    assert (ns.json, ns.quiet, ns.no_color, ns.verbose, ns.project) == (
        False,
        False,
        False,
        0,
        ".",
    )
    assert ns.command == "dummy"


def test_verbose_counts_on_both_sides_and_the_last_project_wins(dummy: Command) -> None:
    ns = parse_args(["-v", "-C", "a", "dummy", "-vv", "--project", "b"], [dummy])
    assert ns.verbose == 3
    assert ns.project == "b"


def test_global_options_after_the_command_reach_the_command(
    dummy: Command, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["dummy", "--json", "-C", "proj", "-v"], commands=[dummy]) == EXIT_OK
    result = json.loads(capsys.readouterr().out)["result"]
    assert result["json"] is True
    assert result["project"] == "proj"
    assert result["verbose"] == 1


@pytest.mark.parametrize(
    "argv",
    [
        ["--vers"],
        ["--js", "dummy"],
        ["--verb", "dummy"],
        ["dummy", "--cra"],
        ["dummy", "--proj", "x"],
        ["dumm"],
    ],
)
def test_no_abbreviations(
    dummy: Command, argv: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    assert _code(argv, [dummy]) == EXIT_USAGE
    assert "usage: mmt-plugin" in capsys.readouterr().err


def test_parsers_disallow_abbreviations(dummy: Command) -> None:
    parser = build_parser([dummy])
    assert parser.allow_abbrev is False
    (subparsers,) = (a for a in parser._actions if isinstance(a, argparse._SubParsersAction))
    assert all(p.allow_abbrev is False for p in subparsers.choices.values())


def test_help_names_linux_and_lists_every_exit_code(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == EXIT_OK
    out = capsys.readouterr().out
    assert "Linux" in out
    for code in ExitCode:
        assert f"\n  {int(code):<4} {code.meaning}\n" in out + "\n"
    for option in (
        "-C",
        "--project DIR",
        "--json",
        "--no-color",
        "-q, --quiet",
        "-v, --verbose",
    ):
        assert option in out


@pytest.mark.parametrize("argv", [["--help"], ["dummy", "--help"], ["--json", "--help"]])
def test_help_is_plain_even_with_force_color(
    run_cli: Callable[..., subprocess.CompletedProcess[bytes]],
    clean_env: Callable[..., dict[str, str]],
    argv: list[str],
) -> None:
    proc = run_cli(argv, env=clean_env(FORCE_COLOR="1", PYTHON_COLORS="1"))
    assert proc.returncode == EXIT_OK, proc.stderr
    assert proc.stdout.startswith(b"usage: mmt-plugin")
    assert b"\x1b" not in proc.stdout + proc.stderr


@pytest.mark.parametrize(
    ("argv", "code"),
    [
        ([], "usage.no-command"),
        (["--no-such-option"], "usage.unknown-option"),
        (["nope"], "usage.unknown-command"),
        (["dummy", "a", "b"], "usage.unexpected-argument"),
        (["dummy", "--mode", "c"], "usage.invalid-value"),
        (["dummy", "--records", "x"], "usage.invalid-value"),
        (["dummy", "--fail"], "usage.missing-argument"),
        (["-C"], "usage.missing-argument"),
        (["dummy", "--left", "--right"], "usage.conflicting-options"),
        (["dummy", "--json=yes"], "usage.invalid-value"),
    ],
)
def test_usage_errors_have_a_registered_code(
    dummy: Command, argv: list[str], code: str, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["--json", *argv], commands=[dummy]) == EXIT_USAGE
    assert json.loads(capsys.readouterr().out)["error"]["code"] == code


#: The phrases ``_classify`` matches, as a user could type them.
_MATCHED_PHRASES = [
    "unrecognized arguments: -x",
    "the following arguments are required: x",
    "one of the arguments --left --right is required",
    "argument <command>: invalid choice: 'x'",
    "invalid choice: 'x'",
    "not allowed with argument --left",
    "not allowed with",
    "expected one argument",
    "required",
    "ignored explicit argument 'x'",
    "invalid int value: 'x'",
]


@pytest.mark.parametrize("phrase", _MATCHED_PHRASES)
@pytest.mark.parametrize(
    ("argv", "code"),
    [
        (["dummy", "--records", "{}"], "usage.invalid-value"),
        (["dummy", "--json={}"], "usage.invalid-value"),
        (["dummy", "--mode", "{}"], "usage.invalid-value"),
        (["{}"], "usage.unknown-command"),
        (["dummy", "a", "{}"], "usage.unexpected-argument"),
        (["dummy", "a", "--bogus", "{}"], "usage.unknown-option"),
    ],
)
def test_user_text_does_not_change_the_usage_code(
    dummy: Command,
    argv: list[str],
    code: str,
    phrase: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    argv = [arg.format(phrase) for arg in argv]
    assert main(["--json", *argv], commands=[dummy]) == EXIT_USAGE
    error = json.loads(capsys.readouterr().out)["error"]
    assert phrase in error["message"]
    assert error["code"] == code


@pytest.mark.parametrize(
    ("message", "code"),
    [
        ("unrecognized arguments: --x y", "usage.unknown-option"),
        ("unrecognized arguments: y --x", "usage.unexpected-argument"),
        ("the following arguments are required: <command>", "usage.missing-argument"),
        ("one of the arguments --a --b is required", "usage.missing-argument"),
        ("argument <command>: invalid choice: 'x' (choose from a, b)", "usage.unknown-command"),
        (
            "argument <command>: invalid choice: 'x', maybe you meant 'a'? (choose from a)",
            "usage.unknown-command",
        ),
        ("argument --mode: invalid choice: 'c' (choose from 'a', 'b')", "usage.invalid-value"),
        ("argument --left: not allowed with argument --right", "usage.conflicting-options"),
        ("argument -C/--project: expected one argument", "usage.missing-argument"),
        ("argument --x: expected at least one argument", "usage.missing-argument"),
        ("argument --x: expected 2 arguments", "usage.missing-argument"),
        ("argument -v/--verbose: ignored explicit argument 'x'", "usage.invalid-value"),
        ("argument --records: invalid int value: 'x'", "usage.invalid-value"),
        # User text in a fixed form never decides the code.
        ("argument --records: invalid int value: 'not allowed with'", "usage.invalid-value"),
        ("argument --json: ignored explicit argument 'required'", "usage.invalid-value"),
        ("argument --mode: invalid choice: 'expected' (choose from a)", "usage.invalid-value"),
        ("unrecognized arguments: invalid choice", "usage.unexpected-argument"),
        # Any other form is the fallback, whatever words it carries.
        ("ambiguous option: --not allowed with could match --a, --b", "usage.invalid"),
        ("argument --x: can't open 'invalid int value: x': No such file", "usage.invalid"),
        ("argument --x: 'f' is not callable", "usage.invalid"),
        ("unexpected option string: --required", "usage.invalid"),
        ("argument without a separator", "usage.invalid"),
        ("not allowed with argument --a", "usage.invalid"),
        ("expected one argument", "usage.invalid"),
    ],
)
def test_classify_matches_only_the_fixed_argparse_forms(message: str, code: str) -> None:
    assert _classify(message) == code


@pytest.mark.parametrize("argv", [["--json=1"], ["--json="], ["dummy", "--json=yes"]])
def test_json_with_a_value_is_a_usage_error_in_one_envelope(
    dummy: Command, argv: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(argv, commands=[dummy]) == EXIT_USAGE
    captured = capsys.readouterr()
    doc = json.loads(captured.out)
    assert doc["error"]["code"] == "usage.invalid-value"
    assert "ignored explicit argument" in doc["error"]["message"]
    assert captured.err == ""


#: Command lines that argparse reads differently from one Python version to
#: the next (3.10 to 3.14), with the code each one gets on every version.
_VERSION_DEPENDENT = [
    (["-vx", "dummy"], "usage.invalid-value"),
    (["dummy", "-vx"], "usage.invalid-value"),
    (["-qvx", "dummy"], "usage.invalid-value"),
    (["-v=x", "dummy"], "usage.invalid-value"),
    (["-vx", "dummy", "--help"], "usage.invalid-value"),
    (["--", "dummy"], "usage.unknown-command"),
    (["-v", "--", "dummy", "x"], "usage.unknown-command"),
    (["--"], "usage.unknown-command"),
    (["--version", "--"], "usage.unknown-command"),
]


@pytest.mark.parametrize(("argv", "code"), _VERSION_DEPENDENT)
def test_argv_parses_the_same_on_every_python(
    dummy: Command, argv: list[str], code: str, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["--json", *argv], commands=[dummy]) == EXIT_USAGE
    assert json.loads(capsys.readouterr().out)["error"]["code"] == code
    assert main(argv, commands=[dummy]) == EXIT_USAGE
    err = capsys.readouterr().err
    assert err.startswith("usage: mmt-plugin")
    assert f"[{code}]" in err


def test_the_ignored_value_of_a_flag_cluster_is_named() -> None:
    with pytest.raises(UsageError) as exc:
        parse_args(["-vqx", "dummy"])
    assert exc.value.message == "argument -q/--quiet: ignored explicit argument 'x'"


@pytest.mark.parametrize(
    ("argv", "verbose", "quiet", "project", "value"),
    [
        (["-vv", "dummy"], 2, False, ".", "hello"),
        (["-qv", "dummy"], 1, True, ".", "hello"),
        (["-vC", "p", "dummy"], 1, False, "p", "hello"),
        (["-vCp", "dummy"], 1, False, "p", "hello"),
        (["-C", "-1", "dummy"], 0, False, "-1", "hello"),
        (["dummy", "-vv", "-"], 2, False, ".", "-"),
        (["dummy", "--", "-vx"], 0, False, ".", "-vx"),
        (["dummy", "x", "-qC", "p"], 0, True, "p", "x"),
    ],
)
def test_flag_clusters_and_values_still_parse(
    dummy: Command, argv: list[str], verbose: int, quiet: bool, project: str, value: str
) -> None:
    ns = parse_args(argv, [dummy])
    assert (ns.verbose, ns.quiet, ns.project, ns.value) == (verbose, quiet, project, value)


@pytest.mark.parametrize(
    ("argv", "code"),
    [
        (["--bogus", "--version"], "usage.unknown-option"),
        (["--version", "--bogus"], "usage.unknown-option"),
        (["--version", "-x"], "usage.unknown-option"),
        (["--version", "dummy", "a", "b"], "usage.unexpected-argument"),
        (["--version", "nope"], "usage.unknown-command"),
        (["--version", "--no-color=1"], "usage.invalid-value"),
        (["--version", "dummy", "--fail"], "usage.missing-argument"),
    ],
)
def test_a_usage_error_wins_over_version(
    dummy: Command, argv: list[str], code: str, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _code(argv, [dummy]) == EXIT_USAGE
    captured = capsys.readouterr()
    assert captured.out == ""
    assert f"[{code}]" in captured.err
    assert main(["--json", *argv], commands=[dummy]) == EXIT_USAGE
    doc = json.loads(capsys.readouterr().out)
    assert (doc["error"]["code"], doc["result"]) == (code, None)


@pytest.mark.parametrize(
    "argv", [["--version"], ["-v", "--version", "-q"], ["--version", "-C", "x"]]
)
def test_version_with_valid_options(
    dummy: Command, argv: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    assert _code(argv, [dummy]) == EXIT_OK
    assert capsys.readouterr().out == f"mmt-plugin {__version__}\n"
    assert main(["--json", *argv], commands=[dummy]) == EXIT_OK
    assert json.loads(capsys.readouterr().out)["result"]["version"] == __version__


def test_help_after_version_prints_the_help(
    dummy: Command, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _code(["--version", "--help"], [dummy]) == EXIT_OK
    assert capsys.readouterr().out.startswith("usage: mmt-plugin")


@pytest.mark.parametrize(
    ("argv", "usage"),
    [
        (["--help", "-vx"], "usage: mmt-plugin [-h]"),
        (["--help", "--"], "usage: mmt-plugin [-h]"),
        (["--help", "--", "dummy"], "usage: mmt-plugin [-h]"),
        (["-h", "-qvx", "dummy"], "usage: mmt-plugin [-h]"),
        (["-vh", "-vx"], "usage: mmt-plugin [-h]"),
        (["dummy", "--help", "-vx"], "usage: mmt-plugin dummy"),
        (["dummy", "-h", "--json=1"], "usage: mmt-plugin dummy"),
        (["-v", "dummy", "-qh", "-vx"], "usage: mmt-plugin dummy"),
    ],
)
def test_help_wins_over_a_later_cluster_error_or_double_dash(
    dummy: Command, argv: list[str], usage: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """``--help`` acts left to right: what follows it does not win (#92)."""
    assert _code(argv, [dummy]) == EXIT_OK
    captured = capsys.readouterr()
    assert captured.out.startswith(usage)
    assert captured.err == ""


@pytest.mark.parametrize(
    ("argv", "code"),
    [
        (["--help=1"], "usage.invalid-value"),
        (["-hx"], "usage.invalid-value"),
        (["dummy", "-vhx"], "usage.invalid-value"),
    ],
)
def test_a_help_flag_with_a_value_is_still_a_usage_error(
    dummy: Command, argv: list[str], code: str, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _code(argv, [dummy]) == EXIT_USAGE
    captured = capsys.readouterr()
    assert captured.out == ""
    assert f"[{code}]" in captured.err


@pytest.mark.parametrize(
    ("argv", "usage"),
    [
        (["--help", "-vx"], "usage: mmt-plugin [-h]"),
        (["validate", "--help", "-vx"], "usage: mmt-plugin validate"),
        (["--help", "--"], "usage: mmt-plugin [-h]"),
    ],
)
def test_help_wins_with_the_real_commands(
    argv: list[str], usage: str, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as exc:
        main(argv)
    assert exc.value.code == EXIT_OK
    assert capsys.readouterr().out.startswith(usage)


def test_usage_error_in_human_mode_is_compiler_style_on_stderr(
    dummy: Command, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["dummy", "--bogus"], commands=[dummy]) == EXIT_USAGE
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("usage: mmt-plugin dummy")
    assert "mmt-plugin: error: unrecognized arguments: --bogus [usage.unknown-option]\n" in (
        captured.err
    )
    assert captured.err.endswith("  hint: run 'mmt-plugin dummy --help' for the usage\n")


def test_results_go_to_stdout_and_diagnostics_to_stderr(
    dummy: Command, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["dummy", "v\x1b[31m\tx", "--warn"], commands=[dummy]) == EXIT_OK
    captured = capsys.readouterr()
    assert captured.out == "value\tv\\x1b[31m\\tx\n"
    # Sorted by file, line, column: diagnostics without a location first.
    assert captured.err == (
        "mmt-plugin: note: a dummy note [model.test-dummy]\n"
        "plugin.yaml:14:9: warning: a dummy warning [model.test-dummy]\n"
        "  plugin.yaml:9:9: note: first defined here\n"
        "  hint: a dummy hint\n"
    )


def test_quiet_prints_only_errors(dummy: Command, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["-q", "dummy", "--warn"], commands=[dummy]) == EXIT_OK
    assert capsys.readouterr() == ("", "")
    assert main(["dummy", "-q", "--fail", "state.test-dummy"], commands=[dummy]) == 7
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == (
        "mmt-plugin: error: dummy failure [state.test-dummy]\n  hint: dummy hint\n"
    )


@pytest.mark.parametrize(
    ("flag", "code", "exit_code"),
    [
        ("--crash", "internal.unexpected", 1),
        ("--oserror", "internal.io", 1),
        ("--bad-result", "internal.unexpected", 1),
        ("--unregistered", "internal.unexpected", 1),
    ],
)
def test_internal_errors_exit_one_without_traceback(
    dummy: Command, flag: str, code: str, exit_code: int, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["--json", "dummy", flag], commands=[dummy]) == exit_code
    captured = capsys.readouterr()
    assert json.loads(captured.out)["error"]["code"] == code
    assert captured.err == ""


def test_traceback_only_with_vv(dummy: Command, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["dummy", "--crash", "-v"], commands=[dummy]) == 1
    err = capsys.readouterr().err
    assert "Traceback" not in err
    assert "unexpected error: RuntimeError: boom [internal.unexpected]" in err
    assert main(["dummy", "--crash", "-vv"], commands=[dummy]) == 1
    err = capsys.readouterr().err
    assert err.startswith("Traceback (most recent call last):")
    assert "RuntimeError: boom" in err


def test_verbose_logs_go_to_stderr(dummy: Command, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--json", "dummy", "--log"], commands=[dummy]) == 0
    assert capsys.readouterr().err == ""
    assert main(["--json", "dummy", "--log", "-v"], commands=[dummy]) == 0
    assert capsys.readouterr().err == "mmt-plugin: stage one\n"
    assert main(["--json", "dummy", "--log", "-vv"], commands=[dummy]) == 0
    assert capsys.readouterr().err == "mmt-plugin: stage one\nmmt-plugin: debug detail\n"


class _NoTerminal(io.StringIO):
    def read(self, size: int | None = -1) -> str:
        raise AssertionError("mmt-plugin read from stdin")

    def readline(self, size: int | None = -1) -> str:  # type: ignore[override]
        raise AssertionError("mmt-plugin read from stdin")


@pytest.mark.parametrize(
    "argv", [[], ["--json"], ["dummy"], ["--json", "dummy", "--fail", "model.test-dummy"]]
)
def test_nothing_is_read_from_the_terminal(
    dummy: Command,
    argv: list[str],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(sys, "stdin", _NoTerminal())
    assert _code(argv, [dummy]) in (0, 2, 3)


def test_stream_decisions_reach_the_command(
    dummy: Command, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[Context] = []
    real_run = dummy.run

    def spy(args: argparse.Namespace, ctx: Context) -> Outcome:
        seen.append(ctx)
        return real_run(args, ctx)

    monkeypatch.setattr(dummy, "run", spy)
    monkeypatch.setenv("FORCE_COLOR", "1")
    monkeypatch.delenv("NO_COLOR", raising=False)
    main(["--json", "dummy"], commands=[dummy])
    main(["--no-color", "dummy"], commands=[dummy])
    assert not seen[0].stdout_style.styled
    assert seen[1].stdout_style.styled
    assert not seen[1].stdout_style.escapes


def test_sigint_exits_130_with_one_envelope(
    run_cli: Callable[..., subprocess.CompletedProcess[bytes]],
    clean_env: Callable[..., dict[str, str]],
    tmp_path: Path,
) -> None:
    for json_mode in (True, False):
        marker = tmp_path / f"started-{json_mode}"
        argv = [*(["--json"] if json_mode else []), "dummy", "--sleep", str(marker)]
        proc = subprocess.Popen(
            [sys.executable, str(DUMMY_SCRIPT), *argv],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=clean_env(),
        )
        deadline = time.monotonic() + 30
        while not marker.exists():
            assert proc.poll() is None, proc.communicate()
            assert time.monotonic() < deadline, "the dummy command did not start"
            time.sleep(0.02)
        proc.send_signal(signal.SIGINT)
        out, err = proc.communicate(timeout=30)
        assert proc.returncode == 130
        if json_mode:
            assert err == b""
            doc = json.loads(out)
            assert (doc["exit_code"], doc["command"]) == (130, "dummy")
            assert doc["error"]["code"] == "interrupted"
        else:
            assert out == b""
            assert err == b"mmt-plugin: error: interrupted [interrupted]\n"


@pytest.mark.parametrize(
    "argv",
    [
        ["--version"],
        ["--json", "--version"],
        ["--help"],
        ["dummy", "--records", "200000"],
        ["--json", "dummy", "--records", "100"],
    ],
)
def test_closed_stdout_ends_quietly(
    argv: list[str], clean_env: Callable[..., dict[str, str]]
) -> None:
    read_end, write_end = os.pipe()
    os.close(read_end)
    try:
        proc = subprocess.run(
            [sys.executable, str(DUMMY_SCRIPT), *argv],
            stdin=subprocess.DEVNULL,
            stdout=write_end,
            stderr=subprocess.PIPE,
            env=clean_env(),
            timeout=60,
            check=False,
        )
    finally:
        os.close(write_end)
    assert proc.stderr == b""
    assert proc.returncode == EXIT_OK


def test_closed_stdout_with_python_dash_m(clean_env: Callable[..., dict[str, str]]) -> None:
    # A pipe whose read end is closed before the command starts: it cannot
    # write before the reader goes away (as it could with `| head -c0`).
    read_end, write_end = os.pipe()
    os.close(read_end)
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "mmt_plugin", "--version"],
            stdin=subprocess.DEVNULL,
            stdout=write_end,
            stderr=subprocess.PIPE,
            env=clean_env(),
            timeout=60,
            check=False,
        )
    finally:
        os.close(write_end)
    assert proc.returncode == 0
    assert proc.stderr == b""


def _strict_utf8_env(clean_env: Callable[..., dict[str, str]]) -> dict[str, str]:
    """An environment in which Python's stdout is strict UTF-8 (not the
    ``surrogateescape`` that C.UTF-8 gives), or a skip when no such locale."""
    env = clean_env(LANG="en_US.UTF-8")
    probe = subprocess.run(
        [sys.executable, "-c", "import sys; print(sys.stdout.encoding, sys.stdout.errors)"],
        capture_output=True,
        env=env,
        timeout=60,
        check=False,
    )
    if probe.stdout.split() != [b"utf-8", b"strict"]:
        pytest.skip(f"no strict UTF-8 locale (en_US.UTF-8 gives {probe.stdout!r})")
    return env


@pytest.mark.parametrize(
    ("extra", "code"), [([], EXIT_OK), (["--return-error", "model.test-dummy"], 3)]
)
def test_undecodable_argv_is_escaped_on_a_strict_utf8_stdout(
    extra: list[str],
    code: int,
    run_cli: Callable[..., subprocess.CompletedProcess[bytes]],
    clean_env: Callable[..., dict[str, str]],
) -> None:
    env = _strict_utf8_env(clean_env)
    proc = run_cli(["dummy", os.fsdecode(b"\xff"), *extra], env=env)
    assert b"Traceback" not in proc.stderr
    assert proc.returncode == code
    assert proc.stdout == b"value\t\\xff\n"
    proc = run_cli(["--json", "dummy", os.fsdecode(b"\xff"), *extra], env=env)
    assert proc.returncode == code
    assert json.loads(proc.stdout)["result"]["value"] == "\udcff"
    assert b'"value": "\\udcff"' in proc.stdout


def test_a_bidi_override_is_escaped_in_plain_output_only(
    dummy: Command, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["dummy", "txt.exe\u202egpj.c"], commands=[dummy]) == EXIT_OK
    assert capsys.readouterr().out == "value\ttxt.exe\\u202egpj.c\n"
    assert main(["--json", "dummy", "txt.exe\u202egpj.c"], commands=[dummy]) == EXIT_OK
    out = capsys.readouterr().out
    assert json.loads(out)["result"]["value"] == "txt.exe\u202egpj.c"
    assert '"value": "txt.exe\\u202egpj.c"' in out


#: Bytes that are not UTF-8: the 8-bit C1 controls (0x9B is CSI, 0x9D OSC,
#: 0x90 DCS), the rest of 0x80-0x9F, and 0xFF.
_NOT_UTF8 = bytes(range(0x80, 0xA0)) + b"\xff"


@pytest.mark.parametrize("locale", ["C", "C.UTF-8", "ascii", "strict UTF-8"])
def test_undecodable_argv_prints_the_same_in_every_locale(
    locale: str,
    run_cli: Callable[..., subprocess.CompletedProcess[bytes]],
    clean_env: Callable[..., dict[str, str]],
) -> None:
    # C and C.UTF-8 give a surrogateescape stdout, which would write the raw
    # bytes; ascii and strict UTF-8 a strict one, switched to backslashreplace.
    if locale == "strict UTF-8":
        env = _strict_utf8_env(clean_env)
    else:
        env = clean_env(
            **{"C": {"LC_ALL": "C"}, "ascii": {"PYTHONIOENCODING": "ascii"}}.get(locale, {})
        )
    proc = run_cli(["dummy", os.fsdecode(b"a" + _NOT_UTF8 + b"z")], env=env)
    assert (proc.returncode, proc.stderr) == (EXIT_OK, b"")
    escaped = "".join(f"\\x{b:02x}" for b in _NOT_UTF8).encode("ascii")
    assert proc.stdout == b"value\ta" + escaped + b"z\n"
    assert all(b < 0x80 for b in proc.stdout)


@pytest.mark.parametrize(
    ("extra", "code"), [([], EXIT_OK), (["--return-error", "model.test-dummy"], 3)]
)
def test_unencodable_record_is_escaped_on_an_ascii_stdout(
    extra: list[str],
    code: int,
    run_cli: Callable[..., subprocess.CompletedProcess[bytes]],
    clean_env: Callable[..., dict[str, str]],
) -> None:
    env = clean_env(PYTHONIOENCODING="ascii")
    proc = run_cli(["dummy", "é", *extra], env=env)
    assert b"Traceback" not in proc.stderr
    assert proc.returncode == code
    assert proc.stdout == b"value\t\\xe9\n"
    plain_json = run_cli(["--json", "dummy", "é", *extra])
    proc = run_cli(["--json", "dummy", "é", *extra], env=env)
    assert proc.returncode == code
    assert proc.stdout == plain_json.stdout
    assert b'"value": "\\u00e9"' in proc.stdout


@pytest.mark.parametrize(
    ("argv", "code"),
    [
        (["dummy"], EXIT_OK),
        (["--json", "dummy"], EXIT_OK),
        (["dummy", "--return-error", "model.test-dummy"], 3),
        (["--json", "dummy", "--return-error", "model.test-dummy"], 3),
        (["--version"], EXIT_OK),
        (["--json", "--version"], EXIT_OK),
        (["--help"], EXIT_OK),
    ],
)
def test_stdout_closed_at_startup_ends_quietly(
    argv: list[str], code: int, clean_env: Callable[..., dict[str, str]]
) -> None:
    # `>&-`: fd 1 is closed, so Python starts with sys.stdout set to None.
    proc = subprocess.run(
        ["sh", "-c", 'exec "$0" "$@" >&-', sys.executable, str(DUMMY_SCRIPT), *argv],
        stdin=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        env=clean_env(),
        timeout=60,
        check=False,
    )
    assert b"Traceback" not in proc.stderr
    assert proc.returncode == code
    if code == EXIT_OK:
        assert proc.stderr == b""


@pytest.mark.skipif(not os.path.exists("/dev/full"), reason="needs /dev/full")
@pytest.mark.parametrize(
    "argv",
    [
        ["dummy"],
        ["--json", "dummy"],
        ["dummy", "--return-error", "model.test-dummy"],
        ["--version"],
        ["--json", "--version"],
        ["--help"],
        ["-vv", "dummy"],
    ],
)
def test_stdout_write_failure_is_one_internal_io_line(
    argv: list[str], clean_env: Callable[..., dict[str, str]]
) -> None:
    with open("/dev/full", "wb") as full:
        proc = subprocess.run(
            [sys.executable, str(DUMMY_SCRIPT), *argv],
            stdin=subprocess.DEVNULL,
            stdout=full,
            stderr=subprocess.PIPE,
            env=clean_env(),
            timeout=60,
            check=False,
        )
    assert proc.returncode == ExitCode.INTERNAL
    line = b"mmt-plugin: error: cannot write to stdout: No space left on device [internal.io]\n"
    assert b"Exception ignored" not in proc.stderr
    if "-vv" in argv:
        assert proc.stderr.startswith(b"Traceback")
        assert proc.stderr.endswith(line)
        assert proc.stderr.count(b"[internal.io]") == 1
    else:
        assert b"Traceback" not in proc.stderr
        # The stdout write fails first: a returned error is not reported.
        assert proc.stderr == line


def _one_envelope(proc: subprocess.CompletedProcess[bytes]) -> dict[str, object]:
    out = proc.stdout.decode()
    doc, end = json.JSONDecoder().raw_decode(out)
    assert out[end:] == "\n"
    assert isinstance(doc, dict)
    return doc


# A digit int() cannot read in COLUMNS (review W1): str.isdigit() is true for
# "²" and "③", and main() calls decide() before its try.
@pytest.mark.parametrize("columns", ["\u00b2", "\u2462"])
def test_a_columns_value_int_cannot_read_falls_back(
    columns: str,
    run_cli: Callable[..., subprocess.CompletedProcess[bytes]],
    clean_env: Callable[..., dict[str, str]],
) -> None:
    env = clean_env(COLUMNS=columns)

    proc = run_cli(["dummy", "x"], env=env)
    assert (proc.returncode, proc.stdout, proc.stderr) == (EXIT_OK, b"value\tx\n", b"")

    proc = run_cli(["dummy", "--box"], env=clean_env(COLUMNS=columns, FORCE_COLOR="1"))
    assert (proc.returncode, proc.stderr) == (EXIT_OK, b"")
    plain = re.sub(r"\x1b\[[0-9;]*m", "", proc.stdout.decode())
    assert {len(line) for line in plain.splitlines()} == {80}  # the fallback width

    for argv in (["--json", "--version"], ["--version", "--json"]):
        proc = run_cli(argv, env=env)
        assert (proc.returncode, proc.stderr) == (EXIT_OK, b"")
        assert _one_envelope(proc)["ok"] is True

    proc = run_cli(["--json", "nosuch"], env=env)
    assert (proc.returncode, proc.stderr) == (EXIT_USAGE, b"")
    error = _one_envelope(proc)["error"]
    assert isinstance(error, dict)
    assert error["code"] == "usage.unknown-command"

    proc = run_cli(["nosuch"], env=env)
    assert (proc.returncode, proc.stdout) == (EXIT_USAGE, b"")
    assert b"Traceback" not in proc.stderr
    assert proc.stderr.count(b"[usage.unknown-command]") == 1
