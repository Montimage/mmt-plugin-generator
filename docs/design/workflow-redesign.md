# MMT plugin generator: workflow redesign and rewrite plan

Status: approved by Luong on 2026-11-10. Owner: Dex (orchestrator). Repo: Montimage/mmt-plugin-generator.
Inputs: the behaviour inventory of the Java tool (Montimage/mmt-plugin-generator#3, first comment) and the NDN example work (#1, #2). Related mmt-dpi changes: #62, #66/#68, #70/#71.

## Goal

Replace the 2015 Java generator with a maintained Python tool and a complete plugin workflow: model, validate, generate, build, test, install. It must be easy to use, intuitive, performant, consistent, resilient, correct and agent-operable. Correctness is proven against mmt-dpi (compile, load, extract the right values), not copied from the Java tool. Today only 4 of the 16 example models compile against mmt-dpi 1.10.2, and the Java tool has 25 listed bugs.

## Decisions (approved)

1. **Language:** Python 3.10 or later.
   - Grammar: Lark or ANTLR 4, with line and column positions.
   - Jinja2 templates, pydantic models, pytest with snapshot tests.
   - scapy for crafting test packets.
   - Distributed with `uv tool install` / `pipx`.
2. **Model format:** `plugin.yaml` with a published JSON Schema is the canonical format. PDL v1 models stay supported: `generate` reads them, and `import` converts them.
3. **Your code vs generated code:** generated files are never hand-edited. User logic goes in `src/<name>_impl.c` as hook functions declared by the generated header. A missing hook is a compile error.
4. **Plugin `.so` naming:** `mmtp_<label>.so`, which always sorts after `libmmt_tcpip.so`. `validate` enforces it.
5. **Third-party protocol ids:** ask mmt-dpi to reserve and document a range (950–999). `validate` warns outside it and fails on a taken id or name.
6. **Java tool:** moved to `legacy/` and kept until the parity tests (#3) pass, then deleted.
7. **Tracking:** one epic plus one issue per task below. Implementation by Claude Code; review by a separate agent session.
8. **PDL semantics (T0.4 corpus, PR #35):** decided by Luong on 2026-11-10. Details in [`tests/corpus/README.md`, Decided rules](../../tests/corpus/README.md#decided-rules).
   - Bitfields: numbered from the most significant bit of the storage unit, read in the model's byte order; the only rule. The `ip` model's `ihl:4, version:4` is a model bug, fixed in T5.1. A declared divergence from Java for T1.6. A per-struct `bit_order` key (default `msb`) may come later.
   - `host` encoding: fixed little-endian, not the order of the machine running the plugin. `little` is an alias.
   - Omitted scope: packet (T1.3 may warn). Omitted `data_len`: the type's width for fixed-width types; T1.3 reports an error for types without one.
   - `struct X` field: `sizeof(struct X)` bytes, read as `MMT_BINARY_DATA`; `X` defined before use.
   - `T*` field: 4 bytes on the wire, read as `MMT_DATA_POINTER`. "Value = offset" is a T2.4 harness convention. T1.3 discourages `T*` in new models.
   - `ntohs`/`ntohl` of a literal: an unconditional byte swap.
   - After if/else, R and the alignment state are the else branch's (Java behaviour, kept). T1.3 warns when a constant, aligned attribute follows an if/else whose branches advance R by different amounts.

## Branching and merge policy

- All work for this plan happens on the long-lived branch **`dev`** (created from `main` at `dcdf62ab`).
- Every issue branch forks from `origin/dev`, and every PR targets `dev`. Agents are launched from a `dev` checkout, which the IDD resolver uses as its base.
- PRs into `dev`:
  - need an independent review PASS and green CI;
  - are squash-merged with a hand-written message;
  - carry no AI co-author trailers or "Generated with" footers.
- `main` stays the stable branch. It only receives `dev` through a release PR (`dev` → `main`), with Luong's explicit OK. Urgent fixes to `main` are cherry-picked back to `dev`.
- Until `dev` is the default branch, `Closes #N` in a PR merged into `dev` does not auto-close the issue. The orchestrator closes it after the merge, pointing at the merge commit, so that dependency gates see it as done.

## Tasks

### Phase 0 — Foundations

- **T0.1 Agent and contributor setup on dev.**
  - Add `AGENTS.md` and `CLAUDE.md` (build and test commands, the dev-branch policy, never touch `/opt/mmt` or use sudo, no AI trailers).
  - Run `init-idd` to add `.idd.yml`.
  - Commit this plan as `docs/design/workflow-redesign.md`.
  - Add a short CONTRIBUTING section stating that PRs target `dev`.
  - Verify: the files exist, and `.idd.yml` loads with the IDD config script.
- **T0.2 CI skeleton.** Depends on T0.1.
  - A GitHub Actions workflow on pull requests to `dev` and `main`, and on pushes to `dev`.
  - It installs the published mmt-dpi v1.10.2 package into the runner and runs `tests/check_ndn_plugin.sh` against it.
  - Shellcheck on the repo's scripts.
  - Pinned action SHAs.
  - Verify: the workflow is green on a PR to `dev`.
- **T0.3 Pinned build and test container.** Depends on T0.2.
  - A Dockerfile with gcc, clang, Python 3.12 and mmt-dpi v1.10.2 installed from the published Release package, pinned by digest and checksum.
  - Used by CI and by a local `make test-container`.
  - Verify: the container builds, and `check_ndn_plugin.sh` passes inside it.
- **T0.4 Test corpus.** Depends on T0.1.
  - Under `tests/corpus/`, for each of the 16 models in `plugins/`: packet fixtures (hex or pcap slices) with the expected classification and attribute values, taken from the protocol specifications.
  - Plus one targeted model per PDL construct: defines, every Properties key, struct with bitfields, every `MMT_*` type, both scopes, if/else nesting, `val()`/`sizeof`/`ntohs`/`ntohl` expressions, the classifynext switch.
  - Verify: the corpus index lists every construct of the inventory with at least one model and one packet.
- **T0.5 Freeze the Java baseline.** Depends on T0.1.
  - Move the Java tool (`src/`, `lib/`, `dist/`, `pdl_grammar/`, `nbproject/`, `build.xml`, `manifest.mf`) to `legacy/`.
  - Store its output for every model as reference artifacts under `legacy/reference-output/`, with the generator version and the date.
  - Add the inventory from #3 as `docs/legacy/java-generator-inventory.md`.
  - Verify: `java -jar legacy/dist/MMTPluginGenerator.jar` still runs on every model, and the reference outputs match a fresh run byte for byte.

### Phase 1 — Core rewrite (Montimage/mmt-plugin-generator#3)

- **T1.1 Python package skeleton.** Depends on T0.2.
  - `pyproject.toml` with a src layout, a `mmt-plugin` console entry point, ruff, mypy (strict on the package) and pytest.
  - A CI job for lint, type checks and unit tests.
  - Verify: `uv run mmt-plugin --version` and `uv run pytest` pass in CI.
- **T1.2 PDL v1 parser into a typed model.** Depends on T1.1.
  - Accepts every construct of the inventory, with the same meaning.
  - Keywords are contextual, so fields named `id`, `len` or `offset` work.
  - Comments are supported, and the parser is anchored at EOF.
  - Syntax errors carry file, line, column and a hint, and the tool exits non-zero without writing anything.
  - Verify: the parser unit tests cover every construct and every Java syntax-recovery case from the inventory.
- **T1.3 Semantic passes.** Depends on T1.2.
  - Layout and offset computation, fixing Java bugs 2, 3 and 4 (bitfield double-counting, padding).
  - Typed expressions and constant folding, fixing bugs 5, 6, 7 and 19.
  - Validation, fixing bugs 9, 12, 16, 17 and 23: duplicates are checked case-insensitively, `val()` targets are checked, and ids are checked.
  - Verify: each fixed bug has a regression test named after its inventory number.
- **T1.4 SDK profile for mmt-dpi 1.10.2 and SDK detection.** Depends on T1.1.
  - A data file describing callback signatures (`mmt_proto_index_t`), registration calls, helpers, the logger (`mmt_log.h`) and the class provider (`mmt_class_provider.h`).
  - Detection order: `MMT_BASE`, the FHS pkg-config file, then `/opt/mmt`.
  - An unknown SDK version falls back to the nearest profile with a warning.
  - Verify: the profile is checked against the installed 1.10.2 headers in CI.
- **T1.5 Code generation.** Depends on T1.3 and T1.4.
  - Jinja2 templates emit the header and source from the model and the SDK profile.
  - Output is deterministic: byte-identical on re-run, with stable ordering.
  - Hooks are declared for user code, writes are atomic, and existing files are never overwritten silently.
  - Fixes bugs 1, 10, 11, 13, 14, 15, 18, 20, 21, 22 and 25.
  - Verify: golden snapshot tests of the generated C for every corpus model.
- **T1.6 Parity and behaviour-changes record.** Depends on T1.5 and T0.5.
  - For the 4 models whose Java output compiles (abb, cotp, s7com, tpkt), a test shows the new output is equivalent in meaning: same protocol id and alias, attribute ids and aliases, offsets, lengths, types, scopes and registrations.
  - `docs/behaviour-changes.md` lists every other difference, each with its Java bug and test.
  - Verify: the parity test is green in CI.
- **T1.7 Compile-and-load matrix for the generator.** Depends on T1.5 and T0.3.
  - Every corpus model's output compiles with `-Wall -Wextra -Werror` under gcc and clang, against the oldest and newest supported mmt-dpi, and loads through `init_extraction()`.
  - Verify: a CI matrix job.

### Phase 2 — Workflow commands

- **T2.1 `mmt-plugin validate`.** Depends on T1.3 and T1.4.
  - Schema and semantic checks.
  - SDK checks: the id and name are free (headers plus the run-time registry of the installed plugins), the parent protocols exist, the `.so` name sorts after `libmmt_tcpip.so`, and the id is in the reserved range (warning).
  - Verify: a test per check, including the load-order and duplicate-name pitfalls from #2.
- **T2.2 Generated vs user code.** Depends on T1.5.
  - Hook prototypes in the generated header, plus a scaffolded `src/<name>_impl.c`.
  - Regeneration never touches `src/`. A model change that adds a hook fails the build with a clear message.
  - Verify: tests for regenerate-after-edit and for a missing hook.
- **T2.3 `mmt-plugin build`.** Depends on T1.5.
  - SDK detection, hardened gcc flags with `-Werror`, output `build/mmtp_<label>.so`.
  - Verify: builds every corpus model in CI.
- **T2.4 `mmt-plugin test`.** Depends on T2.3 and T0.4.
  - A generated host harness loads the plugin and checks each packet test in `tests/*.yaml` (expected classification and attribute values).
  - `--sanitize` runs ASan/UBSan with truncated and random packets, which must not crash.
  - `--bench` reports packets per second against an empty-plugin baseline (advisory).
  - Verify: green on every corpus model, plus a deliberately broken model that must fail.
- **T2.5 `install`, `uninstall` and `doctor`.** Depends on T2.3.
  - `install` defaults to a user prefix; `--system` targets `/opt/mmt`. Both write an install manifest that `uninstall` follows.
  - `doctor` reports the toolchain, SDK version, plugin directory, load order and id/name clashes.
  - Verify: tests in a temporary prefix; no sudo in CI.
- **T2.6 Consistency and resilience across commands.** Depends on T1.5.
  - Every command takes `--json`.
  - Documented exit-code classes: usage, model, SDK, build, test.
  - `plugin.lock` records the generator version, SDK profile and model hash, and `generate --check` fails when the generated files are stale.
  - Verify: CLI contract tests, including the JSON schema of each command's output.
- **T2.7 `mmt-plugin init`.** Depends on T2.2.
  - Scaffolds a plugin project (`plugin.yaml`, `src/`, `tests/`) that builds and tests green out of the box.
  - Verify: an end-to-end test from init to test.

### Phase 3 — Model

- **T3.1 `plugin.yaml` and its JSON Schema.** Depends on T1.3.
  - Covers everything PDL can express, plus explicit parents and classification, absolute offsets by default, and variable-length attributes.
  - The schema is published in the repo and in each release.
  - Verify: schema tests, plus a round trip for every corpus model.
- **T3.2 `mmt-plugin import`.** Depends on T3.1.
  - Converts PDL v1 to YAML without losing anything, and warns on constructs that relied on Java bugs.
  - `generate` accepts both formats and produces identical output.
  - Verify: every corpus PDL model imports, and both formats generate identical C.

### Phase 4 — Autonomy

- **T4.1 `mmt-plugin scaffold --from-pcap`.** Depends on T2.4 and T3.1.
  - Slices the payloads of a pcap under a given parent (for example `udp:port=4433`) into packet tests and proposes a field skeleton.
  - Verify: tests on sample pcaps.
- **T4.2 Agent skill `skills/mmt-plugin-author`.** Depends on T2.6, T3.2 and T4.1.
  - Given a protocol spec or a pcap, an agent drafts `plugin.yaml`, then iterates validate, generate, build and test (with `--json`) until green.
  - Ships with evals, plus AGENTS.md guidance.
  - Verify: the evals pass.

### Phase 5 — Migration and release

- **T5.1 Port the 16 example plugins.** Depends on T2.4 and T3.2.
  - Each becomes a plugin project with packet tests and builds against mmt-dpi 1.10.2, or is listed with a reason.
  - Verify: CI builds and tests every ported example.
- **T5.2 User documentation.** Depends on T5.1.
  - README rewrite, user guide, model reference generated from the schema, and a migration guide from the Java tool.
  - Verify: doc link check, and every example command runs in CI.
- **T5.3 Packaging and release automation.** Depends on T2.5.
  - PyPI or GitHub release artifacts installable with `uv tool install`, the container image, and a release workflow with provenance.
  - Verify: a dry-run release from `dev`.
- **T5.4 Retire the Java tool.** Depends on T1.6 and T5.1.
  - Delete `legacy/` once parity is proven.
  - Verify: no Java left in the build or docs.
- **T5.5 Release: merge `dev` into `main`.** Depends on all tasks above.
  - A release PR from `dev` to `main` with a changelog, then the first release of the Python generator. Needs Luong's explicit OK.

### Cross-repo

- **X1 (Montimage/mmt-dpi):** reserve and document a protocol id range for third-party plugins (950–999) in `docs/Add-New-Protocol.md`, next to the plugin-loading section from #71. Filed as Montimage/mmt-dpi#73. T2.1 reads it.

## Critical path

T0.1 → T0.2 → T1.1 → T1.2 → T1.3 → T1.5 → T2.3 → T2.4 → T5.1 → T5.5.
