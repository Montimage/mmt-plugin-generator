"""``mmt-plugin import PDL`` (``docs/design/cli.md``, sections 4, 5, 6, 7
and 8): the default output, ``-o FILE`` and ``-o -``, stdin, idempotency, an
output in the way and ``--force``, ``--dry-run``, ``--strict``, and the
model errors that write nothing."""

from __future__ import annotations

import io
import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from mmt_plugin import schemas
from mmt_plugin.cli import main
from mmt_plugin.fsio import sha256_bytes
from mmt_plugin.pluginyaml import load

#: A model that relied on no Java bug: no warning.
CLEAN = """// A comment, which plugin.yaml does not keep.
Protocol {
\tProperties { label = "demo" id = "960" encoding = "network" }
\tAttributes {
\t\tstruct demo_hdr { uint8_t version; uint16_t length; }
\t\tattribute { alias="tail" data_type="MMT_U8_DATA" data_len="1" offset="0" scope="packet" }
\t}
}
"""

#: The same model with an SDK id and name: two model.legacy-sdk-conflict warnings.
LEGACY = CLEAN.replace('label = "demo" id = "960"', 'label = "tpkt" id = "637"')

Run = Callable[..., tuple[int, dict[str, Any]]]


@pytest.fixture
def work(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    cwd = tmp_path / "work"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    (cwd / "model.pdl").write_text(CLEAN)
    (cwd / "legacy.pdl").write_text(LEGACY)
    return cwd


@pytest.fixture
def imp(work: Path, capsys: pytest.CaptureFixture[str]) -> Run:
    """``mmt-plugin --json import ARGS``, checked against the schemas."""
    envelope = Draft202012Validator(schemas.load_cli_schema(schemas.ENVELOPE))
    result = Draft202012Validator(schemas.result_schema("import"))

    def go(*args: str) -> tuple[int, dict[str, Any]]:
        code = main(["--json", "import", *args])
        out = capsys.readouterr()
        assert out.err == ""
        doc: dict[str, Any] = json.loads(out.out)
        envelope.validate(doc)
        assert doc["exit_code"] == code
        if doc["result"] is not None:
            result.validate(doc["result"])
        return code, doc

    return go


def _codes(doc: dict[str, Any]) -> list[str]:
    return [d["code"] for d in doc["diagnostics"]]


def test_import_writes_the_project_plugin_yaml(imp: Run, work: Path) -> None:
    code, doc = imp("model.pdl")
    assert code == 0, doc["error"]
    assert doc["diagnostics"] == []
    written = (work / "plugin.yaml").read_bytes()
    assert doc["result"] == {
        "input": "model.pdl",
        "output": "plugin.yaml",
        "model_hash": sha256_bytes(CLEAN.encode()),
        "protocol": {"label": "demo", "id": 960},
        "offsets": "absolute",
        "files": [{"path": "plugin.yaml", "action": "created", "sha256": sha256_bytes(written)}],
        "dry_run": False,
    }
    yaml = load(written.decode(), filename="plugin.yaml").model
    assert yaml.properties.label.text == "demo"
    # PDL v1's running offset placed tail after the 3-byte struct.
    assert "  - name: tail\n    type: MMT_U8_DATA\n    offset: 3\n" in written.decode()


def test_the_output_and_paths_follow_the_project(imp: Run, work: Path) -> None:
    (work / "proj").mkdir()
    code, doc = imp("-C", "proj", "model.pdl")
    assert code == 0, doc["error"]
    assert (work / "proj" / "plugin.yaml").is_file()
    assert doc["result"]["input"] == (work / "model.pdl").as_posix()
    assert doc["result"]["output"] == "plugin.yaml"
    code, doc = imp("model.pdl", "-o", "out/nested/p.yaml")
    assert code == 0, doc["error"]
    assert (work / "out" / "nested" / "p.yaml").read_bytes() == (
        work / "proj" / "plugin.yaml"
    ).read_bytes()


def test_a_rerun_is_a_no_op(imp: Run, work: Path) -> None:
    assert imp("model.pdl")[0] == 0
    target = work / "plugin.yaml"
    os.utime(target, (1_000_000, 1_000_000))
    code, doc = imp("model.pdl")
    assert code == 0
    assert doc["result"]["files"][0]["action"] == "unchanged"
    assert target.stat().st_mtime == 1_000_000


def test_other_content_is_exit_7_unless_force(imp: Run, work: Path) -> None:
    target = work / "plugin.yaml"
    target.write_text("schema: 1\n")
    code, doc = imp("model.pdl")
    assert code == 7
    assert doc["error"]["code"] == "state.output-differs"
    assert _codes(doc) == ["state.output-differs"]
    assert doc["result"]["files"][0]["action"] == "would-update"
    assert target.read_text() == "schema: 1\n"
    code, doc = imp("model.pdl", "--force")
    assert code == 0, doc["error"]
    assert doc["result"]["files"][0]["action"] == "updated"
    assert [d["severity"] for d in doc["diagnostics"]] == ["warning"]
    assert target.read_text().startswith("schema: 1\nprotocol:\n")


def test_a_symbolic_link_needs_force_and_a_directory_is_never_replaced(
    imp: Run, work: Path
) -> None:
    (work / "elsewhere.yaml").write_text("x: 1\n")
    (work / "plugin.yaml").symlink_to("elsewhere.yaml")
    code, doc = imp("model.pdl")
    assert code == 7 and "symbolic link" in doc["diagnostics"][0]["message"]
    code, doc = imp("model.pdl", "--force")
    assert code == 0, doc["error"]
    assert not (work / "plugin.yaml").is_symlink()
    assert (work / "elsewhere.yaml").read_text() == "x: 1\n"
    (work / "dir.yaml").mkdir()
    code, doc = imp("model.pdl", "-o", "dir.yaml", "--force")
    assert code == 7
    assert doc["error"]["code"] == "state.output-differs"
    assert "is a directory" in doc["error"]["message"]


def test_dry_run_writes_nothing(imp: Run, work: Path) -> None:
    code, doc = imp("model.pdl", "--dry-run")
    assert code == 0
    assert doc["result"]["files"][0]["action"] == "would-create"
    assert doc["result"]["dry_run"] is True
    assert not (work / "plugin.yaml").exists()
    (work / "plugin.yaml").write_text("old\n")
    code, doc = imp("model.pdl", "--dry-run", "--force")
    assert code == 0
    assert doc["result"]["files"][0]["action"] == "would-update"
    assert (work / "plugin.yaml").read_text() == "old\n"


def test_legacy_warnings_and_strict(imp: Run, work: Path) -> None:
    code, doc = imp("legacy.pdl")
    assert code == 0, doc["error"]
    assert _codes(doc) == ["model.legacy-sdk-conflict"] * 2
    assert doc["diagnostics"][0]["location"]["file"] == "legacy.pdl"
    (work / "plugin.yaml").unlink()
    code, doc = imp("legacy.pdl", "--strict")
    assert code == 3
    assert doc["error"]["code"] == "model.legacy-sdk-conflict"
    assert not (work / "plugin.yaml").exists()
    assert imp("model.pdl", "--strict")[0] == 0


@pytest.mark.parametrize(
    ("text", "code"),
    [
        ("Protocol {", "model.syntax.unexpected-end"),
        (CLEAN.replace('offset="0"', 'offset="val(nope)"'), "model.unknown-attribute"),
    ],
    ids=["syntax", "semantics"],
)
def test_a_model_error_is_exit_3_with_nothing_written(
    imp: Run, work: Path, text: str, code: str
) -> None:
    (work / "bad.pdl").write_text(text)
    status, doc = imp("bad.pdl")
    assert status == 3
    assert doc["error"]["code"] == code
    assert "nothing imported" in doc["error"]["message"]
    assert doc["result"] is None
    assert not (work / "plugin.yaml").exists()


def test_a_missing_input_is_exit_3(imp: Run) -> None:
    code, doc = imp("nope.pdl")
    assert code == 3 and doc["error"]["code"] == "model.unreadable"


def test_output_dash_prints_the_yaml_and_json_refuses_it(
    work: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["import", "model.pdl", "-o", "-"]) == 0
    out = capsys.readouterr()
    assert out.out.startswith("schema: 1\nprotocol:\n  label: demo\n")
    assert out.err == ""
    assert not (work / "plugin.yaml").exists()
    assert main(["import", "model.pdl", "-o", "-", "--json"]) == 2
    doc = json.loads(capsys.readouterr().out)
    assert doc["error"]["code"] == "usage.conflicting-options"
    assert not (work / "plugin.yaml").exists()


def test_stdin(
    work: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("sys.stdin", io.TextIOWrapper(io.BytesIO(LEGACY.encode())))
    assert main(["--json", "import", "-", "-o", "from-stdin.yaml"]) == 0
    doc = json.loads(capsys.readouterr().out)
    assert doc["result"]["input"] == "<stdin>"
    assert doc["diagnostics"][0]["location"]["file"] == "<stdin>"
    assert (work / "from-stdin.yaml").read_text().startswith("schema: 1\n")


def test_plain_and_styled_output(
    work: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    assert main(["import", "model.pdl"]) == 0
    assert capsys.readouterr().out == "created\tplugin.yaml\n"
    monkeypatch.setenv("FORCE_COLOR", "1")
    monkeypatch.setenv("COLUMNS", "100")
    assert main(["import", "model.pdl"]) == 0
    styled = capsys.readouterr().out
    assert "import demo" in styled and "offsets absolute" in styled and "unchanged" in styled
