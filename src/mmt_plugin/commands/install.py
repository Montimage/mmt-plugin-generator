"""``mmt-plugin install [MODEL]`` and ``mmt-plugin uninstall [LABEL]``
(``docs/design/cli.md``, sections 4, 5, 6, 8 and 9).

``install`` copies the plugin ``mmtp_<label>.so`` into ``<prefix>/plugins/``
and writes the manifest ``<prefix>/plugins/.mmt-plugin/<label>.json``
(``mmt_plugin.manifest``) last. The prefix is ``--prefix`` > ``--system``
(``/opt/mmt``) > ``MMT_PLUGIN_PREFIX`` > ``${XDG_DATA_HOME:-~/.local/share}/mmt``;
the tool never uses sudo, and a prefix it cannot write is
``sdk.prefix-not-writable`` (exit 4). Stages:

1. ``build``: ``mmt-plugin build`` (``mmt_plugin.commands.build``), a no-op
   when the plugin is up to date; with ``--no-deps``, a plugin that is not up
   to date is ``state.stale`` (exit 7) and nothing is built;
2. ``install``: ``mmtp_<label>.so`` must sort after ``libmmt_tcpip.so``
   (``model.load-order``, exit 3), and its id and name must not be another
   installed plugin's (the other manifests of ``<prefix>/plugins``;
   ``model.id-taken``/``model.name-taken``, exit 3). The same file already
   installed is a no-op; a different file the manifest does not list is
   ``state.exists`` and one changed since it was installed
   ``state.installed-modified`` (exit 7), both replaced only with
   ``--force``.

``uninstall`` removes the files the label's manifest lists whose sha256 is
still the recorded one, then the manifest. A changed file is kept, with
``state.installed-modified`` (exit 7), unless ``--force``; the manifest then
lists only the kept files. No manifest is the warning ``state.not-installed``
(exit 0). ``LABEL`` defaults to the project's: the generated header
``<label>_mmt_plugin.h`` that ``plugin.lock`` lists.

Both take ``--dry-run`` (report every action, write nothing, exit as if they
ran). Every write is atomic (``mmt_plugin.fsio``).
"""

from __future__ import annotations

import argparse
import contextlib
import os
import stat
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from mmt_plugin import __version__
from mmt_plugin.commands import Context, Outcome, Subparsers
from mmt_plugin.commands.build import BuildCommand
from mmt_plugin.commands.generate import DEFAULT_OUTPUT, make_generation
from mmt_plugin.commands.modelio import FORMATS, absolute, read_model, show_path
from mmt_plugin.commands.validate import collations, load_order, plugin_file
from mmt_plugin.diagnostics import CliError, Diagnostic, Related, Severity
from mmt_plugin.exitcodes import ExitCode
from mmt_plugin.fsio import sha256_bytes, sha256_file, write_atomic
from mmt_plugin.lock import LOCK_NAME, LockError, read_lock
from mmt_plugin.manifest import (
    ENV_PREFIX,
    LABEL_PATTERN,
    MANIFEST_DIR,
    InstalledFile,
    InstallPrefix,
    Manifest,
    ManifestError,
    check_writable,
    manifest_path,
    read_manifest,
    read_manifests,
    resolve_prefix,
)
from mmt_plugin.sdk.detect import DEFAULT_PREFIX
from mmt_plugin.sdk.resolve import ENV_PROFILE, resolve_profile
from mmt_plugin.ui import style
from mmt_plugin.ui.streams import StreamStyle

__all__ = ["HEADER_SUFFIX", "InstallCommand", "UninstallCommand", "project_label"]

#: The generated header's suffix: ``<label>_mmt_plugin.h``.
HEADER_SUFFIX = "_mmt_plugin.h"
#: The installed plugin's mode: a shared object, readable by every user.
PLUGIN_MODE = 0o755

_LEVELS = {
    "created": style.Level.OK,
    "updated": style.Level.OK,
    "unchanged": style.Level.OK,
    "removed": style.Level.OK,
    "would-create": style.Level.SKIP,
    "would-update": style.Level.SKIP,
    "would-remove": style.Level.SKIP,
    "kept": style.Level.FAIL,
    "missing": style.Level.WARN,
}


def _add_prefix_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--prefix",
        metavar="DIR",
        help=(
            f"the install prefix; the plugin goes to <prefix>/plugins/ (default: {ENV_PREFIX},"
            " else ${XDG_DATA_HOME:-~/.local/share}/mmt)"
        ),
    )
    parser.add_argument(
        "--system",
        action="store_true",
        help="use the prefix /opt/mmt (never with sudo: not writable is exit 4)",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="report every action, write nothing"
    )


def _label_error(label: str) -> CliError:
    return CliError(
        "usage.invalid-value",
        f"LABEL {label!r} is not a protocol label ([a-z][a-z0-9_]*)",
        "pass the label of the installed plugin, lower case (mmtp_<label>.so)",
    )


def project_label(project: Path) -> str | None:
    """The project's label: from the generated header
    ``<label>_mmt_plugin.h`` that ``<project>/plugin.lock`` (else
    ``<project>/generated/plugin.lock``, where ``generate`` writes it for a
    model outside a project) lists; ``None`` without a lock. Raises
    ``CliError`` ``state.invalid-lock`` for a lock that cannot be read."""
    for path in (project / LOCK_NAME, project / DEFAULT_OUTPUT / LOCK_NAME):
        try:
            lock = read_lock(path, show_path(path, project))
        except LockError as exc:
            raise CliError(
                "state.invalid-lock",
                str(exc),
                "pass LABEL, or run mmt-plugin generate to rewrite plugin.lock",
            ) from None
        if lock is None:
            continue
        headers = [
            f.path.rsplit("/", 1)[-1][: -len(HEADER_SUFFIX)].lower()
            for f in lock.files
            if f.path.endswith(HEADER_SUFFIX)
        ]
        if len(headers) == 1 and LABEL_PATTERN.match(headers[0]):
            return headers[0]
    return None


@dataclass
class _Install:
    """What one install reports, filled in stage by stage."""

    build: str = "skipped"
    files: list[dict[str, Any]] = field(default_factory=list)
    manifest: dict[str, Any] | None = None
    diagnostics: list[Diagnostic] = field(default_factory=list)


class InstallCommand:
    """``mmt-plugin install [MODEL]``: copy the plugin into a prefix and
    record a manifest.

    ``pkg_config_dirs`` and ``default_prefix`` are passed to SDK detection,
    ``system_prefix`` is ``--system``'s prefix (tests point them at
    temporary directories)."""

    name = "install"
    exit_codes: tuple[ExitCode, ...] = (
        ExitCode.MODEL,
        ExitCode.SDK,
        ExitCode.BUILD,
        ExitCode.STATE,
    )

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
            help="copy the plugin into a prefix and record a manifest",
            description=(
                "Build the plugin when it is stale, then copy mmtp_<label>.so into\n"
                "<prefix>/plugins/ and record it in <prefix>/plugins/.mmt-plugin/<label>.json,\n"
                "which uninstall follows. The same file already installed is a no-op; a\n"
                "different file that install did not write is replaced only with --force.\n"
                "mmt-dpi loads the plugins of one directory: MMT_DPI_PLUGINS_DIR, else the\n"
                "one compiled into libmmt_core (/opt/mmt/plugins); mmt-plugin doctor says\n"
                "whether it scans the install prefix."
            ),
            epilog=(
                "examples:\n"
                "  mmt-plugin install model.pdl --sdk $HOME/mmt/opt/mmt --dry-run\n"
                "  mmt-plugin install model.pdl --prefix $HOME/mmt/opt/mmt"
            ),
        )
        parser.add_argument(
            "model",
            nargs="?",
            metavar="MODEL",
            help="a PDL v1 model file (default: <project>/plugin.yaml, which needs #24)",
        )
        parser.add_argument(
            "--model-format",
            choices=FORMATS,
            default="auto",
            help="the model format (default: auto: .yaml/.yml is YAML, anything else PDL)",
        )
        _add_prefix_options(parser)
        parser.add_argument(
            "--sdk",
            metavar="PREFIX",
            help="the mmt-dpi prefix to build against (default: MMT_BASE, mmt-dpi.pc, /opt/mmt)",
        )
        parser.add_argument(
            "--sdk-profile",
            metavar="VERSION",
            help=f"the SDK profile, e.g. 1.10.2 (default: {ENV_PROFILE}, else the SDK's own)",
        )
        parser.add_argument(
            "--cc", metavar="CC", help="the compiler, gcc or clang (default: CC, else gcc)"
        )
        parser.add_argument(
            "--build-dir",
            metavar="DIR",
            help="the directory of the built mmtp_<label>.so (default: <project>/build/)",
        )
        parser.add_argument(
            "--no-deps",
            action="store_true",
            help="do not build a stale plugin: exit 7 instead",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="replace a file at the target that install did not write, or that changed",
        )
        return parser

    def run(self, args: argparse.Namespace, ctx: Context) -> Outcome:
        project = absolute(ctx.project)
        if args.model == "-":
            raise CliError(
                "usage.invalid-value",
                "install reads MODEL from a file, not stdin: build compares the generated"
                " files with it",
                "pass the model file as MODEL",
            )
        prefix = resolve_prefix(
            args.prefix, args.system, os.environ, system_prefix=self.system_prefix
        )
        ctx.log(f"install prefix {prefix.path} ({prefix.source})")
        check_writable(prefix)

        build = BuildCommand(
            pkg_config_dirs=self.pkg_config_dirs, default_prefix=self.default_prefix
        )
        # With --no-deps or --dry-run, build only checks (a dry run of its
        # own): up to date or not.
        ns = argparse.Namespace(
            model=args.model,
            model_format=args.model_format,
            sdk=args.sdk,
            sdk_profile=args.sdk_profile,
            cc=args.cc,
            build_dir=args.build_dir,
            rebuild=False,
            no_deps=args.no_deps,
            dry_run=bool(args.no_deps or args.dry_run),
            strict=False,
        )
        built = build.run(ns, ctx)
        run = _Install(diagnostics=list(built.diagnostics))
        context = {**built.context, "prefix": prefix.to_json()}
        model = read_model(args.model, args.model_format, project)
        label: str | None = None
        protocol: dict[str, Any] | None = None

        def outcome(error: CliError | None) -> Outcome:
            result: dict[str, Any] = {
                "model": model.name,
                "label": label,
                "protocol": protocol,
                "prefix": prefix.path.as_posix(),
                "build": run.build,
                "manifest": run.manifest,
                "files": run.files,
                "dry_run": bool(args.dry_run),
            }
            records: list[tuple[str, ...]] = [("build", run.build)]
            records += [(f["action"], f["path"]) for f in run.files]
            if run.manifest is not None:
                records.append((run.manifest["action"], run.manifest["path"]))

            def view(st: StreamStyle) -> str:
                return _install_view(label or "?", result, st)

            return Outcome(
                result=result,
                records=records,
                view=view,
                diagnostics=run.diagnostics,
                error=error,
                context=context,
            )

        if built.error is not None:
            run.build = "stale" if built.error.code == "state.stale" else "failed"
            return outcome(built.error)
        up_to_date = bool(built.result["up_to_date"])
        if up_to_date:
            run.build = "up-to-date"
        elif args.no_deps:
            run.build = "stale"
            return outcome(
                CliError(
                    "state.stale",
                    "the plugin is not up to date (--no-deps)",
                    "run mmt-plugin build first, or install without --no-deps",
                )
            )
        else:
            run.build = "would-run" if args.dry_run else "ran"

        choice = resolve_profile(built.result["profile"], {}, None, None)
        generation, _, error = make_generation(model.name, model.data, choice)
        if error is not None or generation is None:  # pragma: no cover - build generated it
            return outcome(error)
        label = generation.label.lower()
        protocol = {"id": generation.proto_id, "name": generation.name}
        artifact = built.result["artifact"]
        data = None if artifact is None else (project / artifact["path"]).read_bytes()
        return outcome(
            self._install(
                args, project, prefix, label, generation.proto_id, generation.name, data, run
            )
        )

    def _install(
        self,
        args: argparse.Namespace,
        project: Path,
        prefix: InstallPrefix,
        label: str,
        proto_id: int,
        name: str,
        data: bytes | None,
        run: _Install,
    ) -> CliError | None:
        """The ``install`` stage; ``data`` is the plugin, ``None`` when a dry
        run has not built it."""
        file_name = plugin_file(label)
        ok, detail = load_order(file_name, collations())
        if not ok:
            return CliError(
                "model.load-order",
                f"{detail}: mmt-dpi would load it before its parents",
                "the plugin file is mmtp_<label>.so; check LC_COLLATE",
            )
        error = self._clashes(prefix, label, proto_id, name, run)
        if error is not None:
            return error

        plugins = prefix.plugins
        target = plugins / file_name
        mpath = manifest_path(plugins, label)
        shown_manifest = show_path(mpath, project)
        try:
            own = read_manifest(mpath, shown_manifest)
        except ManifestError as exc:
            if not args.force:
                return CliError(
                    "state.invalid-manifest",
                    str(exc),
                    "install with --force to rewrite it, or remove it",
                )
            own = None
        new_sha = None if data is None else sha256_bytes(data)
        error = self._check_target(args, target, project, own, file_name, new_sha)
        if error is not None:
            return error

        if data is None:
            exists = target.exists() or target.is_symlink()
            run.files = [
                {
                    "path": show_path(target, project),
                    "action": "would-update" if exists else "would-create",
                    "sha256": None,
                }
            ]
            run.manifest = {
                "path": shown_manifest,
                "action": "would-update" if mpath.exists() else "would-create",
                "sha256": None,
            }
            return None
        written = write_atomic(target, data, dry_run=bool(args.dry_run), mode=PLUGIN_MODE)
        run.files = [
            {"path": show_path(target, project), "action": written.action.value, "sha256": new_sha}
        ]
        manifest = Manifest(
            __version__, label, proto_id, name, (InstalledFile(file_name, written.sha256),)
        )
        recorded = write_atomic(mpath, manifest.dumps(), dry_run=bool(args.dry_run))
        run.manifest = {
            "path": shown_manifest,
            "action": recorded.action.value,
            "sha256": recorded.sha256,
        }
        return None

    def _clashes(
        self, prefix: InstallPrefix, label: str, proto_id: int, name: str, run: _Install
    ) -> CliError | None:
        """The model's id and name against the other plugins installed in
        the prefix (their manifests)."""
        manifests, problems = read_manifests(prefix.plugins)
        run.diagnostics += [
            Diagnostic(
                Severity.WARNING,
                "state.invalid-manifest",
                f"{p}: not checked for id and name clashes",
                hint="remove it, or uninstall its plugin with --force",
            )
            for p in problems
        ]
        found: list[Diagnostic] = []
        for other in manifests:
            if other.label == label:
                continue
            where = [Related(f"installed by {manifest_path(prefix.plugins, other.label)}")]
            if other.proto_id == proto_id:
                found.append(
                    Diagnostic(
                        Severity.ERROR,
                        "model.id-taken",
                        f"protocol id {proto_id} is already installed in {prefix.plugins},"
                        f' by "{other.name}" ({plugin_file(other.label)})',
                        hint="use a free id from 950 to 999, or uninstall that plugin",
                        related=where,
                    )
                )
            if other.name.casefold() == name.casefold():
                found.append(
                    Diagnostic(
                        Severity.ERROR,
                        "model.name-taken",
                        f"protocol name {name} is already installed in {prefix.plugins}, by id"
                        f" {other.proto_id} ({plugin_file(other.label)}; names are"
                        " case-insensitive)",
                        hint="choose another label, or uninstall that plugin",
                        related=where,
                    )
                )
        if not found:
            return None
        run.diagnostics += found
        return CliError(
            found[0].code,
            f"{len(found)} clash{'es' if len(found) > 1 else ''} with the plugins installed in"
            f" {prefix.plugins}",
            "fix the model, or uninstall the other plugin first",
        )

    def _check_target(
        self,
        args: argparse.Namespace,
        target: Path,
        project: Path,
        own: Manifest | None,
        file_name: str,
        new_sha: str | None,
    ) -> CliError | None:
        """Refuse a target that install did not write, or that changed since
        (``state.exists``, ``state.installed-modified``), unless ``--force``;
        the same file as ``new_sha`` (the plugin's) is always accepted."""
        shown = show_path(target, project)
        if target.is_symlink() or not target.exists():
            if not target.is_symlink():
                return None
            current = None
        else:
            mode = target.lstat().st_mode
            if not stat.S_ISREG(mode):
                return CliError(
                    "state.exists",
                    f"{shown} is not a regular file",
                    "remove it, then re-run install",
                )
            current = sha256_file(target)
        entry = None if own is None else own.file(file_name)
        if current is not None and current in (new_sha, None if entry is None else entry.sha256):
            return None
        if args.force:
            return None
        if entry is None:
            return CliError(
                "state.exists",
                f"{shown} exists and was not installed by mmt-plugin (no manifest lists it)",
                "install with --force to replace it",
            )
        return CliError(
            "state.installed-modified",
            f"{shown} changed since it was installed (its sha256 is not the manifest's)",
            "install with --force to replace it",
        )


def _install_view(label: str, result: Mapping[str, Any], st: StreamStyle) -> str:
    """The styled output: a box ``install <label>`` with the prefix and the
    files table."""
    width = st.width - 4
    facts = [["prefix", result["prefix"]], ["build", result["build"]]]
    entries = list(result["files"])
    if result["manifest"] is not None:
        entries.append(result["manifest"])
    rows = [
        [
            style.status(f["action"], _LEVELS.get(f["action"], style.Level.SKIP), style=st),
            f["path"],
        ]
        for f in entries
    ]
    body: list[str] = [*style.table(None, facts, style=st, width=width)]
    if rows:
        body += ["", *style.table(["action", "path"], rows, style=st, width=width)]
    actions = {f["action"] for f in entries}
    if not entries:
        footer = "not installed"
    elif result["dry_run"]:
        footer = "dry run"
    elif actions == {"unchanged"}:
        footer = "up to date"
    else:
        footer = "installed"
    return style.box(f"install {label}", body, style=st, footer=footer)


# --- uninstall ---------------------------------------------------------------


class UninstallCommand:
    """``mmt-plugin uninstall [LABEL]``: remove an installed plugin by
    following its manifest. ``system_prefix`` is ``--system``'s prefix."""

    name = "uninstall"
    exit_codes: tuple[ExitCode, ...] = (ExitCode.SDK, ExitCode.STATE)

    def __init__(self, *, system_prefix: str = DEFAULT_PREFIX) -> None:
        self.system_prefix = system_prefix

    def register(self, subparsers: Subparsers) -> argparse.ArgumentParser:
        parser = subparsers.add_parser(
            self.name,
            help="remove an installed plugin by following its manifest",
            description=(
                "Remove the files that <prefix>/plugins/.mmt-plugin/<label>.json lists and\n"
                "whose sha256 is still the one install recorded, then the manifest. A file\n"
                "changed since it was installed is kept (exit 7) unless --force. A plugin\n"
                "that is not installed is a warning (exit 0)."
            ),
            epilog=(
                "examples:\n"
                "  mmt-plugin uninstall tpkt --prefix $HOME/mmt/opt/mmt --dry-run\n"
                "  mmt-plugin -C tpkt uninstall   # the project's label"
            ),
        )
        parser.add_argument(
            "label",
            nargs="?",
            metavar="LABEL",
            help="the plugin's label (default: the project's, from plugin.lock)",
        )
        _add_prefix_options(parser)
        parser.add_argument(
            "--force", action="store_true", help="also remove files changed since install"
        )
        return parser

    def run(self, args: argparse.Namespace, ctx: Context) -> Outcome:
        project = absolute(ctx.project)
        if args.label is not None and not LABEL_PATTERN.match(args.label):
            raise _label_error(args.label)
        prefix = resolve_prefix(
            args.prefix, args.system, os.environ, system_prefix=self.system_prefix
        )
        label = args.label if args.label is not None else project_label(project)
        if label is None:
            raise CliError(
                "usage.missing-argument",
                f"no LABEL, and no {LOCK_NAME} in {show_path(project, project)} names the"
                " project's plugin",
                "pass the label of the installed plugin (mmtp_<label>.so)",
            )
        plugins = prefix.plugins
        mpath = manifest_path(plugins, label)
        shown_manifest = show_path(mpath, project)
        removed: list[str] = []
        kept: list[str] = []
        missing: list[str] = []
        diagnostics: list[Diagnostic] = []
        context = {"prefix": prefix.to_json()}

        def outcome(error: CliError | None) -> Outcome:
            result = {
                "prefix": prefix.path.as_posix(),
                "label": label,
                "manifest": shown_manifest,
                "removed": removed,
                "kept": kept,
                "missing": missing,
                "dry_run": bool(args.dry_run),
            }
            action = "would-remove" if args.dry_run else "removed"
            records = [(action, p) for p in removed]
            records += [("kept", p) for p in kept] + [("missing", p) for p in missing]

            def view(st: StreamStyle) -> str:
                return _uninstall_view(str(label), result, st)

            return Outcome(
                result=result,
                records=records,
                view=view,
                diagnostics=diagnostics,
                error=error,
                context=context,
            )

        try:
            manifest = read_manifest(mpath, shown_manifest)
        except ManifestError as exc:
            return outcome(
                CliError(
                    "state.invalid-manifest",
                    str(exc),
                    "remove the plugin's files and the manifest by hand",
                )
            )
        if manifest is None:
            diagnostics.append(
                Diagnostic(
                    Severity.WARNING,
                    "state.not-installed",
                    f"{label} is not installed in {plugins.as_posix()}: no {shown_manifest}",
                    hint="pass the prefix it was installed in with --prefix or --system",
                )
            )
            return outcome(None)
        check_writable(prefix)

        remaining: list[InstalledFile] = []
        for entry in manifest.files:
            path = plugins / entry.path
            shown = show_path(path, project)
            if not path.exists() and not path.is_symlink():
                missing.append(shown)
                continue
            regular = not path.is_symlink() and stat.S_ISREG(path.lstat().st_mode)
            current = sha256_file(path) if regular else None
            if regular and (current == entry.sha256 or args.force):
                removed.append(shown)
                if not args.dry_run:
                    path.unlink()
                continue
            if path.is_symlink() and args.force:
                removed.append(shown)
                if not args.dry_run:
                    path.unlink()
                continue
            kept.append(shown)
            remaining.append(entry)
            diagnostics.append(
                Diagnostic(
                    Severity.ERROR,
                    "state.installed-modified",
                    f"{shown} changed since it was installed (its sha256 is not the manifest's):"
                    " kept",
                    hint="uninstall with --force to remove it too",
                )
            )
        if not args.dry_run:
            if remaining:
                rest = Manifest(
                    manifest.tool_version,
                    manifest.label,
                    manifest.proto_id,
                    manifest.name,
                    tuple(remaining),
                )
                write_atomic(mpath, rest.dumps())
            else:
                mpath.unlink(missing_ok=True)
                with contextlib.suppress(OSError):  # not empty: other plugins' manifests
                    (plugins / MANIFEST_DIR).rmdir()
        if kept:
            return outcome(
                CliError(
                    "state.installed-modified",
                    f"{len(kept)} installed file{'s' if len(kept) > 1 else ''} changed since"
                    " install: kept",
                    "uninstall with --force to remove them too",
                )
            )
        return outcome(None)


def _uninstall_view(label: str, result: Mapping[str, Any], st: StreamStyle) -> str:
    width = st.width - 4
    action = "would-remove" if result["dry_run"] else "removed"
    rows = [[style.status(action, _LEVELS[action], style=st), p] for p in result["removed"]]
    rows += [[style.status("kept", _LEVELS["kept"], style=st), p] for p in result["kept"]]
    rows += [[style.status("missing", _LEVELS["missing"], style=st), p] for p in result["missing"]]
    body: list[str] = [*style.table(None, [["prefix", result["prefix"]]], style=st, width=width)]
    if rows:
        body += ["", *style.table(["action", "path"], rows, style=st, width=width)]
    if not rows:
        footer = "not installed"
    elif result["kept"]:
        footer = f"{len(result['kept'])} kept"
    elif result["dry_run"]:
        footer = "dry run"
    else:
        footer = "uninstalled"
    return style.box(f"uninstall {label}", body, style=st, footer=footer)
