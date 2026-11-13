"""The command registry.

A command is an object with a ``name``, a ``register(subparsers)`` method that
adds its parser and returns it, and a ``run(args, ctx)`` method that returns
an ``Outcome``. The CLI adds the global options to the returned parser,
dispatches to ``run``, and turns the ``Outcome`` into stdout, stderr, the
``--json`` envelope and the exit code. Commands never write to stdout, never
read from the terminal and never call ``sys.exit``; a failure is a
``CliError``, raised or returned in the ``Outcome``.

``COMMANDS`` lists the registered commands. It is empty: each command is added
by its own issue (``docs/design/cli.md``, section 2). Only implemented commands
are registered, so ``--help`` lists only what works.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol, TextIO

from mmt_plugin.diagnostics import CliError, Diagnostic
from mmt_plugin.exitcodes import ExitCode
from mmt_plugin.ui.render import escape
from mmt_plugin.ui.streams import StreamStyle

__all__ = ["COMMANDS", "Command", "Context", "Outcome", "Subparsers"]

if TYPE_CHECKING:
    #: What ``ArgumentParser.add_subparsers()`` returns.
    Subparsers = argparse._SubParsersAction[argparse.ArgumentParser]
else:
    Subparsers = argparse._SubParsersAction


@dataclass(frozen=True)
class Context:
    """The resolved global options and stream decisions, for one run.

    ``project`` is the ``-C`` directory as given (default ``.``); ``stderr``
    is where ``log`` writes ``-v`` messages.
    """

    project: Path
    json: bool
    quiet: bool
    verbose: int
    no_color: bool
    stdout_style: StreamStyle
    stderr_style: StreamStyle
    stderr: TextIO

    def log(self, message: str, *, level: int = 1) -> None:
        """Write a ``-v`` (level 1) or ``-vv`` (level 2) message to stderr."""
        if self.verbose >= level:
            print(f"mmt-plugin: {escape(message)}", file=self.stderr, flush=True)


@dataclass(frozen=True)
class Outcome:
    """What a command returns.

    - ``result``: the envelope's ``result`` (JSON-compatible, deterministic).
    - ``records``: the plain human output, one tuple of fields per line.
    - ``diagnostics``: errors, warnings and notes, in any order.
    - ``error``: the failure that sets the exit code, or ``None`` for success.
    - ``context``: keys added to the envelope's ``context`` (``sdk``, ...).
    """

    result: Any = None
    records: Sequence[Sequence[str]] = ()
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

    def register(self, subparsers: Subparsers) -> argparse.ArgumentParser:
        """Add this command's parser (``subparsers.add_parser(self.name, ...)``)."""
        ...

    def run(self, args: argparse.Namespace, ctx: Context) -> Outcome:
        """Run the command on the parsed arguments."""
        ...


#: The registered commands, in ``--help`` order.
COMMANDS: tuple[Command, ...] = ()
