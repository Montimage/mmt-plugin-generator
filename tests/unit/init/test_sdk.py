"""``init`` then ``test`` against a real mmt-dpi SDK (plan T2.7: "an
end-to-end test from init to test").

In a temporary directory, ``mmt-plugin init demo`` picks its id from the
SDK's run-time registry, then ``mmt-plugin test --json`` (``result.next``:
no ``--model``, since the project's ``plugin.yaml`` is the default model and
pins the profile) builds the project (generate, compile with ``-Wall
-Wextra -Werror``, link) and runs its packet test: exit 0, every packet
passing, also under ``--sanitize``. A second ``init`` is a no-op. With a
``--parent`` the generated code can attach (an EtherType, a UDP port), the
packet test also runs ``through`` it, so the generated classification must
find the protocol in a whole frame; a broken one fails that run (#65).
The SDK is an extracted mmt-dpi package, a private prefix (never
``/opt/mmt``)::

    MMT_GOLDEN_SDK=<dir>/opt/mmt MMT_GOLDEN_CC=gcc uv run pytest tests/unit/init/test_sdk.py

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

SDK_ENV = "MMT_GOLDEN_SDK"
CC_ENV = "MMT_GOLDEN_CC"
REQUIRE_ENV = "MMT_REQUIRE_GOLDEN_COMPILE"


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
def work(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """An empty current directory; the SDK comes from ``MMT_BASE`` and the
    compiler from ``CC``, as a user would set them."""
    sdk, cc = _sdk(), _cc()
    cwd = tmp_path / "work"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    for name in ("MMT_PLUGIN_SDK_PROFILE", "MMT_DPI_PLUGINS_DIR"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("MMT_BASE", str(sdk))
    monkeypatch.setenv("CC", cc)
    return cwd


def test_init_then_test_passes_every_packet(
    work: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code, doc = _json(capsys, "init", "demo")
    assert code == 0, doc["error"]
    assert [d["code"] for d in doc["diagnostics"]] == ["model.no-parent"]
    assert doc["result"]["protocol"]["id"] == 950  # the lowest id the SDK leaves free
    assert doc["context"]["sdk"]["source"] == "MMT_BASE"
    argv = doc["result"]["next"]
    assert argv == ["mmt-plugin", "-C", "demo", "test"]

    code, doc = _json(capsys, *argv[1:])
    assert code == 0, doc["error"]
    assert doc["result"]["summary"] == {"total": 1, "passed": 1, "failed": 0, "skipped": 0}
    assert [p["status"] for p in doc["result"]["packets"]] == ["pass"]
    stages = {s["name"]: s["status"] for s in doc["result"]["stages"]}
    assert stages["build"] == "ran" and stages["packets"] == "ran"
    assert (work / "demo" / "build" / "mmtp_demo.so").is_file()

    code, doc = _json(capsys, *argv[1:], "--sanitize", "--fuzz-count", "20")
    assert code == 0, doc["error"]
    assert doc["result"]["sanitize"]["crashes"] == []

    # The build left build/ and generated/: init is still a no-op.
    code, doc = _json(capsys, "init", "demo")
    assert code == 0, doc["error"]
    assert {f["action"] for f in doc["result"]["files"]} == {"unchanged"}


@pytest.mark.parametrize("parent", ["ethernet:ethertype=0x88b5", "udp:dport=4433"])
def test_init_with_a_classified_parent_tests_green_through_it(
    work: Path, capsys: pytest.CaptureFixture[str], parent: str
) -> None:
    code, doc = _json(capsys, "init", "demo2", "--id", "977", "--parent", parent)
    assert code == 0, doc["error"]
    assert doc["diagnostics"] == []
    argv = doc["result"]["next"][1:]
    code, doc = _json(capsys, *argv)
    assert code == 0, doc["error"]
    packets = doc["result"]["packets"]
    assert [(p["id"], p.get("through"), p["status"]) for p in packets] == [
        ("demo2/basic", None, "pass"),
        ("demo2/basic", parent, "pass"),
    ]
    code, doc = _json(capsys, *argv, "--sanitize", "--fuzz-count", "20")
    assert code == 0, doc["error"]
    assert doc["result"]["sanitize"]["crashes"] == []

    # The through run tests the generated classification: a classify that
    # matches another value fails it, and only it.
    model = work / "demo2" / "plugin.yaml"
    text = model.read_text()
    value = parent.rpartition("=")[2]
    assert f"value: {value}}}" in text
    model.write_text(text.replace(f"value: {value}}}", "value: 0x1234}"))
    code, doc = _json(capsys, *argv)
    assert code == 6
    assert doc["error"]["code"] == "test.packet-failed"
    failed = [(p.get("through"), p["status"]) for p in doc["result"]["packets"]]
    assert failed == [(None, "pass"), (parent, "fail")]


def test_init_with_a_hook_parent_tests_green(
    work: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code, doc = _json(capsys, "init", "demo3", "--id", "978", "--parent", "tcp:port=102")
    assert code == 0, doc["error"]
    code, doc = _json(capsys, *doc["result"]["next"][1:])
    assert code == 0, doc["error"]
    assert [p.get("through") for p in doc["result"]["packets"]] == [None]
