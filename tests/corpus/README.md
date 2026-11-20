# Test corpus

Packet fixtures for the mmt-plugin generator (plan task T0.4,
`docs/design/workflow-redesign.md`). Each fixture pairs a PDL model with
packet bytes and the values a correct generated plugin must extract.
`mmt-plugin test` (T2.4) runs them; T1.x uses the models for parser, layout
and golden-output tests.

The expected values come from the protocol specifications, never from the
Java generator's output, which is wrong in places (inventory bugs 2-7). Every
value records where it comes from.

Check the corpus with:

```
python3 tests/corpus/validate.py
```

It prints `PASS: ...` or one `FAIL:` line per problem, and exits non-zero on
failure. CI runs it (`corpus` job in `.github/workflows/ci.yml`).

## Layout

```
tests/corpus/
  README.md            this file
  index.yaml           constructs -> packets, and models -> packets
  validate.py          the checker (Python 3.8+, stdlib only)
  models/<name>/
    model.pdl          the model
    packets/<stem>.yaml one packet fixture each
```

A packet file must end in `.yaml`; the validator rejects a `packets/*.yml`
file instead of skipping it.

There are two kinds of model:

- **example**: one of the 16 models the Java tool shipped as
  `plugins/<name>_plugin`, byte for byte (`plugins/` was removed by #78; it
  is in the tree at commit f081d43). The validator fails if a model's
  sha256 is not its entry's, or if the example names, each with `_plugin`
  appended, are not the models of `tests/java-output/MANIFEST`, the record
  of the Java tool's last run, which the tests compare with. A `plugins/`
  path in a `spec`, `notes` or `source` names a file at that commit.
- **targeted**: a small model written for this corpus. Each one covers a
  group of PDL constructs (defines, Properties keys, struct element types,
  bitfields, the 26 `MMT_*` types, scopes, conditionals, expressions,
  alignment, classifynext, keyword names). Their ids are in 960-975, inside
  the third-party range of plan decision 5.

## index.yaml

- `constructs`: one entry per PDL construct of the inventory (issue #3,
  first comment, section 1). `id` names it, `inventory` points to the
  subsection, `summary` says what it is, and `covered_by` lists the packets
  that exercise it. `covered_by` is derived from the packets' own
  `constructs` lists; the validator checks that the two agree.
- `models`: one entry per model.
  - `kind`: `example` or `targeted`. `sha256`: the sha256 of the model file
    the Java tool ran on (examples only).
  - `encoding`: the model's encoding (`network`, `host`, `ascii`, `unicode`,
    or `default` when the key is omitted). The validator checks it against
    the model file.
  - `valid`: whether a correct PDL v1 front end (T1.2 parser plus T1.3
    checks) accepts the model. `invalid_reason` says why not.
  - `java`: what the Java tool (removed in #31) did with it. For examples
    this is the inventory section 4 outcome: `compiles`, `compile-fail`,
    `syntax-errors` (output written despite syntax errors) or `no-output`.
    Targeted models were only parsed: `parses` (output written, no syntax
    error) or `no-output`.
  - `spec`: the specification the fixtures follow, or "model-declared".
  - `notes`: where the model and the spec disagree.
  - `packets`: the packet stems under `packets/`.

Model status:

| model | kind | valid | java | packets |
|---|---|---|---|---|
| `abb` | example | yes | compiles | 1 |
| `arp` | example | no | compile-fail | 3 |
| `cam` | example | yes | compile-fail | 1 |
| `cotp` | example | yes | compiles | 2 |
| `cpm` | example | yes | compile-fail | 1 |
| `dns` | example | yes | compile-fail | 3 |
| `ethernet` | example | no | syntax-errors | 5 |
| `ip` | example | yes | no-output | 2 |
| `mongodb` | example | no | syntax-errors | 1 |
| `ndn` | example | yes | compile-fail | 2 |
| `quic` | example | yes | compile-fail | 1 |
| `radius` | example | yes | compile-fail | 2 |
| `s7com` | example | yes | compiles | 2 |
| `tcp` | example | yes | compile-fail | 1 |
| `topo_ind_sch` | example | yes | compile-fail | 2 |
| `tpkt` | example | yes | compiles | 2 |
| `pdl_defines` | targeted | yes | parses | 4 |
| `pdl_classifynext` | targeted | yes | parses | 5 |
| `pdl_properties_all` | targeted | yes | parses | 1 |
| `pdl_properties_minimal` | targeted | yes | parses | 1 |
| `pdl_encoding_host` | targeted | yes | parses | 1 |
| `pdl_encoding_ascii` | targeted | yes | parses | 1 |
| `pdl_encoding_unicode` | targeted | yes | parses | 1 |
| `pdl_struct_types` | targeted | yes | parses | 1 |
| `pdl_bitfields` | targeted | yes | parses | 1 |
| `pdl_types` | targeted | yes | parses | 1 |
| `pdl_sized_types` | targeted | yes | parses | 1 |
| `pdl_scopes` | targeted | yes | parses | 1 |
| `pdl_conditionals` | targeted | yes | parses | 5 |
| `pdl_expressions` | targeted | yes | parses | 1 |
| `pdl_alignment` | targeted | yes | parses | 2 |
| `pdl_keyword_names` | targeted | yes | no-output | 1 |

The invalid examples:

- `arp`: the else branch declares `ar_pro` a second time (inventory bug 12).
- `ethernet`: `sizeof (mac_addr_t)` is not a PDL type.
- `mongodb`: `offset = "POSITION_NOT_KNOWN"` is not an expression.

`ip` and `pdl_keyword_names` are valid but the Java grammar rejects them,
because it treats `id`, `len`, `offset` and the other keywords as reserved
words everywhere. T1.2 makes keywords contextual.

## Packet files

```yaml
schema: 1
id: "dns/query-a"              # <model>/<file stem>
model: "dns"
summary: "..."
constructs: [...]              # construct ids this packet exercises
parent:
  kind: "stack"                # stack | link | none
  path: ["ethernet", "ip", "udp"]
  selector: "UDP port 53"      # what makes the parent hand these bytes over
  source: "RFC 1035 section 4.2.1"
through: "udp:dport=53"        # optional, projects only: also run through the parent
bytes:                         # lower-case hex pairs; lines are concatenated
  - "1a 2b 01 00 ..."
bytes_source: "..."            # where the byte layout and values come from
expect:
  protocol: "DNS"              # the registered name: the upper-cased label
  proto_id: 11                 # the model id
  next:
    kind: "none"               # none | hook | proto
    source: "..."
  attributes:
    - name: "qdcount"
      type: "MMT_U16_DATA"
      offset: 4                # byte offset in `bytes`
      length: 2
      value: 1
      source: "RFC 1035 section 4.1.1 QDCOUNT, bytes 4-5"
note: "..."                    # optional
```

- `bytes` start at the first byte of this protocol and run to the end of
  the packet; fixtures do not carry the lower layers. The `mmt-plugin test`
  harness (T2.4) puts them behind an Ethernet header and attaches the
  protocol to Ethernet itself (EtherType 0x88b5), so a packet is tested
  without the user code's parent registration; `parent` documents the real
  transport.
- `through` (optional; read by `mmt-plugin test`, #74; no corpus fixture
  has it, and the validator does not accept it here): a selector with
  `mmt-plugin init --parent`'s syntax, `ethernet:ethertype=N`, `ip:proto=N`,
  `ipv6:proto=N`, or `udp`/`tcp` with `dport` (or `port`, the same) and
  `sport`. The test then runs a second time, as a whole Ethernet frame:
  `mmt-plugin test` puts the headers the selector names in front of `bytes`
  (IPv4 below UDP and TCP, a lone PSH/ACK TCP segment, ephemeral ports
  where none is given) and hands it to mmt-dpi's stack, so the plugin's own
  parent classification must find it, directly above the selector's
  protocol and where those headers end (`<parent>`). That run checks the
  classification and `expect.attributes`, not `expect.next`: mmt-dpi 1.10.2
  does not process a layer a plugin classified above its TCP or UDP.
- `parent.kind`:
  - `stack`: `path` lists the mmt-dpi protocols below this one, outermost
    first. The models do not declare their parent (inventory section 2:
    the parent registration is hand-written), so the stack comes from the
    specification's transport or from the hand-written source in
    `plugins/` (at commit f081d43), as `source` says.
  - `link`: the bytes are the whole frame (`ethernet`).
  - `none`: no parent is known (targeted models, `topo_ind_sch`). The harness
    hands the bytes to the plugin directly.
- `expect.next`: the result of `classify_next`.
  - `none`: no next protocol. This is the case when `encapsulation` is false,
    when no case matches, or when the matching case sets only `nextoffset`.
  - `hook`: `encapsulation` is true but there is no `classifynext` block, so
    the next protocol is user code.
  - `proto`: `proto_id` and `offset` (from the start of `bytes`) of the next
    protocol.
- `expect.attributes`: every attribute the packet says something about.
  `status` is `value` (the default), `absent` or `undefined`.
  - `value`: needs `offset`, `length` and `value`. A bitfield also has
    `bit_offset` and `bit_width`, counted from the most significant bit of
    the `length`-byte storage unit at `offset`. Optional: `text` (the bytes
    of a byte type as UTF-8), `scope` (`packet` or `session`), `note`.
  - `absent`: a conditional attribute whose branch does not hold for this
    packet. It must not be extracted.
  - `undefined`: the model gives no defined value (an invalid declaration,
    or an extraction left to a user hook). `reason` says why. An optional
    `spec` block gives the specification's `offset`, `length`, `value` and
    `byte_order` (`big`, `little` or `none`) for reviewers and for whoever
    fixes the model. The validator checks the `spec` value against the bytes
    too.

### Session files

A session test (read by `mmt-plugin test`, #99; projects only, like
`through`: no corpus fixture is one, and the validator does not accept
one) is several packets of one TCP connection, run in order by one
harness, so a plugin whose values depend on earlier packets (an opening
handshake, a message over two segments, an answer linked to its request)
is tested with its session state. It has `session` and `packets` instead
of `through`, `bytes` and `expect`:

```yaml
schema: 1
id: "chat/session-login"       # <model>/<file stem>
model: "chat"
summary: "..."
source: "..."                  # where the packets and values come from
session:
  through: "tcp:dport=6667"    # tcp, the server's port (dport or port), sport optional
  protocol: "CHAT"
  proto_id: 970
  attributes:                  # optional: checked on every packet of the plugin's
    - name: "command"
      type: "MMT_STRING_DATA"
    - name: "user"
      type: "MMT_STRING_DATA"
packets:
  - open: true                 # SYN, SYN/ACK, ACK
  - from: "client"
    bytes:
      - "55 53 45 52 20 61 6c 69 63 65 0d 0a"
    expect:
      attributes:
        - name: "command"
          value: "55 53 45 52"
        - name: "user"
          value: "61 6c 69 63 65"
  - from: "server"             # a pure ACK: no bytes
    expect: "none"
  - from: "server"
    bytes:
      - "4f 4b 0d 0a"
    expect:
      attributes:
        - name: "user"         # from the client's segment, the session's state
          value: "61 6c 69 63 65"
  - idle: 70                   # 70 s of other traffic
  - from: "server"
    retransmit: true
    bytes:
      - "4f 4b 0d 0a"
```

- `session.through`: the connection, with `init --parent`'s syntax, `tcp`
  only: `dport` (or `port`) is the server's port and is required, `sport`
  the client's (default 49152). The client is 198.18.0.1, the server
  192.0.2.1; every IPv4 and TCP checksum is right, and a frame shorter
  than 60 bytes gets Ethernet padding.
- `session.protocol`, `session.proto_id`: the plugin's, as `expect`'s.
- `session.attributes` (optional): `name` and `type` of attributes every
  packet of the plugin's checks. One a packet does not list must be
  absent there.
- `session` has no other key (`note` is a comment): a misspelt one, such
  as `atributes`, is an error, not a check turned off (#124).
- `packets`: the steps, in order, each a mapping:
  - `open: true`: the three-way handshake;
  - `idle: N`: `N` seconds (1 to 3600) of other TCP traffic, one pure ACK
    of another connection a second (the harness's packets are one second
    apart), to let mmt-dpi's timers run;
  - `from: client` or `from: server`: one segment of that side, with the
    sequence and acknowledgment numbers of a connection without loss.
    `bytes` is its TCP payload (none: a pure ACK), at most 65495 bytes,
    what one IPv4/TCP frame carries (#124). `retransmit: true` sends
    it at the sequence number of that side's previous segment with data;
    `lost: N` loses that side's next `N` bytes before it (the capture never
    had them); `back: N` sends it `N` bytes before that side's next
    sequence number without moving it (a segment that arrives late, after
    the ones that followed it, or one sent over bytes already sent), and it
    has bytes, at most `N` of them; `N` is at most what that side has sent
    or lost so far. One step gives at most one of `retransmit`, `lost` and
    `back`. `expect` is `"none"` (not the plugin's packet) or a mapping
    with `attributes`, as a packet file's `expect.attributes`, except that
    `offset` and `length` are optional (a value can come from an earlier
    packet) and so is `type` for an attribute `session.attributes` lists.
    Without `expect`, the packet is the plugin's, with every attribute of
    `session.attributes` absent. `text` and `note` are comments.

  The packets of `open` and `idle` steps must not be the plugin's.
- Every packet of the plugin's must be classified directly above TCP, where
  the TCP header ends (`<parent>`), through mmt-dpi's stack and the
  plugin's own parent classification; its next protocol is not checked.
  A failure names the step it is in (`packet` in `result.packets[].failures`).

### Value kinds

| types | `value` |
|---|---|
| `MMT_U8_DATA`, `MMT_U16_DATA`, `MMT_U32_DATA`, `MMT_U64_DATA`, `MMT_DATA_CHAR` (1 byte), `MMT_DATA_PORT` (2 bytes) | unsigned integer |
| `MMT_DATA_MAC_ADDR` | `"aa:bb:cc:dd:ee:ff"` |
| `MMT_DATA_IP_ADDR`, `MMT_DATA_IP_NET` | dotted quad |
| `MMT_DATA_IP6_ADDR` | RFC 5952 text |
| `MMT_DATA_POINTER` | the offset it points at (equals `offset`) |
| every other type | the bytes, as hex pairs |

## Semantics

These are the rules a correct generator follows and the fixtures assume. They
restate inventory section 1 without the Java bugs. Sources that say
"corpus rule" point here.

- **Byte order.** `encoding = "network"`: integers wider than one byte are
  big-endian. `encoding = "host"`: fixed little-endian, whatever machine
  runs the plugin (see the decided rules below). `ASCII`, `UNICODE` or no encoding:
  the fixtures use only single-byte and byte-copy types, whose values do not
  depend on byte order (inventory bug 10).
- **Byte copies.** Addresses and all non-integer types are copied byte for
  byte in every encoding. `MMT_DATA_IP_ADDR` is never swapped (bug 25).
- **Struct layout.** Fields are packed in declaration order, without C
  padding (bug 4). Widths are the PDL ones (inventory section 1, Data
  types): `int`, `long`, `uint32_t` 4; `short`, `uint16_t` 2; `char`,
  `u_char`, `uint8_t` 1; `T*` 4; `MMT_DATA_MAC_ADDR` 6, `MMT_DATA_IP_ADDR` 4,
  `MMT_DATA_IP6_ADDR` 16, `MMT_U64_DATA` 8. All struct integer types are
  unsigned. A `T*` field reads as `MMT_DATA_POINTER`. A `struct X` field
  covers `sizeof(struct X)` bytes and reads as `MMT_BINARY_DATA` (bug 8).
  The grammar's widths for the other `MMT_*` types are SDK struct sizes
  (`MMT_BINARY_DATA` 68, `MMT_DATA_PATH` 68) or 0, not wire sizes, so the
  corpus never puts them in a struct or in `sizeof`. `sizeof(MMT_U16_DATA)`
  is 2.
- **Bitfields.** A run of bitfields fills one storage unit of its declared
  type. Fields are numbered from the most significant bit, in declaration
  order, of the unit read in the model's byte order: the order protocol
  specifications draw them in. The next field starts after the unit (bugs 2
  and 3).
- **Offsets and alignment** (inventory section 1, Offset and alignment). A
  running offset R starts at 0.
  - An attribute is *constant* when both `offset` and `data_len` are integer
    expressions without `val`, `sizeof`, `offset()` or `len()`. While
    alignment is on, a constant attribute sits at R + its declared offset,
    and R grows by its length.
  - A struct adds R to each field's offset, and R grows by the struct size.
  - The first attribute that is not constant (or has no offset or length)
    turns alignment off. From then on every offset is literal, including a
    struct's in-struct offsets.
  - After `if/else`, R and the alignment state are the else branch's; after
    an `if` without `else`, they are the ones from before the `if`. So a
    non-constant attribute inside an if branch turns alignment off only
    inside that branch (no fixture depends on this yet).
  - `pdl_alignment` exercises each rule; most other models start with a
    non-constant attribute so that their offsets are literal.
- **Expressions.** Integer arithmetic with C precedence and truncating
  division. Comparisons and `AND`/`OR` have their usual meaning (bugs 5
  and 6). `val(x)` is the value of attribute x as extracted, wherever x is
  (bug 11). `sizeof(T)` is the PDL width of T, so `sizeof(char)` is 1
  (bug 7), and `sizeof(struct X)` is the packed size. `offset(X)` and
  `len(X)` are attribute X's byte offset and length (bug 19).
  `ntohs`/`ntohl` of a literal is an unconditional byte swap, so
  `ntohs(0x0300)` is 3.
- **Conditionals.** A branch's attributes are present only when its
  condition holds. When none holds, they are absent (bug 13).
- **Scopes.** `packet` means `SCOPE_PACKET` and `session` means
  `SCOPE_SESSION`. An omitted scope means `SCOPE_PACKET` (bug 9). Session
  attributes are checked on a one-packet session, so they hold that packet's
  value.
- **Omitted `offset` or `data_len`.** An attribute without `offset` is a
  user hook: it is `undefined` in the fixtures (radius, `pdl_scopes`
  `no_off`). An attribute without `data_len` but with an offset has the
  width of its fixed-width type (`pdl_scopes` `no_len`). Either one stops
  alignment.
- **classifynext.** C `switch` semantics: a case without `break` falls
  through. `nextencaps` sets the next protocol and marks it classified;
  `nextoffset` sets its offset. A case that sets no `nextencaps` classifies
  nothing. The legacy grammar needs a `default:` (or `break }` on one line)
  before the switch's closing brace, so the targeted models end with
  `default: break`.
- **Protocol name.** The registered name is the upper-cased `label`
  (inventory section 1, Properties).

### Decided rules

The inventory left these rules open. The corpus follows them, and T1.2/T1.3
implement them.

- **Bitfield order** (decided by the maintainer, 2026-11-10, PR #35 review). Bitfields are numbered from the most significant
  bit of the storage unit, read in the model's byte order. This is the only
  rule. The `ip` model's `ihl:4, version:4` is a model bug, fixed when the
  examples are ported (T5.1, `examples/ip`). Bitfields are a declared divergence from Java
  for T1.6. A per-struct `bit_order` key may be added later, defaulting to
  `msb`. The dns, ip, tcp, topo_ind_sch and pdl_bitfields values depend on
  this rule.
- **`host` encoding** (decided by the maintainer, 2026-11-10, PR #35 review). `host` means fixed little-endian, not the order
  of the machine that runs the plugin. `little` is accepted as an alias.
- **Omitted scope** (decided by the maintainer, 2026-11-10, PR #35 review). An omitted scope means packet. T1.3 may warn about
  it.
- **Omitted `data_len`** (decided by the maintainer, 2026-11-10, PR #35 review). An omitted `data_len` means the type's width
  for fixed-width types. T1.3 reports an error for types without a fixed
  width (`MMT_BINARY_DATA`, `MMT_STRING_DATA`, ...).
- **`struct X` fields** (decided by the maintainer, 2026-11-10, PR #35 review). A `struct X` field covers `sizeof(struct X)`
  bytes, read as `MMT_BINARY_DATA`. `X` must be defined before use.
- **`T*` fields** (decided by the maintainer, 2026-11-10, PR #35 review). A `T*` field is 4 bytes on the wire, read as
  `MMT_DATA_POINTER`. "Value = offset" is a harness convention: the T2.4
  harness checks a pointer attribute by the offset it points at, since the
  runtime pointer is 8 bytes on 64-bit hosts. T1.3 discourages `T*` in new
  models.
- **`ntohs`/`ntohl` of a literal** (decided by the maintainer, 2026-11-10, PR #35 review). It is an unconditional byte swap.
- **R after if/else** (decided by the maintainer, 2026-11-10, PR #35 review). After `if/else`, the running offset R and the
  alignment state are those of the else branch (Java behaviour, kept). T1.3
  warns when a constant, aligned attribute follows an if/else whose branches
  advance R by different amounts.
- **`offset()`/`len()`** (implemented by T1.3, #51, as the corpus fixed it;
  moved here from the open rules by #53). `offset(X)` and `len(X)` are
  attribute X's byte offset and length as analysed: an aligned X's
  offset is its absolute one (R + its declared offset), and they fold to a
  number when X's offset or length is constant (`pdl_expressions`:
  `offset(hexoff) + 1` is 11, `len(hexoff)` is 2). X must be declared
  before the expression and visible there (an attribute of an `if` branch
  only inside that branch, `model.conditional-reference`); an X without an
  offset (a user hook) is the error `model.hook-reference`. An attribute
  whose `offset` or `data_len` uses either one is not constant, so it turns
  alignment off, even when it folds.
- **Literal in-struct offsets after alignment stops** (implemented by T1.3,
  #51, as the corpus fixed it; moved here by #53). Once alignment is off, a
  struct no longer adds R: in PDL v1 it sits at offset 0, so each field is
  at its in-struct offset (`pdl_alignment`'s `t0` is at 0, after the
  literal `lit` at 11); a `plugin.yaml` struct sits at its own `offset`.
- **Field names that are C keywords** (implemented by T1.5; moved here by
  #53). A field or attribute named like a C keyword (`sizeof`, `int`,
  `char` in `pdl_keyword_names`) gets a trailing underscore in the
  generated C (`sizeof_`); its alias is unchanged
  (`docs/behaviour-changes.md`, row 19).

The validator checks each expected value against the packet bytes at the
offset the fixture states, not that offset against the model: the T1.x
layout and golden tests must check fixture offsets against the model.

## Sources

Each `source` field names either a specification section (`RFC 1035
section 4.1.1`, `ETSI TS 102 894-2 V1.3.1 ItsPduHeader`, ...) or says
`model-declared` or `corpus rule`.

- The bytes are spec-conformant packets. Where a spec gives an example, the
  fixture copies it (radius: the RFC 2865 section 7.1 hex dumps). Otherwise
  the bytes are packed from field values chosen per the spec, with
  documentation addresses (RFC 5737, RFC 3849, RFC 7042).
- The expected value is what the model, as written, extracts under the rules
  above. When the model's field is the spec's field at that position, the
  source is the spec. When the model reads bytes the spec gives another
  meaning, the source starts with `model-declared` and names the spec field
  actually there (tcp fields `a` to `h`, the cam body, quic, the swapped
  `ihl`/`version` nibbles of ip, cpm `generationTime`).
- Models with no public spec (abb, topo_ind_sch, the targeted models) are
  `model-declared` throughout. s7com follows the de-facto layout of the
  Wireshark S7comm dissector, since Siemens publishes no specification.

## File format

The YAML files use a strict subset so that `validate.py` needs no
third-party parser. A full YAML parser reads every such file to the same
data.

- Block mappings and block sequences, indented with spaces.
- Scalars: double-quoted strings (JSON escapes), decimal integers without
  leading zeros, `true`, `false`, `null`, and plain words matching
  `[A-Za-z_/][A-Za-z0-9_./+-]*` other than YAML 1.1 booleans (`yes`, `no`,
  `on`, `off`, `y`, `n`).
- Flow sequences of scalars (`[a, "b"]`).
- Full-line `#` comments, and `#` comments after a value.
- No anchors, tags, block scalars, multiple documents, tabs or CRLF.

## Adding a fixture

1. Put the model in `models/<name>/model.pdl` and add its entry to
   `index.yaml`. A new model is `targeted`: the 16 examples are the
   models of the Java tool's last run, all in the corpus.
2. Build the bytes from the specification and write
   `models/<name>/packets/<stem>.yaml`, with a `source` on every value.
3. List the constructs the packet exercises, and add the packet id to each
   construct's `covered_by` in `index.yaml`.
4. Run `python3 tests/corpus/validate.py`.
