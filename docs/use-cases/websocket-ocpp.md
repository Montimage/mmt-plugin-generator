# Use case: WebSocket and OCPP 1.6-J

Issue #39 used two real protocols, WebSocket (RFC 6455) and OCPP 1.6-J
(OCPP 1.6 over WebSocket), to try the new workflow end to end. Both plugins
were written with `mmt-plugin` only: `examples/websocket` (#40, PR #94) and
`examples/ocpp` (#41, PR #95), described in
[`examples/README.md`](../../examples/README.md#websocket). This page
records which steps of the workflow were used, how the two plugins compare
with tshark on the four attack captures of the *Federated OCPP 1.6
Intrusion Detection Dataset*, the answers to the issue's five open
questions, and the workflow gaps found, each filed as its own issue.

mmt-dpi has no WebSocket or OCPP dissector: on these captures, mmt-dpi
1.10.2 alone labels every WebSocket session `http`.

## The workflow steps

| Step | Used | How |
|------|------|-----|
| `init` | yes | `init websocket_example --id 992 --parent tcp` and `init ocpp_example --id 993 --parent tcp`: the project, `plugin.yaml` with `sdk.profile` pinned, the scaffold `src/<label>_impl.c`. |
| `plugin.yaml` | yes | Written by hand: `session_context: true`, one `parents` entry `tcp` without `classify`, 19 and 11 attributes, each extracted by a hook. |
| `scaffold --from-pcap` | tried, not usable | On the first 5 000 packets of capture A1 with `--parent tcp:port=80`, it kept 20 payloads of 236 frames and proposed one field, `field_0` (`MMT_U16_DATA` at offset 0). It slices each frame alone, so the slices mix the HTTP handshake and the frames, and it proposes no bit fields (#102). Its packet tests (real bytes) are usable inputs. Neither PR used it. |
| `import` | not needed | No PDL v1 model. |
| `validate` | yes | Every check passes for both. |
| `generate` | yes | `generated/` and `plugin.lock` only from the tool: `generate --check` exits 0 on both (no hand-edited generated file). |
| hooks in `src/<label>_impl.c` | yes | About 1 000 lines (WebSocket) and 1 450 lines (OCPP) of C: the parent classification, the session state, the framing and the extraction hooks. |
| `build` | yes | `-Wall -Wextra -Werror`, against mmt-dpi 1.10.2. |
| `test --sanitize --bench` | yes | 15 of 15 and 14 of 14 packet runs pass; 15 015 and 14 014 sanitizer runs without a crash; 734 046 and 786 669 packets per second against an empty plugin's 4 248 168 and 10 079 959 (one run on the host of this report). The session replays are not packet tests: they are Python in `tests/unit/examples/test_sdk.py` (#99). |
| `install` | yes | Into private prefixes (`--prefix`), then the SDK's plugins linked next to them and `MMT_DPI_PLUGINS_DIR` set, as the [user guide](../user-guide.md#install-the-plugin) says. `doctor` passes with both installed. |
| the agent skill | not recorded | PRs #94 and #95 do not say whether `skills/mmt-plugin-author` drafted the models. |
| a run over a capture | no command | The counts below needed a C program written for the purpose (#103). |

## Results on the dataset captures

The captures are the `OCPPFlowMeter/*.pcap` files of Zenodo record
[14887131](https://zenodo.org/records/14887131) (CC-BY-4.0), each archive's
MD5 checked against the record: plaintext OCPP over WebSocket on TCP port
80, A1 and A2 inside 802.1Q. Each was run three times through mmt-dpi
1.10.2 (`libmmt_core` and the SDK's plugins): alone, with
`websocket_example`, and with `ocpp_example` and `websocket_example`
together (with both, OCPP claims the sessions whose handshake offers
`ocpp1.6`, at a lower weight, and WebSocket keeps the others; here every
session is OCPP). The reference is tshark 4.2.2 with its default TCP
reassembly. How the counts were made, and how to repeat them, is under
"Method" below.

### Classification

Packets of each protocol path above TCP (`ethernet[.8021q].ip.tcp.<x>`):

| Capture | Packets | mmt-dpi alone: `http` | with `websocket_example`: `WEBSOCKET_EXAMPLE` / `http` | with both: `OCPP_EXAMPLE` / `http` |
|---|---:|---:|---:|---:|
| A1 Charging Profile Manipulation | 345 544 | 58 866 | 56 868 / 0 | 59 950 / 0 |
| A2 Denial of Charge | 418 170 | 148 288 | 147 096 / 1 192 | 160 428 / 1 192 |
| A3 Heartbeat flooding | 14 795 256 | 14 790 197 | 14 790 197 / 0 | 14 790 197 / 0 |
| A4 Unauthorized access | 6 425 663 | 4 576 258 | 4 552 847 / 323 | 4 552 847 / 323 |

These counts include every packet of a claimed session (the handshake,
pure ACKs). `ocpp_example` also claims a session captured without its
handshake when a segment starts with an OCPP-J text frame: in A1 and A2,
one such session each, which mmt-dpi alone and `websocket_example` leave
`tcp.unknown` (A2: 13 449 packets `tcp.unknown` without the plugin, 117
with both). With `websocket_example` alone, A1 has 1 998 more packets
`tcp.unknown` than mmt-dpi alone, and A4 23 088 more; these were not
investigated further.

### WebSocket frames

Packets in which `websocket_example` reports at least one frame
(`frame_count`), against the packets tshark decodes with at least one
WebSocket frame, and the frames themselves (the sum of `frame_count`
against tshark's frames):

| Capture | Packets with frames: plugin / tshark | Frames: plugin / tshark | Opening handshakes (101): plugin / tshark |
|---|---:|---:|---:|
| A1 | 28 178 / 29 028 (97.1 %) | 28 269 / 29 575 (95.6 %) | 121 / 121 |
| A2 | 76 525 / 76 514 | 76 547 / 76 535 | 19 / 19 |
| A3 | 8 258 815 / 8 258 815 | 8 258 824 / 8 258 815 (packets) | 100 / 100 |
| A4 | 124 / 124 | 124 / 124 | 1 / 1 |

A4's 124 frames are the same on both sides by opcode (64 text, 30 ping, 30
pong). The plugin's first-frame opcodes are a per-packet count, not a
per-frame one, so they are not compared beyond that.

A1 is short by 1 306 frames. Of the 1 336 tshark frames in packets where the
plugin reports fewer, 1 184 are in two TCP streams (tshark's 94 and 342),
each after a run of retransmissions; in stream 94 the capture lost a client
segment (tshark: "previous segment not captured"). From there the plugin
reports nothing for the rest of the stream, while tshark starts again at
the next segment: `websocket_example` does not find a frame boundary again
after lost header bytes (#104).

### OCPP-J messages

tshark has no OCPP dissector; the reference parses tshark's WebSocket text
payloads as JSON. `ocpp_example` describes the first OCPP-J message of
each TCP segment, so the comparison is against tshark's first text payload
of each packet. That is how the issue's table was counted: it gives exactly
the issue's numbers (A1: 9 618 CALLs, SetChargingProfile 6 598, Heartbeat
2 390, StatusNotification 617, BootNotification 13, 9 337 CALLRESULTs).
The "no handshake" column counts the one session of A1 and of A2 that
tshark does not decode as WebSocket (it was captured without its
handshake), decoded with `-d tcp.port==80,websocket` on that session only.

| Capture | Message | `ocpp_example` | tshark | tshark, no-handshake session | tshark, total |
|---|---|---:|---:|---:|---:|
| A1 | CALL | 9 948 | 9 618 | 167 | 9 785 |
| | SetChargingProfile | 6 879 | 6 598 | 120 | 6 718 |
| | Heartbeat | 2 435 | 2 390 | 43 | 2 433 |
| | StatusNotification | 621 | 617 | 4 | 621 |
| | BootNotification | 13 | 13 | 0 | 13 |
| | CALLRESULT | 9 506 | 9 337 | 167 | 9 504 |
| A2 | CALL | 35 994 | 32 989 | 3 002 | 35 991 |
| | MeterValues | 10 564 | 9 708 | 856 | 10 564 |
| | StatusNotification | 10 268 | 9 408 | 860 | 10 268 |
| | RemoteStartTransaction | 5 159 | 4 730 | 429 | 5 159 |
| | StartTransaction | 4 983 | 4 552 | 428 | 4 980 |
| | StopTransaction | 4 981 | 4 553 | 428 | 4 981 |
| | Heartbeat, BootNotification, RemoteStopTransaction, Reset | 24, 11, 3, 1 | 23, 11, 3, 1 | 1, 0, 0, 0 | 24, 11, 3, 1 |
| | CALLRESULT | 35 960 | 32 959 | 3 001 | 35 960 |
| A3 | Heartbeat | 4 128 772 | 4 128 772 | | 4 128 772 |
| | BootNotification | 100 | 100 | | 100 |
| | CALLRESULT | 4 128 843 | 4 128 843 | | 4 128 843 |
| A4 | CALL (Heartbeat 29, StatusNotification 2, BootNotification 1) | 0 | 32 | | 32 |
| | CALLRESULT | 0 | 32 | | 32 |

No CALLERROR appears in any capture, on either side.

- A2 and A3 agree to within 3 messages, action by action.
- A1 is 163 CALLs over, all but 2 of them SetChargingProfile. A1 is an
  ARP-poisoning attack (the attacker rewrites SetChargingProfile on the
  way), and 1 289 segments carrying a SetChargingProfile are TCP
  retransmissions to tshark. With the segments tshark flags as
  retransmissions removed from the capture, `ocpp_example` gives 9 773
  CALLs (6 708 SetChargingProfile) against 9 785 (6 718): the plugin
  reports some retransmitted copies as new messages (#104).
- A4: the one accepted session negotiated `permessage-deflate` (its 101
  answer has `Sec-WebSocket-Extensions: permessage-deflate`), so its frames
  are compressed; `ocpp_example` does not inflate them (a documented
  limit), tshark does. The plugin reports no message there (#104).
- The answers' `action` comes from the CALL they answer. In A1, 9 474 of
  9 506 answers have it; in A3, 4 126 872 of 4 128 843 (1 971 answers come
  after their CALL was evicted from the 16-entry table during the flood).

The plugins' run time on A3 (14.8 M packets, one core): 12 s through
mmt-dpi alone, 22 s with `websocket_example`, 23 s with both.

## The open questions

1. **Session-state classification.** Worked around, partly not supported.
   Both plugins attach to TCP on any port at a weight below mmt-dpi's HTTP
   (5 and 4, HTTP is 20) and claim the session on the Upgrade request, or
   on a 101 answer when the capture starts there; OCPP also on a segment
   that starts with an OCPP-J text frame. Not supported: an Upgrade after
   other HTTP requests in the session (HTTP has claimed it), a session
   another plugin claimed first, and giving a refused upgrade back to HTTP
   (A4: 623 994 refused upgrades keep 4.55 M packets under the plugin).
   That needs an mmt-dpi change (#98).
2. **Variable-length header.** Supported. The header is 2 bytes, plus 2 or
   8 for the 16-bit or 64-bit length, plus 4 for the masking key when the
   mask bit is set; a split header is kept until the next segment.
   `payload_len` is the resolved length, `masking_key` is reported only
   when `mask` is 1. In the model these are hooks: the generated code
   cannot express a layout that depends on a field (the 7-bit length
   selects the header length), so `plugin.yaml` declares the attributes
   and the hooks read them.
3. **Masking.** Supported: `payload` is the unmasked payload (at most 1 024
   bytes), and `ocpp_example` unmasks as it parses. A child protocol cannot
   read it from a WebSocket layer, since mmt-dpi 1.10.2 does not classify a
   protocol above a plugin above TCP (#96); OCPP sits directly above TCP
   and repeats the WebSocket framing (about 600 lines).
4. **Framing over TCP.** Worked around with per-direction state (the next
   sequence number, the bytes a frame still owes, a split header, the
   message in progress). Several frames per segment: the attributes
   describe the first frame whose header ends in the segment and
   `frame_count` counts them. A frame over several segments: `carried_len`.
   Fragmented messages: `message_opcode`; control frames inside a
   fragmented message are kept out of it. Not supported: reordering
   out-of-order segments, finding a frame boundary again after lost header
   bytes (A1 above), `permessage-deflate` (A4 above). Only one frame (or
   OCPP message) per segment is described: an mmt-dpi attribute has one
   value per packet.
5. **Text / JSON payloads.** Supported for OCPP-J: a bounded JSON scanner
   without allocation reads CALL `[2, id, action, payload]`, CALLRESULT `[3,
   id, payload]` and CALLERROR `[4, id, code, description, details]`, and a
   few typed fields of a CALL's payload, by their place in the object. A
   CALLRESULT or CALLERROR gets its `action` from the CALL with the same
   UniqueId seen in the other direction (a 16-entry table per session).
   Strings are reported as sent (JSON escapes are not decoded), at most 63
   bytes. A message is read from the bytes of its segment only:
   continuation frames are not reassembled.

## The gaps found

| Issue | Gap |
|---|---|
| #96 | A protocol above a plugin above TCP is not classified by mmt-dpi 1.10.2; OCPP cannot be a child of WebSocket (filed with #94/#95). |
| #97 | The example mmt-security rule on the OCPP attributes, which belongs to mmt-security (filed with #95). |
| #98 | An Upgrade session that mmt-dpi's HTTP or another plugin claimed first is never handed over, and a refused one cannot be given back (needs mmt-dpi). |
| #99 | `mmt-plugin test` has no packet test of several packets of one session. |
| #100 | A generated `classify` cannot attach a protocol above TCP (or above tagged Ethernet). |
| #101 | `test` and `validate` assume the parents are mmt-dpi's: one plugin per test run, no `through` a plugin parent, no load-order check between plugins. |
| #102 | `scaffold --from-pcap` does not follow a TCP stream and proposes no bit fields. |
| #103 | No command runs a plugin over a capture and counts what it reports. |
| #104 | The capture findings on the two examples: no resynchronisation after lost header bytes, retransmitted copies counted, `permessage-deflate` not read. |

## Method

Everything below ran outside the repository, as a user: the captures are
data that does not belong in it, and no step needs root. The two programs
are next to this page:
[`websocket-ocpp/count.c`](websocket-ocpp/count.c), which feeds each
packet of a capture to `libmmt_core` and counts the protocol paths and the
attributes above, and
[`websocket-ocpp/tshark_count.py`](websocket-ocpp/tshark_count.py), which
counts the frames and messages in tshark's field output.

Download each archive from the record, check its MD5 against the record's
listing, and unzip `*/OCPPFlowMeter/*.pcap` into a directory of its own.
Then, with `MMT_BASE` a private mmt-dpi 1.10.2 prefix and the two example
projects copied out of the repository:

<!-- doc:skip needs the Zenodo captures and an mmt-dpi prefix -->
```sh
mmt-plugin -C websocket install --prefix "$PWD/plugins-ws"
mmt-plugin -C websocket install --prefix "$PWD/plugins-both"
mmt-plugin -C ocpp install --prefix "$PWD/plugins-both"
ln -sf "$MMT_BASE"/plugins/*.so "$PWD/plugins-ws/plugins/"
ln -sf "$MMT_BASE"/plugins/*.so "$PWD/plugins-both/plugins/"
gcc -O2 -Wall -o count count.c -I"$MMT_BASE/dpi/include" \
    -L"$MMT_BASE/dpi/lib" -Wl,-rpath,"$MMT_BASE/dpi/lib" -lmmt_core -ldl -lpcap
MMT_DPI_PLUGINS_DIR="$MMT_BASE/plugins" ./count A1.pcap        # mmt-dpi alone
MMT_DPI_PLUGINS_DIR="$PWD/plugins-ws/plugins" ./count A1.pcap
MMT_DPI_PLUGINS_DIR="$PWD/plugins-both/plugins" ./count A1.pcap
```

The reference, then the sessions tshark does not decode as WebSocket:

<!-- doc:skip needs the Zenodo captures and tshark -->
```sh
fields="-T fields -e tcp.stream -e websocket.opcode -e websocket.payload.text -e http.response.code"
opts="-E separator=/t -E occurrence=a -E aggregator=$(printf '\036')"
tshark -r A1.pcap $fields $opts | python3 -I tshark_count.py --list-streams ws-streams
tshark -r A1.pcap -d tcp.port==80,websocket $fields $opts | python3 -I tshark_count.py --without ws-streams
```

The capture without retransmissions (A1, the OCPP comparison above) is
`tshark -r A1.pcap -Y "not tcp.analysis.retransmission" -w A1-noretrans.pcap`.
