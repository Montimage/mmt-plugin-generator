"""``mmt-plugin scaffold --from-pcap PCAP --parent SELECTOR``
(``docs/design/cli.md``, sections 4, 5, 6, 8): the files it writes, that a
re-run is a no-op, ``--dry-run``, ``--max-packets``, ``--tests-dir``, an
output in the way and ``--force``, that it never writes the model or
``plugin.yaml``, and the errors (a bad pcap, no payload, a bad selector, a
bad model)."""

from __future__ import annotations

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

from . import samples

#: The project's model: label demo, id 960.
MODEL = """schema: 1
protocol:
  label: demo
  id: 960
attributes:
  - name: version
    type: MMT_U8_DATA
    offset: 0
"""

Run = Callable[..., tuple[int, dict[str, Any]]]


@pytest.fixture
def work(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    cwd = tmp_path / "work"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    (cwd / "plugin.yaml").write_text(MODEL)
    frames = [samples.udp4(50000, 4433, p) for p in samples.demo_payloads()]
    frames.insert(1, samples.udp4(53, 53, b"dns"))
    frames.append(samples.udp4(50000, 4433, b""))
    (cwd / "capture.pcap").write_bytes(samples.pcap(frames))
    return cwd


@pytest.fixture
def scaffold(work: Path, capsys: pytest.CaptureFixture[str]) -> Run:
    """``mmt-plugin --json scaffold ARGS``, checked against the schemas."""
    envelope = Draft202012Validator(schemas.load_cli_schema(schemas.ENVELOPE))
    result = Draft202012Validator(schemas.result_schema("scaffold"))

    def go(*args: str) -> tuple[int, dict[str, Any]]:
        code = main(["--json", "scaffold", *args])
        out = capsys.readouterr()
        assert out.err == ""
        doc: dict[str, Any] = json.loads(out.out)
        envelope.validate(doc)
        assert doc["exit_code"] == code
        if doc["result"] is not None:
            result.validate(doc["result"])
        return code, doc

    return go


ARGS = ("--from-pcap", "capture.pcap", "--parent", "udp:port=4433")
TESTS = ["tests/demo-pcap-001.yaml", "tests/demo-pcap-002.yaml", "tests/demo-pcap-003.yaml"]


def _codes(doc: dict[str, Any]) -> list[str]:
    return [d["code"] for d in doc["diagnostics"]]


def test_scaffold_writes_the_proposal_and_one_test_per_payload(scaffold: Run, work: Path) -> None:
    code, doc = scaffold(*ARGS)
    assert code == 0, doc["error"]
    assert doc["diagnostics"] == []
    result = doc["result"]
    assert [f["path"] for f in result["files"]] == ["plugin.proposed.yaml", *TESTS]
    assert all(f["action"] == "created" for f in result["files"])
    for f in result["files"]:
        assert f["sha256"] == sha256_bytes((work / f["path"]).read_bytes())
    assert result["pcap"] == "capture.pcap"
    assert result["format"] == "pcap"
    assert result["parent"] == "udp:port=4433"
    assert result["model"] == "plugin.yaml"
    assert result["protocol"] == {"label": "demo", "name": "DEMO", "id": 960}
    assert result["packets"] == {
        "frames": 5,
        "payloads": 3,
        "skipped": {
            "no-match": 1,
            "empty": 1,
            "fragment": 0,
            "malformed": 0,
            "truncated": 0,
            "unsupported-link": 0,
        },
    }
    assert result["skeleton"]["header_length"] == 10
    assert [f["name"] for f in result["skeleton"]["fields"]][:3] == [
        "field_0",
        "field_1",
        "length",
    ]
    assert result["proposed"] == "plugin.proposed.yaml"
    assert result["tests_dir"] == "tests"
    assert result["dry_run"] is False
    assert (work / "plugin.yaml").read_text() == MODEL
    # The files name the capture by its file name, and the frame.
    assert '  source: "frame 3 of capture.pcap"' in (work / TESTS[1]).read_text().splitlines()


def test_a_second_run_is_a_no_op(scaffold: Run, work: Path) -> None:
    scaffold(*ARGS)
    stamp = (work / TESTS[0]).stat().st_mtime_ns
    code, doc = scaffold(*ARGS)
    assert code == 0
    assert {f["action"] for f in doc["result"]["files"]} == {"unchanged"}
    assert (work / TESTS[0]).stat().st_mtime_ns == stamp


def test_dry_run_writes_nothing(scaffold: Run, work: Path) -> None:
    code, doc = scaffold(*ARGS, "--dry-run")
    assert code == 0
    assert {f["action"] for f in doc["result"]["files"]} == {"would-create"}
    assert doc["result"]["dry_run"] is True
    assert not (work / "plugin.proposed.yaml").exists()
    assert not (work / "tests").exists()


def test_max_packets_and_tests_dir(scaffold: Run, work: Path) -> None:
    code, doc = scaffold(*ARGS, "--max-packets", "2", "--tests-dir", "drafts")
    assert code == 0, doc["error"]
    assert [f["path"] for f in doc["result"]["files"]] == [
        "drafts/demo-pcap-001.yaml",
        "drafts/demo-pcap-002.yaml",
        "plugin.proposed.yaml",
    ]
    assert doc["result"]["packets"]["frames"] == 3  # stopped at the second payload
    assert doc["result"]["tests_dir"] == "drafts"


def test_reading_stops_at_the_max_packets_th_payload(scaffold: Run, work: Path) -> None:
    # A broken tail after the second payload is never read with
    # --max-packets 2; read in full, it is a bad capture (#71).
    capture = work / "capture.pcap"
    capture.write_bytes(capture.read_bytes() + b"\xff" * 7)
    code, doc = scaffold(*ARGS, "--max-packets", "2")
    assert code == 0, doc["error"]
    assert doc["result"]["packets"]["frames"] == 3
    code, doc = scaffold(*ARGS)
    assert code == 3
    assert doc["error"]["code"] == "model.bad-pcap"
    assert "a truncated record header (7 of 16 bytes)" in doc["error"]["message"]


@pytest.mark.parametrize("value", ["0", "-1", "x"])
def test_max_packets_must_be_positive(scaffold: Run, value: str) -> None:
    code, doc = scaffold(*ARGS, "--max-packets", value)
    assert code == 2
    assert doc["error"]["code"] == "usage.invalid"  # as test's --fuzz-count
    assert "--max-packets" in doc["error"]["message"]


def test_an_output_with_other_content_is_exit_7_unless_force(scaffold: Run, work: Path) -> None:
    (work / "tests").mkdir()
    (work / TESTS[1]).write_text("mine\n")
    code, doc = scaffold(*ARGS)
    assert code == 7
    assert doc["error"]["code"] == "state.output-differs"
    assert _codes(doc) == ["state.output-differs"]
    assert doc["diagnostics"][0]["location"]["file"] == TESTS[1]
    assert {f["action"] for f in doc["result"]["files"]} == {"would-create", "would-update"}
    assert (work / TESTS[1]).read_text() == "mine\n"
    assert not (work / "plugin.proposed.yaml").exists()

    code, doc = scaffold(*ARGS, "--force")
    assert code == 0
    assert doc["diagnostics"][0]["severity"] == "warning"
    assert {f["path"]: f["action"] for f in doc["result"]["files"]}[TESTS[1]] == "updated"
    assert (work / TESTS[1]).read_text() != "mine\n"


def test_a_directory_or_a_file_in_the_way_is_exit_7_even_with_force(
    scaffold: Run, work: Path
) -> None:
    (work / "plugin.proposed.yaml").mkdir()
    code, doc = scaffold(*ARGS, "--force")
    assert code == 7
    assert "is a directory: not replaced" in doc["diagnostics"][0]["message"]
    (work / "plugin.proposed.yaml").rmdir()
    (work / "tests").write_text("a file\n")
    code, doc = scaffold(*ARGS, "--force")
    assert code == 7
    assert {d["message"] for d in doc["diagnostics"]} == {"tests is not a directory: not replaced"}
    assert not (work / "plugin.proposed.yaml").exists()


def test_a_symbolic_link_is_replaced_only_with_force(scaffold: Run, work: Path) -> None:
    (work / "elsewhere").write_text("x\n")
    (work / "plugin.proposed.yaml").symlink_to(work / "elsewhere")
    assert scaffold(*ARGS)[0] == 7
    assert scaffold(*ARGS, "--force")[0] == 0
    assert not (work / "plugin.proposed.yaml").is_symlink()
    assert (work / "elsewhere").read_text() == "x\n"


def test_scaffold_never_writes_the_model(scaffold: Run, work: Path) -> None:
    (work / "plugin.proposed.yaml").write_text(MODEL)
    code, doc = scaffold(*ARGS, "--model", "plugin.proposed.yaml", "--force")
    assert code == 2
    assert doc["error"]["code"] == "usage.conflicting-options"
    assert (work / "plugin.proposed.yaml").read_text() == MODEL
    # Nor a test file.
    (work / "tests").mkdir()
    (work / TESTS[0]).write_text(MODEL)
    code, doc = scaffold(*ARGS, "--model", TESTS[0], "--force")
    assert code == 2
    assert (work / TESTS[0]).read_text() == MODEL


def test_a_pdl_model_and_another_project(scaffold: Run, work: Path) -> None:
    project = work / "demo"
    project.mkdir()
    (project / "model.pdl").write_text(
        'Protocol {\n\tProperties { label = "Pdl" id = "961" }\n\tAttributes {\n'
        '\t\tattribute { alias="k" data_type="MMT_U8_DATA" offset="0" }\n\t}\n}\n'
    )
    code, doc = scaffold(*ARGS, "-C", "demo", "--model", "demo/model.pdl")
    assert code == 0, doc["error"]
    result = doc["result"]
    assert result["pcap"] == (work / "capture.pcap").as_posix()  # outside the project
    assert result["protocol"] == {"label": "Pdl", "name": "PDL", "id": 961}
    assert result["files"][0]["path"] == "plugin.proposed.yaml"
    assert (project / "tests" / "pdl-pcap-001.yaml").is_file()
    assert '  label: "Pdl"' in (project / "plugin.proposed.yaml").read_text().splitlines()


@pytest.mark.parametrize(
    ("content", "message"),
    [
        (b"not a capture at all", "is not a readable capture: not a pcap or pcapng file"),
        (samples.pcap([samples.udp4(1, 4433, b"abc")])[:-2], "only 43 bytes are left"),
    ],
)
def test_a_malformed_pcap_is_exit_3(
    scaffold: Run, work: Path, content: bytes, message: str
) -> None:
    (work / "capture.pcap").write_bytes(content)
    code, doc = scaffold(*ARGS)
    assert code == 3
    assert doc["error"]["code"] == "model.bad-pcap"
    assert message in doc["error"]["message"]
    assert not (work / "plugin.proposed.yaml").exists()


def test_a_missing_pcap_is_exit_3(scaffold: Run) -> None:
    code, doc = scaffold("--from-pcap", "nope.pcap", "--parent", "udp")
    assert code == 3
    assert doc["error"]["code"] == "model.bad-pcap"
    assert "cannot read nope.pcap" in doc["error"]["message"]


def test_a_directory_as_the_pcap_is_exit_3(scaffold: Run, work: Path) -> None:
    (work / "dir.pcap").mkdir()
    code, doc = scaffold("--from-pcap", "dir.pcap", "--parent", "udp")
    assert code == 3
    assert doc["error"]["code"] == "model.bad-pcap"
    assert "cannot read dir.pcap" in doc["error"]["message"]


def test_no_payload_under_the_parent_is_exit_3(scaffold: Run, work: Path) -> None:
    code, doc = scaffold("--from-pcap", "capture.pcap", "--parent", "tcp:port=102")
    assert code == 3
    assert doc["error"]["code"] == "model.no-payloads"
    assert "(5 frames: 5 no-match)" in doc["error"]["message"]
    assert not (work / "tests").exists()


@pytest.mark.parametrize("selector", ["UDP", "udp:port", "sctp", "udp:vlan=3"])
def test_a_bad_selector_is_a_usage_error(scaffold: Run, selector: str) -> None:
    code, doc = scaffold("--from-pcap", "capture.pcap", "--parent", selector)
    assert code == 2
    assert doc["error"]["code"] == "usage.invalid-value"


def test_both_options_are_required(scaffold: Run) -> None:
    assert scaffold("--parent", "udp")[0] == 2
    assert scaffold("--from-pcap", "capture.pcap")[0] == 2


def test_a_model_that_does_not_parse_is_exit_3(scaffold: Run, work: Path) -> None:
    (work / "plugin.yaml").write_text("schema: 2\n")
    code, doc = scaffold(*ARGS)
    assert code == 3
    assert doc["error"]["code"] == "model.schema"
    assert "nothing scaffolded" in doc["error"]["message"]
    assert not (work / "plugin.proposed.yaml").exists()


def test_a_proposal_that_does_not_generate_is_exit_3(scaffold: Run, work: Path) -> None:
    # The model parses, but its id is the SDK's TCP: generate refuses it.
    (work / "plugin.yaml").write_text(
        MODEL.replace("label: demo\n  id: 960", "label: tcp\n  id: 354")
    )
    code, doc = scaffold(*ARGS)
    assert code == 3
    assert doc["error"]["code"] in ("model.id-taken", "model.name-taken")
    assert "does not generate: nothing written" in doc["error"]["message"]
    assert not (work / "plugin.proposed.yaml").exists()


def test_pcapng_and_the_tool_written_samples(scaffold: Run, work: Path) -> None:
    data = Path(__file__).with_name("data")
    for name, fmt in (("demo-tcpdump.pcap", "pcap"), ("demo-editcap.pcapng", "pcapng")):
        code, doc = scaffold(
            "--from-pcap", str(data / name), "--parent", "udp:dport=4433", "--dry-run"
        )
        assert code == 0, doc["error"]
        assert doc["result"]["format"] == fmt
        assert doc["result"]["packets"]["payloads"] == 3
        assert doc["result"]["skeleton"]["length_field"] == {"name": "length", "adjust": 0}


def test_human_output(work: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["scaffold", *ARGS]) == 0
    out = capsys.readouterr().out
    assert out.splitlines() == [f"created\t{p}" for p in ["plugin.proposed.yaml", *TESTS]]


def test_tagged_frames_and_a_name_that_is_not_utf8(scaffold: Run, work: Path) -> None:
    name = os.fsdecode(b"cap\xff.pcap")
    frames = [samples.vlan(5, 0x88B5, p) for p in samples.demo_payloads()]
    (work / name).write_bytes(samples.pcap(frames))
    code, doc = scaffold("--from-pcap", name, "--parent", "ethernet:ethertype=0x88b5")
    assert code == 0, doc["error"]
    text = (work / "plugin.proposed.yaml").read_text()
    assert "classify:" not in text
    assert "cap\\udcff.pcap" in text
