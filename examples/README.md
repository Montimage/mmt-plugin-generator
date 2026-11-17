# Examples

The 16 example models of the Java tool (`plugins/*_plugin`), ported to
mmt-plugin projects (plan task T5.1, `docs/design/workflow-redesign.md`),
and two plugins written with the tool: WebSocket (RFC 6455, #40, below,
"WebSocket") and OCPP 1.6-J (#41, below, "OCPP 1.6-J"). Each one builds
with `mmt-plugin build` and passes its packet tests with `mmt-plugin test`
against mmt-dpi 1.10.2, with gcc and clang, so
no example is left out. The Java tool was retired (T5.4, #31) and `plugins/` removed
(#78): the test corpus keeps the models, and these projects replace the
hand-written C (below, "The Java tool's C sources").

Each directory is a project:

- `plugin.yaml`: the model. `mmt-plugin import` converted the PDL model
  (`tests/corpus/models/<name>/model.pdl`, the Java tool's
  `plugins/<name>_plugin` byte for byte); the table below lists what
  changed after that. Its first line still names `plugins/<name>_plugin`.
  The WebSocket and OCPP examples' were written from their
  specifications, after `mmt-plugin init`.
- `plugin.lock` and `generated/`: written by `mmt-plugin generate`, and
  committed, so that `generate --check` shows when they are stale.
- `src/<label>_impl.c`: the hooks that the generated header declares.
- `tests/*.yaml`: the packet tests, ported from the corpus fixtures in
  `tests/corpus/models/<name>/packets/`, same bytes (the WebSocket
  example's are RFC 6455's examples, the OCPP example's OCPP-J 1.6
  messages). Their expected values
  come from the protocol specifications, by the rules of
  `tests/corpus/README.md`; each one names its source. In an example with a
  parent, one of them also runs through it (`through`, below). The
  WebSocket and OCPP examples also have session tests,
  `tests/session-*.yaml` (#99): TCP sessions, packet by packet, written
  from the same specifications.
- `.gitignore`: `build/`.

Build and test one, with an SDK in a private prefix (`AGENTS.md`, "A
private prefix can also come from the published package"):

```
uv run mmt-plugin -C examples/dns test --sdk <dir>/opt/mmt --cc gcc --sanitize
```

`tests/unit/examples/` checks every example without an SDK (the models,
`generate --check`, the packet tests' bytes) and, with `MMT_GOLDEN_SDK`, runs
`validate`, `build` and `test --sanitize` on each one, then breaks each
parent's classification and checks that only the run through the parent
fails (and the session tests, which run through it too), runs the
WebSocket and OCPP examples' session tests under the sanitizers, and an
OCPP session with the two plugins side by side; CI runs both.

## The ports

Every label is `<protocol>_example`, and every id is in the third-party
range 950-999 (plan decision 5): the SDK has most of the models' own names
and ids (`model.legacy-sdk-conflict`). Every `plugin.yaml` pins the SDK
profile `1.10.2` and declares its parent, which the models did not have.

| example | label | id | parent | changes from the PDL model |
|---|---|---|---|---|
| `abb` | `abb_example` | 976 | `udp`, destination port 12118 | none |
| `arp` | `arp_example` | 977 | `ethernet`, EtherType 0x0806 | the else branch's second `ar_pro` (inventory bug 12) is the sender hardware address, renamed `SRC_HARD`; `unsigned short`, `unsigned char` and `int` fields are `uint16_t`, `uint8_t` and `uint32_t` |
| `cam` | `cam_example` | 978 | `udp`, payload starting 02 02 | none |
| `cotp` | `cotp_example` | 979 | none: `tpkt_example` classifies it | `encapsulation` and a `classify_next`: a DT TPDU (0xf0) carries `s7comm_example` at LI + 1; struct `cotphdr` is `cotp_hdr` |
| `cpm` | `cpm_example` | 981 | `udp`, payload starting 02 0e | none |
| `dns` | `dns_example` | 982 | `udp`, destination port 53 | none |
| `ethernet` | `ethernet_example` | 983 | none: the link layer | `src` and `dst` had `sizeof (mac_addr_t)`, not a PDL type, at offsets 0 and 2: they are the source (6) and destination (0) addresses; the next protocols are mmt-dpi's `PROTO_IP`, `PROTO_ARP` and `PROTO_IPV6`, not the model's own 15, 11 and 16 |
| `ip` | `ip_example` | 984 | `ethernet`, EtherType 0x0800 | `ihl:4, version:4` is `version:4, ihl:4` (plan decision 8) |
| `mongodb` | `mongodb_example` | 985 | `tcp`, port 27017 (hook) | the offsets were `POSITION_NOT_KNOWN`, not an expression: 0, 4, 8 and 12; the encoding is `host` (little-endian), not `network` |
| `ndn` | `ndn_example` | 980 | `ethernet`, EtherType 0x8624 | none (it had its own label and id) |
| `quic` | `quic_example` | 986 | `udp`, destination port 443 | none |
| `radius` | `radius_example` | 987 | `udp`, destination port 1812 | none: the hooks find the TLV attributes |
| `s7com` | `s7comm_example` | 988 | none: `cotp_example` classifies it | struct `s7commphdr` is `s7comm_hdr` |
| `tcp` | `tcp_example` | 989 | `ip`, protocol 6 (hook) | the struct follows RFC 9293 section 3.1 (it had fields `a` to `h` and put `seq` at byte 12): `seq`, `ack_seq`, `doff`, `reserved`, `flags`, `window`, `check`, `urg_ptr` |
| `topo_ind_sch` | `topo_ind_sch_example` | 990 | none known | none (the label was `MSG_TOPO_IND_SCH`) |
| `tpkt` | `tpkt_example` | 991 | `tcp`, port 102 (hook) | `encapsulation` and a `classify_next`: version 3 carries `cotp_example` at 4; struct `tpkthdr` is `tpkt_hdr` |

The three structs renamed after the SDK's: `tcpip/mmt_tcpip_attributes.h`
defines `struct tpkthdr`, `struct cotphdr` and `struct s7commphdr`, so a
hook file that includes `tcpip/mmt_tcpip.h` would not compile.

A parent with a fixed header (Ethernet, UDP) is attached by the generated
code (`parents[].classify`). TCP and IPv4 have a header of variable length,
so the `tcp`, `tpkt`, `mongodb`, `websocket` and `ocpp` examples attach
theirs in `<label>_hook_register_parents`. The UDP parents match the destination port
only, so they classify requests, not the answers.

## Hooks

- `radius`: each TLV attribute (RFC 2865 section 5, RFC 2866, RFC 2869, RFC
  3162) is found by its type, inside the packet's Length and the captured
  bytes.
- `tcp`, `tpkt`, `mongodb`: the parent registration, as above.
- `websocket`: every attribute, the parent registration and the session
  data, which follow the TCP session (below, "WebSocket").
- `ocpp`: the same, with its own WebSocket framing and the CALLs waiting
  for their answers (below, "OCPP 1.6-J").
- `dns`, `ndn`, `ip`: the model sets `session_context`, `session` or
  `context`, so these have the session and context hooks, which keep no
  data. Write your analysis there.
- `ip`: `encapsulation` without `classify_next`, as in the model, so the
  next protocol is the `classify_next` hook, which classifies nothing:
  with mmt-dpi 1.10.2, handing the payload to mmt-dpi's own UDP after this
  plugin crashes `libmmt_tcpip` (`udp_pre_classification_function`,
  SIGSEGV), whose transport protocols expect mmt-dpi's own IP below them.
- The others have only the parent registration.

## Through the parent

`mmt-plugin test` attaches the plugin to Ethernet itself (EtherType 0x88b5)
and hands it the packet's bytes, so most packet tests do not run the parent
classification (the `classify` of `plugin.yaml` or the hook's function).
One test of each example with a parent also runs through it: its `through`
key names the parent, and `test` builds the lower layers, hands the frame
to mmt-dpi's stack and checks that the plugin is classified directly above
that parent, where the layers end, with the same values.

| example | test | `through` |
|---|---|---|
| `abb` | `frame` | `udp:dport=12118` |
| `arp` | `request-ethernet-ipv4` | `ethernet:ethertype=0x0806` |
| `cam` | `header` | `udp` (any port: the classify matches the payload) |
| `cpm` | `header` | `udp` |
| `dns` | `query-a` | `udp:dport=53` (a query: the parent matches the destination port) |
| `ip` | `udp-df` | `ethernet:ethertype=0x0800` |
| `mongodb` | `op-msg-ping` | `tcp:dport=27017` |
| `ndn` | `interest` | `ethernet:ethertype=0x8624` |
| `ocpp` | `call-boot-notification` | `tcp:dport=80` (one segment, its own session, no handshake: the OCPP-J array shape claims it; 80 is a `ws` URI's default port, RFC 6455 section 3) |
| `quic` | `initial-prefix` | `udp:dport=443` |
| `radius` | `access-request` | `udp:dport=1812` |
| `tcp` | `syn-ack-options` | `ip:proto=6` |
| `tpkt` | `cr` | `tcp:dport=102` (one segment, no handshake) |
| `websocket` | `handshake-request` | `tcp:dport=80` (one segment, its own session: the Upgrade request opens it; any port would do) |

`tests/unit/examples/test_sdk.py` removes each `classify` (or attaches each
hook's function to another protocol, or moves the `dns` classify's offset)
and checks that the run through the parent then fails, and only it.

That run does not check the next protocol. mmt-dpi 1.10.2's TCP and UDP
stop a packet at a layer that a plugin, not their own detection,
classified above them (`tcp_post_classification_function` and
`udp_post_classification_function` return 0), so that layer's
`classify_next` never runs there: installed, `tpkt_example` would not hand
a segment to `cotp_example`. The harness's run checks `tpkt`'s next
protocol.

## WebSocket

Not a port: the corpus has no WebSocket model. `mmt-plugin init
websocket_example --id 992 --parent tcp` made the project; then
`plugin.yaml` got the attributes and `session_context`, and
`src/websocket_example_impl.c` its hooks. The packet tests are the
examples of RFC 6455 sections 1.2, 4.4 and 5.7, and a close frame of
section 5.5.1 (`tests/*.yaml`, each value with its section).

| example | label | id | parent | what it reports |
|---|---|---|---|---|
| `websocket` | `websocket_example` | 992 | `tcp`, any port, from the opening handshake (hook) | the handshake's fields; per segment, the first frame's header, its unmasked payload, the number of frames, the bytes of an earlier frame |

Every attribute is a hook, without an offset: where a frame starts in a
segment depends on the session (the handshake before it, a frame begun in
an earlier segment), which no `plugin.yaml` expression can read.

- **Classification.** A TCP segment that starts with `GET ` and has an
  `Upgrade` field with the token `websocket` (RFC 6455 section 4.1), or an
  `HTTP/1.x 101` answer with it (a capture without the request), claims
  the session above TCP, on any port, at weight 5 (mmt-dpi's HTTP is at
  20). Plain HTTP is left to mmt-dpi.
- **Attributes.** `handshake` is 1 on the request (`key`, `subprotocol`:
  the client's list as written), 2 on the answer (`status_code`, `accept`,
  `subprotocol`: the server's choice), 0 on frame data. A segment reports
  the first frame whose header ends in it (`fin`, `rsv1`-`rsv3`, `opcode`,
  `mask`, `payload_len` up to 2^63 - 1, `masking_key`, `payload_offset`
  from the segment's first byte, `payload`: its bytes in the segment,
  unmasked, at most 1024, `close_code`, `message_opcode`: the first
  fragment's opcode on a continuation frame), `frame_count` (frames whose
  header ends in the segment) and `carried_len` (bytes at its start of a
  frame whose header ended earlier, 0 when it starts with a header). A
  header split across segments counts in the segment where it ends. On
  frames, `subprotocol` is the one the 101 answer selected. A pure ACK, a retransmission, client data before the
  answer and anything after a refused upgrade (a status other than 101)
  report nothing.
- **State.** mmt-dpi has no TCP reassembly for plugins. Per direction, the
  session data keeps the next sequence number, the bytes the current frame
  still owes, a split header and the message in progress. A retransmitted
  segment reports nothing (the new bytes after an overlap are parsed);
  after lost bytes the parse stays in step when they were the current
  frame's payload; otherwise (a header was lost) it starts again at the
  first segment that starts with a whole valid frame header (RSV2 and RSV3
  0, a defined opcode, a control frame with FIN set and at most 125
  bytes), and the segments before it, which start inside a frame, report
  no frame (#104). The segment ends where the IP length says, so Ethernet
  padding is not parsed. Without a session (the harness's packets behind
  Ethernet), a segment is parsed alone.
- **Session timeout.** The state lives as long as mmt-dpi's session, which
  ends after a silence: 60 s by default, the long timeout (600 s, as
  mmt-dpi's HTTP gives an HTTP session) for the sessions this plugin
  claims (`set_session_timeout_delay()`). A WebSocket connection is often
  idle for longer than a minute; after mmt-dpi ends a session, the next
  segment opens a new one, mid-stream, which this plugin does not claim
  (no handshake) (#104).
- **Where it runs in mmt-dpi 1.10.2** (checked empirically, and kept by the
  session tests, `tests/session-*.yaml`): TCP stops a packet
  at a layer a plugin classified (above, "Through the parent"), so the
  layer's session data hooks do not run while TCP classifies the session.
  mmt-dpi then calls the session's owner, this classification function,
  directly on every packet, pure ACKs included, and it parses the
  segment without classifying it again (that would be an update, which
  calls `session_data_init` again). After 40 packets of a session its own
  detection did not identify, TCP stops classifying it and the packets
  reach the layer: `session_data_init` (which keeps the state) and
  `session_data_analysis` parse them then. Each packet is parsed once.

The session tests (`tests/session-*.yaml`, #99: `mmt-plugin test` builds
the TCP frames, handshake, sequence numbers, checksums, Ethernet padding)
run on port 8080 and check every attribute of every packet: the handshake, masked and unmasked frames, two
frames in a segment, a fragmented message, a 16-bit frame over two
segments, a split header, a retransmission, lost payload bytes, a lost
frame header, close frames, more than 40 packets, a refused upgrade, plain
HTTP, a capture that starts at the answer, an answer's header block over
two segments, and a session idle for 70 s; with
and without the sanitizers, then corrupted and cut short.

Not covered, or open:

- Out-of-order segments are not reordered: after a gap the parse goes on
  as after lost bytes, and the late segment is then a retransmission. A header field line split across segments is lost; only
  the first segment of the request is read.
- Extensions (RFC 6455 section 9, `permessage-deflate`, RFC 7692): `rsv1`
  is reported, the payload is not inflated.
- A refused upgrade keeps the session as `WEBSOCKET_EXAMPLE` with nothing
  to report: mmt-dpi 1.10.2 has no way for a plugin to give a session back.
- A child protocol can attach with
  `register_classification_function_with_parent_protocol(PROTO_WEBSOCKET_EXAMPLE, ...)`,
  but mmt-dpi 1.10.2 does not process a layer that a plugin classified
  above TCP (above, "Through the parent"), so it is not classified there
  until mmt-dpi changes. The OCPP example (below, "OCPP 1.6-J") sits
  directly above TCP instead and parses the WebSocket framing itself; with
  both installed, a session whose handshake offers `ocpp1.6` is
  `tcp.ocpp_example`, with no WebSocket layer, and the other WebSocket
  sessions stay here.
- When mmt-dpi's HTTP claims a session first (an Upgrade request after
  other HTTP requests in the same session), or another plugin does (a
  weight below 5), the session is not WebSocket here: once a session is
  classified, mmt-dpi 1.10.2 calls only its owner. Handing an Upgrade
  session from HTTP to a plugin needs an mmt-dpi change.
- Checking it against real captures (the Zenodo datasets of #40) is a
  manual run, not CI. The run of #39 (counts against tshark, measured
  again after #104) is in
  [`docs/use-cases/websocket-ocpp.md`](../docs/use-cases/websocket-ocpp.md).

## OCPP 1.6-J

Not a port either: `mmt-plugin init ocpp_example --id 993 --parent tcp`
made the project; then `plugin.yaml` got the attributes and
`session_context`, and `src/ocpp_example_impl.c` its hooks. OCPP 1.6-J is
OCPP 1.6 over WebSocket: the OCPP-J 1.6 specification (Open Charge
Alliance) gives the handshake (section 3) and the messages, JSON arrays
in text frames (section 4); OCPP 1.6 gives their payloads (section 6) and
types (section 7). The packet tests are messages of those sections in
WebSocket frames (`tests/*.yaml`, each value with its section).

| example | label | id | parent | what it reports |
|---|---|---|---|---|
| `ocpp` | `ocpp_example` | 993 | `tcp`, any port, from an opening handshake offering `ocpp1.6` (hook) | per segment, the first OCPP-J message: its type, UniqueId, action (on an answer, its CALL's), error code and description, payload, typed fields; the number of messages |

mmt-dpi 1.10.2 does not classify a protocol above `websocket_example`
(above, "WebSocket", "Not covered, or open"), so `ocpp_example` is not
its child: it sits directly above TCP, at weight 4 (before
`websocket_example`'s 5 and mmt-dpi's HTTP's 20), and parses the WebSocket
framing itself, with `websocket_example`'s code for it (the handshake, the
frame header, the unmasking, the TCP state), trimmed.

- **Classification.** A session is claimed on the client's opening
  handshake, a GET with `Upgrade: websocket` whose
  `Sec-WebSocket-Protocol` offers the token `ocpp1.6` (OCPP-J 1.6 section
  3.1.2; case-sensitive), on any port; any other request is left to
  `websocket_example` and mmt-dpi's HTTP. mmt-dpi's HTTP claims a session
  on its request line, so the decision cannot wait for the answer. A 101
  answer that selects `ocpp1.6` claims a capture without the request, and
  a segment that starts with an unfragmented text frame holding an OCPP-J
  message (`[`, then 2, 3 or 4, then `,`, then a complete string, with
  JSON whitespace around them) one that starts after the handshake.
- **Attributes.** A segment reports the first OCPP-J message whose frame
  header ends in it, parsed from the frame's bytes in the segment,
  unmasked: `message_type_id` (2 CALL, 3 CALLRESULT, 4 CALLERROR),
  `unique_id`, `action` (a CALL's Action; on a CALLRESULT or CALLERROR,
  the Action of the CALL it answers, absent when that CALL was not seen),
  `error_code` and `error_description` (CALLERROR), `payload` (the Payload,
  or a CALLERROR's errorDetails, as sent), and `message_count`, the OCPP-J
  messages whose frame header ends in the segment. The typed fields come
  from a CALL's payload, at their place in it, never from a key found
  anywhere: `connector_id`, the top-level `connectorId`; `id_tag`, the
  top-level `idTag` of Authorize, StartTransaction and
  RemoteStartTransaction; `charging_limit_x10` and `charging_rate_unit`,
  the first `chargingSchedulePeriod`'s `limit` and the
  `chargingRateUnit` (`A` or `W`) of SetChargingProfile's
  `csChargingProfiles.chargingSchedule` or RemoteStartTransaction's
  `chargingProfile.chargingSchedule`. A limit has at most one fractional
  digit (OCPP 1.6 section 7.14), so it is in tenths of the unit: 110005
  for 11000.5 W; more digits are cut (rounded toward zero), and a
  negative limit or one with an exponent is not reported. Strings are the
  bytes between the quotes as sent (escapes not decoded), at most the
  first 63 (`MMT_STRING_DATA`); `payload` at most the first 1024
  (`MMT_BINARY_VAR_DATA`). The handshake, a pure ACK, a retransmission and
  a frame that is not an OCPP-J message (a ping, `[5,...`, `[2,3]`)
  report nothing.
- **Links.** Per session, the CALLs not answered yet, by direction and
  UniqueId (OCPP-J 1.6 section 4.1.4), at most 16, the oldest dropped
  first: a CALLRESULT or CALLERROR takes the action of the CALL sent the
  other way with its UniqueId, and removes it. Both sides may use the
  same UniqueId at once. A UniqueId over 36 bytes, the specification's
  maximum, is not kept, so its answer has no action. Without a session
  (the harness's packets), nothing is linked, so the packet tests'
  answers have no action; the session tests check the links.
- **State and where it runs** are `websocket_example`'s (above): the TCP
  sequence numbers per direction, a frame over segments, a split header,
  the parse starting again after a lost header, the segment's end at the
  IP length, mmt-dpi's long session timeout (so a CALL retransmitted after
  minutes of silence is still a retransmission, #104), and mmt-dpi 1.10.2
  calling the classification function, then after 40 packets the session
  data hooks.

Its session tests (`tests/session-*.yaml`, #99) run TCP sessions through
it (on port 9000) and check every attribute of every packet: CALL then
CALLRESULT and CALLERROR with their action, an answer seen twice, from
the CALL's own side or for an unknown UniqueId, the same UniqueId sent by
both sides, two messages in a segment, the typed fields, a decoy
`connectorId` in a string and a nested object, an escaped quote in a
UniqueId, UniqueIds of 36 and 40 bytes, a frame over two segments, a
ping, more than 40 packets, more than 16 CALLs waiting, an answer
selecting `ocpp2.0.1`, a refused upgrade, a chat WebSocket session, an
`OCPP1.6` offer and plain HTTP (none of them claimed), a capture that
starts after the handshake or at the answer, an answer's header block
over two segments, a CALL retransmitted after 70 s of silence and a lost
frame header; with and without the sanitizers, then corrupted and cut
short. `tests/unit/examples/test_sdk.py` also loads `mmtp_ocpp_example.so` and
`mmtp_websocket_example.so` in one plugin directory: the `ocpp1.6`
session is `OCPP_EXAMPLE`, the chat session `WEBSOCKET_EXAMPLE`, both
directly above TCP.

Not covered, or open:

- Not a child of `websocket_example` until mmt-dpi processes a layer above
  a plugin above TCP (above, "WebSocket", "Not covered, or open").
- A request whose `Sec-WebSocket-Protocol` line is in its second TCP
  segment is not claimed (only the first segment of the request is read,
  as for `websocket_example`); neither is one after other HTTP requests in
  the session, which mmt-dpi's HTTP has claimed.
- A 101 answer that selects another subprotocol (or none), or a refused
  upgrade, keeps the session as `OCPP_EXAMPLE` with nothing to report:
  mmt-dpi 1.10.2 has no way for a plugin to give a session back.
- One message is described per segment (`message_count` counts the
  others, which are linked too). A message is read from its first frame,
  in the segment where that frame's header ends: continuation frames and
  the bytes of a frame in later segments are not reassembled, so a field
  after them is not reported. Compressed frames (`permessage-deflate`,
  RSV1) are not read: inflating them needs a DEFLATE decoder in the
  plugin, which links only `libmmt_core` (#104 kept this limit).
- Checking per-action CALL counts and links against real captures (the
  Zenodo record 14887131 of #41, against tshark) is a manual run, not CI:
  the run of #39 is in
  [`docs/use-cases/websocket-ocpp.md`](../docs/use-cases/websocket-ocpp.md)
  (and its findings in #104); the mmt-security rule on these attributes
  is in that repository, not here (#97).

## What the packet tests do not cover

- The other packet tests run where the harness attaches the plugin, so
  only one packet per example exercises the parent's checks (the port, the
  IHL, the data offset), and with one value of each.
- `cotp` and `s7com` are tested alone: `tpkt_example` and `cotp_example`
  report the next protocol's id and offset, which their tests check.
- The values of `cam`, `cpm` (after byte 7) and `quic` are what the model
  declares: the specifications have no byte-aligned field there (ETSI UPER)
  or another layout (RFC 9000). The tests say so in each `source`.

## The Java tool's C sources

`plugins/` held, next to the models, C that the Java tool generated and
someone then edited, or wrote by hand. It was removed in #78; every file is
in the tree at commit f081d43, for example
`git show f081d43:plugins/http2_src/http2_mmt_plugin.c`. The `source` of a
packet test and the first line of a `plugin.yaml` that name a `plugins/`
file mean that commit's.

| directory at f081d43 | what it was | its port |
|---|---|---|
| `plugins/abb_src/` | the abb plugin, attached to UDP port 12118 (source or destination) | `abb`: `parents[].classify` (destination port 12118) |
| `plugins/arp_src/` | the arp plugin, attached to Ethernet, EtherType 0x0806 | `arp`: `parents[].classify` |
| `plugins/cam_plugin_src/` | the cam plugin, attached to UDP, payload starting 02 02 | `cam`: `parents[].classify` |
| `plugins/cotp/` | the cotp plugin, attached to TPKT | `cotp`: `tpkt_example`'s `classify_next` |
| `plugins/cpm_plugin_src/` | the cpm plugin, attached to UDP, payload starting 01 32 | `cpm`: `parents[].classify` (02 0e, the ETSI header: `tests/corpus/index.yaml`) |
| `plugins/mongodb_src/` | the mongodb plugin, attached to TCP, on the header's `opCode` | `mongodb`: `<label>_hook_register_parents` (port 27017) |
| `plugins/quic_src/` | the quic plugin, attached to UDP ports 80 and 443 | `quic`: `parents[].classify` (destination port 443 only) |
| `plugins/s7comm/` | the s7com plugin, attached to COTP | `s7com`: `cotp_example`'s `classify_next` |
| `plugins/tpkt/` | the tpkt plugin, attached to TCP port 102 (source or destination) | `tpkt`: `<label>_hook_register_parents` |
| `plugins/tptk_src/` | an older tpkt plugin (id 636, registered as a protocol stack, no parent) | none: `plugins/tpkt/` superseded it |
| `plugins/new_abb_src/` | `ABB_CAMERA` (id 800), a variant of abb with no model | none: no model to port, and `abb` covers the protocol |
| `plugins/http2_src/` | an HTTP/2 plugin (id 700) with no model | none: mmt-dpi 1.10.2 has `PROTO_HTTP2`, id 700, in `libmmt_tcpip` |
| `plugins/mongodb_extraction.c`, `plugins/quic_extraction.c` | programs that read a pcap with `libmmt_core` and print the mongodb or quic attributes, not plugins | none: `mmt-plugin test` prints each attribute of a packet test, and `scaffold --from-pcap` reads a capture |

## Installing

`mmt-plugin install` copies an example into a plugin directory. Most of
them re-implement a protocol mmt-dpi has, and their parent classification
runs first, so an installed `ip_example` takes the IPv4 traffic from
mmt-dpi's IP: install the examples into a private prefix only, never next
to an mmt-dpi in use (`websocket_example` takes every TCP session that
upgrades to WebSocket, on any port, and `ocpp_example` every one whose
handshake offers `ocpp1.6`). `ndn_example` has the id and the name
of the NDN plugin in `ndn_src/`, so only one of the two can be installed.

## Regenerating

`plugin.lock` records the mmt-plugin version, so a change to the generator
or to its version makes `generate --check` fail on every example. Then
regenerate them all and commit the result:

```
for d in examples/*/; do uv run mmt-plugin -C "$d" generate; done
```

A release bumps the version, so it regenerates them in the same change;
the release workflow's `verify` job runs `generate --check` on every
example with the built wheel ([`docs/releasing.md`](../docs/releasing.md)).
