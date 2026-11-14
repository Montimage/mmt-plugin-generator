"""``mmt-plugin import PDL`` (``docs/design/cli.md``, sections 4, 5, 6, 8).

Converts a PDL v1 model to ``plugin.yaml`` (``mmt_plugin.pluginyaml.convert``),
which ``generate`` reads into the same model, so both formats generate the
same C. Stages, each stopping the run with its class's exit code:

1. read ``PDL`` (``-`` is stdin, named ``<stdin>``) and parse it (exit 3 on
   a syntax error, nothing written);
2. analyse it against the newest bundled SDK profile and convert it: an SDK
   id or name conflict and the other constructs that relied on Java bugs are
   ``model.legacy-*`` warnings; any other model error is exit 3, nothing
   written. ``--strict`` fails on any warning (exit 3);
3. write the output, ``-o FILE`` (default ``<project>/plugin.yaml``): the
   same content is ``unchanged`` and not rewritten; other content, or a
   symbolic link, is ``state.output-differs`` (exit 7, nothing written)
   unless ``--force``, and a directory is exit 7 even with ``--force``. The
   file is written atomically (``mmt_plugin.fsio``). ``-o -`` prints the
   YAML on stdout instead, and is a usage error with ``--json``, whose
   envelope stdout carries.

``--dry-run`` writes nothing and reports ``would-*`` actions.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from mmt_plugin.commands import Context, Outcome, Subparsers
from mmt_plugin.commands.modelio import (
    PROJECT_FILE,
    absolute,
    decode_model,
    read_model,
    show_path,
)
from mmt_plugin.diagnostics import CliError, Diagnostic, Location, Severity
from mmt_plugin.exitcodes import ExitCode
from mmt_plugin.fsio import sha256_bytes, write_atomic
from mmt_plugin.pdl import PdlSyntaxError, parse
from mmt_plugin.pluginyaml.convert import LEGACY_CODES, convert
from mmt_plugin.sdk.profile import bundled_versions, get_bundled
from mmt_plugin.sdk.resolve import ProfileChoice, ProfileSource, sdk_context
from mmt_plugin.ui import style
from mmt_plugin.ui.streams import StreamStyle

__all__ = ["DIAGNOSTIC_CODES", "ImportCommand"]

#: The codes this command reports itself (besides the parser's and the
#: semantic passes').
DIAGNOSTIC_CODES = (*LEGACY_CODES, "model.unreadable", "state.output-differs")

STDOUT = "-"

_LEVELS = {
    "created": style.Level.OK,
    "unchanged": style.Level.OK,
    "updated": style.Level.WARN,
    "would-create": style.Level.SKIP,
    "would-update": style.Level.SKIP,
}
_WOULD = {"created": "would-create", "updated": "would-update"}


def _plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def _choice() -> ProfileChoice:
    """The newest bundled profile: import pins none, and the profile only
    checks the model's types and its SDK conflicts."""
    profile = get_bundled(bundled_versions()[-1])
    assert profile is not None  # the version comes from the bundle
    return ProfileChoice(profile, ProfileSource.DEFAULT)


def _model_error(name: str, diagnostics: Sequence[Diagnostic]) -> CliError:
    errors = [d for d in diagnostics if d.severity is Severity.ERROR]
    first = errors[0] if errors else diagnostics[0]
    return CliError(
        first.code,
        f"{_plural(len(errors), 'error')} in {name}: nothing imported",
        "fix the errors in the diagnostics, then re-run import",
    )


class ImportCommand:
    """``mmt-plugin import PDL``: convert a PDL v1 model to plugin.yaml."""

    name = "import"
    exit_codes: tuple[ExitCode, ...] = (ExitCode.MODEL, ExitCode.STATE)

    def register(self, subparsers: Subparsers) -> argparse.ArgumentParser:
        parser = subparsers.add_parser(
            self.name,
            help="convert a PDL v1 model to plugin.yaml",
            description=(
                "Convert the PDL v1 model PDL to plugin.yaml, which generates the same C.\n"
                "Constructs whose meaning relied on a bug of the Java tool are warnings\n"
                "(model.legacy-*). The same output is a no-op; a file with other content\n"
                "is not replaced without --force."
            ),
            epilog=(
                "examples:\n"
                "  mmt-plugin import plugins/tpkt_plugin -o tpkt/plugin.yaml\n"
                "  mmt-plugin -C demo import demo/model.pdl   # writes demo/plugin.yaml\n"
                "  mmt-plugin import model.pdl -o -          # prints the YAML"
            ),
        )
        parser.add_argument("pdl", metavar="PDL", help="a PDL v1 model file, or - for stdin")
        parser.add_argument(
            "-o",
            "--output",
            metavar="FILE",
            help="the plugin.yaml to write, or - for stdout (default: <project>/plugin.yaml)",
        )
        parser.add_argument(
            "--dry-run", action="store_true", help="report every action, write nothing"
        )
        parser.add_argument(
            "--force", action="store_true", help="replace an output file that has other content"
        )
        parser.add_argument(
            "--strict", action="store_true", help="fail on warnings, with their class's code"
        )
        return parser

    def run(self, args: argparse.Namespace, ctx: Context) -> Outcome:
        if args.output == STDOUT and ctx.json:
            raise CliError(
                "usage.conflicting-options",
                "-o - writes plugin.yaml to stdout, where --json prints its envelope",
                "pass -o FILE, or drop --json",
            )
        project = absolute(ctx.project)
        source = read_model(args.pdl, "pdl", project)
        name = source.name
        choice = _choice()
        context = {"sdk": sdk_context(None, choice)}
        try:
            model = parse(decode_model(source), filename=name)
        except PdlSyntaxError as exc:
            return Outcome(
                diagnostics=exc.diagnostics,
                error=_model_error(name, exc.diagnostics),
                context=context,
            )
        conversion = convert(model, choice.profile)
        diagnostics = list(conversion.diagnostics)
        if conversion.text is None:
            return Outcome(
                diagnostics=diagnostics, error=_model_error(name, diagnostics), context=context
            )
        warnings = [d for d in diagnostics if d.severity is Severity.WARNING]
        if args.strict and warnings:
            first = warnings[0]
            strict = CliError(
                first.code,
                f"--strict: {_plural(len(warnings), 'warning')} ({first.code})",
                "fix the warnings, or run without --strict",
            )
            return Outcome(diagnostics=diagnostics, error=strict, context=context)

        data = conversion.text.encode("utf-8")
        sha = sha256_bytes(data)
        label = model.properties.label.text
        result: dict[str, Any] = {
            "input": name,
            "output": STDOUT,
            "model_hash": sha256_bytes(source.data),
            "protocol": {"label": label, "id": model.properties.id.value},
            "offsets": conversion.offsets.value,
            "files": [],
            "dry_run": bool(args.dry_run),
        }
        if args.output == STDOUT:
            return Outcome(
                result=result, text=conversion.text, diagnostics=diagnostics, context=context
            )

        path = project / PROJECT_FILE if args.output is None else absolute(args.output)
        shown = show_path(path, project)
        action, problem = self._plan(path, data, shown)
        error = None
        if problem is not None:
            refused = not args.force or problem == "is a directory"
            diagnostics.append(
                Diagnostic(
                    Severity.ERROR if refused else Severity.WARNING,
                    "state.output-differs",
                    f"{problem}: " + ("not replaced" if refused else "replaced (--force)"),
                    hint=(
                        "move it away"
                        if problem == "is a directory"
                        else "move it away, or re-run with --force to replace it"
                        if refused
                        else None
                    ),
                    location=Location(shown),
                )
            )
            if refused:
                error = CliError(
                    "state.output-differs",
                    f"{shown} {problem}: nothing written",
                    "move it away, or pass another -o FILE"
                    if problem == "is a directory"
                    else "move it away, or re-run with --force to replace it",
                )
        if error is None and not args.dry_run and action != "unchanged":
            try:
                action = write_atomic(path, data).action.value
            except OSError as exc:
                raise CliError(
                    "internal.io",
                    f"cannot write {shown}: {exc.strerror or exc}",
                    "check the -o path and its permissions",
                ) from None
        else:
            action = _WOULD.get(action, action)
        result["output"] = shown
        result["files"] = [{"path": shown, "action": action, "sha256": sha}]
        offsets = conversion.offsets.value

        def view(st: StreamStyle) -> str:
            return _view(label, shown, action, offsets, st)

        return Outcome(
            result=result,
            records=[(action, shown)],
            view=view,
            diagnostics=diagnostics,
            error=error,
            context=context,
        )

    @staticmethod
    def _plan(path: Path, data: bytes, shown: str) -> tuple[str, str | None]:
        """The action writing ``data`` to ``path`` takes, and why it needs
        ``--force`` (``None`` when it does not)."""
        if path.is_symlink():
            return "updated", "is a symbolic link"
        if path.is_dir():
            return "updated", "is a directory"
        if not path.exists():
            return "created", None
        try:
            same = path.read_bytes() == data
        except OSError as exc:
            raise CliError(
                "internal.io",
                f"cannot read {shown}: {exc.strerror or exc}",
                "check its permissions",
            ) from None
        return ("unchanged", None) if same else ("updated", "exists with other content")


def _view(label: str, path: str, action: str, offsets: str, st: StreamStyle) -> str:
    """The styled output: a box ``import <label>`` with the file written."""
    shown = style.status(action, _LEVELS.get(action, style.Level.OK), style=st)
    table = style.table(["action", "file"], [[shown, path]], style=st, width=st.width - 4)
    separator = style.glyphs(st).separator
    footer = separator.join([f"offsets {offsets}", action])
    return style.box(f"import {label}", table, style=st, footer=footer)
