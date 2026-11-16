#!/usr/bin/env python3
"""Write a synthetic capture of a protocol's payloads under a parent.

Part of the mmt-plugin-generator skill (``SKILL.md``, Step 1: get a
capture). Use it only when no real capture of the protocol can be found:
each payload is put behind the headers that ``--parent`` names, so that
mmt-dpi sees it as it would on the wire.

    make_pcap.py --parent udp:dport=5684 --out capture.pcap \\
        --payload "12 01 00 0c 00 00 00 2a de ad be ef" \\
        --payload "s:10 02 00 08 00 00 00 2a"
    make_pcap.py --parent tcp:port=102 --out capture.pcap --payloads-file payloads.txt

A payload is hex (spaces, colons and ``0x`` are ignored), prefixed with
``c:`` (client to server, the default) or ``s:`` (server to client). A
payloads file has one per line; empty lines and lines starting with ``#``
are skipped. ``--repeat N`` writes the whole list N times.

Parents (the selectors of ``mmt-plugin init --parent``):

- ``udp:port=N``, ``udp:dport=N``, ``udp:sport=N``: Ethernet, IPv4, UDP;
- ``tcp:port=N``, ``tcp:dport=N``, ``tcp:sport=N``: Ethernet, IPv4, then
  one TCP session: the three-way handshake, each payload in its own
  segment with the right sequence numbers and an ACK, and the FIN
  exchange;
- ``ip:proto=N``: Ethernet, IPv4 with protocol N;
- ``ipv6:proto=N``: Ethernet, IPv6 with next header N;
- ``ethernet:ethertype=N``: Ethernet with EtherType N.

The output is a classic pcap file (LINKTYPE_ETHERNET, microsecond
timestamps, 1 ms apart from ``--start``). Checksums are computed. Only the
Python standard library is used. Exit codes: 0 written, 2 bad arguments.
"""

from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

CLIENT_MAC = bytes.fromhex("020000000001")
SERVER_MAC = bytes.fromhex("020000000002")
CLIENT_IP4 = bytes([10, 0, 0, 1])
SERVER_IP4 = bytes([10, 0, 0, 2])
CLIENT_IP6 = bytes.fromhex("fd000000000000000000000000000001")
SERVER_IP6 = bytes.fromhex("fd000000000000000000000000000002")
CLIENT_PORT = 40000
TCP_FIN, TCP_SYN, TCP_PSH, TCP_ACK = 0x01, 0x02, 0x08, 0x10


class UsageError(Exception):
    """A bad argument: exit 2."""


def parse_selector(text: str) -> tuple[str, dict[str, int]]:
    proto, _, rest = text.partition(":")
    keys: dict[str, int] = {}
    for item in filter(None, rest.split(",")):
        key, sep, value = item.partition("=")
        if not sep:
            raise UsageError(f"--parent {text!r}: {item!r} is not key=value")
        try:
            keys[key] = int(value, 0)
        except ValueError as exc:
            raise UsageError(f"--parent {text!r}: {value!r} is not a number") from exc
    allowed = {
        "udp": {"port", "sport", "dport"},
        "tcp": {"port", "sport", "dport"},
        "ip": {"proto"},
        "ipv6": {"proto"},
        "ethernet": {"ethertype"},
    }
    if proto not in allowed:
        raise UsageError(f"--parent {text!r}: parent must be one of {', '.join(allowed)}")
    if set(keys) - allowed[proto]:
        raise UsageError(
            f"--parent {text!r}: {proto} keys are {', '.join(sorted(allowed[proto]))}"
        )
    if proto in ("ip", "ipv6") and "proto" not in keys:
        raise UsageError(f"--parent {text!r}: give proto=N")
    if proto == "ethernet" and "ethertype" not in keys:
        raise UsageError(f"--parent {text!r}: give ethertype=N")
    if proto in ("udp", "tcp") and not keys:
        raise UsageError(f"--parent {text!r}: give port=N, dport=N or sport=N")
    return proto, keys


def parse_payload(text: str) -> tuple[str, bytes]:
    side = "c"
    body = text.strip()
    if body[:2] in ("c:", "s:"):
        side, body = body[0], body[2:]
    clean = body.replace("0x", "").replace(":", "").replace(" ", "").replace("\t", "")
    try:
        data = bytes.fromhex(clean)
    except ValueError as exc:
        raise UsageError(f"payload {text!r} is not hex") from exc
    if not data:
        raise UsageError(f"payload {text!r} is empty")
    return side, data


def checksum(data: bytes) -> int:
    if len(data) % 2:
        data += b"\0"
    total: int = sum(struct.unpack(f"!{len(data) // 2}H", data))
    while total >> 16:
        total = (total & 0xFFFF) + (total >> 16)
    return ~total & 0xFFFF


def ethernet(src: bytes, dst: bytes, ethertype: int, payload: bytes) -> bytes:
    frame = dst + src + struct.pack("!H", ethertype) + payload
    return frame + b"\0" * max(0, 60 - len(frame))  # minimum frame, without FCS


def ipv4(src: bytes, dst: bytes, proto: int, payload: bytes, ident: int) -> bytes:
    head = struct.pack(
        "!BBHHHBBH4s4s", 0x45, 0, 20 + len(payload), ident & 0xFFFF, 0x4000, 64, proto, 0, src, dst
    )
    return head[:10] + struct.pack("!H", checksum(head)) + head[12:] + payload


def ipv6(src: bytes, dst: bytes, proto: int, payload: bytes) -> bytes:
    return struct.pack("!IHBB16s16s", 6 << 28, len(payload), proto, 64, src, dst) + payload


def l4_checksum(src: bytes, dst: bytes, proto: int, segment: bytes) -> int:
    pseudo = src + dst + struct.pack("!BBH", 0, proto, len(segment))
    return checksum(pseudo + segment)


def udp(src: bytes, dst: bytes, sport: int, dport: int, payload: bytes) -> bytes:
    seg = struct.pack("!HHHH", sport, dport, 8 + len(payload), 0) + payload
    csum = l4_checksum(src, dst, 17, seg) or 0xFFFF
    return seg[:6] + struct.pack("!H", csum) + seg[8:]


def tcp(
    src: bytes, dst: bytes, sport: int, dport: int, seq: int, ack: int, flags: int, payload: bytes
) -> bytes:
    seg = (
        struct.pack(
            "!HHIIBBHHH",
            sport,
            dport,
            seq & 0xFFFFFFFF,
            ack & 0xFFFFFFFF,
            5 << 4,
            flags,
            65535,
            0,
            0,
        )
        + payload
    )
    csum = l4_checksum(src, dst, 6, seg)
    return seg[:16] + struct.pack("!H", csum) + seg[18:]


def ports(keys: dict[str, int]) -> tuple[int, int]:
    """(client port, server port) for a udp or tcp selector."""
    if "dport" in keys or "port" in keys:
        server = keys.get("dport", keys.get("port", 0))
        return keys.get("sport", CLIENT_PORT), server
    # sport only: the client sends from that port.
    return keys["sport"], CLIENT_PORT


def frames(proto: str, keys: dict[str, int], payloads: list[tuple[str, bytes]]) -> list[bytes]:
    out: list[bytes] = []
    ident = 1

    def ip_frame(side: str, l4proto: int, body: bytes) -> bytes:
        nonlocal ident
        ident += 1
        a, b = (CLIENT_IP4, SERVER_IP4) if side == "c" else (SERVER_IP4, CLIENT_IP4)
        ma, mb = (CLIENT_MAC, SERVER_MAC) if side == "c" else (SERVER_MAC, CLIENT_MAC)
        return ethernet(ma, mb, 0x0800, ipv4(a, b, l4proto, body, ident))

    if proto == "ethernet":
        for side, data in payloads:
            ma, mb = (CLIENT_MAC, SERVER_MAC) if side == "c" else (SERVER_MAC, CLIENT_MAC)
            out.append(ethernet(ma, mb, keys["ethertype"], data))
    elif proto == "ip":
        for side, data in payloads:
            out.append(ip_frame(side, keys["proto"], data))
    elif proto == "ipv6":
        for side, data in payloads:
            a, b = (CLIENT_IP6, SERVER_IP6) if side == "c" else (SERVER_IP6, CLIENT_IP6)
            ma, mb = (CLIENT_MAC, SERVER_MAC) if side == "c" else (SERVER_MAC, CLIENT_MAC)
            out.append(ethernet(ma, mb, 0x86DD, ipv6(a, b, keys["proto"], data)))
    elif proto == "udp":
        cport, sport = ports(keys)
        for side, data in payloads:
            a, b = (CLIENT_IP4, SERVER_IP4) if side == "c" else (SERVER_IP4, CLIENT_IP4)
            pa, pb = (cport, sport) if side == "c" else (sport, cport)
            out.append(ip_frame(side, 17, udp(a, b, pa, pb, data)))
    else:  # tcp: one session
        cport, sport = ports(keys)
        seq = {"c": 1000, "s": 5000}

        def seg(side: str, flags: int, data: bytes = b"") -> bytes:
            a, b = (CLIENT_IP4, SERVER_IP4) if side == "c" else (SERVER_IP4, CLIENT_IP4)
            pa, pb = (cport, sport) if side == "c" else (sport, cport)
            other = "s" if side == "c" else "c"
            ack = seq[other] if flags & TCP_ACK else 0
            body = tcp(a, b, pa, pb, seq[side], ack, flags, data)
            seq[side] += len(data) + (1 if flags & (TCP_SYN | TCP_FIN) else 0)
            return ip_frame(side, 6, body)

        out.append(seg("c", TCP_SYN))
        out.append(seg("s", TCP_SYN | TCP_ACK))
        out.append(seg("c", TCP_ACK))
        for side, data in payloads:
            out.append(seg(side, TCP_PSH | TCP_ACK, data))
            out.append(seg("s" if side == "c" else "c", TCP_ACK))
        out.append(seg("c", TCP_FIN | TCP_ACK))
        out.append(seg("s", TCP_FIN | TCP_ACK))
        out.append(seg("c", TCP_ACK))
    return out


def write_pcap(path: Path, packets: list[bytes], start: float) -> None:
    with path.open("wb") as f:
        f.write(struct.pack("<IHHiIII", 0xA1B2C3D4, 2, 4, 0, 0, 65535, 1))
        for i, pkt in enumerate(packets):
            ts = start + i / 1000
            sec = int(ts)
            usec = round((ts - sec) * 1_000_000)
            f.write(struct.pack("<IIII", sec, usec, len(pkt), len(pkt)) + pkt)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--parent", required=True, help="the parent selector, e.g. udp:dport=5684")
    parser.add_argument("--out", required=True, type=Path, help="the pcap file to write")
    parser.add_argument(
        "--payload", action="append", default=[], help="a payload in hex; c: or s: prefix"
    )
    parser.add_argument("--payloads-file", type=Path, help="one hex payload per line")
    parser.add_argument("--repeat", type=int, default=1, help="write the payload list N times (1)")
    parser.add_argument(
        "--start", type=float, default=1_700_000_000.0, help="first timestamp, epoch seconds"
    )
    args = parser.parse_args(argv)
    try:
        texts = list(args.payload)
        if args.payloads_file:
            for line in args.payloads_file.read_text("utf-8").splitlines():
                if line.strip() and not line.lstrip().startswith("#"):
                    texts.append(line)
        if not texts:
            raise UsageError("give at least one --payload or a --payloads-file")
        if args.repeat < 1:
            raise UsageError("--repeat must be at least 1")
        proto, keys = parse_selector(args.parent)
        payloads = [parse_payload(t) for t in texts] * args.repeat
        packets = frames(proto, keys, payloads)
    except (UsageError, OSError) as exc:
        print(f"make_pcap: {exc}", file=sys.stderr)
        return 2
    write_pcap(args.out, packets, args.start)
    print(f"make_pcap: wrote {len(packets)} frames ({len(payloads)} payloads) to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
