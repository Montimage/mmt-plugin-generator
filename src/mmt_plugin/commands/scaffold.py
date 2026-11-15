"""``mmt-plugin scaffold --from-pcap PCAP --parent SELECTOR`` (``docs/design/cli.md``,
sections 4, 5, 6, 8; plan task T4.1).

Slices the payloads of a capture under a parent into packet tests and
proposes a field skeleton (``mmt_plugin.pcap``). Stages, each stopping the
run with its class's exit code:

1. check ``--parent`` (the selector syntax of ``init --parent``, then a
   parent ``mmt_plugin.pcap.layers`` decodes and its keys; usage, exit 2);
2. read the project's model (``--model``, default ``<project>/plugin.yaml``)
   for the protocol's label and id; a model that does not parse is exit 3;
3. read the capture (pcap or pcapng) record by record, up to the record of
   the ``--max-packets``-th payload: one that is not a capture, or is
   broken before the payloads are found, is ``model.bad-pcap`` (exit 3);
   one with no payload under the parent is ``model.no-payloads`` (exit 3);
4. propose the skeleton from the first ``--max-packets`` payloads, render
   ``<project>/plugin.proposed.yaml`` and one packet test per payload,
   ``<tests-dir>/<label>-pcap-<n>.yaml``, and generate the proposal as
   ``build`` will (``make_generation``): a proposal that does not generate
   is exit 3, nothing written;
5. plan the writes: a file with the same content is ``unchanged``; one with
   other content, or a symbolic link, is ``state.output-differs`` (exit 7,
   nothing written) unless ``--force``; a directory, or a file where a
   directory goes, is exit 7 even with ``--force``. The model is never
   written (``usage.conflicting-options``), nor ``plugin.yaml``;
6. write each file atomically (``mmt_plugin.fsio``). Re-running on the same
   inputs is a no-op.

``--dry-run`` writes nothing and reports ``would-*`` actions.
"""

from __future__ import annotations

import argparse
import os
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mmt_plugin.commands import Context, Outcome, Subparsers
from mmt_plugin.commands.generate import make_generation
from mmt_plugin.commands.init import parse_selector
from mmt_plugin.commands.modelio import (
    FORMATS,
    PROJECT_FILE,
    absolute,
    parse_model,
    read_model,
    show_path,
)
from mmt_plugin.diagnostics import CliError, Diagnostic, Location, Severity
from mmt_plugin.exitcodes import ExitCode
from mmt_plugin.fsio import sha256_bytes, write_atomic
from mmt_plugin.pcap import (
    PARENTS,
    PcapError,
    packet_test,
    parent_of,
    propose,
    proposed_yaml,
    read_stream,
    slice_payloads,
)
from mmt_plugin.pdl import PdlSyntaxError
from mmt_plugin.sdk.profile import bundled_versions, get_bundled
from mmt_plugin.sdk.resolve import ProfileChoice, ProfileSource, sdk_context
from mmt_plugin.ui import style
from mmt_plugin.ui.streams import StreamStyle

__all__ = ["DEFAULT_MAX_PACKETS", "DIAGNOSTIC_CODES", "PROPOSED_FILE", "ScaffoldCommand"]

#: The codes this command reports itself (besides the model's).
DIAGNOSTIC_CODES = ("model.bad-pcap", "model.no-payloads", "state.output-differs")

#: The proposed model, next to plugin.yaml.
PROPOSED_FILE = "plugin.proposed.yaml"
DEFAULT_MAX_PACKETS = 20

_LEVELS = {
    "created": style.Level.OK,
    "unchanged": style.Level.OK,
    "updated": style.Level.WARN,
    "would-create": style.Level.SKIP,
    "would-update": style.Level.SKIP,
}
_WOULD = {"created": "would-create", "updated": "would-update"}
_ORDER = ("created", "updated", "unchanged", "would-create", "would-update")


def _plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def _positive(text: str) -> int:
    try:
        value = int(text, 10)
    except ValueError:
        raise argparse.ArgumentTypeError("must be an integer") from None
    if value < 1:
        raise argparse.ArgumentTypeError("must be >= 1")
    return value


def _choice() -> ProfileChoice:
    """The newest bundled profile: scaffold pins none, and the profile only
    checks that the proposal generates."""
    profile = get_bundled(bundled_versions()[-1])
    assert profile is not None  # the version comes from the bundle
    return ProfileChoice(profile, ProfileSource.DEFAULT)


@dataclass
class _Planned:
    path: Path
    shown: str
    action: str
    sha256: str
    data: bytes


class ScaffoldCommand:
    """``mmt-plugin scaffold --from-pcap PCAP --parent SELECTOR``."""

    name = "scaffold"
    exit_codes: tuple[ExitCode, ...] = (ExitCode.MODEL, ExitCode.STATE)

    def register(self, subparsers: Subparsers) -> argparse.ArgumentParser:
        parser = subparsers.add_parser(
            self.name,
            help="draft packet tests and a field skeleton from a pcap",
            description=(
                "Slice the payloads of a pcap or pcapng capture under --parent into packet\n"
                "tests (<tests-dir>/<label>-pcap-<n>.yaml) and propose a field skeleton,\n"
                "plugin.proposed.yaml, whose values the tests expect. plugin.yaml is never\n"
                "edited. Parents: " + ", ".join(PARENTS) + ". Re-running is a no-op;\n"
                "a file with other content is not replaced without --force."
            ),
            epilog=(
                "examples:\n"
                "  mmt-plugin scaffold --from-pcap capture.pcap --parent udp:port=4433\n"
                "  mmt-plugin -C demo scaffold --from-pcap demo.pcapng"
                " --parent ethernet:ethertype=0x88b5\n"
                "  mmt-plugin scaffold --from-pcap capture.pcap --parent tcp:dport=102"
                " --max-packets 5 --dry-run"
            ),
        )
        parser.add_argument(
            "--from-pcap",
            required=True,
            metavar="PCAP",
            help="the capture to slice, pcap or pcapng",
        )
        parser.add_argument(
            "--parent",
            required=True,
            metavar="SELECTOR",
            help="the parent whose payloads are the protocol, e.g. udp:port=4433 (keys:"
            " ethernet ethertype; ip, ipv6 proto; udp, tcp port, sport, dport)",
        )
        parser.add_argument(
            "--model",
            metavar="MODEL",
            help="the project's model, for the label and the id (default: <project>/plugin.yaml)",
        )
        parser.add_argument(
            "--model-format",
            choices=FORMATS,
            default="auto",
            help="the model format (default: auto: .yaml/.yml is YAML, anything else PDL)",
        )
        parser.add_argument(
            "--max-packets",
            type=_positive,
            default=DEFAULT_MAX_PACKETS,
            metavar="N",
            help=f"the payloads to slice, the first N (default: {DEFAULT_MAX_PACKETS})",
        )
        parser.add_argument(
            "--tests-dir",
            metavar="DIR",
            help="where to write the packet tests (default: <project>/tests/)",
        )
        parser.add_argument(
            "--dry-run", action="store_true", help="report every action, write nothing"
        )
        parser.add_argument(
            "--force", action="store_true", help="replace an output file that has other content"
        )
        return parser

    def run(self, args: argparse.Namespace, ctx: Context) -> Outcome:
        project = absolute(ctx.project)
        selector = parse_selector(args.parent)
        parent = parent_of(selector.text, selector.proto, selector.keys)
        choice = _choice()
        context = {"sdk": sdk_context(None, choice)}

        source = read_model(args.model, args.model_format, project)
        try:
            model = parse_model(source)
        except PdlSyntaxError as exc:
            errors = [d for d in exc.diagnostics if d.severity is Severity.ERROR]
            first = errors[0] if errors else exc.diagnostics[0]
            stop = CliError(
                first.code,
                f"{_plural(len(errors), 'error')} in {source.name}: nothing scaffolded",
                "fix the model (scaffold reads its label and id), then re-run scaffold",
            )
            return Outcome(diagnostics=exc.diagnostics, error=stop, context=context)
        label = model.properties.label.text
        pid = int(model.properties.id.value)

        pcap_path = absolute(args.from_pcap)
        pcap = show_path(pcap_path, project)
        # The capture is read record by record and only up to the record of
        # the --max-packets-th payload: never the whole file (#71).
        try:
            with pcap_path.open("rb") as stream:
                capture = read_stream(stream)
                slicing = slice_payloads(capture.frames(), parent, args.max_packets)
        except OSError as exc:
            raise CliError(
                "model.bad-pcap",
                f"cannot read {pcap}: {exc.strerror or exc}",
                "check the --from-pcap path and its permissions",
            ) from None
        except PcapError as exc:
            raise CliError(
                "model.bad-pcap",
                f"{pcap} is not a readable capture: {exc}",
                "pass a pcap or pcapng file (tcpdump -w, Wireshark, editcap -F pcap)",
            ) from None
        skipped = {k: v for k, v in slicing.skipped.items() if v}
        ctx.log(
            f"{capture.format}: {slicing.frames} frames read, {len(slicing.payloads)} payloads"
            f" under {parent.text}"
        )
        if not slicing.payloads:
            why = ", ".join(f"{v} {k}" for k, v in skipped.items()) or "no frame"
            raise CliError(
                "model.no-payloads",
                f"no payload under {parent.text} in {pcap} ({slicing.frames} frames: {why})",
                "check the --parent selector against the capture (tshark -r PCAP)",
            )
        skeleton = propose([p.data for p in slicing.payloads])

        proposed_path = project / PROPOSED_FILE
        proposed_shown = show_path(proposed_path, project)
        # The files name the capture by its file name only, so they do not
        # depend on where it is.
        tagged = any("8021q" in p.path for p in slicing.payloads)
        proposed = proposed_yaml(
            label, pid, parent, skeleton, pcap_path.name, len(slicing.payloads), tagged=tagged
        )
        generation, model_diagnostics, model_error = make_generation(
            proposed_shown, proposed.encode("utf-8"), choice, "yaml"
        )
        if generation is None:
            assert model_error is not None
            stop = CliError(
                model_error.code,
                f"the proposal for {label} (id {pid}) does not generate: nothing written",
                "fix the label or the id of the model, then re-run scaffold",
            )
            return Outcome(diagnostics=model_diagnostics, error=stop, context=context)

        tests_dir = absolute(args.tests_dir) if args.tests_dir is not None else project / "tests"
        width = max(3, len(str(len(slicing.payloads))))
        files: list[tuple[Path, bytes]] = [(proposed_path, proposed.encode("utf-8"))]
        for n, payload in enumerate(slicing.payloads, 1):
            stem = f"pcap-{n:0{width}d}"
            text = packet_test(
                label, pid, f"{label.lower()}/{stem}", payload, skeleton, pcap_path.name, parent
            )
            files.append((tests_dir / f"{label.lower()}-{stem}.yaml", text.encode("utf-8")))

        self._guard(files, source.name, args.model, project)
        planned, diagnostics = self._plan(files, args.force, project)
        refused = [d for d in diagnostics if d.severity is Severity.ERROR]
        error = None
        if refused:
            error = CliError(
                "state.output-differs",
                f"{_plural(len(refused), 'output file')} with other content: nothing written",
                "move them away, or re-run with --force to replace them",
            )
        if error is None and not args.dry_run:
            for p in planned:
                if p.action != "unchanged":
                    try:
                        # A link was refused above unless --force.
                        p.action = write_atomic(p.path, p.data, replace_link=True).action.value
                    except OSError as exc:
                        raise CliError(
                            "internal.io",
                            f"cannot write {p.shown}: {exc.strerror or exc}",
                            "check the directory and its permissions",
                        ) from None
        else:
            for p in planned:
                p.action = _WOULD.get(p.action, p.action)

        files_out = sorted(
            ({"path": p.shown, "action": p.action, "sha256": p.sha256} for p in planned),
            key=lambda f: f["path"],
        )
        result: dict[str, Any] = {
            "pcap": pcap,
            "format": capture.format,
            "parent": parent.text,
            "model": source.name,
            "protocol": {"label": label, "name": label.upper(), "id": pid},
            "packets": {
                "frames": slicing.frames,
                "payloads": len(slicing.payloads),
                "skipped": slicing.skipped,
            },
            "skeleton": skeleton.to_json(),
            "proposed": proposed_shown,
            "tests_dir": show_path(tests_dir, project),
            "files": files_out,
            "dry_run": bool(args.dry_run),
        }
        records = [(f["action"], f["path"]) for f in files_out]
        footer = [
            _plural(len(slicing.payloads), "payload"),
            _plural(len(skeleton.fields), "field"),
            f"header {skeleton.header_length} bytes",
        ]

        def view(st: StreamStyle) -> str:
            return _view(label, files_out, footer, st)

        return Outcome(
            result=result,
            records=records,
            view=view,
            diagnostics=[*model_diagnostics, *diagnostics],
            error=error,
            context=context,
        )

    @staticmethod
    def _guard(
        files: Sequence[tuple[Path, bytes]], model_name: str, given: str | None, project: Path
    ) -> None:
        """Refuse to write over the model (plugin.yaml, the default, is never
        one of the files: they are plugin.proposed.yaml and *-pcap-*.yaml)."""
        model = os.path.realpath(project / PROJECT_FILE if given is None else absolute(given))
        for path, _ in files:
            if given != "-" and os.path.realpath(path) == model:
                raise CliError(
                    "usage.conflicting-options",
                    f"scaffold would write {show_path(path, project)}, the model {model_name}:"
                    " scaffold never edits the model",
                    "pass another --tests-dir or -C, or move the model",
                )

    @staticmethod
    def _plan(
        files: Sequence[tuple[Path, bytes]], force: bool, project: Path
    ) -> tuple[list[_Planned], list[Diagnostic]]:
        planned: list[_Planned] = []
        diagnostics: list[Diagnostic] = []
        for path, data in files:
            shown = show_path(path, project)
            action, problem, always = "created", None, False
            blocked = next(
                (d for d in path.parents if os.path.lexists(d) and not d.is_dir()), None
            )
            if blocked is not None:
                problem = f"{show_path(blocked, project)} is not a directory"
                always = True
            elif path.is_symlink():
                action, problem = "updated", "is a symbolic link"
            elif path.is_dir():
                action, problem, always = "updated", "is a directory", True
            elif path.exists():
                try:
                    same = path.read_bytes() == data
                except OSError as exc:
                    raise CliError(
                        "internal.io",
                        f"cannot read {shown}: {exc.strerror or exc}",
                        "check its permissions",
                    ) from None
                action, problem = (
                    ("unchanged", None) if same else ("updated", "exists with other content")
                )
            if problem is not None:
                refused = always or not force
                diagnostics.append(
                    Diagnostic(
                        Severity.ERROR if refused else Severity.WARNING,
                        "state.output-differs",
                        f"{problem}: " + ("not replaced" if refused else "replaced (--force)"),
                        hint=(
                            "move it away"
                            if always
                            else "move it away, or re-run with --force to replace it"
                            if refused
                            else None
                        ),
                        location=Location(shown),
                    )
                )
            planned.append(_Planned(path, shown, action, sha256_bytes(data), data))
        return planned, diagnostics


def _view(
    label: str, files: Sequence[dict[str, str]], footer: Sequence[str], st: StreamStyle
) -> str:
    """The styled output: a box ``scaffold <label>`` with the files table."""
    rows = []
    counts: dict[str, int] = {}
    for entry in files:
        action = entry["action"]
        counts[action] = counts.get(action, 0) + 1
        shown = style.status(action, _LEVELS.get(action, style.Level.OK), style=st)
        rows.append([shown, entry["path"]])
    table = style.table(["action", "file"], rows, style=st, width=st.width - 4)
    separator = style.glyphs(st).separator
    parts = [*footer, *(f"{counts[a]} {a}" for a in _ORDER if a in counts)]
    return style.box(f"scaffold {label}", table, style=st, footer=separator.join(parts))
