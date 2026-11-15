"""``tests/check_release_tag.sh``: which tag may release which commit (T5.3, #30).

The release workflow runs it on a tag push, where it is the only check
between a tag and a publish, and in every dry run on the branch a release
would come from. Here it runs in a scratch repository whose
``refs/remotes/origin/main`` and ``refs/remotes/origin/dev`` are set by hand:
``main`` <- ``dev`` <- ``feature``, so ``dev`` holds ``main`` and the feature
commit is on neither.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "tests" / "check_release_tag.sh"

pytestmark = pytest.mark.skipif(
    shutil.which("git") is None or shutil.which("bash") is None, reason="needs git and bash"
)


def _git(repo: Path, *args: str) -> str:
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.invalid",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.invalid",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
    }
    done = subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True, env=env
    )
    return done.stdout.strip()


@pytest.fixture(scope="module")
def repo(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("tagrepo")
    _git(path, "init", "-q")
    commits = {}
    for name in ("main", "dev", "feature"):
        _git(path, "commit", "-q", "--allow-empty", "-m", name)
        commits[name] = _git(path, "rev-parse", "HEAD")
    _git(path, "update-ref", "refs/remotes/origin/main", commits["main"])
    _git(path, "update-ref", "refs/remotes/origin/dev", commits["dev"])
    for name, sha in commits.items():
        _git(path, "tag", f"at-{name}", sha)
    return path


def _check(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(SCRIPT), *args], cwd=repo, capture_output=True, text=True, check=False
    )


@pytest.mark.parametrize(
    ("tag", "version", "commit", "prerelease"),
    [
        ("v0.1.0", "0.1.0", "at-main", "false"),
        ("v1.2.3.post1", "1.2.3.post1", "at-main", "false"),
        ("v0.1.0rc1", "0.1.0rc1", "at-main", "true"),
        ("v0.1.0rc1", "0.1.0rc1", "at-dev", "true"),
        ("v0.2.0.dev0", "0.2.0.dev0", "at-dev", "true"),
        ("v0.2.0a1", "0.2.0a1", "at-dev", "true"),
        ("v0.2.0b3", "0.2.0b3", "at-dev", "true"),
    ],
)
def test_a_tag_may_release(
    repo: Path, tag: str, version: str, commit: str, prerelease: str
) -> None:
    done = _check(repo, tag, version, commit)
    assert done.returncode == 0, done.stderr
    assert done.stdout == f"prerelease={prerelease}\n"
    assert done.stderr.startswith("PASS: ")


@pytest.mark.parametrize(
    ("tag", "version", "commit", "message"),
    [
        ("v0.1.1", "0.1.0", "at-main", "the tag v0.1.1 is not v0.1.0"),
        ("0.1.0", "0.1.0", "at-main", "the tag 0.1.0 is not v0.1.0"),
        ("v0.1.0", "", "at-main", "empty version"),
        ("v0.1.0", "0.1.0", "at-dev", "is not on origin/main"),
        ("v0.1.0", "0.1.0", "at-feature", "is not on origin/main"),
        ("v0.1.0rc1", "0.1.0rc1", "at-feature", "on neither origin/main nor origin/dev"),
        ("v0.1.0", "0.1.0", "no-such-ref", "no commit no-such-ref"),
    ],
)
def test_a_tag_may_not_release(
    repo: Path, tag: str, version: str, commit: str, message: str
) -> None:
    done = _check(repo, tag, version, commit)
    assert done.returncode == 1
    assert done.stdout == ""
    assert done.stderr.startswith("FAIL: ")
    assert message in done.stderr


def test_the_commit_defaults_to_head(repo: Path) -> None:
    # HEAD is the feature commit.
    assert _check(repo, "v0.1.0rc1", "0.1.0rc1").returncode == 1


def test_a_missing_remote_branch_is_not_an_ancestor(tmp_path: Path) -> None:
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "commit", "-q", "--allow-empty", "-m", "only")
    done = _check(tmp_path, "v0.1.0", "0.1.0")
    assert done.returncode == 1
    assert "is not on origin/main" in done.stderr


def test_the_usage_is_checked(repo: Path) -> None:
    for args in ((), ("v0.1.0",), ("v0.1.0", "0.1.0", "HEAD", "extra")):
        done = _check(repo, *args)
        assert done.returncode == 1
        assert "usage:" in done.stderr
