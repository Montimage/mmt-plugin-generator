# TELEM: a sensor telemetry protocol, revision 2

An eval input of the mmt-plugin-generator skill: the revised specification an
agent updates an existing plugin project to. `project/` is that project,
written from revision 1 ([`../spec-telem/spec.md`](../spec-telem/spec.md)).
Revision 2 adds one message type, the status report; everything revision 1
says still holds, and the version field stays 1.

TELEM runs over UDP; a sensor sends to destination port 5684.

## Header

All integers are big-endian (network byte order).

| Offset | Size | Field | Meaning |
|---|---|---|---|
| 0 | 4 bits (high) | version | 1 for this version |
| 0 | 4 bits (low) | flags | bit 1: battery low; others reserved |
| 1 | 1 byte | msg_type | 1 = reading, 2 = acknowledgement, 3 = status (new in revision 2) |
| 2 | 2 bytes | length | the whole message, header included |
| 4 | 4 bytes | sequence | the reading's sequence number |
| 8 | length - 8 | payload | the reading; only when msg_type is 1 |
| 8 | 1 byte | battery | the battery charge, in percent; only when msg_type is 3 (new in revision 2) |

A status report is 9 bytes long: the header and `battery`.

A receiver also counts, per session, the readings it has seen
(`readings`, a 32-bit counter). The counter is not in the packet.

## Examples

1. A reading, version 1, flags 2, sequence 42, payload `de ad be ef`:
   `12 01 00 0c 00 00 00 2a de ad be ef`
2. Its acknowledgement, version 1, flags 0, sequence 42, no payload:
   `10 02 00 08 00 00 00 2a`
3. A status report (new in revision 2), version 1, flags 2 (battery low),
   sequence 43, battery 15 %, no payload:
   `12 03 00 09 00 00 00 2b 0f`
