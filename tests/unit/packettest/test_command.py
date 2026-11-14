"""``mmt-plugin test`` with a fake SDK, the fake compiler of the build tests
(``tests/unit/build/fakes.py``) and, where packets run, a fake harness run
(``mmt_plugin.testing.harness.run`` replaced): the stages, the packet
tests' errors, ``--no-deps``, the restart after a crash, ``--fail-fast``,
``--sanitize``'s crashes, the advisory bench, the result schema and the
output. ``test_sdk.py`` runs the real harness against a real mmt-dpi."""

from __future__ import annotations

import importlib.util
import json
from collections.abc import Callable, Sequence
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from mmt_plugin import schemas
from mmt_plugin.cli import main
from mmt_plugin.codegen import scaffold
from mmt_plugin.commands import test as test_module
from mmt_plugin.commands.generate import make_generation
from mmt_plugin.commands.test import TestCommand, packet_paths
from mmt_plugin.diagnostics import CliError
from mmt_plugin.sdk.resolve import resolve_profile
from mmt_plugin.testing import harness
from mmt_plugin.testing.fuzz import fuzz_packets
from mmt_plugin.ui.streams import ColorTier, StreamStyle

MODEL = """Protocol {
    Properties { label = "fakeproto" id = "991" encoding = "network" }
    Attributes {
        attribute { alias="kind" data_type="MMT_U8_DATA" data_len="1" offset="0" scope="packet" }
        attribute { alias="size" data_type="MMT_U16_DATA" data_len="2" offset="1" scope="packet" }
    }
}
"""


def _packet(name: str, data: str, kind: int, size: int) -> str:
    return f"""schema: 1
id: "fakeproto/{name}"
bytes:
  - "{data}"
expect:
  protocol: "FAKEPROTO"
  proto_id: 991
  next:
    kind: "none"
  attributes:
    - name: "kind"
      type: "MMT_U8_DATA"
      offset: 0
      length: 1
      value: {kind}
    - name: "size"
      type: "MMT_U16_DATA"
      offset: 1
      length: 2
      value: {size}
"""


#: Three packet tests, in file name order: a, b, c.
PACKETS = {
    "a": ("01 00 02", 1, 2),
    "b": ("02 00 03", 2, 3),
    "c": ("03 00 04", 3, 4),
}

Run = Callable[..., tuple[int, dict[str, Any]]]


def _fakes() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "packettest_build_fakes", Path(__file__).parents[1] / "build" / "fakes.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


FAKES = _fakes()


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The current directory: ``model.pdl``, its scaffold, three packet tests."""
    work = tmp_path / "project"
    (work / "src").mkdir(parents=True)
    (work / "tests").mkdir()
    (work / "model.pdl").write_text(MODEL)
    choice = resolve_profile("1.10.2", {}, None, None)
    generation, _, _ = make_generation("model.pdl", MODEL.encode(), choice)
    assert generation is not None
    impl = scaffold(generation, choice.profile)
    (work / impl.path).write_text(impl.text)
    for name, (data, kind, size) in PACKETS.items():
        (work / "tests" / f"{name}.yaml").write_text(_packet(name, data, kind, size))
    monkeypatch.chdir(work)
    for name in ("MMT_PLUGIN_SDK_PROFILE", "MMT_BASE", "CC", "FAKE_CC_LINK_FAIL", "FAKE_CC_SLEEP"):
        monkeypatch.delenv(name, raising=False)
    return work


@pytest.fixture
def sdk(tmp_path: Path) -> Path:
    root: Path = FAKES.fake_sdk(tmp_path / "sdk")
    (root / "plugins").mkdir()
    (root / "plugins" / harness.TCPIP).write_text("fake\n")
    return root


@pytest.fixture
def cc(tmp_path: Path) -> Path:
    path: Path = FAKES.fake_cc(tmp_path / "bin")
    return path


@pytest.fixture
def run(tmp_path: Path, sdk: Path, cc: Path, capsys: pytest.CaptureFixture[str]) -> Run:
    """``mmt-plugin --json test --model model.pdl --sdk SDK --cc CC ARGS``:
    the exit code and the envelope, checked against both schemas."""
    envelope = Draft202012Validator(schemas.load_cli_schema(schemas.ENVELOPE))
    result = Draft202012Validator(schemas.result_schema("test"))
    command = TestCommand(pkg_config_dirs=[], default_prefix=str(tmp_path / "no-sdk"))

    def go(*args: str) -> tuple[int, dict[str, Any]]:
        argv = ["--json", "test", "--model", "model.pdl", "--sdk", str(sdk), "--cc", str(cc)]
        code = main([*argv, *args], commands=[command])
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


#: What the fake harness prints per packet of a check run, by its first byte:
#: ``None`` for a crash, else (kind, size).
Script = dict[int, tuple[int, int] | None]


class FakeHarness:
    """Replaces ``harness.run``: answers check, fuzz and bench runs from the
    packet file, and records each run's mode and packet count."""

    def __init__(self) -> None:
        self.check: Script = {}
        self.fuzz_crash: set[bytes] = set()
        self.bench: list[str] | None = None
        self.error: str | None = None
        self.exit_early: set[int] = set()
        self.setup_crash = False
        self.runs: list[tuple[str, int, str]] = []

    def __call__(
        self,
        program: Path,
        args: Sequence[str],
        plugin: Path,
        sdk_plugins: Path,
        *,
        timeout: float,
        on_line: Callable[[str], None] | None = None,
        log: Callable[[str], None] | None = None,
        env: Any = None,
    ) -> harness.HarnessRun:
        assert program.is_file() and timeout > 0
        packets = _read(Path(args[1]))
        self.runs.append((args[0], len(packets), plugin.parent.name))
        lines: list[str] = []
        if self.error is not None:
            return harness.HarnessRun(3, [f"error {self.error}"])
        lines.append("protocol 991 FAKEPROTO")
        if self.setup_crash:
            return harness.HarnessRun(-6, lines)
        if args[0] == "bench":
            if self.bench is None:
                return harness.HarnessRun(-11, lines)
            return harness.HarnessRun(0, [*lines, *self.bench])
        for n, packet in enumerate(packets):
            if args[0] == "fuzz":
                lines.append(f"at {n}")
                if packet in self.fuzz_crash:
                    return harness.HarnessRun(
                        99, lines, "==1==ERROR: AddressSanitizer: heap-buffer-overflow on x"
                    )
                continue
            lines.append(f"packet {n}")
            values = self.check.get(packet[0], (packet[0], int.from_bytes(packet[1:3], "big")))
            if values is None:
                return harness.HarnessRun(-11, lines)
            if packet[0] in self.exit_early:
                return harness.HarnessRun(0, lines)  # user code called exit(0)
            lines += [
                "proto 2",
                "next none",
                f"attr 0 MMT_U8_DATA int {values[0]}",
                f"attr 1 MMT_U16_DATA int {values[1]}",
                "done",
            ]
        return harness.HarnessRun(0, [*lines, f"end {len(packets)}"])


def _read(path: Path) -> list[bytes]:
    data = path.read_bytes()
    out = []
    while data:
        n = int.from_bytes(data[:4], "little")
        out.append(data[4 : 4 + n])
        data = data[4 + n :]
    return out


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch) -> FakeHarness:
    found = FakeHarness()
    monkeypatch.setattr(harness, "run", found)
    return found


# --- stages ------------------------------------------------------------------------


def test_the_packets_pass(project: Path, run: Run, fake: FakeHarness) -> None:
    code, doc = run()
    assert code == 0, doc["error"]
    result = doc["result"]
    assert _stages(doc) == {
        "build": "ran",
        "harness": "ran",
        "packets": "ran",
        "sanitize": "skipped",
        "bench": "skipped",
    }
    assert result["summary"] == {"total": 3, "passed": 3, "failed": 0, "skipped": 0}
    assert [(p["id"], p["file"], p["status"], p["attributes"]) for p in result["packets"]] == [
        (f"fakeproto/{n}", f"tests/{n}.yaml", "pass", 2) for n in "abc"
    ]
    assert result["sanitize"] is None and result["bench"] is None
    assert (project / "build" / "test" / "harness.c").is_file()
    assert fake.runs == [("check", 3, "build")]
    # A second run: the plugin and the harness are up to date.
    code, doc = run()
    assert code == 0
    assert _stages(doc)["build"] == "up-to-date" and _stages(doc)["harness"] == "up-to-date"


def test_a_failing_packet_reports_the_attribute_and_both_values(
    project: Path, run: Run, fake: FakeHarness
) -> None:
    fake.check[2] = (2, 1792)
    code, doc = run()
    assert code == 6
    assert doc["error"]["code"] == "test.packet-failed"
    assert doc["error"]["message"] == "1 of 3 packets failed"
    b = doc["result"]["packets"][1]
    assert b["status"] == "fail"
    assert b["failures"] == [{"attribute": "size", "expected": "3", "actual": "1792"}]
    assert _stages(doc)["packets"] == "failed"
    failed = [d for d in doc["diagnostics"] if d["code"] == "test.packet-failed"]
    assert [d["location"]["file"] for d in failed] == ["tests/b.yaml"]
    assert failed[0]["message"] == "fakeproto/b: size: expected 3, got 1792"


def test_the_harness_restarts_after_a_crash_so_every_packet_runs(
    project: Path, run: Run, fake: FakeHarness
) -> None:
    fake.check[1] = None  # the first packet crashes the harness
    code, doc = run()
    assert code == 6 and doc["error"]["code"] == "test.crash"
    statuses = [p["status"] for p in doc["result"]["packets"]]
    assert statuses == ["crash", "pass", "pass"]
    assert doc["result"]["packets"][0]["failures"] == [
        {"attribute": "<harness>", "expected": "no crash", "actual": "killed by SIGSEGV"}
    ]
    assert [r[:2] for r in fake.runs] == [("check", 3), ("check", 2)]
    assert doc["result"]["summary"]["failed"] == 1


def test_two_crashes_in_the_middle_each_restart_the_harness(
    project: Path, run: Run, fake: FakeHarness
) -> None:
    (project / "tests" / "d.yaml").write_text(_packet("d", "04 00 05", 4, 5))
    fake.check[2] = None
    fake.check[4] = None
    code, doc = run()
    assert code == 6 and doc["error"]["code"] == "test.crash"
    assert [p["status"] for p in doc["result"]["packets"]] == ["pass", "crash", "pass", "crash"]
    assert [r[:2] for r in fake.runs] == [("check", 4), ("check", 2)]


def test_a_harness_that_exits_before_the_end_is_a_crash(
    project: Path, run: Run, fake: FakeHarness
) -> None:
    fake.exit_early = {2}
    code, doc = run()
    assert code == 6 and doc["error"]["code"] == "test.crash"
    statuses = [p["status"] for p in doc["result"]["packets"]]
    assert statuses == ["pass", "crash", "pass"]
    reason = doc["result"]["packets"][1]["failures"][0]["actual"]
    assert reason == "the harness exited before the end (exit status 0)"
    fake.exit_early = set()
    fake.fuzz_crash = set()
    code, doc = run("--sanitize", "--fuzz-count", "3")
    assert code == 0, doc["error"]


def test_a_crash_before_the_first_packet_is_a_load_failure(
    project: Path, run: Run, fake: FakeHarness
) -> None:
    fake.setup_crash = True
    code, doc = run()
    assert code == 6 and doc["error"]["code"] == "test.load-failed"
    assert [p["status"] for p in doc["result"]["packets"]] == ["skipped"] * 3
    assert len(fake.runs) == 1


def test_fail_fast_on_a_value_mismatch(project: Path, run: Run, fake: FakeHarness) -> None:
    fake.check[2] = (2, 9)
    code, doc = run("--fail-fast")
    assert code == 6 and doc["error"]["code"] == "test.packet-failed"
    assert [p["status"] for p in doc["result"]["packets"]] == ["pass", "fail", "skipped"]


def test_two_packet_tests_with_one_id_are_a_bad_packet_test(
    project: Path, run: Run, fake: FakeHarness
) -> None:
    (project / "tests" / "d.yaml").write_text(_packet("a", "04 00 05", 4, 5))
    code, doc = run()
    assert code == 3 and doc["error"]["code"] == "model.bad-packet-test"
    assert [d["location"]["file"] for d in doc["diagnostics"]] == ["tests/d.yaml"]


def test_fail_fast_stops_at_the_first_failing_packet(
    project: Path, run: Run, fake: FakeHarness
) -> None:
    fake.check[1] = None
    code, doc = run("--fail-fast")
    assert code == 6
    assert [p["status"] for p in doc["result"]["packets"]] == ["crash", "skipped", "skipped"]
    assert doc["result"]["summary"] == {"total": 3, "passed": 0, "failed": 1, "skipped": 2}
    assert len(fake.runs) == 1


def test_a_plugin_that_does_not_load_is_exit_6(project: Path, run: Run, fake: FakeHarness) -> None:
    fake.error = "init_extraction() failed: a plugin did not load"
    code, doc = run()
    assert code == 6 and doc["error"]["code"] == "test.load-failed"
    assert "init_extraction() failed" in doc["error"]["message"]


def test_no_packet_test_is_a_warning_and_strict_fails_on_it(
    project: Path, run: Run, fake: FakeHarness
) -> None:
    for p in (project / "tests").iterdir():
        p.unlink()
    code, doc = run()
    assert code == 0, doc["error"]
    assert _codes(doc) == ["test.no-packets"]
    assert _stages(doc)["build"] == "ran" and _stages(doc)["harness"] == "skipped"
    assert doc["result"]["summary"]["total"] == 0 and fake.runs == []
    code, doc = run("--strict")
    assert code == 6 and doc["error"]["code"] == "test.no-packets"


def test_a_bad_packet_test_is_exit_3_before_anything_is_built(
    project: Path, run: Run, fake: FakeHarness
) -> None:
    (project / "tests" / "b.yaml").write_text("schema: 1\nid: x\n")
    (project / "tests" / "c.yaml").write_text("schema: 2\n")
    code, doc = run()
    assert code == 3 and doc["error"]["code"] == "model.bad-packet-test"
    assert doc["error"]["message"] == "2 packet tests cannot be read"
    files = [d["location"]["file"] for d in doc["diagnostics"]]
    assert files == ["tests/b.yaml", "tests/c.yaml"]
    assert set(_stages(doc).values()) == {"skipped"}
    assert not (project / "build").exists()


def test_no_deps_is_exit_7_while_the_plugin_is_stale(
    project: Path, run: Run, fake: FakeHarness
) -> None:
    code, doc = run("--no-deps")
    assert code == 7 and doc["error"]["code"] == "state.stale"
    assert _stages(doc)["build"] == "stale"
    assert not (project / "build" / "mmtp_fakeproto.so").exists()
    assert fake.runs == []
    assert run()[0] == 0
    code, doc = run("--no-deps")
    assert code == 0 and _stages(doc)["build"] == "up-to-date"


def test_a_compile_error_is_exit_5(project: Path, run: Run, fake: FakeHarness) -> None:
    impl = project / "src" / "fakeproto_impl.c"
    impl.write_text("#error broken\n" + impl.read_text())
    code, doc = run()
    assert code == 5 and doc["error"]["code"] == "build.compile-failed"
    assert _stages(doc)["build"] == "failed" and _stages(doc)["packets"] == "skipped"
    assert [p["status"] for p in doc["result"]["packets"]] == ["skipped"] * 3


def test_an_sdk_without_libmmt_tcpip_is_exit_4(
    project: Path, run: Run, sdk: Path, fake: FakeHarness
) -> None:
    (sdk / "plugins" / harness.TCPIP).unlink()
    code, doc = run()
    assert code == 4 and doc["error"]["code"] == "sdk.invalid-prefix"


@pytest.mark.parametrize(
    "args",
    [
        ("--seed", "-1"),
        ("--seed", "x"),
        ("--fuzz-count", "0"),
        ("no-such-*.yaml",),
        ("--model", "-"),
    ],
)
def test_bad_arguments_are_usage_errors(
    project: Path, run: Run, fake: FakeHarness, args: tuple[str, ...]
) -> None:
    code, doc = run(*args)
    assert code == 2, doc["error"]


def test_packets_are_files_directories_or_globs(project: Path, tmp_path: Path) -> None:
    tests = project / "tests"
    assert packet_paths([], project) == [tests / f"{n}.yaml" for n in "abc"]
    assert packet_paths(["tests/b.yaml", "tests/*.yaml"], project) == [
        tests / f"{n}.yaml" for n in "bac"
    ]
    assert packet_paths([str(tests)], project) == [tests / f"{n}.yaml" for n in "abc"]
    assert packet_paths([], tmp_path / "empty") == []
    with pytest.raises(CliError) as exc:
        packet_paths(["tests/*.yml"], project)
    assert exc.value.code == "usage.invalid-value"


# --- --sanitize and --bench ------------------------------------------------------------


def test_sanitize_builds_a_sanitized_plugin_and_reports_crashes_by_seed(
    project: Path, run: Run, fake: FakeHarness
) -> None:
    code, doc = run("--sanitize", "--fuzz-count", "20", "--seed", "5")
    assert code == 0, doc["error"]
    assert doc["result"]["sanitize"] == {"seed": 5, "count": 63, "crashes": []}
    assert _stages(doc)["sanitize"] == "ran"
    assert (project / "build" / "sanitize" / "mmtp_fakeproto.so").is_file()
    assert ("fuzz", 63, "sanitize") in fake.runs
    flags = json.loads((project / "build" / "test" / ".harness-sanitize.json").read_text())
    assert flags["inputs"]
    # Two of b's random packets crash the sanitized plugin: both are reported,
    # with their index for that seed, and the same seed finds the same ones.
    crashing = fuzz_packets(5, "fakeproto/b", bytes.fromhex("020003"), 20)
    fake.fuzz_crash = {crashing[5], crashing[11]}
    code, doc = run("--sanitize", "--fuzz-count", "20", "--seed", "5")
    assert code == 6 and doc["error"]["code"] == "test.crash"
    crashes = doc["result"]["sanitize"]["crashes"]
    assert [(c["test"], c["index"]) for c in crashes] == [("fakeproto/b", 6), ("fakeproto/b", 12)]
    assert crashes[0]["reason"] == "AddressSanitizer: heap-buffer-overflow"
    assert crashes[0]["bytes"] == crashing[5].hex(" ")
    assert doc["result"]["sanitize"]["count"] == 63
    assert _stages(doc)["sanitize"] == "failed"
    assert (
        run("--sanitize", "--fuzz-count", "20", "--seed", "5")[1]["result"]["sanitize"]
        == (doc["result"]["sanitize"])
    )


def test_bench_reports_packets_per_second_against_the_empty_plugin(
    project: Path, run: Run, fake: FakeHarness
) -> None:
    samples = [f"sample 1000 {ns}" for ns in (1000000, 2000000, 1000000, 4000000)]
    fake.bench = samples * 2 + samples[:2]
    code, doc = run("--bench")
    assert code == 0, doc["error"]
    bench = doc["result"]["bench"]
    assert bench["pps"] == 750000 and bench["baseline_pps"] == 750000
    assert bench["ratio"] == 1.0
    assert bench["samples"][:4] == [1000000, 500000, 1000000, 250000]
    assert (project / "build" / "test" / "baseline" / "mmtp_fakeproto.so").is_file()
    assert [r[0] for r in fake.runs] == ["check", "bench", "bench"]
    assert fake.runs[2][2] == "baseline"


def test_a_bench_that_fails_never_changes_the_exit_code(
    project: Path, run: Run, fake: FakeHarness
) -> None:
    code, doc = run("--bench", "--strict")
    assert code == 0, doc["error"]
    assert doc["result"]["bench"] is None
    assert _stages(doc)["bench"] == "failed"
    assert "test.bench-failed" in _codes(doc)
    fake.bench = ["sample 1000 x"] * 10  # unparsable output
    code, doc = run("--bench")
    assert code == 0, doc["error"]
    assert _stages(doc)["bench"] == "failed"


# --- output ----------------------------------------------------------------------------


def _style(tier: ColorTier = ColorTier.NONE) -> StreamStyle:
    return StreamStyle(styled=True, color=tier, unicode=True, width=80)


def test_the_view_shows_the_packets_the_meter_and_the_bench(
    project: Path, run: Run, fake: FakeHarness
) -> None:
    fake.bench = [f"sample 1000 {1000000 + n}" for n in range(10)]
    code, doc = run("--bench")
    assert code == 0, doc["error"]
    details = ["2 attributes", "2 attributes", "size: expected 4, got 7"]
    doc["result"]["packets"][2]["status"] = "fail"
    doc["result"]["summary"].update(passed=2, failed=1)
    view = test_module._view("fakeproto", doc["result"], details, _style())
    lines = view.splitlines()
    assert lines[0].startswith("╭─┐test fakeproto┌")
    row = next(x for x in lines if "fakeproto/c" in x)
    assert "✗ fail" in row and "size: expected 4, got 7" in row
    assert any("passed" in x and "67%" in x and "2 of 3 packets" in x for x in lines)
    assert any("bench" in x and "pps vs" in x for x in lines)
    assert any("samples" in x and "min " in x and "last " in x for x in lines)
    assert lines[-1].startswith("╰─┘3 packets · 1 failed · built")
    assert "\x1b" not in view


def test_plain_records_are_packet_status_detail(
    project: Path, sdk: Path, cc: Path, fake: FakeHarness, capsys: pytest.CaptureFixture[str]
) -> None:
    fake.check[2] = (2, 9)
    command = TestCommand(pkg_config_dirs=[], default_prefix="/nonexistent")
    argv = ["test", "--model", "model.pdl", "--sdk", str(sdk), "--cc", str(cc)]
    assert main(argv, commands=[command]) == 6
    out = capsys.readouterr().out
    assert out.splitlines() == [
        "fakeproto/a\tpass\t2 attributes",
        "fakeproto/b\tfail\tsize: expected 3, got 9",
        "fakeproto/c\tpass\t2 attributes",
    ]
