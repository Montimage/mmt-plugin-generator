"""The install manifest (``mmt_plugin.manifest``): its bytes, the hand-written
checks against the JSON Schema, and ``read_manifests``; and the plugin
directory compiled into ``libmmt_core`` (``mmt_plugin.sdk.registry``)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from mmt_plugin.manifest import (
    InstalledFile,
    Manifest,
    ManifestError,
    load_schema,
    parse_manifest,
    read_manifest,
    read_manifests,
    writable,
)
from mmt_plugin.sdk.detect import Sdk, SdkSource
from mmt_plugin.sdk.registry import compiled_plugin_dir, scanned_plugin_dir

SHA = "a" * 64
GOOD = Manifest("1.0", "tpkt", 961, "TPKT", (InstalledFile("mmtp_tpkt.so", SHA),))


def test_dumps_is_deterministic_and_valid() -> None:
    text = GOOD.dumps()
    assert text == GOOD.dumps()
    assert text.endswith("}\n")
    doc = json.loads(text)
    assert list(doc) == ["manifest_version", "tool", "label", "protocol", "files"]
    Draft202012Validator(load_schema()).validate(doc)
    assert parse_manifest(text, "m") == GOOD


def _bad(change: Any) -> dict[str, Any]:
    doc = GOOD.to_json()
    change(doc)
    return doc


BAD: list[tuple[str, Any]] = [
    ("version", lambda d: d.update(manifest_version=0)),
    ("bool version", lambda d: d.update(manifest_version=True)),
    ("extra key", lambda d: d.update(extra=1)),
    ("missing key", lambda d: d.pop("label")),
    ("tool name", lambda d: d["tool"].update(name="other")),
    ("label", lambda d: d.update(label="Bad-Label")),
    ("id", lambda d: d["protocol"].update(id=0)),
    ("bool id", lambda d: d["protocol"].update(id=True)),
    ("empty files", lambda d: d.update(files=[])),
    ("slash", lambda d: d["files"][0].update(path="../x.so")),
    ("dot", lambda d: d["files"][0].update(path="..")),
    ("sha", lambda d: d["files"][0].update(sha256="xyz")),
    ("twice", lambda d: d["files"].append(dict(d["files"][0]))),
]


@pytest.mark.parametrize(("why", "change"), BAD, ids=[b[0] for b in BAD])
def test_parse_refuses_what_the_schema_refuses(why: str, change: Any) -> None:
    doc = _bad(change)
    with pytest.raises(ManifestError):
        parse_manifest(json.dumps(doc), "m")
    if why != "twice":  # uniqueness is the parser's own rule
        assert not Draft202012Validator(load_schema()).is_valid(doc)


def test_parse_refuses_a_newer_version_and_bad_json() -> None:
    with pytest.raises(ManifestError, match="newer mmt-plugin"):
        parse_manifest(json.dumps(_bad(lambda d: d.update(manifest_version=2))), "m")
    with pytest.raises(ManifestError, match="not JSON"):
        parse_manifest("{", "m")


def test_read_manifests(tmp_path: Path) -> None:
    plugins = tmp_path / "plugins"
    assert read_manifests(plugins) == ([], [])
    (plugins / ".mmt-plugin").mkdir(parents=True)
    (plugins / ".mmt-plugin" / "tpkt.json").write_text(GOOD.dumps())
    (plugins / ".mmt-plugin" / "cotp.json").write_text(GOOD.dumps())  # wrong name
    (plugins / ".mmt-plugin" / "bad.json").write_text("[]")
    found, problems = read_manifests(plugins)
    assert found == [GOOD]
    assert len(problems) == 2
    assert read_manifest(plugins / "none.json") is None
    (plugins / ".mmt-plugin" / "latin.json").write_bytes(b"\xff")
    with pytest.raises(ManifestError, match="UTF-8"):
        read_manifest(plugins / ".mmt-plugin" / "latin.json")


def test_writable(tmp_path: Path) -> None:
    assert writable(tmp_path / "a" / "b" / "c")
    (tmp_path / "file").write_text("")
    assert not writable(tmp_path / "file" / "plugins")


def _sdk(prefix: Path) -> Sdk:
    return Sdk(str(prefix), SdkSource.CLI, "1.10.2")


def test_compiled_plugin_dir(tmp_path: Path) -> None:
    lib = tmp_path / "dpi" / "lib"
    lib.mkdir(parents=True)
    core = lib / "libmmt_core.so.1.10.2"
    core.write_bytes(b"\x7fELF\x00/home/x/opt/mmt/plugins\x00Error\x00/home/x/opt/mmt/plugins\x00")
    assert compiled_plugin_dir(str(core)) == "/home/x/opt/mmt/plugins"
    assert scanned_plugin_dir(_sdk(tmp_path), {}) == ("/home/x/opt/mmt/plugins", "libmmt_core")
    assert scanned_plugin_dir(_sdk(tmp_path), {"MMT_DPI_PLUGINS_DIR": "rel"}) == (
        "rel",
        "MMT_DPI_PLUGINS_DIR",
    )
    core.write_bytes(b"\x00/a/plugins\x00/b/plugins\x00")
    assert compiled_plugin_dir(str(core)) is None
    core.write_bytes(b"")
    assert scanned_plugin_dir(_sdk(tmp_path), {}) == (None, "unknown")
    assert scanned_plugin_dir(None, {}) == (None, "unknown")
    assert compiled_plugin_dir(str(tmp_path / "none")) is None
