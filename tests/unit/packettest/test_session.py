"""Session tests (#99, ``mmt_plugin.testing.session``) without an SDK: the
file format and its errors, the frames of a TCP connection (sequence and
acknowledgment numbers, retransmissions, lost bytes, the handshake, idle
traffic, checksums, padding), the check of each frame, and the corrupted
copies of ``--sanitize``."""

from __future__ import annotations

import struct
from pathlib import Path

import pytest

from mmt_plugin.sdk.profile import DATA_TYPE_GROUP, get_bundled
from mmt_plugin.testing.fuzz import mutate_frames
from mmt_plugin.testing.packets import (
    ExpectedParent,
    Observation,
    ObservedValue,
    PacketTest,
    PacketTestError,
    load,
)
from mmt_plugin.testing.session import (
    MAX_SEGMENT,
    SessionTest,
    build_frames,
    check_frame,
    load_test,
    tcp_frame,
)

SESSION = """schema: 1
id: "demo/session"
session:
  through: "tcp:dport=4433"
  protocol: "DEMO"
  proto_id: 960
  attributes:
    - name: "version"
      type: "MMT_U8_DATA"
    - name: "name"
      type: "MMT_STRING_DATA"
packets:
  - open: true
  - from: "client"
    bytes:
      - "01 02"
    expect:
      attributes:
        - name: "version"
          value: 1
  - from: "server"
    expect: "none"
  - from: "server"
    bytes:
      - "aa bb cc"
  - idle: 2
  - from: "server"
    retransmit: true
    bytes:
      - "aa bb cc"
  - from: "client"
    lost: 5
    bytes:
      - "03"
    expect:
      attributes:
        - name: "name"
          value: "61 62"
        - name: "kind"
          type: "MMT_U16_DATA"
          offset: 0
          length: 2
          value: 7
"""


def _types() -> set[str]:
    profile = get_bundled("1.10.2")
    assert profile is not None
    return {c.name for c in profile.constants if c.group == DATA_TYPE_GROUP}


def _load(tmp_path: Path, text: str) -> PacketTest | SessionTest:
    path = tmp_path / "t.yaml"
    path.write_text(text)
    return load_test(path, "tests/t.yaml", _types())


def _session(tmp_path: Path, text: str = SESSION) -> SessionTest:
    test = _load(tmp_path, text)
    assert isinstance(test, SessionTest)
    return test


def _tcp(frame: bytes) -> tuple[bytes, bytes, int, int, int, int, int, bytes]:
    """Source, destination, ports, sequence and acknowledgment numbers,
    flags and payload of a frame ``tcp_frame`` built."""
    ip = frame[14:34]
    length = struct.unpack(">H", ip[2:4])[0]
    sport, dport, seq, ack, _, flags = struct.unpack(">HHIIBB", frame[34:48])
    return ip[12:16], ip[16:20], sport, dport, seq, ack, flags, frame[54 : 14 + length]


def _checksum(data: bytes) -> int:
    if len(data) % 2:
        data += b"\0"
    total = sum(int(x) for x in struct.unpack(f">{len(data) // 2}H", data))
    while total >> 16:
        total = (total & 0xFFFF) + (total >> 16)
    return total


# --- the format ---------------------------------------------------------------------------


def test_a_session_test_loads_with_its_steps(tmp_path: Path) -> None:
    test = _session(tmp_path)
    assert (test.id, test.file, test.protocol, test.proto_id) == (
        "demo/session",
        "tests/t.yaml",
        "DEMO",
        960,
    )
    assert (test.through.text, test.server_port, test.client_port) == (
        "tcp:dport=4433",
        4433,
        49152,
    )
    assert test.attributes == (("version", "MMT_U8_DATA"), ("name", "MMT_STRING_DATA"))
    kinds = [(s.kind, s.side, s.data, s.retransmit, s.lost, s.count) for s in test.steps]
    assert kinds == [
        ("open", None, b"", False, 0, 0),
        ("segment", "client", b"\x01\x02", False, 0, 0),
        ("segment", "server", b"", False, 0, 0),
        ("segment", "server", b"\xaa\xbb\xcc", False, 0, 0),
        ("idle", None, b"", False, 0, 2),
        ("segment", "server", b"\xaa\xbb\xcc", True, 0, 0),
        ("segment", "client", b"\x03", False, 5, 0),
    ]
    # The type comes from session.attributes; an unlisted one gives its own.
    last = test.steps[-1].expect
    assert last is not None
    assert [(a.name, a.type, a.value, a.length) for a in last] == [
        ("name", "MMT_STRING_DATA", "61 62", None),
        ("kind", "MMT_U16_DATA", 7, 2),
    ]
    assert test.steps[2].expect is None and test.steps[3].expect == ()
    # Every attribute the harness reads: the session's, then each packet's.
    names = [a.name for a in test.named_attributes]
    assert names == ["version", "name", "version", "name", "kind"]


def test_a_packet_test_still_loads_and_load_rejects_a_session_test(tmp_path: Path) -> None:
    packet = (
        'schema: 1\nid: "demo/basic"\nbytes:\n  - "01"\nexpect:\n  protocol: "DEMO"\n'
        '  proto_id: 960\n  next:\n    kind: "none"\n'
    )
    assert isinstance(_load(tmp_path, packet), PacketTest)
    (tmp_path / "s.yaml").write_text(SESSION)
    with pytest.raises(PacketTestError, match="a session test"):
        load(tmp_path / "s.yaml", "s.yaml", _types())


@pytest.mark.parametrize(
    ("old", "new", "message"),
    [
        ('  through: "tcp:dport=4433"', '  through: "udp:dport=4433"', "runs over tcp"),
        # A misspelt key would turn the absent-attribute check off (#124).
        ("\n  attributes:\n", "\n  atributes:\n", "session: unknown key 'atributes'"),
        ("  proto_id: 960\n", "  proto_id: 960\n  bytes: []\n", "session: unknown key 'bytes'"),
        ('  through: "tcp:dport=4433"', '  through: "tcp:sport=1"', "server's port"),
        ('  through: "tcp:dport=4433"', '  through: "tcp:dport=70000"', "is not a number"),
        ("  proto_id: 960\n", "", "missing key 'proto_id'"),
        ('      type: "MMT_U8_DATA"\n', '      type: "MMT_NOPE"\n', "not a data type"),
        ('    - name: "name"\n', '    - name: "version"\n', "listed twice"),
        ("  - open: true\n", "  - open: false\n", "open must be true"),
        ("  - open: true\n", '  - open: true\n    from: "client"\n', "no other key"),
        ("  - idle: 2\n", "  - idle: 0\n", "idle is a number of seconds"),
        ('  - from: "server"\n    expect', '  - from: "nobody"\n    expect', "client or server"),
        ("    lost: 5\n", "    lost: -1\n", "lost is a number"),
        ("    lost: 5\n", "    lost: 5\n    retransmit: true\n", "give retransmit or lost"),
        ("    lost: 5\n", "    back: -1\n", "back is a number"),
        ("    lost: 5\n", "    back: true\n", "back is a number"),
        ("    lost: 5\n", "    lost: 5\n    back: 1\n", "give one of retransmit, lost and back"),
        ("    lost: 5\n", "    back: 3\n", "the client has sent or lost only 2 bytes"),
        ('    expect: "none"\n', '    expect: "maybe"\n', 'expect is "none"'),
        ('    expect: "none"\n', "    flags: 1\n", "unknown key 'flags'"),
        ('      - "01 02"\n', '      - "01 0G"\n', "hex pairs"),
        (
            "          value: 1\n",
            '          type: "MMT_U16_DATA"\n          value: 1\n',
            "lists it",
        ),
        ("          value: 1\n", "", "missing key 'value'"),
        ("packets:\n", 'bytes:\n  - "01"\npackets:\n', "has no 'bytes'"),
    ],
)
def test_a_bad_session_test_is_a_bad_packet_test(
    tmp_path: Path, old: str, new: str, message: str
) -> None:
    assert old in SESSION
    with pytest.raises(PacketTestError, match=message) as exc:
        _load(tmp_path, SESSION.replace(old, new, 1))
    assert exc.value.diagnostic.code == "model.bad-packet-test"
    assert exc.value.diagnostic.location is not None
    assert exc.value.diagnostic.location.file == "tests/t.yaml"


def test_a_session_note_is_a_comment(tmp_path: Path) -> None:
    text = SESSION.replace("  proto_id: 960\n", '  proto_id: 960\n  note: "a comment"\n', 1)
    test = _load(tmp_path, text)
    assert isinstance(test, SessionTest)
    assert test.attributes == _session(tmp_path).attributes


def _one_segment(size: int) -> str:
    """SESSION's connection with one client segment of ``size`` bytes."""
    chunk = " ".join(["00"] * size)
    return SESSION[: SESSION.index("packets:")] + (
        f'packets:\n  - open: true\n  - from: "client"\n    bytes:\n      - "{chunk}"\n'
    )


def test_a_segment_fits_one_ipv4_tcp_frame(tmp_path: Path) -> None:
    # An IPv4 packet is at most 65535 bytes, 40 of them the IPv4 and TCP headers.
    assert MAX_SEGMENT == 65495
    test = _load(tmp_path, _one_segment(MAX_SEGMENT))
    assert isinstance(test, SessionTest)
    frame = build_frames(test)[-1]
    assert len(frame.payload) == MAX_SEGMENT
    assert struct.unpack(">H", frame.frame[16:18])[0] == 65535
    # One byte more is a bad packet test, not a struct.error when the frames
    # are built (#124).
    with pytest.raises(PacketTestError) as exc:
        _load(tmp_path, _one_segment(MAX_SEGMENT + 1))
    diagnostic = exc.value.diagnostic
    assert diagnostic.code == "model.bad-packet-test"
    assert diagnostic.message == (
        "packets[1]: the segment has 65496 bytes; one IPv4/TCP frame carries at most 65495"
    )
    assert diagnostic.location is not None
    assert diagnostic.location.file == "tests/t.yaml"


def test_a_retransmission_needs_data_sent_before_it(tmp_path: Path) -> None:
    text = SESSION.replace('  - from: "server"\n    bytes:\n      - "aa bb cc"\n  - idle: 2\n', "")
    with pytest.raises(PacketTestError, match="the server sent no data before it"):
        _load(tmp_path, text)


def _late(steps: str) -> str:
    """SESSION's connection with the client steps ``steps`` instead of its packets."""
    return SESSION[: SESSION.index("packets:")] + "packets:\n  - open: true\n" + steps


def test_a_segment_sent_back_has_bytes_that_end_by_the_next_sequence_number(
    tmp_path: Path,
) -> None:
    sent = '  - from: "client"\n    bytes:\n      - "01 02 03"\n'
    with pytest.raises(PacketTestError, match="a segment sent back has bytes"):
        _load(tmp_path, _late(sent + '  - from: "client"\n    back: 2\n'))
    with pytest.raises(PacketTestError, match="sent back 2 bytes has at most 2 bytes"):
        _load(
            tmp_path,
            _late(sent + '  - from: "client"\n    back: 2\n    bytes:\n      - "02 03 04"\n'),
        )
    # Bytes lost count: a segment can be sent back into them.
    test = _session(
        tmp_path,
        _late(
            '  - from: "client"\n    lost: 4\n    bytes:\n      - "05"\n'
            '  - from: "client"\n    back: 5\n    bytes:\n      - "01 02"\n'
        ),
    )
    assert [s.back for s in test.steps] == [0, 0, 5]
    # The server's bytes are not the client's.
    with pytest.raises(PacketTestError, match="the server has sent or lost only 0 bytes"):
        _load(
            tmp_path, _late(sent + '  - from: "server"\n    back: 1\n    bytes:\n      - "01"\n')
        )


def test_a_session_needs_packets(tmp_path: Path) -> None:
    text = SESSION[: SESSION.index("packets:")] + "packets: []\n"
    with pytest.raises(PacketTestError, match="at least one packet"):
        _load(tmp_path, text)


# --- the frames ---------------------------------------------------------------------------


def test_the_frames_follow_one_tcp_connection(tmp_path: Path) -> None:
    frames = build_frames(_session(tmp_path))
    client, server = bytes([198, 18, 0, 1]), bytes([192, 0, 2, 1])
    seen = [_tcp(f.frame) for f in frames]
    syn, ack, psh = 0x02, 0x10, 0x08
    assert [f.step for f in frames] == [0, 0, 0, 1, 2, 3, 4, 4, 5, 6]
    assert seen[:4] == [
        (client, server, 49152, 4433, 1000, 500000, syn, b""),
        (server, client, 4433, 49152, 500000, 1001, syn | ack, b""),
        (client, server, 49152, 4433, 1001, 500001, ack, b""),
        (client, server, 49152, 4433, 1001, 500001, psh | ack, b"\x01\x02"),
    ]
    assert seen[4] == (server, client, 4433, 49152, 500001, 1003, ack, b"")  # a pure ACK
    assert seen[5] == (server, client, 4433, 49152, 500001, 1003, psh | ack, b"\xaa\xbb\xcc")
    # Idle traffic: another connection, one pure ACK a second.
    idle = bytes([198, 18, 0, 2])
    assert [s[:4] for s in seen[6:8]] == [(idle, server, 40000, 7)] * 2
    # The retransmission repeats the server's last segment; lost bytes skip.
    assert seen[8] == seen[5]
    assert seen[9] == (client, server, 49152, 4433, 1008, 500004, psh | ack, b"\x03")
    # Only the plugin's packets have expectations; open, idle and "none" are not its.
    assert [f.expect is None for f in frames] == [True] * 3 + [False, True, False] + [
        True,
        True,
        False,
        False,
    ]
    assert [f.payload for f in frames][3] == b"\x01\x02"


def test_a_segment_sent_back_arrives_late_without_moving_the_sequence(tmp_path: Path) -> None:
    # "<!DOC" and "TYPE" in reverse order: TYPE first (the 5 bytes before
    # it lost so far), a filler over the hole, "<!DOC" in it, then more.
    test = _session(
        tmp_path,
        _late(
            '  - from: "client"\n    bytes:\n      - "61 62"\n'
            '  - from: "client"\n    lost: 5\n    bytes:\n      - "54 59 50 45"\n'
            '  - from: "client"\n    back: 9\n    bytes:\n      - "78 78 78"\n'
            '  - from: "client"\n    back: 9\n    bytes:\n      - "3c 21 44 4f 43"\n'
            '  - from: "server"\n    bytes:\n      - "aa"\n'
            '  - from: "client"\n    retransmit: true\n    bytes:\n      - "54 59 50 45"\n'
            '  - from: "client"\n    bytes:\n      - "20"\n'
        ),
    )
    seen = [_tcp(f.frame) for f in build_frames(test)][3:]
    assert [(s[4], s[7]) for s in seen if s[0] == bytes([198, 18, 0, 1])] == [
        (1001, b"ab"),
        (1008, b"TYPE"),
        (1003, b"xxx"),
        (1003, b"<!DOC"),
        (1008, b"TYPE"),  # a retransmission repeats the last segment in order
        (1012, b" "),
    ]
    # The server acknowledges up to the client's next sequence number.
    assert seen[4][4:6] == (500001, 1012)


def test_every_frame_has_right_checksums_and_ethernet_padding(tmp_path: Path) -> None:
    for f in build_frames(_session(tmp_path)):
        frame = f.frame
        assert len(frame) >= 60 and frame[12:14] == b"\x08\x00"
        ip = frame[14:34]
        assert _checksum(ip) == 0xFFFF
        length = struct.unpack(">H", ip[2:4])[0]
        segment = frame[34 : 14 + length]
        pseudo = ip[12:20] + struct.pack(">BBH", 0, 6, len(segment))
        assert _checksum(pseudo + segment) == 0xFFFF
        assert frame[14 + length :] == bytes(len(frame) - 14 - length)
    assert len(tcp_frame(bytes(4), bytes(4), 1, 2, 3, 4, 0x10, b"x" * 20)) == 74


def test_a_selector_sport_is_the_clients_port(tmp_path: Path) -> None:
    test = _session(tmp_path, SESSION.replace("tcp:dport=4433", "tcp:port=80,sport=1234"))
    assert (test.server_port, test.client_port) == (80, 1234)
    assert _tcp(build_frames(test)[0].frame)[2:4] == (1234, 80)


# --- the check ----------------------------------------------------------------------------

TCP = ExpectedParent("tcp", 354, 54)


def _observed(index: int | None, **values: ObservedValue) -> Observation:
    return Observation(index, None, None, values, 54 if index else None, 354 if index else None)


def test_a_frame_is_checked_with_the_sessions_attributes_absent(tmp_path: Path) -> None:
    test = _session(tmp_path)
    frames = build_frames(test)
    plugin = (960, "DEMO")
    absent = ObservedValue("absent", "MMT_STRING_DATA")
    ok = _observed(4, version=ObservedValue("int", "MMT_U8_DATA", 1), name=absent)
    assert check_frame(test, frames[3], ok, plugin, TCP) == ([], 2)
    # An attribute the session lists that the packet does not must be absent.
    named = _observed(
        4,
        version=ObservedValue("int", "MMT_U8_DATA", 1),
        name=ObservedValue("hex", "MMT_STRING_DATA", data=b"ab"),
    )
    failures, _ = check_frame(test, frames[3], named, plugin, TCP)
    assert [f.to_json() for f in failures] == [
        {"attribute": "name", "expected": "absent", "actual": "61 62", "packet": 1}
    ]
    # Not classified, under another parent, or the plugin's where it must not be.
    failures, _ = check_frame(test, frames[3], _observed(None), plugin, TCP)
    assert [(f.attribute, f.actual, f.packet) for f in failures] == [
        ("<protocol>", "not classified", 1)
    ]
    moved = Observation(4, None, None, ok.values, 42, 376)
    failures, _ = check_frame(test, frames[3], moved, plugin, TCP, {376: "udp"})
    assert [(f.attribute, f.expected, f.actual) for f in failures] == [
        ("<parent>", "tcp at offset 54", "udp at offset 42")
    ]
    assert check_frame(test, frames[0], _observed(None), plugin, TCP) == ([], 0)
    failures, _ = check_frame(test, frames[4], ok, plugin, TCP)
    assert [f.to_json() for f in failures] == [
        {
            "attribute": "<protocol>",
            "expected": "not classified",
            "actual": "DEMO (960)",
            "packet": 2,
        }
    ]


def test_corrupted_copies_are_seeded_and_keep_the_lower_layers(tmp_path: Path) -> None:
    frames = [f.frame for f in build_frames(_session(tmp_path))]
    one = mutate_frames(7, "demo/session", 1, frames, 54)
    assert one == mutate_frames(7, "demo/session", 1, frames, 54)
    assert one != mutate_frames(7, "demo/session", 2, frames, 54)
    assert one != mutate_frames(8, "demo/session", 1, frames, 54)
    assert len(one) == len(frames)
    assert all(m[:54] == f[:54] and len(m) <= len(f) for m, f in zip(one, frames, strict=True))
    many = [m for c in range(1, 40) for m in mutate_frames(0, "x", c, frames, 54)]
    assert any(len(m) < 60 for m in many)  # some cut short
