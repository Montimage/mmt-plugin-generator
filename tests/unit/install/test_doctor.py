"""``mmt-plugin doctor`` with a fake SDK and a fake compiler
(``tests/unit/build/fakes.py``): the ten checks in their order, the scanned
plugin directory (``MMT_DPI_PLUGINS_DIR`` or the one compiled into
``libmmt_core``) against the install prefix's, load order, clashes among
the installed plugins and with the project's model, the exit codes, and
the styled view's four sections (``docs/design/cli.md``, sections 4, 5, 6
and 10). ``test_sdk.py`` runs it against a real mmt-dpi."""

from __future__ import annotations

import importlib.util
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from mmt_plugin import schemas
from mmt_plugin.cli import main
from mmt_plugin.commands.doctor import CHECKS, DoctorCommand, _view
from mmt_plugin.manifest import InstalledFile, Manifest
from mmt_plugin.ui.streams import ColorTier, StreamStyle


def _load_fakes() -> Any:
    spec = importlib.util.spec_from_file_location(
        "doctor_build_fakes", Path(__file__).parents[1] / "build" / "fakes.py"
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

Run = Callable[..., tuple[int, dict[str, Any]]]


@pytest.fixture
def sdk(tmp_path: Path) -> Path:
    """A fake SDK whose ``libmmt_core`` names its compiled-in plugin
    directory: ``<sdk>/plugins``, holding ``libmmt_tcpip.so``."""
    prefix = Path(fakes.fake_sdk(tmp_path / "sdk"))
    plugins = prefix / "plugins"
    plugins.mkdir()
    (plugins / "libmmt_tcpip.so").write_text("")
    core = prefix / "dpi" / "lib" / "libmmt_core.so.1.10.2"
    core.write_bytes(b"\x7fELF\x00" + str(plugins).encode() + b"\x00")
    return prefix


@pytest.fixture
def doctor(
    tmp_path: Path,
    sdk: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> Run:
    """``mmt-plugin --json doctor --sdk SDK --cc CC ARGS`` in ``tmp_path/work``,
    with ``XDG_DATA_HOME`` in ``tmp_path``."""
    cc = fakes.fake_cc(tmp_path / "bin")
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.chdir(work)
    for name in ("MMT_DPI_PLUGINS_DIR", "MMT_PLUGIN_PREFIX", "MMT_PLUGIN_SDK_PROFILE", "CC"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    envelope = Draft202012Validator(schemas.load_cli_schema(schemas.ENVELOPE))
    result = Draft202012Validator(schemas.result_schema("doctor"))
    command = DoctorCommand(
        pkg_config_dirs=[], default_prefix=str(tmp_path / "no-sdk"), system_prefix=str(sdk)
    )

    def go(*args: str, sdk_args: bool = True) -> tuple[int, dict[str, Any]]:
        extra = ["--sdk", str(sdk), "--cc", str(cc)] if sdk_args else []
        code = main(["--json", "doctor", *extra, *args], commands=[command])
        out = capsys.readouterr()
        assert out.err == ""
        doc: dict[str, Any] = json.loads(out.out)
        envelope.validate(doc)
        result.validate(doc["result"])
        assert doc["exit_code"] == code
        return code, doc

    return go


def _checks(doc: dict[str, Any]) -> dict[str, tuple[str, str]]:
    checks = doc["result"]["checks"]
    assert [c["id"] for c in checks] == list(CHECKS)
    return {c["id"]: (c["status"], c["detail"]) for c in checks}


def _install(plugins: Path, label: str, pid: int, name: str | None = None) -> None:
    (plugins / ".mmt-plugin").mkdir(parents=True, exist_ok=True)
    so = f"mmtp_{label}.so"
    (plugins / so).write_text("")
    manifest = Manifest("0", label, pid, name or label.upper(), (InstalledFile(so, "0" * 64),))
    (plugins / ".mmt-plugin" / f"{label}.json").write_text(manifest.dumps())


def test_outside_a_project_with_the_default_prefix(doctor: Run, sdk: Path, tmp_path: Path) -> None:
    code, doc = doctor()
    assert code == 0, doc["error"]
    checks = _checks(doc)
    assert checks["python"][0] == checks["compiler"][0] == checks["sdk"][0] == "pass"
    assert checks["sdk-profile"] == ("pass", "1.10.2 (sdk)")
    assert checks["plugin-dir"] == ("pass", f"{sdk}/plugins (compiled into libmmt_core)")
    assert checks["install-dir"][0] == "warn"
    assert "not scanned" in checks["install-dir"][1]
    assert checks["load-order"] == ("skip", "no plugin installed")
    # The fake libmmt_core does not load: the registry is a warning.
    assert checks["registry"][0] == "warn"
    assert checks["project"][0] == "skip"
    assert checks["clashes"][0] == "skip"
    install = doc["result"]["plugin_dirs"]["install"]
    assert install == {
        "path": (tmp_path / "xdg" / "mmt").as_posix(),
        "source": "default",
        "plugins": (tmp_path / "xdg" / "mmt" / "plugins").as_posix(),
        "scanned": False,
        "writable": True,
    }
    assert doc["result"]["plugin_dirs"]["scanned"] == {
        "path": f"{sdk}/plugins",
        "source": "libmmt_core",
    }
    codes = [d["code"] for d in doc["diagnostics"]]
    assert "sdk.install-dir-not-scanned" in codes
    hint = next(d for d in doc["diagnostics"] if d["code"] == "sdk.install-dir-not-scanned")
    assert "MMT_DPI_PLUGINS_DIR=" in hint["hint"] and "ln -s" in hint["hint"]
    assert not (tmp_path / "xdg").exists()  # doctor writes nothing


def test_the_install_prefix_scanned_through_the_variable(
    doctor: Run, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plugins = tmp_path / "xdg" / "mmt" / "plugins"
    _install(plugins, "fakeproto", 991)
    monkeypatch.setenv("MMT_DPI_PLUGINS_DIR", str(plugins))
    code, doc = doctor()
    assert code == 0
    checks = _checks(doc)
    # Scanned, but without the SDK's libmmt_tcpip.so next to it.
    assert checks["plugin-dir"][0] == "warn"
    assert "sdk.no-tcpip-plugin" in [d["code"] for d in doc["diagnostics"]]
    assert checks["install-dir"][0] == "pass"
    assert doc["result"]["plugin_dirs"]["install"]["scanned"] is True
    assert checks["load-order"] == ("pass", "1 plugin after libmmt_tcpip.so")
    assert checks["clashes"] == ("pass", "no clash among 1 installed plugin")
    (plugins / "libmmt_tcpip.so").write_text("")
    assert _checks(doctor()[1])["plugin-dir"][0] == "pass"


def test_the_install_prefix_is_the_compiled_in_directory(doctor: Run, sdk: Path) -> None:
    code, doc = doctor("--system")
    assert code == 0
    assert _checks(doc)["install-dir"][0] == "pass"


def test_a_relative_or_missing_plugin_dir_fails(
    doctor: Run, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MMT_DPI_PLUGINS_DIR", "relative/plugins")
    code, doc = doctor()
    assert code == 4
    assert doc["error"]["code"] == "sdk.invalid-plugin-dir"
    assert _checks(doc)["plugin-dir"][0] == "fail"
    monkeypatch.setenv("MMT_DPI_PLUGINS_DIR", str(tmp_path / "none"))
    code, doc = doctor()
    assert code == 4
    assert doc["error"]["code"] == "sdk.invalid-plugin-dir"


def test_a_plugin_that_loads_before_tcpip_fails(doctor: Run, sdk: Path) -> None:
    (sdk / "plugins" / "aaa.so").write_text("")
    code, doc = doctor()
    assert code == 4
    assert doc["error"]["code"] == "sdk.plugin-load-order"
    assert _checks(doc)["load-order"][0] == "fail"
    assert doc["result"]["load_order"][0] == {
        "path": f"{sdk}/plugins",
        "plugins": ["aaa.so", "libmmt_tcpip.so"],
    }


def test_clashes_among_installed_plugins_and_with_the_project(doctor: Run, tmp_path: Path) -> None:
    plugins = tmp_path / "xdg" / "mmt" / "plugins"
    _install(plugins, "one", 990)
    _install(plugins, "two", 990)
    code, doc = doctor()
    assert code == 4
    assert doc["error"]["code"] == "sdk.plugin-clash"
    assert doc["result"]["clashes"] == [{"kind": "id", "value": "990", "plugins": ["one", "two"]}]
    (plugins / ".mmt-plugin" / "two.json").unlink()
    (Path.cwd() / "model.pdl").write_text(
        MODEL.replace("fakeproto", "three").replace('id = "991"', 'id = "990"')
    )
    code, doc = doctor("--model", "model.pdl")
    assert code == 4
    assert doc["result"]["clashes"] == [
        {"kind": "id", "value": "990", "plugins": ["one", "three"]}
    ]


def test_the_project_model(doctor: Run, tmp_path: Path) -> None:
    plugins = tmp_path / "xdg" / "mmt" / "plugins"
    _install(plugins, "fakeproto", 991)  # the project's own installed copy
    _install(plugins, "other", 992, "FAKEPROTO2")
    (Path.cwd() / "model.pdl").write_text(MODEL)
    code, doc = doctor("--model", "model.pdl")
    assert code == 0
    checks = _checks(doc)
    assert checks["project"] == ("pass", "model.pdl: fakeproto (id 991, FAKEPROTO)")
    assert checks["clashes"] == (
        "pass",
        "no clash among 2 installed plugins and the project's model",
    )
    (Path.cwd() / "model.pdl").write_text(MODEL.replace('id = "991"', 'id = "992"'))
    code, doc = doctor("--model", "model.pdl")
    assert code == 4
    assert doc["result"]["clashes"] == [
        {"kind": "id", "value": "992", "plugins": ["fakeproto", "other"]}
    ]
    # plugin.yaml (#24) is a warning: not checked.
    (Path.cwd() / "model.pdl").unlink()
    (Path.cwd() / "plugin.yaml").write_text("label: x\n")
    code, doc = doctor()
    assert code == 0
    assert _checks(doc)["project"][0] == "warn"


def test_no_sdk_and_no_compiler_fail(doctor: Run, tmp_path: Path) -> None:
    code, doc = doctor("--cc", str(tmp_path / "no-cc"), sdk_args=False)
    assert code == 4
    checks = _checks(doc)
    assert checks["compiler"][0] == "fail"
    assert checks["sdk"][0] == "fail"
    assert checks["sdk-profile"][0] == checks["registry"][0] == "skip"
    assert doc["error"]["code"] == "sdk.cc-not-found"
    assert doc["context"]["sdk"] is None
    assert doc["result"]["toolchain"]["cc"] is None


def test_the_styled_view_has_four_sections() -> None:
    style = StreamStyle(styled=True, color=ColorTier.NONE, unicode=True, width=100, tty=True)
    checks = [{"id": c, "status": "pass", "detail": "ok"} for c in CHECKS]
    text = _view(checks, style)
    assert text.startswith("╭─┐doctor┌")
    assert text.count("├") == 3
    assert "10 checks · 10 pass" in text
