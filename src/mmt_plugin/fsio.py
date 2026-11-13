"""Atomic file writes, reported by content hash (``docs/design/cli.md``, section 8).

``write_atomic`` writes the new content to a temporary file in the target's
directory, fsyncs it, then ``os.replace``s it over the target, so a reader (or
an interrupted run) sees either the old file or the new one, never a partial
one. A file whose content already matches is not rewritten, so its mtime is
kept. Staleness is decided by sha256, never by mtime.
"""

from __future__ import annotations

import contextlib
import hashlib
import os
import stat
import tempfile
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

__all__ = ["Action", "WriteResult", "sha256_bytes", "sha256_file", "write_atomic"]

_CHUNK = 1 << 16


class Action(str, Enum):
    """What a write did, or (with ``dry_run``) would do."""

    CREATED = "created"
    UPDATED = "updated"
    UNCHANGED = "unchanged"
    WOULD_CREATE = "would-create"
    WOULD_UPDATE = "would-update"


@dataclass(frozen=True)
class WriteResult:
    """The outcome of one ``write_atomic`` call."""

    path: Path
    action: Action
    sha256: str


def sha256_bytes(data: bytes) -> str:
    """The hex sha256 of ``data``."""
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str | None:
    """The hex sha256 of a regular file's content, or ``None`` if there is none."""
    digest = hashlib.sha256()
    try:
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(_CHUNK), b""):
                digest.update(chunk)
    except FileNotFoundError:
        return None
    return digest.hexdigest()


def _default_mode() -> int:
    # The mode open() would give a new file: 0o666 minus the umask.
    umask = os.umask(0)
    os.umask(umask)
    return 0o666 & ~umask


def _fsync_dir(directory: Path) -> None:
    # Make the rename itself durable. Some file systems refuse; that is fine.
    try:
        fd = os.open(directory, os.O_RDONLY)
    except OSError:
        return
    try:
        with contextlib.suppress(OSError):
            os.fsync(fd)
    finally:
        os.close(fd)


def write_atomic(
    path: Path | str, data: bytes | str, *, dry_run: bool = False, mode: int | None = None
) -> WriteResult:
    """Write ``data`` to ``path`` atomically and report what changed.

    ``str`` data is encoded as UTF-8, newlines unchanged. Missing parent
    directories are created (not with ``dry_run``). A new file gets ``mode``,
    else the umask default; an existing file keeps its permission bits unless
    ``mode`` is given. If ``path`` is a symbolic link, the link is replaced by
    a regular file. On any exception, including ``KeyboardInterrupt``, the
    temporary file is removed and the target is left as it was.
    """
    target = Path(path)
    content = data.encode("utf-8") if isinstance(data, str) else data
    new_hash = sha256_bytes(content)
    old_hash = sha256_file(target) if not target.is_symlink() else None
    exists = old_hash is not None or target.is_symlink()

    if old_hash == new_hash and (mode is None or stat.S_IMODE(target.stat().st_mode) == mode):
        return WriteResult(target, Action.UNCHANGED, new_hash)
    if dry_run:
        return WriteResult(
            target, Action.WOULD_UPDATE if exists else Action.WOULD_CREATE, new_hash
        )

    if mode is None:
        mode = stat.S_IMODE(target.stat().st_mode) if old_hash is not None else _default_mode()
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=target.parent, prefix=f".{target.name}.", suffix=".tmp")
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(content)
            f.flush()
            os.fchmod(f.fileno(), mode)
            os.fsync(f.fileno())
        os.replace(tmp, target)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    _fsync_dir(target.parent)
    return WriteResult(target, Action.UPDATED if exists else Action.CREATED, new_hash)
