"""The skills directory: where it is, its digest, the read-only snapshot
the agent reads, and the restore of the source when a run changed it."""

from __future__ import annotations

import hashlib
import os
import shutil
import stat
from collections.abc import Mapping
from pathlib import Path

from mmt_plugin.exitcodes import ExitCode
from mmt_plugin_agent.errors import AgentError

__all__ = [
    "ENV_SKILLS",
    "IMAGE_SKILLS",
    "SKILL_NAME",
    "digest",
    "find_skills_dir",
    "make_snapshot",
    "remove_tree",
    "resolve_skills_dir",
    "restore",
    "snapshot_root",
    "tree_files",
]

SKILL_NAME = "mmt-plugin-generator"
ENV_SKILLS = "MMT_PLUGIN_SKILLS"
#: Where the agent image keeps the skills, root-owned and read-only.
IMAGE_SKILLS = Path("/opt/mmt-plugin-skills")
#: A checkout: src/mmt_plugin_agent/ -> the repository's skills/.
_CHECKOUT_SKILLS = Path(__file__).resolve().parents[2] / "skills"


def _holds_skill(path: Path) -> bool:
    return (path / SKILL_NAME / "SKILL.md").is_file()


def find_skills_dir(
    explicit: str | os.PathLike[str] | None = None, environ: Mapping[str, str] | None = None
) -> Path | None:
    """The skills directory: ``explicit``, else ``MMT_PLUGIN_SKILLS``, else
    this checkout's ``skills/``, else the image's; None when the one chosen
    (or every default) holds no ``mmt-plugin-generator/SKILL.md``."""
    env = os.environ if environ is None else environ
    given = explicit if explicit is not None else env.get(ENV_SKILLS) or None
    if given is not None:
        path = Path(given).resolve()
        return path if _holds_skill(path) else None
    for path in (_CHECKOUT_SKILLS, IMAGE_SKILLS):
        if _holds_skill(path):
            return path.resolve()
    return None


def resolve_skills_dir(explicit: str | os.PathLike[str] | None = None) -> Path:
    found = find_skills_dir(explicit)
    if found is None:
        where = explicit or os.environ.get(ENV_SKILLS) or f"a checkout or {IMAGE_SKILLS}"
        raise AgentError(
            ExitCode.SDK,
            "agent.skills-not-found",
            f"no {SKILL_NAME}/SKILL.md in {where}",
            f"pass --skills DIR (or set {ENV_SKILLS}) to a directory holding {SKILL_NAME}/",
        )
    return found


def _skipped(rel: str) -> bool:
    parts = rel.split("/")
    return "__pycache__" in parts or rel.endswith(".pyc")


def tree_files(root: Path) -> dict[str, bytes]:
    """Every regular file under ``root`` by relative path, without byte code."""
    files: dict[str, bytes] = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d != "__pycache__")
        for name in sorted(filenames):
            path = Path(dirpath) / name
            rel = path.relative_to(root).as_posix()
            if _skipped(rel) or path.is_symlink() or not path.is_file():
                continue
            files[rel] = path.read_bytes()
    return files


def digest(files: Mapping[str, bytes]) -> str:
    """The sha256 of a tree: each path with the sha256 of its bytes, sorted."""
    h = hashlib.sha256()
    for rel in sorted(files):
        h.update(f"{rel}\0{hashlib.sha256(files[rel]).hexdigest()}\n".encode())
    return h.hexdigest()


def snapshot_root(environ: Mapping[str, str] | None = None) -> Path:
    """Where snapshots go: outside every work folder, in the user's cache."""
    env = os.environ if environ is None else environ
    cache = env.get("XDG_CACHE_HOME") or str(Path(env.get("HOME", "~")).expanduser() / ".cache")
    return Path(cache).resolve() / "mmt-plugin-agent"


def remove_tree(path: Path) -> None:
    """Remove a read-only tree."""
    if not path.exists():
        return
    for dirpath, _, _ in os.walk(path):
        os.chmod(dirpath, stat.S_IRWXU)
    shutil.rmtree(path)


def make_snapshot(files: Mapping[str, bytes], key: str, root: Path | None = None) -> Path:
    """A read-only copy of ``files`` (files 0444, directories 0555) at
    ``<root>/skills-<key>``, made again when it differs."""
    dest = (root or snapshot_root()) / f"skills-{key}"
    if dest.is_dir() and digest(tree_files(dest)) == digest(files):
        return dest
    remove_tree(dest)
    dest.mkdir(parents=True)
    for rel, data in files.items():
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        target.chmod(0o444)
    for dirpath, _, _ in os.walk(dest, topdown=False):
        os.chmod(dirpath, 0o555)
    return dest


def restore(source: Path, files: Mapping[str, bytes]) -> list[str]:
    """Make ``source`` hold ``files`` again; the paths it changed, added
    back or removed."""
    now = tree_files(source)
    changed = []
    for rel in sorted(set(now) | set(files)):
        if now.get(rel) == files.get(rel):
            continue
        changed.append(rel)
        target = source / rel
        if rel in files:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(files[rel])
        else:
            target.unlink()
    return changed
