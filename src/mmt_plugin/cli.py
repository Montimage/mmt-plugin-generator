"""The ``mmt-plugin`` command line (``docs/design/cli.md``).

``main`` parses the global options and the command (from
``mmt_plugin.commands``), runs it, and turns its ``Outcome`` into output and
an exit code (``mmt_plugin.exitcodes``):

- stdout carries only the result: plain records, the command's styled
  ``view`` when stdout is styled (``mmt_plugin.ui.style``), or with ``--json`` exactly
  one envelope (``mmt_plugin.envelope``), for every outcome, usage errors,
  ``--version``, internal errors and SIGINT included;
- stderr carries diagnostics in compiler style with a ``hint:`` (styled
  ``✗ error:`` and ``▲ warning:`` on a styled stderr), and the ``-v`` logs;
  with ``--json``, only the ``-v`` logs;
- a closed stdout ends the run quietly and keeps its exit code; any other
  failure to write stdout (a full disk, say) is exit 1 with one
  ``internal.io`` line on stderr; nothing is ever read from the terminal.

``--help`` and, without ``--json``, ``--version`` print and exit with
``SystemExit(0)``, as argparse does. Every other outcome returns its code.
"""

from __future__ import annotations

import argparse
import io
import os
import platform
import re
import sys
import traceback
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, NoReturn, TextIO, cast

from mmt_plugin import __version__, envelope
from mmt_plugin.commands import COMMANDS, Command, Context, Outcome, Subparsers
from mmt_plugin.diagnostics import CliError, Severity, sorted_diagnostics
from mmt_plugin.exitcodes import ExitCode
from mmt_plugin.sdk.profile import bundled_versions
from mmt_plugin.ui import render, style
from mmt_plugin.ui.streams import StreamStyle, decide

PROG = "mmt-plugin"

EXIT_OK = ExitCode.SUCCESS
EXIT_USAGE = ExitCode.USAGE

#: The metavar of the command positional, as argparse names it in errors.
COMMAND_METAVAR = "<command>"

#: The global options' destinations; ``_merge_globals`` folds in the copies
#: that each command's parser carries.
_GLOBALS = ("project", "json", "no_color", "quiet", "verbose")
_SUB = "global_after_command_"


#: The exit codes every command can return.
ALWAYS = (ExitCode.SUCCESS, ExitCode.INTERNAL, ExitCode.USAGE, ExitCode.INTERRUPTED)


def exit_codes_of(command: Command) -> tuple[ExitCode, ...]:
    """The exit codes ``command`` can return, in order: 0, 1, 2, 130 and its own."""
    return tuple(sorted({*ALWAYS, *command.exit_codes}))


def _codes_text(codes: Sequence[ExitCode]) -> str:
    return "exit codes:\n" + "\n".join(f"  {int(code):<4} {code.meaning}" for code in codes)


def _epilog() -> str:
    return (
        "Supported platform: Linux (amd64, arm64). The global options are accepted\n"
        "before or after the command. Nothing is ever prompted for.\n"
        f"Run '{PROG} <command> --help' for the options of a command.\n"
        "\n"
        f"{_codes_text(tuple(ExitCode))}"
    )


class UsageError(CliError):
    """A command-line error (exit 2), with the usage line of the parser that saw it."""

    def __init__(self, code: str, message: str, *, usage: str, hint: str | None) -> None:
        super().__init__(code, message, hint)
        self.usage = usage


def _classify(message: str) -> str:
    """Map an argparse error message to a registered ``usage.*`` code.

    Only the fixed forms argparse writes are matched, anchored on their
    start: a message is either ``argument NAME: TEXT`` (``NAME`` is an option
    or metavar of the parser, ``TEXT`` starts with argparse's own words) or
    one of the parser-level forms below. User text (a value, an unknown
    argument) only ever follows those words, so it cannot change the code.
    Any other form is ``usage.invalid``.
    """
    if message.startswith("unrecognized arguments: "):
        first = message[len("unrecognized arguments: ") :]
        return "usage.unknown-option" if first.startswith("-") else "usage.unexpected-argument"
    if message.startswith("the following arguments are required: "):
        return "usage.missing-argument"
    if message.startswith("one of the arguments ") and message.endswith(" is required"):
        return "usage.missing-argument"
    if not message.startswith("argument "):
        return "usage.invalid"
    name, sep, text = message[len("argument ") :].partition(": ")
    if not sep:
        return "usage.invalid"
    if text.startswith("invalid choice: "):
        return "usage.unknown-command" if name == COMMAND_METAVAR else "usage.invalid-value"
    if text.startswith("not allowed with argument "):
        return "usage.conflicting-options"
    if text.startswith("expected "):
        return "usage.missing-argument"
    if text.startswith("ignored explicit argument ") or re.match(r"invalid .+ value: ", text):
        return "usage.invalid-value"
    return "usage.invalid"


class _Parser(argparse.ArgumentParser):
    """No abbreviations, plain help, and errors raised as ``UsageError``."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs.setdefault("allow_abbrev", False)
        kwargs.setdefault("formatter_class", argparse.RawDescriptionHelpFormatter)
        if sys.version_info >= (3, 14):
            # Help is always plain text, whatever FORCE_COLOR says.
            kwargs["color"] = False
        super().__init__(*args, **kwargs)

    def error(self, message: str) -> NoReturn:
        raise UsageError(
            _classify(message),
            message,
            usage=self.format_usage(),
            hint=f"run '{self.prog} --help' for the usage",
        )


class _VersionRequested(Exception):
    """``--version`` was given; ``main`` prints it as text or as an envelope."""


class _VersionAction(argparse.Action):
    def __init__(self, option_strings: Sequence[str], dest: str, help: str | None = None) -> None:
        super().__init__(
            option_strings, dest=argparse.SUPPRESS, default=argparse.SUPPRESS, nargs=0, help=help
        )

    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: object,
        option_string: str | None = None,
    ) -> None:
        raise _VersionRequested


def _add_global_options(parser: argparse.ArgumentParser, *, after_command: bool) -> None:
    """Add the global options; a command's copies leave the values unset when absent."""
    prefix = _SUB if after_command else ""

    def default(value: object) -> object:
        return argparse.SUPPRESS if after_command else value

    group = parser.add_argument_group("global options")
    group.add_argument(
        "-C",
        "--project",
        metavar="DIR",
        dest=prefix + "project",
        default=default("."),
        help="the plugin project directory, which holds plugin.yaml (default: .)",
    )
    group.add_argument(
        "--json",
        action="store_true",
        dest=prefix + "json",
        default=default(False),
        help="print exactly one JSON envelope on stdout, and nothing else",
    )
    group.add_argument(
        "--no-color",
        action="store_true",
        dest=prefix + "no_color",
        default=default(False),
        help="no escape codes at all (same as NO_COLOR=1)",
    )
    group.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        dest=prefix + "quiet",
        default=default(False),
        help="print nothing on stdout, only errors on stderr (ignored with --json)",
    )
    group.add_argument(
        "-v",
        "--verbose",
        action="count",
        dest=prefix + "verbose",
        default=default(0),
        help="-v: log each stage on stderr; -vv: debug, with tracebacks on internal errors",
    )


def build_parser(commands: Sequence[Command] | None = None) -> argparse.ArgumentParser:
    """Return the argument parser for ``mmt-plugin`` and the given commands.

    ``commands`` defaults to the registry, ``mmt_plugin.commands.COMMANDS``.
    """
    parser = _Parser(
        prog=PROG,
        description="Generate, build and test mmt-dpi protocol plugins.",
        epilog=_epilog(),
    )
    parser.add_argument("--version", action=_VersionAction, help="print the version and exit")
    _add_global_options(parser, after_command=False)
    registered = COMMANDS if commands is None else commands
    subparsers = cast(
        "Subparsers",
        parser.add_subparsers(
            title="commands",
            dest="command",
            metavar=COMMAND_METAVAR,
            required=False,
            help=None if registered else "none yet: each command arrives in a later release",
        ),
    )
    for command in registered:
        sub = command.register(subparsers)
        _add_global_options(sub, after_command=True)
        codes = _codes_text(exit_codes_of(command))
        sub.epilog = f"{sub.epilog}\n\n{codes}" if sub.epilog else codes
        sub.set_defaults(_command=command)
    return parser


def _merge_globals(ns: argparse.Namespace) -> None:
    """Fold the global options given after the command into the ones given before."""
    for name in _GLOBALS:
        after = _SUB + name
        if not hasattr(ns, after):
            continue
        value = getattr(ns, after)
        delattr(ns, after)
        if name == "verbose":
            ns.verbose += value
        elif name == "project":
            ns.project = value
        else:
            setattr(ns, name, getattr(ns, name) or value)


def _command_parser(
    parser: argparse.ArgumentParser, ns: argparse.Namespace
) -> argparse.ArgumentParser:
    """The parser of the command in ``ns``, or ``parser`` when there is none."""
    name = getattr(ns, "command", None)
    if name is None:
        return parser
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            sub: argparse.ArgumentParser = action.choices[name]
            return sub
    return parser


def parse_args(
    argv: Sequence[str],
    commands: Sequence[Command] | None = None,
    *,
    parser: argparse.ArgumentParser | None = None,
) -> argparse.Namespace:
    """Parse ``argv``; raise ``UsageError`` on a bad command line or no command.

    The result has the global options (wherever they were given), ``command``
    (the name) and ``_command`` (the ``Command``), plus the command's own.
    ``parser`` is ``build_parser(commands)`` when not given.
    """
    if parser is None:
        parser = build_parser(commands)
    ns, extras = parser.parse_known_args(list(argv))
    if extras:
        # Report them against the command's parser (its usage, its --help).
        _command_parser(parser, ns).error(f"unrecognized arguments: {' '.join(extras)}")
    _merge_globals(ns)
    if getattr(ns, "_command", None) is None:
        raise UsageError(
            "usage.no-command",
            "no command given",
            usage=parser.format_usage(),
            hint=f"run '{PROG} --help' to list the commands",
        )
    return ns


def _has_flag(argv: Sequence[str], flag: str) -> bool:
    for arg in argv:
        if arg == "--":
            return False
        if arg == flag:
            return True
    return False


def _wants_json(argv: Sequence[str]) -> bool:
    """Whether ``--json`` appears before ``--``: decided before parsing, so that
    a usage error is still an envelope."""
    return _has_flag(argv, "--json")


def _project_path(project: str) -> str:
    """The project as reported in ``context.project``: relative to the current
    directory when inside it (POSIX separators), absolute otherwise."""
    cwd = Path.cwd()
    path = Path(os.path.normpath(cwd / project))
    try:
        return path.relative_to(cwd).as_posix()
    except ValueError:
        return path.as_posix()


@dataclass
class _Run:
    """What one run knows so far: enough to report any outcome."""

    json: bool
    out: TextIO
    err: TextIO
    out_style: StreamStyle
    err_style: StreamStyle
    command: str | None = None
    quiet: bool = False
    verbose: int = 0
    context: dict[str, Any] = field(default_factory=dict)


def _internal_error(run: _Run, exc: BaseException) -> CliError:
    if run.verbose >= 2:
        traceback.print_exception(type(exc), exc, exc.__traceback__, file=run.err)
    if isinstance(exc, OSError):
        return CliError(
            "internal.io",
            f"I/O error: {exc}",
            "check the path and its permissions; -vv shows the traceback",
        )
    return CliError(
        "internal.unexpected",
        f"unexpected error: {type(exc).__name__}: {exc}",
        "this is a bug in mmt-plugin: re-run with -vv for the traceback and report it",
    )


def _interrupted() -> CliError:
    return CliError("interrupted", "interrupted")


def _version_outcome() -> Outcome:
    return Outcome(
        result={
            "version": __version__,
            "python": platform.python_version(),
            "sdk_profiles": bundled_versions(),
        },
    )


def _dispatch(run: _Run, argv: Sequence[str], commands: Sequence[Command] | None) -> Outcome:
    parser = build_parser(commands)
    try:
        ns = parse_args(argv, parser=parser)
    except _VersionRequested:
        if run.json:
            return _version_outcome()
        try:
            run.out.write(f"{PROG} {__version__}\n")
        except BrokenPipeError:
            _silence(run.out)
        raise SystemExit(EXIT_OK) from None
    command: Command = ns._command
    run.command = command.name
    run.quiet = ns.quiet
    run.verbose = ns.verbose
    run.context = {"project": _project_path(ns.project), "sdk": None}
    run.out_style = decide(run.out, env=os.environ, no_color=ns.no_color, json=ns.json)
    run.err_style = decide(run.err, env=os.environ, no_color=ns.no_color)
    ctx = Context(
        project=Path(ns.project),
        json=ns.json,
        quiet=ns.quiet,
        verbose=ns.verbose,
        no_color=ns.no_color,
        stdout_style=run.out_style,
        stderr_style=run.err_style,
        stderr=run.err,
        parser=parser,
    )
    try:
        return command.run(ns, ctx)
    except CliError as exc:
        return Outcome(error=exc)


def _outcome(run: _Run, argv: Sequence[str], commands: Sequence[Command] | None) -> Outcome:
    try:
        return _dispatch(run, argv, commands)
    except CliError as exc:
        return Outcome(error=exc)
    except KeyboardInterrupt:
        return Outcome(error=_interrupted())
    except Exception as exc:
        # Commands never write to stdout, so a BrokenPipeError here is theirs
        # (a child's stdin, say): an I/O error, reported like any other.
        return Outcome(error=_internal_error(run, exc))


def _envelope_text(run: _Run, outcome: Outcome) -> tuple[str, int]:
    """The envelope and its exit code; an envelope that cannot be built is an
    internal error, reported as an envelope too."""
    try:
        doc = envelope.build(
            command=run.command,
            error=outcome.error,
            diagnostics=outcome.diagnostics,
            context={**run.context, **outcome.context},
            result=outcome.result,
        )
        return envelope.dumps(doc), doc["exit_code"]
    except Exception as exc:  # a result that is not JSON, for example
        doc = envelope.build(
            command=run.command, error=_internal_error(run, exc), context=run.context
        )
        return envelope.dumps(doc), doc["exit_code"]


def _human(run: _Run, outcome: Outcome) -> str:
    """The human stdout: the command's ``text`` as is; else its ``view`` when
    stdout is styled; else the plain records."""
    if outcome.text is not None:
        return outcome.text
    if outcome.view is not None and run.out_style.styled:
        text = outcome.view(run.out_style)
        return text if not text or text.endswith("\n") else text + "\n"
    return "".join(render.record(fields) for fields in outcome.records)


def _emit(run: _Run, outcome: Outcome) -> int:
    if run.json:
        text, code = _envelope_text(run, outcome)
        run.out.write(text)
        run.out.flush()
        return code
    if not run.quiet:
        try:
            text = _human(run, outcome)
        except Exception as exc:  # a view that fails is a bug, reported as one
            failure = _internal_error(run, exc)
            outcome = Outcome(diagnostics=outcome.diagnostics, error=failure)
            text = ""
        run.out.write(text)
    run.out.flush()
    for diagnostic in sorted_diagnostics(outcome.diagnostics):
        if run.quiet and diagnostic.severity is not Severity.ERROR:
            continue
        run.err.write(style.format_diagnostic(diagnostic, prog=PROG, style=run.err_style))
    error = outcome.error
    if error is not None:
        if isinstance(error, UsageError):
            run.err.write(error.usage)
        run.err.write(style.format_error(error, prog=PROG, style=run.err_style))
    run.err.flush()
    return int(outcome.exit_code)


def _silence(stream: TextIO) -> None:
    """Point a closed stdout at /dev/null, so the final flush cannot fail."""
    try:
        fd = stream.fileno()
    except (AttributeError, ValueError, OSError):
        return
    devnull = os.open(os.devnull, os.O_WRONLY)
    try:
        os.dup2(devnull, fd)
    finally:
        os.close(devnull)


def _flush(stream: TextIO) -> None:
    try:
        stream.flush()
    except BrokenPipeError:
        _silence(stream)


def _stdout() -> TextIO:
    """``sys.stdout``, ready for any text.

    A stdout closed at startup (``>&-``: Python then sets ``sys.stdout`` to
    None) becomes /dev/null, so the run ends quietly and keeps its exit code.
    A strict encoder (a UTF-8 locale and non-UTF-8 argv bytes, or
    ``PYTHONIOENCODING=ascii``) is switched to ``backslashreplace``, so a
    record that it cannot encode comes out escaped; the JSON envelope is
    ASCII and does not change.
    """
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")  # noqa: SIM115
    out = sys.stdout
    if isinstance(out, io.TextIOWrapper) and out.errors == "strict":
        out.reconfigure(errors="backslashreplace")
    return out


def _write_failed(run: _Run, exc: OSError) -> int:
    """stdout cannot be written: point it at /dev/null, so that the final
    flush at exit cannot fail again, and report one line on stderr."""
    _silence(run.out)
    if run.verbose >= 2:
        traceback.print_exception(type(exc), exc, exc.__traceback__, file=run.err)
    error = CliError("internal.io", f"cannot write to stdout: {exc.strerror or exc}")
    try:
        run.err.write(style.format_error(error, prog=PROG, style=run.err_style))
        run.err.flush()
    except OSError:
        pass
    return int(error.exit_code)


def main(argv: Sequence[str] | None = None, *, commands: Sequence[Command] | None = None) -> int:
    """Run ``mmt-plugin`` and return its exit code.

    ``commands`` replaces the registry (tests only).
    """
    args = sys.argv[1:] if argv is None else list(argv)
    wants_json = _wants_json(args)
    no_color = _has_flag(args, "--no-color")
    out, err = _stdout(), sys.stderr
    run = _Run(
        json=wants_json,
        out=out,
        err=err,
        # Decided again after parsing; these cover a usage error before it.
        out_style=decide(out, env=os.environ, no_color=no_color, json=wants_json),
        err_style=decide(err, env=os.environ, no_color=no_color),
    )
    code = int(ExitCode.INTERNAL)
    try:
        try:
            outcome = _outcome(run, args, commands)
        except SystemExit:
            _flush(run.out)
            raise
        code = int(outcome.exit_code)
        code = _emit(run, outcome)
    except BrokenPipeError:
        _silence(run.out)
    except OSError as exc:
        # Also when flushing --help or --version fails: exit 1, not 0.
        code = _write_failed(run, exc)
    except KeyboardInterrupt:
        code = int(ExitCode.INTERRUPTED)
    return code
