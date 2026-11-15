"""Every example command of the user documentation runs (plan task T5.2, #29).

In the user docs (``USER_DOCS``), each ``sh`` block is marked on the line
before its fence:

- ``<!-- doc:run no-sdk -->``: runs without an SDK;
- ``<!-- doc:run sdk -->``: needs mmt-dpi, the prefix in ``MMT_BASE`` and the
  compiler in ``CC``;
- ``<!-- doc:run install -->``: installs the tool with ``uv tool install``
  (needs the network, or uv's cache);
- ``<!-- doc:skip REASON -->``: not run, for REASON (it needs an mmt-dpi
  checkout, root, or a download).

A shell block (``sh``, ``bash``, ``shell`` or ``console``) with no marker,
a fenced block with no language, or a runnable block that names ``sudo``,
``--system`` or ``/opt/mmt`` fails the test: nothing here may need root or
touch the host's SDK.
The blocks of one page run in order, each with ``bash -euo pipefail`` from
the root of a sandbox: a copy of the tracked tree (so ``examples/`` and
``plugins/`` are there), with ``HOME`` and ``XDG_DATA_HOME`` inside it and
an ``mmt-plugin`` on ``PATH`` that runs this checkout's package. A block
keeps the files of the blocks before it, not their ``cd`` or variables.

``test_the_commands_run_without_an_sdk`` runs the ``no-sdk`` blocks, and the
``install`` ones too with ``MMT_DOCS_INSTALL=1`` (CI's Python 3.12 job), so
no ``no-sdk`` block may depend on an ``sdk`` one. Its ``MMT_BASE`` is an
empty directory, so a command that looks for an SDK exits 4 instead of
finding the host's (``/opt/mmt``, pkg-config's ``mmt-dpi.pc``): a ``no-sdk``
block pins the profile (``--sdk-profile``, ``sdk.profile``) and passes
``--no-sdk`` to ``validate``. With ``MMT_GOLDEN_SDK``
(and ``MMT_GOLDEN_CC``), ``test_the_commands_run_with_an_sdk`` runs every
block that is not skipped, in order: CI's "Generated code" job, where
``MMT_REQUIRE_GOLDEN_COMPILE=1`` makes a missing SDK fail instead of skip::

    MMT_GOLDEN_SDK=<dir>/opt/mmt MMT_GOLDEN_CC=gcc uv run pytest tests/unit/docs/test_commands.py
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import pytest

from .mdtext import ROOT, Block, blocks

#: The pages whose commands run: what a user reads.
USER_DOCS = ("README.md", "docs/user-guide.md", "docs/migration.md")

#: Fenced blocks of these languages are commands and need a marker.
SHELL_INFOS = frozenset({"sh", "bash", "shell", "console"})

#: The other languages a user doc may fence; any other one is an error, so
#: that no command hides behind an unexpected language (``zsh``, ``Bash``).
OTHER_INFOS = frozenset({"yaml", "json", "c", "text", "pdl"})

KINDS = ("no-sdk", "sdk", "install")

_MARKER = re.compile(r"^<!-- doc:(run|skip) ?(.*?) -->$")

#: What no runnable block may contain: root, or the host's SDK.
_FORBIDDEN = re.compile(r"(?<![\w-])(sudo|--system)(?![\w-])|/opt/mmt")

SDK_ENV = "MMT_GOLDEN_SDK"
CC_ENV = "MMT_GOLDEN_CC"
REQUIRE_ENV = "MMT_REQUIRE_GOLDEN_COMPILE"
INSTALL_ENV = "MMT_DOCS_INSTALL"

#: Variables of the caller that would change what a block does.
_DROPPED = re.compile(
    r"^(MMT_.*|CC|CFLAGS|LDFLAGS|XDG_.*|PKG_CONFIG_.*|UV_TOOL_.*|VIRTUAL_ENV|PYTHONPATH|"
    r"FORCE_COLOR|NO_COLOR|CLICOLOR_FORCE|COLUMNS|LC_.*)$"
)


@dataclass(frozen=True)
class Command:
    """A marked shell block: ``kind`` is a member of ``KINDS`` or ``skip``."""

    page: str
    line: int
    kind: str
    reason: str
    text: str


class MarkerError(ValueError):
    pass


def commands(page: str, text: str) -> list[Command]:
    """The shell blocks of ``text`` with their markers; ``MarkerError`` for a
    block with no language, a shell block with no marker, or a bad marker."""
    found: list[Command] = []
    for block in blocks(text):
        where = f"{page}:{block.line}"
        if not block.info:
            raise MarkerError(f"{where}: a fenced block with no language (sh, yaml, text, ...)")
        language = block.info.split()[0]
        if language not in SHELL_INFOS | OTHER_INFOS:
            raise MarkerError(
                f"{where}: a {language} block: use sh for commands, or one of "
                + ", ".join(sorted(OTHER_INFOS))
            )
        marker = _marker_before(text, block)
        if language not in SHELL_INFOS:
            if marker is not None:
                raise MarkerError(f"{where}: a doc: marker on a {language} block")
            continue
        if marker is None:
            raise MarkerError(f"{where}: an {language} block without a doc:run or doc:skip marker")
        verb, arg = marker
        if verb == "run" and arg not in KINDS:
            raise MarkerError(f"{where}: doc:run {arg!r}: expected one of {', '.join(KINDS)}")
        if verb == "skip" and not arg:
            raise MarkerError(f"{where}: doc:skip needs a reason")
        if verb == "run":
            bad = _FORBIDDEN.search(block.text)
            if bad is not None:
                raise MarkerError(
                    f"{where}: a runnable block names {bad.group(0)!r}: use doc:skip"
                )
        kind = arg if verb == "run" else "skip"
        found.append(Command(page, block.line, kind, arg if verb == "skip" else "", block.text))
    return found


def _marker_before(text: str, block: Block) -> tuple[str, str] | None:
    before = text[: block.start].rstrip().splitlines()
    if not before:
        return None
    match = _MARKER.match(before[-1].strip())
    return None if match is None else (match.group(1), match.group(2).strip())


def page_commands(page: str) -> list[Command]:
    return commands(page, (ROOT / page).read_text(encoding="utf-8"))


# --- the sandbox ----------------------------------------------------------


def _tracked() -> list[str]:
    out = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "-z"], capture_output=True, check=True
    ).stdout
    return [name for name in out.decode("utf-8").split("\0") if name]


def make_sandbox(root: Path) -> Path:
    """A copy of the tracked tree under ``root``/``work``, a home and a
    ``mmt-plugin`` shim; returns the work directory."""
    work = root / "work"
    for name in _tracked():
        source = ROOT / name
        if source.is_symlink() or not source.is_file():
            continue
        dest = work / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)
    (root / "home").mkdir()
    (root / "empty").mkdir()
    write_shim(root / "bin")
    return work


def write_shim(directory: Path) -> None:
    """An ``mmt-plugin`` in ``directory`` that runs this checkout's package
    (``-I``: not the block's directory on ``sys.path``)."""
    directory.mkdir(parents=True, exist_ok=True)
    shim = directory / "mmt-plugin"
    shim.write_text(
        f'#!/bin/sh\nexec "{sys.executable}" -I -m mmt_plugin "$@"\n', encoding="utf-8"
    )
    shim.chmod(0o755)


def block_env(root: Path, *, sdk: Path | None, cc: str | None) -> dict[str, str]:
    """The environment of every block: the caller's, without what changes a
    command's result, with the sandbox's home and tools first on ``PATH``."""
    env = {k: v for k, v in os.environ.items() if not _DROPPED.match(k)}
    home = root / "home"
    cache = os.environ.get("UV_CACHE_DIR") or str(Path.home() / ".cache" / "uv")
    env.update(
        {
            "HOME": str(home),
            "XDG_DATA_HOME": str(home / ".local" / "share"),
            "XDG_CONFIG_HOME": str(home / ".config"),
            # No mmt-dpi.pc from the host: the SDK is MMT_BASE or nothing.
            "PKG_CONFIG_LIBDIR": str(root / "empty"),
            "UV_CACHE_DIR": cache,
            "UV_TOOL_DIR": str(root / "uv-tools"),
            "UV_TOOL_BIN_DIR": str(root / "uv-bin"),
            "PATH": os.pathsep.join(
                [str(root / "uv-bin"), str(root / "bin"), env.get("PATH", os.defpath)]
            ),
            "LANG": "C.UTF-8",
            "NO_COLOR": "1",
        }
    )
    # Without an SDK, MMT_BASE is an empty directory: looking for an SDK is
    # sdk.invalid-prefix (exit 4), never a fall-through to the host's.
    no_sdk = root / "no-sdk"
    no_sdk.mkdir(exist_ok=True)
    env["MMT_BASE"] = str(no_sdk if sdk is None else sdk)
    if cc is not None:
        env["CC"] = cc
    return env


def run_commands(cmds: Iterable[Command], work: Path, env: dict[str, str]) -> None:
    """Run each block in order; fail at the first one that exits non-zero."""
    for cmd in cmds:
        result = subprocess.run(
            ["bash", "-euo", "pipefail", "-c", cmd.text],
            cwd=work,
            env=env,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=900,
            check=False,
        )
        if result.returncode != 0:
            pytest.fail(
                f"{cmd.page}:{cmd.line}: the {cmd.kind} block exited {result.returncode}\n"
                f"--- block\n{cmd.text}--- stdout\n{result.stdout[-4000:]}"
                f"--- stderr\n{result.stderr[-4000:]}"
            )


def _kinds_without_sdk() -> set[str]:
    return {"no-sdk", "install"} if os.environ.get(INSTALL_ENV) == "1" else {"no-sdk"}


# --- the tests ------------------------------------------------------------


@pytest.mark.parametrize("page", USER_DOCS)
def test_every_shell_block_is_marked(page: str) -> None:
    cmds = page_commands(page)
    assert any(c.kind != "skip" for c in cmds), f"{page} has no runnable block"


@pytest.mark.parametrize("page", USER_DOCS)
def test_the_commands_run_without_an_sdk(page: str, tmp_path: Path) -> None:
    kinds = _kinds_without_sdk()
    cmds = [c for c in page_commands(page) if c.kind in kinds]
    if not cmds:
        pytest.skip(f"{page} has no block that runs without an SDK")
    work = make_sandbox(tmp_path)
    run_commands(cmds, work, block_env(tmp_path, sdk=None, cc=None))


@pytest.mark.parametrize("page", USER_DOCS)
def test_the_commands_run_with_an_sdk(page: str, tmp_path: Path) -> None:
    cmds = page_commands(page)
    if not any(c.kind == "sdk" for c in cmds):
        pytest.skip(f"{page} has no block that needs an SDK")
    prefix = os.environ.get(SDK_ENV, "")
    if not prefix:
        if os.environ.get(REQUIRE_ENV) == "1":
            pytest.fail(f"{REQUIRE_ENV}=1 but {SDK_ENV} is not set")
        pytest.skip(f"{SDK_ENV} is not set")
    kinds = _kinds_without_sdk() | {"sdk"}
    work = make_sandbox(tmp_path)
    env = block_env(tmp_path, sdk=Path(prefix).resolve(), cc=os.environ.get(CC_ENV) or "gcc")
    run_commands([c for c in cmds if c.kind in kinds], work, env)


# --- the checks themselves -----------------------------------------------


def test_markers_are_required_and_read() -> None:
    text = (
        "<!-- doc:run no-sdk -->\n```sh\nmmt-plugin --version\n```\n\n"
        "<!-- doc:skip needs root -->\n\n```sh\nsudo true\n```\n"
        "```yaml\nschema: 1\n```\n"
    )
    assert commands("p.md", text) == [
        Command("p.md", 2, "no-sdk", "", "mmt-plugin --version\n"),
        Command("p.md", 8, "skip", "needs root", "sudo true\n"),
    ]
    with pytest.raises(MarkerError, match=r"p.md:1: an sh block without"):
        commands("p.md", "```sh\nls\n```\n")
    with pytest.raises(MarkerError, match=r"p.md:1: a fenced block with no language"):
        commands("p.md", "```\nls\n```\n")
    with pytest.raises(MarkerError, match=r"doc:run 'sdkk'"):
        commands("p.md", "<!-- doc:run sdkk -->\n```sh\nls\n```\n")
    with pytest.raises(MarkerError, match=r"doc:skip needs a reason"):
        commands("p.md", "<!-- doc:skip -->\n```sh\nls\n```\n")
    with pytest.raises(MarkerError, match=r"a doc: marker on a yaml block"):
        commands("p.md", "<!-- doc:run sdk -->\n```yaml\na: 1\n```\n")
    with pytest.raises(MarkerError, match=r"p.md:1: an bash block without"):
        commands("p.md", "```bash\nls\n```\n")
    for text in ("sudo make install", "mmt-plugin install --system", "ls /opt/mmt/plugins"):
        with pytest.raises(MarkerError, match=r"a runnable block names"):
            commands("p.md", f"<!-- doc:run sdk -->\n```sh\n{text}\n```\n")
    assert commands("p.md", "<!-- doc:skip root -->\n```sh\nsudo make install\n```\n")
    assert commands("p.md", "<!-- doc:run sdk -->\n```sh\nmmt-plugin --system-x\n```\n")
    for info in ("zsh", "Bash", "shell-session"):
        with pytest.raises(MarkerError, match=rf"a {info} block: use sh"):
            commands("p.md", f"```{info}\nls\n```\n")


def test_an_indented_fence_is_a_block() -> None:
    text = (
        "1. Install:\n\n    - nested\n\n      ```sh\n      sudo make install\n      ```\n\n"
        "2. Step\n\n    <!-- doc:run no-sdk -->\n    ```sh\n    mkdir -p a\n      ls a\n    ```\n"
    )
    with pytest.raises(MarkerError, match=r"p.md:5: an sh block without"):
        commands("p.md", text)
    fixed = text.replace(
        "      ```sh\n      sudo", "      <!-- doc:skip root -->\n      ```sh\n      sudo"
    )
    assert [(c.kind, c.text) for c in commands("p.md", fixed)] == [
        ("skip", "sudo make install\n"),
        ("no-sdk", "mkdir -p a\n  ls a\n"),
    ]


def test_a_crlf_page_reads_as_lf(tmp_path: Path) -> None:
    text = "# T\r\n\r\n<!-- doc:run no-sdk -->\r\n```sh\r\necho a > out\r\n```\r\n"
    cmds = commands("p.md", text)
    assert cmds == [Command("p.md", 4, "no-sdk", "", "echo a > out\n")]
    (tmp_path / "home").mkdir()
    run_commands(cmds, tmp_path, block_env(tmp_path, sdk=None, cc=None))
    assert (tmp_path / "out").read_bytes() == b"a\n"


def test_a_failing_block_fails_with_its_place(tmp_path: Path) -> None:
    (tmp_path / "home").mkdir()
    env = block_env(tmp_path, sdk=None, cc=None)
    ok = Command("p.md", 3, "no-sdk", "", "touch made\n")
    bad = Command("p.md", 9, "no-sdk", "", "test -f made\nfalse\necho never\n")
    with pytest.raises(pytest.fail.Exception, match=r"p.md:9: the no-sdk block exited 1"):
        run_commands([ok, bad], tmp_path, env)
    assert (tmp_path / "made").is_file()


def test_the_blocks_see_no_host_sdk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MMT_BASE", "/somewhere")
    monkeypatch.setenv("PKG_CONFIG_PATH", "/somewhere")
    monkeypatch.setenv("CC", "tcc")
    monkeypatch.setenv("MMT_PLUGIN_PREFIX", "/somewhere")
    monkeypatch.setenv("MMT_DPI_PLUGINS_DIR", "/somewhere")
    monkeypatch.setenv("MMT_PLUGIN_SDK_PROFILE", "0.0.1")
    env = block_env(tmp_path, sdk=None, cc=None)
    for name in (
        "PKG_CONFIG_PATH",
        "CC",
        "MMT_PLUGIN_PREFIX",
        "MMT_DPI_PLUGINS_DIR",
        "MMT_PLUGIN_SDK_PROFILE",
    ):
        assert name not in env
    assert env["MMT_BASE"] == str(tmp_path / "no-sdk")
    assert env["PKG_CONFIG_LIBDIR"] == str(tmp_path / "empty")
    assert env["HOME"] == str(tmp_path / "home")


def test_a_no_sdk_block_never_finds_the_host_sdk(tmp_path: Path) -> None:
    (tmp_path / "home").mkdir()
    write_shim(tmp_path / "bin")
    env = block_env(tmp_path, sdk=None, cc=None)
    result = subprocess.run(
        ["mmt-plugin", "--json", "doctor"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 4, result.stdout
    assert json.loads(result.stdout)["error"]["code"] == "sdk.invalid-prefix"
