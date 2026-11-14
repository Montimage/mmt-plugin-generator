"""``mmt-plugin build`` against a real mmt-dpi SDK (plan T2.3: "builds every
corpus model in CI").

Every corpus model that generates is built in its own project, with its
scaffold ``src/<label>_impl.c``, by ``mmt-plugin build`` with the SDK's
profile; mmt-dpi then loads the plugin from a plugin directory next to the
SDK's ``libmmt_tcpip.so`` (``mmt_plugin.sdk.registry``), and registers the
protocol under the model's id and label. One model also checks, with the
real compiler, that a second build is a no-op, that a compile error is
located in the user file and that a missing hook fails the build.

The SDK is an extracted mmt-dpi package, a private prefix (never
``/opt/mmt``), as for ``tests/unit/generate/test_compile.py``::

    MMT_GOLDEN_SDK=<dir>/opt/mmt MMT_GOLDEN_CC=gcc uv run pytest tests/unit/build/test_sdk.py

Without ``MMT_GOLDEN_SDK`` the tests skip, unless
``MMT_REQUIRE_GOLDEN_COMPILE=1`` (CI's "Generated code" job) makes them fail.
"""

from __future__ import annotations

import json
import os
import re
import shutil
from functools import cache
from pathlib import Path
from typing import Any

import pytest

from mmt_plugin.cli import main
from mmt_plugin.codegen import Generation, scaffold
from mmt_plugin.commands.generate import make_generation
from mmt_plugin.sdk.detect import SdkSource, find_sdk, read_version
from mmt_plugin.sdk.registry import PLUGINS_DIR_ENV, read_registry
from mmt_plugin.sdk.resolve import ProfileChoice, resolve_profile

SDK_ENV = "MMT_GOLDEN_SDK"
CC_ENV = "MMT_GOLDEN_CC"
REQUIRE_ENV = "MMT_REQUIRE_GOLDEN_COMPILE"
CORPUS = Path(__file__).resolve().parents[2] / "corpus" / "models"
TCPIP = "libmmt_tcpip.so"
_PROTO_MACRO = re.compile(r"^#define PROTO_\w+ ([0-9]+)$", re.MULTILINE)


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


@cache
def _choice(version: str) -> ProfileChoice:
    return resolve_profile(version, {}, None, None)


def _generation(name: str, version: str) -> Generation | None:
    data = (CORPUS / name / "model.pdl").read_bytes()
    generation, _, _ = make_generation("model.pdl", data, _choice(version))
    return generation


def _models() -> list[str]:
    return sorted(d.name for d in CORPUS.iterdir() if (d / "model.pdl").is_file())


def _project(name: str, root: Path, version: str) -> tuple[Path, Generation]:
    """A project for corpus model ``name``: ``model.pdl`` and the scaffold."""
    generation = _generation(name, version)
    assert generation is not None, f"{name} does not generate with {version}"
    project = root / name
    (project / "src").mkdir(parents=True)
    shutil.copy(CORPUS / name / "model.pdl", project / "model.pdl")
    impl = scaffold(generation, _choice(version).profile)
    (project / impl.path).write_text(impl.text)
    return project, generation


def _build(
    project: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    *args: str,
) -> tuple[int, dict[str, Any]]:
    monkeypatch.chdir(project)
    code = main(["--json", "build", "model.pdl", "--sdk", str(_sdk()), "--cc", _cc(), *args])
    doc: dict[str, Any] = json.loads(capsys.readouterr().out)
    return code, doc


def _version() -> str:
    version = read_version(str(_sdk()))
    assert version is not None, f"{_sdk()} has no VERSION in mmt_core.h"
    return version


def _accepted() -> list[str]:
    # The SDK is not known at collection time: the list uses the newest
    # profile, and each test checks its model with the SDK's own.
    choice = resolve_profile(None, {}, None, None)
    return [m for m in _models() if _generation(m, choice.profile.version) is not None]


ACCEPTED = _accepted()


def test_the_corpus_has_the_models_generate_accepts() -> None:
    # tests/unit/generate/test_golden.py: 16 corpus models generate.
    assert len(ACCEPTED) == 16


@pytest.mark.parametrize("name", ACCEPTED)
def test_build_makes_a_plugin_that_mmt_dpi_loads(
    name: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    version = _version()
    project, generation = _project(name, tmp_path, version)
    code, doc = _build(project, monkeypatch, capsys)
    assert code == 0, (doc["error"], doc["diagnostics"])
    assert doc["diagnostics"] == [] or all(d["severity"] != "error" for d in doc["diagnostics"]), (
        doc["diagnostics"]
    )
    label = generation.label.lower()
    plugin = project / "build" / f"mmtp_{label}.so"
    assert plugin.is_file()
    assert doc["result"]["artifact"]["path"] == f"build/mmtp_{label}.so"

    plugins = tmp_path / "plugins"
    plugins.mkdir()
    (plugins / TCPIP).symlink_to((_sdk() / "plugins" / TCPIP).resolve())
    (plugins / plugin.name).symlink_to(plugin)
    sdk = find_sdk(str(_sdk()), {})
    assert sdk is not None and sdk.source is SdkSource.CLI
    profile = _choice(version).profile
    max_id = profile.constant("PROTO_MAX_IDENTIFIER").value
    assert isinstance(max_id, int)
    registry = read_registry(sdk, env={**os.environ, PLUGINS_DIR_ENV: str(plugins)}, max_id=max_id)
    header = generation.file(generation.header).text
    ids = _PROTO_MACRO.findall(header)
    assert len(ids) == 1, ids
    registered = registry.by_id(int(ids[0]))
    assert registered is not None, f"{plugin.name} did not register protocol {ids[0]}"
    assert registered.name.casefold() == label.casefold()


def test_a_second_build_is_a_no_op_and_errors_are_located(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    project, generation = _project("pdl_scopes", tmp_path, _version())
    assert _build(project, monkeypatch, capsys)[0] == 0
    code, doc = _build(project, monkeypatch, capsys)
    assert code == 0 and doc["result"]["up_to_date"] is True

    impl = project / "src" / "pdl_scopes_impl.c"
    good = impl.read_text()
    impl.write_text(good + "\nint broken(void) { return undeclared_name; }\n")
    line = impl.read_text().count("\n")
    code, doc = _build(project, monkeypatch, capsys)
    assert code == 5
    assert doc["error"]["code"] == "build.compile-failed"
    located = [
        d["location"]
        for d in doc["diagnostics"]
        if d["code"] == "build.cc" and d["severity"] == "error" and d["location"]
    ]
    assert {"file": "src/pdl_scopes_impl.c", "line": line} in [
        {"file": loc["file"], "line": loc["line"]} for loc in located
    ], doc["diagnostics"]
    assert any("undeclared_name" in d["message"] for d in doc["diagnostics"])

    hook = generation.hooks[0]
    start = good.index(f"{hook.declaration}\n{{")
    end = good.index("\n}\n", start) + 3
    impl.write_text(good[:start] + good[end:])
    code, doc = _build(project, monkeypatch, capsys)
    assert code == 5, doc["diagnostics"]
    assert doc["error"]["code"] == "build.missing-hook"
    assert hook.name in doc["error"]["message"]
    assert not (project / "build" / ".mmtp_pdl_scopes.so.tmp").exists()
    # The plugin of the last good build is still there.
    assert (project / "build" / "mmtp_pdl_scopes.so").is_file()
