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
run fails. The WebSocket and OCPP examples also replay TCP sessions
through the harness that ``test`` built (``tcpsession.py``), packet by
packet, since their state spans segments, and the OCPP example's run next
to the WebSocket example's plugin. The SDK is an extracted mmt-dpi package, a
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
import subprocess
import tempfile
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


def _runs(project: Path) -> int:
    """The packet runs of a project's tests: each one, and each ``through``."""
    tests = [load(p, p.name, _TYPES) for p in (project / "tests").glob("*.yaml")]
    return len(tests) + sum(1 for t in tests if t.through is not None)


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

    # The capture loses a frame's header and its first payload bytes: the
    # segment after the gap starts inside the frame, and reports no frame;
    # the parse starts again at the next segment that starts with a valid
    # header (#104).
    g = Session(frames, 7, 49157, 8080)
    want[g.client(_WS_REQUEST)] = dict(_WS_REQUESTED)
    want[g.server(_WS_ANSWER)] = {
        "handshake": 2,
        "status_code": 101,
        "accept": b"s3pPLMBiTxaQ9kYGzzhZRbK+xOo=",
        "subprotocol": b"chat",
    }
    want[g.server(b"\x81\x05" + _HELLO)] = _frame(opcode=1, payload=_HELLO, message=1)
    g.skip_server(5)  # b"\x81\x0bHel" of b"\x81\x0bHello world"
    want[g.server(b"lo world")] = {"handshake": 0, "subprotocol": b"chat"}
    want[g.server(b"\x81\x05" + _HELLO)] = _frame(opcode=1, payload=_HELLO, message=1)

    # A session idle for longer than mmt-dpi's default session timeout (60
    # s; the harness's packets are 1 s apart): still the same session, its
    # state kept (#104).
    q = Session(frames, 8, 49158, 8080)
    want[q.client(_WS_REQUEST)] = dict(_WS_REQUESTED)
    want[q.server(_WS_ANSWER)] = {
        "handshake": 2,
        "status_code": 101,
        "accept": b"s3pPLMBiTxaQ9kYGzzhZRbK+xOo=",
        "subprotocol": b"chat",
    }
    body = bytes(range(200))
    want[q.server(b"\x82\x7e\x00\xc8" + body[:100])] = _frame(
        opcode=2, payload=body[:100], length=200, offset=4, message=2
    )
    _idle(frames, want, 70)
    want[q.server(body[100:] + b"\x81\x05" + _HELLO)] = _frame(
        opcode=1, payload=_HELLO, offset=102, carried=100, message=1
    )
    return frames, want


def _idle(frames: list[bytes], want: dict[int, Any], seconds: int) -> None:
    """``seconds`` packets of other TCP traffic (the harness's packets are
    1 s apart), none of them the plugin's."""
    other = Session(frames, 99, 40000, 7)
    for _ in range(seconds):
        want[other.client()] = None


def _check_replay(
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
        _check_replay(run, names, frames, want)

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


# --- the OCPP 1.6-J example's session replay ---

#: OCPP-J 1.6 section 3: the Charge Point's opening handshake, offering
#: ocpp1.6 and ocpp1.5 (the section's example), and the answer selecting one.
_OCPP_REQUEST = (
    b"GET /webServices/ocpp/CP3211 HTTP/1.1\r\nHost: some.server.com:33033\r\n"
    b"Upgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: x3JJHMbDL1EzLkh9GBhXDw==\r\n"
    b"Sec-WebSocket-Protocol: ocpp1.6, ocpp1.5\r\nSec-WebSocket-Version: 13\r\n\r\n"
)


def _ocpp_answer(subprotocol: bytes) -> bytes:
    """The 101 answer (RFC 6455 section 4.2.2) selecting ``subprotocol``."""
    return (
        b"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
        b"Sec-WebSocket-Accept: HSmrc0sMlYUkAGmm5OPpG2HaGWk=\r\n"
        b"Sec-WebSocket-Protocol: " + subprotocol + b"\r\n\r\n"
    )


_OCPP_ANSWER = _ocpp_answer(b"ocpp1.6")
#: OCPP 1.6 section 6.3 and 6.4: BootNotification.req and .conf.
_BOOT = b'{"chargePointVendor":"VendorX","chargePointModel":"SingleSocketCharger"}'
_BOOT_CONF = b'{"status":"Accepted","currentTime":"2013-02-01T20:53:32.486Z","interval":300}'
#: OCPP 1.6 section 6.30: Heartbeat.conf.
_HB_CONF = b'{"currentTime":"2013-02-01T20:53:32.486Z"}'
_ACCEPTED = b'{"status":"Accepted"}'
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


def _error(uid: bytes, code: bytes, description: bytes, details: bytes = b"{}") -> bytes:
    """A CALLERROR (OCPP-J 1.6 section 4.2.3)."""
    return b'[4,"' + uid + b'","' + code + b'","' + description + b'",' + details + b"]"


def _called(
    uid: bytes, action: bytes, payload: bytes = b"{}", count: int = 1, **typed: int | bytes
) -> _Want:
    """What a segment whose first message is that CALL reports."""
    return {
        "message_type_id": 2,
        "unique_id": uid,
        "action": action,
        "payload": payload,
        "message_count": count,
        **typed,
    }


def _answered(
    kind: int,
    uid: bytes,
    action: bytes | None,
    payload: bytes = b"{}",
    count: int = 1,
    **error: bytes,
) -> _Want:
    """What a segment whose first message is an answer reports: ``action``,
    the CALL's it is linked to (``None``: none)."""
    return {
        "message_type_id": kind,
        "unique_id": uid,
        "action": action,
        "payload": payload,
        "message_count": count,
        **error,
    }


def _ocpp_replay() -> tuple[list[bytes], dict[int, _Want | None]]:
    """The frames of OCPP and other TCP sessions and what each one must
    report, as ``_websocket_replay``'s: by index, the attributes, or
    ``None`` when the packet is not OCPP_EXAMPLE; an index not listed is
    OCPP_EXAMPLE with every attribute absent."""
    frames: list[bytes] = []
    want: dict[int, _Want | None] = {}

    # An OCPP 1.6-J session on port 9000 (any port: the handshake says OCPP).
    s = Session(frames, 11, 49200, 9000)
    s.open()
    for i in range(3):
        want[i] = None  # before the handshake: TCP only
    want[s.client(_OCPP_REQUEST)] = {}
    s.server()  # a pure ACK
    want[s.server(_OCPP_ANSWER)] = {}
    # CALL then CALLRESULT: the answer reports the CALL's action; the same
    # answer again finds no CALL left to answer.
    want[s.client(_text(_call(b"1", b"BootNotification", _BOOT), masked=True))] = _called(
        b"1", b"BootNotification", _BOOT
    )
    want[s.server(_text(_result(b"1", _BOOT_CONF), masked=False))] = _answered(
        3, b"1", b"BootNotification", _BOOT_CONF
    )
    want[s.server(_text(_result(b"1", _BOOT_CONF), masked=False))] = _answered(
        3, b"1", None, _BOOT_CONF
    )
    # CALL then CALLERROR (OCPP-J 1.6 section 4.2.3, InternalError's description).
    auth = b'{"idTag":"B4F62CEF"}'
    want[s.client(_text(_call(b"2", b"Authorize", auth), masked=True))] = _called(
        b"2", b"Authorize", auth, id_tag=b"B4F62CEF"
    )
    internal = (
        b"An internal error occurred and the receiver was not able to process the "
        b"requested Action successfully"
    )
    want[s.server(_text(_error(b"2", b"InternalError", internal), masked=False))] = _answered(
        4, b"2", b"Authorize", error_code=b"InternalError", error_description=internal[:63]
    )
    # Both sides send a CALL with UniqueId 7: each answer goes to the other side's.
    remote = b'{"connectorId":1,"idTag":"B4F62CEF"}'
    want[s.server(_text(_call(b"7", b"RemoteStartTransaction", remote), masked=False))] = _called(
        b"7", b"RemoteStartTransaction", remote, connector_id=1, id_tag=b"B4F62CEF"
    )
    status = b'{"connectorId":1,"errorCode":"NoError","status":"Preparing"}'
    want[s.client(_text(_call(b"7", b"StatusNotification", status), masked=True))] = _called(
        b"7", b"StatusNotification", status, connector_id=1
    )
    want[s.client(_text(_result(b"7", _ACCEPTED), masked=True))] = _answered(
        3, b"7", b"RemoteStartTransaction", _ACCEPTED
    )
    want[s.server(_text(_result(b"7"), masked=False))] = _answered(3, b"7", b"StatusNotification")
    # An answer from the CALL's own side is not its answer; an unknown UniqueId.
    want[s.client(_text(_call(b"8", b"Heartbeat"), masked=True))] = _called(b"8", b"Heartbeat")
    want[s.client(_text(_result(b"8"), masked=True))] = _answered(3, b"8", None)
    want[s.server(_text(_result(b"8", _HB_CONF), masked=False))] = _answered(
        3, b"8", b"Heartbeat", _HB_CONF
    )
    want[s.server(_text(_result(b"99"), masked=False))] = _answered(3, b"99", None)
    # Two messages in a segment: both are linked, the first is reported.
    two = _text(_call(b"a", b"Heartbeat"), masked=True)
    two += _text(_call(b"b", b"Heartbeat"), masked=True)
    want[s.client(two)] = _called(b"a", b"Heartbeat", count=2)
    two = _text(_result(b"a", _HB_CONF), masked=False) + _text(_result(b"b"), masked=False)
    want[s.server(two)] = _answered(3, b"a", b"Heartbeat", _HB_CONF, count=2)
    want[s.server(_text(_result(b"b"), masked=False))] = _answered(3, b"b", None)
    # A limit with two fractional digits is cut to tenths (src/ocpp_example_impl.c).
    profile = (
        b'{"connectorId":2,"csChargingProfiles":{"chargingProfileId":3,"stackLevel":0,'
        b'"chargingProfilePurpose":"TxDefaultProfile","chargingProfileKind":"Absolute",'
        b'"chargingSchedule":{"chargingRateUnit":"A","chargingSchedulePeriod":'
        b'[{"startPeriod":0,"limit":32.25}]}}}'
    )
    want[s.server(_text(_call(b"c", b"SetChargingProfile", profile), masked=False))] = _called(
        b"c",
        b"SetChargingProfile",
        profile,
        connector_id=2,
        charging_limit_x10=322,
        charging_rate_unit=b"A",
    )
    # A connectorId in a string or a nested object is not the payload's.
    decoy = (
        b'{"vendorId":"com.example","messageId":"{\\"connectorId\\":4}","meta":{"connectorId":5}}'
    )
    want[s.client(_text(_call(b"d", b"DataTransfer", decoy), masked=True))] = _called(
        b"d", b"DataTransfer", decoy
    )
    # An escaped quote in a UniqueId does not end it, and still links.
    quoted = b'e\\"1'
    want[s.client(_text(_call(quoted, b"Heartbeat"), masked=True))] = _called(quoted, b"Heartbeat")
    want[s.server(_text(_result(quoted), masked=False))] = _answered(3, quoted, b"Heartbeat")
    # A UniqueId over 36 bytes (OCPP-J 1.6 section 4.1.4) is not kept; 36 is.
    for uid, linked in ((b"x" * 40, None), (b"y" * 36, b"Heartbeat")):
        want[s.client(_text(_call(uid, b"Heartbeat"), masked=True))] = _called(uid, b"Heartbeat")
        want[s.server(_text(_result(uid), masked=False))] = _answered(3, uid, linked)
    # A frame over two segments: the first reports what it has; the second's
    # first bytes are the rest of it, then another frame.
    big = b'{"vendorId":"com.example","data":"' + b"0123456789" * 30 + b'"}'
    frame = _text(_call(b"f", b"DataTransfer", big), masked=True)
    cut = 100
    head = len(b'[2,"f","DataTransfer",')
    want[s.client(frame[:cut])] = _called(b"f", b"DataTransfer", big[: cut - 8 - head])
    want[s.client(frame[cut:] + _text(_call(b"g", b"Heartbeat"), masked=True))] = _called(
        b"g", b"Heartbeat"
    )
    want[s.server(_text(_result(b"f"), masked=False))] = _answered(3, b"f", b"DataTransfer")
    s.server(b"\x89\x00")  # a ping: not an OCPP-J message
    # Over 40 packets: the layer's session data hooks parse them (as for
    # websocket_example); the links go on.
    n = 0
    while len(frames) < 64:
        uid = b"h%d" % n
        want[s.client(_text(_call(uid, b"Heartbeat"), masked=True))] = _called(uid, b"Heartbeat")
        want[s.server(_text(_result(uid, _HB_CONF), masked=False))] = _answered(
            3, uid, b"Heartbeat", _HB_CONF
        )
        n += 1
    # 17 CALLs without an answer: the session keeps 16, the oldest goes.
    for i in range(17):
        uid = b"o%d" % i
        want[s.client(_text(_call(uid, b"Heartbeat"), masked=True))] = _called(uid, b"Heartbeat")
    for i, linked in ((0, None), (1, b"Heartbeat"), (16, b"Heartbeat")):
        uid = b"o%d" % i
        want[s.server(_text(_result(uid), masked=False))] = _answered(3, uid, linked)

    # The client offers ocpp1.6 and ocpp2.0.1, the server selects ocpp2.0.1:
    # the session is claimed, and reports nothing.
    r = Session(frames, 12, 49201, 9000)
    r.open()
    for i in range(len(frames) - 3, len(frames)):
        want[i] = None
    want[r.client(_OCPP_REQUEST.replace(b"ocpp1.6, ocpp1.5", b"ocpp1.6, ocpp2.0.1"))] = {}
    want[r.server(_ocpp_answer(b"ocpp2.0.1"))] = {}
    r.client(_text(_call(b"1", b"BootNotification", _BOOT), masked=True))
    r.server(_text(_result(b"1", _BOOT_CONF), masked=False))

    # The server refuses the upgrade: HTTP goes on, nothing to report.
    f = Session(frames, 13, 49202, 9000)
    want[f.client(_OCPP_REQUEST)] = {}
    want[f.server(b"HTTP/1.1 400 Bad Request\r\nSec-WebSocket-Version: 13\r\n\r\n")] = {}
    f.client(_text(_call(b"1", b"Heartbeat"), masked=True))

    # Not OCPP: a WebSocket session for another subprotocol (even with an
    # OCPP-J shaped frame), a subprotocol in another case, plain HTTP.
    for k, request in enumerate(
        (_WS_REQUEST, _OCPP_REQUEST.replace(b"ocpp1.6", b"OCPP1.6"), b"GET / HTTP/1.1\r\n\r\n")
    ):
        o = Session(frames, 14 + k, 49203 + k, 9000)
        o.open()
        o.client(request)
        o.server(_WS_ANSWER if k == 0 else b"HTTP/1.1 200 OK\r\nContent-Length: 0\r\n\r\n")
        o.client(_text(_call(b"1", b"Heartbeat"), masked=True))
        for i in range(len(frames) - 6, len(frames)):
            want[i] = None

    # A capture that starts after the handshake: the array shape claims the
    # session, whose CALLs are linked from there.
    m = Session(frames, 17, 49206, 9000)
    want[m.server(_text(_call(b"m1", b"RemoteStartTransaction", remote), masked=False))] = _called(
        b"m1", b"RemoteStartTransaction", remote, connector_id=1, id_tag=b"B4F62CEF"
    )
    want[m.client(_text(_result(b"m1", _ACCEPTED), masked=True))] = _answered(
        3, b"m1", b"RemoteStartTransaction", _ACCEPTED
    )
    # A capture that starts at the 101 answer selecting ocpp1.6, a frame after it.
    a = Session(frames, 18, 49207, 9000)
    config = b'{"configurationKey":[]}'
    opening = _OCPP_ANSWER + _text(_call(b"s1", b"GetConfiguration"), masked=False)
    want[a.server(opening)] = _called(b"s1", b"GetConfiguration")
    want[a.client(_text(_result(b"s1", config), masked=True))] = _answered(
        3, b"s1", b"GetConfiguration", config
    )
    # Answers whose header block goes on in the next segment, before their
    # Sec-WebSocket-Protocol line: ocpp1.6 is selected there, or not.
    for k, chosen in enumerate((b"ocpp1.6", b"ocpp2.0.1")):
        c = Session(frames, 19 + k, 49208 + k, 9000)
        answer = _ocpp_answer(chosen)
        split = answer.index(b"Sec-WebSocket-Protocol")
        want[c.client(_OCPP_REQUEST)] = {}
        want[c.server(answer[:split])] = {}
        frame = _text(_call(b"p1", b"Heartbeat"), masked=False)
        want[c.server(answer[split:] + frame)] = (
            _called(b"p1", b"Heartbeat") if chosen == b"ocpp1.6" else {}
        )

    # A CALL retransmitted after longer than mmt-dpi's default session
    # timeout (60 s; the harness's packets are 1 s apart): the same session,
    # so a retransmission, not a new message; its answer is still linked
    # (#104).
    t = Session(frames, 22, 49222, 9000)
    want[t.client(_OCPP_REQUEST)] = {}
    want[t.server(_OCPP_ANSWER)] = {}
    first = t.server_seq
    call = _text(_call(b"r1", b"RemoteStartTransaction", remote), masked=False)
    want[t.server(call)] = _called(
        b"r1", b"RemoteStartTransaction", remote, connector_id=1, id_tag=b"B4F62CEF"
    )
    _idle(frames, want, 70)
    want[t.server(call, seq=first)] = {}
    want[t.client(_text(_result(b"r1", _ACCEPTED), masked=True))] = _answered(
        3, b"r1", b"RemoteStartTransaction", _ACCEPTED
    )

    # The capture loses a CALL's frame header: the segment after the gap
    # starts inside the frame and reports nothing; the next frame is read
    # (#104).
    g = Session(frames, 23, 49223, 9000)
    want[g.client(_OCPP_REQUEST)] = {}
    want[g.server(_OCPP_ANSWER)] = {}
    lost = _text(_call(b"l1", b"Heartbeat"), masked=False)
    g.skip_server(6)  # the 2-byte header and '[2,"'
    want[g.server(lost[6:])] = {}
    want[g.server(_text(_call(b"l2", b"Heartbeat"), masked=False))] = _called(b"l2", b"Heartbeat")
    return frames, want


def _ocpp_project(tmp_path: Path, name: str, capsys: pytest.CaptureFixture[str]) -> Path:
    """A copy of an example, built and tested with its harnesses (and both
    again with ASan and UBSan); the current directory."""
    sdk, cc = _sdk(), _cc()
    project = tmp_path / name
    shutil.copytree(EXAMPLES / name, project, ignore=shutil.ignore_patterns("build"))
    os.chdir(project)
    code, doc = _json(
        capsys, "test", "--sdk", str(sdk), "--cc", cc, "--sanitize", "--fuzz-count", "10"
    )
    assert code == 0, (doc["error"], doc["result"] and doc["result"]["packets"])
    return project


def _harness_names(project: Path) -> list[str]:
    """The attributes the project's harness reads, in its order."""
    tests = [load(p, p.name, _TYPES) for p in (project / "tests").glob("*.yaml")]
    sizes = {
        c.name: c.size or 0
        for c in resolve_profile("1.10.2", {}, None, None).profile.constants
        if c.group == DATA_TYPE_GROUP
    }
    return [n for n, _ in sorted(harness_lengths(tests, sizes).items())]


def test_the_ocpp_example_follows_its_sessions(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The OCPP example's sessions, through mmt-dpi's TCP: a session claimed
    only when its handshake offers ocpp1.6 and reported only when the answer
    selects it, answers linked to their CALL's action by UniqueId and
    direction, the 16-CALL table and its oldest entry evicted, a UniqueId
    too long to keep, typed fields by their place in the payload, a frame
    over two segments, a capture that starts after the handshake or at the
    answer, and a session longer than mmt-dpi's TCP classifies
    (examples/README.md, "OCPP 1.6-J"); with and without the sanitizers,
    then with its payloads corrupted and its frames cut short, under them."""
    sdk = _sdk()
    monkeypatch.delenv("MMT_PLUGIN_SDK_PROFILE", raising=False)
    monkeypatch.chdir(tmp_path)
    project = _ocpp_project(tmp_path, "ocpp", capsys)
    names = _harness_names(project)
    assert len(names) == 11, names
    build = project / "build"
    builds = [
        (build / "test" / "harness", build / "mmtp_ocpp_example.so"),
        (build / "test" / "harness-sanitize", build / "sanitize" / "mmtp_ocpp_example.so"),
    ]

    frames, want = _ocpp_replay()
    packets = tmp_path / "session.bin"
    harness.write_packets(packets, [harness.Record(f, frame=True) for f in frames])
    for program, plugin in builds:
        run = harness.run(program, ["check", str(packets)], plugin, sdk / "plugins", timeout=60)
        _check_replay(run, names, frames, want)

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
    o = Session(frames, 31, 49300, 9000)
    o.open()
    for i in range(3):
        ocpp_want[i] = None
    ocpp_want[o.client(_OCPP_REQUEST)] = {}
    ocpp_want[o.server(_OCPP_ANSWER)] = {}
    ocpp_want[o.client(_text(_call(b"1", b"BootNotification", _BOOT), masked=True))] = _called(
        b"1", b"BootNotification", _BOOT
    )
    ocpp_want[o.server(_text(_result(b"1", _BOOT_CONF), masked=False))] = _answered(
        3, b"1", b"BootNotification", _BOOT_CONF
    )
    ocpp_session = len(frames)
    w = Session(frames, 32, 49301, 9000)
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
