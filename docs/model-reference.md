# plugin.yaml reference

<!-- Generated from src/mmt_plugin/schemas/model/v1/plugin.json by `uv run python -m mmt_plugin.pluginyaml.reference --write docs/model-reference.md`. Do not edit: edit the schema and regenerate. -->

Every key of `plugin.yaml`, generated from its JSON Schema, [`src/mmt_plugin/schemas/model/v1/plugin.json`](../src/mmt_plugin/schemas/model/v1/plugin.json) (mmt-plugin plugin.yaml, schema 1). [`plugin-yaml.md`](plugin-yaml.md) explains the format, with an example, the expressions, the offsets and the YAML subset; [the user guide](user-guide.md) shows how to write one.

## Contents

- [`plugin.yaml`](#pluginyaml)
- [`sdk`](#sdk)
- [`name`](#name)
- [`expression`](#expression)
- [`offset`](#offset)
- [`length`](#length)
- [`number_or_name`](#number_or_name)
- [`protocol`](#protocol)
- [`parent`](#parent)
- [`classify_fixed`](#classify_fixed)
- [`classify_fixed.match[]`](#classify_fixedmatch)
- [`classify_tcp`](#classify_tcp)
- [`classify_tcp.match[]`](#classify_tcpmatch)
- [`elements`](#elements)
- [`element`](#element)
- [`attribute`](#attribute)
- [`struct`](#struct)
- [`field`](#field)
- [`bitfields`](#bitfields)
- [`bitfields.bits[]`](#bitfieldsbits)
- [`element_type`](#element_type)
- [`data_type`](#data_type)
- [`conditional`](#conditional)
- [`classify_next`](#classify_next)
- [`classify_next.cases[]`](#classify_nextcases)
- [`classify_next.default`](#classify_nextdefault)
- [`next`](#next)
- [`next_offset`](#next_offset)
- [`fallthrough`](#fallthrough)

## `plugin.yaml`

A protocol model for mmt-plugin (docs/plugin-yaml.md): the protocol, its attributes and structs, the classification of the next protocol, and the parents it attaches to. Everything a PDL v1 model says, plus parents, absolute offsets and the SDK profile. A committed file: nothing machine-specific (an SDK prefix, a compiler) belongs here. Expressions are PDL v1 expressions written as strings: numbers, + - * /, comparisons, AND, OR, parentheses, val(x), sizeof(T), offset(x), len(x), ntohs(n), ntohl(n).

A mapping with only these keys (any other key is an error). Required: `schema`, `protocol`.

| Key | Type | Required | Default | Constraints | Description |
|---|---|---|---|---|---|
| `schema` | `1` | yes |  |  | The version of this format. A reader refuses a version it does not know. |
| `protocol` | [`protocol`](#protocol) | yes |  |  | The protocol: what PDL v1's Properties block says. |
| `sdk` | [`sdk`](#sdk) | no |  |  | The SDK the model is written for. |
| `offsets` | one of `absolute`, `running` | no | `absolute` |  | absolute (the default): every offset counts from the start of the protocol. running: PDL v1's running offset, where a constant attribute's or struct's offset is relative to the end of the constant ones before it, until the first attribute that is not constant (tests/corpus/README.md, Offsets and alignment); a struct then has no offset key. |
| `defines` | mapping of name to integer or string | no |  | each key is a [`name`](#name) | Named numbers, in order: each is a number, or the name of an earlier define or of an SDK protocol id macro (PROTO_TCP). Expressions, case values and next protocols use them. |
| `parents` | list of [`parent`](#parent) | no |  |  | The protocols this one runs on. Each one is checked by validate (parents-exist); one with classify is attached by the generated code, one without by the hook &lt;label&gt;_hook_register_parents in src/&lt;label&gt;_impl.c. |
| `plugins` | list of string | no |  |  | The other plugins this one needs loaded with it, a parent plugin first (a plugin its &lt;label&gt;_hook_register_parents attaches it to). Each is a path relative to the directory of this file: a project directory (its plugin.yaml; test builds its build/mmtp_&lt;label&gt;.so when it is stale, and loads the plugins that project names before it) or a built plugin, a file ending in .so. test loads them, in this order, before the plugin. |
| `attributes` | [`elements`](#elements) | no |  |  | The attributes, structs and conditionals, in packet order. |
| `classify_next` | [`classify_next`](#classify_next) | no |  |  | The classification of the next protocol: a C switch on an expression. |

## `sdk`

The SDK the model is written for.

A mapping with only these keys (any other key is an error).

| Key | Type | Required | Default | Constraints | Description |
|---|---|---|---|---|---|
| `profile` | string | no |  | a string matches `^[0-9]+\.[0-9]+\.[0-9]+([-+.][0-9A-Za-z.-]+)?$` | The SDK profile to generate for (for example 1.10.2), when no --sdk-profile or MMT_PLUGIN_SDK_PROFILE is given. It must be a profile mmt-plugin bundles. |

## `name`

A C identifier.

Type: string.
Constraints: a string matches `^[A-Za-z_][A-Za-z0-9_]*$`.

## `expression`

A number, or a PDL v1 expression as a string.

Type: integer or string.
Constraints: a string is not empty.

## `offset`

A byte offset: a number, or a PDL v1 expression as a string.

Type: integer or string.
Constraints: at least 0; a string is not empty.

## `length`

A length in bytes: a number, or a PDL v1 expression as a string. An expression that reads the packet (val(len) - 4) makes a variable-length attribute, of type MMT_BINARY_DATA, MMT_BINARY_VAR_DATA or MMT_STRING_DATA.

Type: integer or string.
Constraints: at least 1; a string is not empty.

## `number_or_name`

A number, or the name of a define or of an SDK protocol id macro.

Type: integer or string.
Constraints: a string matches `^[A-Za-z_][A-Za-z0-9_]*$`.

## `protocol`

The protocol: what PDL v1's Properties block says.

A mapping with only these keys (any other key is an error). Required: `label`, `id`.

| Key | Type | Required | Default | Constraints | Description |
|---|---|---|---|---|---|
| `label` | [`name`](#name) | yes |  |  | The protocol's label: the plugin is mmtp_&lt;label&gt;.so, and its registered name is the label upper-cased, the name mmt-security rules use (DEMO.kind for the label demo, never demo.kind). |
| `id` | integer | yes |  | at least 1 | The protocol id; third-party plugins use 950 to 999. |
| `context` | boolean | no | `false` |  | Generate the context hooks. |
| `session_context` | boolean | no | `false` |  | Generate the session data hooks. |
| `session` | boolean | no | `false` |  | Generate the sessionizer hooks. |
| `encapsulation` | boolean | no | `false` |  | The protocol carries another one (classify_next, or the classify_next hook). |
| `encoding` | one of `network`, `host`, `little`, `ASCII`, `UNICODE` | no |  |  | How integers are read: network is big-endian, host (alias little) little-endian. ASCII, UNICODE or no encoding: no byte order (a warning). |

## `parent`

A mapping with only these keys (any other key is an error). Required: `protocol`.

| Key | Type | Required | Default | Constraints | Description |
|---|---|---|---|---|---|
| `protocol` | [`name`](#name) | yes |  |  | The parent's registered name, case-insensitively (ethernet, udp, ...): an SDK protocol or an installed plugin's. |
| `weight` | integer | no | `5` | 0 to 100 | The classification weight: a parent runs its classification functions in increasing weight; mmt-dpi documents 0 to 9 and 90 to 100. |
| `classify` | [`classify_tcp`](#classify_tcp) when it has `port`; [`classify_tcp`](#classify_tcp) when it has `sport`; [`classify_tcp`](#classify_tcp) when it has `dport`; [`classify_fixed`](#classify_fixed) otherwise | no |  |  | The generated classification: by a TCP port (classify_tcp) when it has port, sport or dport, else at fixed offsets of the parent (classify_fixed). Needs a parent of the SDK profile. |

## `classify_fixed`

A parent's generated classification at fixed offsets: the protocol is classified when every match holds, at offset bytes after the start of the parent.

A mapping with only these keys (any other key is an error). Required: `match`, `offset`.

| Key | Type | Required | Default | Constraints | Description |
|---|---|---|---|---|---|
| `match` | list of [`classify_fixed.match[]`](#classify_fixedmatch) | yes |  | at least 1 item(s) |  |
| `offset` | integer | yes |  | at least 0 | Where the protocol starts, in bytes from the start of the parent (the parent's header length). |

## `classify_fixed.match[]`

A mapping with only these keys (any other key is an error). Required: `offset`, `length`, `value`.

| Key | Type | Required | Default | Constraints | Description |
|---|---|---|---|---|---|
| `offset` | integer | yes |  | at least 0 | From the start of the parent, in bytes. |
| `length` | integer | yes |  | 1 to 8 | In bytes. |
| `value` | integer | yes |  | at least 0 | The unsigned integer of length bytes, in network byte order. |

## `classify_tcp`

A tcp parent's generated classification by port: the protocol is classified in a segment with a payload when every port and every match holds, and starts with the payload, after the TCP header and its options (the header's data offset). Give port, sport or dport, or several: all of them must hold. Only under protocol tcp (model.classify-port otherwise).

A mapping with only these keys (any other key is an error).

| Key | Type | Required | Default | Constraints | Description |
|---|---|---|---|---|---|
| `port` | integer | no |  | 0 to 65535 | The source or the destination port. |
| `sport` | integer | no |  | 0 to 65535 | The source port. |
| `dport` | integer | no |  | 0 to 65535 | The destination port. |
| `match` | list of [`classify_tcp.match[]`](#classify_tcpmatch) | no |  |  | Fixed-offset tests of the payload, the protocol's first bytes. |

## `classify_tcp.match[]`

A mapping with only these keys (any other key is an error). Required: `offset`, `length`, `value`.

| Key | Type | Required | Default | Constraints | Description |
|---|---|---|---|---|---|
| `offset` | integer | yes |  | at least 0 | From the start of the TCP payload (where the protocol starts), in bytes. |
| `length` | integer | yes |  | 1 to 8 | In bytes. |
| `value` | integer | yes |  | at least 0 | The unsigned integer of length bytes, in network byte order. |

## `elements`

Type: list of [`element`](#element).

## `element`

An attribute; a struct when it has a struct key; a conditional when it has an if key.

Type: [`struct`](#struct) when it has `struct`; [`conditional`](#conditional) when it has `if`; [`attribute`](#attribute) otherwise.

## `attribute`

An attribute. Without offset, its extraction is a user hook.

A mapping with only these keys (any other key is an error). Required: `name`, `type`.

| Key | Type | Required | Default | Constraints | Description |
|---|---|---|---|---|---|
| `name` | [`name`](#name) | yes |  |  | The attribute's name (case-insensitive in expressions). |
| `type` | [`data_type`](#data_type) | yes |  |  | The attribute's mmt-dpi data type. |
| `offset` | [`offset`](#offset) | no |  |  | A byte offset: a number, or a PDL v1 expression as a string. |
| `length` | [`length`](#length) | no |  |  | Defaults to the type's width for a fixed-width type. |
| `scope` | one of `packet`, `session` | no | `packet` |  |  |

## `struct`

A struct: its fields are packed in order, without padding, and each one is a packet attribute.

A mapping with only these keys (any other key is an error). Required: `struct`, `fields`.

| Key | Type | Required | Default | Constraints | Description |
|---|---|---|---|---|---|
| `struct` | [`name`](#name) | yes |  |  | The struct's name (sizeof(struct X), a struct X field). |
| `offset` | integer | no | `0` | at least 0 | The offset of the struct's first byte. Not with offsets: running. |
| `fields` | list of [`field`](#field) | yes |  | at least 1 item(s) |  |

## `field`

A field; a run of bitfields when it has a bits key.

Type: [`bitfields`](#bitfields) when it has `bits`; otherwise a mapping of the keys below.

A mapping with only these keys (any other key is an error). Required: `name`, `type`.

| Key | Type | Required | Default | Constraints | Description |
|---|---|---|---|---|---|
| `name` | [`name`](#name) | yes |  |  | A C identifier. |
| `type` | [`element_type`](#element_type) | yes |  |  | A struct field's type: int, long, uint32_t (4 bytes), short, uint16_t (2), char, u_char, uint8_t (1), any of them or void followed by * (a 4-byte pointer), a fixed-width MMT_* type, or struct X. |

## `bitfields`

One storage unit of type, split into bitfields from its most significant bit, read in the model's byte order.

A mapping with only these keys (any other key is an error). Required: `type`, `bits`.

| Key | Type | Required | Default | Constraints | Description |
|---|---|---|---|---|---|
| `type` | [`element_type`](#element_type) | yes |  |  | A struct field's type: int, long, uint32_t (4 bytes), short, uint16_t (2), char, u_char, uint8_t (1), any of them or void followed by * (a 4-byte pointer), a fixed-width MMT_* type, or struct X. |
| `bits` | list of [`bitfields.bits[]`](#bitfieldsbits) | yes |  | at least 1 item(s) |  |

## `bitfields.bits[]`

A mapping with only these keys (any other key is an error). Required: `name`, `width`.

| Key | Type | Required | Default | Constraints | Description |
|---|---|---|---|---|---|
| `name` | [`name`](#name) | yes |  |  | A C identifier. |
| `width` | integer | yes |  | at least 1 | In bits. |

## `element_type`

A struct field's type: int, long, uint32_t (4 bytes), short, uint16_t (2), char, u_char, uint8_t (1), any of them or void followed by * (a 4-byte pointer), a fixed-width MMT_* type, or struct X.

Type: string.
Constraints: a string matches `^((unsigned )?(int|long|uint32_t|short|uint16_t|char|u_char|uint8_t)\*?|(unsigned )?void\*|MMT_[A-Z0-9_]+|struct [A-Za-z_][A-Za-z0-9_]*)$`.

## `data_type`

The attribute's mmt-dpi data type.

Type: one of `MMT_U8_DATA`, `MMT_U16_DATA`, `MMT_U32_DATA`, `MMT_U64_DATA`, `MMT_DATA_POINTER`, `MMT_STRING_DATA`, `MMT_DATA_IP_NET`, `MMT_DATA_MAC_ADDR`, `MMT_DATA_IP_ADDR`, `MMT_DATA_PATH`, `MMT_DATA_TIMEVAL`, `MMT_BINARY_DATA`, `MMT_DATA_BUFFER`, `MMT_DATA_CHAR`, `MMT_DATA_IP6_ADDR`, `MMT_DATA_PORT`, `MMT_DATA_POINT`, `MMT_DATA_PORT_RANGE`, `MMT_DATA_DATE`, `MMT_DATA_TIMEARG`, `MMT_DATA_STRING_INDEX`, `MMT_DATA_FLOAT`, `MMT_DATA_LAYERID`, `MMT_DATA_FILTER_STATE`, `MMT_DATA_PARENT`, `MMT_BINARY_VAR_DATA`.

## `conditional`

The then elements exist when the condition holds, the else elements when it does not.

A mapping with only these keys (any other key is an error). Required: `if`, `then`.

| Key | Type | Required | Default | Constraints | Description |
|---|---|---|---|---|---|
| `if` | [`expression`](#expression) | yes |  |  | A number, or a PDL v1 expression as a string. |
| `then` | [`elements`](#elements) | yes |  |  |  |
| `else` | [`elements`](#elements) | no |  |  |  |

## `classify_next`

The classification of the next protocol: a C switch on an expression.

A mapping with only these keys (any other key is an error). Required: `switch`.

| Key | Type | Required | Default | Constraints | Description |
|---|---|---|---|---|---|
| `switch` | [`expression`](#expression) | yes |  |  | A number, or a PDL v1 expression as a string. |
| `cases` | list of [`classify_next.cases[]`](#classify_nextcases) | no |  |  |  |
| `default` | [`classify_next.default`](#classify_nextdefault) | no |  |  | When no case matches. |

## `classify_next.cases[]`

A mapping with only these keys (any other key is an error). Required: `case`.

| Key | Type | Required | Default | Constraints | Description |
|---|---|---|---|---|---|
| `case` | [`number_or_name`](#number_or_name) | yes |  |  | The value of switch this case is for. |
| `next` | [`next`](#next) | no |  |  | The next protocol's id; setting it classifies the next protocol. |
| `offset` | [`next_offset`](#next_offset) | no |  |  | The next protocol's offset from the start of this one. |
| `fallthrough` | [`fallthrough`](#fallthrough) | no |  |  | Go on to the next case, as a C case without break. |

## `classify_next.default`

When no case matches.

A mapping with only these keys (any other key is an error).

| Key | Type | Required | Default | Constraints | Description |
|---|---|---|---|---|---|
| `next` | [`next`](#next) | no |  |  | The next protocol's id; setting it classifies the next protocol. |
| `offset` | [`next_offset`](#next_offset) | no |  |  | The next protocol's offset from the start of this one. |
| `fallthrough` | [`fallthrough`](#fallthrough) | no |  |  | Go on to the next case, as a C case without break. |

## `next`

The next protocol's id; setting it classifies the next protocol.

Type: [`number_or_name`](#number_or_name).

## `next_offset`

The next protocol's offset from the start of this one.

Type: [`expression`](#expression).

## `fallthrough`

Go on to the next case, as a C case without break.

Type: boolean.
Default: `false`.
