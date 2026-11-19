"""The examples (plan T5.1, #28; the WebSocket example, #40; the OCPP 1.6-J
example, #41), without an SDK.

Every example model of the corpus (``kind: example`` in
``tests/corpus/index.yaml``: the Java tool's ``plugins/<name>_plugin``, removed
by #78) has a project ``examples/<name>/``, a port, and ``NEW`` lists the
examples written with the tool instead (``examples/README.md``): each
``plugin.yaml`` validates with the profile it pins, ``generate --check``
finds the committed ``generated/`` and ``plugin.lock`` up to date, and the
packet tests load and name the example's protocol; a port's carry the bytes
of the corpus fixture they were ported from, a new example's give a source
for every value. ``tests/unit/examples/test_sdk.py`` builds and tests them
against a real SDK.
"""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path
from typing import Any

import pytest

from mmt_plugin import pluginyaml
from mmt_plugin.cli import main
from mmt_plugin.sdk.profile import DATA_TYPE_GROUP
from mmt_plugin.sdk.resolve import resolve_profile
from mmt_plugin.testing.packets import PacketTest, load
from mmt_plugin.testing.session import SessionTest, load_test
from mmt_plugin.testing.yamlsubset import loads

REPO = Path(__file__).resolve().parents[3]
EXAMPLES = REPO / "examples"
CORPUS = REPO / "tests" / "corpus" / "models"
PROFILE = "1.10.2"


def _example_models() -> list[str]:
    """The names of the corpus's example models."""
    path = REPO / "tests" / "corpus" / "validate.py"
    spec = importlib.util.spec_from_file_location("corpus_validate", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    index = module.load_yaml(REPO / "tests" / "corpus" / "index.yaml")
    return sorted(m["name"] for m in index["models"] if m["kind"] == "example")


#: The ports: the example models of the corpus.
PORTS = _example_models()
#: The examples that are not ports (no corpus model): written with mmt-plugin init.
NEW = ["ocpp", "websocket"]
#: Every example.
NAMES = sorted(PORTS + NEW)


def _json(capsys: pytest.CaptureFixture[str], *argv: str) -> tuple[int, dict[str, Any]]:
    code = main(["--json", *argv])
    doc: dict[str, Any] = json.loads(capsys.readouterr().out)
    return code, doc


def _protocol(name: str) -> tuple[str, int]:
    """The example's label and id."""
    path = EXAMPLES / name / "plugin.yaml"
    read = pluginyaml.load(path.read_text(), filename=str(path))
    assert read.sdk_profile == PROFILE, name
    properties = read.model.properties
    return properties.label.text, properties.id.value


def _readme_rows() -> dict[str, tuple[str, int]]:
    rows = {}
    for line in (EXAMPLES / "README.md").read_text().splitlines():
        m = re.match(r"\| `(\w+)` \| `(\w+)` \| (\d+) \|", line)
        if m:
            rows[m.group(1)] = (m.group(2), int(m.group(3)))
    return rows


def test_every_example_model_has_a_project() -> None:
    assert len(PORTS) == 16
    assert not set(NEW) & set(PORTS)
    projects = sorted(p.parent.name for p in EXAMPLES.glob("*/plugin.yaml"))
    assert projects == NAMES


def test_the_readme_lists_every_example_with_its_label_and_id() -> None:
    rows = _readme_rows()
    assert sorted(rows) == NAMES
    for name in NAMES:
        assert rows[name] == _protocol(name), name


def test_labels_and_ids_are_distinct_third_party_ones() -> None:
    labels, ids = zip(*(_protocol(n) for n in NAMES), strict=True)
    assert all(re.fullmatch(r"[a-z][a-z0-9_]*_example", label) for label in labels), labels
    assert all(950 <= i <= 999 for i in ids), ids
    assert len(set(labels)) == len(set(ids)) == len(NAMES)


@pytest.mark.parametrize("name", NAMES)
def test_the_model_validates_with_its_pinned_profile(
    name: str, capsys: pytest.CaptureFixture[str]
) -> None:
    code, doc = _json(capsys, "-C", str(EXAMPLES / name), "validate", "--no-sdk")
    assert code == 0, doc["error"]
    errors = [d for d in doc["diagnostics"] if d["severity"] == "error"]
    assert errors == []
    assert doc["context"]["sdk"]["profile"] == PROFILE
    assert doc["context"]["sdk"]["profile_source"] == "plugin.yaml"
    assert doc["result"]["format"] == "yaml"
    checks = {c["id"]: c["status"] for c in doc["result"]["checks"]}
    assert checks["schema"] == checks["semantics"] == checks["id-range"] == "pass"


@pytest.mark.parametrize("name", NAMES)
def test_the_committed_generated_files_are_up_to_date(
    name: str, capsys: pytest.CaptureFixture[str]
) -> None:
    project = EXAMPLES / name
    label, _ = _protocol(name)
    code, doc = _json(capsys, "-C", str(project), "generate", "--check")
    hint = f"regenerate: uv run mmt-plugin -C examples/{name} generate"
    assert code == 0, (hint, doc["error"])
    assert sorted(p.name for p in (project / "generated").iterdir()) == [
        f"{label}_mmt_plugin.c",
        f"{label}_mmt_plugin.h",
    ]
    assert (project / "plugin.lock").is_file()
    assert (project / "src" / f"{label}_impl.c").is_file()
    assert (project / ".gitignore").read_text() == "build/\n"


@pytest.mark.parametrize("name", PORTS)
def test_the_packet_tests_are_the_corpus_packets_of_the_example(name: str) -> None:
    label, pid = _protocol(name)
    profile = resolve_profile(PROFILE, {}, None, None).profile
    types = {c.name for c in profile.constants if c.group == DATA_TYPE_GROUP}
    tests = sorted((EXAMPLES / name / "tests").glob("*.yaml"))
    corpus = sorted((CORPUS / name / "packets").glob("*.yaml"))
    assert [t.name for t in tests] == [c.name for c in corpus]
    for path, origin in zip(tests, corpus, strict=True):
        test = load(path, path.name, types)
        assert (test.protocol, test.proto_id) == (label.upper(), pid)
        assert test.id == f"{name}/{path.stem}"
        assert test.data == load(origin, origin.name, types).data, path
        # Only the corpus uses `undefined`: a port extracts every value it lists.
        assert all(a.status != "undefined" for a in test.attributes), path


@pytest.mark.parametrize("name", NEW)
def test_the_packet_tests_of_a_new_example_name_a_source_for_every_value(name: str) -> None:
    label, pid = _protocol(name)
    profile = resolve_profile(PROFILE, {}, None, None).profile
    types = {c.name for c in profile.constants if c.group == DATA_TYPE_GROUP}
    paths = sorted((EXAMPLES / name / "tests").glob("*.yaml"))
    assert paths, name
    for path in paths:
        found = load_test(path, path.name, types)
        assert (found.protocol, found.proto_id) == (label.upper(), pid)
        assert found.id == f"{name}/{path.stem}"
        doc = loads(path.read_bytes())
        assert doc["model"] == name, path
        if isinstance(found, SessionTest):
            # A session test (#99) names its source once, for every packet.
            assert path.stem.startswith("session-"), path
            assert str(doc.get("source", "")).strip(), path
            assert found.attributes, path
            continue
        test = found
        assert not path.stem.startswith("session-"), path
        assert test.attributes, path
        assert all(a.status != "undefined" for a in test.attributes), path
        # load() reads no source: every expected attribute names where its value comes from.
        for attr in doc["expect"]["attributes"]:
            assert str(attr.get("source", "")).strip(), (path, attr["name"])


@pytest.mark.parametrize("name", NAMES)
def test_an_example_with_a_parent_runs_one_packet_test_through_it(name: str) -> None:
    path = EXAMPLES / name / "plugin.yaml"
    parents = {
        p.protocol.text
        for p in pluginyaml.load(path.read_text(), filename=str(path)).model.parents
    }
    profile = resolve_profile(PROFILE, {}, None, None).profile
    types = {c.name for c in profile.constants if c.group == DATA_TYPE_GROUP}
    paths = sorted((EXAMPLES / name / "tests").glob("*.yaml"))
    tests = [t for t in (load_test(p, p.name, types) for p in paths) if isinstance(t, PacketTest)]
    through = [t.through for t in tests if t.through is not None]
    if not parents:
        assert through == [], name
        return
    # One test, through the parent plugin.yaml declares (tests/unit/examples/test_sdk.py
    # runs it, and breaks that parent's classification).
    assert len(through) == 1, name
    assert through[0].proto in parents, (name, through[0].text, parents)


@pytest.mark.parametrize("file", ["ws_inflate.c", "ws_inflate.h"])
def test_the_websocket_and_ocpp_examples_share_one_inflater(file: str) -> None:
    """The permessage-deflate decoder (#107) is one pair of files, copied
    into both projects (a project builds only its own src/): the copies
    must stay byte for byte the same."""
    websocket = (EXAMPLES / "websocket" / "src" / file).read_bytes()
    ocpp = (EXAMPLES / "ocpp" / "src" / file).read_bytes()
    assert websocket == ocpp, f"copy examples/websocket/src/{file} to examples/ocpp/src/"
