"""Install manifests and install prefixes (``docs/design/cli.md``, sections 4,
8 and 9; D11).

``mmt-plugin install`` copies ``mmtp_<label>.so`` into ``<prefix>/plugins/``
and records what it wrote in the manifest
``<prefix>/plugins/.mmt-plugin/<label>.json``: the tool version, the label,
the protocol's id and name, and each file's path (relative to
``<prefix>/plugins``, a bare file name) and sha256. ``uninstall`` follows it
and removes only the files whose sha256 is still the recorded one; ``doctor``
reads every manifest of a plugin directory to find id and name clashes.

Format: JSON, schema ``mmt_plugin/schemas/install/v1/manifest.json``
(``load_schema``), ``manifest_version`` 1, written with two-space indentation,
keys in schema order and a final newline, no timestamp and no absolute path.
``parse_manifest`` repeats the schema's checks by hand (no run-time
dependency on a JSON Schema validator) and refuses a newer
``manifest_version``.

The install prefix is ``--prefix`` > ``--system`` (``/opt/mmt``) >
``MMT_PLUGIN_PREFIX`` > ``${XDG_DATA_HOME:-~/.local/share}/mmt``
(``resolve_prefix``). mmt-dpi 1.10.2 scans one plugin directory only
(``mmt_plugin.sdk.registry.scanned_plugin_dir``), so a plugin installed under
the default prefix loads once ``MMT_DPI_PLUGINS_DIR`` names
``<prefix>/plugins``; ``doctor`` says so.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any

from mmt_plugin.diagnostics import CliError

__all__ = [
    "ENV_PREFIX",
    "LABEL_PATTERN",
    "MANIFEST_DIR",
    "MANIFEST_VERSION",
    "SCHEMA_RESOURCE",
    "InstallPrefix",
    "InstalledFile",
    "Manifest",
    "ManifestError",
    "check_writable",
    "default_prefix",
    "load_schema",
    "manifest_path",
    "parse_manifest",
    "read_manifest",
    "read_manifests",
    "resolve_prefix",
    "writable",
]

#: The ``manifest_version`` this module writes and reads.
MANIFEST_VERSION = 1
#: The manifests' directory, inside ``<prefix>/plugins``.
MANIFEST_DIR = ".mmt-plugin"
#: The manifest's JSON Schema, inside the package.
SCHEMA_RESOURCE = "schemas/install/v1/manifest.json"
#: The environment variable that names the install prefix.
ENV_PREFIX = "MMT_PLUGIN_PREFIX"
#: A protocol label (``init LABEL``): it names files, so it is checked.
LABEL_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_KEYS = ("manifest_version", "tool", "label", "protocol", "files")


class ManifestError(ValueError):
    """A manifest that cannot be read: not JSON, or not a valid manifest."""


@dataclass(frozen=True)
class InstalledFile:
    """A file ``install`` wrote: its name in ``<prefix>/plugins``, and sha256."""

    path: str
    sha256: str


@dataclass(frozen=True)
class Manifest:
    """The content of ``<prefix>/plugins/.mmt-plugin/<label>.json``."""

    tool_version: str
    label: str
    proto_id: int
    name: str
    files: tuple[InstalledFile, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "files", tuple(sorted(self.files, key=lambda f: f.path)))

    def file(self, path: str) -> InstalledFile | None:
        """The entry of ``path``, or ``None``."""
        return next((f for f in self.files if f.path == path), None)

    def to_json(self) -> dict[str, Any]:
        """The JSON document, keys in schema order."""
        return {
            "manifest_version": MANIFEST_VERSION,
            "tool": {"name": "mmt-plugin", "version": self.tool_version},
            "label": self.label,
            "protocol": {"id": self.proto_id, "name": self.name},
            "files": [{"path": f.path, "sha256": f.sha256} for f in self.files],
        }

    def dumps(self) -> str:
        """The manifest's text: deterministic, ASCII, ending in a newline."""
        return json.dumps(self.to_json(), indent=2, ensure_ascii=True) + "\n"


def manifest_path(plugins: Path, label: str) -> Path:
    """``<plugins>/.mmt-plugin/<label>.json``."""
    return plugins / MANIFEST_DIR / f"{label}.json"


def _object(value: Any, where: str, keys: tuple[str, ...]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ManifestError(f"{where} is not an object")
    missing = [k for k in keys if k not in value]
    extra = sorted(set(value) - set(keys))
    if missing:
        raise ManifestError(f"{where} has no {', '.join(missing)}")
    if extra:
        raise ManifestError(f"{where} has unknown keys: {', '.join(extra)}")
    return value


def _text(value: Any, where: str, pattern: re.Pattern[str] | None = None) -> str:
    if not isinstance(value, str) or not value:
        raise ManifestError(f"{where} is not a non-empty string")
    if pattern is not None and not pattern.match(value):
        raise ManifestError(f"{where} is not valid: {value!r}")
    return value


def _file_name(value: Any, where: str) -> str:
    # A bare file name: uninstall removes <plugins>/<path>, never anything
    # outside the plugin directory.
    name = _text(value, where)
    if "/" in name or "\\" in name or "\x00" in name or name in (".", ".."):
        raise ManifestError(f"{where} is not a file name: {name!r}")
    return name


def parse_manifest(text: str, source: str) -> Manifest:
    """Parse and check a manifest; raise ``ManifestError`` with ``source``."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ManifestError(f"{source}: not JSON: {exc}") from None
    if isinstance(data, dict) and isinstance(data.get("manifest_version"), int):
        version = data["manifest_version"]
        if version > MANIFEST_VERSION:
            raise ManifestError(
                f"{source}: manifest_version {version} was written by a newer mmt-plugin"
                f" (this one reads {MANIFEST_VERSION})"
            )
    top = _object(data, source, _KEYS)
    version = top["manifest_version"]
    if isinstance(version, bool) or version != MANIFEST_VERSION:
        raise ManifestError(f"{source}: manifest_version is not {MANIFEST_VERSION}")
    tool = _object(top["tool"], f"{source}: tool", ("name", "version"))
    if tool["name"] != "mmt-plugin":
        raise ManifestError(f"{source}: tool.name is not mmt-plugin")
    protocol = _object(top["protocol"], f"{source}: protocol", ("id", "name"))
    pid = protocol["id"]
    if isinstance(pid, bool) or not isinstance(pid, int) or pid < 1:
        raise ManifestError(f"{source}: protocol.id is not a positive integer")
    if not isinstance(top["files"], list) or not top["files"]:
        raise ManifestError(f"{source}: files is not a non-empty array")
    files: list[InstalledFile] = []
    seen: set[str] = set()
    for n, item in enumerate(top["files"]):
        where = f"{source}: files[{n}]"
        entry = _object(item, where, ("path", "sha256"))
        path = _file_name(entry["path"], f"{where}.path")
        if path in seen:
            raise ManifestError(f"{where}: path {path!r} is listed twice")
        seen.add(path)
        files.append(InstalledFile(path, _text(entry["sha256"], f"{where}.sha256", _SHA256)))
    return Manifest(
        tool_version=_text(tool["version"], f"{source}: tool.version"),
        label=_text(top["label"], f"{source}: label", LABEL_PATTERN),
        proto_id=pid,
        name=_text(protocol["name"], f"{source}: protocol.name"),
        files=tuple(files),
    )


def read_manifest(path: Path, source: str | None = None) -> Manifest | None:
    """The manifest at ``path``, ``None`` when there is no file;
    ``ManifestError`` when it cannot be read or is not valid."""
    name = source or str(path)
    try:
        data = path.read_bytes()
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise ManifestError(f"{name}: cannot be read: {exc.strerror or exc}") from None
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        raise ManifestError(f"{name}: not UTF-8") from None
    return parse_manifest(text, name)


def read_manifests(plugins: Path) -> tuple[list[Manifest], list[str]]:
    """Every manifest of a plugin directory, by label, and the problems of
    those that cannot be read (one message each)."""
    directory = plugins / MANIFEST_DIR
    try:
        names = sorted(p.name for p in directory.iterdir() if p.name.endswith(".json"))
    except OSError:
        return [], []
    found: list[Manifest] = []
    problems: list[str] = []
    for name in names:
        try:
            manifest = read_manifest(directory / name)
        except ManifestError as exc:
            problems.append(str(exc))
            continue
        if manifest is None:  # removed meanwhile
            continue
        if f"{manifest.label}.json" != name:
            problems.append(f"{directory / name}: label {manifest.label!r} is not its file name")
            continue
        found.append(manifest)
    return found, problems


def load_schema() -> dict[str, Any]:
    """The manifest's JSON Schema."""
    schema: dict[str, Any] = json.loads(
        resources.files("mmt_plugin").joinpath(SCHEMA_RESOURCE).read_text("utf-8")
    )
    return schema


# --- the install prefix ------------------------------------------------------


@dataclass(frozen=True)
class InstallPrefix:
    """The install prefix (absolute) and where it came from: ``--prefix``,
    ``--system``, ``MMT_PLUGIN_PREFIX`` or ``default``."""

    path: Path
    source: str

    @property
    def plugins(self) -> Path:
        """``<prefix>/plugins``, where the plugin goes."""
        return self.path / "plugins"

    def to_json(self) -> dict[str, str]:
        return {"path": self.path.as_posix(), "source": self.source}


def _absolute(path: str) -> Path:
    return Path(os.path.normpath(os.path.join(os.getcwd(), os.path.expanduser(path))))


def default_prefix(env: Mapping[str, str]) -> Path:
    """``${XDG_DATA_HOME:-~/.local/share}/mmt`` (D11). A relative
    ``XDG_DATA_HOME`` is ignored, as the XDG base directory spec says."""
    data = env.get("XDG_DATA_HOME", "")
    if not data or not os.path.isabs(data):
        home = env.get("HOME", "") or str(Path.home())
        data = os.path.join(home, ".local", "share")
    return Path(os.path.normpath(data)) / "mmt"


def resolve_prefix(
    cli: str | None, system: bool, env: Mapping[str, str], *, system_prefix: str
) -> InstallPrefix:
    """The install prefix: ``--prefix`` > ``--system`` (``system_prefix``,
    ``/opt/mmt``) > ``MMT_PLUGIN_PREFIX`` > the default. Relative paths are
    made absolute against the current directory. Raises ``CliError``
    (``usage.*``) for ``--prefix`` with ``--system`` or an empty ``--prefix``.
    """
    if cli is not None and system:
        raise CliError(
            "usage.conflicting-options",
            "--prefix and --system cannot be used together",
            "--system is --prefix /opt/mmt: pass one of them",
        )
    if cli is not None:
        if not cli:
            raise CliError("usage.invalid-value", "--prefix is empty", "pass a directory")
        return InstallPrefix(_absolute(cli), "--prefix")
    if system:
        return InstallPrefix(Path(system_prefix), "--system")
    given = env.get(ENV_PREFIX, "")
    if given:
        return InstallPrefix(_absolute(given), ENV_PREFIX)
    return InstallPrefix(default_prefix(env), "default")


def writable(directory: Path) -> bool:
    """Whether ``directory`` can be created or written: it, or its nearest
    existing ancestor, is a directory this process may write into."""
    current = directory
    while True:
        if current.exists():
            return current.is_dir() and os.access(current, os.W_OK | os.X_OK)
        if current.parent == current:
            return False
        current = current.parent


def check_writable(prefix: InstallPrefix) -> None:
    """Raise ``sdk.prefix-not-writable`` (exit 4) unless ``<prefix>/plugins``
    can be written. The tool never uses sudo."""
    if not writable(prefix.plugins):
        raise CliError(
            "sdk.prefix-not-writable",
            f"{prefix.plugins.as_posix()} is not writable ({prefix.source})",
            "pass a prefix you can write with --prefix or MMT_PLUGIN_PREFIX;"
            " mmt-plugin never uses sudo",
        )
