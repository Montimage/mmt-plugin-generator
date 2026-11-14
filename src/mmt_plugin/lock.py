"""``plugin.lock``: what ``mmt-plugin generate`` last wrote (``docs/design/cli.md``,
sections 4 and 8).

The lock records the generator version, the SDK profile, the model's format
and sha256, and the sha256 of each generated file, by its path relative to
the lock's directory (POSIX separators, sorted). ``generate`` writes it last,
after every generated file, and reads it to tell a file it wrote (its sha256
is the lock's) from one that was edited by hand since.

Format: JSON, schema ``mmt_plugin/schemas/lock/v1/plugin-lock.json``
(``load_schema``), ``lock_version`` 1. ``dumps`` writes it with two-space
indentation, keys in schema order and a final newline, so the same inputs
give the same bytes; no timestamp and no absolute path is recorded.
``parse_lock`` repeats the schema's checks by hand (no run-time dependency on
a JSON Schema validator) and refuses a newer ``lock_version``.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any

__all__ = [
    "LOCK_NAME",
    "LOCK_VERSION",
    "SCHEMA_RESOURCE",
    "Lock",
    "LockError",
    "LockedFile",
    "load_schema",
    "parse_lock",
    "read_lock",
]

#: The lock's file name.
LOCK_NAME = "plugin.lock"

#: The ``lock_version`` this module writes and reads.
LOCK_VERSION = 1

#: The lock's JSON Schema, inside the package.
SCHEMA_RESOURCE = "schemas/lock/v1/plugin-lock.json"

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_FORMATS = ("pdl", "yaml")
_KEYS = ("lock_version", "generator", "sdk_profile", "model", "files")


class LockError(ValueError):
    """A lock that cannot be read: not JSON, or not a valid lock."""


@dataclass(frozen=True)
class LockedFile:
    """A generated file: its path relative to the lock's directory, and sha256."""

    path: str
    sha256: str


@dataclass(frozen=True)
class Lock:
    """The content of ``plugin.lock``."""

    generator: str
    generator_version: str
    sdk_profile: str
    model_format: str
    model_sha256: str
    files: tuple[LockedFile, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "files", tuple(sorted(self.files, key=lambda f: f.path)))

    def file(self, path: str) -> LockedFile | None:
        """The entry of ``path``, or ``None``."""
        for f in self.files:
            if f.path == path:
                return f
        return None

    def to_json(self) -> dict[str, Any]:
        """The JSON document, keys in schema order."""
        return {
            "lock_version": LOCK_VERSION,
            "generator": {"name": self.generator, "version": self.generator_version},
            "sdk_profile": self.sdk_profile,
            "model": {"format": self.model_format, "sha256": self.model_sha256},
            "files": [{"path": f.path, "sha256": f.sha256} for f in self.files],
        }

    def dumps(self) -> str:
        """The lock's text: deterministic, ASCII, ending in a newline."""
        return json.dumps(self.to_json(), indent=2, ensure_ascii=True) + "\n"


def _check_path(path: Any, where: str) -> str:
    if not isinstance(path, str) or not path:
        raise LockError(f"{where}: path is not a non-empty string")
    if path.startswith("/") or "\\" in path or "\x00" in path:
        raise LockError(f"{where}: path {path!r} is not a relative POSIX path")
    if any(part in ("", ".") for part in path.split("/")):
        raise LockError(f"{where}: path {path!r} is not normalised")
    return path


def _object(value: Any, where: str, keys: tuple[str, ...]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise LockError(f"{where} is not an object")
    missing = [k for k in keys if k not in value]
    extra = sorted(set(value) - set(keys))
    if missing:
        raise LockError(f"{where} has no {', '.join(missing)}")
    if extra:
        raise LockError(f"{where} has unknown keys: {', '.join(extra)}")
    return value


def _text(value: Any, where: str, pattern: re.Pattern[str] | None = None) -> str:
    if not isinstance(value, str) or not value:
        raise LockError(f"{where} is not a non-empty string")
    if pattern is not None and not pattern.match(value):
        raise LockError(f"{where} is not valid: {value!r}")
    return value


def parse_lock(text: str, source: str = LOCK_NAME) -> Lock:
    """Parse and check a lock; raise ``LockError`` with ``source`` in the message."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise LockError(f"{source}: not JSON: {exc}") from None
    if isinstance(data, dict) and isinstance(data.get("lock_version"), int):
        version = data["lock_version"]
        if version > LOCK_VERSION:
            raise LockError(
                f"{source}: lock_version {version} was written by a newer mmt-plugin"
                f" (this one reads {LOCK_VERSION})"
            )
    top = _object(data, source, _KEYS)
    if top["lock_version"] != LOCK_VERSION or isinstance(top["lock_version"], bool):
        raise LockError(f"{source}: lock_version is not {LOCK_VERSION}")
    gen = _object(top["generator"], f"{source}: generator", ("name", "version"))
    model = _object(top["model"], f"{source}: model", ("format", "sha256"))
    if model["format"] not in _FORMATS:
        raise LockError(f"{source}: model.format is not one of {', '.join(_FORMATS)}")
    if not isinstance(top["files"], list):
        raise LockError(f"{source}: files is not an array")
    files: list[LockedFile] = []
    seen: set[str] = set()
    for n, item in enumerate(top["files"]):
        where = f"{source}: files[{n}]"
        entry = _object(item, where, ("path", "sha256"))
        path = _check_path(entry["path"], where)
        if path in seen:
            raise LockError(f"{where}: path {path!r} is listed twice")
        seen.add(path)
        files.append(LockedFile(path, _text(entry["sha256"], f"{where}.sha256", _SHA256)))
    return Lock(
        generator=_text(gen["name"], f"{source}: generator.name"),
        generator_version=_text(gen["version"], f"{source}: generator.version"),
        sdk_profile=_text(top["sdk_profile"], f"{source}: sdk_profile"),
        model_format=model["format"],
        model_sha256=_text(model["sha256"], f"{source}: model.sha256", _SHA256),
        files=tuple(files),
    )


def read_lock(path: Path, source: str | None = None) -> Lock | None:
    """The lock at ``path``, ``None`` when there is no file; ``LockError``
    when it cannot be read or is not valid."""
    name = source or str(path)
    try:
        data = path.read_bytes()
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise LockError(f"{name}: cannot be read: {exc.strerror or exc}") from None
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        raise LockError(f"{name}: not UTF-8") from None
    return parse_lock(text, name)


def load_schema() -> dict[str, Any]:
    """The lock's JSON Schema."""
    schema: dict[str, Any] = json.loads(
        resources.files("mmt_plugin").joinpath(SCHEMA_RESOURCE).read_text("utf-8")
    )
    return schema
