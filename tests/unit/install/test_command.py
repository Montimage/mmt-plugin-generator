"""``mmt-plugin install`` and ``uninstall`` with a fake SDK and a fake
compiler (``tests/unit/build/fakes.py``), every write in a temporary prefix:
the prefix precedence, ``--system`` (pointed at a temporary directory), a
prefix that cannot be written, the manifest, idempotency, refused targets
and ``--force``, ``--dry-run``, ``--no-deps``, clashes with other installed
plugins, and uninstall's kept, missing and not-installed files
(``docs/design/cli.md``, sections 4, 5, 6, 8 and 9). ``test_sdk.py`` loads an
installed plugin with a real mmt-dpi."""

from __future__ import annotations

import importlib.util
import json
import os
import stat
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from mmt_plugin import manifest as manifest_module
from mmt_plugin import schemas
from mmt_plugin.cli import main
from mmt_plugin.codegen import scaffold
from mmt_plugin.commands.generate import make_generation
from mmt_plugin.commands.install import InstallCommand, UninstallCommand, project_label
from mmt_plugin.diagnostics import CliError
from mmt_plugin.manifest import Manifest, default_prefix, read_manifest, resolve_prefix
from mmt_plugin.sdk.resolve import resolve_profile


def _load_fakes() -> Any:
    # build's fake SDK and compiler (tests/unit/build/fakes.py).
    spec = importlib.util.spec_from_file_location(
        "install_build_fakes", Path(__file__).parents[1] / "build" / "fakes.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


fakes = _load_fakes()

MODEL = """Protocol {
    Properties { label = "fakeproto" id = "991" encoding = "network" }
    Attributes {
        attribute { alias="kind" data_type="MMT_U8_DATA" data_len="1" offset="0" scope="packet" }
    }
}
"""
SO = "mmtp_fakeproto.so"

Run = Callable[..., tuple[int, dict[str, Any]]]


def _scaffold(text: str) -> tuple[str, str]:
    choice = resolve_profile("1.10.2", {}, None, None)
    generation, _, error = make_generation("model.pdl", text.encode(), choice)
    assert generation is not None, error
    impl = scaffold(generation, choice.profile)
    return impl.path, impl.text


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The current directory: ``model.pdl`` and its scaffold; ``HOME`` and
    ``XDG_DATA_HOME`` point into ``tmp_path``, so the default prefix is a
    temporary one too."""
    work = tmp_path / "project"
    (work / "src").mkdir(parents=True)
    (work / "model.pdl").write_text(MODEL)
    path, text = _scaffold(MODEL)
    (work / path).write_text(text)
    monkeypatch.chdir(work)
    for name in ("MMT_PLUGIN_SDK_PROFILE", "MMT_BASE", "CC", "MMT_PLUGIN_PREFIX", "FAKE_CC_LOG"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    return work


@pytest.fixture
def sdk(tmp_path: Path) -> Path:
    return Path(fakes.fake_sdk(tmp_path / "sdk"))


@pytest.fixture
def cc(tmp_path: Path) -> Path:
    return Path(fakes.fake_cc(tmp_path / "bin"))


@pytest.fixture
def system(tmp_path: Path) -> Path:
    """``--system``'s prefix in these tests (never ``/opt/mmt``)."""
    return tmp_path / "system"


def _runner(
    name: str, command: Any, capsys: pytest.CaptureFixture[str], extra: list[str]
) -> Callable[..., tuple[int, Any]]:
    envelope = Draft202012Validator(schemas.load_cli_schema(schemas.ENVELOPE))
    result = Draft202012Validator(schemas.result_schema(name))

    def go(*args: str) -> tuple[int, Any]:
        code = main(["--json", name, *extra, *args], commands=[command])
        out = capsys.readouterr()
        assert out.err == ""
        doc: dict[str, Any] = json.loads(out.out)
        envelope.validate(doc)
        assert doc["exit_code"] == code
        if doc["result"] is not None:
            result.validate(doc["result"])
        return code, doc

    return go


@pytest.fixture
def install(
    tmp_path: Path, sdk: Path, cc: Path, system: Path, capsys: pytest.CaptureFixture[str]
) -> Run:
    """``mmt-plugin --json install model.pdl --sdk SDK --cc CC ARGS``."""
    command = InstallCommand(
        pkg_config_dirs=[], default_prefix=str(tmp_path / "no-sdk"), system_prefix=str(system)
    )
    return _runner("install", command, capsys, ["model.pdl", "--sdk", str(sdk), "--cc", str(cc)])


@pytest.fixture
def uninstall(system: Path, capsys: pytest.CaptureFixture[str]) -> Run:
    """``mmt-plugin --json uninstall ARGS``."""
    return _runner("uninstall", UninstallCommand(system_prefix=str(system)), capsys, [])


def _manifest(plugins: Path, label: str = "fakeproto") -> dict[str, Any]:
    doc: dict[str, Any] = json.loads((plugins / ".mmt-plugin" / f"{label}.json").read_text())
    return doc


# --- the prefix --------------------------------------------------------------


def test_prefix_precedence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    env = {"MMT_PLUGIN_PREFIX": "envp", "XDG_DATA_HOME": "/x", "HOME": "/h"}
    sys_prefix = str(tmp_path / "sys")
    assert resolve_prefix("cli", False, env, system_prefix=sys_prefix).path == tmp_path / "cli"
    assert resolve_prefix("cli", False, env, system_prefix=sys_prefix).source == "--prefix"
    chosen = resolve_prefix(None, True, env, system_prefix=sys_prefix)
    assert (chosen.path, chosen.source) == (Path(sys_prefix), "--system")
    chosen = resolve_prefix(None, False, env, system_prefix=sys_prefix)
    assert (chosen.path, chosen.source) == (tmp_path / "envp", "MMT_PLUGIN_PREFIX")
    chosen = resolve_prefix(None, False, {"XDG_DATA_HOME": "/x"}, system_prefix=sys_prefix)
    assert (chosen.path, chosen.source) == (Path("/x/mmt"), "default")
    assert chosen.plugins == Path("/x/mmt/plugins")
    # A relative XDG_DATA_HOME is ignored (XDG base directory spec).
    assert default_prefix({"XDG_DATA_HOME": "rel", "HOME": "/h"}) == Path("/h/.local/share/mmt")
    assert default_prefix({"HOME": "/h"}) == Path("/h/.local/share/mmt")
    with pytest.raises(CliError) as exc:
        resolve_prefix("p", True, env, system_prefix=sys_prefix)
    assert exc.value.code == "usage.conflicting-options"
    with pytest.raises(CliError) as exc:
        resolve_prefix("", False, env, system_prefix=sys_prefix)
    assert exc.value.code == "usage.invalid-value"


def test_install_defaults_to_the_user_prefix(project: Path, install: Run, tmp_path: Path) -> None:
    code, doc = install()
    assert code == 0, doc["error"]
    prefix = tmp_path / "xdg" / "mmt"
    assert doc["result"]["prefix"] == prefix.as_posix()
    assert doc["context"]["prefix"] == {"path": prefix.as_posix(), "source": "default"}
    assert doc["result"]["build"] == "ran"
    assert doc["result"]["label"] == "fakeproto"
    assert doc["result"]["protocol"] == {"id": 991, "name": "FAKEPROTO"}
    target = prefix / "plugins" / SO
    assert target.read_bytes() == (project / "build" / SO).read_bytes()
    assert stat.S_IMODE(target.stat().st_mode) == 0o755
    sha = doc["result"]["files"][0]["sha256"]
    assert doc["result"]["files"] == [
        {"path": target.as_posix(), "action": "created", "sha256": sha}
    ]
    manifest = _manifest(prefix / "plugins")
    Draft202012Validator(manifest_module.load_schema()).validate(manifest)
    assert manifest["label"] == "fakeproto"
    assert manifest["protocol"] == {"id": 991, "name": "FAKEPROTO"}
    assert manifest["files"] == [{"path": SO, "sha256": sha}]
    assert doc["result"]["manifest"]["action"] == "created"


def test_install_env_prefix_and_cli_prefix(
    project: Path, install: Run, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MMT_PLUGIN_PREFIX", str(tmp_path / "envp"))
    code, doc = install()
    assert code == 0
    assert (tmp_path / "envp" / "plugins" / SO).is_file()
    code, doc = install("--prefix", "../clip")
    assert code == 0
    assert doc["context"]["prefix"]["source"] == "--prefix"
    assert (tmp_path / "clip" / "plugins" / SO).is_file()
    assert not (tmp_path / "xdg").exists()


def test_install_system_uses_the_system_prefix(project: Path, install: Run, system: Path) -> None:
    code, doc = install("--system")
    assert code == 0
    assert doc["context"]["prefix"] == {"path": system.as_posix(), "source": "--system"}
    assert (system / "plugins" / SO).is_file()
    code, doc = install("--system", "--prefix", "elsewhere")
    assert code == 2
    assert doc["error"]["code"] == "usage.conflicting-options"


@pytest.mark.skipif(os.geteuid() == 0, reason="root can write any directory")
def test_a_prefix_that_cannot_be_written_is_exit_4(
    project: Path, install: Run, system: Path, uninstall: Run
) -> None:
    system.mkdir()
    system.chmod(0o555)
    try:
        code, doc = install("--system")
        assert code == 4
        assert doc["error"]["code"] == "sdk.prefix-not-writable"
        assert "sudo" in doc["error"]["hint"]
        code, doc = install("--system", "--dry-run")
        assert code == 4
    finally:
        system.chmod(0o755)
    assert list(system.iterdir()) == []


def test_install_is_idempotent(project: Path, install: Run, tmp_path: Path) -> None:
    assert install()[0] == 0
    manifest = tmp_path / "xdg" / "mmt" / "plugins" / ".mmt-plugin" / "fakeproto.json"
    before = manifest.stat().st_mtime_ns
    code, doc = install()
    assert code == 0
    assert doc["result"]["build"] == "up-to-date"
    assert [f["action"] for f in doc["result"]["files"]] == ["unchanged"]
    assert doc["result"]["manifest"]["action"] == "unchanged"
    assert manifest.stat().st_mtime_ns == before


def test_install_updates_the_file_it_installed(
    project: Path, install: Run, tmp_path: Path
) -> None:
    assert install()[0] == 0
    # The fake compiler's plugin holds its command line: another build
    # directory makes another plugin.
    code, doc = install("--build-dir", "../other-build")
    assert code == 0, doc["error"]
    assert doc["result"]["build"] == "ran"
    assert [f["action"] for f in doc["result"]["files"]] == ["updated"]
    sha = doc["result"]["files"][0]["sha256"]
    assert _manifest(tmp_path / "xdg" / "mmt" / "plugins")["files"][0]["sha256"] == sha


def test_install_refuses_a_file_it_did_not_install(
    project: Path, install: Run, tmp_path: Path
) -> None:
    plugins = tmp_path / "xdg" / "mmt" / "plugins"
    plugins.mkdir(parents=True)
    (plugins / SO).write_bytes(b"someone else's plugin")
    code, doc = install()
    assert code == 7
    assert doc["error"]["code"] == "state.exists"
    assert (plugins / SO).read_bytes() == b"someone else's plugin"
    assert not (plugins / ".mmt-plugin").exists()
    code, doc = install("--force")
    assert code == 0
    assert [f["action"] for f in doc["result"]["files"]] == ["updated"]


def test_install_accepts_the_same_file_it_did_not_install(
    project: Path, install: Run, tmp_path: Path
) -> None:
    assert install("--prefix", "../a")[0] == 0
    plugins = tmp_path / "xdg" / "mmt" / "plugins"
    plugins.mkdir(parents=True)
    (plugins / SO).write_bytes((tmp_path / "a" / "plugins" / SO).read_bytes())
    (plugins / SO).chmod(0o755)
    code, doc = install()
    assert code == 0
    assert [f["action"] for f in doc["result"]["files"]] == ["unchanged"]
    assert doc["result"]["manifest"]["action"] == "created"


def test_install_refuses_a_file_changed_since_install(
    project: Path, install: Run, tmp_path: Path
) -> None:
    assert install()[0] == 0
    target = tmp_path / "xdg" / "mmt" / "plugins" / SO
    target.write_bytes(b"edited")
    code, doc = install()
    assert code == 7
    assert doc["error"]["code"] == "state.installed-modified"
    assert target.read_bytes() == b"edited"
    code, doc = install("--dry-run", "--force")
    assert code == 0
    assert [f["action"] for f in doc["result"]["files"]] == ["would-update"]
    assert target.read_bytes() == b"edited"
    assert install("--force")[0] == 0
    assert target.read_bytes() == (project / "build" / SO).read_bytes()


def test_install_refuses_a_directory_or_a_symlink(
    project: Path, install: Run, tmp_path: Path
) -> None:
    plugins = tmp_path / "xdg" / "mmt" / "plugins"
    (plugins / SO).mkdir(parents=True)
    code, doc = install("--force")
    assert code == 7
    assert doc["error"]["code"] == "state.exists"
    (plugins / SO).rmdir()
    (tmp_path / "other.so").write_bytes(b"x")
    (plugins / SO).symlink_to(tmp_path / "other.so")
    assert install()[0] == 7
    assert install("--force")[0] == 0
    assert not (plugins / SO).is_symlink()
    assert (tmp_path / "other.so").read_bytes() == b"x"


def test_install_dry_run_writes_nothing(project: Path, install: Run, tmp_path: Path) -> None:
    code, doc = install("--dry-run")
    assert code == 0
    assert doc["result"]["dry_run"] is True
    assert doc["result"]["build"] == "would-run"
    assert doc["result"]["files"][0]["action"] == "would-create"
    assert doc["result"]["files"][0]["sha256"] is None
    assert doc["result"]["manifest"]["sha256"] is None
    assert not (project / "build").exists()
    assert not (tmp_path / "xdg").exists()
    # Built, the dry run knows the plugin's sha256.
    assert main(["-q", "build", "model.pdl", "--sdk", str(tmp_path / "sdk"),
                 "--cc", str(tmp_path / "bin" / "fakecc")]) == 0  # fmt: skip
    code, doc = install("--dry-run")
    assert code == 0
    assert doc["result"]["build"] == "up-to-date"
    assert doc["result"]["files"][0]["action"] == "would-create"
    assert doc["result"]["files"][0]["sha256"] is not None
    assert not (tmp_path / "xdg").exists()


def test_install_no_deps_refuses_a_stale_plugin(
    project: Path, install: Run, tmp_path: Path
) -> None:
    code, doc = install("--no-deps")
    assert code == 7
    assert doc["error"]["code"] == "state.stale"
    assert doc["result"]["build"] == "stale"
    assert not (tmp_path / "xdg").exists()


def test_install_refuses_an_id_or_name_another_plugin_installed(
    project: Path, install: Run, tmp_path: Path
) -> None:
    plugins = tmp_path / "xdg" / "mmt" / "plugins"
    other = Manifest(
        "0", "other", 991, "FAKEPROTO", (manifest_module.InstalledFile("x.so", "0" * 64),)
    )
    (plugins / ".mmt-plugin").mkdir(parents=True)
    (plugins / ".mmt-plugin" / "other.json").write_text(other.dumps())
    code, doc = install("--force")
    assert code == 3
    assert doc["error"]["code"] == "model.id-taken"
    codes = sorted(d["code"] for d in doc["diagnostics"] if d["severity"] == "error")
    assert codes == ["model.id-taken", "model.name-taken"]
    assert not (plugins / SO).exists()


def test_install_never_reads_stdin(
    project: Path, system: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    command = InstallCommand(pkg_config_dirs=[], system_prefix=str(system))
    assert main(["--json", "install", "-"], commands=[command]) == 2
    assert json.loads(capsys.readouterr().out)["error"]["code"] == "usage.invalid-value"


def test_install_refuses_an_invalid_own_manifest(
    project: Path, install: Run, tmp_path: Path
) -> None:
    mdir = tmp_path / "xdg" / "mmt" / "plugins" / ".mmt-plugin"
    mdir.mkdir(parents=True)
    (mdir / "fakeproto.json").write_text("{")
    code, doc = install()
    assert code == 7
    assert doc["error"]["code"] == "state.invalid-manifest"
    assert install("--force")[0] == 0
    assert read_manifest(mdir / "fakeproto.json") is not None


# --- uninstall ---------------------------------------------------------------


def test_uninstall_removes_what_install_wrote(
    project: Path, install: Run, uninstall: Run, tmp_path: Path
) -> None:
    assert install()[0] == 0
    plugins = tmp_path / "xdg" / "mmt" / "plugins"
    code, doc = uninstall("fakeproto", "--dry-run")
    assert code == 0
    assert doc["result"]["removed"] == [(plugins / SO).as_posix()]
    assert (plugins / SO).is_file()
    code, doc = uninstall("fakeproto")
    assert code == 0
    assert doc["result"] == {
        "prefix": (tmp_path / "xdg" / "mmt").as_posix(),
        "label": "fakeproto",
        "manifest": (plugins / ".mmt-plugin" / "fakeproto.json").as_posix(),
        "removed": [(plugins / SO).as_posix()],
        "kept": [],
        "missing": [],
        "dry_run": False,
    }
    assert sorted(p.name for p in plugins.iterdir()) == []


def test_uninstall_defaults_to_the_project_label(
    project: Path, install: Run, uninstall: Run, tmp_path: Path
) -> None:
    assert install()[0] == 0
    assert project_label(project) == "fakeproto"
    code, doc = uninstall()
    assert code == 0
    assert doc["result"]["label"] == "fakeproto"
    assert not (tmp_path / "xdg" / "mmt" / "plugins" / SO).exists()


def test_uninstall_without_a_label_outside_a_project(
    tmp_path: Path, uninstall: Run, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    code, doc = uninstall("--prefix", "p")
    assert code == 2
    assert doc["error"]["code"] == "usage.missing-argument"
    code, doc = uninstall("../etc", "--prefix", "p")
    assert code == 2
    assert doc["error"]["code"] == "usage.invalid-value"


def test_uninstall_keeps_a_changed_file_unless_force(
    project: Path, install: Run, uninstall: Run, tmp_path: Path
) -> None:
    assert install()[0] == 0
    plugins = tmp_path / "xdg" / "mmt" / "plugins"
    (plugins / SO).write_bytes(b"edited")
    code, doc = uninstall("fakeproto")
    assert code == 7
    assert doc["error"]["code"] == "state.installed-modified"
    assert doc["result"]["kept"] == [(plugins / SO).as_posix()]
    assert (plugins / SO).read_bytes() == b"edited"
    assert (plugins / ".mmt-plugin" / "fakeproto.json").is_file()
    code, doc = uninstall("fakeproto", "--force")
    assert code == 0
    assert doc["result"]["removed"] == [(plugins / SO).as_posix()]
    assert not (plugins / SO).exists()
    assert not (plugins / ".mmt-plugin").exists()


def test_uninstall_reports_missing_files_and_keeps_other_manifests(
    project: Path, install: Run, uninstall: Run, tmp_path: Path
) -> None:
    assert install()[0] == 0
    plugins = tmp_path / "xdg" / "mmt" / "plugins"
    (plugins / SO).unlink()
    other = Manifest(
        "0", "other", 992, "OTHER", (manifest_module.InstalledFile("x.so", "0" * 64),)
    )
    (plugins / ".mmt-plugin" / "other.json").write_text(other.dumps())
    code, doc = uninstall("fakeproto")
    assert code == 0
    assert doc["result"]["missing"] == [(plugins / SO).as_posix()]
    assert sorted(p.name for p in (plugins / ".mmt-plugin").iterdir()) == ["other.json"]


def test_uninstall_of_a_plugin_not_installed_is_a_warning(
    project: Path, uninstall: Run, tmp_path: Path
) -> None:
    code, doc = uninstall("fakeproto")
    assert code == 0
    assert doc["result"]["removed"] == doc["result"]["kept"] == doc["result"]["missing"] == []
    assert [d["code"] for d in doc["diagnostics"]] == ["state.not-installed"]


def test_uninstall_never_removes_outside_the_plugin_directory(
    project: Path, uninstall: Run, tmp_path: Path
) -> None:
    mdir = tmp_path / "xdg" / "mmt" / "plugins" / ".mmt-plugin"
    mdir.mkdir(parents=True)
    victim = tmp_path / "victim"
    victim.write_text("keep me")
    doc = Manifest("0", "fakeproto", 991, "FAKEPROTO", ()).to_json()
    doc["files"] = [{"path": "../../../victim", "sha256": "0" * 64}]
    (mdir / "fakeproto.json").write_text(json.dumps(doc))
    code, out = uninstall("fakeproto", "--force")
    assert code == 7
    assert out["error"]["code"] == "state.invalid-manifest"
    assert victim.read_text() == "keep me"


@pytest.mark.skipif(os.geteuid() == 0, reason="root can write any directory")
def test_uninstall_from_a_prefix_that_cannot_be_written_is_exit_4(
    project: Path, install: Run, uninstall: Run, system: Path
) -> None:
    assert install("--system")[0] == 0
    plugins = system / "plugins"
    plugins.chmod(0o555)
    try:
        code, doc = uninstall("fakeproto", "--system")
        assert code == 4
        assert doc["error"]["code"] == "sdk.prefix-not-writable"
    finally:
        plugins.chmod(0o755)
    assert (plugins / SO).is_file()


def test_human_output(
    project: Path,
    tmp_path: Path,
    sdk: Path,
    cc: Path,
    system: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    command = InstallCommand(pkg_config_dirs=[], system_prefix=str(system))
    assert (
        main(["install", "model.pdl", "--sdk", str(sdk), "--cc", str(cc)], commands=[command]) == 0
    )
    out = capsys.readouterr().out
    target = (tmp_path / "xdg" / "mmt" / "plugins" / SO).as_posix()
    assert out.splitlines()[:2] == ["build\tran", f"created\t{target}"]
    assert main(["uninstall"], commands=[UninstallCommand(system_prefix=str(system))]) == 0
    assert capsys.readouterr().out.splitlines() == [f"removed\t{target}"]
