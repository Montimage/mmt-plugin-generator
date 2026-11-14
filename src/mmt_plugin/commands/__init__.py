"""The command registry.

A command is an object with a ``name``, the ``exit_codes`` it can return
besides 0, 1, 2 and 130, a ``register(subparsers)`` method that adds its
parser and returns it, and a ``run(args, ctx)`` method that returns an
``Outcome``. Its ``result`` schema is ``mmt_plugin/schemas/cli/v1/<name>.json``
(``mmt_plugin.schemas``); the contract tests fail for a command without one.
The CLI adds the global options to the returned parser, dispatches to
``run``, and turns the ``Outcome`` into stdout, stderr, the ``--json``
envelope and the exit code. Commands never write to stdout, never
read from the terminal and never call ``sys.exit``; a failure is a
``CliError``, raised or returned in the ``Outcome``.

Human output: ``records`` are the plain records, printed when stdout is plain
(piped, ``TERM=dumb``) and by commands without a ``view``; ``view`` renders
the styled (btop) output with ``mmt_plugin.ui.style`` when stdout is styled;
``text`` is output the tool wrote itself and that must print as is, such as a
completion script. A new command only adds its ``view``: the CLI picks the
mode and applies it.

``COMMANDS`` lists the registered commands. Each command is added by its own
issue (``docs/design/cli.md``, section 2). Only implemented commands are
registered, so ``--help`` lists only what works.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol, TextIO

from mmt_plugin.diagnostics import CliError, Diagnostic
from mmt_plugin.exitcodes import ExitCode
from mmt_plugin.ui.render import escape
from mmt_plugin.ui.streams import StreamStyle
from mmt_plugin.ui.style import Progress

__all__ = ["COMMANDS", "Command", "Context", "Outcome", "Subparsers", "View"]

if TYPE_CHECKING:
    #: What ``ArgumentParser.add_subparsers()`` returns.
    Subparsers = argparse._SubParsersAction[argparse.ArgumentParser]
else:
    Subparsers = argparse._SubParsersAction


@dataclass(frozen=True)
class Context:
    """The resolved global options and stream decisions, for one run.

    ``project`` is the ``-C`` directory as given (default ``.``); ``stderr``
    is where ``log`` writes ``-v`` messages and ``progress`` its line;
    ``parser`` is the root parser of this run (``completion`` reads it).
    """

    project: Path
    json: bool
    quiet: bool
    verbose: int
    no_color: bool
    stdout_style: StreamStyle
    stderr_style: StreamStyle
    stderr: TextIO
    parser: argparse.ArgumentParser

    def progress(self, label: str, *, total: int | None = None) -> Progress:
        """A progress line on stderr, for an operation that may take more than
        2 seconds; it shows only on a terminal, never with ``--json`` or
        ``-q``. Use it as a context manager, so it is cleared before the
        result prints."""
        return Progress(
            self.stderr,
            self.stderr_style,
            label,
            total=total,
            enabled=not (self.json or self.quiet),
        )

    def log(self, message: str, *, level: int = 1) -> None:
        """Write a ``-v`` (level 1) or ``-vv`` (level 2) message to stderr."""
        if self.verbose >= level:
            print(f"mmt-plugin: {escape(message)}", file=self.stderr, flush=True)


#: A styled renderer: the stdout decision in, the text to print out.
View = Callable[[StreamStyle], str]


@dataclass(frozen=True)
class Outcome:
    """What a command returns.

    - ``result``: the envelope's ``result`` (JSON-compatible, deterministic).
    - ``records``: the plain human output, one tuple of fields per line.
    - ``view``: the styled human output, used instead of ``records`` when
      stdout is styled; ``None`` prints the records in every mode.
    - ``text``: human output printed as is in every mode, instead of
      ``records`` and ``view`` (text the tool wrote itself, never user text).
    - ``diagnostics``: errors, warnings and notes, in any order.
    - ``error``: the failure that sets the exit code, or ``None`` for success.
    - ``context``: keys added to the envelope's ``context`` (``sdk``, ...).
    """

    result: Any = None
    records: Sequence[Sequence[str]] = ()
    view: View | None = None
    text: str | None = None
    diagnostics: Sequence[Diagnostic] = ()
    error: CliError | None = None
    context: Mapping[str, Any] = field(default_factory=dict)

    @property
    def exit_code(self) -> ExitCode:
        """0, or the error's class code."""
        return ExitCode.SUCCESS if self.error is None else self.error.exit_code


class Command(Protocol):
    """One ``mmt-plugin`` command."""

    @property
    def name(self) -> str:
        """The command name, as typed on the command line and in ``command``."""
        ...

    @property
    def exit_codes(self) -> Sequence[ExitCode]:
        """The exit codes it can return besides 0, 1, 2 and 130 (``--help`` lists them)."""
        ...

    def register(self, subparsers: Subparsers) -> argparse.ArgumentParser:
        """Add this command's parser (``subparsers.add_parser(self.name, ...)``)."""
        ...

    def run(self, args: argparse.Namespace, ctx: Context) -> Outcome:
        """Run the command on the parsed arguments."""
        ...


# The commands use the types above, so they are imported after them.
from mmt_plugin.commands.completion import CompletionCommand  # noqa: E402
from mmt_plugin.commands.generate import GenerateCommand  # noqa: E402
from mmt_plugin.commands.validate import ValidateCommand  # noqa: E402

#: The registered commands, in ``--help`` order (``docs/design/cli.md``, section 2).
COMMANDS: tuple[Command, ...] = (ValidateCommand(), GenerateCommand(), CompletionCommand())
