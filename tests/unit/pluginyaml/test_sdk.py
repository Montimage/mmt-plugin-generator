"""A plugin.yaml project against a real mmt-dpi SDK: the generated parent
classification classifies the protocol.

The project's plugin.yaml declares Ethernet as a parent, with a generated
classification that needs one more byte than the ``test`` harness's own
(EtherType 0x88b5, then 0xee) and starts the protocol two bytes later. With
weight 0 it runs before the harness's (weight 1), so the packet test passes
only if the generated function classified the packet; with weight 9 the
harness's runs first, and the same test fails. ``validate`` finds the parent
in the SDK. The SDK is an extracted mmt-dpi package, a private prefix (never
``/opt/mmt``)::

    MMT_GOLDEN_SDK=<dir>/opt/mmt MMT_GOLDEN_CC=gcc uv run pytest tests/unit/pluginyaml/test_sdk.py

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
from mmt_plugin.codegen import generate, scaffold
from mmt_plugin.pluginyaml import load
from mmt_plugin.semantics import analyse

from .corpus import profile

SDK_ENV = "MMT_GOLDEN_SDK"
CC_ENV = "MMT_GOLDEN_CC"
REQUIRE_ENV = "MMT_REQUIRE_GOLDEN_COMPILE"

PLUGIN_YAML = """\
schema: 1
protocol:
  label: yamlpar
  id: 962
  encoding: network
sdk:
  profile: "1.10.2"
parents:
  - protocol: ethernet
    weight: WEIGHT
    classify:
      match:
        - {offset: 12, length: 2, value: 0x88b5}
        - {offset: 14, length: 1, value: 0xee}
      offset: 16
attributes:
  - name: version
    type: MMT_U8_DATA
    offset: 0
  - name: length
    type: MMT_U16_DATA
    offset: 1
  - name: payload
    type: MMT_BINARY_DATA
    offset: 3
    length: val(length)
"""

PACKET = """\
schema: 1
id: "yamlpar/basic"
model: "yamlpar"
summary: "the generated Ethernet classification starts the protocol after 0xee and a byte"
parent:
  kind: "none"
  path: []
  selector: "Ethernet, EtherType 0x88b5, then 0xee"
  source: "model-declared"
bytes:
  - "ee 00 07 00 02 ab cd"
bytes_source: "model-declared: 0xee, a pad byte, then the protocol"
expect:
  protocol: "YAMLPAR"
  proto_id: 962
  next:
    kind: "none"
    source: "model-declared"
  attributes:
    - name: "version"
      type: "MMT_U8_DATA"
      offset: 0
      length: 1
      value: 7
      source: "model-declared"
    - name: "length"
      type: "MMT_U16_DATA"
      offset: 1
      length: 2
      value: 2
      source: "model-declared"
    - name: "payload"
      type: "MMT_BINARY_DATA"
      offset: 3
      length: 2
      value: "ab cd"
      source: "model-declared: length bytes"
"""


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


def _project(root: Path, weight: int) -> Path:
    text = PLUGIN_YAML.replace("WEIGHT", str(weight))
    (root / "src").mkdir(parents=True)
    (root / "tests").mkdir()
    (root / "plugin.yaml").write_text(text)
    (root / "tests" / "basic.yaml").write_text(PACKET)
    analysed, diagnostics = analyse(load(text, filename="plugin.yaml").model, profile=profile())
    assert analysed is not None, diagnostics
    impl = scaffold(generate(analysed, profile()), profile())
    (root / impl.path).write_text(impl.text)
    return root


@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch) -> tuple[Path, str]:
    sdk, cc = _sdk(), _cc()
    for name in ("MMT_PLUGIN_SDK_PROFILE", "MMT_DPI_PLUGINS_DIR", "MMT_BASE", "CC"):
        monkeypatch.delenv(name, raising=False)
    return sdk, cc


def test_the_generated_parent_classification_classifies_the_protocol(
    env: tuple[Path, str], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    sdk, cc = env
    project = _project(tmp_path / "first", 0)
    tool = ["--sdk", str(sdk), "--cc", cc]
    code, doc = _json(capsys, "-C", str(project), "validate", "--sdk", str(sdk))
    assert code == 0, doc["error"]
    checks = {c["id"]: c for c in doc["result"]["checks"]}
    assert checks["parents-exist"]["status"] == "pass"
    assert checks["schema"]["detail"] == "plugin.yaml, schema 1"
    code, doc = _json(capsys, "-C", str(project), "test", *tool)
    assert code == 0, doc["error"]
    assert doc["context"]["sdk"]["profile_source"] == "plugin.yaml"
    assert [p["status"] for p in doc["result"]["packets"]] == ["pass"]
    sanitize = ["--sanitize", "--fuzz-count", "200"]
    code, doc = _json(capsys, "-C", str(project), "test", *tool, *sanitize)
    assert code == 0, doc["error"]


def test_with_a_later_weight_the_harness_classifies_first(
    env: tuple[Path, str], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    sdk, cc = env
    project = _project(tmp_path / "late", 9)
    code, doc = _json(capsys, "-C", str(project), "test", "--sdk", str(sdk), "--cc", cc)
    assert code == 6
    assert doc["error"]["code"] == "test.packet-failed"
