"""``mmt-plugin run PCAP`` with a fake SDK, the fake compiler of the build
tests (``tests/unit/build/fakes.py``) and the fake runner of ``fakes.py``
in place of the compiled one (the real ``mmt_plugin.capture.runner.run``
streams to it): the stages, the counts, the warnings and ``--strict``,
crashes, load failures, broken captures, ``--no-deps`` and ``--dry-run``,
``--plugin`` and ``--protocol``, the result schema and the output.
``test_sdk.py`` runs the real runner against a real mmt-dpi."""

from __future__ import annotations

import importlib.util
import json
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from mmt_plugin import schemas
from mmt_plugin.capture import runner as runner_mod
from mmt_plugin.cli import main
from mmt_plugin.codegen import scaffold
from mmt_plugin.commands import run as run_module
from mmt_plugin.commands.generate import make_generation
from mmt_plugin.commands.run import RunCommand
from mmt_plugin.sdk.resolve import resolve_profile
from mmt_plugin.ui.streams import ColorTier, StreamStyle

from . import fakes

samples = fakes.SAMPLES

MODEL = """Protocol {
    Properties { label = "fakeproto" id = "991" encoding = "network" }
    Attributes {
        attribute { alias="kind" data_type="MMT_U8_DATA" data_len="1" offset="0" scope="packet" }
        attribute { alias="size" data_type="MMT_U16_DATA" data_len="2" offset="1" scope="packet" }
    }
}
"""

Run = Callable[..., tuple[int, dict[str, Any]]]


def _build_fakes() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "run_build_fakes", Path(__file__).parents[1] / "build" / "fakes.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BUILD_FAKES = _build_fakes()


def _dns(n: int, size: int = 0) -> bytes:
    frame: bytes = samples.udp4(40000 + n, 53, bytes(8 + size))
    return frame


def _other(n: int) -> bytes:
    frame: bytes = samples.udp4(1000 + n, 9999, b"xx")
    return frame


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The current directory: ``model.pdl``, its scaffold, ``capture.pcap``
    (3 frames to port 53, one of them long, and 2 others)."""
    work = tmp_path / "project"
    (work / "src").mkdir(parents=True)
    (work / "model.pdl").write_text(MODEL)
    choice = resolve_profile("1.10.2", {}, None, None)
    generation, _, _ = make_generation("model.pdl", MODEL.encode(), choice)
    assert generation is not None
    impl = scaffold(generation, choice.profile)
    (work / impl.path).write_text(impl.text)
    frames = [_dns(1, 40), _other(1), _dns(2), _other(2), _dns(3)]
    (work / "capture.pcap").write_bytes(samples.pcap(frames))
    monkeypatch.chdir(work)
    for name in ("MMT_PLUGIN_SDK_PROFILE", "MMT_BASE", "CC", "FAKE_CC_LINK_FAIL"):
        monkeypatch.delenv(name, raising=False)
    return work


@pytest.fixture
def sdk(tmp_path: Path) -> Path:
    root: Path = BUILD_FAKES.fake_sdk(tmp_path / "sdk")
    (root / "plugins").mkdir()
    for name in ("libmmt_tcpip.so", "libmmt_business_app.so", "README"):
        (root / "plugins" / name).write_text("fake\n")
    return root


@pytest.fixture
def cc(tmp_path: Path) -> Path:
    path: Path = BUILD_FAKES.fake_cc(tmp_path / "bin")
    return path


@pytest.fixture
def log(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The fake runner's log; the compiled runner is replaced by the fake."""
    fake = fakes.fake_runner(tmp_path / "runner-bin")
    real = runner_mod.run
    programs: list[Path] = []

    def substitute(program: Path, *args: Any, **kwargs: Any) -> runner_mod.CaptureRun:
        assert program.is_file()  # what the (fake) compiler wrote
        programs.append(program)
        return real(fake, *args, **kwargs)

    monkeypatch.setattr(runner_mod, "run", substitute)
    path = tmp_path / "runner.log"
    monkeypatch.setenv("FAKE_RUNNER_LOG", str(path))
    for name in ("FAKE_RUNNER_ERROR", "FAKE_RUNNER_CRASH", "FAKE_RUNNER_SLEEP"):
        monkeypatch.delenv(name, raising=False)
    return path


@pytest.fixture
def run(tmp_path: Path, sdk: Path, cc: Path, log: Path, capsys: pytest.CaptureFixture[str]) -> Run:
    """``mmt-plugin --json run --model model.pdl --sdk SDK --cc CC ARGS``
    (``capture.pcap`` unless the first argument names a capture): the exit
    code and the envelope, checked against both schemas."""
    envelope = Draft202012Validator(schemas.load_cli_schema(schemas.ENVELOPE))
    result = Draft202012Validator(schemas.result_schema("run"))
    command = RunCommand(pkg_config_dirs=[], default_prefix=str(tmp_path / "no-sdk"))

    def go(*args: str) -> tuple[int, dict[str, Any]]:
        if not args or args[0].startswith("-"):
            args = ("capture.pcap", *args)
        argv = ["--json", "run", *args, "--model", "model.pdl", "--sdk", str(sdk), "--cc", str(cc)]
        code = main(argv, commands=[command])
        out = capsys.readouterr()
        doc: dict[str, Any] = json.loads(out.out)
        envelope.validate(doc)
        assert doc["exit_code"] == code
        if doc["result"] is not None:
            result.validate(doc["result"])
        return code, doc

    return go


def _stages(doc: dict[str, Any]) -> dict[str, str]:
    return {s["name"]: s["status"] for s in doc["result"]["stages"]}


def _codes(doc: dict[str, Any]) -> list[str]:
    return [d["code"] for d in doc["diagnostics"]]


def _logged(log: Path) -> list[dict[str, Any]]:
    return [json.loads(x) for x in log.read_text().splitlines()]


def test_the_plugin_runs_over_the_capture_and_its_counts_are_reported(
    project: Path, run: Run, log: Path
) -> None:
    code, doc = run()
    assert code == 0, doc["error"]
    assert _codes(doc) == []
    result = doc["result"]
    assert _stages(doc) == {"build": "ran", "runner": "ran", "capture": "ran"}
    assert result["capture"] == {"path": "capture.pcap", "format": "pcap", "linktype": 1}
    assert result["dry_run"] is False
    assert result["summary"] == {"frames": 5, "processed": 5, "skipped": 0, "classified": 3}
    assert result["plugins"] == [
        "libmmt_business_app.so",
        "libmmt_tcpip.so",
        "mmtp_fakeproto.so",
    ]
    assert result["paths"] == [
        {"path": "ethernet.ip.udp.FAKEPROTO", "ids": [99, 178, 354, 991], "packets": 3},
        {"path": "ethernet.ip.udp.unknown", "ids": [99, 178, 354, 0], "packets": 2},
    ]
    assert result["paths_other"] == 0
    assert result["protocols"] == [
        {
            "name": "FAKEPROTO",
            "id": 991,
            "packets": 3,
            "attributes": [
                {"id": 1, "name": "kind", "type": "MMT_U8_DATA", "packets": 3},
                {"id": 2, "name": "size", "type": "MMT_U16_DATA", "packets": 1},
            ],
        }
    ]
    assert set(result["stats"]) == {"elapsed_ms", "frames_per_second"}
    (entry,) = _logged(log)
    assert entry["argv"] == ["1", "991"]
    assert entry["plugins"] == result["plugins"]
    assert (project / "build" / "run" / "runner.c").is_file()

    code, again = run()
    assert code == 0
    assert _stages(again) == {"build": "up-to-date", "runner": "up-to-date", "capture": "ran"}
    for key in ("stats", "stages"):
        again["result"].pop(key)
        result.pop(key)
    assert again["result"] == result


def test_max_packets_stops_after_n_frames(project: Path, run: Run) -> None:
    code, doc = run("--max-packets", "2")
    assert code == 0
    assert doc["result"]["summary"] == {
        "frames": 2,
        "processed": 2,
        "skipped": 0,
        "classified": 1,
    }


def test_no_packet_of_the_protocol_is_a_warning_and_strict_fails_on_it(
    project: Path, run: Run
) -> None:
    (project / "none.pcap").write_bytes(samples.pcap([_other(1), _other(2)]))
    code, doc = run("none.pcap")
    assert code == 0
    assert _codes(doc) == ["test.no-match"]
    assert "none of 2 frames" in doc["diagnostics"][0]["message"]
    code, doc = run("none.pcap", "--strict")
    assert code == 6
    assert doc["error"]["code"] == "test.no-match"
    assert doc["result"]["summary"]["frames"] == 2


def test_an_empty_capture_runs_and_has_no_match(project: Path, run: Run) -> None:
    (project / "empty.pcap").write_bytes(samples.pcap([]))
    code, doc = run("empty.pcap")
    assert code == 0
    assert _codes(doc) == ["test.no-match"]
    assert "the capture has no frame" in doc["diagnostics"][0]["message"]
    assert doc["result"]["capture"]["linktype"] is None


def test_frames_of_another_link_type_are_skipped_with_a_warning(project: Path, run: Run) -> None:
    data = samples.pcapng([_dns(1), _dns(2)]) + samples.pcapng([bytes(16) + _dns(3)[14:]], 113)
    (project / "two.pcapng").write_bytes(data)
    code, doc = run("two.pcapng")
    assert code == 0
    assert _codes(doc) == ["test.other-linktype"]
    assert doc["result"]["summary"] == {
        "frames": 3,
        "processed": 2,
        "skipped": 1,
        "classified": 2,
    }
    assert doc["result"]["capture"] == {"path": "two.pcapng", "format": "pcapng", "linktype": 1}


def test_protocol_counts_another_protocol_and_warns_on_an_unknown_one(
    project: Path, run: Run, log: Path
) -> None:
    code, doc = run("--protocol", "udp", "--protocol", "nope")
    assert code == 0
    assert _codes(doc) == ["test.unknown-protocol"]
    assert [(p["name"], p["id"]) for p in doc["result"]["protocols"]] == [
        ("FAKEPROTO", 991),
        ("udp", 354),
        ("nope", None),
    ]
    assert _logged(log)[0]["argv"] == ["1", "991", "udp", "nope"]


def test_a_crash_is_exit_6_and_names_the_frame(
    project: Path, run: Run, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_RUNNER_CRASH", "4")
    code, doc = run()
    assert code == 6
    assert doc["error"]["code"] == "test.crash"
    assert "frame 4" in doc["error"]["message"] and "SIGSEGV" in doc["error"]["message"]
    assert _stages(doc)["capture"] == "failed"
    # Only the frames before the crash are known to be processed.
    assert doc["result"]["summary"] == {
        "frames": 3,
        "processed": 3,
        "skipped": 0,
        "classified": 0,
    }


def test_a_timeout_is_a_crash(project: Path, run: Run, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_RUNNER_SLEEP", "30")
    code, doc = run("--timeout", "0.5")
    assert code == 6
    assert doc["error"]["code"] == "test.crash"
    assert "timed out" in doc["error"]["message"]


def test_a_plugin_that_does_not_load_is_exit_6(
    project: Path, run: Run, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_RUNNER_ERROR", "init_extraction() failed: a plugin did not load")
    code, doc = run()
    assert code == 6
    assert doc["error"]["code"] == "test.load-failed"
    assert "init_extraction() failed" in doc["error"]["message"]
    assert _stages(doc) == {"build": "ran", "runner": "ran", "capture": "failed"}


def test_a_file_that_is_not_a_capture_is_exit_3_before_anything_is_built(
    project: Path, run: Run
) -> None:
    (project / "notes.txt").write_text("not a capture\n")
    code, doc = run("notes.txt")
    assert code == 3
    assert doc["error"]["code"] == "model.bad-pcap"
    assert doc["result"] is None
    assert not (project / "build").exists()
    code, doc = run("missing.pcap")
    assert code == 3 and doc["error"]["code"] == "model.bad-pcap"


def test_a_capture_broken_after_its_header_reports_the_frames_before(
    project: Path, run: Run
) -> None:
    data = samples.pcap([_dns(1), _other(1), _dns(2)])
    (project / "cut.pcap").write_bytes(data[:-5])
    code, doc = run("cut.pcap")
    assert code == 3
    assert doc["error"]["code"] == "model.bad-pcap"
    assert "after 2 frames" in doc["error"]["message"]
    assert doc["result"]["summary"]["frames"] == 2
    assert doc["result"]["summary"]["classified"] == 1
    assert _stages(doc)["capture"] == "ran"
    (diagnostic,) = [d for d in doc["diagnostics"] if d["code"] == "model.bad-pcap"]
    assert diagnostic["location"]["file"] == "cut.pcap"


def test_no_deps_is_exit_7_while_the_plugin_is_stale(project: Path, run: Run, log: Path) -> None:
    code, doc = run("--no-deps")
    assert code == 7
    assert doc["error"]["code"] == "state.stale"
    assert _stages(doc) == {"build": "stale", "runner": "skipped", "capture": "skipped"}
    assert not log.exists()


def test_dry_run_compiles_and_runs_nothing(project: Path, run: Run, log: Path) -> None:
    code, doc = run("--dry-run")
    assert code == 0
    assert doc["result"]["dry_run"] is True
    assert _stages(doc) == {"build": "stale", "runner": "skipped", "capture": "skipped"}
    assert not (project / "build").exists()
    assert run()[0] == 0
    log.unlink()
    code, doc = run("--dry-run")
    assert code == 0
    assert _stages(doc) == {"build": "up-to-date", "runner": "skipped", "capture": "skipped"}
    assert not log.exists()


def test_a_plugin_replaces_the_sdk_plugin_of_its_name(
    project: Path, run: Run, tmp_path: Path
) -> None:
    other = tmp_path / "other"
    other.mkdir()
    (other / "mmtp_other_example.so").write_text("other\n")
    (other / "libmmt_business_app.so").write_text("mine\n")
    code, doc = run(
        "--plugin",
        str(other / "mmtp_other_example.so"),
        "--plugin",
        str(other / "libmmt_business_app.so"),
        "--protocol",
        "other_example",
    )
    assert code == 0, doc["error"]
    assert doc["result"]["plugins"] == [
        "libmmt_business_app.so",
        "libmmt_tcpip.so",
        "mmtp_fakeproto.so",
        "mmtp_other_example.so",
    ]
    assert doc["result"]["protocols"][1]["name"] == "OTHER_EXAMPLE"


@pytest.mark.parametrize(
    ("make", "message"),
    [
        (lambda d: d / "missing.so", "not a file"),
        (lambda d: d / "mmtp_fakeproto.so", "the plugin's own file name"),
    ],
)
def test_bad_plugins_are_usage_errors(
    project: Path,
    run: Run,
    tmp_path: Path,
    make: Callable[[Path], Path],
    message: str,
) -> None:
    (tmp_path / "mmtp_fakeproto.so").write_text("x\n")
    code, doc = run("--plugin", str(make(tmp_path)))
    assert code == 2
    assert doc["error"]["code"] == "usage.invalid-value"
    assert message in doc["error"]["message"]


def test_two_plugins_of_one_name_are_a_usage_error(
    project: Path, run: Run, tmp_path: Path
) -> None:
    for d in ("a", "b"):
        (tmp_path / d).mkdir()
        (tmp_path / d / "mmtp_x.so").write_text("x\n")
    code, doc = run(
        "--plugin", str(tmp_path / "a/mmtp_x.so"), "--plugin", str(tmp_path / "b/mmtp_x.so")
    )
    assert code == 2
    assert "two plugins named mmtp_x.so" in doc["error"]["message"]


def test_an_sdk_without_libmmt_tcpip_is_exit_4(project: Path, run: Run, sdk: Path) -> None:
    (sdk / "plugins" / "libmmt_tcpip.so").unlink()
    code, doc = run()
    assert code == 4
    assert doc["error"]["code"] == "sdk.invalid-prefix"


def test_a_runner_that_does_not_compile_is_exit_5(
    project: Path, run: Run, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert run()[0] == 0
    (project / "build" / "run" / ".runner.json").unlink()
    monkeypatch.setenv("FAKE_CC_LINK_FAIL", "1")
    code, doc = run()
    assert code == 5
    assert doc["error"]["code"] == "build.runner-failed"
    assert _stages(doc) == {"build": "up-to-date", "runner": "failed", "capture": "skipped"}


@pytest.mark.parametrize("args", [["-"], ["capture.pcap", "--model", "-"], ["--timeout", "x"]])
def test_bad_arguments_are_usage_errors(
    project: Path, sdk: Path, cc: Path, capsys: pytest.CaptureFixture[str], args: list[str]
) -> None:
    command = RunCommand(pkg_config_dirs=[], default_prefix="/nonexistent")
    argv = ["--json", "run", *args, "--sdk", str(sdk), "--cc", str(cc)]
    if args[0].startswith("--t"):
        argv.insert(2, "capture.pcap")
    assert main(argv, commands=[command]) == 2
    capsys.readouterr()


def _style() -> StreamStyle:
    return StreamStyle(styled=True, color=ColorTier.NONE, unicode=True, width=80)


def test_the_view_shows_the_paths_and_the_attribute_meters(project: Path, run: Run) -> None:
    code, doc = run()
    assert code == 0
    view = run_module._view("fakeproto", doc["result"], _style())
    lines = view.splitlines()
    assert lines[0].startswith("╭─┐run fakeproto┌")
    assert any("3" in x and "60.0%" in x and "ethernet.ip.udp.FAKEPROTO" in x for x in lines)
    assert any("FAKEPROTO (991): 3 packets" in x for x in lines)
    assert any(x.startswith("│   size ") and x.rstrip(" │").endswith("1") for x in lines)
    assert lines[-1].startswith("╰─┘5 frames · 3 fakeproto · built")
    assert "\x1b" not in view


def test_the_view_says_how_many_paths_it_leaves_out(project: Path, run: Run) -> None:
    _, doc = run()
    result = doc["result"]
    result["paths"] = [
        {"path": f"p{n}", "ids": [n], "packets": 1} for n in range(run_module.VIEW_PATHS + 3)
    ]
    result["paths_other"] = 7
    view = run_module._view("fakeproto", result, _style())
    assert "… 3 more paths, 7 packets of paths not kept (--json has every path)" in view


def test_plain_records_are_frames_paths_and_attributes(
    project: Path, sdk: Path, cc: Path, log: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    command = RunCommand(pkg_config_dirs=[], default_prefix="/nonexistent")
    argv = ["run", "capture.pcap", "--model", "model.pdl", "--sdk", str(sdk), "--cc", str(cc)]
    assert main(argv, commands=[command]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "frames\t5\t5\t0\t3",
        "path\t3\tethernet.ip.udp.FAKEPROTO",
        "path\t2\tethernet.ip.udp.unknown",
        "attribute\tFAKEPROTO\tkind\t3",
        "attribute\tFAKEPROTO\tsize\t1",
    ]


def test_a_linux_cooked_capture_is_read_as_mmt_dpis_sll_stack(
    project: Path, run: Run, log: Path
) -> None:
    sll = [bytes(16) + _dns(n)[14:] for n in range(3)]
    (project / "any.pcap").write_bytes(samples.pcap(sll, samples.SLL))
    code, doc = run("any.pcap")
    assert code == 0
    assert doc["result"]["capture"]["linktype"] == samples.SLL
    assert _logged(log)[0]["argv"][0] == "624"


def test_a_link_type_mmt_dpi_does_not_read_is_exit_3_before_anything_is_built(
    project: Path, run: Run
) -> None:
    (project / "raw.pcap").write_bytes(samples.pcap([_dns(1)[14:]], samples.RAW))
    code, doc = run("raw.pcap")
    assert code == 3
    assert doc["error"]["code"] == "model.unsupported-linktype"
    assert "link type, 101" in doc["error"]["message"]
    assert not (project / "build").exists()


def test_a_broken_first_record_is_exit_3_before_anything_is_built(project: Path, run: Run) -> None:
    (project / "cut.pcap").write_bytes(samples.pcap([_dns(1)])[:-5])
    code, doc = run("cut.pcap")
    assert code == 3
    assert doc["error"]["code"] == "model.bad-pcap"
    assert not (project / "build").exists()


def test_too_many_protocols_are_a_usage_error(project: Path, run: Run) -> None:
    args = [x for n in range(16) for x in ("--protocol", f"p{n}")]
    code, doc = run(*args)
    assert code == 2
    assert doc["error"]["code"] == "usage.invalid-value"
