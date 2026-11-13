"""Tests for ``mmt_plugin.fsio``: atomic writes reported by content hash."""

from __future__ import annotations

import hashlib
import os
import stat
from pathlib import Path

import pytest

from mmt_plugin.fsio import Action, sha256_file, write_atomic


def _files(directory: Path) -> list[str]:
    return sorted(p.name for p in directory.iterdir())


def test_create_update_unchanged(tmp_path: Path) -> None:
    target = tmp_path / "out" / "a.c"
    created = write_atomic(target, "int x;\n")
    assert created.action is Action.CREATED
    assert created.sha256 == hashlib.sha256(b"int x;\n").hexdigest() == sha256_file(target)
    assert target.read_bytes() == b"int x;\n"
    assert write_atomic(target, b"int x;\n").action is Action.UNCHANGED
    assert write_atomic(target, "int y;\n").action is Action.UPDATED
    assert target.read_text() == "int y;\n"
    assert _files(target.parent) == ["a.c"]


def test_unchanged_keeps_the_mtime(tmp_path: Path) -> None:
    target = tmp_path / "a.h"
    write_atomic(target, "x")
    os.utime(target, ns=(1_000_000_000_000_000_000, 1_000_000_000_000_000_000))
    inode = target.stat().st_ino
    assert write_atomic(target, "x").action is Action.UNCHANGED
    assert target.stat().st_mtime_ns == 1_000_000_000_000_000_000
    assert target.stat().st_ino == inode


def test_dry_run_writes_nothing(tmp_path: Path) -> None:
    target = tmp_path / "new" / "a.c"
    assert write_atomic(target, "x", dry_run=True).action is Action.WOULD_CREATE
    assert not target.parent.exists()
    existing = tmp_path / "b.c"
    existing.write_text("old")
    assert write_atomic(existing, "new", dry_run=True).action is Action.WOULD_UPDATE
    assert write_atomic(existing, "old", dry_run=True).action is Action.UNCHANGED
    assert existing.read_text() == "old"
    assert _files(tmp_path) == ["b.c"]


@pytest.mark.parametrize("failure", [OSError(28, "No space left on device"), KeyboardInterrupt()])
@pytest.mark.parametrize("where", ["fsync", "replace"])
def test_an_interrupted_write_leaves_the_old_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: BaseException, where: str
) -> None:
    target = tmp_path / "a.c"
    target.write_text("old content")

    def fail(*args: object) -> None:
        raise failure

    monkeypatch.setattr(os, where, fail)
    with pytest.raises(type(failure)):
        write_atomic(target, "new content that is never seen")
    assert target.read_text() == "old content"
    assert _files(tmp_path) == ["a.c"], "the temporary file was left behind"


def test_the_new_content_is_complete_before_the_rename(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "a.c"
    target.write_text("old")
    seen: list[tuple[str, bytes, str]] = []
    real_replace = os.replace

    def spy(src: str, dst: str) -> None:
        seen.append((Path(src).name, Path(src).read_bytes(), target.read_text()))
        real_replace(src, dst)

    monkeypatch.setattr(os, "replace", spy)
    write_atomic(target, "new")
    ((tmp_name, tmp_content, target_during),) = seen
    assert tmp_name.startswith(".a.c.") and tmp_name.endswith(".tmp")
    assert (tmp_content, target_during) == (b"new", "old")


def test_permissions(tmp_path: Path) -> None:
    old_umask = os.umask(0o022)
    try:
        new = write_atomic(tmp_path / "new.c", "x").path
        assert stat.S_IMODE(new.stat().st_mode) == 0o644
    finally:
        os.umask(old_umask)
    existing = tmp_path / "run.sh"
    existing.write_text("old")
    existing.chmod(0o750)
    write_atomic(existing, "new")
    assert stat.S_IMODE(existing.stat().st_mode) == 0o750
    assert write_atomic(existing, "new", mode=0o700).action is Action.UPDATED
    assert stat.S_IMODE(existing.stat().st_mode) == 0o700
    assert write_atomic(existing, "new", mode=0o700).action is Action.UNCHANGED


def test_a_symlink_is_replaced_by_a_file(tmp_path: Path) -> None:
    real = tmp_path / "real.c"
    real.write_text("same")
    link = tmp_path / "link.c"
    link.symlink_to(real)
    assert write_atomic(link, "same").action is Action.UPDATED
    assert not link.is_symlink() and link.read_text() == "same"
    assert real.read_text() == "same"


def test_sha256_file_of_a_missing_file(tmp_path: Path) -> None:
    assert sha256_file(tmp_path / "missing") is None
