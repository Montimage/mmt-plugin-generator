"""Shared fixtures: the test-only ``dummy`` command, a clean environment for
subprocesses, the envelope schema validator, and the guard that keeps every
test away from the host's SDK (``/opt/mmt`` and pkg-config's directories)."""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from collections.abc import Callable, Iterator, Mapping, Sequence
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from mmt_plugin import diagnostics
from mmt_plugin.commands import Command
from mmt_plugin.envelope import load_schema
from mmt_plugin.sdk.detect import DEFAULT_PREFIX, default_pkg_config_dirs

DUMMY_SCRIPT = Path(__file__).with_name("dummy_command.py")

#: Variables that change colors, widths or locales; unset for subprocesses.
_STYLE_VARS = (
    "FORCE_COLOR",
    "NO_COLOR",
    "CLICOLOR_FORCE",
    "COLORTERM",
    "COLUMNS",
    "LC_ALL",
    "LC_CTYPE",
    "PYTHON_COLORS",
)


#: Paths no test may touch: the host's SDK and where its mmt-dpi.pc would be.
SYSTEM_SDK_PATHS = (DEFAULT_PREFIX, *default_pkg_config_dirs())


class SystemSdkAccessed(AssertionError):
    """A test read the host's SDK. An AssertionError, so that the
    ``os.path.isfile`` family, which turns OSError into False, lets it through."""


def system_sdk_path(path: object) -> str | None:
    """``path`` made absolute if it is one of ``SYSTEM_SDK_PATHS`` or below one."""
    if isinstance(path, int) or not isinstance(path, (str, bytes, os.PathLike)):
        return None
    text = os.path.abspath(os.fsdecode(path))
    for root in SYSTEM_SDK_PATHS:
        if text == root or text.startswith(root.rstrip("/") + "/"):
            return text
    return None


_guard = {"on": False}


def _audit(event: str, args: tuple[Any, ...]) -> None:
    # open() and os.open() ("open"), directory listings; stat has no audit
    # event, so os.stat and os.lstat are wrapped below.
    if _guard["on"] and event in ("open", "os.listdir", "os.scandir") and args:
        hit = system_sdk_path(args[0])
        if hit is not None:
            raise SystemSdkAccessed(f"a test opened {hit}: inject the SDK paths instead")


sys.addaudithook(_audit)


@pytest.fixture(autouse=True)
def forbid_system_sdk(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Fail any test that opens, lists or stats the host's SDK paths."""
    for name in ("stat", "lstat"):
        real = getattr(os, name)

        def guarded(path: Any, *args: Any, _real: Any = real, **kwargs: Any) -> Any:
            hit = system_sdk_path(path)
            if hit is not None:
                raise SystemSdkAccessed(f"a test looked at {hit}: inject the SDK paths instead")
            return _real(path, *args, **kwargs)

        monkeypatch.setattr(os, name, guarded)
    _guard["on"] = True
    try:
        yield
    finally:
        _guard["on"] = False


def _load_dummy() -> ModuleType:
    spec = importlib.util.spec_from_file_location("dummy_command", DUMMY_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_DUMMY = _load_dummy()


@pytest.fixture
def dummy(monkeypatch: pytest.MonkeyPatch) -> Iterator[Command]:
    """The ``dummy`` command, with its test-only codes registered."""
    monkeypatch.setattr(diagnostics, "CODES", _DUMMY.codes_with_test_codes())
    command: Command = _DUMMY.DummyCommand()
    yield command


@pytest.fixture
def validate_envelope() -> Callable[[Any], None]:
    """Validate a parsed envelope against the shipped schema."""
    validator = Draft202012Validator(load_schema())

    def check(doc: Any) -> None:
        validator.validate(doc)

    return check


def _clean_env(**overrides: str) -> dict[str, str]:
    """``os.environ`` without the style variables, plus ``overrides``."""
    env = {k: v for k, v in os.environ.items() if k not in _STYLE_VARS}
    env.update({"TERM": "xterm-256color", "LANG": "C.UTF-8"})
    env.update(overrides)
    return env


@pytest.fixture
def clean_env() -> Callable[..., dict[str, str]]:
    """Build a subprocess environment: no style variables, ``TERM=xterm-256color``,
    ``LANG=C.UTF-8``, plus the keyword overrides."""
    return _clean_env


@pytest.fixture
def run_cli() -> Callable[..., subprocess.CompletedProcess[bytes]]:
    """Run the CLI with the ``dummy`` command in a subprocess; bytes in and out."""

    def run(
        args: Sequence[str],
        *,
        env: Mapping[str, str] | None = None,
        module: bool = False,
        timeout: float = 60,
    ) -> subprocess.CompletedProcess[bytes]:
        prefix = ["-m", "mmt_plugin"] if module else [str(DUMMY_SCRIPT)]
        return subprocess.run(
            [sys.executable, *prefix, *args],
            capture_output=True,
            stdin=subprocess.DEVNULL,
            env=_clean_env() if env is None else dict(env),
            timeout=timeout,
            check=False,
        )

    return run


# --- fake SDKs ------------------------------------------------------------


def _make_prefix(
    root: Path, *, version: str | None = "1.10.2", marker: bool = True, core: bool = True
) -> Path:
    """An SDK prefix under ``root``: a stub ``dpi/include/mmt_log.h`` (unless
    ``marker`` is false) and an ``mmt_core.h`` with a ``VERSION`` macro laid
    out as in mmt-dpi 1.10.2 (none when ``version`` is None; no file at all
    when ``core`` is false)."""
    include = root / "dpi" / "include"
    include.mkdir(parents=True, exist_ok=True)
    if marker:
        (include / "mmt_log.h").write_text("#ifndef MMT_LOG_H_\n#define MMT_LOG_H_\n#endif\n")
    if core:
        macro = "" if version is None else f'#define VERSION "{version}" ///< SDK version\n'
        (include / "mmt_core.h").write_text(
            f'/* #define VERSION "0.0" in a comment */\n#ifndef VERSION\n{macro}#endif\n'
        )
    return root


def _make_pc(directory: Path, includedir: str, *, prefix_var: bool = True) -> Path:
    """An ``mmt-dpi.pc`` in ``directory``, shaped like the published one."""
    directory.mkdir(parents=True, exist_ok=True)
    head = f"prefix={includedir.rsplit('/dpi/include', 1)[0]}\n" if prefix_var else ""
    inc = (
        "${prefix}/dpi/include"
        if prefix_var and includedir.endswith("/dpi/include")
        else includedir
    )
    pc = directory / "mmt-dpi.pc"
    pc.write_text(
        f"{head}libdir=/opt/mmt/dpi/lib\nincludedir={inc}\n"
        "plugindir=/opt/mmt/plugins\nrpath=-Wl,-rpath,${libdir}\n\n"
        "Name: mmt-dpi\nDescription: MMT-DPI deep packet inspection library\n"
        "Version: 1.10.2\nLibs: -L${libdir} ${rpath} -lmmt_core\nCflags: -I${includedir}\n"
    )
    return pc


MakePrefix = Callable[..., Path]
MakePc = Callable[..., Path]


@pytest.fixture
def make_prefix() -> MakePrefix:
    """Build a fake SDK prefix: ``make_prefix(root, version=..., marker=..., core=...)``."""
    return _make_prefix


@pytest.fixture
def make_pc() -> MakePc:
    """Write a fake ``mmt-dpi.pc``: ``make_pc(directory, includedir, prefix_var=...)``."""
    return _make_pc
