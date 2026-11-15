"""The examples (plan T5.1, #28: "CI builds and tests every ported
example"; the WebSocket example, #40) against a real mmt-dpi SDK.

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
run fails. The WebSocket example also replays TCP sessions through the
harness that ``test`` built (``tcpsession.py``), packet by packet, since
its state spans segments. The SDK is an extracted mmt-dpi package, a
private prefix (never ``/opt/mmt``), as for
``tests/unit/packettest/test_sdk.py``::

    MMT_GOLDEN_SDK=<dir>/opt/mmt MMT_GOLDEN_CC=gcc uv run pytest tests/unit/examples/test_sdk.py

Without ``MMT_GOLDEN_SDK`` the tests skip, unless
``MMT_REQUIRE_GOLDEN_COMPILE=1`` (CI's "Generated code" job) makes them fail.
"""

from __future__ import annotations

import json
import os
import random
import re
import shutil
from pathlib import Path
from typing import Any

import pytest

from mmt_plugin.cli import main
from mmt_plugin.sdk.profile import DATA_TYPE_GROUP
from mmt_plugin.sdk.resolve import resolve_profile
from mmt_plugin.testing import harness
from mmt_plugin.testing.packets import harness_lengths, load

from .tcpsession import Session

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


def _runs(project: Path) -> int:
    """The packet runs of a project's tests: each one, and each ``through``."""
    tests = [load(p, p.name, _TYPES) for p in (project / "tests").glob("*.yaml")]
    return len(tests) + sum(1 for t in tests if t.through is not None)


def test_every_example_is_tested() -> None:
    assert len(NAMES) == 17
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
    runs = _runs(project)
    assert result["summary"] == {"total": runs, "passed": runs, "failed": 0, "skipped": 0}
    assert all(p["attributes"] > 0 for p in result["packets"]), result["packets"]
    through = [p for p in result["packets"] if "through" in p]
    assert len(through) == (0 if project.name in NO_PARENT else 1), result["packets"]
    assert result["sanitize"] == {"seed": 0, "count": 101 * runs, "crashes": []}
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
    failed = [p for p in doc["result"]["packets"] if p["status"] != "pass"]
    assert [("through" in p) for p in failed] == [True], doc["result"]["packets"]
    first = failed[0]["failures"][0]
    if how == "offset":
        assert first == {
            "attribute": "<parent>",
            "expected": "udp at offset 42",
            "actual": "udp at offset 34",
        }
    else:
        assert (first["attribute"], first["actual"]) == ("<protocol>", "not classified")


# --- the WebSocket example's session replay ---

#: RFC 6455 section 1.2's opening handshake, and section 4.4's refused one.
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
_WS_REFUSED = b"HTTP/1.1 400 Bad Request\r\nSec-WebSocket-Version: 13\r\n\r\n"
#: What the request reports (RFC 6455 section 1.2 and 4.1).
_WS_REQUESTED: dict[str, int | bytes | None] = {
    "handshake": 1,
    "key": b"dGhlIHNhbXBsZSBub25jZQ==",
    "subprotocol": b"chat, superchat",
}
_WS_KEY = bytes.fromhex("37fa213d")
_HELLO = b"Hello"


def _masked(header: bytes, payload: bytes) -> bytes:
    """A client frame: ``header`` (its MASK bit set), section 5.7's key, the
    payload masked with it (RFC 6455 section 5.3)."""
    return header + _WS_KEY + bytes(b ^ _WS_KEY[i % 4] for i, b in enumerate(payload))


def _frame(
    *,
    opcode: int,
    payload: bytes,
    length: int | None = None,
    offset: int = 2,
    fin: int = 1,
    masked: bool = False,
    count: int = 1,
    carried: int = 0,
    message: int | None = None,
    close: int | None = None,
    handshake: int = 0,
) -> dict[str, int | bytes | None]:
    """The attributes of a segment whose first frame is this one."""
    return {
        "handshake": handshake,
        "subprotocol": b"chat",
        "fin": fin,
        "rsv1": 0,
        "rsv2": 0,
        "rsv3": 0,
        "opcode": opcode,
        "mask": int(masked),
        "masking_key": int.from_bytes(_WS_KEY, "big") if masked else None,
        "payload_len": len(payload) if length is None else length,
        "payload_offset": offset,
        "payload": payload,
        "frame_count": count,
        "carried_len": carried,
        "message_opcode": message,
        "close_code": close,
    }


def _websocket_replay() -> tuple[list[bytes], dict[int, dict[str, int | bytes | None] | None]]:
    """The frames of four TCP sessions and what each one must report: by
    index, the attributes (unlisted ones absent; ``None``: absent), or
    ``None`` when the packet is not WebSocket. An index not listed is
    WebSocket with every attribute absent (a pure ACK, a retransmission)."""
    frames: list[bytes] = []
    want: dict[int, dict[str, int | bytes | None] | None] = {}

    # A session on port 8080 (any port: the handshake says WebSocket).
    s = Session(frames, 1, 49152, 8080)
    s.open()
    for i in range(3):
        want[i] = None  # before the handshake: TCP only
    want[s.client(_WS_REQUEST)] = dict(_WS_REQUESTED)
    s.server()  # a pure ACK: classified, nothing to report
    want[s.server(_WS_ANSWER)] = {
        "handshake": 2,
        "status_code": 101,
        "accept": b"s3pPLMBiTxaQ9kYGzzhZRbK+xOo=",
        "subprotocol": b"chat",
    }
    want[s.client(_masked(b"\x81\x85", _HELLO))] = _frame(
        opcode=1, payload=_HELLO, offset=6, masked=True, message=1
    )
    # Two frames in one segment: a fragmented message (section 5.7).
    want[s.server(b"\x01\x03Hel\x80\x02lo")] = _frame(
        opcode=1, payload=b"Hel", fin=0, count=2, message=1
    )
    # The same message, one frame per segment: the continuation's message.
    want[s.server(b"\x01\x03Hel")] = _frame(opcode=1, payload=b"Hel", fin=0, message=1)
    want[s.server(b"\x80\x02lo")] = _frame(opcode=0, payload=b"lo", message=1)
    # A 256-byte binary frame over two segments, then a ping after it.
    body = bytes(range(256))
    want[s.server(b"\x82\x7e\x01\x00" + body[:96])] = _frame(
        opcode=2, payload=body[:96], length=256, offset=4, message=2
    )
    want[s.server(body[96:] + b"\x89\x05" + _HELLO)] = _frame(
        opcode=9, payload=_HELLO, offset=162, carried=160
    )
    # A masked pong whose 6-byte header is split 4 + 2 over two segments.
    pong = _masked(b"\x8a\x85", _HELLO)
    want[s.client(pong[:4])] = {"handshake": 0, "subprotocol": b"chat", "carried_len": 0}
    second = s.client_seq
    want[s.client(pong[4:])] = _frame(opcode=10, payload=_HELLO, offset=2, masked=True)
    s.client(pong[4:], seq=second)  # its retransmission: nothing, counted once
    s.client()
    # Over 40 packets: mmt-dpi's TCP stops classifying a session its own
    # detection did not classify, and the layer's session data hooks run
    # instead (src/websocket_example_impl.c); the same answers.
    while len(frames) < 50:
        want[s.client(_masked(b"\x81\x85", _HELLO))] = _frame(
            opcode=1, payload=_HELLO, offset=6, masked=True, message=1
        )
        want[s.server(b"\x81\x05" + _HELLO)] = _frame(opcode=1, payload=_HELLO, message=1)
    want[s.server(b"\x82\x7e\x01\x00" + body[:96])] = _frame(
        opcode=2, payload=body[:96], length=256, offset=4, message=2
    )
    want[s.server(body[96:200])] = {"handshake": 0, "subprotocol": b"chat", "carried_len": 104}
    s.skip_server(36)  # payload bytes the capture lost: still in step after them
    want[s.server(body[236:] + b"\x01\x03Hel")] = _frame(
        opcode=1, payload=b"Hel", fin=0, offset=22, carried=20, message=1
    )
    want[s.server(b"\x80\x02lo")] = _frame(opcode=0, payload=b"lo", message=1)
    s.client()
    want[s.server(b"\x88\x02\x03\xe8")] = _frame(opcode=8, payload=b"\x03\xe8", close=1000)
    want[s.client(_masked(b"\x88\x82", b"\x03\xe8"))] = _frame(
        opcode=8, payload=b"\x03\xe8", offset=6, masked=True, close=1000
    )

    # The server refuses the upgrade: HTTP goes on, no frames.
    r = Session(frames, 2, 49153, 8080)
    r.open()
    for i in range(len(frames) - 3, len(frames)):
        want[i] = None
    want[r.client(_WS_REQUEST)] = dict(_WS_REQUESTED)
    want[r.server(_WS_REFUSED)] = {"handshake": 2, "status_code": 400}
    r.server(b"\x81\x05" + _HELLO)
    r.client(_masked(b"\x81\x85", _HELLO))

    # Plain HTTP on the same port: not WebSocket.
    h = Session(frames, 3, 49154, 8080)
    h.open()
    h.client(b"GET /chat HTTP/1.1\r\nHost: server.example.com\r\n\r\n")
    h.server(b"HTTP/1.1 200 OK\r\nContent-Length: 0\r\n\r\n")
    for i in range(len(frames) - 5, len(frames)):
        want[i] = None

    # A capture that starts at the server's answer, with a frame after it.
    a = Session(frames, 4, 49155, 8080)
    want[a.server(_WS_ANSWER + b"\x81\x05" + _HELLO)] = {
        **_frame(opcode=1, payload=_HELLO, offset=len(_WS_ANSWER) + 2, message=1, handshake=2),
        "status_code": 101,
        "accept": b"s3pPLMBiTxaQ9kYGzzhZRbK+xOo=",
    }
    want[a.client(_masked(b"\x81\x85", _HELLO))] = _frame(
        opcode=1, payload=_HELLO, offset=6, masked=True, message=1
    )

    # Answers whose header block goes on in the next segment, cut in a line
    # and in the blank line's CR LF: the field and the end are found there.
    for n, cut in ((5, _WS_ANSWER.index(b"Accept:") + 10), (6, len(_WS_ANSWER) - 1)):
        c = Session(frames, n, 49150 + n, 8080)
        want[c.client(_WS_REQUEST)] = dict(_WS_REQUESTED)
        first: dict[str, int | bytes | None] = {"handshake": 2, "status_code": 101}
        if n == 6:
            first.update(accept=b"s3pPLMBiTxaQ9kYGzzhZRbK+xOo=", subprotocol=b"chat")
        want[c.server(_WS_ANSWER[:cut])] = first
        rest = _WS_ANSWER[cut:]
        want[c.server(rest + b"\x81\x05" + _HELLO)] = _frame(
            opcode=1, payload=_HELLO, offset=len(rest) + 2, message=1
        )
        want[c.client(_masked(b"\x81\x85", _HELLO))] = _frame(
            opcode=1, payload=_HELLO, offset=6, masked=True, message=1
        )
    return frames, want


def _check_websocket_replay(
    run: harness.HarnessRun,
    names: list[str],
    frames: list[bytes],
    want: dict[int, dict[str, int | bytes | None] | None],
) -> None:
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


def test_the_websocket_example_follows_its_sessions(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The WebSocket example's state, through mmt-dpi's TCP: several frames in
    a segment, frames and headers over segments, a retransmission, lost
    bytes, a refused upgrade, plain HTTP not claimed, any port, and a
    session longer than mmt-dpi's TCP classifies (examples/README.md,
    "WebSocket"); with and without the sanitizers, then with its payloads
    corrupted and its frames cut short, under them."""
    sdk, cc = _sdk(), _cc()
    project = tmp_path / "websocket"
    shutil.copytree(EXAMPLES / "websocket", project, ignore=shutil.ignore_patterns("build"))
    monkeypatch.chdir(project)
    monkeypatch.delenv("MMT_PLUGIN_SDK_PROFILE", raising=False)
    # test builds the plugin and its harness, which reads every attribute,
    # and both again with ASan and UBSan.
    code, doc = _json(
        capsys, "test", "--sdk", str(sdk), "--cc", cc, "--sanitize", "--fuzz-count", "10"
    )
    assert code == 0, (doc["error"], doc["result"] and doc["result"]["packets"])
    tests = [load(p, p.name, _TYPES) for p in (project / "tests").glob("*.yaml")]
    sizes = {
        c.name: c.size or 0
        for c in resolve_profile("1.10.2", {}, None, None).profile.constants
        if c.group == DATA_TYPE_GROUP
    }
    names = [n for n, _ in sorted(harness_lengths(tests, sizes).items())]
    assert len(names) == 19, names
    build = project / "build"
    builds = [
        (build / "test" / "harness", build / "mmtp_websocket_example.so"),
        (build / "test" / "harness-sanitize", build / "sanitize" / "mmtp_websocket_example.so"),
    ]

    frames, want = _websocket_replay()
    packets = tmp_path / "session.bin"
    harness.write_packets(packets, [harness.Record(f, frame=True) for f in frames])
    for program, plugin in builds:
        run = harness.run(program, ["check", str(packets)], plugin, sdk / "plugins", timeout=60)
        _check_websocket_replay(run, names, frames, want)

    # The same sessions, each payload byte changed with probability 1/8 and
    # one frame in four cut short: no crash.
    rng = random.Random(0)
    for _ in range(5):
        broken = []
        for frame in frames:
            data = bytearray(frame)
            for k in range(54, len(data)):
                if rng.random() < 0.125:
                    data[k] = rng.randrange(256)
            if len(data) > 55 and rng.random() < 0.25:
                del data[rng.randrange(54, len(data)) :]
            broken.append(harness.Record(bytes(data), frame=True))
        harness.write_packets(packets, broken)
        program, plugin = builds[1]
        run = harness.run(program, ["fuzz", str(packets)], plugin, sdk / "plugins", timeout=60)
        assert harness.crash_reason(run, len(broken)) is None, run.stderr
