"""``mmt-plugin doctor`` (``docs/design/cli.md``, sections 4, 5, 6 and 10).

Reports the environment a plugin is built, installed and loaded in, inside
or outside a project, as checks with a stable ``id``, each ``pass``,
``warn``, ``fail`` or ``skip``, in this order:

- toolchain: ``python``, ``compiler`` (``--cc`` > ``CC`` > ``gcc``, as
  ``build``);
- SDK: ``sdk`` (prefix, where it came from, version, ``libmmt_core``),
  ``sdk-profile``;
- plugin directories: ``plugin-dir``, the one directory mmt-dpi 1.10.2 scans
  (``MMT_DPI_PLUGINS_DIR``, else the one compiled into ``libmmt_core``;
  ``mmt_plugin.sdk.registry.scanned_plugin_dir``), and ``install-dir``,
  ``<prefix>/plugins`` of the install prefix (``--prefix``/``--system``, as
  ``install``): whether mmt-dpi scans it, and how to make it do so;
- load order and clashes: ``load-order`` (every installed plugin sorts after
  ``libmmt_tcpip.so``), ``registry`` (``init_extraction()`` loads the scanned
  directory, ``mmt_plugin.sdk.registry``), ``project`` (the project's model,
  ``--model`` or ``<project>/plugin.yaml``) and ``clashes`` (no two installed
  plugins, from their install manifests, nor one of them and the project's
  model, register the same id or name).

Exit 0 when no check fails (warnings allowed), 4 otherwise, with the first
failing check's code. Nothing is written.
"""

from __future__ import annotations

import argparse
import os
import platform
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from mmt_plugin.commands import Context, Outcome, Subparsers
from mmt_plugin.commands.build import find_compiler
from mmt_plugin.commands.generate import make_generation
from mmt_plugin.commands.modelio import PROJECT_FILE, absolute, read_model, show_path
from mmt_plugin.commands.validate import TCPIP_PLUGIN, Check, collations, load_order
from mmt_plugin.diagnostics import CliError, Diagnostic, Severity
from mmt_plugin.exitcodes import ExitCode
from mmt_plugin.manifest import (
    ENV_PREFIX,
    InstallPrefix,
    manifest_path,
    read_manifests,
    resolve_prefix,
    writable,
)
from mmt_plugin.sdk.detect import DEFAULT_PREFIX, Sdk, require_sdk
from mmt_plugin.sdk.profile import Profile
from mmt_plugin.sdk.registry import (
    PLUGINS_DIR_ENV,
    RegistryError,
    core_library,
    read_registry,
    scanned_plugin_dir,
)
from mmt_plugin.sdk.resolve import ProfileChoice, resolve_profile, sdk_context
from mmt_plugin.ui import style
from mmt_plugin.ui.streams import StreamStyle

__all__ = ["CHECKS", "DoctorCommand"]

#: The checks, in run order, by section (the styled view's four sections).
SECTIONS: tuple[tuple[str, ...], ...] = (
    ("python", "compiler"),
    ("sdk", "sdk-profile"),
    ("plugin-dir", "install-dir"),
    ("load-order", "registry", "project", "clashes"),
)
CHECKS = tuple(c for section in SECTIONS for c in section)
_BORDERS = (
    style.Role.BORDER,
    style.Role.BORDER_MEM,
    style.Role.BORDER_NET,
    style.Role.BORDER_PROC,
)
_TITLES = {c: c.replace("-", " ") for c in CHECKS}
_LEVELS = {
    "pass": style.Level.OK,
    "warn": style.Level.WARN,
    "fail": style.Level.FAIL,
    "skip": style.Level.SKIP,
}


def _plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


@dataclass
class _Run:
    checks: list[Check] = field(default_factory=list)
    diagnostics: list[Diagnostic] = field(default_factory=list)

    def add(self, check_id: str, status: str, detail: str, error: CliError | None = None) -> None:
        self.checks.append(Check(check_id, status, detail, error))

    def warn(self, code: str, message: str, hint: str | None = None) -> None:
        self.diagnostics.append(Diagnostic(Severity.WARNING, code, message, hint=hint))


def _max_id(profile: Profile) -> int:
    try:
        value = profile.constant("PROTO_MAX_IDENTIFIER").value
    except KeyError:  # pragma: no cover - every bundled profile has it
        value = None
    return 1000 if value is None else value


def _plugin_names(directory: str) -> list[str]:
    """The ``*.so`` files of a directory, in mmt-dpi's load order (C bytes)."""
    try:
        names = [n for n in os.listdir(directory) if n.endswith(".so")]
    except OSError:
        return []
    return sorted(names, key=lambda n: n.encode("utf-8", "surrogateescape"))


def _is_sdk_plugin(name: str) -> bool:
    # The SDK's own plugins: libmmt_tcpip.so, libmmt_tmobile.so, ...
    return name.startswith("libmmt_")


class DoctorCommand:
    """``mmt-plugin doctor``: report the toolchain, the SDK, the plugin
    directories, the load order and the id/name clashes.

    ``pkg_config_dirs`` and ``default_prefix`` are passed to SDK detection,
    ``system_prefix`` is ``--system``'s prefix (tests point them at
    temporary directories)."""

    name = "doctor"
    exit_codes: tuple[ExitCode, ...] = (ExitCode.SDK,)

    def __init__(
        self,
        *,
        pkg_config_dirs: Sequence[str] | None = None,
        default_prefix: str = DEFAULT_PREFIX,
        system_prefix: str = DEFAULT_PREFIX,
    ) -> None:
        self.pkg_config_dirs = pkg_config_dirs
        self.default_prefix = default_prefix
        self.system_prefix = system_prefix

    def register(self, subparsers: Subparsers) -> argparse.ArgumentParser:
        parser = subparsers.add_parser(
            self.name,
            help="report toolchain, SDK, plugin directory, load order, clashes",
            description=(
                "Report the compiler, the SDK and its profile, the plugin directory mmt-dpi\n"
                "scans (MMT_DPI_PLUGINS_DIR, else the one compiled into libmmt_core) and\n"
                "whether it is the install prefix's, the load order of the installed\n"
                "plugins and their id/name clashes, with the project's model too when run\n"
                "in a project. Exit 0 when no check fails (warnings allowed), 4 otherwise.\n"
                "Nothing is written."
            ),
            epilog=(
                "examples:\n"
                "  mmt-plugin doctor --sdk $HOME/mmt/opt/mmt\n"
                "  mmt-plugin doctor --prefix $HOME/mmt/opt/mmt --model model.pdl"
            ),
        )
        parser.add_argument(
            "--sdk",
            metavar="PREFIX",
            help="the mmt-dpi prefix (default: MMT_BASE, mmt-dpi.pc, /opt/mmt)",
        )
        parser.add_argument(
            "--cc", metavar="CC", help="the compiler, gcc or clang (default: CC, else gcc)"
        )
        parser.add_argument(
            "--prefix",
            metavar="DIR",
            help=(
                f"the install prefix to report, as for install (default: {ENV_PREFIX}, else"
                " ${XDG_DATA_HOME:-~/.local/share}/mmt)"
            ),
        )
        parser.add_argument(
            "--system", action="store_true", help="report the install prefix /opt/mmt"
        )
        parser.add_argument(
            "--model",
            metavar="MODEL",
            help="the project's model, checked for clashes (default: <project>/plugin.yaml)",
        )
        return parser

    def run(self, args: argparse.Namespace, ctx: Context) -> Outcome:
        env = os.environ
        project = absolute(ctx.project)
        prefix = resolve_prefix(args.prefix, args.system, env, system_prefix=self.system_prefix)
        run = _Run()
        context: dict[str, Any] = {"sdk": None, "prefix": prefix.to_json()}

        toolchain = self._toolchain(args, env, run)
        sdk, choice = self._sdk(args, env, run)
        if sdk is not None and choice is not None:
            context["sdk"] = sdk_context(sdk, choice)
        plugin_dirs, scanned = self._plugin_dirs(sdk, prefix, env, run)
        dirs = [d for d in dict.fromkeys([scanned, str(prefix.plugins)]) if d and os.path.isdir(d)]
        orders = self._load_order(dirs, run)
        self._registry(sdk, choice, scanned, env, run)
        project_proto = self._project(args, project, choice, run)
        clashes = self._clashes(dirs, project_proto, project, run)

        checks = [c.to_json() for c in run.checks]
        result = {
            "checks": checks,
            "toolchain": toolchain,
            "plugin_dirs": plugin_dirs,
            "load_order": orders,
            "clashes": clashes,
        }
        failing = [c for c in run.checks if c.error is not None]
        error = None
        if failing:
            first = failing[0].error
            assert first is not None
            error = CliError(
                first.code,
                f"{_plural(len(failing), 'check')} failed: {', '.join(c.id for c in failing)}"
                f" ({first.message})",
                first.hint or "fix the failing checks, then re-run doctor",
            )

        def view(st: StreamStyle) -> str:
            return _view(checks, st)

        return Outcome(
            result=result,
            records=[(c["id"], c["status"], c["detail"]) for c in checks],
            view=view,
            diagnostics=run.diagnostics,
            error=error,
            context=context,
        )

    # --- the checks ---

    def _toolchain(
        self, args: argparse.Namespace, env: Mapping[str, str], run: _Run
    ) -> dict[str, Any]:
        python = {"version": platform.python_version(), "path": sys.executable}
        run.add("python", "pass", f"{python['version']} ({python['path']})")
        cc: dict[str, str] | None = None
        try:
            found = find_compiler(args.cc, env)
        except CliError as exc:
            if exc.exit_code is ExitCode.USAGE:
                raise
            run.add("compiler", "fail", exc.message, exc)
        else:
            cc = {"name": found.name, "path": found.path, "version": found.version}
            run.add("compiler", "pass", f"{found.version} ({found.path})")
        return {"python": python, "cc": cc}

    def _sdk(
        self, args: argparse.Namespace, env: Mapping[str, str], run: _Run
    ) -> tuple[Sdk | None, ProfileChoice | None]:
        try:
            sdk = require_sdk(
                args.sdk,
                env,
                pkg_config_dirs=self.pkg_config_dirs,
                default_prefix=self.default_prefix,
            )
        except CliError as exc:
            run.add("sdk", "fail", exc.message, exc)
            run.add("sdk-profile", "skip", "no SDK")
            return None, None
        detail = f"{sdk.prefix} ({sdk.source.value}), version {sdk.version or 'unknown'}"
        if core_library(sdk) is None:
            error = CliError(
                "sdk.invalid-prefix",
                f"{sdk.prefix}/dpi/lib has no libmmt_core shared object",
                "pass the prefix of a complete mmt-dpi install with --sdk or MMT_BASE",
            )
            run.add("sdk", "fail", f"{detail}: no libmmt_core", error)
        else:
            run.add("sdk", "pass", detail)
        try:
            choice = resolve_profile(None, env, None, sdk)
        except CliError as exc:
            run.add("sdk-profile", "fail", exc.message, exc)
            return sdk, None
        run.diagnostics += choice.diagnostics
        status = "warn" if choice.diagnostics else "pass"
        run.add("sdk-profile", status, f"{choice.profile.version} ({choice.source.value})")
        return sdk, choice

    def _plugin_dirs(
        self, sdk: Sdk | None, prefix: InstallPrefix, env: Mapping[str, str], run: _Run
    ) -> tuple[dict[str, Any], str | None]:
        """The ``plugin-dir`` and ``install-dir`` checks; the scanned
        directory when it is a usable one."""
        scanned, source = scanned_plugin_dir(sdk, env)
        usable: str | None = None
        if scanned is None:
            if sdk is None:
                run.add("plugin-dir", "skip", f"no SDK and no {PLUGINS_DIR_ENV}")
            else:
                why = f"cannot read the plugin directory compiled into {sdk.prefix}'s libmmt_core"
                run.warn(
                    "sdk.plugin-dir-unknown",
                    why,
                    f"set {PLUGINS_DIR_ENV} to the directory mmt-dpi should load",
                )
                run.add("plugin-dir", "warn", why)
        elif source == PLUGINS_DIR_ENV and not os.path.isabs(scanned):
            error = CliError(
                "sdk.invalid-plugin-dir",
                f"{PLUGINS_DIR_ENV}={scanned} is relative: mmt-dpi refuses it and loads no plugin",
                f"set {PLUGINS_DIR_ENV} to an absolute directory",
            )
            run.add("plugin-dir", "fail", error.message, error)
        elif not (os.path.isdir(scanned) and os.access(scanned, os.R_OK | os.X_OK)):
            if source == PLUGINS_DIR_ENV:
                error = CliError(
                    "sdk.invalid-plugin-dir",
                    f"{PLUGINS_DIR_ENV}={scanned} is not a readable directory: init_extraction()"
                    " fails",
                    f"create it, or unset {PLUGINS_DIR_ENV}",
                )
                run.add("plugin-dir", "fail", error.message, error)
            else:
                run.add(
                    "plugin-dir",
                    "warn",
                    f"{scanned} (compiled into libmmt_core) does not exist: mmt-dpi loads no"
                    " plugin",
                )
        else:
            usable = scanned
            where = PLUGINS_DIR_ENV if source == PLUGINS_DIR_ENV else "compiled into libmmt_core"
            if os.path.exists(os.path.join(scanned, TCPIP_PLUGIN)):
                run.add("plugin-dir", "pass", f"{scanned} ({where})")
            else:
                hint = "link the SDK's plugins into it"
                if sdk is not None:
                    hint += f" (ln -s {sdk.prefix}/plugins/*.so {scanned}/)"
                run.warn(
                    "sdk.no-tcpip-plugin",
                    f"{scanned} has no {TCPIP_PLUGIN}: mmt-dpi registers no Ethernet, IP, TCP"
                    " or UDP, so a plugin attached to one of them gets no packet",
                    hint,
                )
                run.add("plugin-dir", "warn", f"{scanned} ({where}): no {TCPIP_PLUGIN}")

        install = prefix.plugins
        is_scanned = usable is not None and os.path.realpath(usable) == os.path.realpath(install)
        can_write = writable(install)
        detail = f"{install.as_posix()} ({prefix.source})"
        if not can_write:
            detail += ", not writable"
        if is_scanned:
            run.add("install-dir", "pass", f"{detail}: mmt-dpi scans it")
        elif scanned is None:
            run.add("install-dir", "warn", f"{detail}: cannot tell whether mmt-dpi scans it")
        else:
            hint = f"export {PLUGINS_DIR_ENV}={install.as_posix()}"
            if sdk is not None and not (install / TCPIP_PLUGIN).exists():
                hint += (
                    f", and link the SDK's plugins into it (ln -s {sdk.prefix}/plugins/*.so"
                    f" {install.as_posix()}/): {PLUGINS_DIR_ENV} replaces {scanned}"
                )
            run.warn(
                "sdk.install-dir-not-scanned",
                f"mmt-dpi scans {scanned}, not {install.as_posix()}: the plugins installed there"
                " do not load",
                hint,
            )
            run.add("install-dir", "warn", f"{detail}: not scanned by mmt-dpi ({scanned} is)")
        dirs = {
            "scanned": None if scanned is None else {"path": scanned, "source": source},
            "install": {
                **prefix.to_json(),
                "plugins": install.as_posix(),
                "scanned": is_scanned if scanned is not None else None,
                "writable": can_write,
            },
        }
        return dirs, usable

    def _load_order(self, dirs: Sequence[str], run: _Run) -> list[dict[str, Any]]:
        orders = collations()
        found: list[dict[str, Any]] = []
        bad: list[str] = []
        count = 0
        for directory in dirs:
            names = _plugin_names(directory)
            found.append({"path": directory, "plugins": names})
            for name in names:
                if _is_sdk_plugin(name):
                    continue
                count += 1
                ok, detail = load_order(name, orders)
                if not ok:
                    bad.append(f"{directory}/{name}")
                    run.diagnostics.append(
                        Diagnostic(
                            Severity.ERROR,
                            "sdk.plugin-load-order",
                            f"{directory}/{name}: {detail}",
                            hint="rename the plugin mmtp_<label>.so, or reinstall it with"
                            " mmt-plugin install",
                        )
                    )
        if bad:
            error = CliError(
                "sdk.plugin-load-order",
                f"{', '.join(bad)} sorts before {TCPIP_PLUGIN}",
                "rename the plugin mmtp_<label>.so, or reinstall it with mmt-plugin install",
            )
            run.add("load-order", "fail", error.message, error)
        elif count:
            run.add("load-order", "pass", f"{_plural(count, 'plugin')} after {TCPIP_PLUGIN}")
        else:
            run.add("load-order", "skip", "no plugin installed")
        return found

    def _registry(
        self,
        sdk: Sdk | None,
        choice: ProfileChoice | None,
        scanned: str | None,
        env: Mapping[str, str],
        run: _Run,
    ) -> None:
        if sdk is None or choice is None or scanned is None:
            run.add("registry", "skip", "no SDK" if sdk is None else "no plugin directory")
            return
        try:
            registry = read_registry(
                sdk,
                env={**env, PLUGINS_DIR_ENV: scanned},
                max_id=_max_id(choice.profile),
            )
        except RegistryError as exc:
            run.warn(
                "sdk.registry-unavailable",
                f"cannot read the run-time registry: {exc}",
                "an installed plugin may fail to load: check each with mmt-plugin validate",
            )
            run.add("registry", "warn", f"cannot load {scanned}: {exc}")
            return
        run.add(
            "registry",
            "pass",
            f"{_plural(len(registry.plugins), 'plugin')} load,"
            f" {_plural(len(registry.protocols), 'protocol')} registered",
        )

    def _project(
        self,
        args: argparse.Namespace,
        project: Path,
        choice: ProfileChoice | None,
        run: _Run,
    ) -> tuple[str, int, str] | None:
        """The ``project`` check: the project's label, id and name, or ``None``."""
        if args.model is None and not (project / PROJECT_FILE).is_file():
            run.add("project", "skip", f"not in a project (no {PROJECT_FILE})")
            return None
        try:
            model = read_model(args.model, "auto", project)
        except CliError as exc:
            run.add("project", "warn", f"{exc.message}: not checked for clashes")
            return None
        if choice is None:
            choice = resolve_profile(None, {}, None, None)
        generation, _, error = make_generation(model.name, model.data, choice)
        if generation is None:
            message = error.message if error is not None else "it does not generate"
            run.add("project", "warn", f"{message}: not checked for clashes")
            return None
        label = generation.label.lower()
        run.add(
            "project",
            "pass",
            f"{model.name}: {label} (id {generation.proto_id}, {generation.name})",
        )
        return label, generation.proto_id, generation.name

    def _clashes(
        self,
        dirs: Sequence[str],
        project_proto: tuple[str, int, str] | None,
        project: Path,
        run: _Run,
    ) -> list[dict[str, Any]]:
        """The ``clashes`` check: the installed plugins (their manifests) and
        the project's model, by id and by name (case-insensitive)."""
        entries: dict[str, tuple[int, str, str]] = {}
        for directory in dirs:
            manifests, problems = read_manifests(Path(directory))
            for problem in problems:
                run.warn("state.invalid-manifest", f"{problem}: not checked for clashes")
            for m in manifests:
                where = show_path(manifest_path(Path(directory), m.label), project)
                entries.setdefault(m.label, (m.proto_id, m.name, where))
        installed = len(entries)
        if project_proto is not None:
            label, pid, name = project_proto
            # The project's own installed copy is the same plugin, not a clash.
            entries[label] = (pid, name, "the project's model")
        by_id: dict[int, list[str]] = {}
        by_name: dict[str, list[str]] = {}
        for label, (pid, name, _) in sorted(entries.items()):
            by_id.setdefault(pid, []).append(label)
            by_name.setdefault(name.casefold(), []).append(label)
        clashes = [
            {"kind": "id", "value": str(pid), "plugins": labels}
            for pid, labels in sorted(by_id.items())
            if len(labels) > 1
        ] + [
            {"kind": "name", "value": entries[labels[0]][1], "plugins": labels}
            for _, labels in sorted(by_name.items())
            if len(labels) > 1
        ]
        for clash in clashes:
            sources = ", ".join(f"{p} ({entries[p][2]})" for p in clash["plugins"])
            run.diagnostics.append(
                Diagnostic(
                    Severity.ERROR,
                    "sdk.plugin-clash",
                    f"protocol {clash['kind']} {clash['value']} is registered by {sources}",
                    hint="uninstall one of them, or change its id or label",
                )
            )
        scope = _plural(installed, "installed plugin")
        if project_proto is not None:
            scope += " and the project's model"
        if clashes:
            first = clashes[0]
            error = CliError(
                "sdk.plugin-clash",
                f"{_plural(len(clashes), 'clash')} among {scope} (first: {first['kind']}"
                f" {first['value']}: {', '.join(first['plugins'])})",
                "uninstall one of them, or change its id or label",
            )
            run.add("clashes", "fail", error.message, error)
        elif installed or project_proto is not None:
            run.add("clashes", "pass", f"no clash among {scope}")
        else:
            run.add("clashes", "skip", "no plugin installed by mmt-plugin")
        return clashes


def _view(checks: Sequence[Mapping[str, str]], st: StreamStyle) -> str:
    """The styled output: one box ``doctor``, four sections (toolchain, SDK,
    plugin directories, load order and clashes), each with its own border
    role."""
    by_id = {c["id"]: c for c in checks}
    width = st.width - 4
    widest = max(len(t) for t in _TITLES.values())
    body: list[str | style.Section] = []
    for section, border in zip(SECTIONS, _BORDERS, strict=True):
        rows = [
            [
                _TITLES[i].ljust(widest),
                style.status(by_id[i]["status"], _LEVELS[by_id[i]["status"]], style=st),
                by_id[i]["detail"],
            ]
            for i in section
        ]
        body.append(style.Section(style.table(None, rows, style=st, width=width), border))
    counts = {s: sum(1 for c in checks if c["status"] == s) for s in _LEVELS}
    parts = [_plural(len(checks), "check"), f"{counts['pass']} pass"]
    if counts["warn"]:
        parts.append(_plural(counts["warn"], "warning"))
    if counts["fail"]:
        parts.append(f"{counts['fail']} failed")
    if counts["skip"]:
        parts.append(f"{counts['skip']} skipped")
    return style.box("doctor", body, style=st, footer=style.glyphs(st).separator.join(parts))
