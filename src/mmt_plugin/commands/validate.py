"""``mmt-plugin validate [MODEL]`` (``docs/design/cli.md``, sections 4, 5, 6, 10).

Checks a model without writing anything, and reports each check with a
stable id and a status (``pass``, ``warn``, ``fail``, ``skip``) and a detail:

- ``schema``: the model parses (PDL v1 syntax);
- ``semantics``: the semantic passes (``mmt_plugin.semantics``) find no
  error, apart from the SDK conflicts the next two checks report;
- ``sdk-profile``: the SDK and the profile are found (``--sdk``, ``MMT_BASE``,
  ``mmt-dpi.pc``, ``/opt/mmt``; ``--sdk-profile``, ``MMT_PLUGIN_SDK_PROFILE``);
- ``id-free``: no SDK protocol has the id, in the SDK headers (the profile)
  or at run time with the installed plugins (``mmt_plugin.sdk.registry``);
- ``name-free``: the same for the name, compared case-insensitively;
- ``parents-exist``: every parent protocol the model names is in the SDK;
- ``load-order``: ``mmtp_<label>.so`` sorts after ``libmmt_tcpip.so`` in the
  C locale and in the current ``LC_COLLATE``, as mmt-dpi's loader
  (``scandir`` with ``alphasort``) needs for the parents to be registered;
- ``id-range``: the id is in 950-999, the third-party range (a warning).

Without an SDK, the run exits 4 (``sdk.not-found``, decision D12) unless
``--no-sdk``: then ``id-free`` and ``name-free`` check the profile only and
report ``skip`` (or ``fail`` on a conflict the profile shows), and
``parents-exist`` is ``skip``. The exit code is the first failing check's
class (a taken id or name is 3); ``--strict`` also fails on the first
warning, with its code's class.
"""

from __future__ import annotations

import argparse
import locale
import os
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

from mmt_plugin.commands import Context, Outcome, Subparsers
from mmt_plugin.commands.modelio import FORMATS, absolute, decode_model, read_model
from mmt_plugin.diagnostics import CliError, Diagnostic, Location, Related, Severity
from mmt_plugin.exitcodes import ExitCode
from mmt_plugin.pdl import Model, PdlSyntaxError, parse
from mmt_plugin.sdk.detect import DEFAULT_PREFIX, Sdk, require_sdk
from mmt_plugin.sdk.profile import Profile
from mmt_plugin.sdk.registry import Registry, RegistryError, read_registry
from mmt_plugin.sdk.resolve import ENV_PROFILE, ProfileChoice, resolve_profile, sdk_context
from mmt_plugin.semantics import SDK_CONFLICT_CODES, THIRD_PARTY_IDS, analyse
from mmt_plugin.ui import style
from mmt_plugin.ui.streams import StreamStyle

__all__ = [
    "CHECKS",
    "DIAGNOSTIC_CODES",
    "TCPIP_PLUGIN",
    "Check",
    "ValidateCommand",
    "load_order",
    "parents_check",
    "parents_exist",
    "plugin_file",
]

#: The codes this command reports itself (besides the parser's, the
#: semantic passes' and the SDK's).
DIAGNOSTIC_CODES = ("model.unknown-parent", "model.load-order", "sdk.registry-unavailable")

#: The check ids, in the order they run and are reported.
CHECKS = (
    "schema",
    "semantics",
    "sdk-profile",
    "id-free",
    "name-free",
    "parents-exist",
    "load-order",
    "id-range",
)

#: The SDK plugin that registers the parents (TCP, UDP, ...).
TCPIP_PLUGIN = "libmmt_tcpip.so"

#: The styled view's name of each check.
_TITLES = {
    "schema": "schema",
    "semantics": "semantics",
    "sdk-profile": "sdk profile",
    "id-free": "id free",
    "name-free": "name free",
    "parents-exist": "parents exist",
    "load-order": "load order",
    "id-range": "reserved id range",
}
_LEVELS = {
    "pass": style.Level.OK,
    "warn": style.Level.WARN,
    "fail": style.Level.FAIL,
    "skip": style.Level.SKIP,
}

#: A reader of the run-time registry (tests replace it).
RegistryReader = Callable[..., Registry]
#: A collation: its name and its sort key.
Collation = tuple[str, Callable[[str], Any]]


@dataclass
class Check:
    """One reported check; ``error`` is set on the check that fails the run."""

    id: str
    status: str
    detail: str
    error: CliError | None = None

    def to_json(self) -> dict[str, str]:
        return {"id": self.id, "status": self.status, "detail": self.detail}


@dataclass
class _Run:
    """What the checks of one run share."""

    name: str
    checks: list[Check] = field(default_factory=list)
    diagnostics: list[Diagnostic] = field(default_factory=list)

    def add(self, check_id: str, status: str, detail: str, error: CliError | None = None) -> None:
        self.checks.append(Check(check_id, status, detail, error))

    def skip_rest(self, why: str) -> None:
        done = {c.id for c in self.checks}
        for check_id in CHECKS:
            if check_id not in done:
                self.add(check_id, "skip", why)


def _plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def plugin_file(label: str) -> str:
    """The plugin file of a label: ``mmtp_<label>.so``, lower case (plan
    decision 4; ``build`` writes it)."""
    return f"mmtp_{label.lower()}.so"


def _c_key(name: str) -> bytes:
    return name.encode("utf-8", "surrogateescape")


def collations() -> list[Collation]:
    """The C locale, then the environment's ``LC_COLLATE`` when it is another
    one that this system has; the process's locale is restored after."""
    found: list[Collation] = [("C", _c_key)]
    try:
        old = locale.setlocale(locale.LC_COLLATE)
    except locale.Error:  # pragma: no cover - querying never fails on Linux
        return found
    try:
        current = locale.setlocale(locale.LC_COLLATE, "")
    except locale.Error:
        return found
    try:
        if current not in ("C", "POSIX"):
            # The key sets the locale for each call: it must not depend on
            # the one restored below.
            found.append((current, _frozen_key(current)))
    finally:
        locale.setlocale(locale.LC_COLLATE, old)
    return found


def _frozen_key(name: str) -> Callable[[str], str]:
    def key(text: str) -> str:
        old = locale.setlocale(locale.LC_COLLATE)
        try:
            locale.setlocale(locale.LC_COLLATE, name)
            return locale.strxfrm(text)
        finally:
            locale.setlocale(locale.LC_COLLATE, old)

    return key


def load_order(file_name: str, orders: Sequence[Collation]) -> tuple[bool, str]:
    """Whether ``file_name`` sorts after ``libmmt_tcpip.so`` in every
    collation of ``orders``, and the detail to report."""
    before = [name for name, key in orders if not key(file_name) > key(TCPIP_PLUGIN)]
    names = " and ".join(name for name, _ in orders)
    if before:
        return False, f"{file_name} sorts before {TCPIP_PLUGIN} ({', '.join(before)})"
    return True, f"{file_name} after {TCPIP_PLUGIN} ({names})"


def parents_exist(
    parents: Sequence[str], profile: Profile, registry: Registry | None
) -> tuple[list[str], list[str]]:
    """The parents found and the parents missing, by label. A parent exists
    when the profile names it (``PROTO_<LABEL>``, its registered name) or,
    with a registry, when an installed plugin registers its name."""
    by_macro = {p.macro for p in profile.parents.protocols()}
    by_alias = {p.alias.casefold() for p in profile.parents.protocols() if p.alias}
    found: list[str] = []
    missing: list[str] = []
    for label in parents:
        known = profile.parents.id_for(label) in by_macro or label.casefold() in by_alias
        if not known and registry is not None:
            known = registry.by_name(label) is not None
        (found if known else missing).append(label)
    return found, missing


def parents_check(
    parents: Sequence[str],
    choice: ProfileChoice | None,
    registry: Registry | None,
    skipped: str | None,
) -> Check:
    """The ``parents-exist`` check of ``parents`` (labels): against the
    profile and the registry; ``skipped`` says why there is no registry
    (``None``: there is one, or it could not be read)."""
    if not parents:
        return Check("parents-exist", "skip", "the model declares no parent protocol (PDL v1)")
    if choice is None:
        return Check("parents-exist", "skip", "no SDK profile")
    found, missing = parents_exist(parents, choice.profile, registry)
    if missing:
        message = f"parent protocol {', '.join(missing)} is not in the SDK"
        if registry is None:
            message += f" profile {choice.profile.version}"
        error = CliError("model.unknown-parent", message, "use a protocol the SDK registers")
        return Check("parents-exist", "fail", message, error)
    if skipped is not None:
        return Check(
            "parents-exist",
            "skip",
            f"{skipped}: {', '.join(found)} in SDK {choice.profile.version}",
        )
    return Check("parents-exist", "pass", ", ".join(found))


class ValidateCommand:
    """``mmt-plugin validate [MODEL]``: check a model: schema, semantics, SDK,
    ids, load order.

    ``pkg_config_dirs`` and ``default_prefix`` are passed to SDK detection,
    ``registry_reader`` reads the run-time registry and ``orders`` gives the
    collations of the load-order check (tests replace all four)."""

    name = "validate"
    exit_codes: tuple[ExitCode, ...] = (ExitCode.MODEL, ExitCode.SDK)

    def __init__(
        self,
        *,
        pkg_config_dirs: Sequence[str] | None = None,
        default_prefix: str = DEFAULT_PREFIX,
        registry_reader: RegistryReader = read_registry,
        orders: Callable[[], Sequence[Collation]] = collations,
    ) -> None:
        self.pkg_config_dirs = pkg_config_dirs
        self.default_prefix = default_prefix
        self.registry_reader = registry_reader
        self.orders = orders

    def register(self, subparsers: Subparsers) -> argparse.ArgumentParser:
        parser = subparsers.add_parser(
            self.name,
            help="check a model: schema, semantics, SDK, ids, load order",
            description=(
                "Check MODEL and report each check (schema, semantics, sdk-profile,\n"
                "id-free, name-free, parents-exist, load-order, id-range) as pass, warn,\n"
                "fail or skip. The id and the name must be free in the SDK headers and\n"
                "among the protocols the installed plugins register at run time\n"
                "(names are compared case-insensitively). Without an SDK, validate\n"
                "exits 4 unless --no-sdk. Nothing is written."
            ),
            epilog=(
                "examples:\n"
                "  mmt-plugin validate plugins/tpkt_plugin --sdk $HOME/mmt/opt/mmt\n"
                "  mmt-plugin validate model.pdl --no-sdk --sdk-profile 1.10.2 --strict"
            ),
        )
        parser.add_argument(
            "model",
            nargs="?",
            metavar="MODEL",
            help=(
                "a PDL v1 model file, or - for stdin (default: <project>/plugin.yaml, which"
                " needs #24)"
            ),
        )
        parser.add_argument(
            "--model-format",
            choices=FORMATS,
            default="auto",
            help="the model format (default: auto: .yaml/.yml is YAML, anything else PDL)",
        )
        parser.add_argument(
            "--sdk",
            metavar="PREFIX",
            help="the mmt-dpi prefix to check the id, name and parents against (default:"
            " detected)",
        )
        parser.add_argument(
            "--sdk-profile",
            metavar="VERSION",
            help=(
                f"the SDK profile, e.g. 1.10.2 (default: {ENV_PROFILE}, else the detected"
                " SDK's, else the newest bundled one)"
            ),
        )
        parser.add_argument(
            "--no-sdk",
            action="store_true",
            help="skip the checks that need an installed SDK (reported as skip)",
        )
        parser.add_argument(
            "--strict", action="store_true", help="fail on warnings, with their class's code"
        )
        return parser

    # --- stages ---

    def _sdk(
        self, args: argparse.Namespace, ctx: Context
    ) -> tuple[Sdk | None, ProfileChoice | None, CliError | None]:
        """The SDK (``None`` with ``--no-sdk``), the profile, and the SDK or
        profile error. Without a usable SDK the profile is still chosen as if
        there were none, so the model can be checked, but its warning is
        dropped: the SDK error is what the run reports."""
        env = os.environ
        sdk = None
        sdk_error = None
        if not args.no_sdk:
            try:
                sdk = require_sdk(
                    args.sdk,
                    env,
                    pkg_config_dirs=self.pkg_config_dirs,
                    default_prefix=self.default_prefix,
                )
            except CliError as exc:
                sdk_error = exc
        try:
            choice = resolve_profile(args.sdk_profile, env, None, sdk)
        except CliError as exc:
            return sdk, None, sdk_error or exc
        if sdk_error is not None:
            choice = ProfileChoice(choice.profile, choice.source)
        ctx.log(f"SDK profile {choice.profile.version} ({choice.source.value})")
        return sdk, choice, sdk_error

    def run(self, args: argparse.Namespace, ctx: Context) -> Outcome:
        if args.no_sdk and args.sdk is not None:
            raise CliError(
                "usage.conflicting-options",
                "--no-sdk and --sdk cannot be used together",
                "drop --no-sdk to check against the SDK at --sdk, or drop --sdk",
            )
        project = absolute(ctx.project)
        model_input = read_model(args.model, args.model_format, project)
        name = model_input.name
        text = decode_model(model_input)
        sdk, choice, sdk_error = self._sdk(args, ctx)
        context = {"sdk": sdk_context(sdk, choice)}
        state = _Run(name)
        if choice is not None:
            state.diagnostics += choice.diagnostics

        # schema
        model: Model | None = None
        try:
            model = parse(text, filename=name)
        except PdlSyntaxError as exc:
            state.diagnostics += exc.diagnostics
            state.add("schema", "fail", f"{name}: PDL v1 syntax", _model_error(name, exc))
            state.skip_rest("the model does not parse")
        else:
            state.add("schema", "pass", f"{name}, PDL v1")

        if model is not None:
            self._model_checks(args, model, sdk, choice, sdk_error, state)

        protocol = None
        if model is not None:
            p = model.properties
            protocol = {"label": p.label.text, "name": p.label.text.upper(), "id": p.id.value}
        error = _run_error(state)
        warnings = [d for d in state.diagnostics if d.severity is Severity.WARNING]
        if error is None and args.strict and warnings:
            first = warnings[0]
            error = CliError(
                first.code,
                f"--strict: {_plural(len(warnings), 'warning')} ({first.code})",
                "fix the warnings, or run without --strict",
            )
        checks = [c.to_json() for c in state.checks]
        result = {
            "model": name,
            "format": model_input.format,
            "protocol": protocol,
            "checks": checks,
        }
        records = [(c["id"], c["status"], c["detail"]) for c in checks]
        label = name if protocol is None else str(protocol["label"]).lower()

        def view(st: StreamStyle) -> str:
            return _view(label, checks, st)

        return Outcome(
            result=result,
            records=records,
            view=view,
            diagnostics=state.diagnostics,
            error=error,
            context=context,
        )

    def _model_checks(
        self,
        args: argparse.Namespace,
        model: Model,
        sdk: Sdk | None,
        choice: ProfileChoice | None,
        sdk_error: CliError | None,
        state: _Run,
    ) -> None:
        """Every check after ``schema``."""
        props = model.properties
        label, pid = props.label.text, props.id.value

        # semantics, against the profile; the SDK conflicts are id-free's and
        # name-free's.
        conflicts: list[Diagnostic] = []
        if choice is None:
            state.add("semantics", "skip", "no SDK profile")
        else:
            analysed, found = analyse(model, profile=choice.profile, allow_sdk_conflicts=True)
            state.diagnostics += found
            conflicts = [d for d in found if d.code in SDK_CONFLICT_CODES]
            errors = [
                d
                for d in found
                if d.severity is Severity.ERROR and d.code not in SDK_CONFLICT_CODES
            ]
            if errors:
                first = errors[0]
                state.add(
                    "semantics",
                    "fail",
                    f"{_plural(len(errors), 'error')} ({first.code})",
                    CliError(
                        first.code,
                        f"{_plural(len(errors), 'error')} in {state.name}",
                        "fix the errors in the diagnostics, then re-run validate",
                    ),
                )
            else:
                assert analysed is not None  # no error but the SDK conflicts
                state.add(
                    "semantics",
                    "pass",
                    f"{_plural(len(analysed.attributes), 'attribute')},"
                    f" {_plural(len(analysed.structs), 'struct')}",
                )

        # sdk-profile
        if sdk_error is not None or choice is None:
            error = sdk_error
            assert error is not None
            state.add("sdk-profile", "fail", error.message, error)
        else:
            source = choice.source.value if sdk is None else _profile_source(sdk, choice)
            detail = f"{choice.profile.version} ({source})"
            if args.no_sdk:
                detail += ", --no-sdk"
            state.add("sdk-profile", "warn" if choice.diagnostics else "pass", detail)

        # The run-time registry, when there is an SDK.
        registry = None
        registry_problem = None
        if sdk is not None and sdk_error is None and choice is not None:
            max_id = _max_id(choice.profile)
            try:
                registry = self.registry_reader(
                    sdk, env=os.environ, max_id=max_id, exclude=plugin_file(label)
                )
            except RegistryError as exc:
                registry_problem = str(exc)
                state.diagnostics.append(
                    Diagnostic(
                        Severity.WARNING,
                        "sdk.registry-unavailable",
                        f"{exc}: the id and the name are checked against the SDK profile"
                        f" {choice.profile.version} only",
                        hint="check that the SDK's plugins load (init_extraction()), or run"
                        " with --no-sdk to skip the installed plugins",
                    )
                )
        why_skipped = (
            "--no-sdk" if args.no_sdk else "no SDK" if sdk_error is not None else "no SDK profile"
        )

        # id-free and name-free
        id_span = props.id.span.location()
        label_span = props.label.span.location()
        for check_id, code, shown in (
            ("id-free", "model.id-taken", str(pid)),
            ("name-free", "model.name-taken", label.upper()),
        ):
            from_profile = [d for d in conflicts if d.code == code]
            from_registry = None
            if registry is not None and not from_profile:
                hit = registry.by_id(pid) if code == "model.id-taken" else registry.by_name(label)
                if hit is not None:
                    where = id_span if code == "model.id-taken" else label_span
                    from_registry = _registry_conflict(
                        code, pid, label, hit.id, hit.name, registry
                    )
                    from_registry = _at(from_registry, where)
                    state.diagnostics.append(from_registry)
            taken = from_profile[0] if from_profile else from_registry
            if taken is not None:
                state.add(
                    check_id,
                    "fail",
                    taken.message,
                    CliError(
                        code,
                        taken.message,
                        "use a free id from 950 to 999"
                        if code == "model.id-taken"
                        else "choose another label",
                    ),
                )
            elif choice is None:
                state.add(check_id, "skip", why_skipped)
            elif registry is not None:
                state.add(
                    check_id,
                    "pass",
                    f"{shown}: not in SDK {choice.profile.version} or"
                    f" {_plural(len(registry.plugins), 'installed plugin')}",
                )
            elif registry_problem is not None:
                state.add(
                    check_id,
                    "warn",
                    f"{shown}: not in SDK {choice.profile.version}; installed plugins not read",
                )
            else:
                state.add(
                    check_id,
                    "skip",
                    f"{why_skipped}: {shown} not in SDK {choice.profile.version};"
                    " installed plugins not checked",
                )

        # parents-exist: PDL v1 declares no parent (plugin.yaml does, #24).
        skipped = None if registry is not None or registry_problem is not None else why_skipped
        check = parents_check((), choice, registry, skipped)
        state.add(check.id, check.status, check.detail, check.error)
        if check.error is not None:
            state.diagnostics.append(
                Diagnostic(Severity.ERROR, "model.unknown-parent", check.error.message)
            )

        # load-order
        file_name = plugin_file(label)
        ok, detail = load_order(file_name, self.orders())
        if ok:
            state.add("load-order", "pass", detail)
        else:
            message = (
                f"the plugin file {file_name} would load before {TCPIP_PLUGIN}: its parents"
                " would not be registered yet"
            )
            state.diagnostics.append(
                Diagnostic(
                    Severity.ERROR,
                    "model.load-order",
                    f"{detail}: {message}",
                    hint="choose a label whose plugin file sorts after libmmt_tcpip.so",
                    location=label_span,
                )
            )
            state.add(
                "load-order",
                "fail",
                detail,
                CliError("model.load-order", message, "choose another label"),
            )

        # id-range (a warning: model.id-outside-reserved-range, from semantics)
        low, high = THIRD_PARTY_IDS.start, THIRD_PARTY_IDS.stop - 1
        if pid in THIRD_PARTY_IDS:
            state.add("id-range", "pass", f"{pid} in {low}-{high}")
        else:
            state.add("id-range", "warn", f"{pid} outside {low}-{high}")


def _run_error(state: _Run) -> CliError | None:
    """The run's error: the first failing check's code. An SDK or profile
    error is reported as it is (no diagnostic carries it); any other failure
    as a summary of the error diagnostics, which carry the details."""
    failing = [c for c in state.checks if c.error is not None]
    if not failing:
        return None
    first = failing[0].error
    assert first is not None
    if failing[0].id == "sdk-profile":
        return first
    errors = sum(1 for d in state.diagnostics if d.severity is Severity.ERROR)
    return CliError(
        first.code,
        f"{_plural(errors, 'error')} in {state.name} ({', '.join(c.id for c in failing)} failed)",
        "fix the errors in the diagnostics, then re-run validate",
    )


def _profile_source(sdk: Sdk, choice: ProfileChoice) -> str:
    """Where the profile came from: the prefix's source when it is the SDK's
    own version (``MMT_BASE``), else the pin (``--sdk-profile``)."""
    if choice.source.value == "sdk":
        return sdk.source.value
    return choice.source.value


def _max_id(profile: Profile) -> int:
    try:
        value = profile.constant("PROTO_MAX_IDENTIFIER").value
    except KeyError:  # pragma: no cover - every bundled profile has it
        value = None
    return 1000 if value is None else value


def _at(d: Diagnostic, location: Location) -> Diagnostic:
    return Diagnostic(d.severity, d.code, d.message, d.hint, location, d.related)


def _registry_conflict(
    code: str, pid: int, label: str, hit_id: int, hit_name: str, registry: Registry
) -> Diagnostic:
    where = Related(
        f"registered at run time with the plugins of {registry.plugin_dir}:"
        f" {', '.join(registry.plugins) or 'none'}"
    )
    if code == "model.id-taken":
        message = f'protocol id {pid} is already registered at run time, by "{hit_name}"'
        hint = "use a free id from 950 to 999, the third-party range"
    else:
        message = (
            f"protocol name {label.upper()} is already registered at run time, by id {hit_id}"
            f' ("{hit_name}"; names are case-insensitive)'
        )
        hint = "choose another label: an installed plugin already registers this name"
    return Diagnostic(Severity.ERROR, code, message, hint=hint, related=[where])


def _model_error(name: str, exc: PdlSyntaxError) -> CliError:
    errors = [d for d in exc.diagnostics if d.severity is Severity.ERROR]
    first = errors[0] if errors else exc.diagnostics[0]
    return CliError(
        first.code,
        f"{_plural(len(errors), 'error')} in {name}",
        "fix the errors in the diagnostics, then re-run validate",
    )


def _view(label: str, checks: Sequence[dict[str, str]], st: StreamStyle) -> str:
    """The styled output: a box ``validate <label>`` with the checks table."""
    rows = [
        [
            _TITLES[c["id"]],
            style.status(c["status"], _LEVELS[c["status"]], style=st),
            c["detail"],
        ]
        for c in checks
    ]
    table = style.table(["check", "status", "detail"], rows, style=st, width=st.width - 4)
    counts = {s: sum(1 for c in checks if c["status"] == s) for s in _LEVELS}
    parts = [_plural(len(checks), "check"), f"{counts['pass']} pass"]
    if counts["warn"]:
        parts.append(_plural(counts["warn"], "warning"))
    if counts["fail"]:
        parts.append(f"{counts['fail']} failed")
    if counts["skip"]:
        parts.append(f"{counts['skip']} skipped")
    footer = style.glyphs(st).separator.join(parts)
    return style.box(f"validate {label}", table, style=st, footer=footer)
