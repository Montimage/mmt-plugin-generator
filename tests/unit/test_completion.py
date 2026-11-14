"""Tests for ``mmt-plugin completion {bash,zsh,fish}``.

Each script is checked against the parser it came from (every command, every
option ``--help`` shows, every choice), for syntax (``bash -n``, and
``zsh -n``/``fish -n`` when the shell is installed), and for not running
``mmt-plugin`` when it is loaded or used.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from collections.abc import Sequence
from pathlib import Path

import pytest

from mmt_plugin.cli import build_parser, main
from mmt_plugin.commands import COMMANDS, Command, Context, Outcome, Subparsers
from mmt_plugin.commands.completion import SHELLS, UnsafeWordError, generate, spec_of
from mmt_plugin.exitcodes import ExitCode


class TrickyCommand:
    """A command whose help and choices need quoting in every shell."""

    name = "tricky"
    exit_codes = (ExitCode.MODEL,)

    def register(self, subparsers: Subparsers) -> argparse.ArgumentParser:
        parser = subparsers.add_parser(self.name, help='it\'s [odd]: "quoted" \\ $HOME `x`')
        parser.add_argument("model", metavar="MODEL", help="a file: it's [here]")
        parser.add_argument("--out", metavar="DIR", help="dir ]; echo pwned [")
        parser.add_argument("--level", choices=["low", "high"], help="one of: low, high")
        parser.add_argument("--addr", metavar="HOST:PORT", help="an address: host:port")
        parser.add_argument("--hidden", help=argparse.SUPPRESS)
        return parser

    def run(self, args: argparse.Namespace, ctx: Context) -> Outcome:
        return Outcome()


@pytest.fixture
def commands(dummy: Command) -> list[Command]:
    return [*COMMANDS, dummy, TrickyCommand()]


def _script(shell: str, commands: Sequence[Command], capsys: pytest.CaptureFixture[str]) -> str:
    assert main(["completion", shell], commands=commands) == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    return captured.out


def _shown_options(parser: argparse.ArgumentParser) -> list[str]:
    return [
        flag
        for action in parser._actions
        if action.option_strings and action.help != argparse.SUPPRESS
        for flag in action.option_strings
    ]


def _fish_form(flag: str) -> str:
    return f"-l '{flag[2:]}'" if flag.startswith("--") else f"-s '{flag[1:]}'"


@pytest.mark.parametrize("shell", SHELLS)
def test_every_command_option_and_choice_appears(
    shell: str, commands: list[Command], capsys: pytest.CaptureFixture[str]
) -> None:
    script = _script(shell, commands, capsys)
    parser = build_parser(commands)
    (subparsers,) = (a for a in parser._actions if isinstance(a, argparse._SubParsersAction))
    form = _fish_form if shell == "fish" else str
    for flag in _shown_options(parser):
        assert form(flag) in script, (shell, flag)
    for name, sub in subparsers.choices.items():
        assert name in script
        for flag in _shown_options(sub):
            assert form(flag) in script, (shell, name, flag)
        for action in sub._actions:
            for choice in action.choices or ():
                if not isinstance(action, argparse._SubParsersAction):
                    assert str(choice) in script, (shell, name, choice)
    assert "hidden" not in script  # suppressed options stay hidden


@pytest.mark.parametrize("shell", SHELLS)
def test_the_script_is_generated_from_the_run_parser(
    shell: str, commands: list[Command], capsys: pytest.CaptureFixture[str]
) -> None:
    script = _script(shell, commands, capsys)
    assert script == generate(shell, build_parser(commands))
    assert "tricky" not in _script(shell, list(COMMANDS), capsys)


@pytest.mark.parametrize("shell", SHELLS)
def test_json_puts_the_script_in_the_result(
    shell: str, commands: list[Command], capsys: pytest.CaptureFixture[str]
) -> None:
    script = _script(shell, commands, capsys)
    assert main(["completion", shell, "--json"], commands=commands) == 0
    doc = json.loads(capsys.readouterr().out)
    assert doc["command"] == "completion"
    assert doc["result"] == {"shell": shell, "script": script}


def test_quiet_prints_nothing(commands: list[Command], capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["-q", "completion", "bash"], commands=commands) == 0
    assert capsys.readouterr().out == ""


def test_an_unknown_shell_is_a_usage_error(
    commands: list[Command], capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["--json", "completion", "tcsh"], commands=commands) == 2
    doc = json.loads(capsys.readouterr().out)
    assert doc["error"]["code"] == "usage.invalid-value"
    assert doc["result"] is None


class UnsafeChoice:
    """A command whose choice the shells would expand when completing it."""

    name = "unsafe"
    exit_codes = ()

    def register(self, subparsers: Subparsers) -> argparse.ArgumentParser:
        parser = subparsers.add_parser(self.name, help="has an unsafe choice")
        parser.add_argument("--pick", choices=["ok", "a$(touch PWNED)"])
        return parser

    def run(self, args: argparse.Namespace, ctx: Context) -> Outcome:
        return Outcome()


@pytest.mark.parametrize("shell", SHELLS)
def test_a_choice_with_shell_metacharacters_is_refused(
    shell: str, capsys: pytest.CaptureFixture[str]
) -> None:
    commands: list[Command] = [*COMMANDS, UnsafeChoice()]
    with pytest.raises(UnsafeWordError, match="cannot be completed safely"):
        generate(shell, build_parser(commands))
    assert main(["completion", shell], commands=commands) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "[internal.unexpected]" in captured.err


def test_zsh_specs_keep_their_fields(
    commands: list[Command], capsys: pytest.CaptureFixture[str]
) -> None:
    script = _script("zsh", commands, capsys)
    # A ':' in a metavar would start a new spec field, run as a command.
    assert "--addr='[an address: host:port]:host port: '" in script
    # "--opt=" completes the value after "=" and as the next word.
    assert "{-C,--project=}'[" in script
    assert "--level='[one of: low, high]:level:(low high)'" in script


def test_spec_reads_choices_and_value_kinds(commands: list[Command]) -> None:
    spec = spec_of(build_parser(commands))
    tricky = next(c for c in spec.commands if c.name == "tricky")
    options = {o.flags[0]: o for o in tricky.options}
    assert options["--out"].kind == "dir"
    assert options["--level"].choices == ("low", "high")
    assert options["-C"].kind == "dir"
    assert options["-v"].repeat and not options["-v"].takes_value
    assert "--hidden" not in options
    assert tricky.positionals[0].kind == "file"
    completion = next(c for c in spec.commands if c.name == "completion")
    assert completion.positionals[0].choices == SHELLS


# --- syntax ------------------------------------------------------------------


def _need(shell: str) -> None:
    """Skip when ``shell`` is missing, or fail when ``MMT_REQUIRE_SHELLS=1``
    (set in the CI job that installs zsh and fish)."""
    if shutil.which(shell) is None:
        if os.environ.get("MMT_REQUIRE_SHELLS") == "1":
            pytest.fail(f"{shell} is not installed, and MMT_REQUIRE_SHELLS=1 requires it")
        pytest.skip(f"{shell} is not installed")


def _check_syntax(shell: str, script: str, tmp_path: Path) -> None:
    path = tmp_path / f"script.{shell}"
    path.write_text(script)
    proc = subprocess.run([shell, "-n", str(path)], capture_output=True, text=True, check=False)
    assert proc.returncode == 0, proc.stderr
    assert proc.stderr == ""


@pytest.mark.parametrize("shell", SHELLS)
def test_the_script_parses(
    shell: str, commands: list[Command], capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    _need(shell)
    _check_syntax(shell, _script(shell, commands, capsys), tmp_path)


# --- loading never runs the tool ------------------------------------------------


@pytest.fixture
def trap(tmp_path: Path) -> tuple[dict[str, str], Path]:
    """An environment whose PATH starts with a fake ``mmt-plugin`` that leaves
    a marker when run, and the marker's path."""
    bindir = tmp_path / "bin"
    bindir.mkdir()
    marker = tmp_path / "ran"
    fake = bindir / "mmt-plugin"
    fake.write_text(f"#!/bin/sh\ntouch '{marker}'\n")
    fake.chmod(0o755)
    env = {**os.environ, "PATH": f"{bindir}{os.pathsep}{os.environ.get('PATH', '')}"}
    env["HOME"] = str(tmp_path)
    return env, marker


_BASH_DRIVER = r"""
source "$1"
complete -p mmt-plugin
t() {
    COMP_WORDS=("$@")
    COMP_CWORD=$(( ${#COMP_WORDS[@]} - 1 ))
    _mmt_plugin
    printf '%s|' "$*"
    printf '%s ' "${COMPREPLY[@]}"
    printf '\n'
}
t mmt-plugin ''
t mmt-plugin --js
t mmt-plugin completion ''
t mmt-plugin --json completion z
t mmt-plugin -C "$2/" ''
t mmt-plugin -C "$2/su"
t mmt-plugin --project = "$2/su"
t mmt-plugin --project = "$2" comp
t mmt-plugin completion --project = "$2" ''
t mmt-plugin tricky --level ''
t mmt-plugin tricky --le
t mmt-plugin dummy --mode ''
"""


def test_bash_loads_without_running_the_tool_and_completes(
    commands: list[Command],
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    trap: tuple[dict[str, str], Path],
) -> None:
    env, marker = trap
    script = tmp_path / "mmt-plugin.bash"
    script.write_text(_script("bash", commands, capsys))
    (tmp_path / "sub").mkdir()
    proc = subprocess.run(
        ["bash", "--norc", "--noprofile", "-c", _BASH_DRIVER, "_", str(script), str(tmp_path)],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert not marker.exists()
    lines = proc.stdout.splitlines()
    assert lines[0] == "complete -F _mmt_plugin mmt-plugin"
    got = dict(line.split("|", 1) for line in lines[1:])
    assert got["mmt-plugin "] == "generate completion dummy tricky "
    assert got["mmt-plugin --js"] == "--json "
    assert got["mmt-plugin completion "] == "bash zsh fish "
    assert got["mmt-plugin --json completion z"] == "zsh "
    assert got[f"mmt-plugin -C {tmp_path}/su"] == f"{tmp_path}/sub "
    # --project=DIR, which bash splits at '='.
    assert got[f"mmt-plugin --project = {tmp_path}/su"] == f"{tmp_path}/sub "
    assert got[f"mmt-plugin --project = {tmp_path} comp"] == "completion "
    assert got[f"mmt-plugin completion --project = {tmp_path} "] == "bash zsh fish "
    assert got["mmt-plugin tricky --level "] == "low high "
    assert got["mmt-plugin tricky --le"] == "--level "
    assert got["mmt-plugin dummy --mode "] == "a b "


def test_zsh_loads_without_running_the_tool_and_registers(
    commands: list[Command],
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    trap: tuple[dict[str, str], Path],
) -> None:
    _need("zsh")
    env, marker = trap
    fpath = tmp_path / "zfunc"
    fpath.mkdir()
    (fpath / "_mmt-plugin").write_text(_script("zsh", commands, capsys))
    driver = (
        f"fpath=({fpath} $fpath); autoload -Uz compinit; compinit -u -d {tmp_path}/dump; "
        'print -r -- "${_comps[mmt-plugin]}"; '
        f"source {fpath}/_mmt-plugin; "  # sourcing it after compinit also registers it
        'print -r -- "${_comps[mmt-plugin]}"'
    )
    proc = subprocess.run(
        ["zsh", "-f", "-c", driver], capture_output=True, text=True, env=env, check=False
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.splitlines() == ["_mmt-plugin", "_mmt-plugin"]
    assert not marker.exists()
    # Sourced without compinit, it defines the function and registers nothing.
    proc = subprocess.run(
        ["zsh", "-f", "-c", f"source {fpath}/_mmt-plugin; whence -w _mmt-plugin"],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == "_mmt-plugin: function"
    assert not marker.exists()


# Drives a real interactive zsh through zpty: types each line and a TAB, and
# records the words the completion system offers. The shell in the pty
# sources _ZSH_SETUP first.
# usage: zsh -f driver SETUP FPATH CWD HITS LINE...; prints "LINE|word ...".
_ZSH_DRIVER = r"""
zmodload zsh/zpty zsh/zselect || exit 3
setup=$1
export ZT_FPATH=$2 ZT_CWD=$3 ZT_HITS=$4
shift 4
zpty z zsh -f -i
zpty -w z "source ${(q)setup}"
for line in "$@"; do
  : >| $ZT_HITS
  zpty -w z 'comppostfuncs=(_zt_done)'
  zpty -w -n z "$line"$'\t'
  ok=0
  for i in {1..300}; do
    while zpty -r -t z junk; do :; done
    [[ "$(<$ZT_HITS)" == *'<DONE>'* ]] && { ok=1; break }
    zselect -t 5
  done
  (( ok )) || { print -r -- "$line|TIMEOUT"; continue }
  got=(${${(M)${(f)"$(<$ZT_HITS)"}:#<HIT>*}#<HIT>})
  print -r -- "$line|${(j: :)${(@ou)got}}"
  zpty -w -n z $'\C-u'
done
zpty -d z
"""

_ZSH_SETUP = r"""
PROMPT= RPROMPT=
fpath=($ZT_FPATH $fpath)
autoload -Uz compinit
compinit -u -d $HOME/zcompdump
cd $ZT_CWD
compadd() {
  # Record the offered words; compadd's own queries (-O, -A, -D) pass through.
  if [[ ${@[1,(i)(-|--)]} == *-(O|A|D)\ * ]]; then
    builtin compadd "$@"
    return
  fi
  local -a hits
  builtin compadd -A hits "$@"
  (( $#hits )) && print -rl -- "<HIT>"${^hits} >&2
  builtin compadd "$@"
}
_zt_done() { print -r -- "<DONE>" >&2 }
zstyle ':completion:*' menu no
zstyle ':completion:*' list-prompt ''
exec 2>>$ZT_HITS
"""


def test_zsh_completes_commands_options_and_values(
    commands: list[Command],
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    trap: tuple[dict[str, str], Path],
) -> None:
    _need("zsh")
    env, marker = trap
    fpath = tmp_path / "zfunc"
    fpath.mkdir()
    (fpath / "_mmt-plugin").write_text(_script("zsh", commands, capsys))
    work = tmp_path / "work"
    (work / "subdir").mkdir(parents=True)
    driver = tmp_path / "driver.zsh"
    driver.write_text(_ZSH_DRIVER)
    setup = tmp_path / "setup.zsh"
    setup.write_text(_ZSH_SETUP)
    expected = {
        "mmt-plugin ": "completion dummy generate tricky",
        "mmt-plugin --js": "--json",
        "mmt-plugin completion ": "bash fish zsh",
        "mmt-plugin tricky --le": "--level",
        "mmt-plugin tricky --level ": "high low",
        "mmt-plugin tricky --level=": "high low",
        "mmt-plugin -C su": "subdir",
        "mmt-plugin --project=su": "subdir",
    }
    proc = subprocess.run(
        [
            "zsh",
            "-f",
            str(driver),
            str(setup),
            str(fpath),
            str(work),
            str(tmp_path / "hits"),
            *expected,
        ],
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    got = dict(line.split("|", 1) for line in proc.stdout.splitlines())
    assert got == expected
    assert not marker.exists()


def test_fish_loads_without_running_the_tool(
    commands: list[Command],
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    trap: tuple[dict[str, str], Path],
) -> None:
    _need("fish")
    env, marker = trap
    script = tmp_path / "mmt-plugin.fish"
    script.write_text(_script("fish", commands, capsys))
    proc = subprocess.run(
        ["fish", "--no-config", "-c", f"source {script}; complete -C 'mmt-plugin completion '"],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert set(proc.stdout.split()) >= {"bash", "zsh", "fish"}
    assert not marker.exists()
