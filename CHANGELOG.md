# Changelog

All notable changes to `mmt-plugin` are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project
uses [semantic versioning](https://semver.org/) for its command line, its
`--json` contract and its model format.

## [Unreleased]

### Added

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
