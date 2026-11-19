"""``install``, ``doctor`` and ``uninstall`` against a real mmt-dpi SDK
(plan T2.5: "tests in a temporary prefix; no sudo in CI; a load test shows
mmt-dpi 1.10.2 finds a plugin installed at the default prefix").

mmt-dpi 1.10.2 scans one plugin directory: ``MMT_DPI_PLUGINS_DIR`` when set,
else the one compiled into ``libmmt_core`` (``/opt/mmt/plugins`` in the
published package; ``src/mmt_core/src/plugins_engine.c``). A corpus model is
built, installed at the default prefix ``${XDG_DATA_HOME}/mmt`` (a temporary
``XDG_DATA_HOME``), and loaded by an unmodified ``libmmt_core`` with
``MMT_DPI_PLUGINS_DIR=<prefix>/plugins`` (``mmt_plugin.sdk.registry``), alone
and next to the SDK's own plugins linked into that directory; ``doctor``
then reports the directory as scanned. Nothing is written outside
``tmp_path``: the SDK is an extracted package (never ``/opt/mmt``)::

    MMT_GOLDEN_SDK=<dir>/opt/mmt MMT_GOLDEN_CC=gcc uv run pytest tests/unit/install/test_sdk.py

Without ``MMT_GOLDEN_SDK`` the tests skip, unless
``MMT_REQUIRE_GOLDEN_COMPILE=1`` (CI's "Generated code" job) makes them fail.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any

import pytest

from mmt_plugin.cli import main
from mmt_plugin.codegen import scaffold
from mmt_plugin.commands.generate import make_generation
from mmt_plugin.sdk.detect import require_sdk
from mmt_plugin.sdk.registry import compiled_plugin_dir, core_library, read_registry
from mmt_plugin.sdk.resolve import resolve_profile

SDK_ENV = "MMT_GOLDEN_SDK"
CC_ENV = "MMT_GOLDEN_CC"
REQUIRE_ENV = "MMT_REQUIRE_GOLDEN_COMPILE"
CORPUS = Path(__file__).resolve().parents[2] / "corpus" / "models"
MODEL = "pdl_bitfields"


def _skip_or_fail(why: str) -> None:
    if os.environ.get(REQUIRE_ENV) == "1":
        pytest.fail(f"{REQUIRE_ENV}=1 but {why}")
    pytest.skip(why)


def _sdk() -> Path:
    prefix = os.environ.get(SDK_ENV, "")
    if not prefix:
        _skip_or_fail(f"{SDK_ENV} is not set (an extracted mmt-dpi prefix)")
    return Path(prefix)


def _cc() -> str:
    cc = os.environ.get(CC_ENV, "gcc")
    if shutil.which(cc) is None:
        _skip_or_fail(f"{cc} is not installed")
    return cc


def _json(capsys: pytest.CaptureFixture[str], *argv: str) -> tuple[int, dict[str, Any]]:
    code = main(["--json", *argv])
    doc: dict[str, Any] = json.loads(capsys.readouterr().out)
    return code, doc


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A project for corpus model ``pdl_bitfields`` with its scaffold; the
    default install prefix is ``tmp_path/xdg/mmt``."""
    sdk, _ = _sdk(), _cc()
    choice = resolve_profile(None, {}, None, require_sdk(str(sdk), {}))
    data = (CORPUS / MODEL / "model.pdl").read_bytes()
    generation, _, error = make_generation("model.pdl", data, choice)
    assert generation is not None, error
    work = tmp_path / "project"
    (work / "src").mkdir(parents=True)
    (work / "model.pdl").write_bytes(data)
    impl = scaffold(generation, choice.profile)
    (work / impl.path).write_text(impl.text)
    monkeypatch.chdir(work)
    for name in ("MMT_PLUGIN_PREFIX", "MMT_DPI_PLUGINS_DIR", "MMT_PLUGIN_SDK_PROFILE", "MMT_BASE"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    return work


def test_the_package_scans_its_compiled_in_directory_only() -> None:
    # The published package is built with MMT_BASE=/opt/mmt: an extracted
    # copy still scans /opt/mmt/plugins, never its own prefix or ~/.local.
    sdk = require_sdk(str(_sdk()), {})
    core = core_library(sdk)
    assert core is not None
    assert compiled_plugin_dir(core) == "/opt/mmt/plugins"


def test_a_plugin_installed_at_the_default_prefix_loads(
    project: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    sdk_path, cc = _sdk(), _cc()
    code, doc = _json(capsys, "install", "model.pdl", "--sdk", str(sdk_path), "--cc", cc)
    assert code == 0, doc["error"]
    plugins = tmp_path / "xdg" / "mmt" / "plugins"
    assert doc["context"]["prefix"]["source"] == "default"
    assert (plugins / "mmtp_pdl_bitfields.so").is_file()
    pid = doc["result"]["protocol"]["id"]

    sdk = require_sdk(str(sdk_path), {})
    max_id = 1000
    # An unmodified libmmt_core loads it from the default prefix through
    # MMT_DPI_PLUGINS_DIR, alone ...
    env = {**os.environ, "MMT_DPI_PLUGINS_DIR": str(plugins)}
    registry = read_registry(sdk, env=env, max_id=max_id)
    assert registry.plugins == ("mmtp_pdl_bitfields.so",)
    assert registry.by_id(pid) is not None
    # ... and next to the SDK's plugins linked into the same directory, as
    # doctor's hint says (the variable replaces the compiled-in directory).
    for so in sorted((sdk_path / "plugins").glob("*.so")):
        (plugins / so.name).symlink_to(so)
    registry = read_registry(sdk, env=env, max_id=max_id)
    assert registry.plugins[-1] == "mmtp_pdl_bitfields.so"
    assert registry.by_id(pid) is not None
    assert registry.by_name("ethernet") is not None

    monkeypatch.setenv("MMT_DPI_PLUGINS_DIR", str(plugins))
    code, doc = _json(capsys, "doctor", "--sdk", str(sdk_path), "--cc", cc, "--model", "model.pdl")
    assert code == 0, doc["error"]
    checks = {c["id"]: c["status"] for c in doc["result"]["checks"]}
    assert checks == dict.fromkeys(checks, "pass"), doc["result"]["checks"]
    assert doc["result"]["plugin_dirs"]["install"]["scanned"] is True

    code, doc = _json(capsys, "uninstall")
    assert code == 0, doc["error"]
    assert doc["result"]["removed"] == [(plugins / "mmtp_pdl_bitfields.so").as_posix()]
    registry = read_registry(sdk, env=env, max_id=max_id)
    assert registry.by_id(pid) is None
    # The SDK's own plugins, linked by hand, are not install's to remove.
    assert (plugins / "libmmt_tcpip.so").is_symlink()
