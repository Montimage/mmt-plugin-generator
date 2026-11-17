# Drafting plugin.yaml and the packet tests

`plugin.yaml` is described in [`docs/plugin-yaml.md`](../../../docs/plugin-yaml.md);
its JSON Schema, `src/mmt_plugin/schemas/model/v1/plugin.json`, is the
reference. Packet tests are corpus schema 1 files,
[`tests/corpus/README.md`](../../../tests/corpus/README.md), "Packet files".
This page says how to get from each starting point to both, and how to
change them in an existing project.

## From a protocol specification

Write down, for each field of the header: its name, its offset from the
start of the protocol, its width in bits or bytes, and when it is present.
Then:

```yaml
schema: 1
protocol:
  label: telem           # mmtp_telem.so; registered name TELEM
  id: 963                # 950-999
  encoding: network      # big-endian integers: almost every spec
sdk:
  profile: "1.10.2"      # the profile you generate for; quote it
parents:
  - protocol: udp
    classify:            # the generated code attaches the protocol
      match:
        - {offset: 2, length: 2, value: 5684}   # UDP destination port
      offset: 8          # the protocol starts after the 8-byte UDP header
attributes:
  - struct: telem_hdr    # consecutive fixed fields, packed from offset 0
    fields:
      - type: uint8_t
        bits:            # numbered from the most significant bit
          - {name: version, width: 4}
          - {name: flags, width: 4}
      - name: msg_type
        type: uint8_t
      - name: length
        type: uint16_t
  - if: val(msg_type) == 1
    then:
      - name: payload
        type: MMT_BINARY_DATA
        offset: 8
        length: val(length) - 8
```

- **Types.** In a struct: `uint8_t`, `uint16_t`, `uint32_t` (1, 2, 4
  bytes), or a fixed-width `MMT_*` type. As an attribute: `MMT_U8_DATA`,
  `MMT_U16_DATA`, `MMT_U32_DATA`, `MMT_U64_DATA`, `MMT_DATA_MAC_ADDR`,
  `MMT_DATA_IP_ADDR`, `MMT_DATA_IP6_ADDR`, and the byte types
  `MMT_BINARY_DATA`, `MMT_BINARY_VAR_DATA`, `MMT_STRING_DATA` for runs of
  bytes. A field that is not a whole number of bytes is a bitfield.
- **Offsets** are absolute: from the start of the protocol. A struct starts
  at its `offset` (0 by default); an attribute has its own.
- **Bitfields** fill one storage unit from its most significant bit: in a
  byte `vvvvffff`, `version` comes first. Getting this backwards is the
  most common `test.packet-failed`.
- **Present only sometimes**: put the attributes in an `if` with `then`
  (and `else`). A test lists such an attribute with `status: "absent"`
  when it is not there.
- **Variable length**: a `length` that reads the packet (`val(length) - 8`)
  needs a byte type.
- **Computed per session or by your code**: an attribute without `offset`
  is extracted by a hook, `<label>_hook_extract_<name>` in
  `src/<label>_impl.c`. `build` fails with `build.missing-hook` until you
  define it; its hint gives the declaration.
- **Parents.** Use `classify` when the parent's header says it is this
  protocol (a UDP port, an EtherType): the match reads the parent's
  header, in network byte order. Under `tcp`, `classify` names the port
  instead (`port`, either one, `sport` or `dport`), with optional `match`es
  whose offsets count from the start of the payload; the generated code
  reads the TCP header's length. Without `classify`, attach the protocol
  yourself in `<label>_hook_register_parents`. `validate` checks that the
  parent exists.
- **Next protocol**: `classify_next` with `protocol.encapsulation: true`.
- **Names**: lower case, unique case-insensitively, C identifiers.

Write one packet test per example the spec gives, in
`tests/<label>-<example>.yaml`:

```yaml
schema: 1
id: "telem/reading"
summary: "A reading: version 1, flags 2, sequence 42, a 4-byte payload"
bytes:
  - "12 01 00 0c 00 00 00 2a de ad be ef"
expect:
  protocol: "TELEM"      # the label, upper case
  proto_id: 963
  next:
    kind: "none"         # none, hook, or proto with proto_id and offset
  attributes:
    - name: "version"
      type: "MMT_U8_DATA"   # a uint8_t field or bitfield is MMT_U8_DATA
      offset: 0
      length: 1
      value: 1
    - name: "payload"
      type: "MMT_BINARY_DATA"
      offset: 8
      length: 4
      value: "de ad be ef"  # byte types: hex pairs
```

The bytes are the protocol's own, from its first byte: no Ethernet, IP or
UDP header (the test harness attaches the protocol to Ethernet itself).
The expected values come from the spec. A test that passes because its
values were copied from the plugin's output tests nothing.

To check `parents:` too, add `through` to one packet test: the parent as
an `init --parent` selector, e.g. `through: "udp:dport=4433"` (also
`ethernet:ethertype=N`, `ip:proto=N`, `ipv6:proto=N`, `tcp:dport=N`; `udp`
alone for a `classify` that matches the payload). `test` then also runs the
bytes behind the headers it names, through mmt-dpi's stack: a second
`result.packets` entry with `through`, which fails `<protocol>` (not
classified) when the parent's classification does not match the packet and
`<parent>` when the plugin starts at another protocol or offset. Fix
`parents:` (or the hook), not the selector, unless the selector contradicts
the spec. That run does not check `next`.

When a value depends on earlier packets of the connection (a handshake, a
message over two segments, an answer linked to its request), write a
session test, `tests/<label>-session-<case>.yaml`, from the spec's
exchange: `session` (`through: "tcp:dport=N"`, the protocol, its id, and
the `attributes` every packet of the plugin's checks, absent where a
packet does not list them) and `packets`, the steps in order: `open: true`
(the handshake), `from: client` or `from: server` with the segment's
`bytes` and its `expect` (`"none"`, or its `attributes`, without
`offset`/`length` when the value comes from an earlier packet),
`retransmit: true`, `lost: N`, and `idle: N` seconds. `test` builds the
TCP frames and runs them in one harness, through the plugin's parent;
each failure names its step (`packet`). The format is in
`tests/corpus/README.md`, "Session files".

## From a capture

`scaffold --from-pcap` writes `<project>/plugin.proposed.yaml` and one
packet test per payload, `<project>/tests/<label>-pcap-<n>.yaml`, whose
values are what the proposal extracts. It never edits `plugin.yaml`.
Under a `tcp` parent the payloads are each segment's new bytes in stream
order; when each session starts with a text handshake (an HTTP upgrade),
pass `--skip-until 0d0a0d0a` so that only the protocol's own bytes are
sliced. When tshark is on `PATH` and dissects the protocol, `--tshark`
drafts the fields from tshark's dissection instead, named after its fields
(`--protocol` when it dissects several at the payloads' start,
`--decode-as` for a port it does not know), and the tests expect the
values tshark decodes: still a draft, to check against the spec.

1. Read the proposal: each field has a comment with what was seen
   (constant, varies, the payload length). A byte cut into bit fields is a
   struct `bits_<offset>` of `field_<offset>_b<bit>` fields.
2. Match the fields with what you know of the protocol (a spec, a
   description, the port). Rename them (`field_0` to `version`), merge or
   split them, and delete those that are payload, not header.
3. Copy the result over `plugin.yaml`, pin `sdk.profile`, and make the same
   renames and deletions in the `tests/<label>-pcap-<n>.yaml` files.
4. Delete `tests/<label>-basic.yaml`, which `init` wrote for its sample
   header, if `init` wrote it in this session.

The tests `scaffold` wrote check only that the plugin extracts the
captured bytes; they cannot tell a wrong field boundary. Add a test from
the spec when you have one.

## From a legacy PDL v1 model

`import` converts the model to `plugin.yaml` with absolute offsets and no
pinned profile. Then:

1. Read each `model.legacy-*` warning; the table in `docs/plugin-yaml.md`,
   "From PDL v1", says what the Java tool did and what the model does now.
2. Old models often have an id or a label the SDK already has
   (`model.legacy-sdk-conflict`): `validate` fails with `model.id-taken`
   or `model.name-taken`. Use the label and id you gave `init`.
3. Put back the `parents:` and the `sdk.profile` pin of `init`'s
   `plugin.yaml` (PDL v1 has no parent, and `import` pins no profile).
4. Write packet tests from the protocol's spec. The corpus,
   `tests/corpus/models/<name>/packets/`, has some for the Java tool's
   example models (`kind: example` in `tests/corpus/index.yaml`); change
   their `protocol` and `proto_id` to yours.

## Updating an existing project

The project's `plugin.yaml` and its packet tests describe what the plugin
does today. An update changes the model and adds tests; it keeps
`protocol.label`, `protocol.id`, `sdk.profile` and `parents:` unless the
request changes them, and it keeps every test the project has.

- **Add a field.** Write it as for a new protocol, at the offset and with
  the type the revision gives; a field that only some messages carry goes
  in an `if` on what tells them apart. The tests the project has do not list
  it, and need no change.
- **Change a field** (its offset, type or width). The tests that read it
  expect the old layout. When the request says the old one was wrong, the
  revision contradicts those tests: stop and report them, with the passage
  of the spec, before you change the model.
- **Remove a field.** Remove it from `plugin.yaml` and from each test that
  lists it: a test may lose an attribute that the model also loses.
- **Rename a field.** Rename it in `plugin.yaml` and in every test that
  lists it, keeping its expected values.
- **New behaviour gets new tests.** Write a test for each example the
  revision adds, in a new file, `tests/<label>-<example>.yaml`, with an `id`
  no other test of the project has, and the values the revision gives.
  Never edit an existing test's bytes or expected values to match the
  revision.

From a new capture, never let `scaffold` write into the project: it would
want to replace `plugin.proposed.yaml` and the `tests/<label>-pcap-<n>.yaml`
of an earlier run. Scaffold into a scratch directory outside the project,
reading the project's model for the label and the id:

```sh
mmt-plugin -C <scratch> --json scaffold --from-pcap <pcap> --parent <selector> --model <project>/plugin.yaml
```

It writes `<scratch>/plugin.proposed.yaml` and
`<scratch>/tests/<label>-pcap-<n>.yaml`, and nothing in the project. Then:

1. Compare the proposal with `plugin.yaml`, and fold the fields that are
   new into `plugin.yaml` by hand, named after the spec.
2. Copy the drafted tests you keep into `<project>/tests/`, under file
   names and `id`s that no test of the project has (for example
   `tests/<label>-pcap2-<n>.yaml` and `"<label>/pcap2-<n>"`), and make the
   same renames and deletions in them as in the model.
3. Never write over the project's `plugin.proposed.yaml` or its tests, and
   never `--force` over a file you did not write.
