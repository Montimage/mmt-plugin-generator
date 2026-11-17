# Changelog

All notable changes to `mmt-plugin` are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project
uses [semantic versioning](https://semver.org/) for its command line, its
`--json` contract and its model format.

## [Unreleased]

### Added

- `mmt-plugin test` runs session tests (#99): a file in `tests/` with
  `session` (a `tcp` selector, the protocol, its id, the attributes every
  packet checks) and `packets` (the three-way handshake, idle time, and
  client or server segments, with retransmissions and lost bytes) is one
  TCP connection, whose frames `test` builds and runs in order in one
  harness, so a plugin's session state is tested. It is one
  `result.packets` entry with `session`, and each failure names its step
  (`packet`); `--sanitize` also runs corrupted copies of the session.
  `tests/corpus/README.md` ("Session files"), the user guide and the
  skill's `drafting.md` describe it. The WebSocket and OCPP examples' TCP
  session replays, which were Python in `tests/unit/examples/test_sdk.py`,
  are now their session tests, `examples/*/tests/session-*.yaml`.
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
- `scaffold --skip-until HEX` (a `tcp` parent only; another is
  `usage.conflicting-options`, exit 2) skips each direction's bytes of
  each TCP session up to the end of a byte pattern, found across segments:
  `0d0a0d0a` skips a WebSocket session's HTTP upgrade, and a frame in the
  segment of the 101 answer becomes a payload of its own (#102). The
  `--json` result has `skip_until`, the pattern in hex or null.
- `scaffold` proposes bit fields (#102): a byte whose bits vary
  independently is cut into `field_<offset>_b<bit>` fields in a struct
  `bits_<offset>` of `plugin.proposed.yaml`, and the packet tests give
  their `bit_offset` and `bit_width`, as `result.skeleton.fields` does.
  Runs of varying bits are groups, a constant bit between two varying ones
  is taken as varying, two groups that do not vary independently (one's
  value seen with two of the other, both ways) are merged, and the top bit
  of a run is a flag of its own when the two directions of each
  connection seen both ways set it to opposite values and the rest of the
  run varies within a direction (WebSocket's MASK, DNS's QR); a byte
  constant within each direction (a per-flow identifier such as RTP's
  SSRC), or unrelated one-way flows, are never cut by this rule, so a
  4-byte identifier stays one field. On a WebSocket session it
  proposes FIN, RSV1-3, the opcode, MASK and the 7-bit length
  (`tests/unit/scaffold/test_command.py`, `test_sdk.py`). A byte left with
  one varying group, or with fewer than 4 distinct values (too little
  evidence), stays one field, so the proposals of the demo captures are
  unchanged.

### Changed

- `scaffold` under a `tcp` parent follows each direction of each
  connection as a stream (`src/mmt_plugin/pcap/streams.py`, #102): a
  payload is a segment's new bytes in sequence order (from the SYN, or
  the first segment seen), a retransmission is skipped and an overlap cut
  off, a segment after missing bytes waits for them, and a SYN with a new
  initial sequence number starts a new session. `result.packets.skipped`
  has three new reasons, `retransmission`, `gap` (more than 64 segments
  waiting in a direction, or 1024 in all directions, which gives the
  direction up until a new SYN, so memory is bounded by these caps, or
  still waiting when the capture ends) and `skip-until`. Before, each
  segment was a payload as captured, retransmissions and handshakes
  included. Decided, of what #102 lists: segments are not split into
  messages nor joined (several WebSocket frames in one segment stay one
  payload, one frame over several segments stays several): that needs the
  protocol's length rule, which is what the proposal is drafting, so it
  is left to the user's hooks, as `examples/websocket/` does. A length
  field that selects the header's length (WebSocket's 126 and 127) is not
  proposed either: the length rule still looks for one fixed field whose
  value is the payload length minus a constant. `--skip-until` takes a
  byte pattern only, not a number of payloads per session: a pattern also
  finds the end of a handshake whose last segment carries the first
  message, which a count cannot.
- SDK profiles have an `entry_point` (#56, N12): the callback role, the
  symbol mmt-dpi looks up in a plugin (`init_proto`) and the macro of a
  plugin built into the core (`CORE`). The generator takes both names
  from it instead of writing them itself; the generated code is
  unchanged. The template test also refuses an SDK struct field written
  as a member access (`->caplen`). Decided: `headercheck` does not check
  `entry_point`, which no header declares; loading every generated plugin
  (`test_compile.py`) does.
- The agent skill `skills/mmt-plugin-author/` is renamed
  `skills/mmt-plugin-generator/`. Its steps are renumbered: 0, the work
  folder; 1, the capture; 2, the project; 3, the drafts; 4, the loop; 5, the
  envelope; 6, the capture evaluation.
- Styled output (#54, N5): the width that boxes and tables are drawn to is
  at most 500 cells (`ui.streams.MAX_WIDTH`), whatever `COLUMNS` or the
  terminal says; `COLUMNS=100000` draws a 500-cell box
  (`docs/design/cli.md`, section 10).
- zsh completion (#54, N8): `-h`, `--help` and `--version` are no longer
  offered once another option is on the line, and an option of an argparse
  mutually exclusive group no longer offers the group's other options.
  Decided: `--version` is excluded after another option although
  `mmt-plugin --json --version` is valid (it prints the version envelope);
  typing it in full still works. bash and fish completion are unchanged:
  the issue asked for zsh, whose `_arguments` has exclusion lists. No
  built-in command has a mutually exclusive group yet; the test command
  of `tests/unit/test_completion.py` has one.

### Fixed

- `generate` after an interrupted run (#56, N2): it writes a journal,
  `plugin.lock.pending`, next to `plugin.lock` before its first write
  (each file it is about to write or remove, with its sha256 before and
  after), and removes it after the lock. The next run, with the old model
  or the new one, accepts a file whose sha256 the lock or the journal
  lists, so it no longer reports `state.modified` for files nobody edited
  and needs no `--force`; `--check` reports `state.stale`. A run keeps the
  entries of the journal it finds (two interruptions in a row), journals a
  file `--force` overwrites only as it writes it (an interrupted `--force`
  run does not adopt the hand edit), counts a leftover journal as drift
  for `--check`, and refuses a directory in its place
  (`state.invalid-lock`). Decided: fix
  the code rather than correct `docs/design/cli.md` section 8 to the old
  guarantee; a journal that cannot be read is ignored (the run is then as
  strict as before); `init`'s `.gitignore` does not list the journal,
  which exists only after an interrupted run.
- `generate --strict` (#56, N3) also fails, before anything is written, on
  the warnings found while planning the writes: `state.kept` and the
  `--force` warnings, exit 7. The model's and the profile's warnings are
  still checked first. `docs/design/cli.md` ("Details fixed by #14") is
  the repository's record of #55's decision 13 and says so; #55's own
  description is not edited.
- `generate` and what is in the way (#56, N4): a directory (or any file
  that is neither a regular file nor a symbolic link) where a generated
  file goes is `state.modified`, and a directory named `plugin.lock` is
  `state.invalid-lock`, both exit 7, also with `--check`, and never
  replaced, even with `--force`; the hint is to move or delete it, no
  longer `--force`. An `--output` (or a default `generated/`) that is, or
  is under, an existing file is `usage.invalid-value` (exit 2), no longer
  `internal.io` (exit 1). Decided: no new code; `state.modified` and
  `state.invalid-lock` say "(a directory, never)" as `init`'s
  `state.file-differs` and `import`'s `state.output-differs` already do.
- `generate -o DIR` from inside a project with a `DIR` outside it (#56,
  N10) writes its own `plugin.lock` in `DIR` and no longer rewrites the
  project's. An output is the project's when its path or its real path is
  inside the project, so a `generated/` linked elsewhere keeps the
  project's lock.
- `generate --force` with `--check`, `--dry-run` or a refused run (#56,
  N11) says `would be overwritten (--force)` or `would be removed
  (--force)`; the warning of an invalid lock that `--force` ignores no
  longer repeats the lock's name, which is its location.
- `docs/design/cli.md` (#56, N9): a modified file that the lock lists and
  that is no longer generated is refused (`state.modified`, exit 7,
  `--force` removes it), as the code always did; `state.kept` is for one
  that is not a regular file of the output directory. Decided: keep the
  code and fix the sentence, as the review proposed; a maintainer may
  still choose the other way.
- `val()` of 2^63 or more (#56, N7): already fixed on `dev` by #55 (the
  value fails the evaluation). Added: the rule in `docs/plugin-yaml.md`
  (Expressions) and a packet test against the SDK on `ff` x 8, where both
  branches of `if (val(big) > 0)` are absent
  (`tests/unit/packettest/test_sdk.py`). Decided: a test there rather
  than a corpus model, since the corpus describes the Java tool's
  constructs.
- Styled output (#54, N1): `cell_width`, and `fit`, `box` and `table`
  with it, count an emoji sequence as the 2 cells a terminal draws: a ZWJ
  sequence, a regional-indicator flag, an emoji with a skin-tone modifier,
  a character with VS16, a keycap; `fit` never cuts one in the middle. It
  uses `unicodedata` only, with an approximation of
  Extended_Pictographic (the emoji blocks), so an emoji outside them is
  not joined. Decided: user text keeps its ZWJ escaped as `\u200d`
  (`ui.render.escape` escapes every format character, #46), so a ZWJ
  sequence draws joined only in text a renderer wrote; a lone regional
  indicator counts 1, as `unicodedata` says.
- Styled output (#54, N2): a table given a width below its minimum (one
  cell per column plus the gaps) cuts each line to that width with an
  ellipsis, instead of drawing it wider. Decided against dropping columns
  or gaps first: a cut line keeps the first columns readable and the
  rule is the one `box` already applies to a long line.
- Styled output (#54, N3, N4): `meter(nan)` draws every cell empty and
  ` n/a` instead of 100%, and an infinity clamps to 0% or 100%.
  `sparkline` no longer raises on a NaN or infinite sample: a NaN is a gap,
  an infinity clamps, `min` and `max` are of the finite samples (`n/a`
  when there is none) and a NaN, infinite or non-positive `ceiling` draws
  every level 0. `gradient_rgb` takes any float the same way.
- Tests (#54, N7): already done on `dev` before this change (#55, which
  found completion by name); the contract test now also finds the dummy
  command by name, and the completion tests derive the command list from
  the registry, so registering a command breaks none of them. The zsh
  completion test (#54, R1, R2) also has a file next to the directory, to
  show `-C` and `--project=` complete directories only, clears an
  exported `FPATH`, and gives each line 10 s inside an outer limit of
  10 s per line plus 60 s, so a broken setup ends in a readable diff.
  N6 (bidi controls) was #46, closed.

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
