"""The OCI-P plugin project ``ocip-plugin/project`` (#134, #138) against a
real mmt-dpi SDK.

The project is copied, without its ``build/``, to a temporary directory,
then: ``validate --sdk`` passes; ``build`` compiles it with the hardened
``-Wall -Wextra -Werror`` flags without regenerating (the committed
``generated/`` is up to date); and ``test --sanitize`` passes every packet
test, its run through TCP port 2208, and every session test (the
per-direction stream state: split, reordered and lost segments, #137, and an
in-order filler, #140),
also under ASan and UBSan with truncated, random and corrupted packets.
The SDK is an extracted mmt-dpi package, a private prefix (never
``/opt/mmt``)::

    MMT_GOLDEN_SDK=<dir>/opt/mmt MMT_GOLDEN_CC=gcc uv run pytest tests/unit/ocip/test_sdk.py

Without ``MMT_GOLDEN_SDK`` the tests skip, unless
``MMT_REQUIRE_GOLDEN_COMPILE=1`` (CI's "Generated code" job) makes them fail.
"""

from __future__ import annotations

import json
import math
import os
import shutil
from pathlib import Path
from typing import Any

import pytest

from mmt_plugin.cli import main
from mmt_plugin.sdk.profile import DATA_TYPE_GROUP
from mmt_plugin.sdk.resolve import resolve_profile
from mmt_plugin.testing.packets import PacketTest
from mmt_plugin.testing.session import SessionTest, build_frames, load_test

SDK_ENV = "MMT_GOLDEN_SDK"
CC_ENV = "MMT_GOLDEN_CC"
REQUIRE_ENV = "MMT_REQUIRE_GOLDEN_COMPILE"
REPO = Path(__file__).resolve().parents[3]
PROJECT = REPO / "ocip-plugin" / "project"
_TYPES = {
    c.name
    for c in resolve_profile("1.10.2", {}, None, None).profile.constants
    if c.group == DATA_TYPE_GROUP
}


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


def _stages(doc: dict[str, Any]) -> dict[str, str]:
    return {s["name"]: s["status"] for s in doc["result"]["stages"]}


def _runs(project: Path, fuzz_count: int) -> tuple[int, int]:
    """The runs of the project's tests (each one, and each ``through``) and
    the packets ``--sanitize --fuzz-count fuzz_count`` runs."""
    tests = [load_test(p, p.name, _TYPES) for p in (project / "tests").glob("*.yaml")]
    packets = [t for t in tests if isinstance(t, PacketTest)]
    runs = len(tests) + sum(1 for t in packets if t.through is not None)
    fuzzed = (fuzz_count + 1) * (runs - (len(tests) - len(packets)))
    for test in tests:
        if isinstance(test, SessionTest):
            n = len(build_frames(test))
            fuzzed += n * (1 + math.ceil(fuzz_count / n))
    return runs, fuzzed


def test_the_project_validates_builds_and_passes_its_tests(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    sdk, cc = _sdk(), _cc()
    project = tmp_path / "project"
    shutil.copytree(PROJECT, project, ignore=shutil.ignore_patterns("build"))
    monkeypatch.chdir(project)
    monkeypatch.delenv("MMT_PLUGIN_SDK_PROFILE", raising=False)
    # validate reads the SDK's own plugins; the harness sets its own directory.
    monkeypatch.setenv("MMT_DPI_PLUGINS_DIR", str(sdk / "plugins"))

    code, doc = _json(capsys, "validate", "--sdk", str(sdk))
    assert code == 0, doc["error"]
    checks = {c["id"]: c["status"] for c in doc["result"]["checks"]}
    assert checks["id-free"] == checks["name-free"] == checks["load-order"] == "pass", checks
    assert checks["parents-exist"] == "pass", checks

    code, doc = _json(capsys, "build", "--sdk", str(sdk), "--cc", cc)
    assert code == 0, (doc["error"], doc["diagnostics"])
    # The committed generated/ is this SDK's generation: build compiles it as it is.
    assert _stages(doc) == {
        "generate": "up-to-date",
        "compile": "ran",
        "hooks": "ran",
        "link": "ran",
    }

    code, doc = _json(
        capsys, "test", "--sdk", str(sdk), "--cc", cc, "--sanitize", "--fuzz-count", "100"
    )
    assert code == 0, (doc["error"], doc["result"] and doc["result"]["packets"])
    result = doc["result"]
    runs, fuzzed = _runs(project, 100)
    assert runs == 38
    assert result["summary"] == {"total": runs, "passed": runs, "failed": 0, "skipped": 0}
    sessions = [p for p in result["packets"] if "session" in p]
    assert len(sessions) == 18, result["packets"]
    assert len([p for p in result["packets"] if "through" in p]) == 10, result["packets"]
    assert result["sanitize"] == {"seed": 0, "count": fuzzed, "crashes": []}
    assert _stages(doc) == {
        "build": "up-to-date",
        "harness": "ran",
        "packets": "ran",
        "sanitize": "ran",
        "bench": "skipped",
    }
