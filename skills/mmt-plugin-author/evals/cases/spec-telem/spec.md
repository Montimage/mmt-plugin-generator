# TELEM: a sensor telemetry protocol

An eval input of the mmt-plugin-author skill: the specification an agent
starts from. TELEM runs over UDP; a sensor sends to destination port 5684.

## Header

All integers are big-endian (network byte order).

| Offset | Size | Field | Meaning |
|---|---|---|---|
| 0 | 4 bits (high) | version | 1 for this version |
| 0 | 4 bits (low) | flags | bit 1: battery low; others reserved |
| 1 | 1 byte | msg_type | 1 = reading, 2 = acknowledgement |
| 2 | 2 bytes | length | the whole message, header included |
| 4 | 4 bytes | sequence | the reading's sequence number |
| 8 | length - 8 | payload | the reading; only when msg_type is 1 |

A receiver also counts, per session, the readings it has seen
(`readings`, a 32-bit counter). The counter is not in the packet.

## Examples

1. A reading, version 1, flags 2, sequence 42, payload `de ad be ef`:
   `12 01 00 0c 00 00 00 2a de ad be ef`
2. Its acknowledgement, version 1, flags 0, sequence 42, no payload:
   `10 02 00 08 00 00 00 2a`
