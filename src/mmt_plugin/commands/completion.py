"""``mmt-plugin completion {bash,zsh,fish}`` (``docs/design/cli.md``, section 4).

The script is generated from the argparse tree of the run (``Context.parser``),
so it cannot drift from the parser: every command, every option that ``--help``
shows, and every choice. It is static: loading it only defines functions and
registers them, and completing never runs ``mmt-plugin``.

Values are completed from the parser too: an option or argument with
``choices`` completes them; a metavar or name that is a directory (``DIR``,
``PREFIX``, ``--project``) completes directories, a file (``FILE``, ``PATH``,
``MODEL``, ``PDL``, ``PCAP``, ``PACKETS``) completes files; any other value
completes nothing.
"""

from __future__ import annotations

import argparse
import re
import shlex
from collections.abc import Sequence
from dataclasses import dataclass

from mmt_plugin.commands import Context, Outcome, Subparsers
from mmt_plugin.exitcodes import ExitCode

__all__ = ["SHELLS", "CompletionCommand", "Spec", "UnsafeWordError", "generate", "spec_of"]

PROG = "mmt-plugin"
SHELLS = ("bash", "zsh", "fish")

_DIR_NAMES = frozenset({"DIR", "PREFIX", "PROJECT"})
_FILE_NAMES = frozenset({"FILE", "PATH", "MODEL", "PDL", "PCAP", "PACKETS", "OUTPUT"})

#: What a command name, an option flag or a choice may contain: the shells
#: expand completion words (bash ``compgen -W``, zsh ``(...)`` actions, fish
#: ``-a``), so a word with a shell metacharacter could run code when completed.
_SAFE_WORD = re.compile(r"-{0,2}[A-Za-z0-9][A-Za-z0-9_.+-]*")


class UnsafeWordError(ValueError):
    """A command name, flag or choice that the scripts cannot carry safely."""


def _checked(word: str) -> str:
    if not _SAFE_WORD.fullmatch(word):
        raise UnsafeWordError(
            f"{word!r} cannot be completed safely: use letters, digits, '_', '.', '+', '-'"
        )
    return word


@dataclass(frozen=True)
class Option:
    """An option as completion sees it."""

    flags: tuple[str, ...]
    help: str
    takes_value: bool
    value: str  # metavar, for zsh's message
    choices: tuple[str, ...]
    kind: str  # "dir", "file" or "none": what a value completes to
    repeat: bool


@dataclass(frozen=True)
class Positional:
    """A positional argument as completion sees it."""

    name: str
    help: str
    choices: tuple[str, ...]
    kind: str
    optional: bool
    many: bool


@dataclass(frozen=True)
class CommandSpec:
    """One command: its help line, options and positionals."""

    name: str
    help: str
    options: tuple[Option, ...]
    positionals: tuple[Positional, ...]


@dataclass(frozen=True)
class Spec:
    """The completion model of a parser: root options and commands."""

    options: tuple[Option, ...]
    commands: tuple[CommandSpec, ...]


def _help(parser: argparse.ArgumentParser, action: argparse.Action) -> str:
    formatter = parser._get_formatter()
    text = formatter._expand_help(action) if action.help else ""
    return " ".join(text.split())


def _kind(action: argparse.Action) -> str:
    names = {str(action.metavar or "").upper(), action.dest.upper()}
    names |= {s.lstrip("-").upper() for s in action.option_strings}
    if names & _DIR_NAMES:
        return "dir"
    if names & _FILE_NAMES:
        return "file"
    return "none"


def _choices(action: argparse.Action) -> tuple[str, ...]:
    return tuple(_checked(str(c)) for c in action.choices) if action.choices else ()


def _shown(action: argparse.Action) -> bool:
    return action.help != argparse.SUPPRESS


def _options(parser: argparse.ArgumentParser) -> tuple[Option, ...]:
    out = []
    for action in parser._actions:
        if not action.option_strings or not _shown(action):
            continue
        out.append(
            Option(
                flags=tuple(_checked(f) for f in action.option_strings),
                help=_help(parser, action),
                takes_value=action.nargs != 0,
                value=str(action.metavar or action.dest.upper()),
                choices=_choices(action),
                kind=_kind(action),
                repeat=isinstance(action, (argparse._CountAction, argparse._AppendAction)),
            )
        )
    return tuple(out)


def _positionals(parser: argparse.ArgumentParser) -> tuple[Positional, ...]:
    out = []
    for action in parser._actions:
        if action.option_strings or isinstance(action, argparse._SubParsersAction):
            continue
        if not _shown(action):
            continue
        out.append(
            Positional(
                name=str(action.metavar or action.dest),
                help=_help(parser, action),
                choices=_choices(action),
                kind=_kind(action),
                optional=action.nargs in ("?", "*"),
                many=action.nargs in ("*", "+", argparse.REMAINDER),
            )
        )
    return tuple(out)


def spec_of(parser: argparse.ArgumentParser) -> Spec:
    """The completion model of ``parser``: what ``--help`` shows, at each level."""
    commands = []
    for action in parser._actions:
        if not isinstance(action, argparse._SubParsersAction):
            continue
        helps = {c.dest: c.help or "" for c in action._choices_actions}
        for name, sub in action.choices.items():
            commands.append(
                CommandSpec(
                    name=_checked(name),
                    help=" ".join(helps.get(name, "").split()),
                    options=_options(sub),
                    positionals=_positionals(sub),
                )
            )
    return Spec(options=_options(parser), commands=tuple(commands))


# --- bash ------------------------------------------------------------------


def _bash_words(words: Sequence[str]) -> str:
    return shlex.quote(" ".join(words))


def _bash_pattern(flags: Sequence[str]) -> str:
    return "|".join(shlex.quote(f) for f in flags)


def _bash_value(kind: str, choices: Sequence[str]) -> str:
    if choices:
        return f"_mmt_plugin_words {_bash_words(choices)}"
    if kind == "dir":
        return "_mmt_plugin_dirs"
    if kind == "file":
        return "_mmt_plugin_files"
    return ":"


def _bash_level(options: Sequence[Option], words: Sequence[str], value: str) -> list[str]:
    """The body of one level: option values, then options or the words."""
    lines = ["            case $prev in"]
    for opt in options:
        if opt.takes_value:
            action = _bash_value(opt.kind, opt.choices)
            lines.append(f"                {_bash_pattern(opt.flags)}) {action}; return ;;")
    lines.append("            esac")
    flags = [f for opt in options for f in opt.flags]
    lines.append("            if [[ $cur == -* ]]; then")
    lines.append(f"                _mmt_plugin_words {_bash_words(flags)}")
    lines.append("            else")
    lines.append(f"                {value}")
    lines.append("            fi")
    lines.append("            ;;")
    return lines


def _bash(spec: Spec) -> str:
    valued = [f for opt in spec.options if opt.takes_value for f in opt.flags]
    lines = [
        f"# bash completion for {PROG}",
        f"# Generated by '{PROG} completion bash' from its argument parser.",
        f"# Install: {PROG} completion bash > ~/.local/share/bash-completion/completions/{PROG}",
        f"# Loading it defines the functions below and registers them; it never runs {PROG}.",
        "",
        "_mmt_plugin_words() {",
        '    mapfile -t COMPREPLY < <(compgen -W "$1" -- "$cur")',
        "}",
        "",
        "_mmt_plugin_dirs() {",
        "    compopt -o filenames 2>/dev/null",
        '    mapfile -t COMPREPLY < <(compgen -d -- "$cur")',
        "}",
        "",
        "_mmt_plugin_files() {",
        "    compopt -o filenames 2>/dev/null",
        '    mapfile -t COMPREPLY < <(compgen -f -- "$cur")',
        "}",
        "",
        "_mmt_plugin() {",
        "    local cur prev cmd word i",
        "    COMPREPLY=()",
        '    cur="${COMP_WORDS[COMP_CWORD]}"',
        '    prev=""',
        '    (( COMP_CWORD > 0 )) && prev="${COMP_WORDS[COMP_CWORD-1]}"',
        "    # COMP_WORDBREAKS splits --opt=value into --opt, =, value.",
        "    if [[ $cur == = ]]; then",
        '        cur=""',
        '        prev="${COMP_WORDS[COMP_CWORD-1]}"',
        "    elif [[ $prev == = ]] && (( COMP_CWORD > 1 )); then",
        '        prev="${COMP_WORDS[COMP_CWORD-2]}"',
        "    fi",
        '    cmd=""',
        "    for (( i = 1; i < COMP_CWORD; i++ )); do",
        '        word="${COMP_WORDS[i]}"',
        "        case $word in",
        "            --) break ;;",
    ]
    if valued:
        lines.append(
            f"            {_bash_pattern(valued)})"
            " (( i++ )); [[ ${COMP_WORDS[i]} == = ]] && (( i++ )) ;;"
        )
    lines += [
        "            -*) ;;",
        '            *) cmd="$word"; break ;;',
        "        esac",
        "    done",
        '    case "$cmd" in',
        "        '')",
    ]
    names = [c.name for c in spec.commands]
    lines += _bash_level(spec.options, names, f"_mmt_plugin_words {_bash_words(names)}")
    for command in spec.commands:
        lines.append(f"        {shlex.quote(command.name)})")
        first = command.positionals[0] if command.positionals else None
        value = ":" if first is None else _bash_value(first.kind, first.choices)
        lines += _bash_level(command.options, [], value)
    lines += [
        "    esac",
        "}",
        "",
        f"complete -F _mmt_plugin {PROG}",
    ]
    return "\n".join(lines) + "\n"


# --- zsh -------------------------------------------------------------------


def _zq(text: str) -> str:
    """``text`` inside zsh single quotes."""
    return text.replace("'", "'\\''")


def _zdesc(text: str) -> str:
    """A description inside ``[...]`` of an ``_arguments`` spec."""
    return _zq(text.replace("\\", "\\\\").replace("[", "\\[").replace("]", "\\]"))


def _zaction(kind: str, choices: Sequence[str]) -> str:
    if choices:
        return "(" + " ".join(_zq(c) for c in choices) + ")"
    if kind == "dir":
        return "_files -/"
    if kind == "file":
        return "_files"
    return " "


def _zsh_option(opt: Option) -> str:
    desc = f"[{_zdesc(opt.help)}]"
    value = ""
    flags = opt.flags
    if opt.takes_value:
        message = _zq(opt.value.lower().replace(":", " "))
        value = f":{message}:{_zaction(opt.kind, opt.choices)}"
        # "--opt=" takes the value after "=" or as the next word.
        flags = tuple(f + "=" if f.startswith("--") else f for f in flags)
    if opt.repeat:
        head = "'*'"
    elif opt.flags[0] in ("-h", "--help") or "--version" in opt.flags:
        head = "'(- *)'"
    elif len(opt.flags) > 1:
        head = "'(" + " ".join(opt.flags) + ")'"
    else:
        head = ""
    names = flags[0] if len(flags) == 1 else "{" + ",".join(flags) + "}"
    return f"{head}{names}'{desc}{value}'"


def _zsh_positional(index: int, pos: Positional) -> str:
    where = "*" if pos.many else str(index)
    optional = ":" if pos.optional and not pos.many else ""
    message = _zq(pos.name.replace(":", " "))
    return f"'{where}:{optional}{message}:{_zaction(pos.kind, pos.choices)}'"


def _zsh_arguments(
    indent: str, specs: Sequence[str], tail: str, *, flags: str = "-s"
) -> list[str]:
    lines = [f"{indent}_arguments {flags} \\"]
    lines += [f"{indent}  {s} \\" for s in specs]
    lines.append(f"{indent}  {tail}")
    return lines


def _zsh(spec: Spec) -> str:
    lines = [
        f"#compdef {PROG}",
        f"# zsh completion for {PROG}.",
        f"# Generated by '{PROG} completion zsh' from its argument parser.",
        f"# Install: {PROG} completion zsh > ~/.zfunc/_{PROG}",
        "# (with fpath=(~/.zfunc $fpath) before compinit in ~/.zshrc).",
        f"# Loading it defines _{PROG} and registers it; it never runs {PROG}.",
        "",
        f"_{PROG}() {{",
        '  local curcontext="$curcontext" state state_descr line ret=1',
        "  typeset -A opt_args",
    ]
    root = [_zsh_option(o) for o in spec.options]
    if spec.commands:
        lines += _zsh_arguments(
            "  ", [*root, "'1: :->command'"], "'*:: :->args' && ret=0", flags="-C -s"
        )
        lines += [
            "  case $state in",
            "    command)",
            "      local -a commands",
            "      commands=(",
        ]
        for command in spec.commands:
            name = command.name.replace(":", "\\:")
            lines.append(f"        '{_zq(name)}:{_zq(command.help)}'")
        lines += [
            "      )",
            f"      _describe -t commands '{PROG} command' commands && ret=0",
            "      ;;",
            "    args)",
            "      case $line[1] in",
        ]
        for command in spec.commands:
            specs = [_zsh_option(o) for o in command.options]
            specs += [_zsh_positional(i + 1, p) for i, p in enumerate(command.positionals)]
            lines.append(f"        {shlex.quote(command.name)})")
            if specs:
                lines += _zsh_arguments("          ", specs[:-1], specs[-1] + " && ret=0")
            lines.append("          ;;")
        lines += [
            "      esac",
            "      ;;",
            "  esac",
        ]
    elif root:
        lines += _zsh_arguments("  ", root[:-1], root[-1] + " && ret=0")
    lines += [
        "  return ret",
        "}",
        "",
        "if [[ ${zsh_eval_context[-1]} == loadautofunc ]]; then",
        f'  _{PROG} "$@"',
        "elif (( $+functions[compdef] )); then",
        f"  compdef _{PROG} {PROG}",
        "fi",
    ]
    return "\n".join(lines) + "\n"


# --- fish ------------------------------------------------------------------


def _fq(text: str) -> str:
    """``text`` in fish single quotes."""
    return "'" + text.replace("\\", "\\\\").replace("'", "\\'") + "'"


def _fish_option(condition: str, opt: Option) -> str:
    parts = [f"complete -c {PROG}", f"-n {_fq(condition)}"]
    for flag in opt.flags:
        if flag.startswith("--"):
            parts.append(f"-l {_fq(flag[2:])}")
        elif len(flag) == 2:
            parts.append(f"-s {_fq(flag[1:])}")
        else:
            parts.append(f"-o {_fq(flag[1:])}")
    if opt.takes_value:
        if opt.choices:
            parts.append(f"-x -a {_fq(' '.join(opt.choices))}")
        elif opt.kind == "dir":
            parts.append("-x -a '(__fish_complete_directories (commandline -ct))'")
        elif opt.kind == "file":
            parts.append("-r -F")
        else:
            parts.append("-x")
    if opt.help:
        parts.append(f"-d {_fq(opt.help)}")
    return " ".join(parts)


def _fish(spec: Spec) -> str:
    names = " ".join(c.name for c in spec.commands)
    no_command = f"not __fish_seen_subcommand_from {names}" if names else "true"
    lines = [
        f"# fish completion for {PROG}.",
        f"# Generated by '{PROG} completion fish' from its argument parser.",
        f"# Install: {PROG} completion fish > ~/.config/fish/completions/{PROG}.fish",
        f"# Loading it only registers completions; it never runs {PROG}.",
        "",
        f"complete -c {PROG} -f",
        "",
        "# before the command",
    ]
    lines += [_fish_option(no_command, o) for o in spec.options]
    for command in spec.commands:
        desc = f" -d {_fq(command.help)}" if command.help else ""
        lines.append(f"complete -c {PROG} -n {_fq(no_command)} -a {_fq(command.name)}{desc}")
    for command in spec.commands:
        seen = f"__fish_seen_subcommand_from {command.name}"
        lines += ["", f"# {command.name}"]
        lines += [_fish_option(seen, o) for o in command.options]
        for pos in command.positionals:
            if pos.choices:
                lines.append(f"complete -c {PROG} -n {_fq(seen)} -a {_fq(' '.join(pos.choices))}")
            elif pos.kind in ("dir", "file"):
                lines.append(f"complete -c {PROG} -n {_fq(seen)} -F")
    return "\n".join(lines) + "\n"


_GENERATORS = {"bash": _bash, "zsh": _zsh, "fish": _fish}


def generate(shell: str, parser: argparse.ArgumentParser) -> str:
    """The completion script for ``shell`` (one of ``SHELLS``), from ``parser``."""
    return _GENERATORS[shell](spec_of(parser))


class CompletionCommand:
    """``mmt-plugin completion SHELL``: print a completion script."""

    name = "completion"
    exit_codes: tuple[ExitCode, ...] = ()

    def register(self, subparsers: Subparsers) -> argparse.ArgumentParser:
        parser = subparsers.add_parser(
            self.name,
            help="print a shell completion script: bash, zsh or fish",
            description=(
                "Print a completion script for SHELL on stdout, generated from this\n"
                "parser. Loading it never runs mmt-plugin. With --json, the script is\n"
                "result.script."
            ),
            epilog=(
                "install:\n"
                f"  bash: {PROG} completion bash > "
                f"~/.local/share/bash-completion/completions/{PROG}\n"
                f"  zsh:  {PROG} completion zsh > ~/.zfunc/_{PROG}"
                "   (fpath=(~/.zfunc $fpath) before compinit)\n"
                f"  fish: {PROG} completion fish > ~/.config/fish/completions/{PROG}.fish"
            ),
        )
        parser.add_argument(
            "shell", choices=SHELLS, metavar="SHELL", help="the shell: bash, zsh or fish"
        )
        return parser

    def run(self, args: argparse.Namespace, ctx: Context) -> Outcome:
        script = generate(args.shell, ctx.parser)
        return Outcome(result={"shell": args.shell, "script": script}, text=script)
