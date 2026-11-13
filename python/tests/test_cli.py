"""Tests for the ``mmt-plugin`` command line."""

from __future__ import annotations

import subprocess
import sys
from importlib.metadata import entry_points, version

import pytest

from mmt_plugin import __version__
from mmt_plugin.cli import EXIT_OK, EXIT_USAGE, main


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
