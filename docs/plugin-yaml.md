# plugin.yaml

`plugin.yaml` is the protocol model of an mmt-plugin project (plan task T3.1,
#24). Every command that reads a model (`generate`, `validate`, `build`,
`test`, `install`, `doctor`) reads it, and PDL v1 models too: both are read
into the same typed model, so a model generates the same C from either.

The format is defined by its JSON Schema,
[`src/mmt_plugin/schemas/model/v1/plugin.json`](../src/mmt_plugin/schemas/model/v1/plugin.json)
(draft 2020-12). The schema ships in the `mmt_plugin` package, so in each
release, at `mmt_plugin/schemas/model/v1/plugin.json`. This page describes
it; the schema is the reference, and
[`model-reference.md`](model-reference.md), generated from it, lists every
key.

## Example

```yaml
schema: 1
protocol:
  label: demo            # mmtp_demo.so; registered name DEMO
  id: 960                # third-party ids: 950-999
  encapsulation: true
  encoding: network      # big-endian integers
sdk:
  profile: "1.10.2"      # optional: the SDK profile to generate for
defines:
  KIND_DATA: 2
parents:
  - protocol: ethernet   # attached by the generated code
    classify:
      match:
        - {offset: 12, length: 2, value: 0x88b5}   # the EtherType
      offset: 14         # demo starts 14 bytes after the Ethernet header's start
  - protocol: udp        # attached by your code (demo_hook_register_parents)
attributes:
  - struct: demo_hdr     # at offset 0: version, kind, length
    fields:
      - type: uint8_t
        bits:
          - {name: version, width: 4}
          - {name: flags, width: 4}
      - name: kind
        type: uint8_t
      - name: length
        type: uint16_t
  - if: val(kind) == 1
    then:
      - name: payload    # variable length: read from the packet
        type: MMT_BINARY_DATA
        offset: 4
        length: val(length) - 4
  - name: session_bytes
    type: MMT_U32_DATA
    scope: session       # no offset: extracted by a user hook
classify_next:
  switch: val(kind)
  cases:
    - case: KIND_DATA    # a define
      next: 955          # the next protocol's id
      offset: 4
```

## Keys

| Key | Required | Meaning |
|---|---|---|
| `schema` | yes | `1`, the format's version. A reader refuses another one. |
| `protocol` | yes | `label` (a C identifier), `id` (a positive integer), and the optional flags `context`, `session_context`, `session`, `encapsulation` (`false` by default) and `encoding` (`network`, `host` or its alias `little`, `ASCII`, `UNICODE`): PDL v1's Properties block. |
| `sdk.profile` | no | The SDK profile to generate for, below `--sdk-profile` and `MMT_PLUGIN_SDK_PROFILE` (`docs/design/cli.md`, section 9). Quote it: `"1.10.2"`. |
| `offsets` | no | `absolute` (the default) or `running`, below. |
| `defines` | no | Named numbers, in order: a number, or the name of an earlier define or of an SDK protocol id macro (`PROTO_TCP`). A case value or a `next` may name one; an expression may not (PDL v1). |
| `parents` | no | The protocols this one runs on, below. |
| `attributes` | no | The attributes, structs and conditionals, in order. |
| `classify_next` | no | The classification of the next protocol: `switch` (an expression), `cases` (each with `case`, a number or a define, and optional `next`, `offset`, `fallthrough`) and `default` (optional `next`, `offset`). `next` sets the next protocol's id and classifies it, `offset` its offset; `fallthrough: true` goes on to the next case, as a C `case` without `break`. |

Nothing machine-specific (an SDK prefix, a compiler) goes in `plugin.yaml`,
which is committed: every mapping is closed, and an unknown key is an error.

### Elements of `attributes`

- An **attribute**: `name`, `type` (an `MMT_*` data type), and optional
  `offset`, `length` and `scope` (`packet`, the default, or `session`).
  Without `offset`, the extraction is a user hook. Without `length`, a
  fixed-width type has its width.
- A **struct** (it has a `struct` key): `struct` (its name), optional
  `offset`, and `fields`. Fields are packed in order, without padding, and
  each one is an attribute. A field is `{name, type}`, or a run of bitfields
  `{type, bits: [{name, width}, ...]}` that fills one storage unit of `type`
  from its most significant bit, in the model's byte order. A field `type` is
  `int`, `long`, `uint32_t` (4 bytes), `short`, `uint16_t` (2), `char`,
  `u_char`, `uint8_t` (1), any of them or `void` followed by `*` (a 4-byte
  pointer, read as `MMT_DATA_POINTER`), a fixed-width `MMT_*` type, or
  `struct X` for an earlier struct.
- A **conditional** (it has an `if` key): `if` (an expression), `then` and
  optional `else`, each a list of elements that exist only when the
  condition holds (or does not).

### Expressions

`offset`, `length`, `if`, `switch` and a case's `offset` are a number or a
PDL v1 expression written as a string: numbers (decimal or `0x` hex),
`+ - * /`, the comparisons `== != > < >= <=`, `AND`, `OR`, parentheses, and
`val(x)` (attribute x's value), `offset(x)`, `len(x)`, `sizeof(T)`,
`ntohs(n)`, `ntohl(n)`. An attribute whose `length` reads the packet
(`val(length) - 4`) is a **variable-length attribute**, of a byte type
(`MMT_BINARY_DATA`, `MMT_BINARY_VAR_DATA`, `MMT_STRING_DATA`).

### Offsets

With `offsets: absolute` (the default), every offset counts from the start
of the protocol, and a struct's `offset` (0 by default) is where its first
field is. With `offsets: running`, offsets follow PDL v1's running offset
(`tests/corpus/README.md`, Offsets and alignment): a constant attribute's or
struct's offset is relative to the end of the constant ones before it, until
the first attribute that is not constant, and a struct has no `offset`.

### Parents

Each parent names a protocol by its registered name, case-insensitively: an
SDK protocol (`ethernet`, `udp`, ...) or an installed plugin's. `validate`
checks that each one exists (`parents-exist`).

- With `classify`, the generated code attaches the protocol: when every
  `match` holds (the `length`-byte unsigned integer at `offset` from the
  start of the parent, in network byte order, equals `value`; `length` is 1
  to 8), the protocol is classified, starting `offset` bytes after the start
  of the parent. `weight` (0 to 100, default 5) orders the parent's
  classification functions, lowest first; mmt-dpi documents 0 to 9 and 90 to
  100. The parent must be a protocol of the SDK profile.
- Under `tcp`, `classify` can name ports instead: `port` (the source or
  the destination port), `sport` (the source port), `dport` (the
  destination port), at least one, all of them holding, and no `offset`.
  The protocol then starts with the TCP payload, after the header and its
  options (the header's data offset says where), and is classified only in
  a segment with a payload; where the segment ends comes from the IP
  header, not from the capture, so Ethernet padding after a short segment
  is not a payload. Its optional `match` tests the payload: each `offset`
  counts from the start of the payload, where the protocol starts. A port
  under any other parent is `model.classify-port`.

  ```yaml
  parents:
    - protocol: tcp
      classify:
        port: 4840                                # either port
        match:
          - {offset: 0, length: 3, value: 0x48454c}   # the payload starts with HEL
  ```

- Without `classify`, your code attaches the protocol, in
  `<label>_hook_register_parents` (`src/<label>_impl.c`), which the
  generated init calls after attaching the others.

## The YAML subset

`mmt-plugin` reads `plugin.yaml` without a YAML library, so a file must be
in this subset of YAML, which every YAML 1.1 and 1.2 reader reads the same
way:

- block mappings and block lists, indented with spaces; one-line flow lists
  (`[a, b]`) and mappings (`{name: a, width: 4}`) of values, with a space
  after each `:` of a flow mapping (`{name: a}`, not `{name:a}`, which YAML
  1.2 reads as the key `name:a`); `#` comments; an optional `---` before the
  document;
- plain, `'single'` and `"double"` (JSON escapes) quoted values. A decimal
  integer (without a leading zero) or a `0x` hex one is a number; `true`,
  `false` are booleans; anything else is a string. A value that YAML 1.1 and
  1.2 read differently (`yes`, `off`, `010`, `0o17`, `-0x10`, `1:30`) must
  be quoted;
- no anchors, aliases, tags, block scalars (`|`, `>`) or second document.

## Errors

Every error is a diagnostic at its node's line and column, exit 3:

- `model.yaml-syntax`: the text is not in the subset (the first error only);
- `model.schema`: the document does not follow the schema (every violation,
  in document order), or a struct has an `offset` with `offsets: running`;
- `model.syntax.*`: an expression does not parse, at its place in the
  value;
- then the semantic checks of any model (`model.duplicate-name`,
  `model.unknown-attribute`, ...), and for a parent with `classify`
  `model.unknown-parent` when the SDK profile does not have it, and
  `model.classify-port` for ports under a parent other than `tcp`.

```
plugin.yaml:4:7: error: protocol.id: expected an integer, found a string (`960`) [model.schema]
  hint: The protocol id; third-party plugins use 950 to 999.
```

## From PDL v1

`mmt_plugin.pluginyaml.dumps(analysed)` writes an analysed model of either
format as `plugin.yaml`; every corpus model round-trips through it
(`tests/unit/pluginyaml/test_roundtrip.py`). With absolute offsets it writes
the offsets the semantic passes computed for the attributes and structs the
running offset placed; `offsets=Offsets.RUNNING` keeps the offsets as
written.

`mmt-plugin import PDL` (#25) converts a PDL v1 model to `plugin.yaml`
(`<project>/plugin.yaml`, or `-o FILE`; `-o -` prints it), and `generate`
gives the same C from both. It analyses the model against the newest
bundled SDK profile, pins no `sdk.profile`, and writes absolute offsets.
Comments and the spelling of a packet scope are not kept: an omitted
`scope` is packet. A model error stops it (exit 3, nothing written), except
for the constructs below, which the Java tool accepted. Each is a warning
whose code starts with `model.legacy-`, and which says what the Java tool
did; `--strict` makes them fail. "Bug" is the number in section 5 of the
[inventory](legacy/java-generator-inventory.md), and "Row" the row of
[`behaviour-changes.md`](behaviour-changes.md) that pins what mmt-plugin
does instead.

| Code | The construct | Bug | Row |
|---|---|---|---|
| `model.legacy-sdk-conflict` | A protocol id or name that the SDK already has. The model is converted; `generate` refuses it. | 23 | 2 |
| `model.legacy-duplicate-name` | A name used twice, where the second is conditional or differs only in case. The analysis cannot place the attributes, so the model is written with `offsets: running`, as PDL v1 placed them, until one is renamed. | 12, 16 | 30, 31 |
| `model.legacy-bitfield-order` | A bitfield run: numbered from the most significant bit of its unit, not in the C compiler's order (least significant bit first with gcc on x86). | – (plan decision 8) | 17 |
| `model.legacy-bitfield-offset` | A struct line that starts with a plain field after a line that ends with a bitfield, or an element the running offset places after a struct with bitfields (each branch of an `if` from the offset before it) when the Java tool's running offset passed that struct by another amount than its size: it added each field's type length, a bitfield's at its type's full width, so a struct whose runs each have one field (`uint8_t a:4, b, c:4;`) gets no warning. The Java tool placed both elsewhere. | 2, 3 | 22, 23 |
| `model.legacy-constant-folding` | An offset, `data_len` or `nextoffset` that the Java tool folded to a constant because its last operand is a literal or `ntohs`/`ntohl` (and it is not a comparison), but that is not one (`val(x) - 4` became -4), or is another number: it read `offset()` and `len()` as 0, `a AND b` as `a > 0`, and did not swap the bytes of `ntohs`/`ntohl`. | 5, 19 | 25, 33, 34 |
| `model.legacy-comparison` | Such an expression whose value changes because the Java tool folded `>`, `<`, `>=` and `<=` as `!=`. A comparison it wrote into the C as text (an `if` condition, an expression it did not fold) was right. | 6 | 26 |
| `model.legacy-sizeof` | `sizeof` of a C or MMT type that the Java tool wrote into the C (an `if` condition, the switch subject, an expression it did not fold) as `sizeof(MMT_U8_DATA)` and the like, the size of an enum constant, 4: `sizeof(char)` is 1, `sizeof(short)` 2, `sizeof(MMT_DATA_MAC_ADDR)` 6. | 7 | 27 |
| `model.legacy-classifynext` | A `classifynext` block without `encapsulation = "true"`, which the Java tool dropped. | 21 | 15 |
| `model.legacy-ip-addr` | An `MMT_DATA_IP_ADDR` of a model in network byte order that the Java tool byte-swapped: one whose offset or `data_len` it did not fold, and every one in an `if` block. | 25 | 16 |

The other bugs of the inventory are not in the model (22, 24) or made
output that did not compile or did not work, so no working model relied on
them; the analysis reports what is still wrong with its own codes. The analysis warnings are kept, apart from
`model.default-scope`.

## From a capture

`mmt-plugin scaffold --from-pcap PCAP --parent SELECTOR` (#26) drafts a
`plugin.yaml` from captured traffic: it writes `plugin.proposed.yaml` next
to `plugin.yaml` (which it never edits), with the label and id of the
project's model, the parent, and a field skeleton of the first bytes every
payload has, plus one packet test per payload whose values that proposal
extracts. Rename the fields, check them against the protocol's
specification, and copy what you keep into `plugin.yaml`. The rules are in
[`docs/design/cli.md`](design/cli.md), "Details fixed by #26".
