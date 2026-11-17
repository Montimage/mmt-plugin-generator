# Changelog

All notable changes to `mmt-plugin` are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project
uses [semantic versioning](https://semver.org/) for its command line, its
`--json` contract and its model format.

## [Unreleased]

### Added

- `mmt-plugin run PCAP` runs the project's plugin, built when stale, over
  a pcap or pcapng capture through mmt-dpi's stack, with the SDK's plugins
  and any `--plugin`, and reports the protocol paths with their packet
  counts and, per attribute of the plugin's protocol (and each
  `--protocol`), how many packets have it, as text and in its `--json`
  `result` (#103). The capture is streamed to a generated runner one frame
  at a time, so a capture of several gigabytes runs in constant memory.
  It reads Ethernet and Linux cooked (`tcpdump -i any`) captures; another
  link type is the new error `model.unsupported-linktype`. New codes
  `build.runner-failed`, and the warnings `test.no-match`,
  `test.other-linktype` and `test.unknown-protocol`; `--max-packets`,
  `--timeout`, `--dry-run`, `--strict`. The user guide and the
  mmt-plugin-generator skill (Step 6) describe it.
- The pcap reader gives each frame's time stamp (nanoseconds since the
  epoch: pcap's microseconds or nanoseconds, pcapng's `if_tsresol` and
  `if_tsoffset`), which `run` hands to mmt-dpi (#103).
- `plugin.yaml`: a `tcp` parent's `classify` can name ports, `port` (the
  source or the destination port), `sport` and `dport`, with optional
  `match`es on the payload's first bytes (#100). The generated
  classification finds the payload after the TCP header and its options
  (the header's data offset), and classifies only a segment with a payload
  (its end from the IP header, so Ethernet padding is not one). `init
  --parent tcp:...` and `scaffold --parent tcp:...` write it, and `init`'s
  packet test also runs `through` the selector. A port under another parent
  is the new error `model.classify-port`. The model reference has the two
  forms as `classify_fixed` and `classify_tcp`.
- `examples/websocket/`: a WebSocket (RFC 6455) plugin, `websocket_example`
  (id 992), made with `mmt-plugin init` (#40). It claims a TCP session on
  any port from its opening handshake and follows it across segments: the
  frame header fields, the unmasked payload, close codes, fragmented
  messages, the handshake's key, accept and the negotiated subprotocol.
  Its packet tests come from RFC 6455; `tests/unit/examples/test_sdk.py`
  also replays TCP sessions through it.
- `examples/ocpp/`: an OCPP 1.6-J plugin, `ocpp_example` (id 993), made
  with `mmt-plugin init` (#41). Directly above TCP, it claims a session
  whose WebSocket handshake offers `ocpp1.6` (or, mid-capture, a text frame
  with the OCPP-J array shape), and reports per segment the message type,
  UniqueId, action, error code and description, payload, `connectorId`,
  `idTag` and the charging limit and unit of a CALL; a CALLRESULT or
  CALLERROR reports the action of the CALL it answers, matched by UniqueId
  and direction in the session. Its packet tests come from OCPP-J 1.6 and
  OCPP 1.6; `tests/unit/examples/test_sdk.py` replays TCP sessions through
  it, also next to `websocket_example`.
- `docs/use-cases/websocket-ocpp.md`: the WebSocket and OCPP 1.6-J use
  case of the workflow (#39): the steps used, both examples against tshark
  on the four captures of Zenodo record 14887131, the answers to its open
  questions and the gaps found, with the counter it was measured with.
- The agent skill gets a capture of the protocol when the user gives none
  (found in public sources, recorded from a real implementation, or
  generated from the spec with the new `scripts/make_pcap.py` and marked
  synthetic), evaluates the green plugin on it with the new
  `scripts/pcap_eval.py` (mmt-dpi without and with the plugin: recall,
  foreign frames, attribute values and, with tshark, field agreement), and
  keeps a work folder with the request, the inputs and their sources, the
  capture, each loop run's envelopes and notes, the evaluation and a
  report, to review or resume the work later.
- Two semantic checks left out of #51 (#53), run by every command that
  analyses a model. A define named like a macro, constant, type or
  protocol macro that the SDK profile records (ethernet's
  `PROTO_IP = 15`) is the new error `model.define-sdk-name`, its related
  location the SDK header: the generated header would redefine the SDK's
  macro, and the model's expressions would read the define's value where
  they name the SDK's. A constant `data_len` other than a fixed-width
  type's width (`MMT_U16_DATA` with `data_len="4"`, `MMT_U32_DATA` with 3)
  is the new warning `model.data-len-width`, naming both widths
  (`docs/behaviour-changes.md`, rows 36 and 37). Decisions: the define
  check is an error, not a warning, since the C would silently use another
  protocol id; it is case-sensitive, as C is, so `define proto_ip` is
  accepted, and an expression that names `PROTO_IP` exactly now reads the
  SDK's macro, not that define (PDL names are otherwise case-insensitive).
  `MMT_DATA_POINTER` is not width-checked: it is stored as a pointer into
  the packet whatever its length. The width check is a warning, not an
  error: a field narrower than its integer type (24 bits in
  `MMT_U32_DATA`) is read correctly from `data_len` bytes by the new
  generator, unlike Java's fixed-width reads, and a longer integer is
  already the error `model.integer-length` at generation. A user hook's
  `data_len` (no offset) is not checked, as it only places what follows.
  No corpus model or example is affected (ethernet's model does not parse).
  Importing a PDL v1 model with such a define now exits 3.
- `tests/corpus/README.md` moves its "still open" rules to "Decided
  rules", worded as T1.3 (#51) implements them: `offset()`/`len()`,
  literal in-struct offsets after alignment stops and, also implemented
  (T1.5, behaviour change 19) though #53 did not list it, field names that
  are C keywords. The section had no other entry, so it is removed.

### Changed

- The agent skill `skills/mmt-plugin-author/` is renamed
  `skills/mmt-plugin-generator/`. Its steps are renumbered: 0, the work
  folder; 1, the capture; 2, the project; 3, the drafts; 4, the loop; 5, the
  envelope; 6, the capture evaluation.

### Fixed

- `examples/websocket/` and `examples/ocpp/` (#104): their sessions get
  mmt-dpi's long session timeout (600 s, as its HTTP's), so a connection
  idle for more than a minute keeps its state: `websocket_example` no
  longer loses the rest of such a stream, and `ocpp_example` no longer
  reports a CALL retransmitted after a long silence as a new one. After a
  lost frame header, both start again at the first segment that starts
  with a valid header, not inside a frame. `permessage-deflate` frames
  stay unread (a documented limit). The use case's A1 and A4 counts are
  measured again: A1 is within 31 frames and 5 messages of tshark.
- PDL v1 (#48): an error inside a quoted value whose closing quote is
  missing is reported once. `offset="BAD scope="packet"` gave a second,
  spurious `model.syntax.unexpected-token` at `packet`; the parse now stops
  at the first error (`docs/behaviour-changes.md`, row 42). Branch
  coverage, #48's optional N7, was decided against: it needs a new dev
  dependency, a `uv.lock` change and CI changes, while the parser's
  constructs are already enumerated by `@covers` and each syntax code has a
  test. It can be added later, project-wide, as its own change.
- SDK detection (#50, F6): the SDK version is read from the `VERSION`
  macro of `mmt_core.h` outside its comments, so a `#define VERSION`
  inside a `/* */` or `//` comment before the real one is no longer taken
  for it. The header check strips comments the same way, leaving string
  literals alone (`"/*"` starts no comment), after joining continued
  lines, so a `//` comment ending in a backslash also hides the next line.
- SDK profiles (#50, F7): the loader rejects a `$comment` that is not a
  string, and one below the top level, as the schema does, and the schema
  rejects an empty `c_std`, as the loader does. A test runs both on about
  2,200 mutations of the bundled profile; they agree on every one except
  the loader's cross-reference checks.
- `python -m mmt_plugin.sdk.headercheck` (#50): the completeness check of
  `parents.ids` counts every `PROTO_*` macro a header defines, whatever its
  value (`(PROTO_NAS5G + 1)`) and on continued lines, not only literal
  one-line numbers: each must be an id, in `not_ids`, the `_ALIAS` of a
  listed id or a `PROTO_CLASS_*` macro. mmt-dpi 1.10.2's headers pass
  unchanged. `tests/check_headercheck_mutations.sh` also changes
  `PROTO_MAX_IDENTIFIER`, `PROTO_UNKNOWN`, `PROTO_META` and adds such
  definitions, and must see each fail.
- SDK profile values (#50, F3): already done on `dev` before this change
  (#49, #51): the profile records, and the header check asserts, the value
  of `Max_Alias_Len`, `PROTO_MAX_IDENTIFIER`, `PROTO_UNKNOWN`,
  `PROTO_META` and every id of `parents.ids`, the values the tool uses as
  numbers. Decided: the other constants (`Classified`,
  `MMT_CLASSIFY_MATCHED`, `SCOPE_PACKET`, the `MMT_*` data types...) keep
  no value, since generated code names them and the header gives their
  value at compile time; the profile's `$comment` says so, and a test fails
  when the code reads the value of a constant whose value is not recorded.
  A new test also checks the run-time registry against the profile (#50,
  review of #51): with all the package's plugins loaded, mmt-dpi registers
  exactly the profile's ids, under their aliases. It runs, with
  `MMT_GOLDEN_SDK`, in `tests/unit/test_sdk_registry.py`, which CI's SDK
  jobs already run; it is not added to the `sdk-profile` CI job, whose
  workflow this change does not edit.
- Profile choice (#50): decided to keep the order and document it: a
  detected version with any suffix after its number, also `1.10.2.post1`,
  `1.10.2+git` or a Debian revision `1.10.2-1`, ranks below its release,
  like a pre-release (`docs/design/cli.md`, section 9). The version comes
  from the `VERSION` macro, which a release sets to its plain number, and
  a profile too old is the safe side.

## [0.1.0] - 2026-11-15

The first release of the Python generator, `mmt-plugin`. It replaces the
2015 Java generator (`MMTPluginGenerator.jar`), which is no longer part of
the repository (its sources and jar are in `legacy/` at commit 4076899).
The work is plan epic #4, tasks T0.1 to T5.4, described in
[`docs/design/workflow-redesign.md`](docs/design/workflow-redesign.md).

### Compared with the Java tool

The Java tool did one thing: turn a PDL model into C sources, whether or
not they compiled, and exit 0. `mmt-plugin` covers the whole life of a
plugin, from a new project to a plugin that mmt-dpi loads:

- **Code that compiles and loads.** Only 4 of the 16 example models gave
  Java output that compiled against mmt-dpi 1.10.2. Every example and
  corpus model that `mmt-plugin generate` accepts compiles with
  `-Wall -Wextra -Werror` (gcc and clang, amd64 and arm64), registers
  every attribute and loads through `init_extraction()`; CI checks it on
  every change.
- **Same meaning where Java was right.** For abb, cotp, s7com and tpkt the
  generated C means to mmt-dpi what the Java output meant (protocol,
  attributes, reads, structs, registrations), apart from Java's
  `register_protocol_stack` (bug 22); `tests/unit/generate/test_parity.py`
  checks it. Every other difference, and the Java bug it fixes, is in
  [`docs/behaviour-changes.md`](docs/behaviour-changes.md).
- **Safe packet reads.** Each attribute is read by a generated function
  that only touches bytes inside the captured packet, byte by byte in the
  model's byte order; no C struct is overlaid on packet bytes.
- **User code kept apart.** Generated files are never edited by hand: what
  the model cannot say goes in hooks in `src/<label>_impl.c`, and a missing
  hook is a build error, not a link failure.
- **Errors instead of silence.** A syntax error, a taken protocol id or
  name, or a type mmt-dpi cannot register is a model error (exit 3) with a
  file, line and column, and nothing is written. Java recovered silently
  and could write `null` or nothing.
- **A versioned SDK.** Every mmt-dpi name and type comes from an SDK
  profile (mmt-dpi 1.10.2 is bundled), checked against the real headers.
- **A scriptable contract.** Stable exit codes, a `--json` envelope with a
  published JSON Schema for every command, diagnostic codes that are never
  reused, and nothing ever prompted for.

### Added

- `plugin.yaml`, the model format, with its JSON Schema
  (`schemas/model/v1/plugin.json`), documented in
  [`docs/plugin-yaml.md`](docs/plugin-yaml.md) and
  [`docs/model-reference.md`](docs/model-reference.md). PDL v1 is still
  read, and `import` converts it without loss.
- Commands:
  - `init`: a project that builds and passes its packet test unmodified.
  - `import`: PDL v1 to `plugin.yaml`; constructs that relied on Java
    bugs are `model.legacy-*` warnings.
  - `validate`: schema, semantics, SDK profile, free id and name (in the
    profile and among the installed plugins), parents and load order.
  - `generate`: the plugin header and source and a `plugin.lock`;
    `--check` reports stale output, a hand-edited file is not overwritten
    without `--force`, and writes are atomic.
  - `build`: `mmtp_<label>.so` against an SDK, with fixed hardened flags
    and incremental rebuilds.
  - `test`: packet tests through a generated harness that loads the plugin
    into mmt-dpi, with each failing attribute's expected and actual value;
    `--sanitize` (ASan, UBSan and fuzzed packets) and `--bench`.
  - `install`, `uninstall`: a plugin and its manifest into a user prefix
    by default, never with root; only files whose hash still matches are
    removed.
  - `doctor`: toolchain, SDK, the directory mmt-dpi scans, load order,
    registry and clashes.
  - `scaffold --from-pcap`: packet tests and a field skeleton from a pcap
    or pcapng capture.
  - `completion`: bash, zsh and fish completion scripts.
- 16 example projects in [`examples/`](examples/README.md), ported from
  the `plugins/` models, each with packet tests whose expected values come
  from the protocol specifications; CI builds and tests every one.
- A test corpus (`tests/corpus/`): every example model plus a model per
  construct, with packet fixtures.
- The `mmt-plugin-author` agent skill
  (`skills/mmt-plugin-author/`, now
  [`skills/mmt-plugin-generator/`](skills/mmt-plugin-generator/SKILL.md)), which
  drafts and iterates a plugin from a spec, a capture or a PDL v1 model,
  with scripted evals.
- Documentation: the [user guide](docs/user-guide.md), the
  [migration guide](docs/migration.md) from the Java tool, and
  [releasing](docs/releasing.md).
- Release assets: a wheel and an sdist, a tarball of every JSON Schema,
  `SHA256SUMS` with a provenance attestation, and the container image
  `ghcr.io/montimage/mmt-plugin` (gcc, clang and mmt-dpi 1.10.2, amd64
  and arm64).
- CI: shellcheck, the corpus validator, ruff, mypy and pytest on Python
  3.10, 3.12 and 3.14, the generated-code matrix against a real mmt-dpi,
  a pinned build and test container, and a release dry run on every pull
  request.

### Removed

- The Java generator: its sources, jars, ANTLR grammar and NetBeans
  project (#31). The frozen Java output the parity test reads is kept in
  `tests/java-output/`.

[Unreleased]: https://github.com/Montimage/mmt-plugin-generator/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Montimage/mmt-plugin-generator/releases/tag/v0.1.0
