# Java generator inventory

> **Source:** the first comment on issue #3, by luongnv89, posted
> 2026-11-10T11:22:44Z and not edited since:
> https://github.com/Montimage/mmt-plugin-generator/issues/3#issuecomment-6766030100
> (comment id 6766030100). Copied verbatim on 2026-11-13 for plan task T0.5
> (#9); everything below the line is that comment, unedited.
>
> Paths in it are the locations before T0.5: `dist/`, `src/`, `lib/`,
> `pdl_grammar/`, `nbproject/`, `build.xml` and `manifest.mf` now live under
> `legacy/`. Its findings are pinned by `legacy/reference-output/`.

---

## Current Java generator: behaviour inventory (the parity baseline)

Evidence gathered by Dex's research agent on 2026-11-10. It ran the shipped `dist/MMTPluginGenerator.jar` (built 2015-04-20, parser from ANTLR 3.4) on all 16 models in `plugins/`, then compiled each output against a private mmt-dpi 1.10.2 install (main `9ea989d7`) with `gcc -Wall -fPIC -shared`. Java 8 runs the jar, but there is no `javac`, so it could not be rebuilt; the text strings inside the jar's classes match the current sources.

Short names: G = `pdl_grammar/PluginGrammar.g`, P = `MMT_Plugin.java`, A = `MMT_Proto_Attribute.java`, C = `ConditionalAttributeProperties.java`, S = `StructElementAttribute.java`.

### 1. PDL language features

**Top level** (G:27-33): `Protocol { define* Properties Attributes classifynext? }`.
- `prog` has no EOF anchor, so text after the closing `}` is silently ignored.
- There is no comment syntax.
- Keywords are global lexer tokens. A field or alias named `id`, `len`, `offset`, `val`, `sizeof`, `label`, `session`, `packet`, `int`, `char`, `AND` or `OR` is a parse error. This is why `ip_plugin` fails on `uint16_t id;`.

**define** (G:40-60): `define NAME = <dec | 0x.. | NAME>`.
- A duplicate name is an error (P:316-326).
- Each define is written to the header as `#ifndef/#define/#endif`.
- Defines are only checked when used as `case` labels or `nextencaps` values.

**Properties** (G:178-255): the order is fixed. `label` comes first, then `id`, then the optional keys `context`, `session_context`, `session`, `encapsulation`, `encoding`.
- `label`: lower-cased for file and function names, upper-cased for macros. `PROTO_X_ALIAS` is the upper-cased label (P:449).
- `id`: read with `Integer.parseInt`. Negative values are accepted, and there is no range or uniqueness check: dns and radius are both 11, ip and ethernet are both 12.
- The boolean keys take `"true"`/`"false"` and default to false.
- `encoding`: `network`, `host` or `ASCII`/`UNICODE`. `ASCII` and `UNICODE` map to UNKNOWN (0), which is also the default when the key is omitted.

**Attributes** (G:263-312) can be a mix of three element kinds:
- **struct** `struct N { type a, b:4, c:4; ... }`.
  - Element types: `[unsigned] int|long|uint32_t` → U32, `short|uint16_t` → U16, `char|u_char|uint8_t` → U8, `T*` → POINTER, any `MMT_*` type, or `struct X` (must already be defined).
  - Every field becomes a SCOPE_PACKET attribute.
  - Each run of consecutive bitfields creates a helper struct.
- **attribute** `{ alias data_type [data_len] [offset] [scope] }`. The keys must appear in that order. `scope` is `SCOPE_PACKET|packet|SCOPE_SESSION|session`.
- **conditional** `if (expr) { … } [else { … }]`, which can be nested. There is no switch for attributes.

**Data types**: 26 `MMT_*` tokens. Lengths used for struct layout: U8=1, U16=2, U32=4, U64=8, POINTER/STRING/IP_NET/IP_ADDR=4, MAC=6, IP6=16, PATH=68, TIMEVAL=8, BINARY=68, everything else 0. C typedefs come from P:757-813, and unknown types become `void`.

**Expressions** (G:661-758):
- Operators: `OR`/`AND`, `== != > < >= <=`, `+ - * /`, parentheses, decimal and hex numbers.
- Functions:
  - `val(attr)` becomes `<label>_<attr>_get_value(ipacket, proto_index)`; the attribute must already be declared.
  - `sizeof(type)`.
  - `offset(X)` and `len(X)` are copied verbatim.
  - `ntohs`/`ntohl`.

**Offset and alignment** (G:274-311):
- There is a running offset R. For an aligned plain attribute, offset = R + declared offset, then R += length.
- A struct adds R to each field's offset, then adds every field's length to R.
- The first non-simple attribute stops alignment for good: later offsets are taken literally.
- An if/else block hands back the else-branch R, or the pre-if R when there is no else.

**classifynext**:
- Exactly one `switch(expr) { case N|0x..|DEFINE: … default: … }`.
- `nextencaps = N|DEFINE` sets `retval.proto_id` and `Classified`. `nextoffset = expr` sets `retval.offset`.
- A missing `break` falls through.

### 2. Generated output

Two files, `<label_lc>_mmt_plugin.h` and `.c`.

**Header:**
- Include guard `<LABEL>_H`.
- `PROTO_<L>` and `PROTO_<L>_ALIAS`.
- The attributes enum: starts at 1, source order, conditional attributes last, then `_ATTRIBUTES_NB`.
- Lower-cased attribute aliases.
- The defines, then the structs (in HashMap order, so not deterministic), then the init prototypes.

**Source, in this order:**
1. Includes.
2. get_value, get_offset and get_length prototypes.
3. Extraction functions: incomplete stubs that return 0 with "User code to be added", complex (expression offset or length), bitfield, and conditional.
4. `<l>_stack_classification`, always generated.
5. The `attribute_metadata_t` table: simple types map to `general_*_extraction` (`_with_ordering_change` for network encoding), everything else to `<l>_<a>_extraction`.
6. get_value functions (U8/U16/U32 referenced by `val()` only), then the conditional get_value, get_offset and get_length functions.
7. Optional stubs:
   - context: `context_cleanup`, `setup_context`;
   - session_context: `session_data_init/cleanup/analysis`;
   - encapsulation: `classify_next_proto`, either a stub or the switch;
   - session: `sessionizer`, `session_cleanup_on_timeout`, `session_comp`.
8. `init_<l>_proto_struct()` registers the attributes, then the classification, context, session-data and sessionizer functions, then `register_protocol_stack` (always) and `register_protocol`.
9. `init_proto()` inside `#ifndef CORE`.

**Left for the user to hand-edit:**
- incomplete extraction stubs;
- the context, session and sessionizer stubs;
- `classify_next` when there is no classifynext block;
- the parent-classification registration (the README tells the user to add it by hand).

Regenerating overwrites all of these edits.

### 3. CLI and error behaviour

- Usage: `<model> [<outdir>]`. The output directory defaults to `./plugins` relative to the current directory.
- **The exit code is always 0**, on every error (`System.exit(0)` at G:56, 140, 287, 303, 449, 560, 583, 603, 727, 773).
- Semantic errors print `Error: (line N) …` and write no files.
- Syntax errors: ANTLR prints `line L:C`, recovers and carries on, so the output can contain `null` (ethernet, mongodb), or an NPE means nothing is written (ip).
- A missing output directory is not created.
- An NPE during generation leaves partial files.
- Existing output files are overwritten silently.

### 4. Run results against mmt-dpi 1.10.2

| model | output | gcc | first error | cause |
|---|---|---|---|---|
| abb, cotp, s7com, tpkt | ok | **OK** | – | – |
| cam, cpm, quic, topo_ind_sch | ok | FAIL | `<l>_attributes_metadata` undeclared | generator (declaration order) |
| dns, ndn | ok | FAIL | same, plus session signature warnings and a missing return | generator and SDK drift |
| tcp | ok | FAIL | `TCP_H` enum value wiped by the include-guard macro | generator |
| arp | ok | FAIL | redeclaration of `ARP_AR_PRO` | generator (no duplicate check) and model |
| radius | ok | FAIL | `null` (offset/data_len omitted) | generator |
| ethernet | ok + syntax errors | FAIL | `sizeof(null)` | model and silent recovery |
| mongodb | ok + syntax errors | FAIL | `null` from `offset="POSITION_NOT_KNOWN"` | model |
| ip | **none** | – | `id` is a keyword | grammar limitation |

SDK drift against 1.10.2:
- Extraction functions take `int proto_index`, but the SDK expects `mmt_proto_index_t` (unsigned). That gives 88 incompatible-pointer warnings, which GCC 14 treats as errors.
- The session-data callbacks use `int` and `void` where the SDK expects other types.
- `register_proto_context_cleanup_function` does not exist in the SDK.
- `general_short_extraction` is deprecated.

### 5. Bugs and limitations

1. Extraction functions use the metadata table before its static definition (P:557-595, A:114/120, S:258/264).
2. Struct field offsets double-count after a bitfield line, because `previous_chuncked` is not reset (G:477-495). dns `qdcount` comes out at 6 instead of 4, tcp `seq` at 14 instead of 12.
3. The running offset adds each bitfield member's full type width (G:276-282).
4. C padding is ignored, but the emitted structs are not packed.
5. Whether an expression is simple depends only on its last operand (G:667-698): `val(x)-4` folds to -4.
6. `>`, `<`, `>=` and `<=` fold as `!=` (G:682-685).
7. `sizeof(char)` emits `sizeof(MMT_U8_DATA)`, which is 4 (G:733).
8. A nested `struct X` field gets a line number as its length and C type `void` (G:600, P:812).
9. A missing `scope`, `offset` or `data_len` emits the text `null`.
10. An unknown encoding references extraction functions that are never generated.
11. `val()` on an attribute with an expression offset reads position -2 (A:62).
12. Conditional attributes skip the duplicate check (P:386) and cannot be used in `val()`.
13. A conditional get_value with no matching branch returns an uninitialised `retval` (C:350-449).
14. An incomplete conditional attribute emits a bare `TODO: …`, which does not compile (C:242).
15. An attribute named `h` collides with the `<LABEL>_H` include guard.
16. Aliases are lower-cased, but the duplicate check is case-sensitive.
17. Bitfield helper struct names are not unique (G:557).
18. Struct emission order is not deterministic (HashMap).
19. `offset()` and `len()` emit calls to C functions that do not exist (G:736-742).
20. The sessionizer and timeout stubs have no return statement (P:198-204).
21. `classifynext` is dropped silently unless `encapsulation="true"`.
22. `register_protocol_stack` is always emitted.
23. Ids are not validated.
24. The exit code is always 0, and syntax errors are recovered from silently.
25. `MMT_DATA_IP_ADDR` is byte-swapped on the complex path but copied raw on the simple path.

### 6. Tests

None exist. `PluginTest.java` is the CLI entry point, not a test. `nbproject` points at a `test/` directory that does not exist.
