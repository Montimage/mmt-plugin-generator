# Agent instructions

MMT plugin generator: generates mmt-dpi protocol plugin sources (C) from a
protocol model. A Python rewrite is planned in
`docs/design/workflow-redesign.md`; what exists today is below.

## What exists today

- The Java generator (2015, `MMTPluginGenerator.jar`) was removed by T5.4
  (#31); its sources, jar and reference output were in `legacy/` up to
  commit 4076899. `docs/legacy/java-generator-inventory.md` describes its
  behaviour. `tests/java-output/` keeps, frozen, what the tests still need
  from its last run: `MANIFEST` (each model's status and every output
  file's sha256, byte for byte as it was), the generated C of abb, cotp,
  s7com and tpkt (the parity test) and the three non-empty stderr files
  (ethernet, ip, mongodb: the syntax errors `tests/unit/pdl/test_corpus.py`
  compares with). The tests check every kept file against `MANIFEST`, and
  `MANIFEST` against its sha256 at that commit; never edit them.
- `plugins/` (the Java tool's 16 example models, `plugins/*_plugin`, and
  their generated or hand-written C) was removed by #78; it is in the tree
  at commit f081d43. The models are `tests/corpus/models/<name>/model.pdl`
  byte for byte (`kind: example`, with their `sha256`, in
  `tests/corpus/index.yaml`; `MANIFEST` names them `<name>_plugin`), ported
  in `examples/`; `examples/README.md` ("The Java tool's C sources") lists
  the C and what replaced it. Only 4 of the 16 models (abb, cotp, s7com,
  tpkt) produced code that compiles against mmt-dpi 1.10.2 with the Java
  tool.
- `examples/` (T5.1): the 16 example models of the Java tool ported to
  mmt-plugin projects, `examples/<name>/` (`plugin.yaml` from `import`,
  then edited; the committed `plugin.lock` and `generated/`;
  `src/<label>_impl.c`; `tests/*.yaml`, the corpus packets of the model
  with the port's name and id, same bytes, values from the specs), and
  `examples/websocket/` (#40), a WebSocket (RFC 6455) plugin made with
  `init`, not a port: every attribute is a hook, and its session state
  follows the TCP session (`src/websocket_example_impl.c` says where
  mmt-dpi 1.10.2 runs it), and `examples/ocpp/` (#41), an OCPP 1.6-J
  plugin made the same way: directly above TCP (mmt-dpi 1.10.2 does not
  classify a layer above `websocket_example`), it claims a session whose
  handshake offers `ocpp1.6`, parses the WebSocket framing itself and
  links each answer to its CALL's action. Both inflate permessage-deflate
  messages (RFC 7692, #107) with one decoder, `src/ws_inflate.c` and
  `src/ws_inflate.h`, copied byte for byte into each project (a project
  builds only its own `src/`). Labels are `<protocol>_example`,
  ids 976-993, profile 1.10.2 pinned. All 18 build and pass their packet
  tests against
  mmt-dpi 1.10.2; `examples/README.md` lists each one's label, id,
  parent, model fixes and hooks. After a generator change (or a version
  bump: `plugin.lock` records it), regenerate them all, as the README
  says. Tests in `tests/unit/examples/`: `test_examples.py` (the models,
  `generate --check`, the ports' packet tests against the corpus, a source
  for every value of the others', one `through` test per example with a
  parent, a source for every session test, `tests/session-*.yaml`, and
  the two `ws_inflate` copies identical)
  and `test_sdk.py` (`validate`, `build` and `test --sanitize` on each
  one, then each parent's classification broken, which fails only the
  run through it and the session tests; the WebSocket and OCPP examples'
  session tests (#99, #107), 24 and 23, under the sanitizers with corrupted
  copies, and one without its CALL; then an OCPP session through the
  harness `test` built, next to the WebSocket plugin; needs
  `MMT_GOLDEN_SDK`).
- `ocip-plugin/` (#134): the work folder of the Cisco BroadWorks OCI-P
  plugin for mmt-security rule 232 (`README.md`, `REPORT.md`,
  `request.md`, `inputs/`, `runs/`, the synthetic capture and its
  evaluation). Its project, `ocip-plugin/project` (label `ocip`, id 960,
  registered name `OCIP`, parent `tcp` port 2208 in its hook), is not an
  example: rule 232 reads `OCIP.*`, so it keeps its label and is not
  under `examples/`. It is kept current (#138, option 1 of the three the
  issue weighed): regenerate it with the examples after a generator change
  or a version bump (`examples/README.md`, "Regenerating"; the release's
  `verify` job runs `generate --check` on it). Its packet and session
  tests are written by `ocip-plugin/inputs/make_tests.py` (stdlib only)
  from the wire format, never by hand. Tests in `tests/unit/ocip/`:
  `test_project.py` (`validate --no-sdk`, `generate --check`, the tests
  load and are what `make_tests.py` writes) and `test_sdk.py` (`validate`,
  `build` and `test --sanitize` on a copy; needs `MMT_GOLDEN_SDK`).
- `ndn_src/`: the NDN example plugin, kept building against mmt-dpi 1.10.2.
- `tests/check_ndn_plugin.sh`: builds and loads the NDN example.
- `tests/corpus/`: the test corpus (T0.4): the Java tool's 16 example
  models plus
  targeted per-construct models, each with packet fixtures whose expected
  values come from the protocol specs. `tests/corpus/README.md` defines the
  format and the extraction rules; `tests/corpus/validate.py` checks it.
- `tests/fetch_mmt_dpi_package.sh`: downloads a published mmt-dpi package
  from its GitHub Release and verifies it (pinned `SHA256SUMS` hash, then
  `SHA256SUMS` and `manifest.json`); it never installs.
- `Dockerfile`, `Makefile`: the pinned build and test container (T0.3):
  ubuntu:24.04 by digest, gcc, clang, Python 3.12 and the verified mmt-dpi
  v1.10.2 `.deb`. `make test-container` builds it (stage `toolchain`, the
  default target `test`) and runs the NDN check. The target `release`
  (T5.3) adds a released wheel to it (`--build-arg WHEEL=<file in dist/>`,
  dependencies from `uv.lock` with hashes, in `/opt/mmt-plugin`);
  `make release-image` builds this checkout's.
- Packaging and releases (T5.3): `.github/workflows/release.yml` and
  `docs/releasing.md`. Every PR to `dev`/`main`, push to `dev` and manual
  run is a dry run: `tests/build_release_assets.sh OUT_DIR` (the wheel, the
  sdist, `mmt-plugin-schemas-<version>.tar.gz` with every
  `src/mmt_plugin/schemas/**/*.json`, and `SHA256SUMS`) checked by
  `tests/unit/release/test_dist.py` (with `MMT_RELEASE_DIST=OUT_DIR`),
  `tests/check_release_tag.sh`, `tests/check_action_pins.sh` (each pinned
  action SHA is its tag's commit; needs gh and the network), `uv tool
  install` of the wheel and of the sdist (Python 3.10 and 3.14, then
  `generate --check` on every example), the release image on amd64 and
  arm64 (smoke-tested from `init` to `test`) and its push, by
  `tests/push_release_image.sh`, to a registry service in the job. Only a
  pushed `v*` tag runs the `publish-*` jobs, the only ones with write
  permissions: attestations and the GitHub release, the image on
  `ghcr.io/montimage/mmt-plugin`, and PyPI (trusted publishing) once the
  variable `PYPI_PUBLISH` is `true`. `tests/unit/release/test_workflow.py`
  checks the gates, the permissions and the pins;
  `test_release_tag.py` the tag rules. Never push a tag, create a release
  or run the workflow to publish without the maintainer's explicit OK. A
  version bump (`uv version V`) makes every example stale: regenerate them
  in the same change (`examples/README.md`), with CI's pinned uv, and add
  the release's section to `CHANGELOG.md` (Keep a Changelog).
- `pyproject.toml`, `uv.lock`, `src/`, `tests/unit/`: the Python rewrite
  (T1.1 onwards). The package `mmt_plugin` is in `src/mmt_plugin/` (uv_build's
  default layout) and its unit tests in `tests/unit/`. The `mmt-plugin` CLI
  has the contract core of `docs/design/cli.md` (exit codes in
  `exitcodes.py`, diagnostic codes in `diagnostics.py`, the `--json`
  envelope and its schema) and twelve commands, `init` (T2.7), `import`
  (T3.2), `validate` (T2.1), `generate` (T1.5), `build` (T2.3), `test` (T2.4),
  `run` (#103), `install`,
  `uninstall` and `doctor` (T2.5), `scaffold` (T4.1) and
  `completion {bash,zsh,fish}` (T2.6); each other
  command registers itself in `src/mmt_plugin/commands/` with its own issue,
  declaring its `exit_codes` and shipping its `result` schema as
  `src/mmt_plugin/schemas/cli/v1/<command>.json`. Styled (btop)
  output goes through `src/mmt_plugin/ui/style.py`: a command returns a
  `view` in its `Outcome`. `tests/unit/test_contract.py` checks every
  registered command's `--json` envelope, `result` schema and `--help` exit
  codes; `tests/unit/test_style.py` holds the cli-builder style tests.
- `src/mmt_plugin/pdl/` (T1.2): the PDL v1 lexer and parser.
  `parse(text, filename=...)` returns a typed model (`pdl/model.py`) or
  raises `PdlSyntaxError` with `model.syntax.*` diagnostics. It checks syntax
  only; names, layouts and values are T1.3. Its tests are in
  `tests/unit/pdl/`, with golden model dumps in `tests/unit/pdl/golden/`
  (regenerate with `MMT_UPDATE_GOLDEN=1 uv run pytest tests/unit/pdl`).
- `src/mmt_plugin/sdk/`: the SDK profiles (T1.4), one JSON file per mmt-dpi
  version in `sdk/profiles/` (only 1.10.2 so far; schema in
  `schemas/sdk/v1/profile.json`), SDK prefix detection and profile choice.
  Each `data_type` constant records its `size`, what mmt-dpi's
  `get_data_size_by_data_type()` returns: an attribute registers only with a
  `data_len` up to it, or 0 for a size of 0, so `generate` rejects a type of
  size 0 and a longer constant `data_len` (`model.type-size`).
  Plain functions for the commands to call; no command of its own.
- `src/mmt_plugin/semantics/` (T1.3): the semantic passes.
  `analyse(model, profile=...)` returns the analysed model
  (`semantics/model.py`: types, offsets, bitfields, folded expressions,
  resolved references, defaults) and `model.*` diagnostics; no file I/O.
  The model is `None` on any error, including an id or name the SDK already
  takes; `allow_sdk_conflicts=True` still returns it with those two errors
  (T1.6). Tests in `tests/unit/semantics/`, including the layout of every
  corpus fixture.
- `src/mmt_plugin/codegen/` (T1.5): `generate(analysed, profile)` renders the
  Jinja2 templates `codegen/templates/plugin.{h,c}.j2` (the package's only
  run-time dependency) into the plugin header and source, in memory; every
  SDK name comes from the profile. `mmt-plugin generate`
  (`commands/generate.py`) writes them and `plugin.lock` (`lock.py`, schema
  `schemas/lock/v1/plugin-lock.json`; in the output directory when that is
  outside the project), with its journal `plugin.lock.pending` written
  first and removed last, so an interrupted run recovers without `--force`
  (#56). Tests in `tests/unit/generate/`, with
  golden C for every corpus model that generates in
  `tests/unit/generate/golden/` (regenerate with
  `MMT_UPDATE_GOLDEN=1 uv run pytest tests/unit/generate`).
- User code (T2.2): the generated header declares every hook, including
  `<label>_hook_register_parents`, which the generated init calls to attach
  the protocol to its parents. `codegen.scaffold(generation, profile)`
  (`codegen/templates/impl.c.j2`) renders `src/<label>_impl.c` in memory,
  which `init` writes once; nothing else writes under `src/`.
  `codegen/hooks.py` finds the hooks that compiled user objects do not
  define (`build.missing-hook`, exit 5), which `build` runs before it links.
  Tests in
  `tests/unit/generate/test_scaffold.py` and `test_compile.py` (which also
  classifies a corpus packet through the scaffold's Ethernet example).
- `tests/unit/generate/test_compile.py` (T1.7): the compile-and-load check.
  Every corpus model that `generate` accepts (the rejected ones produce no
  output) is generated with the profile of an extracted SDK's version, and
  must compile with `-Wall -Wextra -Werror`, register with `libmmt_core`,
  build into a plugin and load through `init_extraction()` next to the SDK's
  `libmmt_tcpip.so`, its protocol and every attribute resolving to their own
  id and name. `tests/unit/generate/test_ci_matrix.py` checks that CI runs
  it with gcc and clang against the oldest and newest bundled profile.
- `docs/behaviour-changes.md` (T1.6): every difference from the Java tool,
  each with its inventory bug (or where it was decided) and the test that
  pins it; `tests/unit/test_behaviour_changes.py` checks that every inventory
  bug has a row and every named test exists. The parity test,
  `tests/unit/generate/test_parity.py`, reduces the Java output frozen in
  `tests/java-output/` and the new output of abb, cotp, s7com and tpkt
  to protocol, attributes, table rows, reads, structs and registrations, and
  asserts they are equal apart from Java's `register_protocol_stack` (bug 22)
  and the new init's call of `<label>_hook_register_parents` (T2.2).
  Add a row to the page when `generate` changes behaviour the Java tool had.
- `src/mmt_plugin/commands/validate.py` (T2.1): `mmt-plugin validate` reports
  the checks `schema`, `semantics`, `sdk-profile`, `id-free`, `name-free`,
  `parents-exist`, `load-order` and `id-range`, each `pass`/`warn`/`fail`/`skip`.
  The id and the name are checked against the profile (the SDK headers) and
  against what `init_extraction()` registers with the installed plugins
  (`src/mmt_plugin/sdk/registry.py`: a child Python process loads
  `libmmt_core` with ctypes, without the plugin's own `mmtp_<label>.so`).
  Without an SDK it exits 4 unless `--no-sdk`. `commands/modelio.py` reads
  `MODEL` (PDL v1 or `plugin.yaml`) for every command that takes one.
  Tests in `tests/unit/test_validate.py`
  and `tests/unit/test_sdk_registry.py` (its real-SDK tests need
  `MMT_GOLDEN_SDK`, like `test_compile.py`).
- `src/mmt_plugin/commands/build.py` (T2.3): `mmt-plugin build` compiles
  `<build-dir>/mmtp_<label>.so` (`build/` by default) from `generated/` and
  every `src/*.c`, against an SDK (`--sdk`, `MMT_BASE`, ...) with
  `--cc` > `CC` > `gcc`. Stages `generate` (runs `generate` when
  `generate --check` finds it stale; `--no-deps` exits 7 instead),
  `compile`, `hooks` (`codegen/hooks.py`) and `link` (to a temporary name,
  then renamed), in `result.stages`. The flags are fixed in code (`CFLAGS`,
  `LDFLAGS`: hardened, `-Wall -Wextra -Werror`, `-Wl,-z,defs` against
  `libmmt_core`); compiler messages become `build.cc` diagnostics. An
  unchanged input hash, with every file the compiler read unchanged (its
  `-MD` dependency files; `build/.mmtp_<label>.build.json`), is a no-op
  unless `--rebuild`; `--dry-run` reports the commands. Tests in `tests/unit/build/`:
  `test_command.py` with a fake SDK and compiler (`fakes.py`), and
  `test_sdk.py`, which builds and loads every corpus model against a real
  SDK (needs `MMT_GOLDEN_SDK`, like `test_compile.py`).
- `src/mmt_plugin/commands/test.py` (T2.4): `mmt-plugin test [PACKETS...]`
  runs packet tests (corpus schema 1; default `<project>/tests/*.yaml`)
  against the plugin of `--model` (as `build`'s `MODEL`). Stages `build`
  (`build` when stale; `--no-deps` exits 7 instead), `harness`, `packets`,
  `sanitize` and `bench`. `src/mmt_plugin/testing/`: `harness.py` renders
  the C host harness (`testing/templates/harness.c.j2`, into
  `build/test/`), which loads the plugin with `init_extraction()` next to
  the SDK's `libmmt_tcpip.so` (its own `MMT_DPI_PLUGINS_DIR`, never the
  host's), attaches it to Ethernet (EtherType 0x88b5, no parent hook
  needed) and prints the classification, the next protocol and each
  attribute; `packets.py` reads the fixtures (`yamlsubset.py`: the
  corpus's YAML subset, no YAML dependency) and compares. A packet test
  with `through` (an `init --parent` selector, #74) also runs as a whole
  frame whose lower layers `frames.py` builds, through mmt-dpi's stack and
  the plugin's own parent classification: its own `result.packets` entry
  (with `through`), a `<parent>` failure when the plugin is not directly
  above that protocol where the layers end, `next` not checked (mmt-dpi
  1.10.2's TCP and UDP stop at a plugin's layer); the harness's records
  are a kind byte (0 a packet, 1 a whole frame), a length, the bytes. A
  session test (#99, `session.py`: `session` and `packets` instead of
  `bytes` and `expect`; `tests/corpus/README.md`, "Session files") is the
  packets of one TCP connection (`open`, `idle` and client or server
  segments, with `retransmit`, `lost` and `back`, a late segment;
  sequence numbers, checksums and
  padding built by `session.py`), run in order in a harness of its own,
  each checked directly above TCP (`<parent>`), the attributes of
  `session.attributes` it does not list absent: one `result.packets`
  entry with `session` (its packet count), each failure with `packet` (its
  step). A mismatch is
  `test.packet-failed`, a crash `test.crash` (exit 6), each failure with
  its attribute, expected and actual value. `--sanitize` builds
  `build/sanitize/` with ASan/UBSan and runs truncated and random packets
  (`fuzz.py`, `--seed`, `--fuzz-count`), and each session test as it is,
  then corrupted copies of it (`mutate_frames`) until they make
  `--fuzz-count` packets, each in a harness of its own (a crash has its
  copy as `index` and its step as `packet`); `--bench` compares packets
  per second over the packet tests with an empty plugin
  (`templates/baseline.c.j2`) and never changes the exit code. Tests in
  `tests/unit/packettest/`: `test_testing.py`, `test_frames.py`,
  `test_session.py` and `test_command.py` (fake SDK, compiler and harness
  run), and `test_sdk.py`
  (every corpus model under the sanitizers, a broken model, against a real
  SDK; needs `MMT_GOLDEN_SDK`).
- `src/mmt_plugin/commands/install.py` (T2.5): `mmt-plugin install [MODEL]`
  runs `build` when stale (`--no-deps` exits 7 instead), then copies
  `mmtp_<label>.so` into `<prefix>/plugins/` and writes the manifest
  `<prefix>/plugins/.mmt-plugin/<label>.json` (`src/mmt_plugin/manifest.py`,
  schema `schemas/install/v1/manifest.json`: tool version, label, protocol
  id and name, each file's sha256). Prefix: `--prefix` > `--system`
  (`/opt/mmt`) > `MMT_PLUGIN_PREFIX` > `${XDG_DATA_HOME:-~/.local/share}/mmt`;
  never sudo, a prefix it cannot write is `sdk.prefix-not-writable` (exit 4).
  The same file is a no-op; a file no manifest lists (`state.exists`) or one
  changed since install (`state.installed-modified`) is exit 7 unless
  `--force`; another installed plugin's id or name is exit 3.
  `mmt-plugin uninstall [LABEL]` (default: the label of the header
  `plugin.lock` lists) removes only the manifest's files whose sha256 still
  matches. mmt-dpi 1.10.2 scans one plugin directory, `MMT_DPI_PLUGINS_DIR`
  or the one compiled into `libmmt_core` (`/opt/mmt/plugins` in the package),
  so a plugin under the default prefix loads through `MMT_DPI_PLUGINS_DIR`
  (`docs/design/cli.md`, D11). `src/mmt_plugin/commands/doctor.py`:
  `mmt-plugin doctor` reports the checks `python`, `compiler`, `sdk`,
  `sdk-profile`, `plugin-dir` (what mmt-dpi scans,
  `sdk/registry.py:scanned_plugin_dir`), `install-dir` (whether it is the
  prefix's), `load-order`, `registry`, `project` and `clashes` (among the
  installed manifests and the project's model); exit 4 when one fails.
  Tests in `tests/unit/install/`: `test_command.py`, `test_doctor.py` and
  `test_manifest.py` with build's fakes, every write in a temporary prefix
  (`--system` is pointed at one), and `test_sdk.py`, the load test at the
  default prefix against a real SDK (needs `MMT_GOLDEN_SDK`).
- `src/mmt_plugin/commands/init.py` (T2.7): `mmt-plugin init LABEL` creates
  a project in `--dir` (default `./<LABEL>`): `plugin.yaml` (a 4-byte
  header, the profile pinned in `sdk.profile`, `--parent` as its `parents`
  entry, #65), the scaffold `src/<label>_impl.c`, the packet test
  `tests/<label>-basic.yaml` and a `.gitignore` with `build/`. A parent the
  generated code can attach (`ethernet:ethertype=`, `udp:sport=`/`dport=`,
  `tcp:` with `port=`, `sport=` or `dport=`, #100) gets a `classify`, the one `scaffold` proposes
  (`pcap/skeleton.py:parent_yaml`), and the packet test also runs
  `through` it; any other is left to `<label>_hook_register_parents`.
  `--name` is only the label upper-cased (`plugin.yaml` has no other). `--id` defaults to the lowest id in 950-999
  that the profile and the installed plugins (`sdk/registry.py`) leave free,
  950 with the warning `sdk.id-unchecked` without an SDK; no `--parent` is
  the warning `model.no-parent`. The model must generate (exit 3 otherwise,
  nothing written). Re-running is a no-op; a file with other content
  (`state.file-differs`) or a non-empty directory without `plugin.yaml`
  (`state.not-a-project`) is exit 7 unless `--force`; a project of an older
  `init` (`model.pdl`, no `plugin.yaml`) is `state.file-differs` even with
  `--force`, its hint the `import` that converts it. `result.next` is the
  `test` command line for the project, `mmt-plugin -C <dir> test`. Tests in `tests/unit/init/`:
  `test_command.py` (a stubbed registry, build's fakes) and `test_sdk.py`,
  `init` then `test --json` against a real SDK (needs `MMT_GOLDEN_SDK`).
- `src/mmt_plugin/pluginyaml/` (T3.1): `plugin.yaml`, the canonical model
  format, described in `docs/plugin-yaml.md`. Its JSON Schema is
  `src/mmt_plugin/schemas/model/v1/plugin.json` (draft 2020-12, shipped in
  the package): everything PDL v1 says, plus `parents` (with an optional
  generated `classify`), `sdk.profile` and `offsets` (`absolute` by default,
  or PDL v1's `running`); no machine-specific key. `nodes.py` reads a YAML
  subset with line and column (no YAML dependency; `model.yaml-syntax`),
  `schema.py` enforces the schema file itself (`model.schema` at each
  offending node; `jsonschema` agrees in the tests), `load.py` builds the
  same typed model as the PDL v1 parser (`pdl/model.py` gained
  `Model.offsets`, `Model.parents`, `Struct.offset`; expressions go through
  `pdl.parser.parse_expression`), and `dump.py` writes an analysed model
  as `plugin.yaml`. Every command reads both formats; `sdk.profile` pins the
  profile below `--sdk-profile` and `MMT_PLUGIN_SDK_PROFILE`. A parent with
  `classify` gets a generated classification function that the init
  registers before calling `<label>_hook_register_parents`: matches at
  fixed offsets of the parent (`classify_fixed`), or, under `tcp`, ports
  (`port`, `sport`, `dport`) and matches on the payload, which starts after
  the TCP header's data offset (`classify_tcp`, #100; a port under another
  parent is `model.classify-port`). Tests in
  `tests/unit/pluginyaml/`: `test_nodes.py`, `test_schema.py`, `test_load.py`,
  `test_roundtrip.py` (every corpus model round-trips in both offset modes
  and generates the same C) and `test_sdk.py` (a packet test that passes
  only through the generated parent classification, and frames with TCP
  options, other ports and padding through the TCP one; needs
  `MMT_GOLDEN_SDK`).
- `src/mmt_plugin/commands/import_pdl.py` (T3.2): `mmt-plugin import PDL`
  (`-` is stdin) converts a PDL v1 model to `plugin.yaml`
  (`pluginyaml/convert.py`): `-o FILE` (default `<project>/plugin.yaml`; `-o -`
  prints it, a usage error with `--json`), `--dry-run`, `--force`,
  `--strict`. It analyses against the newest bundled profile and pins none;
  offsets are absolute, or `running` when the only errors are duplicate
  names the Java tool accepted. A construct that relied on a Java bug is a
  `model.legacy-*` warning (the table in `docs/plugin-yaml.md`, "From PDL
  v1"), an SDK id or name conflict among them; any other model error is exit
  3, nothing written. The same output is a no-op; other content, or a
  symbolic link, is `state.output-differs` (exit 7) unless `--force`, a
  directory always. Tests in `tests/unit/importpdl/`: `test_convert.py` (each
  warning), `test_command.py` and `test_corpus.py` (every corpus model that
  parses imports, and `generate` gives the same C from both formats).
- `src/mmt_plugin/commands/scaffold.py` (T4.1): `mmt-plugin scaffold
  --from-pcap PCAP --parent SELECTOR` slices the payloads of a pcap or pcapng
  capture under a parent (`init --parent`'s selector: `ethernet:ethertype`,
  `ip`/`ipv6:proto`, `udp`/`tcp:port|sport|dport`) into packet tests,
  `<tests-dir>/<label>-pcap-<n>.yaml` (`--tests-dir`, default
  `<project>/tests/`), and proposes a field skeleton,
  `<project>/plugin.proposed.yaml`, whose values the tests expect; it never
  edits `plugin.yaml`. The label and id come from `--model` (default
  `<project>/plugin.yaml`). `--max-packets` (default 20), `--dry-run`,
  `--force`. Under a `tcp` parent each payload is a segment's new bytes in
  its stream's order (retransmissions dropped, a gap given up), and
  `--skip-until HEX` skips each direction's bytes of each session up to the
  end of that pattern (an HTTP upgrade's `0d0a0d0a`), #102. A byte whose
  bits vary independently is proposed as bit fields (a struct
  `bits_<offset>`), with a role flag a direction sets its own way.
  `--tshark` (#125, `pcap/tshark.py`) drafts the fields from tshark's
  dissection instead (`tshark -T pdml` on the frames read, `-G fields`
  for types and bitmasks): the protocol at the payloads' start
  (`Payload.start`; `--protocol` when several, `--decode-as` as `-d`),
  each field every payload has at one offset as an attribute named after
  it, the tests expecting tshark's values; no tshark is
  `sdk.tshark-not-found`, tshark failing `sdk.tshark-failed` (exit 4), no
  dissector `model.no-dissector`, no field `model.no-fields` (exit 3),
  nothing written. A malformed pcap is `model.bad-pcap`, none under the parent
  `model.no-payloads` (exit 3); an output with other content is
  `state.output-differs` (exit 7) unless `--force`. `src/mmt_plugin/pcap/`:
  `reader.py` (pcap and pcapng, no dependency), `layers.py` (Ethernet,
  802.1Q, IPv4, IPv6, UDP, TCP; skip reasons), `streams.py` (TCP stream
  order) and `skeleton.py` (the field
  rules, the bit groups, the proposal, the packet tests). Tests in `tests/unit/scaffold/`:
  `samples.py` builds captures (a WebSocket session among them), `test_streams.py`, `data/` holds two written by tcpdump and
  editcap, `test_reader.py`, `test_layers.py`, `test_skeleton.py`,
  `test_command.py`, `test_tshark.py` (a fake tshark on `PATH` printing
  `data/tshark/`, what tshark 4.2.2 printed for `samples.dns_capture()`),
  and `test_sdk.py` (`init`, `scaffold`, then the proposal passes `test`;
  with `--tshark` too when tshark is installed, and failing without it
  when `MMT_REQUIRE_TSHARK=1`, #128; needs `MMT_GOLDEN_SDK`).
- `src/mmt_plugin/commands/run.py` (#103): `mmt-plugin run PCAP` runs the
  plugin of `--model` (as `test`'s) over a pcap or pcapng capture through
  mmt-dpi's stack and counts what it reports. Stages `build` (`build` when
  stale; `--no-deps` exits 7 instead), `runner` and `capture`.
  `src/mmt_plugin/capture/`: `runner.py` renders the C runner
  (`templates/runner.c.j2`, into `<build-dir>/run/`, `build.runner-failed`
  exit 5), which loads, from a plugin directory of its own
  (`MMT_DPI_PLUGINS_DIR`), every `*.so` of the SDK's `plugins/`, the plugin
  and each `--plugin` (one named as an SDK plugin replaces it), opens a
  handler for the first frame's link type and processes the frames it
  reads on stdin through mmt-dpi's stack (nothing attaches the plugin: its
  own parent classification runs); `run` streams the capture's frames to
  it (`mmt_plugin.pcap.reader`, record by record, with their time stamps,
  which the reader now gives in nanoseconds) in batches while threads read
  its report and the tail of its stderr: constant memory whatever the
  capture's size. `result`: `summary` (frames, processed, skipped,
  classified), `paths` (protocol names and ids, packets; at most 1024, the
  rest in `paths_other`), `protocols` (the plugin's, then each
  `--protocol`: packets, and per attribute the packets that have it).
  Ethernet and Linux cooked captures only (mmt-dpi's stacks 1 and 624;
  another link type is `model.unsupported-linktype`, exit 3).
  Warnings `test.no-match`, `test.other-linktype`, `test.unknown-protocol`;
  `test.load-failed` and `test.crash` (the frame; `--timeout`) exit 6; a
  capture broken after its header `model.bad-pcap` (exit 3) with the
  counts so far; `--max-packets`, `--dry-run`, `--strict`. Tests in
  `tests/unit/run/`: `test_runner.py` and `test_command.py` (a fake runner,
  `fakes.py`, with build's fakes) and `test_sdk.py` (a real runner against
  a real SDK, including its memory on a small and a large capture; needs
  `MMT_GOLDEN_SDK`).
- `skills/mmt-plugin-generator/` (T4.2; `skills/mmt-plugin-author/` before
  it was renamed): the agent skill that writes a plugin
  from a protocol spec, a capture or a legacy PDL v1 model, or updates an
  existing project (#89; changing a protocol mmt-dpi ships is out of
  scope). Every run keeps a work folder (`references/workfolder.md`: the
  request, the inputs and their sources, the capture, each loop run's
  envelopes and notes, the evaluation, `REPORT.md`, `manifest.json`), gets
  a capture of the protocol when the user gave none
  (`references/capture.md`: found, recorded or crafted through the
  `cyberlab` skill, a frontmatter dependency acquired with `asm` at first
  use, or, without it, generated with `scripts/make_pcap.py`, stdlib only) and evaluates the green plugin on it
  (`references/evaluation.md`: `scripts/pcap_eval.py` compiles
  `scripts/pcap_eval.c` against the SDK and libpcap, runs the capture
  through mmt-dpi without and with the plugin, and reports recall, foreign
  frames and, with tshark, field agreement, and the drift against tshark,
  the only reference tool (#123): each `--field` attribute that differs,
  `missed` and `foreign` frames, every frame in `drift.jsonl`; a drift is a
  defect, and the verdict FAIL, unless `--accept <key>=<reason>` accepts
  it; without tshark it is not checked). `SKILL.md` gives the entry commands (`init`, then `import` or
  `scaffold --from-pcap`; for an existing project, `validate --no-sdk`, then
  the loop once before any edit, which must be green) and the loop
  (`validate`, `generate`, `build`, `test`, each with `--json`) in fenced
  blocks marked `<!-- eval:entry ... -->` and `<!-- eval:loop ... -->`;
  `references/contract.md` the envelope keys it reads and an action for every
  exit class and every code of `diagnostics.CODES` (exact or a `*` family);
  `references/drafting.md` how to write `plugin.yaml` and packet tests.
  `evals/run_evals.py` (stdlib only) runs those blocks, as written, on each
  case of `evals/cases/<id>/` (`case.json`: the entry's parameters, then one
  set of scripted edits and an expected stop per loop run, the last one
  green; an `update` case, `telem-update`, also names `project`, a seed
  project in the case that the runner copies, checks with the entry block
  and runs the loop on once, green, as run 0), each command with an open
  stdin pipe that gets no data, no terminal and a time limit, and checks
  every envelope against `contract.md`, that each fix touches the reported
  location, that no packet test the case, `scaffold` or the seed wrote is
  deleted or rewritten, that the green model pins `sdk.profile` and
  attaches its parents, and, for an update, that it keeps the seed's label,
  id, `sdk.profile` and `parents:` and adds or changes a packet test.
  Without an SDK it stops after `generate`. Tests in `tests/unit/skill/`: `test_evals.py`
  (every case without an SDK, the envelopes against the JSON Schemas, the
  tables against `exitcodes.py` and `CODES`, the blocks, and evals that must
  fail), `test_scripts.py` (`make_pcap.py`'s captures sliced back by
  `mmt_plugin.pcap`, `pcap_eval.py`'s filters, comparisons, drift and
  report, a drift and a no-drift run through `main` with the runner and
  tshark faked) and
  `test_sdk.py` (every case green with a real SDK, and `pcap_eval.py` on the
  spec-telem plugin with and without tshark, with tshark a field without
  drift and one with, open then accepted; needs `MMT_GOLDEN_SDK` and
  `libpcap-dev`, and tshark for its tshark run, which skips without it
  unless `MMT_REQUIRE_TSHARK=1`).
- User documentation (T5.2): `README.md` (CRLF), `docs/user-guide.md`
  (install from a checkout, a project from `init` to `install`, every
  command, `--json`, exit codes, settings), `docs/migration.md` (from the
  Java tool and PDL v1) and `docs/model-reference.md`, generated from
  `schemas/model/v1/plugin.json` by `src/mmt_plugin/pluginyaml/reference.py`
  (never edit it: regenerate it, see Commands). The tool is not published
  yet (the first release is T5.5, #32): the docs install it from a checkout
  or a built wheel, and show the release's installs as `doc:skip` blocks.
  Tests in `tests/unit/docs/`: `test_links.py` (every relative link and
  `#anchor` of every tracked `*.md` resolves, offline, GitHub's anchors),
  `test_model_reference.py` (the committed page is current) and
  `test_commands.py`: in the three user docs every fenced block has a
  language, and every `sh` block a marker on the line before its fence,
  `<!-- doc:run no-sdk|sdk|install -->` or `<!-- doc:skip REASON -->`. The
  `doc:run` blocks of a page run in order with `bash -euo pipefail` in a copy
  of the tracked tree, with `mmt-plugin` on `PATH`, `HOME` in the sandbox
  and the host's `MMT_*`, `CC`, `PKG_CONFIG_*` and `XDG_*` dropped; a runnable
  block may not name `sudo`, `--system` or `/opt/mmt`. `no-sdk` blocks run
  with `MMT_BASE` an empty directory (so they must pin the profile and pass
  `validate --no-sdk`) and may not depend on an `sdk` block; `sdk` blocks get
  `MMT_BASE` and `CC` from `MMT_GOLDEN_SDK` and `MMT_GOLDEN_CC`; `install`
  blocks (`uv tool install`, into the sandbox) run only with
  `MMT_DOCS_INSTALL=1`. When you change a command, update the docs' blocks.
- `docs/use-cases/websocket-ocpp.md` (#39): the WebSocket and OCPP 1.6-J
  use case: the workflow steps used, both examples against tshark on the
  four captures of Zenodo record 14887131, the answers to the issue's open
  questions and the gaps filed (#96 to #104). `docs/use-cases/websocket-ocpp/`
  holds the two programs it was measured with, `count.c` (libpcap and
  `libmmt_core`) and `tshark_count.py`; neither runs in CI, and the
  captures are never committed.
- `.github/workflows/ci.yml`: CI on PRs to `dev`/`main` and pushes to `dev`.
  Runs shellcheck on every tracked `*.sh`, the corpus validator,
  `check_ndn_plugin.sh` against the mmt-dpi v1.10.2 ubuntu-24.04 `.deb`
  (amd64 and arm64), `make test-container` on both arches, the Python
  checks below (Python 3.10, 3.12 and 3.14; the 3.12 job installs zsh and
  fish and sets `MMT_REQUIRE_SHELLS=1`, so their completion tests fail
  instead of skipping), the SDK profile header check (amd64 and arm64; it
  also runs `test_sdk_registry.py::test_the_real_registry_is_the_profile`,
  the profile's ids against the run-time registry, and requires it to
  pass), and the generated code matrix: `test_compile.py` per mmt-dpi (the oldest and
  newest with a bundled profile, both v1.10.2 for now), per compiler (gcc,
  clang) and per arch (amd64, arm64), then `tests/unit/build/test_sdk.py`
  (`build` on every corpus model), `tests/unit/packettest/test_sdk.py`
  (`test` on every corpus model), `tests/unit/examples/test_sdk.py`
  (`build` and `test` on every example, and the WebSocket and OCPP
  session tests), `tests/unit/ocip/test_sdk.py` (`build` and
  `test --sanitize` on `ocip-plugin/project`, #138), `tests/unit/init/test_sdk.py` (`init` then `test`),
  `tests/unit/pluginyaml/test_sdk.py` (a `plugin.yaml` project classified
  by its generated parent code), `tests/unit/scaffold/test_sdk.py`
  (`scaffold` on sample pcaps, then `test` on the proposal),
  `tests/unit/run/test_sdk.py` (`run` over captures the test writes),
  `tests/unit/skill/test_sdk.py` (the mmt-plugin-generator evals, green),
  the scaffold and skill ones with the real tshark: every leg of this job
  installs the distribution's tshark (step "Install tshark", #128) and
  sets `MMT_REQUIRE_TSHARK=1` on those two steps, so `scaffold --tshark`
  and `pcap_eval.py`'s drift check against tshark run there and fail
  instead of skipping when tshark is missing (the Python jobs have no
  tshark and skip them),
  `tests/unit/docs/test_commands.py` (every `doc:run` block of the user
  docs, with `MMT_DOCS_INSTALL=1`; the Python 3.12 job also runs the
  install blocks),
  `tests/unit/install/test_sdk.py`
  (`install`, `doctor` and `uninstall` in a temporary prefix) and
  `test_sdk_registry.py` (the run-time registry and `validate` against that
  SDK). `.github/workflows/release.yml` (above) runs alongside it.

## Commands

Build and check the NDN example. It needs mmt-dpi >= 1.10.2 installed into a
private prefix (see README, "Install mmt-dpi"); pass that prefix as an
absolute path:

```
MMT_BASE=<private prefix> bash tests/check_ndn_plugin.sh
```

A private prefix can also come from the published package, without root.
The package's `libmmt_*.so` links point to absolute `/opt/mmt/...` paths, so
make them relative before linking against the prefix (`<dir>` absolute):

```
deb="$(bash tests/fetch_mmt_dpi_package.sh <download dir>)"
dpkg-deb -x "$deb" <dir>
for l in <dir>/opt/mmt/dpi/lib/*.so; do ln -sfn "$(basename "$(readlink "$l")")" "$l"; done
MMT_BASE=<dir>/opt/mmt bash tests/check_ndn_plugin.sh
```

It prints one `PASS:`/`FAIL:` line per check and exits non-zero on failure.
Always set `MMT_BASE`: the script defaults to `/opt/mmt`.

Or run the same check in the pinned container (docker, or
`CONTAINER=podman`); it needs no mmt-dpi on the host and no root:

```
make test-container
```

Check the test corpus (Python 3.8+, no dependencies). Run it after any change
under `tests/corpus/`; it also checks that the 16 example models still have
the bytes the Java tool ran on, and are the models of
`tests/java-output/MANIFEST`:

```
python3 tests/corpus/validate.py
```

Python package (needs [uv](https://docs.astral.sh/uv/); CI pins uv 0.12.10).
Python >= 3.10; `.python-version` picks 3.12 locally, as in the build
container. Run these checks before pushing a change under `src/`,
`tests/unit/` or to `pyproject.toml`; after a dependency change, commit the
updated `uv.lock`:

```
uv sync
uv run ruff check
uv run ruff format --check
uv run mypy
uv run pytest
uv run mmt-plugin --version
```

Check the bundled SDK profile against real mmt-dpi headers (needs gcc or
clang; `<dir>` is the extracted package of "A private prefix can also come
from the published package"). It prints one `PASS:`/`FAIL:` line per check
and exits non-zero on failure:

```
uv run python -m mmt_plugin.sdk.headercheck --sdk <dir>/opt/mmt --cc gcc
```

Check that it fails on broken scratch copies of those headers (an
unprototyped declaration, a wrong `Max_Alias_Len`, `PROTO_MAX_IDENTIFIER`
or `PROTO_META`, a plugin id or alias changed, a protocol id that
`parents.ids` does not list, also as an expression or on a continued line);
same output and exit:

```
bash tests/check_headercheck_mutations.sh <dir>/opt/mmt gcc
```

Compile every generated pair (and its scaffold `src/<label>_impl.c`)
against those headers, `-fsyntax-only -std=gnu11 -Wall -Wextra -Werror`, then link
each with the prefix's `libmmt_core` and check that its
`init_<label>_proto_struct()` returns 1 (every attribute registers); build
each into a plugin (`-O2 -fPIC -shared -Wall -Wextra -Werror -Wl,-z,defs`)
and check that `init_extraction()` loads it from `MMT_DPI_PLUGINS_DIR` next
to the prefix's `libmmt_tcpip.so`; and check that the profile's data type
sizes are what `get_data_size_by_data_type()` returns. The prefix's version
needs a bundled profile; without `MMT_GOLDEN_SDK` the test skips:

```
MMT_GOLDEN_SDK=<dir>/opt/mmt MMT_GOLDEN_CC=gcc uv run pytest tests/unit/generate/test_compile.py
```

Validate a model against an SDK prefix (`--no-sdk --sdk-profile 1.10.2` checks
it without one, skipping the installed-plugin checks):

```
uv run mmt-plugin validate tests/corpus/models/ndn/model.pdl --sdk <dir>/opt/mmt
```

Read the run-time registry and validate against a real SDK (skips without
`MMT_GOLDEN_SDK`):

```
MMT_GOLDEN_SDK=<dir>/opt/mmt uv run pytest tests/unit/test_sdk_registry.py
```

Create a plugin project and test it (`<dir>` as above):

```
MMT_BASE=<dir>/opt/mmt uv run mmt-plugin init demo
MMT_BASE=<dir>/opt/mmt uv run mmt-plugin -C demo test
```

Generate a model's C sources (no installed SDK needed with a pinned profile):

```
uv run mmt-plugin generate tests/corpus/models/pdl_bitfields/model.pdl -o <dir> --sdk-profile 1.10.2
```

The same for a `plugin.yaml` model (`docs/plugin-yaml.md`); a project's
`plugin.yaml` is the default `MODEL` of every command:

```
uv run mmt-plugin validate <project>/plugin.yaml --no-sdk
uv run mmt-plugin -C <project> generate --sdk-profile 1.10.2
```

Convert a PDL v1 model to `plugin.yaml` (warnings on constructs that relied
on Java bugs are `model.legacy-*`; `-o -` prints the YAML):

```
uv run mmt-plugin import tests/corpus/models/tpkt/model.pdl -o <project>/plugin.yaml
```

Load a `plugin.yaml` project whose parent is classified by generated code
against those headers (skips without `MMT_GOLDEN_SDK`):

```
MMT_GOLDEN_SDK=<dir>/opt/mmt MMT_GOLDEN_CC=gcc uv run pytest tests/unit/pluginyaml/test_sdk.py
```

Build a plugin (`<project>` holds the model and `src/<label>_impl.c`, the
scaffold of `codegen.scaffold`; `<dir>` as above). It writes
`<project>/generated/` and `<project>/build/mmtp_<label>.so`:

```
uv run mmt-plugin -C <project> build <project>/model.pdl --sdk <dir>/opt/mmt --cc gcc
```

Build and load every corpus model against those headers (skips without
`MMT_GOLDEN_SDK`):

```
MMT_GOLDEN_SDK=<dir>/opt/mmt MMT_GOLDEN_CC=gcc uv run pytest tests/unit/build/test_sdk.py
```

Test a plugin on packet tests (builds it first when stale; `--sanitize`
adds ASan/UBSan and random packets, `--bench` packets per second). It exits
6 when a packet fails, with the attribute, expected and actual value:

```
uv run mmt-plugin -C <project> test --model <project>/model.pdl --sdk <dir>/opt/mmt --cc gcc tests/corpus/models/pdl_scopes/packets
```

Run every corpus model's packet tests under the sanitizers against those
headers (skips without `MMT_GOLDEN_SDK`):

```
MMT_GOLDEN_SDK=<dir>/opt/mmt MMT_GOLDEN_CC=gcc uv run pytest tests/unit/packettest/test_sdk.py
```

Build and test a ported example, then all of them, against those headers
(the second skips without `MMT_GOLDEN_SDK`):

```
uv run mmt-plugin -C examples/dns test --sdk <dir>/opt/mmt --cc gcc --sanitize
MMT_GOLDEN_SDK=<dir>/opt/mmt MMT_GOLDEN_CC=gcc uv run pytest tests/unit/examples/test_sdk.py
```

Draft packet tests and a field skeleton from a capture (writes
`<project>/plugin.proposed.yaml` and `<project>/tests/<label>-pcap-<n>.yaml`,
never `plugin.yaml`), then check that the proposal passes them against those
headers (skips without `MMT_GOLDEN_SDK`):

```
uv run mmt-plugin -C <project> scaffold --from-pcap capture.pcap --parent udp:port=4433 --dry-run
MMT_GOLDEN_SDK=<dir>/opt/mmt MMT_GOLDEN_CC=gcc uv run pytest tests/unit/scaffold/test_sdk.py
```

Run the mmt-plugin-generator skill's evals: without `--sdk`, each case's loop
stops after `generate`; with it, every case must go green (`<dir>` as above).
It prints one `PASS:`/`FAIL:` line per case and exits 1 on failure:

```
uv run python skills/mmt-plugin-generator/evals/run_evals.py
uv run python skills/mmt-plugin-generator/evals/run_evals.py --sdk <dir>/opt/mmt --cc gcc
MMT_GOLDEN_SDK=<dir>/opt/mmt MMT_GOLDEN_CC=gcc uv run pytest tests/unit/skill/test_sdk.py
```

Install a plugin into a private prefix (never `--system` on a host whose
`/opt/mmt` is real), check where mmt-dpi looks for it, and remove it:

```
uv run mmt-plugin -C <project> install <project>/model.pdl --sdk <dir>/opt/mmt --prefix <prefix> --dry-run
uv run mmt-plugin -C <project> install <project>/model.pdl --sdk <dir>/opt/mmt --prefix <prefix>
MMT_DPI_PLUGINS_DIR=<prefix>/plugins uv run mmt-plugin doctor --sdk <dir>/opt/mmt --prefix <prefix>
uv run mmt-plugin -C <project> uninstall --prefix <prefix>
```

Load a plugin installed at the default prefix (a temporary `XDG_DATA_HOME`)
against those headers (skips without `MMT_GOLDEN_SDK`):

```
MMT_GOLDEN_SDK=<dir>/opt/mmt MMT_GOLDEN_CC=gcc uv run pytest tests/unit/install/test_sdk.py
```

Check the docs: links and anchors, the generated model reference, and the
docs' commands (the `sdk` blocks skip without `MMT_GOLDEN_SDK`, the
`install` blocks without `MMT_DOCS_INSTALL=1`). Regenerate the reference
after a change to the model schema:

```
uv run pytest tests/unit/docs
MMT_DOCS_INSTALL=1 MMT_GOLDEN_SDK=<dir>/opt/mmt MMT_GOLDEN_CC=gcc uv run pytest tests/unit/docs/test_commands.py
uv run python -m mmt_plugin.pluginyaml.reference --write docs/model-reference.md
```

Build and check the release assets (`<dir>` must not exist or be empty;
`check_action_pins.sh` needs gh and the network), and the release image
(docker, or `CONTAINER=podman`):

```
bash tests/build_release_assets.sh <dir>
MMT_RELEASE_DIST=<dir> uv run pytest tests/unit/release
bash tests/check_action_pins.sh
make release-image
```

## Writing a plugin as an agent

Follow `skills/mmt-plugin-generator/SKILL.md`. In short:

- Pass `--json` to every `mmt-plugin` command and decide from the envelope
  (`schema_version` 1): `exit_code` and its class first, then `error.code`,
  then each error of `diagnostics` at its `location`. Never parse the
  messages. `skills/mmt-plugin-generator/references/contract.md` has the action
  for every exit class and every code.
- Never pass `-` (stdin); no command prompts. Never `--system`, `sudo` or
  `/opt/mmt`; use a private SDK prefix with `--sdk`.
- Run `validate`, `generate`, `build` and `test` in that order, stop at the
  first non-zero exit, fix it, and start again from `validate`. Green is all
  four at 0, with at least one packet test and every one passing.
- `init` writes `plugin.yaml` with `sdk.profile` pinned and `--parent` under
  `parents:`; keep them (and `init`'s label and id) when you replace its
  sample model, and import a PDL v1 model next to it
  (`-o <project>/plugin.imported.yaml`), never over it with `--force`.
- Never delete a packet test written from the spec or by `scaffold`, or
  change its expected values to what the plugin outputs.
- Keep a work folder with everything that made the plugin, get a capture
  (found, recorded, or generated and marked synthetic) and evaluate the
  green plugin on it with `scripts/pcap_eval.py`. Judge every drift against
  tshark from the spec: fix it, or accept it with `--accept <key>=<reason>`;
  never report a plugin done while a drift is a defect.
- To update an existing project, check it (`validate --no-sdk`) and run the
  loop once before any edit; stop and report if it is not green. Keep its
  label, id, `sdk.profile` and `parents:` unless the request changes them,
  and every packet test it has (never edit their bytes or expected values;
  stop and report when the revised spec contradicts one); write the changed
  behaviour in new packet tests from the spec. Scaffold a new capture into
  a scratch directory (`--model <project>/plugin.yaml`), never into the
  project. A protocol mmt-dpi already ships cannot be changed by a plugin.
- When a command, a flag or a diagnostic code changes, update the skill:
  `tests/unit/skill/test_evals.py` fails until `contract.md` has a row for
  every code and the skill's blocks still run.

## Rules

- Never use `sudo`, and never write to `/opt/mmt`. Install mmt-dpi and
  plugins into a private prefix only.
- Branches: all plan work happens on `dev`. Fork issue branches from
  `origin/dev` and open PRs against `dev`, never `main`. `main` only receives
  `dev` through a release PR approved by the maintainer. Never force-push.
- PRs into `dev` need an independent review PASS and green CI, and are
  squash-merged with a hand-written message.
- Commits and PR bodies carry no AI co-author trailers (`Co-Authored-By: ...`)
  and no "Generated with ..." footers.
- Line endings: keep each file's existing ones. `README.md` uses CRLF; check
  with `cat -A <file>` (CRLF lines end in `^M$`) before and after editing.
