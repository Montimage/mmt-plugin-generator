"""``mmt_plugin.sdk.registry``: the run-time registry of the installed plugins.

The plumbing (plugin directory, exclusion, the child process and its report)
is tested with a stand-in probe script; the real probe runs against an
extracted mmt-dpi prefix when ``MMT_GOLDEN_SDK`` is set (as for
``tests/unit/generate/test_compile.py``), and skips otherwise, unless
``MMT_REQUIRE_GOLDEN_COMPILE=1`` (CI) makes it fail. ``validate`` runs
against that SDK too.
"""

from __future__ import annotations

import json
import os
import re
import textwrap
from pathlib import Path

import pytest

from mmt_plugin.cli import main
from mmt_plugin.commands.validate import ValidateCommand
from mmt_plugin.sdk import registry as registry_module
from mmt_plugin.sdk.detect import Sdk, SdkSource, find_sdk
from mmt_plugin.sdk.profile import get_bundled
from mmt_plugin.sdk.registry import (
    PLUGINS_DIR_ENV,
    RegisteredProtocol,
    Registry,
    RegistryError,
    core_library,
    plugin_dir,
    read_registry,
)
from mmt_plugin.sdk.resolve import find_bundled

#: A stand-in probe: reports one protocol per plugin file it is given (the
#: names of $MMT_DPI_PLUGINS_DIR), so the tests see what the real probe
#: would load. MODE selects a failure.
FAKE_PROBE = textwrap.dedent(
    """
    import json, os, sys, time
    mode = os.environ.get("FAKE_MODE", "")
    plugins = sorted(os.listdir(os.environ["MMT_DPI_PLUGINS_DIR"]))
    if mode == "crash":
        os.kill(os.getpid(), 9)
    if mode == "hang":
        time.sleep(30)
    if mode == "garbage":
        print("not json")
    elif mode == "fail":
        print(json.dumps({"ok": False, "error": "init_extraction() failed"}))
    else:
        protocols = [[900 + i, p[:-3]] for i, p in enumerate(plugins)]
        print(json.dumps({"ok": True, "protocols": protocols,
                          "argv": sys.argv[1:], "cwd": os.getcwd()}))
    """
)


def fake_sdk(tmp_path: Path, plugins: tuple[str, ...] = ("libmmt_tcpip.so",)) -> Sdk:
    prefix = tmp_path / "sdk"
    lib = prefix / "dpi" / "lib"
    lib.mkdir(parents=True)
    (lib / "libmmt_core.so.1.10.2").write_bytes(b"\x7fELF")
    (prefix / "plugins").mkdir()
    for name in plugins:
        (prefix / "plugins" / name).write_bytes(b"\x7fELF")
    return Sdk(str(prefix), SdkSource.CLI, "1.10.2")


@pytest.fixture
def probe(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "probe.py"
    path.write_text(FAKE_PROBE)
    monkeypatch.setattr(registry_module, "_PROBE", path)
    return path


def env(**extra: str) -> dict[str, str]:
    base = {k: v for k, v in os.environ.items() if k != PLUGINS_DIR_ENV}
    return {**base, **extra}


def test_registry_lookups_compare_names_case_insensitively() -> None:
    reg = Registry("/p", ("a.so",), (RegisteredProtocol(625, "ndn"),))
    assert reg.by_id(625) == RegisteredProtocol(625, "ndn")
    assert reg.by_id(626) is None
    assert reg.by_name("NDN") == RegisteredProtocol(625, "ndn")
    assert reg.by_name("nd") is None


def test_the_plugin_dir_is_the_env_override_or_the_prefix(tmp_path: Path) -> None:
    sdk = Sdk(str(tmp_path), SdkSource.CLI, None)
    assert plugin_dir(sdk, {}) == f"{tmp_path}/plugins"
    assert plugin_dir(sdk, {PLUGINS_DIR_ENV: ""}) == f"{tmp_path}/plugins"
    assert plugin_dir(sdk, {PLUGINS_DIR_ENV: "/x/y/"}) == "/x/y"


def test_core_library_prefers_the_newest_versioned_file(tmp_path: Path) -> None:
    lib = tmp_path / "dpi" / "lib"
    sdk = Sdk(str(tmp_path), SdkSource.CLI, None)
    assert core_library(sdk) is None
    lib.mkdir(parents=True)
    assert core_library(sdk) is None
    (lib / "libmmt_core.so").write_bytes(b"")
    assert core_library(sdk) == str(lib / "libmmt_core.so")
    for version in ("1.9.10", "1.10.2"):
        (lib / f"libmmt_core.so.{version}").write_bytes(b"")
    # A dangling link (the package's absolute /opt/mmt links) is ignored.
    (lib / "libmmt_core.so.1").symlink_to("/opt/mmt/nowhere/libmmt_core.so.1.10.2")
    assert core_library(sdk) == str(lib / "libmmt_core.so.1.10.2")


def test_the_probe_loads_every_plugin_but_the_excluded_one(tmp_path: Path, probe: Path) -> None:
    sdk = fake_sdk(tmp_path, ("libmmt_tcpip.so", "mmtp_x.so", "Zeta.so", "notes.txt"))
    reg = read_registry(sdk, env=env(), max_id=1000, exclude="mmtp_x.so")
    assert reg.plugin_dir == f"{sdk.prefix}/plugins"
    # C (byte) order: upper case first; not a .so: not a plugin.
    assert reg.plugins == ("Zeta.so", "libmmt_tcpip.so")
    assert reg.protocols == (
        RegisteredProtocol(900, "Zeta"),
        RegisteredProtocol(901, "libmmt_tcpip"),
    )


def test_the_env_plugin_dir_replaces_the_prefix_one(tmp_path: Path, probe: Path) -> None:
    sdk = fake_sdk(tmp_path)
    other = tmp_path / "mine"
    other.mkdir()
    (other / "mine.so").write_bytes(b"")
    reg = read_registry(sdk, env=env(**{PLUGINS_DIR_ENV: str(other)}), max_id=1000)
    assert reg.plugin_dir == str(other)
    assert reg.plugins == ("mine.so",)


@pytest.mark.parametrize(
    ("mode", "message"),
    [
        ("fail", "init_extraction() failed with the plugins of "),
        ("garbage", "failed (exit code 0)"),
        ("crash", "failed (signal 9)"),
    ],
)
def test_probe_failures_are_registry_errors(
    tmp_path: Path, probe: Path, mode: str, message: str
) -> None:
    sdk = fake_sdk(tmp_path)
    with pytest.raises(RegistryError, match=re.escape(message)):
        read_registry(sdk, env=env(FAKE_MODE=mode), max_id=1000)


def test_a_hanging_probe_times_out(tmp_path: Path, probe: Path) -> None:
    sdk = fake_sdk(tmp_path)
    with pytest.raises(RegistryError, match=r"took more than 0\.5 s"):
        read_registry(sdk, env=env(FAKE_MODE="hang"), max_id=1000, timeout=0.5)


def test_no_core_library_or_plugin_dir(tmp_path: Path, probe: Path) -> None:
    sdk = fake_sdk(tmp_path)
    for f in (Path(sdk.prefix) / "plugins").iterdir():
        f.unlink()
    (Path(sdk.prefix) / "plugins").rmdir()
    with pytest.raises(RegistryError, match="cannot list the plugin directory"):
        read_registry(sdk, env=env(), max_id=1000)
    (Path(sdk.prefix) / "dpi" / "lib" / "libmmt_core.so.1.10.2").unlink()
    with pytest.raises(RegistryError, match="no libmmt_core shared object"):
        read_registry(sdk, env=env(), max_id=1000)


# --- against a real SDK -------------------------------------------------------


@pytest.fixture
def real_sdk() -> Sdk:
    prefix = os.environ.get("MMT_GOLDEN_SDK", "")
    if not prefix:
        if os.environ.get("MMT_REQUIRE_GOLDEN_COMPILE") == "1":
            pytest.fail("MMT_REQUIRE_GOLDEN_COMPILE=1 but MMT_GOLDEN_SDK is not set")
        pytest.skip("MMT_GOLDEN_SDK is not set (an extracted mmt-dpi prefix)")
    sdk = find_sdk(prefix, {})
    assert sdk is not None
    return sdk


def test_the_real_registry_has_the_sdk_protocols(real_sdk: Sdk) -> None:
    reg = read_registry(real_sdk, env=env(), max_id=1000)
    assert "libmmt_tcpip.so" in reg.plugins
    assert reg.by_name("TCP") == RegisteredProtocol(354, "tcp")
    assert reg.by_id(625) == RegisteredProtocol(625, "ndn")
    assert reg.by_id(980) is None


def test_the_real_registry_is_the_profile(real_sdk: Sdk) -> None:
    # The run-time cross-check of the profile's ids (#50): with every plugin
    # of the package loaded, mmt-dpi registers exactly the ids of
    # parents.ids and the protocol_id constants, each under its recorded
    # alias. An id without an alias (no PROTO_<X>_ALIAS in its header, such
    # as PROTO_INT) registers a name no listed alias takes. So not_ids, which
    # the headers' completeness check trusts, hides no registered id.
    version = find_bundled(real_sdk.version or "")
    if version is None:
        pytest.skip(f"no profile is bundled for mmt-dpi {real_sdk.version}")
    profile = get_bundled(version)
    assert profile is not None
    max_id = profile.constant("PROTO_MAX_IDENTIFIER").value
    assert max_id is not None
    reg = read_registry(real_sdk, env=env(), max_id=max_id)
    expected_plugins = {
        "libmmt_business_app.so",
        "libmmt_tcpip.so",
        "libmmt_tdicom.so",
        "libmmt_tmobile.so",
    }
    if not expected_plugins <= set(reg.plugins):
        pytest.skip(f"this SDK has only {', '.join(reg.plugins)}")
    listed = {p.id: p.alias for p in profile.parents.protocols()}
    for c in profile.constants:
        if c.group == "protocol_id" and c.value is not None:
            listed[c.value] = None  # the core's pseudo-protocols
    registered = {p.id: p.name for p in reg.protocols}
    assert sorted(set(registered) - set(listed)) == [], "registered, not in the profile"
    assert sorted(set(listed) - set(registered)) == [], "in the profile, not registered"
    wrong = {
        pid: (name, alias)
        for pid, name in registered.items()
        if (alias := listed[pid]) is not None and name.casefold() != alias.casefold()
    }
    assert wrong == {}
    aliases = {a.casefold() for a in listed.values() if a is not None}
    unaliased = {pid: registered[pid] for pid, alias in listed.items() if alias is None}
    assert not {n.casefold() for n in unaliased.values()} & aliases, unaliased


def test_the_real_registry_without_a_plugin(real_sdk: Sdk) -> None:
    every = read_registry(real_sdk, env=env(), max_id=1000)
    if "libmmt_tdicom.so" not in every.plugins:
        pytest.skip("this SDK has no libmmt_tdicom.so")
    dicom = every.by_name("dicom")
    assert dicom is not None
    without = read_registry(real_sdk, env=env(), max_id=1000, exclude="libmmt_tdicom.so")
    assert "libmmt_tdicom.so" not in without.plugins
    assert without.by_id(dicom.id) is None
    assert without.by_name("tcp") is not None


@pytest.mark.parametrize(
    ("model", "code", "failed"),
    [
        ("ndn", 0, []),  # ndn_example, 980: free, next to the built-in ndn (625)
        ("tpkt", 3, ["id-free", "name-free"]),  # 636 is PROTO_LOOPBACK, TPKT is built in
    ],
)
def test_validate_against_the_real_sdk(
    real_sdk: Sdk,
    model: str,
    code: int,
    failed: list[str],
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(PLUGINS_DIR_ENV, raising=False)
    path = Path(__file__).parents[1] / "corpus" / "models" / model / "model.pdl"
    argv = ["--json", "validate", str(path), "--sdk", real_sdk.prefix]
    assert main(argv, commands=[ValidateCommand()]) == code
    doc = json.loads(capsys.readouterr().out)
    checks = {c["id"]: c for c in doc["result"]["checks"]}
    assert [k for k, c in checks.items() if c["status"] == "fail"] == failed
    if not failed:
        assert checks["id-free"]["status"] == checks["name-free"]["status"] == "pass"
        assert "installed plugin" in checks["id-free"]["detail"]
