"""The ported examples (plan T5.1, #28: "CI builds and tests every ported
example") against a real mmt-dpi SDK.

Each ``examples/<name>/`` project is copied, without its ``build/``, to a
temporary directory, then: ``validate --sdk`` passes, with its parents
found in the SDK (``parents-exist``) or none declared; ``build`` compiles
it with the hardened ``-Wall -Wextra -Werror`` flags without regenerating
(the committed ``generated/`` is up to date); and ``test --sanitize`` passes
every packet test, also under ASan and UBSan with truncated and random
packets, and the run of each example's ``through`` test through its real
parent. With that parent's classification removed (the generated
``classify`` taken out of ``plugin.yaml``) or wrong (the hook's function
attached to another protocol, or a wrong ``classify`` offset), only that
run fails. The SDK is an extracted mmt-dpi package, a private prefix (never
``/opt/mmt``), as for ``tests/unit/packettest/test_sdk.py``::

    MMT_GOLDEN_SDK=<dir>/opt/mmt MMT_GOLDEN_CC=gcc uv run pytest tests/unit/examples/test_sdk.py

Without ``MMT_GOLDEN_SDK`` the tests skip, unless
``MMT_REQUIRE_GOLDEN_COMPILE=1`` (CI's "Generated code" job) makes them fail.
"""

from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path
from typing import Any

import pytest

from mmt_plugin.cli import main
from mmt_plugin.sdk.profile import DATA_TYPE_GROUP
from mmt_plugin.sdk.resolve import resolve_profile
from mmt_plugin.testing.packets import load

SDK_ENV = "MMT_GOLDEN_SDK"
CC_ENV = "MMT_GOLDEN_CC"
REQUIRE_ENV = "MMT_REQUIRE_GOLDEN_COMPILE"
REPO = Path(__file__).resolve().parents[3]
EXAMPLES = REPO / "examples"
NAMES = sorted(p.parent.name for p in EXAMPLES.glob("*/plugin.yaml"))

#: The examples that declare no parent (examples/README.md, "The ports").
NO_PARENT = {"cotp", "ethernet", "s7com", "topo_ind_sch"}
PARENTED = sorted(set(NAMES) - NO_PARENT)
#: The examples whose parent hook (src/<label>_impl.c) attaches the protocol,
#: and another parent for it: the frame's never reaches the function there.
HOOKED = {
    "mongodb": ("PROTO_TCP", "PROTO_UDP"),
    "tcp": ("PROTO_IP", "PROTO_IPV6"),
    "tpkt": ("PROTO_TCP", "PROTO_UDP"),
}
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


@pytest.fixture
def project(
    request: pytest.FixtureRequest, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Path:
    """A copy of the example, the current directory; no host plugin
    directory and no profile from the environment."""
    sdk, _ = _sdk(), _cc()
    name: str = request.param
    copy = tmp_path / name
    shutil.copytree(EXAMPLES / name, copy, ignore=shutil.ignore_patterns("build"))
    monkeypatch.chdir(copy)
    monkeypatch.delenv("MMT_PLUGIN_SDK_PROFILE", raising=False)
    # validate reads the SDK's own plugins; the harness sets its own directory.
    monkeypatch.setenv("MMT_DPI_PLUGINS_DIR", str(sdk / "plugins"))
    return copy


def _runs(project: Path) -> int:
    """The packet runs of a project's tests: each one, and each ``through``."""
    tests = [load(p, p.name, _TYPES) for p in (project / "tests").glob("*.yaml")]
    return len(tests) + sum(1 for t in tests if t.through is not None)


def test_every_example_is_tested() -> None:
    assert len(NAMES) == 16
    assert set(NAMES) >= NO_PARENT
    assert set(HOOKED) < set(PARENTED)


@pytest.mark.parametrize("project", NAMES, indirect=True)
def test_the_example_validates_builds_and_passes_its_packet_tests(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    sdk, cc = str(_sdk()), _cc()

    code, doc = _json(capsys, "validate", "--sdk", sdk)
    assert code == 0, doc["error"]
    checks = {c["id"]: c["status"] for c in doc["result"]["checks"]}
    assert checks["id-free"] == checks["name-free"] == checks["load-order"] == "pass", checks
    assert checks["parents-exist"] == ("skip" if project.name in NO_PARENT else "pass"), checks

    code, doc = _json(capsys, "build", "--sdk", sdk, "--cc", cc)
    assert code == 0, (doc["error"], doc["diagnostics"])
    # The committed generated/ is this SDK's generation: build compiles it as it is.
    assert _stages(doc) == {
        "generate": "up-to-date",
        "compile": "ran",
        "hooks": "ran",
        "link": "ran",
    }

    code, doc = _json(
        capsys, "test", "--sdk", sdk, "--cc", cc, "--sanitize", "--fuzz-count", "100"
    )
    assert code == 0, (doc["error"], doc["result"] and doc["result"]["packets"])
    result = doc["result"]
    runs = _runs(project)
    assert result["summary"] == {"total": runs, "passed": runs, "failed": 0, "skipped": 0}
    assert all(p["attributes"] > 0 for p in result["packets"]), result["packets"]
    through = [p for p in result["packets"] if "through" in p]
    assert len(through) == (0 if project.name in NO_PARENT else 1), result["packets"]
    assert result["sanitize"] == {"seed": 0, "count": 101 * runs, "crashes": []}
    assert _stages(doc) == {
        "build": "up-to-date",
        "harness": "ran",
        "packets": "ran",
        "sanitize": "ran",
        "bench": "skipped",
    }


def _break_parent(project: Path, how: str) -> None:
    """Remove the example's parent classification, or make it wrong."""
    if how == "hook":
        impl = next((project / "src").glob("*_impl.c"))
        old, new = HOOKED[project.name]
        call = f"register_classification_function_with_parent_protocol({old},"
        text = impl.read_text()
        assert text.count(call) == 1, impl
        impl.write_text(text.replace(call, call.replace(old, new)))
        return
    model = project / "plugin.yaml"
    text = model.read_text()
    if how == "removed":
        broken = re.sub(r"\n    classify:\n(?:      .*\n)+", "\n", text, count=1)
    else:  # the protocol starts at the parent's own first byte
        broken = re.sub(
            r"(\n    classify:\n(?:      .*\n)*?)      offset: \d+\n",
            r"\1      offset: 0\n",
            text,
            count=1,
        )
    assert broken != text, model
    model.write_text(broken)


@pytest.mark.parametrize(
    ("project", "how"),
    [(n, "hook" if n in HOOKED else "removed") for n in PARENTED] + [("dns", "offset")],
    indirect=["project"],
)
def test_only_the_run_through_the_parent_fails_when_its_classification_breaks(
    project: Path, how: str, capsys: pytest.CaptureFixture[str]
) -> None:
    sdk, cc = str(_sdk()), _cc()
    _break_parent(project, how)
    code, doc = _json(capsys, "test", "--sdk", sdk, "--cc", cc)
    assert code == 6, (doc["error"], doc["result"] and doc["result"]["packets"])
    assert doc["error"]["code"] == "test.packet-failed"
    failed = [p for p in doc["result"]["packets"] if p["status"] != "pass"]
    assert [("through" in p) for p in failed] == [True], doc["result"]["packets"]
    first = failed[0]["failures"][0]
    if how == "offset":
        assert first == {
            "attribute": "<parent>",
            "expected": "udp at offset 42",
            "actual": "udp at offset 34",
        }
    else:
        assert (first["attribute"], first["actual"]) == ("<protocol>", "not classified")
