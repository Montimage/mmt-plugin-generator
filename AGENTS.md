# Agent instructions

MMT plugin generator: generates mmt-dpi protocol plugin sources (C) from a
protocol model. A Python rewrite is planned in
`docs/design/workflow-redesign.md`; what exists today is below.

## What exists today

- `legacy/`: the legacy Java generator (2015, NetBeans Ant project), frozen
  by T0.5: `src/`, `lib/`, `dist/`, `pdl_grammar/`, `nbproject/`,
  `build.xml`, `manifest.mf`. The prebuilt jar is
  `legacy/dist/MMTPluginGenerator.jar`. `legacy/reference-output/` holds its
  output for every `plugins/*_plugin` model (exit code, stdout and stderr
  included) and a `MANIFEST` with the jar's sha256; CI regenerates it with
  `legacy/check-reference-output.sh`. `docs/legacy/java-generator-inventory.md`
  describes the tool's behaviour.
- `plugins/`: the 16 example models (`plugins/*_plugin`) and generated or
  hand-written C sources (`*_src/`, `cotp/`, `tpkt/`, ...). Only 4 of the
  16 models (abb, cotp, s7com, tpkt) produce code that compiles against
  mmt-dpi 1.10.2 with the Java tool. Left as it is until T5.4 (#31); the
  ported projects are in `examples/`.
- `examples/` (T5.1): the 16 `plugins/*_plugin` models ported to
  mmt-plugin projects, `examples/<name>/` (`plugin.yaml` from `import`,
  then edited; the committed `plugin.lock` and `generated/`;
  `src/<label>_impl.c`; `tests/*.yaml`, the corpus packets of the model
  with the port's name and id, same bytes, values from the specs). Labels
  are `<protocol>_example`, ids 976-991, profile 1.10.2 pinned. All 16
  build and pass their packet tests against mmt-dpi 1.10.2;
  `examples/README.md` lists each one's label, id, parent, model fixes and
  hooks. After a generator change (or a version bump: `plugin.lock`
  records it), regenerate them all, as the README says. Tests in
  `tests/unit/examples/`: `test_examples.py` (the models, `generate
  --check`, the packet tests against the corpus) and `test_sdk.py`
  (`validate`, `build` and `test --sanitize` on each one; needs
  `MMT_GOLDEN_SDK`).
- `ndn_src/`: the NDN example plugin, kept building against mmt-dpi 1.10.2.
- `tests/check_ndn_plugin.sh`: builds and loads the NDN example.
- `tests/corpus/`: the test corpus (T0.4): every `plugins/` model plus
  targeted per-construct models, each with packet fixtures whose expected
  values come from the protocol specs. `tests/corpus/README.md` defines the
  format and the extraction rules; `tests/corpus/validate.py` checks it.
- `tests/fetch_mmt_dpi_package.sh`: downloads a published mmt-dpi package
  from its GitHub Release and verifies it (pinned `SHA256SUMS` hash, then
  `SHA256SUMS` and `manifest.json`); it never installs.
- `Dockerfile`, `Makefile`: the pinned build and test container (T0.3):
  ubuntu:24.04 by digest, gcc, clang, Python 3.12 and the verified mmt-dpi
  v1.10.2 `.deb`. `make test-container` builds it and runs the NDN check.
- `pyproject.toml`, `uv.lock`, `src/`, `tests/unit/`: the Python rewrite
  (T1.1 onwards). The package `mmt_plugin` is in `src/mmt_plugin/` (uv_build's
  default layout) and its unit tests in `tests/unit/`. The `mmt-plugin` CLI
  has the contract core of `docs/design/cli.md` (exit codes in
  `exitcodes.py`, diagnostic codes in `diagnostics.py`, the `--json`
  envelope and its schema) and eleven commands, `init` (T2.7), `import`
  (T3.2), `validate` (T2.1), `generate` (T1.5), `build` (T2.3), `test` (T2.4), `install`,
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
  `schemas/lock/v1/plugin-lock.json`). Tests in `tests/unit/generate/`, with
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
  `tests/unit/generate/test_parity.py`, reduces the Java output in
  `legacy/reference-output/` and the new output of abb, cotp, s7com and tpkt
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
  corpus's YAML subset, no YAML dependency) and compares. A mismatch is
  `test.packet-failed`, a crash `test.crash` (exit 6), each failure with
  its attribute, expected and actual value. `--sanitize` builds
  `build/sanitize/` with ASan/UBSan and runs truncated and random packets
  (`fuzz.py`, `--seed`, `--fuzz-count`); `--bench` compares packets per
  second with an empty plugin (`templates/baseline.c.j2`) and never changes
  the exit code. Tests in `tests/unit/packettest/`: `test_testing.py` and
  `test_command.py` (fake SDK, compiler and harness run), and `test_sdk.py`
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
  a project in `--dir` (default `./<LABEL>`): `model.pdl` (a PDL v1 model of
  a 4-byte header; writing `plugin.yaml` instead is #65), the scaffold
  `src/<label>_impl.c`, the packet test `tests/<label>-basic.yaml` and a
  `.gitignore` with `build/`. `--id` defaults to the lowest id in 950-999
  that the profile and the installed plugins (`sdk/registry.py`) leave free,
  950 with the warning `sdk.id-unchecked` without an SDK; no `--parent` is
  the warning `model.no-parent`. The model must generate (exit 3 otherwise,
  nothing written). Re-running is a no-op; a file with other content
  (`state.file-differs`) or a non-empty directory without `model.pdl`
  (`state.not-a-project`) is exit 7 unless `--force`. `result.next` is the
  `test` command line for the project. Tests in `tests/unit/init/`:
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
  registers before calling `<label>_hook_register_parents`. Tests in
  `tests/unit/pluginyaml/`: `test_nodes.py`, `test_schema.py`, `test_load.py`,
  `test_roundtrip.py` (every corpus model round-trips in both offset modes
  and generates the same C) and `test_sdk.py` (a packet test that passes
  only through the generated parent classification; needs `MMT_GOLDEN_SDK`).
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
  `--force`. A malformed pcap is `model.bad-pcap`, none under the parent
  `model.no-payloads` (exit 3); an output with other content is
  `state.output-differs` (exit 7) unless `--force`. `src/mmt_plugin/pcap/`:
  `reader.py` (pcap and pcapng, no dependency), `layers.py` (Ethernet,
  802.1Q, IPv4, IPv6, UDP, TCP; skip reasons) and `skeleton.py` (the field
  rules, the proposal, the packet tests). Tests in `tests/unit/scaffold/`:
  `samples.py` builds captures, `data/` holds two written by tcpdump and
  editcap, `test_reader.py`, `test_layers.py`, `test_skeleton.py`,
  `test_command.py`, and `test_sdk.py` (`init`, `scaffold`, then the
  proposal passes `test`; needs `MMT_GOLDEN_SDK`).
- `skills/mmt-plugin-author/` (T4.2): the agent skill that writes a plugin
  from a protocol spec, a capture or a legacy PDL v1 model. `SKILL.md` gives
  the entry commands (`init`, then `import` or `scaffold --from-pcap`) and the
  loop (`validate`, `generate`, `build`, `test`, each with `--json`) in fenced
  blocks marked `<!-- eval:entry ... -->` and `<!-- eval:loop ... -->`;
  `references/contract.md` the envelope keys it reads and an action for every
  exit class and every code of `diagnostics.CODES` (exact or a `*` family);
  `references/drafting.md` how to write `plugin.yaml` and packet tests.
  `evals/run_evals.py` (stdlib only) runs those blocks, as written, on each
  case of `evals/cases/<id>/` (`case.json`: the entry's parameters, then one
  set of scripted edits and an expected stop per loop run, the last one
  green), each command with an open stdin pipe that gets no data, no
  terminal and a time limit, and checks every envelope against
  `contract.md`, that each fix touches the reported location, that no packet
  test the case or `scaffold` wrote is deleted or rewritten, and that the
  green model pins `sdk.profile` and attaches its parents. Without an SDK it
  stops after `generate`. Tests in `tests/unit/skill/`: `test_evals.py`
  (every case without an SDK, the envelopes against the JSON Schemas, the
  tables against `exitcodes.py` and `CODES`, the blocks, and evals that must
  fail) and `test_sdk.py` (every case green with a real SDK; needs
  `MMT_GOLDEN_SDK`).
- User documentation (T5.2): `README.md` (CRLF), `docs/user-guide.md`
  (install from a checkout, a project from `init` to `install`, every
  command, `--json`, exit codes, settings), `docs/migration.md` (from the
  Java tool and PDL v1) and `docs/model-reference.md`, generated from
  `schemas/model/v1/plugin.json` by `src/mmt_plugin/pluginyaml/reference.py`
  (never edit it: regenerate it, see Commands). The tool is not published:
  the docs install it from a checkout or a built wheel until T5.3 (#30).
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
- `.github/workflows/ci.yml`: CI on PRs to `dev`/`main` and pushes to `dev`.
  Runs shellcheck on every tracked `*.sh`, the corpus validator,
  `check_ndn_plugin.sh` against the mmt-dpi v1.10.2 ubuntu-24.04 `.deb`
  (amd64 and arm64), `make test-container` on both arches, the Python
  checks below (Python 3.10, 3.12 and 3.14; the 3.12 job installs zsh and
  fish and sets `MMT_REQUIRE_SHELLS=1`, so their completion tests fail
  instead of skipping), the SDK profile header check (amd64 and arm64), and
  the generated code matrix: `test_compile.py` per mmt-dpi (the oldest and
  newest with a bundled profile, both v1.10.2 for now), per compiler (gcc,
  clang) and per arch (amd64, arm64), then `tests/unit/build/test_sdk.py`
  (`build` on every corpus model), `tests/unit/packettest/test_sdk.py`
  (`test` on every corpus model), `tests/unit/examples/test_sdk.py`
  (`build` and `test` on every ported example), `tests/unit/init/test_sdk.py` (`init`
  then `test`), `tests/unit/pluginyaml/test_sdk.py` (a `plugin.yaml`
  project classified by its generated parent code), `tests/unit/scaffold/test_sdk.py`
  (`scaffold` on sample pcaps, then `test` on the proposal),
  `tests/unit/skill/test_sdk.py` (the mmt-plugin-author evals, green),
  `tests/unit/docs/test_commands.py` (every `doc:run` block of the user
  docs, with `MMT_DOCS_INSTALL=1`; the Python 3.12 job also runs the
  install blocks),
  `tests/unit/install/test_sdk.py`
  (`install`, `doctor` and `uninstall` in a temporary prefix) and
  `test_sdk_registry.py` (the run-time registry and `validate` against that
  SDK).

## Commands

Generate C sources from a model with the legacy tool (needs Java):

```
java -jar legacy/dist/MMTPluginGenerator.jar plugins/tpkt_plugin <output dir>
```

Create the output dir first: if it is missing, the tool prints
`Error in writing to file` and still exits 0.

Check that the jar still reproduces `legacy/reference-output/` byte for byte
(needs a Java 8 runtime; set `JAVA` to pick one). It exits non-zero on any
difference; `--write` regenerates the reference instead:

```
bash legacy/check-reference-output.sh
```

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
under `tests/corpus/` or to a `plugins/*_plugin` model, since the corpus holds
byte-identical copies of those models:

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
unprototyped declaration, a wrong `Max_Alias_Len`); same output and exit:

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
MMT_BASE=<dir>/opt/mmt uv run mmt-plugin -C demo test --model demo/model.pdl
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
uv run mmt-plugin import plugins/tpkt_plugin -o <project>/plugin.yaml
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
uv run mmt-plugin -C <project> scaffold --from-pcap capture.pcap --parent udp:port=4433 --model <project>/model.pdl --dry-run
MMT_GOLDEN_SDK=<dir>/opt/mmt MMT_GOLDEN_CC=gcc uv run pytest tests/unit/scaffold/test_sdk.py
```

Run the mmt-plugin-author skill's evals: without `--sdk`, each case's loop
stops after `generate`; with it, every case must go green (`<dir>` as above).
It prints one `PASS:`/`FAIL:` line per case and exits 1 on failure:

```
uv run python skills/mmt-plugin-author/evals/run_evals.py
uv run python skills/mmt-plugin-author/evals/run_evals.py --sdk <dir>/opt/mmt --cc gcc
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

## Writing a plugin as an agent

Follow `skills/mmt-plugin-author/SKILL.md`. In short:

- Pass `--json` to every `mmt-plugin` command and decide from the envelope
  (`schema_version` 1): `exit_code` and its class first, then `error.code`,
  then each error of `diagnostics` at its `location`. Never parse the
  messages. `skills/mmt-plugin-author/references/contract.md` has the action
  for every exit class and every code.
- Never pass `-` (stdin); no command prompts. Never `--system`, `sudo` or
  `/opt/mmt`; use a private SDK prefix with `--sdk`.
- Run `validate`, `generate`, `build` and `test` in that order, stop at the
  first non-zero exit, fix it, and start again from `validate`. Green is all
  four at 0, with at least one packet test and every one passing.
- `init --parent` is only a comment: write `parents:` into `plugin.yaml`, and
  pin `sdk.profile`. Keep `init`'s label and id.
- Never delete a packet test written from the spec or by `scaffold`, or
  change its expected values to what the plugin outputs.
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
