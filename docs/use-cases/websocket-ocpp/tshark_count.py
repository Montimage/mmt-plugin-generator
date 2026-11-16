"""Count WebSocket frames and OCPP-J messages in tshark's field output.

The reference side of docs/use-cases/websocket-ocpp.md (issue #39). Python 3,
standard library only. Read tshark's output on stdin:

    tshark -r CAPTURE -T fields -e tcp.stream -e websocket.opcode \
        -e websocket.payload.text -e http.response.code \
        -E separator=/t -E occurrence=a -E aggregator=$'\\x1e' \
        | python3 -I tshark_count.py

Options:

--list-streams FILE   also write the TCP streams tshark decoded as
                      WebSocket to FILE, one per line.
--without FILE        count only the streams not listed in FILE (run tshark
                      with -d tcp.port==80,websocket to decode the streams
                      captured without their opening handshake).

"first" counts describe the first text payload of each packet, as
ocpp_example describes the first message of each TCP segment.
"""

import argparse
import collections
import json
import sys

SEP = b"\x1e"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list-streams")
    ap.add_argument("--without")
    args = ap.parse_args()
    skip = set()
    if args.without:
        with open(args.without, "rb") as f:
            skip = {line.strip() for line in f if line.strip()}
    c: collections.Counter[str] = collections.Counter()
    streams = set()
    for line in sys.stdin.buffer:
        f = line.rstrip(b"\n").split(b"\t")
        f += [b""] * (4 - len(f))
        stream, opcodes, texts, codes = f[:4]
        if stream in skip:
            continue
        if b"101" in codes.split(SEP):
            c["101 answers"] += 1
        if not opcodes:
            continue
        streams.add(stream)
        c["packets with frames"] += 1
        for op in opcodes.split(SEP):
            c["frames"] += 1
            c[f"opcode {int(op)}"] += 1
        for i, text in enumerate(texts.split(SEP) if texts else []):
            try:
                m = json.loads(text)
            except ValueError:
                c["text, not OCPP-J"] += 1
                continue
            if not (isinstance(m, list) and m and m[0] in (2, 3, 4)):
                c["text, not OCPP-J"] += 1
                continue
            c[f"type {m[0]}"] += 1
            call = m[0] == 2 and len(m) > 2
            if call:
                c[f"CALL {m[2]}"] += 1
            if i == 0:
                c[f"first type {m[0]}"] += 1
                if call:
                    c[f"first CALL {m[2]}"] += 1
    c["streams with frames"] = len(streams)
    if args.list_streams:
        with open(args.list_streams, "wb") as f:
            f.writelines(s + b"\n" for s in sorted(streams))
    for key in sorted(c):
        print(f"{key}\t{c[key]}")


if __name__ == "__main__":
    main()
