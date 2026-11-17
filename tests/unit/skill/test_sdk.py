"""The mmt-plugin-generator skill's evals against a real mmt-dpi SDK (plan T4.2,
#27, "Verify: the evals pass").

Every case of ``skills/mmt-plugin-generator/evals/cases/`` runs the whole loop of
the skill's ``SKILL.md``, ``validate``, ``generate``, ``build`` and ``test``,
each with ``--json``, until its last run is green: every packet test passes,
``validate``'s ``parents-exist`` is ``pass``, and every envelope keeps the
contract of ``references/contract.md`` (and the package's JSON Schemas). The
SDK is an extracted mmt-dpi package, a private prefix (never
``/opt/mmt``)::

    MMT_GOLDEN_SDK=<dir>/opt/mmt MMT_GOLDEN_CC=gcc uv run pytest tests/unit/skill/test_sdk.py

Without ``MMT_GOLDEN_SDK`` the tests skip, unless
``MMT_REQUIRE_GOLDEN_COMPILE=1`` (CI's "Generated code" job) makes them fail.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest

import make_pcap
import pcap_eval
import run_evals

from .test_evals import CASES, validate_schemas

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
    return Path(prefix).resolve()


def _cc() -> str:
    cc = os.environ.get(CC_ENV, "gcc")
    if shutil.which(cc) is None:
        _skip_or_fail(f"{cc} is not installed")
    return cc


@pytest.mark.parametrize("case_dir", CASES, ids=lambda p: p.name)
def test_the_case_goes_green_with_the_sdk(case_dir: Path, tmp_path: Path) -> None:
    sdk, cc = _sdk(), _cc()
    result = run_evals.run_case(case_dir, work=tmp_path, sdk=sdk, cc=cc)
    assert result.problems == []
    assert result.ok
    validate_schemas(result)
    last = max(s.run for s in result.steps)
    assert [s.command for s in result.steps if s.run == last] == list(run_evals.LOOP_COMMANDS)
    # Every loop run that is not the last one stopped on a failure.
    for n in range(1, last):
        assert any(s.run == n and s.returncode != 0 for s in result.steps), n


@pytest.mark.parametrize("tshark", [True, False], ids=["tshark", "no-tshark"])
def test_the_capture_evaluation_passes_on_a_synthetic_capture(
    tshark: bool, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Step 1 and Step 6 of SKILL.md: the spec-telem case's plugin, built by
    its loop, evaluated on a capture make_pcap.py writes from the spec's two
    examples (both directions: mmt-dpi classifies the UDP session), then on
    one whose port is not TELEM's; with tshark, and without it (the expected
    frames then come from mmt_plugin.pcap)."""
    sdk, cc = _sdk(), _cc()
    if tshark and shutil.which("tshark") is None:
        pytest.skip("tshark is not installed")
    if not tshark:
        real_which = shutil.which
        monkeypatch.setattr(
            shutil, "which", lambda name: None if name == "tshark" else real_which(name)
        )
    case = next(c for c in CASES if c.name == "spec-telem")
    result = run_evals.run_case(case, work=tmp_path / "work", sdk=sdk, cc=cc)
    assert result.ok, result.problems
    plugin = tmp_path / "work" / "telem" / "build" / "mmtp_telem.so"
    assert plugin.is_file()

    capture = tmp_path / "telem.pcap"
    reading, ack = "12 01 00 0c 00 00 00 2a de ad be ef", "s:10 02 00 08 00 00 00 2a"
    args = ["--parent", "udp:dport=5684", "--out", str(capture), "--repeat", "2"]
    assert make_pcap.main([*args, "--payload", reading, "--payload", ack]) == 0
    out = tmp_path / "eval"
    common = ["--sdk", str(sdk), "--cc", cc, "--plugin", str(plugin), "--label", "telem"]
    common += ["--parent", "udp:dport=5684", "--synthetic"]
    assert pcap_eval.main([*common, "--capture", str(capture), "--out", str(out)]) == 0
    report = json.loads((out / "report.json").read_text("utf-8"))
    assert report["verdict"] == "PASS", report["problems"]
    assert (report["expected"]["frames"], report["claimed"], report["recall"]) == (4, 4, 1.0)
    attrs = report["attributes"]
    assert attrs["version"]["values"] == {"1": 4}
    assert attrs["msg_type"]["values"] == {"1": 2, "2": 2}
    assert attrs["payload"]["values"] == {"deadbeef": 2}
    assert any("synthetic" in w for w in report["warnings"])
    assert report["expected"]["source"] == ("tshark" if tshark else "mmt_plugin.pcap")
    assert (out / "report.md").read_text("utf-8").startswith("# Capture evaluation: telem — PASS")
    lines = (out / "frames.jsonl").read_text("utf-8").splitlines()
    assert [json.loads(line)["frame"] for line in lines] == [1, 2, 3, 4]
    if tshark:
        assert report["drift"]["checked"] and report["drift"]["items"] == []
        # The drift check against tshark: the message length agrees with
        # tshark's data.len (no drift), never with udp.length (8 bytes more
        # in every frame: a drift, a defect until accepted).
        same = ["--decode-as", "udp.port==5684,data", "--field", "length=data.len"]
        assert pcap_eval.main([*common, "--capture", str(capture), "--out", str(out), *same]) == 0
        report = json.loads((out / "report.json").read_text("utf-8"))
        assert report["fields"]["length"]["agreement"] == 1.0
        assert report["drift"]["items"] == []
        drift = ["--field", "length=udp.length"]
        assert pcap_eval.main([*common, "--capture", str(capture), "--out", str(out), *drift]) == 1
        report = json.loads((out / "report.json").read_text("utf-8"))
        (item,) = report["drift"]["items"]
        assert (item["key"], item["frames"], item["status"]) == ("length", 4, "defect")
        accept = [*drift, "--accept", "length=udp.length counts the UDP header"]
        assert (
            pcap_eval.main([*common, "--capture", str(capture), "--out", str(out), *accept]) == 0
        )
        report = json.loads((out / "report.json").read_text("utf-8"))
        assert report["drift"]["items"][0]["status"] == "accepted"
    else:
        assert not report["drift"]["checked"]

    other = tmp_path / "other.pcap"
    assert (
        make_pcap.main(["--parent", "udp:dport=9999", "--out", str(other), "--payload", reading])
        == 0
    )
    out2 = tmp_path / "eval-other"
    assert pcap_eval.main([*common, "--capture", str(other), "--out", str(out2)]) == 1
    failed = json.loads((out2 / "report.json").read_text("utf-8"))
    assert failed["verdict"] == "FAIL"
    assert failed["claimed"] == 0
