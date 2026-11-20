"""Session tests: several packets of one TCP connection, run in order in one
harness process, so that a plugin's session state (an opening handshake, a
message over two segments, an answer linked to its request) is tested
(``tests/corpus/README.md``, "Session files"; #99).

A session test is a schema 1 file with ``session`` instead of ``bytes`` and
``expect``: the connection (``session.through``, a ``tcp`` selector with
the server's port, ``dport`` or ``port``, and optionally the client's,
``sport``), the plugin's ``protocol`` and ``proto_id``, the
``attributes`` every packet of the plugin's checks (one a packet does not
list must be absent), and ``packets``, its steps, in order:

- ``open: true``: the three-way handshake (SYN, SYN/ACK, ACK);
- ``idle: N``: ``N`` seconds of other TCP traffic (the harness's packets
  are one second apart), one pure ACK of another connection a second;
- ``from: client`` or ``from: server``: one segment of that side, its
  payload ``bytes`` (none: a pure ACK), with the sequence and
  acknowledgment numbers of a connection without loss; ``retransmit: true``
  sends it again at the sequence number of that side's previous segment
  with data, ``lost: N`` loses that side's next ``N`` bytes before it (the
  capture never had them), ``back: N`` sends it ``N`` bytes before that
  side's next sequence number without moving it (a segment that arrives
  late, after the ones that followed it, or one that overlaps bytes
  already sent; it ends at or before that number). ``expect`` is ``"none"`` (not the plugin's
  packet) or a mapping with ``attributes``, as a packet test's (``offset``
  and ``length`` optional, ``type`` too for an attribute
  ``session.attributes`` lists); without ``expect``, the packet is the
  plugin's and every attribute of ``session.attributes`` is absent.

The packets of ``open`` and ``idle`` steps must not be the plugin's. Every
packet of the plugin's must be classified directly above TCP, where the
TCP header ends (``<parent>``); the next protocol is not checked.

``load_test(path, shown, data_types)`` reads a packet test or a session
test. ``build_frames(test)`` returns the Ethernet frames of a session test
with the step and the expectation of each; ``check_frame`` checks one
harness observation against it.
"""

from __future__ import annotations

import struct
from collections.abc import Collection, Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mmt_plugin.testing.frames import PluginParent, Through, parse_through
from mmt_plugin.testing.packets import (
    PROTOCOL,
    ExpectedAttribute,
    ExpectedNext,
    ExpectedParent,
    Failure,
    Observation,
    PacketTest,
    attribute,
    check,
    error,
    hex_bytes,
    load_doc,
    need,
    read_doc,
)

__all__ = [
    "CLIENT_PORT",
    "Connection",
    "SessionFrame",
    "SessionStep",
    "SessionTest",
    "build_frames",
    "check_frame",
    "load_test",
    "tcp_frame",
]

#: The client's port when the selector gives no ``sport``.
CLIENT_PORT = 49152
#: The longest ``idle`` step, in seconds.
MAX_IDLE = 3600

_MAC_CLIENT = bytes.fromhex("020000000001")
_MAC_SERVER = bytes.fromhex("020000000002")
#: The server (RFC 5737), the client and the idle traffic's client (RFC 2544).
SERVER = bytes([192, 0, 2, 1])
CLIENT = bytes([198, 18, 0, 1])
_IDLE_CLIENT = bytes([198, 18, 0, 2])
_IDLE_PORTS = (40000, 7)
_SYN, _ACK, _PSH = 0x02, 0x10, 0x08
#: The shortest Ethernet frame without its FCS (IEEE 802.3).
_MIN_FRAME = 60
_SIDES = ("client", "server")
_SEGMENT_KEYS = {
    "from",
    "bytes",
    "retransmit",
    "lost",
    "back",
    "expect",
    "summary",
    "note",
    "text",
}


def _checksum(data: bytes) -> int:
    """The Internet checksum (RFC 1071)."""
    if len(data) % 2:
        data += b"\0"
    total = sum(int(x) for x in struct.unpack(f">{len(data) // 2}H", data))
    while total >> 16:
        total = (total & 0xFFFF) + (total >> 16)
    return ~total & 0xFFFF


def tcp_frame(
    src: bytes, dst: bytes, sport: int, dport: int, seq: int, ack: int, flags: int, data: bytes
) -> bytes:
    """An Ethernet frame of one IPv4 TCP segment (a 20-byte header, every
    checksum right); a frame shorter than 60 bytes gets Ethernet padding, as
    on the wire, so that only the IPv4 length says where the segment ends."""
    header = struct.pack(
        ">HHIIBBHHH", sport, dport, seq & 0xFFFFFFFF, ack & 0xFFFFFFFF, 5 << 4, flags, 65535, 0, 0
    )
    pseudo = src + dst + struct.pack(">BBH", 0, 6, len(header) + len(data))
    checksum = _checksum(pseudo + header + data)
    segment = header[:16] + struct.pack(">H", checksum) + header[18:] + data
    ip = struct.pack(">BBHHHBBH4s4s", 0x45, 0, 20 + len(segment), 1, 0x4000, 64, 6, 0, src, dst)
    ip = ip[:10] + struct.pack(">H", _checksum(ip)) + ip[12:]
    mac_dst, mac_src = (_MAC_SERVER, _MAC_CLIENT) if dst == SERVER else (_MAC_CLIENT, _MAC_SERVER)
    frame = mac_dst + mac_src + b"\x08\x00" + ip + segment
    return frame + bytes(max(0, _MIN_FRAME - len(frame)))


class Connection:
    """One TCP connection between ``client`` (an address and a port) and
    the server 192.0.2.1, whose frames it appends to ``frames`` (a list
    several connections may share): ``open()`` adds the three-way
    handshake, ``client(data)`` and ``server(data)`` a segment of each side
    (a pure ACK without data), with the sequence and acknowledgment numbers
    of a connection without loss; ``seq=`` sends a segment at another
    sequence number (a retransmission), ``skip_client`` and ``skip_server``
    lose bytes."""

    def __init__(
        self,
        frames: list[bytes],
        client: bytes,
        client_port: int,
        server_port: int,
        *,
        client_seq: int = 1000,
        server_seq: int = 500000,
    ) -> None:
        self.client_ip = client
        self.client_port = client_port
        self.server_port = server_port
        self.client_seq = client_seq
        self.server_seq = server_seq
        self.frames = frames

    def _send(self, from_client: bool, data: bytes, flags: int, seq: int | None) -> int:
        if from_client:
            first = self.client_seq if seq is None else seq
            frame = tcp_frame(
                self.client_ip,
                SERVER,
                self.client_port,
                self.server_port,
                first,
                self.server_seq,
                flags,
                data,
            )
        else:
            first = self.server_seq if seq is None else seq
            frame = tcp_frame(
                SERVER,
                self.client_ip,
                self.server_port,
                self.client_port,
                first,
                self.client_seq,
                flags,
                data,
            )
        self.frames.append(frame)
        return len(self.frames) - 1

    def open(self) -> None:
        """SYN, SYN/ACK, ACK (RFC 9293 section 3.5); each SYN takes a sequence number."""
        self._send(True, b"", _SYN, None)
        self.client_seq += 1
        self._send(False, b"", _SYN | _ACK, None)
        self.server_seq += 1
        self._send(True, b"", _ACK, None)

    def client(self, data: bytes = b"", seq: int | None = None) -> int:
        """A segment from the client; its index in the frames."""
        index = self._send(True, data, _PSH | _ACK if data else _ACK, seq)
        if seq is None:
            self.client_seq += len(data)
        return index

    def server(self, data: bytes = b"", seq: int | None = None) -> int:
        """A segment from the server; its index in the frames."""
        index = self._send(False, data, _PSH | _ACK if data else _ACK, seq)
        if seq is None:
            self.server_seq += len(data)
        return index

    def skip_client(self, count: int) -> None:
        """Lose the client's next ``count`` bytes: the capture never has them."""
        self.client_seq += count

    def skip_server(self, count: int) -> None:
        """Lose the server's next ``count`` bytes: the capture never has them."""
        self.server_seq += count


@dataclass(frozen=True)
class SessionStep:
    """One step of ``packets``: ``kind`` is ``open``, ``idle`` (``count``
    seconds) or ``segment`` (``side``, ``data``, ``retransmit``, ``lost``,
    ``back``);
    ``expect`` is ``None`` for a packet that must not be the plugin's, else
    the attributes it lists."""

    kind: str
    side: str | None = None
    data: bytes = b""
    retransmit: bool = False
    lost: int = 0
    count: int = 0
    back: int = 0
    expect: tuple[ExpectedAttribute, ...] | None = None


@dataclass(frozen=True)
class SessionTest:
    """A session test: its ``id``, the ``file`` it came from (as shown),
    its connection (``through``), the plugin's ``protocol`` and
    ``proto_id``, the ``attributes`` every packet of the plugin's checks,
    and its ``steps``."""

    id: str
    file: str
    through: Through
    protocol: str
    proto_id: int
    attributes: tuple[tuple[str, str], ...]
    steps: tuple[SessionStep, ...]

    @property
    def named_attributes(self) -> Iterable[ExpectedAttribute]:
        """Every attribute the test names (what the harness must read)."""
        for name, type_name in self.attributes:
            yield ExpectedAttribute(name, type_name, "absent", None, None)
        for step in self.steps:
            yield from step.expect or ()

    @property
    def server_port(self) -> int:
        port = self.through.key("dport")
        if port is None:
            port = self.through.key("port")
        assert port is not None  # load_test requires it
        return port

    @property
    def client_port(self) -> int:
        port = self.through.key("sport")
        return CLIENT_PORT if port is None else port


def load_test(
    path: Path,
    shown: str,
    data_types: Collection[str],
    plugins: Mapping[str, PluginParent] | None = None,
) -> PacketTest | SessionTest:
    """Read the packet test or the session test at ``path`` (``shown`` names
    it in diagnostics); ``data_types`` are the SDK profile's data type names,
    ``plugins`` the plugin parents a packet test's ``through`` may name."""
    doc = read_doc(path, shown)
    if "session" not in doc:
        return load_doc(doc, shown, data_types, plugins)
    return _load_session(doc, shown, data_types)


def _load_session(doc: Mapping[str, Any], shown: str, data_types: Collection[str]) -> SessionTest:
    for key in ("bytes", "expect", "through"):
        if key in doc:
            raise error(shown, f"a session test has no {key!r}: its packets are in 'packets'")
    test_id = need(shown, "the test", doc, "id", str)
    session = need(shown, "the test", doc, "session", dict)
    text = need(shown, "session", session, "through", str)
    try:
        through = parse_through(text)
    except ValueError as exc:
        raise error(shown, f"session.through: {exc}") from None
    if through.proto != "tcp":
        raise error(shown, f"session.through: {text!r}: a session test runs over tcp")
    if through.key("dport") is None and through.key("port") is None:
        raise error(shown, f"session.through: {text!r}: give the server's port, tcp:dport=N")
    protocol = need(shown, "session", session, "protocol", str)
    proto_id = need(shown, "session", session, "proto_id", int)
    listed = session.get("attributes", [])
    if not isinstance(listed, list):
        raise error(shown, "session: 'attributes' must be a list")
    known: dict[str, str] = {}
    for i, item in enumerate(listed):
        where = f"session.attributes[{i}]"
        if not isinstance(item, dict):
            raise error(shown, f"{where}: must be a mapping")
        name = need(shown, where, item, "name", str)
        type_name = need(shown, where, item, "type", str)
        if type_name not in data_types:
            raise error(
                shown, f"{where} ({name}): {type_name!r} is not a data type of the SDK profile"
            )
        if name in known:
            raise error(shown, f"session.attributes: {name!r} is listed twice")
        # The name's form is checked as an expected attribute's.
        attribute(shown, where, {"name": name, "type": type_name, "status": "absent"}, data_types)
        known[name] = type_name
    raw = need(shown, "the test", doc, "packets", list)
    if not raw:
        raise error(shown, "packets: a session test has at least one packet")
    steps = tuple(_step(shown, i, item, data_types, known) for i, item in enumerate(raw))
    sent = {"client": False, "server": False}
    stream = {"client": 0, "server": 0}  # the bytes of each side's sequence space so far
    for i, step in enumerate(steps):
        if step.kind != "segment":
            continue
        assert step.side is not None
        if step.retransmit and not sent[step.side]:
            raise error(
                shown, f"packets[{i}]: retransmit, but the {step.side} sent no data before it"
            )
        if step.back > stream[step.side]:
            raise error(
                shown,
                f"packets[{i}]: back is {step.back}, but the {step.side} has sent or lost "
                f"only {stream[step.side]} bytes before it",
            )
        sent[step.side] = sent[step.side] or bool(step.data)
        if not step.retransmit and not step.back:
            stream[step.side] += step.lost + len(step.data)
    return SessionTest(test_id, shown, through, protocol, proto_id, tuple(known.items()), steps)


def _step(
    shown: str, i: int, item: object, data_types: Collection[str], known: Mapping[str, str]
) -> SessionStep:
    where = f"packets[{i}]"
    if not isinstance(item, dict):
        raise error(shown, f"{where}: must be a mapping")
    if "open" in item or "idle" in item:
        kind = "open" if "open" in item else "idle"
        if len(item) != 1:
            raise error(shown, f"{where}: an {kind} step has no other key")
        if kind == "open":
            if item["open"] is not True:
                raise error(shown, f"{where}: open must be true")
            return SessionStep("open")
        seconds = need(shown, where, item, "idle", int)
        if not 1 <= seconds <= MAX_IDLE:
            raise error(shown, f"{where}: idle is a number of seconds from 1 to {MAX_IDLE}")
        return SessionStep("idle", count=seconds)
    unknown = sorted(set(item) - _SEGMENT_KEYS)
    if unknown:
        raise error(
            shown,
            f"{where}: unknown key {unknown[0]!r} (a step is open, idle, or from with bytes)",
        )
    side = need(shown, where, item, "from", str)
    if side not in _SIDES:
        raise error(shown, f"{where}: from must be client or server")
    chunks = item.get("bytes", [])
    if not isinstance(chunks, list):
        raise error(shown, f"{where}: 'bytes' must be a list")
    data = b"".join(hex_bytes(shown, f"{where}.bytes[{k}]", c) for k, c in enumerate(chunks))
    retransmit = item.get("retransmit", False)
    if not isinstance(retransmit, bool):
        raise error(shown, f"{where}: retransmit must be true or false")
    lost = item.get("lost", 0)
    if not isinstance(lost, int) or isinstance(lost, bool) or lost < 0:
        raise error(shown, f"{where}: lost is a number of bytes, 0 or more")
    if retransmit and lost:
        raise error(shown, f"{where}: a retransmission loses no bytes: give retransmit or lost")
    back = item.get("back", 0)
    if not isinstance(back, int) or isinstance(back, bool) or back < 0:
        raise error(shown, f"{where}: back is a number of bytes, 0 or more")
    if back and (retransmit or lost):
        raise error(shown, f"{where}: give one of retransmit, lost and back")
    if back and not data:
        raise error(shown, f"{where}: a segment sent back has bytes")
    if len(data) > back > 0:
        raise error(
            shown,
            f"{where}: a segment sent back {back} bytes has at most {back} bytes "
            "(it ends at or before the side's next sequence number)",
        )
    expect = item.get("expect", {})
    attributes: tuple[ExpectedAttribute, ...] | None
    if expect == "none":
        attributes = None
    elif isinstance(expect, dict):
        unknown = sorted(set(expect) - {"attributes", "note"})
        if unknown:
            raise error(shown, f"{where}.expect: unknown key {unknown[0]!r}")
        items = expect.get("attributes", [])
        if not isinstance(items, list):
            raise error(shown, f"{where}.expect: 'attributes' must be a list")
        attributes = tuple(
            attribute(shown, f"{where}.expect.attributes[{k}]", a, data_types, known)
            for k, a in enumerate(items)
        )
        names = [a.name for a in attributes]
        duplicate = next((n for n in names if names.count(n) > 1), None)
        if duplicate is not None:
            raise error(shown, f"{where}.expect.attributes: {duplicate!r} is listed twice")
    else:
        raise error(shown, f'{where}: expect is "none" or a mapping with attributes')
    return SessionStep("segment", side, data, retransmit, lost, expect=attributes, back=back)


@dataclass(frozen=True)
class SessionFrame:
    """One frame of a session test's run: the whole Ethernet ``frame``, its
    TCP ``payload``, the ``step`` it comes from, and what it must be:
    ``expect`` is ``None`` when it must not be the plugin's packet."""

    frame: bytes
    payload: bytes
    step: int
    expect: tuple[ExpectedAttribute, ...] | None


def build_frames(test: SessionTest) -> list[SessionFrame]:
    """The frames of ``test``, in order."""
    frames: list[bytes] = []
    idle_frames: list[bytes] = []
    conn = Connection(frames, CLIENT, test.client_port, test.server_port)
    idle = Connection(idle_frames, _IDLE_CLIENT, *_IDLE_PORTS)
    last = {"client": conn.client_seq, "server": conn.server_seq}
    out: list[SessionFrame] = []

    def add(frame: bytes, payload: bytes, step: int, expect: Any) -> None:
        out.append(SessionFrame(frame, payload, step, expect))

    for i, step in enumerate(test.steps):
        if step.kind == "open":
            start = len(frames)
            conn.open()
            last = {"client": conn.client_seq, "server": conn.server_seq}
            for frame in frames[start:]:
                add(frame, b"", i, None)
        elif step.kind == "idle":
            for _ in range(step.count):
                idle.client()
                add(idle_frames[-1], b"", i, None)
        else:
            assert step.side is not None
            client = step.side == "client"
            if step.lost:
                (conn.skip_client if client else conn.skip_server)(step.lost)
            seq = last[step.side] if step.retransmit else None
            if step.back:
                seq = (conn.client_seq if client else conn.server_seq) - step.back
            elif not step.retransmit and step.data:
                last[step.side] = conn.client_seq if client else conn.server_seq
            (conn.client if client else conn.server)(step.data, seq)
            add(frames[-1], step.data, i, step.expect)
    return out


def check_frame(
    test: SessionTest,
    frame: SessionFrame,
    observed: Observation,
    plugin: tuple[int, str],
    parent: ExpectedParent,
    names: Mapping[int, str] | None = None,
) -> tuple[list[Failure], int]:
    """The failures of one frame of ``test`` given what the harness
    ``observed``, each with its step, and the attributes checked."""
    pid, name = plugin
    if frame.expect is None:
        if observed.index is None:
            return [], 0
        return [Failure(PROTOCOL, "not classified", f"{name} ({pid})", frame.step)], 0
    listed = {a.name for a in frame.expect}
    absent = tuple(
        ExpectedAttribute(n, t, "absent", None, None)
        for n, t in test.attributes
        if n not in listed
    )
    expected = PacketTest(
        test.id,
        test.file,
        frame.payload,
        test.protocol,
        test.proto_id,
        ExpectedNext("hook"),
        (*frame.expect, *absent),
    )
    failures, checked = check(expected, observed, plugin, parent, names)
    return [Failure(f.attribute, f.expected, f.actual, frame.step) for f in failures], checked
