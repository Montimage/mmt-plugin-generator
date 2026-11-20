"""The OCI-P plugin project ``ocip-plugin/project`` (#134, kept current by
#138), without an SDK.

It is not an example (``tests/unit/examples`` enumerates ``examples/`` and
expects ``*_example`` labels; its label ``ocip`` registers the name ``OCIP``
that mmt-security rule 232 reads), so these tests keep it current
instead: its ``plugin.yaml`` validates with the profile it pins,
``generate --check`` finds the committed ``generated/`` and ``plugin.lock``
up to date (a generator change or a version bump makes it stale, as it
makes every example stale), and its packet and session tests load and are
what ``ocip-plugin/inputs/make_tests.py`` writes; the sha256 that
``inputs/SOURCES.md`` and ``manifest.json`` record are the files' (#155).
``test_sdk.py`` builds it
and runs them against a real SDK.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from mmt_plugin.cli import main
from mmt_plugin.sdk.profile import DATA_TYPE_GROUP
from mmt_plugin.sdk.resolve import resolve_profile
from mmt_plugin.testing.packets import PacketTest
from mmt_plugin.testing.session import SessionTest, load_test
from mmt_plugin.testing.yamlsubset import loads

REPO = Path(__file__).resolve().parents[3]
WORK = REPO / "ocip-plugin"
PROJECT = WORK / "project"
PROFILE = "1.10.2"


def _json(capsys: pytest.CaptureFixture[str], *argv: str) -> tuple[int, dict[str, Any]]:
    code = main(["--json", *argv])
    doc: dict[str, Any] = json.loads(capsys.readouterr().out)
    return code, doc


def _types() -> set[str]:
    profile = resolve_profile(PROFILE, {}, None, None).profile
    return {c.name for c in profile.constants if c.group == DATA_TYPE_GROUP}


def test_the_model_validates_with_its_pinned_profile(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("MMT_PLUGIN_SDK_PROFILE", raising=False)
    code, doc = _json(capsys, "-C", str(PROJECT), "validate", "--no-sdk")
    assert code == 0, doc["error"]
    assert [d for d in doc["diagnostics"] if d["severity"] == "error"] == []
    assert doc["context"]["sdk"]["profile"] == PROFILE
    assert doc["context"]["sdk"]["profile_source"] == "plugin.yaml"
    checks = {c["id"]: c["status"] for c in doc["result"]["checks"]}
    assert checks["schema"] == checks["semantics"] == checks["id-range"] == "pass"


def test_the_committed_generated_files_are_up_to_date(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("MMT_PLUGIN_SDK_PROFILE", raising=False)
    code, doc = _json(capsys, "-C", str(PROJECT), "generate", "--check")
    hint = "regenerate: uv run mmt-plugin -C ocip-plugin/project generate"
    assert code == 0, (hint, doc["error"])
    assert sorted(p.name for p in (PROJECT / "generated").iterdir()) == [
        "ocip_mmt_plugin.c",
        "ocip_mmt_plugin.h",
    ]
    assert (PROJECT / "plugin.lock").is_file()
    assert (PROJECT / "src" / "ocip_impl.c").is_file()


def test_the_tests_load_and_name_a_source() -> None:
    paths = sorted((PROJECT / "tests").glob("*.yaml"))
    tests = [load_test(p, p.name, _types()) for p in paths]
    assert [t.id for t in tests] == [f"ocip/{p.stem}" for p in paths]
    assert all((t.protocol, t.proto_id) == ("OCIP", 960) for t in tests)
    sessions = [t for t in tests if isinstance(t, SessionTest)]
    packets = [t for t in tests if isinstance(t, PacketTest)]
    assert (len(packets), len(sessions)) == (10, 18)
    # Every packet test also runs through TCP port 2208, the plugin's parent.
    assert all(t.through is not None and t.through.text == "tcp:dport=2208" for t in packets)
    for path in paths:
        doc = loads(path.read_bytes())
        assert doc["model"] == "ocip", path
        if path.stem.startswith("session-"):
            assert str(doc.get("source", "")).strip(), path
        else:
            for attr in doc["expect"]["attributes"]:
                assert str(attr.get("source", "")).strip(), (path, attr["name"])


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_the_recorded_hashes_are_the_files_on_disk() -> None:
    # inputs/SOURCES.md and manifest.json record the sha256 of the work
    # folder's files (#155): each must be the file's, except the build
    # output, which is not committed (project/build/ is ignored).
    rows = re.findall(
        r"^\| `([^`]+)` \|.*\| `([0-9a-f]{64})` \|$",
        (WORK / "inputs" / "SOURCES.md").read_text(encoding="utf-8"),
        re.MULTILINE,
    )
    assert rows, "no hash in inputs/SOURCES.md"
    for name, digest in rows:
        assert _sha256(WORK / "inputs" / name) == digest, f"inputs/SOURCES.md: {name}"
    manifest = json.loads((WORK / "manifest.json").read_text(encoding="utf-8"))
    checked = 0
    for name, digest in manifest["files"].items():
        if name.startswith("project/build/"):
            continue
        assert _sha256(WORK / name) == digest, f"manifest.json: {name}"
        checked += 1
    assert checked >= len(rows) + 1, manifest["files"]


def test_the_tests_are_what_make_tests_writes(tmp_path: Path) -> None:
    # The tests come from the wire format by ocip-plugin/inputs/make_tests.py
    # (stdlib only), never edited by hand.
    script = WORK / "inputs" / "make_tests.py"
    run = subprocess.run(
        [sys.executable, "-I", str(script), str(tmp_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert run.returncode == 0, run.stderr
    written = sorted(p.name for p in tmp_path.glob("*.yaml"))
    assert written == sorted(p.name for p in (PROJECT / "tests").glob("*.yaml"))
    for name in written:
        assert (tmp_path / name).read_bytes() == (PROJECT / "tests" / name).read_bytes(), name
