"""``init``, ``scaffold --from-pcap`` then ``test`` against a real mmt-dpi
SDK (plan T4.1, "Verify: tests on sample pcaps").

In a temporary directory, ``mmt-plugin init demo`` creates a project, then
``mmt-plugin scaffold`` slices a sample capture (``samples``, and the
tcpdump-written ``data/demo-tcpdump.pcap``) into packet tests and
``plugin.proposed.yaml``. Copied over ``plugin.yaml``, the proposal builds
(generate, compile with ``-Wall -Wextra -Werror``, link) and passes every
packet test scaffold wrote, also under ``--sanitize``, whether the user code
attaches the parent (``udp:port``) or the generated code does
(``udp:dport``, ``ethernet:ethertype``). The SDK is an extracted mmt-dpi
package, a private prefix (never ``/opt/mmt``)::

    MMT_GOLDEN_SDK=<dir>/opt/mmt MMT_GOLDEN_CC=gcc uv run pytest tests/unit/scaffold/test_sdk.py

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

from . import samples

SDK_ENV = "MMT_GOLDEN_SDK"
CC_ENV = "MMT_GOLDEN_CC"
REQUIRE_ENV = "MMT_REQUIRE_GOLDEN_COMPILE"
DATA = Path(__file__).with_name("data")


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
    (cwd / "udp.pcapng").write_bytes(
        samples.pcapng(
            [
                samples.udp4(50000, 4433, samples.demo_payload(2, 7, b"first")),
                samples.udp4(53, 53, b"dns"),
                samples.ethernet(
                    0x86DD,
                    samples.ipv6(17, samples.udp(4433, 50000, samples.demo_payload(4, 8, b""))),
                ),
                samples.udp4(50000, 4433, samples.demo_payload(3, 0x10009, b"third one")),
            ]
        )
    )
    (cwd / "eth.pcap").write_bytes(
        samples.pcap([samples.ethernet(0x88B6, p) for p in samples.demo_payloads()])
    )
    return cwd


@pytest.mark.parametrize(
    ("pcap", "parent", "payloads"),
    [
        ("udp.pcapng", "udp:port=4433", 3),
        (str(DATA / "demo-tcpdump.pcap"), "udp:dport=4433", 3),
        ("eth.pcap", "ethernet:ethertype=0x88b6", 3),
    ],
)
def test_the_proposal_passes_the_tests_scaffold_wrote(
    work: Path, capsys: pytest.CaptureFixture[str], pcap: str, parent: str, payloads: int
) -> None:
    code, doc = _json(capsys, "init", "demo", "--id", "977", "--parent", parent)
    assert code == 0, doc["error"]
    project = work / "demo"
    code, doc = _json(
        capsys, "-C", "demo", "scaffold", "--from-pcap", pcap, "--parent", parent,
    )  # fmt: skip
    assert code == 0, doc["error"]
    assert doc["result"]["packets"]["payloads"] == payloads
    tests = [f["path"] for f in doc["result"]["files"] if f["path"].startswith("tests/")]
    assert len(tests) == payloads

    shutil.copy(project / "plugin.proposed.yaml", project / "plugin.yaml")
    argv = ["-C", "demo", "test", "--model", "demo/plugin.yaml"]
    argv += [str(project / t) for t in tests]
    code, doc = _json(capsys, *argv)
    assert code == 0, doc["error"] or doc["result"]["packets"]
    assert doc["result"]["summary"] == {
        "total": payloads,
        "passed": payloads,
        "failed": 0,
        "skipped": 0,
    }
    code, doc = _json(capsys, *argv, "--sanitize", "--fuzz-count", "20")
    assert code == 0, doc["error"]
    assert doc["result"]["sanitize"]["crashes"] == []

    # A second scaffold is a no-op, and plugin.yaml was never touched by it.
    code, doc = _json(
        capsys, "-C", "demo", "scaffold", "--from-pcap", pcap, "--parent", parent,
    )  # fmt: skip
    assert code == 0, doc["error"]
    assert {f["action"] for f in doc["result"]["files"]} == {"unchanged"}
