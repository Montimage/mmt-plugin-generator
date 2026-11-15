# Drafting plugin.yaml and the packet tests

`plugin.yaml` is described in [`docs/plugin-yaml.md`](../../../docs/plugin-yaml.md);
its JSON Schema, `src/mmt_plugin/schemas/model/v1/plugin.json`, is the
reference. Packet tests are corpus schema 1 files,
[`tests/corpus/README.md`](../../../tests/corpus/README.md), "Packet files".
This page says how to get from each starting point to both.

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
  protocol (a UDP or TCP port, an EtherType): the match reads the parent's
  header, in network byte order. Without `classify`, attach the protocol
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

## From a capture

`scaffold --from-pcap` writes `<project>/plugin.proposed.yaml` and one
packet test per payload, `<project>/tests/<label>-pcap-<n>.yaml`, whose
values are what the proposal extracts. It never edits `plugin.yaml`.

1. Read the proposal: each field has a comment with what was seen
   (constant, varies, the payload length).
2. Match the fields with what you know of the protocol (a spec, a
   description, the port). Rename them (`field_0` to `version`), merge or
   split them, and delete those that are payload, not header.
3. Copy the result over `plugin.yaml`, pin `sdk.profile`, and make the same
   renames and deletions in the `tests/<label>-pcap-<n>.yaml` files.
4. Delete `tests/<label>-basic.yaml`, which `init` wrote for its sample
   header.

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
3. Add the parents (PDL v1 has none) and pin `sdk.profile`.
4. Write packet tests from the protocol's spec. The corpus,
   `tests/corpus/models/<name>/packets/`, has some for the models of
   `plugins/`; change their `protocol` and `proto_id` to yours.
