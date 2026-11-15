# Examples

The 16 example models of `plugins/*_plugin`, ported to mmt-plugin projects
(plan task T5.1, `docs/design/workflow-redesign.md`). Each one builds with
`mmt-plugin build` and passes its packet tests with `mmt-plugin test`
against mmt-dpi 1.10.2, with gcc and clang, so no example is left out.
`plugins/` stays as it was until the Java tool is retired (T5.4).

Each directory is a project:

- `plugin.yaml`: the model. `mmt-plugin import` converted the PDL model
  (`tests/corpus/models/<name>/model.pdl`, a copy of
  `plugins/<name>_plugin`); the table below lists what changed after that.
- `plugin.lock` and `generated/`: written by `mmt-plugin generate`, and
  committed, so that `generate --check` shows when they are stale.
- `src/<label>_impl.c`: the hooks that the generated header declares.
- `tests/*.yaml`: the packet tests, ported from the corpus fixtures in
  `tests/corpus/models/<name>/packets/`, same bytes. Their expected values
  come from the protocol specifications, by the rules of
  `tests/corpus/README.md`; each one names its source.
- `.gitignore`: `build/`.

Build and test one, with an SDK in a private prefix (`AGENTS.md`, "A
private prefix can also come from the published package"):

```
uv run mmt-plugin -C examples/dns test --sdk <dir>/opt/mmt --cc gcc --sanitize
```

`tests/unit/examples/` checks every example without an SDK (the models,
`generate --check`, the packet tests' bytes) and, with `MMT_GOLDEN_SDK`, runs
`validate`, `build` and `test --sanitize` on each one; CI runs both.

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
so the `tcp`, `tpkt` and `mongodb` examples attach theirs in
`<label>_hook_register_parents`. The UDP parents match the destination port
only, so they classify requests, not the answers.

## Hooks

- `radius`: each TLV attribute (RFC 2865 section 5, RFC 2866, RFC 2869, RFC
  3162) is found by its type, inside the packet's Length and the captured
  bytes.
- `tcp`, `tpkt`, `mongodb`: the parent registration, as above.
- `dns`, `ndn`, `ip`: the model sets `session_context`, `session` or
  `context`, so these have the session and context hooks, which keep no
  data. Write your analysis there.
- `ip`: `encapsulation` without `classify_next`, as in the model, so the
  next protocol is the `classify_next` hook, which classifies nothing:
  with mmt-dpi 1.10.2, handing the payload to mmt-dpi's own UDP after this
  plugin crashes `libmmt_tcpip` (`udp_pre_classification_function`,
  SIGSEGV), whose transport protocols expect mmt-dpi's own IP below them.
- The others have only the parent registration.

## What the packet tests do not cover

- `mmt-plugin test` attaches the plugin to Ethernet itself (EtherType
  0x88b5) and hands it the packet's bytes, so the parent classification
  (the `classify` of `plugin.yaml` or the hook's function) never runs. It
  is registered when the plugin loads, so a registration that fails fails
  the test.
- `cotp` and `s7com` are tested alone: `tpkt_example` and `cotp_example`
  report the next protocol's id and offset, which their tests check.
- The values of `cam`, `cpm` (after byte 7) and `quic` are what the model
  declares: the specifications have no byte-aligned field there (ETSI UPER)
  or another layout (RFC 9000). The tests say so in each `source`.

## Installing

`mmt-plugin install` copies an example into a plugin directory. Most of
them re-implement a protocol mmt-dpi has, and their parent classification
runs first, so an installed `ip_example` takes the IPv4 traffic from
mmt-dpi's IP: install the examples into a private prefix only, never next
to an mmt-dpi in use. `ndn_example` has the id and the name of the NDN
plugin in `ndn_src/`, so only one of the two can be installed.

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
