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


#: How ``tree_files`` records a symbolic link: this prefix, then its target.
_LINK = b"\0mmt-plugin-agent symlink\0"


def _skipped(rel: str) -> bool:
    parts = rel.split("/")
    return "__pycache__" in parts or rel.endswith(".pyc")


def tree_files(root: Path) -> dict[str, bytes]:
    """Every regular file under ``root`` by relative path, without byte code,
    and every symbolic link (to a file or a directory, never followed) as
    ``_LINK`` and its target, so that a link the agent plants changes the
    digest."""
    files: dict[str, bytes] = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for name in sorted([*dirnames, *filenames]):
            path = Path(dirpath) / name
            rel = path.relative_to(root).as_posix()
            if _skipped(rel):
                continue
            if path.is_symlink():
                files[rel] = _LINK + os.fsencode(os.readlink(path))
            elif path.is_file():
                files[rel] = path.read_bytes()
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
    return files


def _place(target: Path, data: bytes) -> None:
    """Write one entry of ``tree_files`` at ``target``, whose parents are
    real directories: a file, or a link when ``data`` records one."""
    if data.startswith(_LINK):
        os.symlink(os.fsdecode(data[len(_LINK) :]), target)
    else:
        target.write_bytes(data)


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
        _place(target, data)
        if not target.is_symlink():
            target.chmod(0o444)
    for dirpath, _, _ in os.walk(dest, topdown=False):
        os.chmod(dirpath, 0o555)
    return dest


def _remove(path: Path) -> None:
    """Remove a file, a link (never what it points to) or a directory."""
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)


def _real_parents(source: Path, rel: str) -> Path:
    """``source / rel`` with every parent below ``source`` a real directory:
    a link or a file in the way is removed, so nothing is written through
    a link the agent planted."""
    current = source
    for part in rel.split("/")[:-1]:
        current = current / part
        if current.is_symlink() or (current.exists() and not current.is_dir()):
            _remove(current)
        current.mkdir(exist_ok=True)
    return source / rel


def restore(source: Path, files: Mapping[str, bytes]) -> list[str]:
    """Make ``source`` hold ``files`` again; the paths it changed, added
    back or removed. Links are removed or written as links, never followed."""
    now = tree_files(source)
    changed = sorted(rel for rel in set(now) | set(files) if now.get(rel) != files.get(rel))
    for rel in sorted((r for r in changed if r not in files), reverse=True):
        target = source / rel
        if target.is_symlink() or target.exists():
            _remove(target)
    for rel in (r for r in changed if r in files):
        target = _real_parents(source, rel)
        if target.is_symlink() or target.exists():
            _remove(target)
        _place(target, files[rel])
    return changed
