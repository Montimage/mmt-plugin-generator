"""The parts of ``mmt-plugin test`` that need no SDK (``mmt_plugin.testing``):
the YAML subset loader (the same data as ``tests/corpus/validate.py``'s on
every corpus file), packet tests and their checks, the seeded random
packets, and reading the harness's output."""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from mmt_plugin.codegen import Generation
from mmt_plugin.commands.generate import make_generation
from mmt_plugin.sdk.profile import DATA_TYPE_GROUP
from mmt_plugin.sdk.resolve import resolve_profile
from mmt_plugin.testing import harness
from mmt_plugin.testing.fuzz import fuzz_packets
from mmt_plugin.testing.packets import (
    NEXT,
    PROTOCOL,
    Failure,
    Observation,
    ObservedValue,
    PacketTest,
    PacketTestError,
    check,
    harness_lengths,
    load,
)
from mmt_plugin.testing.yamlsubset import LoadError, loads

CORPUS = Path(__file__).resolve().parents[2] / "corpus"
PROFILE = resolve_profile("1.10.2", {}, None, None).profile
TYPES = {c.name for c in PROFILE.constants if c.group == DATA_TYPE_GROUP}
SIZES = {c.name: c.size or 0 for c in PROFILE.constants if c.group == DATA_TYPE_GROUP}


def _validator() -> ModuleType:
    spec = importlib.util.spec_from_file_location("corpus_validate", CORPUS / "validate.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _fixtures() -> list[Path]:
    return sorted(CORPUS.glob("models/*/packets/*.yaml"))


# --- the YAML subset -----------------------------------------------------------


@pytest.mark.parametrize("path", [CORPUS / "index.yaml", *_fixtures()], ids=lambda p: p.name)
def test_the_loader_reads_every_corpus_file_as_the_validator_does(path: Path) -> None:
    assert loads(path.read_bytes()) == _validator().load_yaml(path)


@pytest.mark.parametrize(
    ("text", "message", "line"),
    [
        (b"a: 1\r\n", "CRLF line endings (use LF)", None),
        (b"a:\t1\n", "tab character", 1),
        (b"a: 1\nb: yes\n", "unsupported scalar 'yes' (quote it)", 2),
        (b"a: 1\na: 2\n", "duplicate key 'a'", 2),
        (b"a:\n", "key 'a' has no value", 1),
        (b"a: &x 1\n", "unsupported scalar '&x 1' (quote it)", 1),
        (b"# only a comment\n", "empty file", None),
        (b"a: [1, [2]]\n", "nested flow collections are not allowed", 1),
        (b'a: "x\n', "unterminated string", 1),
        (b"a: 1\n  b: 2\n", "unexpected indentation", 2),
        (b"\xff\n", "not UTF-8 text (byte 0)", None),
    ],
)
def test_the_loader_rejects_what_the_subset_has_not(
    text: bytes, message: str, line: int | None
) -> None:
    with pytest.raises(LoadError) as exc:
        loads(text)
    assert (exc.value.message, exc.value.line) == (message, line)


def test_the_loader_reads_the_subset() -> None:
    text = b'# c\na: 1\nb: "x\\ny" # c\nc: [a, "b", 3]\nd:\n  - e: true\n    f: null\n  - 7\n'
    assert loads(text) == {
        "a": 1,
        "b": "x\ny",
        "c": ["a", "b", 3],
        "d": [{"e": True, "f": None}, 7],
    }


# --- packet tests ------------------------------------------------------------------


@pytest.mark.parametrize("path", _fixtures(), ids=lambda p: f"{p.parent.parent.name}/{p.stem}")
def test_every_corpus_fixture_is_a_packet_test(path: Path) -> None:
    test = load(path, path.name, TYPES)
    doc = _validator().load_yaml(path)
    assert test.id == doc["id"]
    assert test.data == bytes.fromhex("".join(doc["bytes"]))
    assert test.proto_id == doc["expect"]["proto_id"]
    assert [a.name for a in test.attributes] == [a["name"] for a in doc["expect"]["attributes"]]


PACKET = """schema: 1
id: "t/one"
bytes:
  - "01 02 03 04 c6 33 64 07"
expect:
  protocol: "T"
  proto_id: 990
  next:
    kind: "proto"
    proto_id: 956
    offset: 4
  attributes:
    - name: "a"
      type: "MMT_U16_DATA"
      offset: 0
      length: 2
      value: 258
    - name: "ip"
      type: "MMT_DATA_IP_ADDR"
      offset: 4
      length: 4
      value: "198.51.100.7"
    - name: "gone"
      type: "MMT_U8_DATA"
      status: "absent"
    - name: "hook"
      type: "MMT_U8_DATA"
      status: "undefined"
      reason: "user code"
"""


def _test(tmp_path: Path, text: str = PACKET) -> PacketTest:
    path = tmp_path / "t.yaml"
    path.write_text(text)
    return load(path, "tests/t.yaml", TYPES)


def _seen(
    index: int | None = 2, next_id: int | None = 956, offset: int | None = 4, **values: Any
) -> Observation:
    base = {
        "a": ObservedValue("int", "MMT_U16_DATA", number=258),
        "ip": ObservedValue("hex", "MMT_DATA_IP_ADDR", data=bytes([198, 51, 100, 7])),
        "gone": ObservedValue("absent", "MMT_U8_DATA"),
        "hook": ObservedValue("int", "MMT_U8_DATA", number=9),
    }
    base.update(values)
    return Observation(index, next_id, offset, base)


def test_a_matching_observation_passes(tmp_path: Path) -> None:
    failures, checked = check(_test(tmp_path), _seen(), (990, "T"))
    assert failures == []
    assert checked == 3  # the undefined attribute is not checked


@pytest.mark.parametrize(
    ("observed", "failure"),
    [
        (_seen(a=ObservedValue("int", "MMT_U16_DATA", number=1792)), Failure("a", "258", "1792")),
        (_seen(a=ObservedValue("absent", "MMT_U16_DATA")), Failure("a", "258", "absent")),
        (
            _seen(a=ObservedValue("int", "MMT_U8_DATA", number=1)),
            Failure("a", "MMT_U16_DATA", "MMT_U8_DATA"),
        ),
        (_seen(a=ObservedValue("missing")), Failure("a", "258", "not an attribute of the plugin")),
        (
            _seen(ip=ObservedValue("hex", "MMT_DATA_IP_ADDR", data=bytes([1, 2, 3, 4]))),
            Failure("ip", "198.51.100.7", "1.2.3.4"),
        ),
        (
            _seen(gone=ObservedValue("int", "MMT_U8_DATA", number=5)),
            Failure("gone", "absent", "5"),
        ),
        (_seen(next_id=None, offset=None), Failure(NEXT, "956 at offset 4", "none")),
        (_seen(offset=6), Failure(NEXT, "956 at offset 4", "956 at offset 6")),
    ],
)
def test_each_mismatch_names_the_attribute_and_both_values(
    tmp_path: Path, observed: Observation, failure: Failure
) -> None:
    failures, _ = check(_test(tmp_path), observed, (990, "T"))
    assert failures == [failure]


def test_an_unclassified_packet_or_another_protocol_fails_on_the_protocol(
    tmp_path: Path,
) -> None:
    test = _test(tmp_path)
    assert check(test, _seen(index=None), (990, "T")) == (
        [Failure(PROTOCOL, "T (990)", "not classified")],
        0,
    )
    assert check(test, _seen(), (991, "T"))[0] == [Failure(PROTOCOL, "T (990)", "T (991)")]
    # Names compare case-insensitively, as mmt-dpi does.
    assert check(test, _seen(), (990, "t"))[0] == []


def test_a_next_protocol_where_none_is_expected_fails(tmp_path: Path) -> None:
    test = _test(tmp_path, PACKET.replace('kind: "proto"', 'kind: "none"'))
    assert check(test, _seen(), (990, "T"))[0] == [Failure(NEXT, "none", "956 at offset 4")]
    hook = _test(tmp_path, PACKET.replace('kind: "proto"', 'kind: "hook"'))
    assert check(hook, _seen(), (990, "T"))[0] == []  # user code decides


@pytest.mark.parametrize(
    ("old", "new", "message", "line"),
    [
        ("schema: 1", "schema: 2", "schema must be 1", None),
        ('id: "t/one"', "id: 3", "the test: 'id' must be a string", None),
        ('"01 02', '"01 2', "bytes[0]: must be lower-case hex pairs separated by one space", None),
        ('type: "MMT_U16_DATA"', 'type: "MMT_NOPE"', "is not a data type of the SDK", None),
        ("value: 258", 'value: "258"', "a MMT_U16_DATA value is a non-negative integer", None),
        ('value: "198.51.100.7"', 'value: "300.1.1.1"', "is not a MMT_DATA_IP_ADDR value", None),
        ('kind: "proto"', 'kind: "maybe"', "kind must be none, hook or proto", None),
        ('name: "gone"', 'name: "a"', "'a' is listed twice", None),
        ('name: "gone"', 'name: "a-b"', "is not a C identifier", None),
        ("      offset: 0\n", "", "missing key 'offset'", None),
        ('status: "absent"', 'status: "maybe"', "status must be value, absent or undefined", None),
        ("schema: 1", "schema: yes", "unsupported scalar 'yes' (quote it)", 1),
    ],
)
def test_a_bad_packet_test_is_located(
    tmp_path: Path, old: str, new: str, message: str, line: int | None
) -> None:
    assert old in PACKET
    with pytest.raises(PacketTestError) as exc:
        _test(tmp_path, PACKET.replace(old, new, 1))
    d = exc.value.diagnostic
    assert d.code == "model.bad-packet-test"
    assert message in d.message
    assert d.location is not None and d.location.file == "tests/t.yaml"
    assert d.location.line == line


def test_an_unreadable_packet_test_is_a_bad_packet_test(tmp_path: Path) -> None:
    with pytest.raises(PacketTestError) as exc:
        load(tmp_path / "missing.yaml", "missing.yaml", TYPES)
    assert "cannot read missing.yaml" in exc.value.diagnostic.message


def test_the_harness_prints_each_attribute_within_its_sdk_size(tmp_path: Path) -> None:
    test = _test(tmp_path)
    assert harness_lengths([test], SIZES) == {"a": 2, "ip": 4, "gone": 1, "hook": 1}


# --- random packets ----------------------------------------------------------------


SCOPES = bytes.fromhex("0a0b123456780c9abc")


def test_truncations_come_first_then_random_packets() -> None:
    packets = fuzz_packets(0, "t", SCOPES, 30)
    assert len(packets) == 30
    assert packets[:9] == [SCOPES[:n] for n in range(9)]
    assert all(len(p) <= 64 for p in packets[9:])
    assert fuzz_packets(0, "t", SCOPES, 3) == [b"", SCOPES[:1], SCOPES[:2]]
    assert len(fuzz_packets(0, "t", b"", 5)) == 5


def test_the_same_seed_gives_the_same_packets_everywhere() -> None:
    # A digest of the packets of seed 0: the generator draws only
    # getrandbits, so every Python version and machine gives these bytes.
    packets = fuzz_packets(0, "pdl_scopes/single-packet-session", SCOPES, 200)
    data = b"".join(len(p).to_bytes(4, "little") + p for p in packets)
    assert (
        hashlib.sha256(data).hexdigest()
        == "ddf7cabf0b17ca0a23243093fc6a0eb93cddf8e46c30c354e44ca5003131a626"
    )
    assert fuzz_packets(7, "t", SCOPES, 100) == fuzz_packets(7, "t", SCOPES, 100)
    assert fuzz_packets(7, "t", SCOPES, 100) != fuzz_packets(8, "t", SCOPES, 100)
    assert fuzz_packets(7, "t", SCOPES, 100) != fuzz_packets(7, "u", SCOPES, 100)


# --- the harness -----------------------------------------------------------------------


MODEL = """Protocol {
    Properties { label = "harnessed" id = "990" encoding = "network" }
    Attributes {
        attribute { alias="kind" data_type="MMT_U8_DATA" data_len="1" offset="0" scope="packet" }
    }
}
"""


def _generation() -> Generation:
    generation, _, error = make_generation(
        "model.pdl", MODEL.encode(), resolve_profile("1.10.2", {}, None, None)
    )
    assert generation is not None, error
    return generation


def test_the_harness_source_names_the_protocol_and_the_attributes() -> None:
    text = harness.harness_source(_generation(), PROFILE, [("kind", 1), ("extra", 6)])
    assert "#define HARNESS_PROTO 990" in text
    assert '{"kind", 1, 0, 0},' in text and '{"extra", 6, 0, 0},' in text
    assert "#define HARNESS_ATTRIBUTES 2" in text
    assert "!= 0x88" in text and "!= 0xb5" in text
    assert '{MMT_U8_DATA, "MMT_U8_DATA"},' in text
    assert "register_classification_function_with_parent_protocol(PROTO_ETHERNET" in text
    for header in ("plugin_defs.h", "types_defs.h", "tcpip/mmt_tcpip.h", "mmt_core.h"):
        assert f'#include "{header}"' in text
    # The same inputs, the same bytes.
    assert text == harness.harness_source(_generation(), PROFILE, [("kind", 1), ("extra", 6)])


def test_the_baseline_plugin_registers_the_protocol_without_attributes() -> None:
    text = harness.baseline_source(_generation(), PROFILE)
    assert 'init_protocol_struct_for_registration(990, "HARNESSED")' in text
    assert "register_protocol(protocol_struct, 990)" in text
    assert "attribute" not in text.split("*/", 1)[1].replace("no attribute", "")


def test_the_packet_file_is_length_prefixed(tmp_path: Path) -> None:
    path = tmp_path / "p.bin"
    harness.write_packets(path, [b"\x01\x02", b"", b"\xff"])
    assert path.read_bytes() == b"\x02\0\0\0\x01\x02" + b"\0\0\0\0" + b"\x01\0\0\0\xff"


def test_the_check_output_reads_into_observations() -> None:
    lines = [
        "protocol 990 HARNESSED",
        "packet 0",
        "proto 2",
        "next 956 4",
        "attr 0 MMT_U8_DATA int 7",
        "attr 1 MMT_DATA_MAC_ADDR hex 00005e00530d",
        "attr 2 missing",
        "done",
        "packet 1",
        "proto none",
        "done",
        "packet 2",
        "proto 2",
    ]
    parsed = harness.parse_check(lines, ["kind", "mac", "nope"])
    assert parsed.plugin == (990, "HARNESSED")
    assert parsed.error is None
    first = parsed.observations[0]
    assert (first.index, first.next_id, first.next_offset) == (2, 956, 4)
    assert first.values == {
        "kind": ObservedValue("int", "MMT_U8_DATA", number=7),
        "mac": ObservedValue("hex", "MMT_DATA_MAC_ADDR", data=bytes.fromhex("00005e00530d")),
        "nope": ObservedValue("missing"),
    }
    assert parsed.observations[1] == Observation(None, None, None, {})
    assert parsed.unfinished == 2
    assert harness.parse_check(["error init_extraction() failed"], []).error == (
        "init_extraction() failed"
    )


@pytest.mark.parametrize(
    "bad",
    [
        "attr len=3",
        "next hop",
        "proto x",
        "packet one",
        "attr 9 MMT_U8_DATA int 1",
        "attr 0 MMT_U8_DATA int x",
        "attr 0 MMT_BINARY_DATA hex zz",
        "protocol x y",
    ],
)
def test_an_unreadable_check_line_stops_the_reading_and_is_never_a_pass(bad: str) -> None:
    lines = ["protocol 990 HARNESSED", "packet 0", "proto 2", bad, "done", "end 1"]
    parsed = harness.parse_check(lines, ["kind"])
    assert parsed.malformed == bad
    assert parsed.observations == {}
    assert parsed.unfinished == 0


def test_the_fuzz_and_bench_lines_read_only_when_well_formed() -> None:
    assert harness.at_index("at 12") == 12
    for line in ("at offset 4", "at", "at 1 2", "at -1", "at \u00b2", "attr 0 missing"):
        assert harness.at_index(line) is None
    assert harness.parse_sample("sample 100 2000") == (100, 2000)
    for line in ("sample", "sample a 1", "sample 1 2 3", "sample 1 -2", "samples 1 2"):
        assert harness.parse_sample(line) is None


@pytest.mark.parametrize(
    ("run", "reason"),
    [
        (harness.HarnessRun(0), None),
        (harness.HarnessRun(3, ["error setup"]), None),
        (harness.HarnessRun(3), "exit status 3"),
        (harness.HarnessRun(-11), "killed by SIGSEGV"),
        (harness.HarnessRun(1), "exit status 1"),
        (harness.HarnessRun(0, timed_out=True), "timed out"),
        (
            harness.HarnessRun(
                99,
                stderr="==2285==ERROR: AddressSanitizer: heap-buffer-overflow on address"
                " 0x5030 at pc 0x7\n",
            ),
            "AddressSanitizer: heap-buffer-overflow",
        ),
        (
            harness.HarnessRun(
                99, stderr="/w/src/x_impl.c:12:5: runtime error: load of address 0x1f/2\n"
            ),
            "x_impl.c:12:5: runtime error: load of address 0x.../2",
        ),
        (harness.HarnessRun(99), "a sanitizer stopped the harness"),
    ],
)
def test_a_crash_has_a_reason_that_does_not_change_between_runs(
    run: harness.HarnessRun, reason: str | None
) -> None:
    assert harness.crash_reason(run) == reason


def test_a_harness_run_is_killed_on_its_timeout(tmp_path: Path) -> None:
    program = tmp_path / "slow"
    program.write_text("#!/bin/sh\necho started\nexec sleep 30\n")
    program.chmod(0o755)
    plugins = tmp_path / "sdk-plugins"
    plugins.mkdir()
    (plugins / harness.TCPIP).write_text("")
    plugin = tmp_path / "mmtp_x.so"
    plugin.write_text("")
    seen: list[str] = []
    run = harness.run(program, [], plugin, plugins, timeout=0.5, on_line=seen.append)
    assert run.timed_out and seen == ["started"]
    assert harness.crash_reason(run) == "timed out"


def test_a_harness_run_sees_only_its_own_plugin_directory(tmp_path: Path) -> None:
    program = tmp_path / "env"
    program.write_text(
        '#!/bin/sh\necho "$MMT_DPI_PLUGINS_DIR"\nls "$MMT_DPI_PLUGINS_DIR"\npwd\nls\n'
    )
    program.chmod(0o755)
    plugins = tmp_path / "sdk-plugins"
    plugins.mkdir()
    (plugins / harness.TCPIP).write_text("")
    plugin = tmp_path / "mmtp_x.so"
    plugin.write_text("")
    run = harness.run(program, [], plugin, plugins, timeout=10, env={"PATH": "/usr/bin:/bin"})
    directory, first, second, cwd = run.lines
    assert (first, second) == (harness.TCPIP, "mmtp_x.so")
    assert Path(directory).parent == Path(cwd).parent  # an empty run directory beside it
    assert run.returncode == 0


def test_a_run_that_does_not_print_its_end_line_crashed() -> None:
    assert harness.crash_reason(harness.HarnessRun(0, ["packet 0", "end 1"]), 1) is None
    assert harness.crash_reason(harness.HarnessRun(0, ["packet 0"]), 1) == (
        "the harness exited before the end (exit status 0)"
    )
    assert harness.crash_reason(harness.HarnessRun(0, ["end 1"]), 2) is not None


def test_a_harness_run_drops_the_loader_variables(tmp_path: Path) -> None:
    # LD_LIBRARY_PATH comes before the harness's run path: another
    # libmmt_core (the host's) would load instead of the SDK's.
    program = tmp_path / "env"
    program.write_text('#!/bin/sh\necho "[$LD_LIBRARY_PATH][$LD_PRELOAD][$KEEP]"\n')
    program.chmod(0o755)
    plugins = tmp_path / "sdk-plugins"
    plugins.mkdir()
    (plugins / harness.TCPIP).write_text("")
    plugin = tmp_path / "mmtp_x.so"
    plugin.write_text("")
    env = {"PATH": "/usr/bin:/bin", "LD_LIBRARY_PATH": "/decoy", "LD_PRELOAD": "x.so", "KEEP": "1"}
    run = harness.run(program, [], plugin, plugins, timeout=10, env=env)
    assert run.lines == ["[][][1]"]
