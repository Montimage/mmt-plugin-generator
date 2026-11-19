"""``mmt_plugin.lock``: the plugin.lock format, its schema and its checks."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from mmt_plugin.lock import (
    LOCK_VERSION,
    Lock,
    LockedFile,
    LockError,
    load_schema,
    parse_lock,
    read_lock,
)

SHA = "a" * 64


def sample() -> Lock:
    return Lock(
        generator="mmt-plugin",
        generator_version="0.1.0",
        sdk_profile="1.10.2",
        model_format="pdl",
        model_sha256=SHA,
        files=(LockedFile("generated/x.h", "b" * 64), LockedFile("generated/x.c", "c" * 64)),
    )


def test_a_lock_round_trips_deterministically_and_matches_its_schema() -> None:
    lock = sample()
    text = lock.dumps()
    assert text.endswith("}\n") and text.isascii()
    assert parse_lock(text) == lock
    assert [f.path for f in lock.files] == ["generated/x.c", "generated/x.h"]  # sorted
    doc = json.loads(text)
    assert list(doc) == ["lock_version", "generator", "sdk_profile", "model", "files"]
    assert doc["lock_version"] == LOCK_VERSION == 1
    Draft202012Validator.check_schema(load_schema())
    Draft202012Validator(load_schema()).validate(doc)
    assert sample().dumps() == text


def test_lock_file_lookup() -> None:
    assert sample().file("generated/x.c") == LockedFile("generated/x.c", "c" * 64)
    assert sample().file("nope") is None


def _doc(**changes: Any) -> dict[str, Any]:
    doc = sample().to_json()
    doc.update(changes)
    return doc


@pytest.mark.parametrize(
    ("doc", "message"),
    [
        ([], "is not an object"),
        (_doc(extra=1), "unknown keys: extra"),
        ({k: v for k, v in _doc().items() if k != "files"}, "has no files"),
        (_doc(lock_version=0), "lock_version is not 1"),
        (_doc(lock_version=True), "lock_version is not 1"),
        (_doc(lock_version=2), "written by a newer mmt-plugin"),
        (_doc(sdk_profile=""), "sdk_profile is not a non-empty string"),
        (_doc(model={"format": "xml", "sha256": SHA}), "model.format"),
        (_doc(model={"format": "pdl", "sha256": "A" * 64}), "model.sha256 is not valid"),
        (_doc(files={}), "files is not an array"),
        (_doc(files=[{"path": "/abs.c", "sha256": SHA}]), "not a relative POSIX path"),
        (_doc(files=[{"path": "a\\b.c", "sha256": SHA}]), "not a relative POSIX path"),
        (_doc(files=[{"path": "a//b.c", "sha256": SHA}]), "not normalised"),
        (_doc(files=[{"path": "./b.c", "sha256": SHA}]), "not normalised"),
        (_doc(files=[{"path": "b.c", "sha256": "x"}]), "sha256 is not valid"),
        (_doc(files=[{"path": "b.c", "sha256": SHA}] * 2), "listed twice"),
    ],
)
def test_an_invalid_lock_is_refused_by_the_loader_and_the_schema(doc: Any, message: str) -> None:
    with pytest.raises(LockError, match=message):
        parse_lock(json.dumps(doc), "plugin.lock")
    if "listed twice" not in message:  # the schema cannot say "unique by path"
        assert not Draft202012Validator(load_schema()).is_valid(doc)


def test_text_that_is_not_json_is_refused() -> None:
    with pytest.raises(LockError, match="not JSON"):
        parse_lock("{", "x/plugin.lock")


def test_read_lock(tmp_path: Path) -> None:
    path = tmp_path / "plugin.lock"
    assert read_lock(path) is None
    path.write_bytes(b"\xff")
    with pytest.raises(LockError, match="not UTF-8"):
        read_lock(path)
    path.write_text(sample().dumps())
    assert read_lock(path) == sample()
