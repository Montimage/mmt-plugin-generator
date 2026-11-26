"""The skills tree's integrity coverage (R6): the digest records each
entry's kind, executable bit and directories, a planted special file is
never silently ignored, and restore puts the mode back."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from mmt_plugin.exitcodes import ExitCode
from mmt_plugin_agent.errors import AgentError
from mmt_plugin_agent.skills import TreeEntry, digest, make_snapshot, restore, tree_files


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    root = tmp_path / "skills"
    (root / "sub").mkdir(parents=True)
    (root / "SKILL.md").write_text("# skill\n")
    script = root / "sub" / "run.py"
    script.write_text("print(1)\n")
    script.chmod(0o755)
    return root


def test_the_digest_records_kind_mode_and_directories(tree: Path) -> None:
    entries = tree_files(tree)
    assert entries["sub"] == TreeEntry("dir")
    assert entries["sub/run.py"].kind == "file" and entries["sub/run.py"].executable
    assert not entries["SKILL.md"].executable
    base = digest(entries)
    (tree / "SKILL.md").chmod(0o755)
    assert digest(tree_files(tree)) != base, "a chmod changes the digest"
    (tree / "SKILL.md").chmod(0o644)
    (tree / "empty").mkdir()
    assert digest(tree_files(tree)) != base, "an added directory changes the digest"
    (tree / "empty").rmdir()
    assert digest(tree_files(tree)) == base


def test_a_planted_special_file_changes_the_digest(tree: Path) -> None:
    base = digest(tree_files(tree))
    os.mkfifo(tree / "planted")
    entries = tree_files(tree)
    assert entries["planted"] == TreeEntry("special", b"fifo")
    assert digest(entries) != base


def test_restore_removes_a_planted_special_file(tree: Path) -> None:
    original = tree_files(tree)
    os.mkfifo(tree / "planted")
    changed = restore(tree, original)
    assert "planted" in changed
    assert not os.path.lexists(tree / "planted")
    assert digest(tree_files(tree)) == digest(original)


def test_restore_brings_back_the_executable_bit(tree: Path) -> None:
    original = tree_files(tree)
    script = tree / "sub" / "run.py"
    script.chmod(0o644)
    changed = restore(tree, original)
    assert "sub/run.py" in changed
    assert script.stat().st_mode & 0o100
    assert digest(tree_files(tree)) == digest(original)


def test_a_special_file_in_the_source_fails_the_snapshot(tree: Path, tmp_path: Path) -> None:
    os.mkfifo(tree / "fifo")
    with pytest.raises(AgentError) as caught:
        make_snapshot(tree_files(tree), "k", root=tmp_path / "snapshots")
    assert caught.value.code == "agent.skills-special"
    assert caught.value.exit_code is ExitCode.SDK


def test_the_snapshot_keeps_the_executable_bit_and_its_digest(tree: Path, tmp_path: Path) -> None:
    entries = tree_files(tree)
    snapshot = make_snapshot(entries, "k", root=tmp_path / "snapshots")
    copied = snapshot / "sub" / "run.py"
    mode = copied.stat().st_mode
    assert mode & 0o100, "the copy stays executable"
    assert not mode & 0o222, "the copy is read-only"
    assert digest(tree_files(snapshot)) == digest(entries), "the copy is made once"
    again = make_snapshot(entries, "k", root=tmp_path / "snapshots")
    assert again == snapshot
