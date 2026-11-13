"""A test-only ``dummy`` command, used to test option placement and the envelope.

Loaded by ``conftest.py`` for in-process tests; run as a script
(``python dummy_command.py ARGS``) for the subprocess tests. Its test-only
codes are registered only while a test uses them (``TEST_CODES``).
"""

from __future__ import annotations

import argparse
import sys
import time
from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType

from mmt_plugin import diagnostics
from mmt_plugin.commands import Context, Outcome, Subparsers
from mmt_plugin.diagnostics import CliError, Diagnostic, Location, Related, Severity

#: One test-only code per failure class that commands will use.
TEST_CODES: Mapping[str, str] = {
    f"{cls}.test-dummy": f"test-only {cls} code"
    for cls in ("model", "sdk", "build", "test", "state")
}


def codes_with_test_codes() -> Mapping[str, str]:
    """The registry plus ``TEST_CODES``."""
    return MappingProxyType({**diagnostics.CODES, **TEST_CODES})


class DummyCommand:
    """``mmt-plugin dummy [VALUE]``: echoes VALUE; flags make it fail in each way."""

    name = "dummy"

    def register(self, subparsers: Subparsers) -> argparse.ArgumentParser:
        parser = subparsers.add_parser(self.name, help="test-only command")
        parser.add_argument("value", nargs="?", default="hello")
        parser.add_argument("--fail", metavar="CODE", help="raise a CliError with CODE")
        parser.add_argument("--return-error", metavar="CODE", help="return it in the Outcome")
        parser.add_argument("--crash", action="store_true", help="raise RuntimeError")
        parser.add_argument("--oserror", action="store_true", help="raise PermissionError")
        parser.add_argument("--broken-pipe", action="store_true", help="raise BrokenPipeError")
        parser.add_argument("--bad-result", action="store_true", help="return a non-JSON result")
        parser.add_argument("--unregistered", action="store_true", help="use an unknown code")
        parser.add_argument("--warn", action="store_true", help="add a warning and a note")
        parser.add_argument("--log", action="store_true", help="log at -v and -vv")
        parser.add_argument("--sleep", metavar="MARKER", help="touch MARKER, then sleep")
        parser.add_argument("--records", type=int, default=0, help="extra output records")
        parser.add_argument("--mode", choices=["a", "b"])
        group = parser.add_mutually_exclusive_group()
        group.add_argument("--left", action="store_true")
        group.add_argument("--right", action="store_true")
        return parser

    def run(self, args: argparse.Namespace, ctx: Context) -> Outcome:
        if args.sleep:
            Path(args.sleep).touch()
            time.sleep(60)
        if args.log:
            ctx.log("stage one")
            ctx.log("debug detail", level=2)
        if args.crash:
            raise RuntimeError("boom")
        if args.oserror:
            raise PermissionError(13, "Permission denied", "/nonexistent/x")
        if args.broken_pipe:
            raise BrokenPipeError(32, "Broken pipe")
        if args.fail:
            raise CliError(args.fail, "dummy failure", "dummy hint")
        if args.unregistered:
            Diagnostic(Severity.ERROR, "model.never-registered", "unknown code")
        result: dict[str, object] = {
            "value": args.value,
            "project": ctx.project.as_posix(),
            "json": ctx.json,
            "quiet": ctx.quiet,
            "verbose": ctx.verbose,
            "no_color": ctx.no_color,
        }
        if args.bad_result:
            result["bad"] = object()
        diags: list[Diagnostic] = []
        if args.warn:
            diags.append(
                Diagnostic(
                    Severity.WARNING,
                    "model.test-dummy",
                    "a dummy warning",
                    hint="a dummy hint",
                    location=Location("plugin.yaml", 14, 9, 14, 12),
                    related=[Related("first defined here", Location("plugin.yaml", 9, 9))],
                )
            )
            diags.append(Diagnostic(Severity.NOTE, "model.test-dummy", "a dummy note"))
        records = [("value", args.value)] + [("n", str(i)) for i in range(args.records)]
        error = CliError(args.return_error, "returned failure") if args.return_error else None
        return Outcome(result=result, records=records, diagnostics=diags, error=error)


if __name__ == "__main__":
    import signal

    from mmt_plugin.cli import main

    # The subprocess tests send SIGINT: make sure it raises KeyboardInterrupt
    # even when the test runner started with SIGINT ignored.
    signal.signal(signal.SIGINT, signal.default_int_handler)
    diagnostics.CODES = codes_with_test_codes()
    sys.exit(main(sys.argv[1:], commands=[DummyCommand()]))
