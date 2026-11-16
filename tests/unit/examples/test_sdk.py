"""The examples (plan T5.1, #28: "CI builds and tests every ported
example"; the WebSocket example, #40; the OCPP 1.6-J example, #41) against
a real mmt-dpi SDK.

Each ``examples/<name>/`` project is copied, without its ``build/``, to a
temporary directory, then: ``validate --sdk`` passes, with its parents
found in the SDK (``parents-exist``) or none declared; ``build`` compiles
it with the hardened ``-Wall -Wextra -Werror`` flags without regenerating
(the committed ``generated/`` is up to date); and ``test --sanitize`` passes
every packet test, also under ASan and UBSan with truncated and random
packets, and the run of each example's ``through`` test through its real
parent. With that parent's classification removed (the generated
``classify`` taken out of ``plugin.yaml``) or wrong (the hook's function
attached to another protocol, or a wrong ``classify`` offset), only that
run fails. The WebSocket and OCPP examples' session tests (#99) run their
TCP sessions packet by packet, since their state spans segments, and an
OCPP session runs next to the WebSocket example's plugin through the
harness that ``test`` built. The SDK is an extracted mmt-dpi package, a
private prefix (never ``/opt/mmt``), as for
``tests/unit/packettest/test_sdk.py``::

    MMT_GOLDEN_SDK=<dir>/opt/mmt MMT_GOLDEN_CC=gcc uv run pytest tests/unit/examples/test_sdk.py

Without ``MMT_GOLDEN_SDK`` the tests skip, unless
``MMT_REQUIRE_GOLDEN_COMPILE=1`` (CI's "Generated code" job) makes them fail.
"""

from __future__ import annotations

import json
import math
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import pytest

from mmt_plugin.cli import main
from mmt_plugin.sdk.profile import DATA_TYPE_GROUP
from mmt_plugin.sdk.resolve import resolve_profile
from mmt_plugin.testing import harness
from mmt_plugin.testing.packets import PacketTest, harness_lengths
from mmt_plugin.testing.session import Connection, SessionTest, build_frames, load_test

SDK_ENV = "MMT_GOLDEN_SDK"
CC_ENV = "MMT_GOLDEN_CC"
REQUIRE_ENV = "MMT_REQUIRE_GOLDEN_COMPILE"
REPO = Path(__file__).resolve().parents[3]
EXAMPLES = REPO / "examples"
NAMES = sorted(p.parent.name for p in EXAMPLES.glob("*/plugin.yaml"))

#: The examples that declare no parent (examples/README.md, "The ports").
NO_PARENT = {"cotp", "ethernet", "s7com", "topo_ind_sch"}
PARENTED = sorted(set(NAMES) - NO_PARENT)
#: The examples whose parent hook (src/<label>_impl.c) attaches the protocol,
#: and another parent for it: the frame's never reaches the function there.
HOOKED = {
    "mongodb": ("PROTO_TCP", "PROTO_UDP"),
    "tcp": ("PROTO_IP", "PROTO_IPV6"),
    "ocpp": ("PROTO_TCP", "PROTO_UDP"),
    "tpkt": ("PROTO_TCP", "PROTO_UDP"),
    "websocket": ("PROTO_TCP", "PROTO_UDP"),
}
_TYPES = {
    c.name
    for c in resolve_profile("1.10.2", {}, None, None).profile.constants
    if c.group == DATA_TYPE_GROUP
}


def _skip_or_fail(why: str) -> None:
    if os.environ.get(REQUIRE_ENV) == "1":
        pytest.fail(f"{REQUIRE_ENV}=1 but {why}")
    pytest.skip(why)


def _sdk() -> Path:
    prefix = os.environ.get(SDK_ENV, "")
    if not prefix:
        _skip_or_fail(f"{SDK_ENV} is not set (an extracted mmt-dpi prefix)")
    return Path(prefix)


def _cc() -> str:
    cc = os.environ.get(CC_ENV, "gcc")
    if shutil.which(cc) is None:
        _skip_or_fail(f"{cc} is not installed")
    return cc


def _json(capsys: pytest.CaptureFixture[str], *argv: str) -> tuple[int, dict[str, Any]]:
    code = main(["--json", *argv])
    doc: dict[str, Any] = json.loads(capsys.readouterr().out)
    return code, doc


def _stages(doc: dict[str, Any]) -> dict[str, str]:
    return {s["name"]: s["status"] for s in doc["result"]["stages"]}


@pytest.fixture
def project(
    request: pytest.FixtureRequest, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Path:
    """A copy of the example, the current directory; no host plugin
    directory and no profile from the environment."""
    sdk, _ = _sdk(), _cc()
    name: str = request.param
    copy = tmp_path / name
    shutil.copytree(EXAMPLES / name, copy, ignore=shutil.ignore_patterns("build"))
    monkeypatch.chdir(copy)
    monkeypatch.delenv("MMT_PLUGIN_SDK_PROFILE", raising=False)
    # validate reads the SDK's own plugins; the harness sets its own directory.
    monkeypatch.setenv("MMT_DPI_PLUGINS_DIR", str(sdk / "plugins"))
    return copy


def _runs(project: Path) -> tuple[int, int]:
    """The runs of a project's tests: each one, and each ``through``; and the
    packets ``--sanitize --fuzz-count 100`` runs."""
    tests = [load_test(p, p.name, _TYPES) for p in (project / "tests").glob("*.yaml")]
    packets = [t for t in tests if isinstance(t, PacketTest)]
    runs = len(tests) + sum(1 for t in packets if t.through is not None)
    fuzzed = 101 * (runs - (len(tests) - len(packets)))
    for test in tests:
        if isinstance(test, SessionTest):
            n = len(build_frames(test))
            fuzzed += n * (1 + math.ceil(100 / n))
    return runs, fuzzed


def test_every_example_is_tested() -> None:
    assert len(NAMES) == 18
    assert set(NAMES) >= NO_PARENT
    assert set(HOOKED) < set(PARENTED)


@pytest.mark.parametrize("project", NAMES, indirect=True)
def test_the_example_validates_builds_and_passes_its_packet_tests(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    sdk, cc = str(_sdk()), _cc()

    code, doc = _json(capsys, "validate", "--sdk", sdk)
    assert code == 0, doc["error"]
    checks = {c["id"]: c["status"] for c in doc["result"]["checks"]}
    assert checks["id-free"] == checks["name-free"] == checks["load-order"] == "pass", checks
    assert checks["parents-exist"] == ("skip" if project.name in NO_PARENT else "pass"), checks

    code, doc = _json(capsys, "build", "--sdk", sdk, "--cc", cc)
    assert code == 0, (doc["error"], doc["diagnostics"])
    # The committed generated/ is this SDK's generation: build compiles it as it is.
    assert _stages(doc) == {
        "generate": "up-to-date",
        "compile": "ran",
        "hooks": "ran",
        "link": "ran",
    }

    code, doc = _json(
        capsys, "test", "--sdk", sdk, "--cc", cc, "--sanitize", "--fuzz-count", "100"
    )
    assert code == 0, (doc["error"], doc["result"] and doc["result"]["packets"])
    result = doc["result"]
    runs, fuzzed = _runs(project)
    assert result["summary"] == {"total": runs, "passed": runs, "failed": 0, "skipped": 0}
    packets = [p for p in result["packets"] if "session" not in p]
    assert all(p["attributes"] > 0 for p in packets), result["packets"]
    through = [p for p in result["packets"] if "through" in p]
    assert len(through) == (0 if project.name in NO_PARENT else 1), result["packets"]
    assert result["sanitize"] == {"seed": 0, "count": fuzzed, "crashes": []}
    assert _stages(doc) == {
        "build": "up-to-date",
        "harness": "ran",
        "packets": "ran",
        "sanitize": "ran",
        "bench": "skipped",
    }


def _break_parent(project: Path, how: str) -> None:
    """Remove the example's parent classification, or make it wrong."""
    if how == "hook":
        impl = next((project / "src").glob("*_impl.c"))
        old, new = HOOKED[project.name]
        call = f"register_classification_function_with_parent_protocol({old},"
        text = impl.read_text()
        assert text.count(call) == 1, impl
        impl.write_text(text.replace(call, call.replace(old, new)))
        return
    model = project / "plugin.yaml"
    text = model.read_text()
    if how == "removed":
        broken = re.sub(r"\n    classify:\n(?:      .*\n)+", "\n", text, count=1)
    else:  # the protocol starts at the parent's own first byte
        broken = re.sub(
            r"(\n    classify:\n(?:      .*\n)*?)      offset: \d+\n",
            r"\1      offset: 0\n",
            text,
            count=1,
        )
    assert broken != text, model
    model.write_text(broken)


@pytest.mark.parametrize(
    ("project", "how"),
    [(n, "hook" if n in HOOKED else "removed") for n in PARENTED] + [("dns", "offset")],
    indirect=["project"],
)
def test_only_the_run_through_the_parent_fails_when_its_classification_breaks(
    project: Path, how: str, capsys: pytest.CaptureFixture[str]
) -> None:
    sdk, cc = str(_sdk()), _cc()
    _break_parent(project, how)
    code, doc = _json(capsys, "test", "--sdk", sdk, "--cc", cc)
    assert code == 6, (doc["error"], doc["result"] and doc["result"]["packets"])
    assert doc["error"]["code"] == "test.packet-failed"
    # The run through the parent fails; so do the session tests, which run
    # through it too (#99), but none of the packets the harness attaches.
    failed = [p for p in doc["result"]["packets"] if p["status"] != "pass"]
    assert [p for p in failed if "session" not in p] == failed[:1], doc["result"]["packets"]
    assert "through" in failed[0], doc["result"]["packets"]
    sessions = [p for p in failed if "session" in p]
    assert bool(sessions) == (project.name in ("websocket", "ocpp")), failed
    for session in sessions:
        # Its packets of the plugin's are not classified any more.
        assert {(f["attribute"], f["actual"]) for f in session["failures"]} == {
            ("<protocol>", "not classified")
        }, session
    first = failed[0]["failures"][0]
    if how == "offset":
        assert first == {
            "attribute": "<parent>",
            "expected": "udp at offset 42",
            "actual": "udp at offset 34",
        }
    else:
        assert (first["attribute"], first["actual"]) == ("<protocol>", "not classified")


# --- session tests -------------------------------------------------------------------

#: RFC 6455 section 1.2's opening handshake (the shared TCP test below).
_WS_REQUEST = (
    b"GET /chat HTTP/1.1\r\nHost: server.example.com\r\nUpgrade: websocket\r\n"
    b"Connection: Upgrade\r\nSec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n"
    b"Origin: http://example.com\r\nSec-WebSocket-Protocol: chat, superchat\r\n"
    b"Sec-WebSocket-Version: 13\r\n\r\n"
)
_WS_ANSWER = (
    b"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
    b"Sec-WebSocket-Accept: s3pPLMBiTxaQ9kYGzzhZRbK+xOo=\r\nSec-WebSocket-Protocol: chat\r\n\r\n"
)
_WS_KEY = bytes.fromhex("37fa213d")
_HELLO = b"Hello"


def _masked(header: bytes, payload: bytes) -> bytes:
    """A client frame: ``header`` (its MASK bit set), section 5.7's key, the
    payload masked with it (RFC 6455 section 5.3)."""
    return header + _WS_KEY + bytes(b ^ _WS_KEY[i % 4] for i, b in enumerate(payload))


#: OCPP-J 1.6 section 3: the Charge Point's opening handshake, offering
#: ocpp1.6 and ocpp1.5 (the section's example), and the answer selecting one.
_OCPP_REQUEST = (
    b"GET /webServices/ocpp/CP3211 HTTP/1.1\r\nHost: some.server.com:33033\r\n"
    b"Upgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: x3JJHMbDL1EzLkh9GBhXDw==\r\n"
    b"Sec-WebSocket-Protocol: ocpp1.6, ocpp1.5\r\nSec-WebSocket-Version: 13\r\n\r\n"
)
_OCPP_ANSWER = (
    b"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
    b"Sec-WebSocket-Accept: HSmrc0sMlYUkAGmm5OPpG2HaGWk=\r\n"
    b"Sec-WebSocket-Protocol: ocpp1.6\r\n\r\n"
)
#: OCPP 1.6 section 6.3 and 6.4: BootNotification.req and .conf.
_BOOT = b'{"chargePointVendor":"VendorX","chargePointModel":"SingleSocketCharger"}'
_BOOT_CONF = b'{"status":"Accepted","currentTime":"2013-02-01T20:53:32.486Z","interval":300}'
_Want = dict[str, int | bytes | None]


def _text(payload: bytes, *, masked: bool) -> bytes:
    """One text frame (RFC 6455 section 5.2), masked for a client (section 5.3)."""
    n = len(payload)
    length = bytes([n]) if n < 126 else bytes([126]) + n.to_bytes(2, "big")
    header = bytes([0x81, length[0] | (0x80 if masked else 0)]) + length[1:]
    return _masked(header, payload) if masked else header + payload


def _call(uid: bytes, action: bytes, payload: bytes = b"{}") -> bytes:
    """A CALL (OCPP-J 1.6 section 4.2.1)."""
    return b'[2,"' + uid + b'","' + action + b'",' + payload + b"]"


def _result(uid: bytes, payload: bytes = b"{}") -> bytes:
    """A CALLRESULT (OCPP-J 1.6 section 4.2.2)."""
    return b'[3,"' + uid + b'",' + payload + b"]"


def _called(uid: bytes, action: bytes, payload: bytes = b"{}") -> _Want:
    """What a segment whose only message is that CALL reports."""
    return {
        "message_type_id": 2,
        "unique_id": uid,
        "action": action,
        "payload": payload,
        "message_count": 1,
    }


def _answered(uid: bytes, action: bytes | None, payload: bytes = b"{}") -> _Want:
    """What a segment whose only message is a CALLRESULT reports: ``action``,
    the CALL's it is linked to (``None``: none)."""
    return {
        "message_type_id": 3,
        "unique_id": uid,
        "action": action,
        "payload": payload,
        "message_count": 1,
    }


def _session_tests(project: Path) -> list[SessionTest]:
    tests = [load_test(p, p.name, _TYPES) for p in sorted((project / "tests").glob("*.yaml"))]
    return [t for t in tests if isinstance(t, SessionTest)]


@pytest.mark.parametrize("project", ["websocket", "ocpp"], indirect=True)
def test_the_session_tests_follow_the_plugins_state(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The WebSocket and OCPP examples' session tests (#99; written from the
    replays of #40 and #41): several frames in a segment, frames and headers
    over segments, retransmissions, lost bytes, refused upgrades, answers
    linked to their CALL, idle gaps and sessions longer than mmt-dpi's TCP
    classifies (examples/README.md), each packet checked with every
    attribute the session lists; then under the sanitizers, with their
    corrupted copies. Without its CALL, a CALLRESULT is not linked: the
    expected action comes from the session, not from the packet."""
    sdk, cc = str(_sdk()), _cc()
    sessions = _session_tests(project)
    assert len(sessions) == {"websocket": 8, "ocpp": 12}[project.name]
    code, doc = _json(
        capsys,
        "test",
        "--sdk",
        sdk,
        "--cc",
        cc,
        "--sanitize",
        "--fuzz-count",
        "300",
        *(f"tests/{Path(t.file).name}" for t in sessions),
    )
    assert code == 0, (doc["error"], doc["result"] and doc["result"]["packets"])
    result = doc["result"]
    frames = {t.id: len(build_frames(t)) for t in sessions}
    assert {p["id"]: p["session"] for p in result["packets"]} == frames
    assert all(p["status"] == "pass" for p in result["packets"])
    copies = sum(n * (1 + math.ceil(300 / n)) for n in frames.values())
    assert result["sanitize"] == {"seed": 0, "count": copies, "crashes": []}

    if project.name != "ocpp":
        return
    path = project / "tests" / "session-after-handshake.yaml"
    text = path.read_text()
    # Drop the CALL, the first step: its CALLRESULT is now the first packet.
    first = text.index("  - from:")
    second = text.index("  - from:", first + 1)
    path.write_text(text[:first] + text[second:])
    code, doc = _json(
        capsys, "test", "--sdk", sdk, "--cc", cc, "tests/session-after-handshake.yaml"
    )
    assert code == 6, doc["error"]
    (packet,) = doc["result"]["packets"]
    assert packet["failures"] == [
        {
            "attribute": "action",
            "expected": "52 65 6d 6f 74 65 53 74 61 72 74 54 72 61 6e 73 61 63 74 69 6f 6e",
            "actual": "absent",
            "packet": 0,
        }
    ]


def _ocpp_project(tmp_path: Path, name: str, capsys: pytest.CaptureFixture[str]) -> Path:
    """A copy of an example, built and tested with its harness; the current
    directory."""
    sdk, cc = _sdk(), _cc()
    project = tmp_path / name
    shutil.copytree(EXAMPLES / name, project, ignore=shutil.ignore_patterns("build"))
    os.chdir(project)
    code, doc = _json(capsys, "test", "--sdk", str(sdk), "--cc", cc)
    assert code == 0, (doc["error"], doc["result"] and doc["result"]["packets"])
    return project


def _harness_names(project: Path) -> list[str]:
    """The attributes the project's harness reads, in its order."""
    tests = [load_test(p, p.name, _TYPES) for p in (project / "tests").glob("*.yaml")]
    sizes = {
        c.name: c.size or 0
        for c in resolve_profile("1.10.2", {}, None, None).profile.constants
        if c.group == DATA_TYPE_GROUP
    }
    return [n for n, _ in sorted(harness_lengths(tests, sizes).items())]


def _check_replay(
    run: harness.HarnessRun,
    names: list[str],
    frames: list[bytes],
    want: dict[int, _Want | None],
) -> None:
    """Each frame is the plugin's, directly above TCP, with the attributes
    ``want`` gives it (unlisted ones absent), or not (``None``)."""
    assert harness.crash_reason(run, len(frames)) is None, run.stderr
    parsed = harness.parse_check(run.lines, names)
    assert parsed.malformed is None and parsed.error is None, run.lines
    assert sorted(parsed.observations) == list(range(len(frames)))
    for i, observed in parsed.observations.items():
        expected = want.get(i, {})
        if expected is None:
            assert observed.index is None, (i, observed)
            continue
        # Directly above TCP, after Ethernet, IPv4 and a 20-byte TCP header.
        assert (observed.index, observed.offset) == (4, 54), (i, observed)
        seen: dict[str, int | bytes | None] = {}
        for name in names:
            value = observed.values[name]
            assert value.kind in ("absent", "int", "hex"), (i, name, value)
            seen[name] = value.data if value.kind == "hex" else value.number
        assert seen == {n: expected.get(n) for n in names}, i


def _run_with(program: Path, packets: Path, plugins: list[Path], sdk: Path) -> harness.HarnessRun:
    """``harness check`` as ``harness.run`` runs it, with several plugins in
    its plugin directory, next to the SDK's libmmt_tcpip.so."""
    root = Path(tempfile.mkdtemp(prefix="mmt-plugin-test-", dir=packets.parent))
    directory = root / "plugins"
    directory.mkdir()
    (directory / harness.TCPIP).symlink_to(os.path.realpath(sdk / "plugins" / harness.TCPIP))
    for plugin in plugins:
        (directory / plugin.name).symlink_to(os.path.realpath(plugin))
    cwd = root / "run"
    cwd.mkdir()
    env = {k: v for k, v in os.environ.items() if k not in ("LD_LIBRARY_PATH", "LD_PRELOAD")}
    env.update(MMT_DPI_PLUGINS_DIR=str(directory), LC_ALL="C")
    proc = subprocess.run(
        [str(program), "check", str(packets)],
        cwd=cwd,
        env=env,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        errors="replace",
        timeout=60,
        check=False,
    )
    return harness.HarnessRun(proc.returncode, proc.stdout.splitlines(), proc.stderr)


def test_the_ocpp_and_websocket_examples_share_tcp(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Both plugins in one plugin directory (mmtp_ocpp_example.so loads
    first, both above TCP): an ocpp1.6 session is OCPP_EXAMPLE directly above
    TCP, and a WebSocket session for another subprotocol stays
    WEBSOCKET_EXAMPLE (examples/README.md, "OCPP 1.6-J")."""
    sdk = _sdk()
    monkeypatch.delenv("MMT_PLUGIN_SDK_PROFILE", raising=False)
    monkeypatch.chdir(tmp_path)
    ocpp = _ocpp_project(tmp_path, "ocpp", capsys)
    websocket = _ocpp_project(tmp_path, "websocket", capsys)
    plugins = [
        ocpp / "build" / "mmtp_ocpp_example.so",
        websocket / "build" / "mmtp_websocket_example.so",
    ]

    frames: list[bytes] = []
    ocpp_want: dict[int, _Want | None] = {}
    o = Connection(frames, bytes([198, 18, 0, 31]), 49300, 9000)
    o.open()
    for i in range(3):
        ocpp_want[i] = None
    ocpp_want[o.client(_OCPP_REQUEST)] = {}
    ocpp_want[o.server(_OCPP_ANSWER)] = {}
    ocpp_want[o.client(_text(_call(b"1", b"BootNotification", _BOOT), masked=True))] = _called(
        b"1", b"BootNotification", _BOOT
    )
    ocpp_want[o.server(_text(_result(b"1", _BOOT_CONF), masked=False))] = _answered(
        b"1", b"BootNotification", _BOOT_CONF
    )
    ocpp_session = len(frames)
    w = Connection(frames, bytes([198, 18, 0, 32]), 49301, 9000)
    w.open()
    w.client(_WS_REQUEST)
    w.server(_WS_ANSWER)
    w.client(_masked(b"\x81\x85", _HELLO))
    w.server(_text(_call(b"1", b"Heartbeat"), masked=False))  # OCPP-J shaped, in a chat session
    for i in range(ocpp_session, len(frames)):
        ocpp_want[i] = None
    packets = tmp_path / "both.bin"
    harness.write_packets(packets, [harness.Record(f, frame=True) for f in frames])

    run = _run_with(ocpp / "build" / "test" / "harness", packets, plugins, sdk)
    _check_replay(run, _harness_names(ocpp), frames, ocpp_want)

    run = _run_with(websocket / "build" / "test" / "harness", packets, plugins, sdk)
    assert harness.crash_reason(run, len(frames)) is None, run.stderr
    parsed = harness.parse_check(run.lines, _harness_names(websocket))
    assert parsed.malformed is None and parsed.error is None, run.lines
    assert sorted(parsed.observations) == list(range(len(frames)))
    # WEBSOCKET_EXAMPLE from the chat session's request on, directly above TCP;
    # never in the OCPP session.
    chat = ocpp_session + 3
    for i, observed in parsed.observations.items():
        where = (4, 54) if i >= chat else (None, None)
        assert (observed.index, observed.offset) == where, (i, observed)
    assert parsed.observations[chat].values["handshake"].number == 1
    assert parsed.observations[chat + 2].values["payload"].data == _HELLO
