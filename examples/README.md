# Examples

The 16 example models of the Java tool (`plugins/*_plugin`), ported to
mmt-plugin projects (plan task T5.1, `docs/design/workflow-redesign.md`),
and a WebSocket (RFC 6455) plugin written with the tool (#40, below,
"WebSocket"). Each one builds with `mmt-plugin build` and passes its packet
tests with `mmt-plugin test` against mmt-dpi 1.10.2, with gcc and clang, so
no example is left out. The Java tool was retired (T5.4, #31) and `plugins/` removed
(#78): the test corpus keeps the models, and these projects replace the
hand-written C (below, "The Java tool's C sources").

Each directory is a project:

- `plugin.yaml`: the model. `mmt-plugin import` converted the PDL model
  (`tests/corpus/models/<name>/model.pdl`, the Java tool's
  `plugins/<name>_plugin` byte for byte); the table below lists what
  changed after that. Its first line still names `plugins/<name>_plugin`.
  The WebSocket example's was written from RFC 6455, after `mmt-plugin
  init`.
- `plugin.lock` and `generated/`: written by `mmt-plugin generate`, and
  committed, so that `generate --check` shows when they are stale.
- `src/<label>_impl.c`: the hooks that the generated header declares.
- `tests/*.yaml`: the packet tests, ported from the corpus fixtures in
  `tests/corpus/models/<name>/packets/`, same bytes (the WebSocket
  example's are RFC 6455's examples). Their expected values
  come from the protocol specifications, by the rules of
  `tests/corpus/README.md`; each one names its source. In an example with a
  parent, one of them also runs through it (`through`, below).
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
fails, and replays the WebSocket example's TCP sessions; CI runs both.

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
so the `tcp`, `tpkt`, `mongodb` and `websocket` examples attach theirs in
`<label>_hook_register_parents`. The UDP parents match the destination port
only, so they classify requests, not the answers.

## Hooks

- `radius`: each TLV attribute (RFC 2865 section 5, RFC 2866, RFC 2869, RFC
  3162) is found by its type, inside the packet's Length and the captured
  bytes.
- `tcp`, `tpkt`, `mongodb`: the parent registration, as above.
- `websocket`: every attribute, the parent registration and the session
  data, which follow the TCP session (below, "WebSocket").
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
  frames, `subprotocol` is the one the 101 answer selected: what an OCPP
  plugin (#41) reads. A pure ACK, a retransmission, client data before the
  answer and anything after a refused upgrade (a status other than 101)
  report nothing.
- **State.** mmt-dpi has no TCP reassembly for plugins. Per direction, the
  session data keeps the next sequence number, the bytes the current frame
  still owes, a split header and the message in progress. A retransmitted
  segment reports nothing (the new bytes after an overlap are parsed);
  after lost bytes the parse stays in step when they were the current
  frame's payload, and restarts at the segment's first byte otherwise. The
  segment ends where the IP length says, so Ethernet padding is not
  parsed. Without a session (the harness's packets behind Ethernet), a
  segment is parsed alone.
- **Where it runs in mmt-dpi 1.10.2** (checked empirically, and kept by the
  session replay of `tests/unit/examples/test_sdk.py`): TCP stops a packet
  at a layer a plugin classified (above, "Through the parent"), so the
  layer's session data hooks do not run while TCP classifies the session.
  mmt-dpi then calls the session's owner, this classification function,
  directly on every packet, pure ACKs included, and it parses the
  segment without classifying it again (that would be an update, which
  calls `session_data_init` again). After 40 packets of a session its own
  detection did not identify, TCP stops classifying it and the packets
  reach the layer: `session_data_init` (which keeps the state) and
  `session_data_analysis` parse them then. Each packet is parsed once.

The replay builds whole TCP sessions (`tcpsession.py`: handshake, sequence
numbers, checksums, Ethernet padding) on port 8080 and checks every
attribute of every packet: the handshake, masked and unmasked frames, two
frames in a segment, a fragmented message, a 16-bit frame over two
segments, a split header, a retransmission, lost payload bytes, close
frames, more than 40 packets, a refused upgrade, plain HTTP, a capture that
starts at the answer, and an answer's header block over two segments; with
and without the sanitizers, then corrupted and cut short.

Not covered, or open:

- Out-of-order segments are not reordered: a segment after a gap restarts
  the parse unless the gap was payload, and the late one is then a
  retransmission. A header field line split across segments is lost; only
  the first segment of the request is read.
- Extensions (RFC 6455 section 9, `permessage-deflate`, RFC 7692): `rsv1`
  is reported, the payload is not inflated.
- A refused upgrade keeps the session as `WEBSOCKET_EXAMPLE` with nothing
  to report: mmt-dpi 1.10.2 has no way for a plugin to give a session back.
- A child protocol (OCPP, #41) can attach with
  `register_classification_function_with_parent_protocol(PROTO_WEBSOCKET_EXAMPLE, ...)`,
  but mmt-dpi 1.10.2 does not process a layer that a plugin classified
  above TCP (above, "Through the parent"), so it is not classified there
  until mmt-dpi changes; read `payload` and `subprotocol` from this
  layer meanwhile.
- When mmt-dpi's HTTP claims a session first (an Upgrade request after
  other HTTP requests in the same session), or another plugin does (a
  weight below 5), the session is not WebSocket here: once a session is
  classified, mmt-dpi 1.10.2 calls only its owner. Handing an Upgrade
  session from HTTP to a plugin needs an mmt-dpi change.
- Checking it against real captures (the Zenodo datasets of #40) is a
  manual run, not CI.

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
upgrades to WebSocket, on any port). `ndn_example` has the id and the name
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
