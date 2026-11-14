# mmt-plugin CLI design

Status: approved by Luong on 2026-11-13, with decisions D1–D14 (section 12). D11 was provisional until #21 checked which plugin directories mmt-dpi 1.10.2 scans; it is kept, with the reason in section 12. Plan: [`workflow-redesign.md`](workflow-redesign.md) (tasks T1.1–T4.1, issues #10–#26 and #43).
Inputs: the plan, the Python skeleton, and four answers from the maintainer: no config file beyond `plugin.yaml`; shell completions under #22; Linux only; no interactive prompts.
Section 12 lists every point where this design goes beyond or against the plan, each as a decision with the recommendation that was approved. Section 13 says where each part is implemented.

## 1. Tool name and entry points

- Distribution: `mmt-plugin` (PyPI/uv name, unchanged). Binary: `mmt-plugin`. Module: `python -m mmt_plugin`. Entry: `mmt_plugin.cli:main(argv) -> int` (unchanged signature).
- Parser: **argparse** (stdlib, already in place). Decision D1.
- Platform: Linux (amd64, arm64). `--help` says so; macOS best-effort, no CI.

## 2. Command tree

```
mmt-plugin [global options] <command> [command options] [args]

  init        Create a plugin project that builds and tests green        T2.7  #23
  import      Convert a PDL v1 model to plugin.yaml                      T3.2  #25
  validate    Check a model: schema, semantics, SDK, ids, load order     T2.1  #17
  generate    Write the generated C sources and plugin.lock              T1.5  #14 (incl. --check)
  build       Compile build/mmtp_<label>.so                              T2.3  #19
  test        Run the packet tests (tests/*.yaml) against the plugin     T2.4  #20
  install     Copy the plugin into a prefix and record a manifest        T2.5  #21
  uninstall   Remove an installed plugin by following its manifest       T2.5  #21
  doctor      Report toolchain, SDK, plugin directory, load order, clashes T2.5 #21
  scaffold    Draft packet tests and a field skeleton (--from-pcap)      T4.1  #26  (added in T4.1)
  completion  Print a shell completion script: bash, zsh or fish         T2.6  #22
```

The workflow is the plan's: `init` (or `import`) → `validate` → `generate` → `build` → `test` → `install`. `completion` is the only command outside the plan's list (approved with the maintainer's answers, D9). A command that does not exist yet is not registered (no placeholder that exits 1): `--help` lists only what works.

## 3. Global options

Accepted before or after the command (`mmt-plugin --json validate` = `mmt-plugin validate --json`).

| Option | Type | Default | Help |
|---|---|---|---|
| `-h`, `--help` | flag | — | Show help for this level and exit 0. Help is always plain text. |
| `--version` | flag | — | Print `mmt-plugin <version>` and exit 0 (with `--json`: an envelope with `result.version`, `result.python`, `result.sdk_profiles`). |
| `-C`, `--project DIR` | path | `.` | The plugin project directory (holds `plugin.yaml`). All relative paths in output are relative to it. |
| `--json` | flag | off | Print exactly one JSON envelope (section 6) on stdout; nothing else on stdout. |
| `--no-color` | flag | off | No escape codes at all (same as `NO_COLOR=1`). |
| `-q`, `--quiet` | flag | off | Human mode: print nothing on stdout, only errors on stderr; the exit code is the result. Ignored with `--json`. |
| `-v`, `--verbose` | count | 0 | `-v`: each stage and every external command line (gcc, harness) on stderr. `-vv`: debug, plus tracebacks on internal errors. |

All parsers use `allow_abbrev=False` (an abbreviation would break when an option is added later). `--` ends options. No option is ever prompted for.

**Shared option groups** (only on the commands that use them; never accepted and ignored):

- *SDK*: `--sdk PREFIX` (an mmt-dpi prefix: `dpi/include`, `dpi/lib`, `plugins/`), `--sdk-profile VERSION` (e.g. `1.10.2`).
- *Write safety*: `--dry-run` (report every action, write nothing, exit as if it ran), `--force` (overwrite a file the tool would otherwise refuse to; see section 8).
- *Strictness*: `--strict` (warnings count as errors and fail with their class's exit code).
- *Chaining*: `--no-deps` (do not run a stale upstream stage; fail with exit 7 instead). See D5.

## 4. Arguments and options per command

`MODEL` everywhere: a `plugin.yaml` path, a PDL v1 file (for example `plugins/tpkt_plugin`), or `-` for stdin. Default: `<project>/plugin.yaml`. The format is detected (`.yaml`/`.yml` → YAML, else PDL); `--model-format {auto,yaml,pdl}` overrides it (needed for `-`).
`SELECTOR` everywhere: `<proto>[:<key>=<value>[,<key>=<value>...]]`, for example `udp:port=4433`, `tcp:port=102`, `ethernet:ethertype=0x8624`.

### `init LABEL`
| Arg/option | Type | Req | Default | Help |
|---|---|---|---|---|
| `LABEL` | `[a-z][a-z0-9_]*` | yes | — | Protocol label; names `mmtp_<label>.so`, `src/<label>_impl.c`. |
| `--dir DIR` | path | no | `./<LABEL>` | Where to create the project (`.` allowed when empty or already this project). |
| `--id N` | int | no | lowest id in 950–999 free in the detected SDK; 950 with a warning if no SDK is found | Protocol id. |
| `--name NAME` | str | no | `LABEL` upper-cased | Registered protocol name. |
| `--parent SELECTOR` | selector | no | none (warning `model.no-parent`: the plugin is never handed packets) | Parent protocol. |
| `--sdk-profile VERSION` | str | no | newest bundled profile | Pinned into `plugin.yaml` (`sdk.profile`). |
| `--dry-run`, `--force` | flags | no | off | Section 8. |

Creates `plugin.yaml`, `src/<label>_impl.c`, `tests/<label>-basic.yaml`, `.gitignore` (`build/`). Generated sources are not created by `init`: `build`/`test` generate them (D5).

### `import PDL`
| Arg/option | Type | Req | Default | Help |
|---|---|---|---|---|
| `PDL` | path or `-` | yes | — | PDL v1 model file. |
| `-o`, `--output FILE` | path or `-` | no | `<project>/plugin.yaml` | `-` writes the YAML to stdout (usage error with `--json`). |
| `--dry-run`, `--force`, `--strict` | flags | no | off | Warnings flag constructs that relied on Java bugs (`model.legacy-*`). |

### `validate [MODEL]`
| Option | Type | Default | Help |
|---|---|---|---|
| `--model-format` | enum | `auto` | See above. |
| `--sdk`, `--sdk-profile` | | detected | SDK used for the id/name, parent and load-order checks. |
| `--no-sdk` | flag | off | Skip the checks that need an installed SDK (reported as `skip`). Without it, a missing SDK is exit 4 (D12). |
| `--strict` | flag | off | Warnings fail. |

Checks (each reported pass/warn/fail/skip, with a stable `id`): `schema`, `semantics`, `sdk-profile`, `id-free`, `name-free` (case-insensitive; SDK headers plus installed plugins), `parents-exist`, `load-order` (`mmtp_<label>.so` after `libmmt_tcpip.so` in the C and the current `LC_COLLATE`), `id-range` (950–999, warning).

### `generate [MODEL]`
| Option | Type | Default | Help |
|---|---|---|---|
| `-o`, `--output DIR` | path | `<project>/generated/` | Output directory for the generated `.h`/`.c` (D6). |
| `--model-format` | enum | `auto` | |
| `--sdk-profile VERSION` | str | CLI > env > `plugin.yaml` > detected SDK > newest (warning) | Generation needs a profile, not an installed SDK. |
| `--sdk PREFIX` | path | detected | Only used to pick the profile. |
| `--check` | flag | off | Write nothing; exit 7 if any generated file or `plugin.lock` would change, 0 if up to date. |
| `--dry-run`, `--force`, `--strict` | flags | off | `--force` overwrites a generated file that was hand-edited. |

Writes `plugin.lock` at the project root; for a `MODEL` outside a project (no `plugin.yaml` in `--project`), into the output directory. Never writes under `src/`.

### `build [MODEL]`
| Option | Type | Default | Help |
|---|---|---|---|
| `MODEL` | path | `<project>/plugin.yaml` | As for `generate`; not `-` (#19). |
| `--model-format` | enum | `auto` | |
| `--sdk`, `--sdk-profile` | | detected | |
| `--cc CC` | str | `CC` env, else `gcc` | Compiler (gcc or clang). |
| `--build-dir DIR` | path | `<project>/build/` | Output: `<build-dir>/mmtp_<label>.so`. |
| `--rebuild` | flag | off | Compile even when the inputs are unchanged. |
| `--no-deps`, `--dry-run`, `--strict` | flags | off | `--dry-run` prints the compiler command lines and writes nothing. |

Flags: hardened (`-O2 -fPIC -shared -fstack-protector-strong -D_FORTIFY_SOURCE=2 -Wl,-z,relro,-z,now`) with `-Wall -Wextra -Werror`; the exact list is fixed in #19 (section 13) and reported in `result.cflags` and `result.ldflags`.

### `test [PACKETS...]`
| Arg/option | Type | Default | Help |
|---|---|---|---|
| `PACKETS` | paths/globs | `<project>/tests/*.yaml` | Packet tests (corpus schema 1): files, directories (their `*.yaml`) or globs. |
| `--model MODEL` | path | `<project>/plugin.yaml` | The model, as `build`'s `MODEL` (an option: the positionals are `PACKETS`; #20). |
| `--model-format`, `--build-dir` | | | As for `build`. |
| `--sanitize` | flag | off | Rebuild with ASan/UBSan and also run truncated and random packets; any crash fails. |
| `--seed N` | int | `0` | Seed for random packets: the same seed gives the same packets. |
| `--fuzz-count N` | int | `1000` | Random/truncated packets per test with `--sanitize`. |
| `--bench` | flag | off | Packets per second vs an empty-plugin baseline. Advisory: never changes the exit code. |
| `--fail-fast` | flag | off | Stop at the first failing packet. |
| `--sdk`, `--sdk-profile`, `--cc`, `--no-deps`, `--strict` | | | |

The harness (#20) is generated into `<build-dir>/test/` and compiled against the SDK. It loads the plugin with `init_extraction()` from a temporary plugin directory that holds only the SDK's `libmmt_tcpip.so` and the plugin (its own `MMT_DPI_PLUGINS_DIR`), attaches the protocol to Ethernet itself (EtherType 0x88b5), so packets are tested without the user code's parent registration, and checks the classification, the next protocol and each attribute value of every packet; it restarts after a crash, so every packet is reported. `--sanitize` builds `<build-dir>/sanitize/mmtp_<label>.so`; a crash names its test, its index for the seed, and its bytes.

### `install` / `uninstall [LABEL]`
| Option | Type | Default | Help |
|---|---|---|---|
| `--prefix DIR` | path | `MMT_PLUGIN_PREFIX`, else `${XDG_DATA_HOME:-~/.local/share}/mmt` (D11) | Install prefix; the plugin goes to `<prefix>/plugins/`. |
| `--system` | flag | off | Prefix `/opt/mmt`. Never uses sudo; not writable → exit 4. Exclusive with `--prefix`. |
| `--sdk` | path | detected | (`install`) for the load-order and clash checks. |
| `--no-deps`, `--dry-run`, `--force` | flags | off | |
| `LABEL` | str | the project's label | (`uninstall`) which plugin to remove. |

Both read/write the manifest `<prefix>/plugins/.mmt-plugin/<label>.json` (files, sha256, tool version). `uninstall` removes only files listed there whose hash still matches; a modified file is kept and is exit 7 unless `--force`. Uninstalling something not installed: exit 0, `result.removed: []`, warning `state.not-installed`.

### `doctor`
Options: `--sdk`, `--prefix`/`--system`, `--cc`. Runs inside or outside a project. Checks: Python, compiler and version, SDK prefix/version/profile (and where each came from), plugin directories, load order of the installed plugins, id/name clashes among them (and with this project's model when run in one). Exit 0 when nothing fails (warnings allowed), 4 otherwise.

### `scaffold --from-pcap PCAP --parent SELECTOR` (T4.1)
Options: `--max-packets N` (default 20), `--tests-dir DIR` (default `<project>/tests/`), `--dry-run`, `--force`. Writes packet tests and `plugin.proposed.yaml`; never edits `plugin.yaml`. A malformed pcap is exit 3.

### `completion {bash,zsh,fish}`
Prints the script on stdout, generated from the argparse tree (so it cannot drift from the parser). Install: `mmt-plugin completion bash > ~/.local/share/bash-completion/completions/mmt-plugin`.

## 5. Exit codes (D2)

Aligned with the cli-builder skill's canonical table (0, 1, 2, 3, 130) and the plan's classes (usage, model, SDK, build, test), plus one class for on-disk state.

| Code | Class (`error.class`) | Meaning | Examples (`error.code`) |
|---|---|---|---|
| 0 | — | Success (warnings allowed unless `--strict`) | |
| 1 | `internal` | Unexpected failure: a bug, an I/O error with no better class | `internal.unexpected`, `internal.io` |
| 2 | `usage` | Bad arguments or option combination | `usage.unknown-option`, `usage.conflicting-options` |
| 3 | `model` | The input model or data is wrong (= skill "input error") | `model.syntax`, `model.duplicate-name`, `model.id-taken`, `model.bad-pcap` |
| 4 | `sdk` | SDK, toolchain or prefix problem | `sdk.not-found`, `sdk.invalid-prefix`, `sdk.profile-not-found`, `sdk.cc-not-found`, `sdk.prefix-not-writable` |
| 5 | `build` | The compiler or linker failed | `build.compile-failed`, `build.missing-hook` |
| 6 | `test` | A packet test failed, or a sanitizer/crash | `test.packet-failed`, `test.crash` |
| 7 | `state` | Files on disk are not what the command needs | `state.stale` (`generate --check`, `--no-deps`), `state.exists`, `state.modified` |
| 130 | `interrupted` | SIGINT; temp files removed, child processes killed | `interrupted` |

Rules:
- A command runs its stages in order and stops at the first failing stage; the exit code is that stage's class. A taken id or name is `model` (3): the fix is in the model.
- Warnings never change the exit code, except with `--strict`.
- A closed stdout (`| head`) ends the run quietly (no traceback).
- `--help` lists the codes; each command's help lists only the codes it can return.

Per command (besides 0, 1, 2, 130 everywhere):

| | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|
| init | ✓ | | | | ✓ |
| import | ✓ | | | | ✓ |
| validate | ✓ | ✓ | | | |
| generate | ✓ | ✓ | | | ✓ |
| build | ✓ | ✓ | ✓ | | ✓ |
| test | ✓ | ✓ | ✓ | ✓ | ✓ |
| install | ✓ | ✓ | ✓ | | ✓ |
| uninstall | | ✓ | | | ✓ |
| doctor | | ✓ | | | |
| scaffold | ✓ | | | | ✓ |
| completion | | | | | |

## 6. The `--json` envelope (shared by every command)

One JSON document on stdout, UTF-8, keys in schema order, ending in one newline. Paths relative to the project when inside it (POSIX separators), absolute otherwise. No timestamps or durations outside `result.stats` (so two runs on the same inputs give the same bytes, timings aside). The one exception is `test --bench`, whose `result.bench` is a measurement (#20).

```json
{
  "schema_version": 1,
  "tool": {"name": "mmt-plugin", "version": "0.3.0"},
  "command": "validate",
  "ok": false,
  "exit_code": 3,
  "error": {
    "class": "model",
    "code": "model.duplicate-name",
    "message": "1 error in plugin.yaml",
    "hint": "fix the errors in diagnostics, then re-run validate"
  },
  "diagnostics": [
    {
      "severity": "error",
      "code": "model.duplicate-name",
      "message": "attribute name \"LEN\" is already used by \"len\" (names are case-insensitive)",
      "hint": "rename one of the two attributes",
      "location": {"file": "plugin.yaml", "line": 14, "column": 9, "end_line": 14, "end_column": 12},
      "related": [{"message": "first defined here", "location": {"file": "plugin.yaml", "line": 9, "column": 9}}]
    }
  ],
  "context": {
    "project": ".",
    "sdk": {"prefix": "/home/u/mmt/opt/mmt", "version": "1.10.2", "profile": "1.10.2", "source": "MMT_BASE", "profile_source": "sdk"}
  },
  "result": {"...": "command-specific, below"}
}
```

- `schema_version` (int): bumped only on a breaking change (a key removed, renamed or changing meaning). New keys are additive and do not bump it. Consumers must ignore unknown keys.
- `ok` = (`exit_code` == 0). `error` is `null` when `ok`. `diagnostics` is always an array (sorted by file, line, column, code).
- `severity`: `error` | `warning` | `note`. `location` is `null` for diagnostics with no file. `line`/`column` are 1-based; columns count Unicode code points. Compiler diagnostics are mapped into the same shape (`code: "build.cc"`, the compiler's file:line:col relative to the project).
- Codes (`error.code`, `diagnostics[].code`) are stable dotted slugs whose prefix is the class (D8). The list is documented and tested; a code is never reused for another meaning.
- `context`: the resolved settings and where each came from (`source`: `--sdk`, `MMT_BASE`, `pkg-config`, `/opt/mmt`, `plugin.yaml`, `default`). `sdk` is `null` for commands that do not use it. In `sdk` (#13), `source` is where the prefix came from (`null` with no SDK), `version` is the SDK's `VERSION` macro (`null` when unknown), and `profile_source` is where the profile came from: `--sdk-profile`, `MMT_PLUGIN_SDK_PROFILE`, `plugin.yaml`, `sdk` (the detected version) or `default` (no SDK).
- `result` is `null` on usage errors. With `--json`, a usage error is still an envelope (the CLI checks for a `--json` token before `--` before parsing). `--help --json` prints plain help.
- JSON Schemas: one for the envelope and one per command's `result`, shipped in the package (`mmt_plugin/schemas/cli/v1/*.json`) and in each release; contract tests validate every command's output against them (#22).

`result` per command (main keys; lists sorted by path or id):

| Command | `result` |
|---|---|
| init | `project`, `files: [{path, action}]` (`created`/`unchanged`/`would-create`) |
| import | `input`, `output`, `model_hash`, `files: [{path, action}]` |
| validate | `model`, `format` (`yaml`/`pdl`), `protocol: {label, name, id}`, `checks: [{id, status, detail}]` |
| generate | `profile`, `files: [{path, action, sha256}]` (`created`/`updated`/`unchanged`/`removed`/`would-*`), `lock`, `check`, `dry_run` |
| build | `stages: [{name, status}]`, `artifact: {path, sha256}`, `cc: {path, version}`, `cflags`, `up_to_date` (#19 adds `model`, `profile`, `build_dir`, `ldflags`, `commands`, `dry_run`) |
| test | `stages`, `summary: {total, passed, failed, skipped}`, `packets: [{id, file, status, failures: [{attribute, expected, actual}]}]`, `sanitize: {seed, count, crashes}` or `null`, `bench: {pps, baseline_pps, ratio, samples}` or `null`, `stats: {elapsed_ms}` (#20 adds `model`, `profile`, `build_dir`, `packets[].attributes`; `crashes` is a list of `{test, index, length, reason, bytes}`) |
| install | `prefix`, `manifest`, `files: [{path, action, sha256}]` (#21 adds `model`, `label`, `protocol`, `build`, `dry_run`) |
| uninstall | `prefix`, `removed`, `kept`, `missing` (#21 adds `label`, `manifest`, `dry_run`) |
| doctor | `checks: [{id, status, detail}]`, `toolchain`, `plugin_dirs`, `load_order`, `clashes` |
| scaffold | `pcap`, `parent`, `files: [{path, action}]`, `skeleton` |
| completion | `shell`, `script` |

Not used: NDJSON/streaming events. One document at the end is enough for the loop the agent skill (T4.2) runs (validate → generate → build → test); long commands show progress only on a TTY stderr.

## 7. I/O behaviour

- **stdout**: the command's result only: the human summary (styled or plain, section 10) or the JSON envelope. Nothing else, ever, so `--json` output always parses.
- **stderr**: everything for humans that is not the result: diagnostics in compiler style, warnings, `-v` logs, progress. With `--json`, stderr carries nothing except `-v`/`-vv` logs (diagnostics are in the envelope).
- **Diagnostics on stderr** (human mode), one per line, editors can jump to them:
  ```
  plugin.yaml:14:9: error: attribute name "LEN" is already used by "len" (names are case-insensitive) [model.duplicate-name]
    plugin.yaml:9:9: note: first defined here
    hint: rename one of the two attributes
  ```
- **stdin**: `-` as `MODEL` (`validate -`, `generate -`) or `PDL` (`import -`); the location's file is `<stdin>`. `import PDL -o -` writes YAML to stdout.
- **Compiler output**: captured, parsed into diagnostics, and shown on stderr (human) or in the envelope (`--json`); `-v` also echoes the raw compiler output on stderr.
- **No prompts**: no command ever reads from the terminal. A choice the tool cannot make is a usage error or an exit 7 with a hint naming the flag (`--force`, `--id`, ...).
- **Signals**: SIGINT kills the compiler/harness process group, removes temp files, prints the envelope (`--json`) or one line on stderr, exit 130. A closed stdout pipe ends quietly.

## 8. Idempotency, atomic writes and `--dry-run`

| Command | Re-run on unchanged inputs | Refuses (exit 7) unless `--force` | `--dry-run` |
|---|---|---|---|
| init | no-op (files with identical content are `unchanged`) | a target file exists with other content | yes |
| import | no-op | output exists with other content | yes |
| generate | no-op: unchanged files are not rewritten (mtimes kept) | a generated file was hand-edited (hash ≠ `plugin.lock`) | yes; `--check` = dry run + exit 7 on drift |
| build | no-op when the input hash (sources, flags, cc, profile) is unchanged | — | yes (prints commands) |
| test | always runs the tests; builds only if stale | — | no |
| install | no-op when the same file is installed | a different file at the target that is not in the manifest | yes |
| uninstall | no-op when not installed | a manifest file was modified since install | yes |
| scaffold | no-op | output exists with other content | yes |

- Atomic writes: each file is written to a temp file in the same directory, fsynced, then `os.replace`d. `generate` renders the whole set first and writes `plugin.lock` last, so an interrupted run leaves either the old set (and `--check` reports it) or the new one. `build` links to a temp name and renames, so a failed build never leaves a broken `.so`.
- Output is deterministic: byte-identical on re-run (plan T1.5); staleness is hash-based, never mtime-based.
- `generate` removes a file it generated before and no longer produces only when `plugin.lock` lists it and it is unmodified.

## 9. Config strategy (precedence: CLI > env > `plugin.yaml` > defaults)

No other config file (maintainer's answer). Machine-specific values (prefixes, compiler) are never read from `plugin.yaml`, which is committed.

| Setting | CLI | Env | `plugin.yaml` | Default |
|---|---|---|---|---|
| Project dir | `-C` | — | — | `.` |
| SDK prefix | `--sdk` | `MMT_BASE` | — | `mmt-dpi.pc` on pkg-config's search path, then `/opt/mmt` |
| SDK profile | `--sdk-profile` | `MMT_PLUGIN_SDK_PROFILE` | `sdk.profile` | detected SDK version → nearest profile (warning `sdk.profile-fallback`); no SDK → newest profile (warning) |
| Compiler | `--cc` | `CC` | — | `gcc` |
| Install prefix | `--prefix` / `--system` | `MMT_PLUGIN_PREFIX` | — | `${XDG_DATA_HOME:-~/.local/share}/mmt` (D11) |
| Color | `--no-color` | `NO_COLOR`, `FORCE_COLOR`, `TERM` | — | auto (section 10) |
| Width | — | `COLUMNS` | — | terminal size, else 80 |
| Strictness | `--strict` | — | — | off |

Relative paths in `--sdk`/`MMT_BASE`/`--prefix` are resolved against the current directory and reported absolute in `context`. A prefix without `dpi/include/mmt_log.h` is `sdk.invalid-prefix` (exit 4) with a hint.

SDK detection and profiles (#13, `mmt_plugin.sdk`):

- The pkg-config file is `mmt-dpi.pc` (the package installs `/usr/share/pkgconfig/mmt-dpi.pc`). It is read, not run: the directories of `PKG_CONFIG_PATH`, then of `PKG_CONFIG_LIBDIR` when set or else pkg-config's default search path, are searched in order, and the prefix is the file's `includedir` without its final `/dpi/include`. A file whose `includedir` is not such an absolute path is `sdk.invalid-pkg-config` (exit 4).
- An explicit prefix that is not valid (`--sdk`, `MMT_BASE`, the `.pc` file) is an error, never a fall-through to the next source; an empty `--sdk` is `sdk.invalid-prefix`, not the current directory (an empty `MMT_BASE` is unset). `/opt/mmt` is only looked at when it exists; no SDK at all is `sdk.not-found` (exit 4) for the commands that need one.
- The SDK version is the `VERSION` string macro of `dpi/include/mmt_core.h`, read from the prefix itself.
- An explicit profile (CLI, env or `plugin.yaml`) that is not bundled is `sdk.profile-not-found` (exit 4). A detected version with no bundled profile gets the nearest one, with the warning `sdk.profile-fallback`: the newest bundled profile not above that version, else the oldest (a pre-release such as `1.10.2-rc1` is just below its release `1.10.2`); an unknown version gets the newest. With no SDK and nothing pinned, the newest profile is used with the warning `sdk.profile-default`.
- The profiles are `mmt_plugin/sdk/profiles/<version>.json` (schema: `mmt_plugin/schemas/sdk/v1/profile.json`). CI checks each entry against the published mmt-dpi headers with `python -m mmt_plugin.sdk.headercheck --sdk PREFIX` (gcc and clang, amd64 and arm64).

## 10. Visual style (btop)

**Components per command** (stdout, styled mode; plain mode prints the same records, tab-separated):

| Command | Styled stdout | Plain stdout records |
|---|---|---|
| validate | box `validate <label>`, checks table with status symbols, footer `N checks · N pass · N warnings` | `check⇥status⇥detail` |
| generate | box `generate <label>`, files table (`● created`, `● unchanged`, `▲ updated`, `✗ stale` for `--check`) | `action⇥path` |
| build | box `build <label>`: stages, artifact, size, cc, flags | `stage⇥status`, then `artifact⇥path⇥sha256` |
| test | box `test <label>`: packets table, pass meter; with `--bench` a pps meter vs baseline and a braille sparkline of the samples (with min/max/last numbers) | `packet⇥status⇥detail`; bench `bench⇥pps⇥baseline_pps⇥ratio` |
| install / uninstall | box with prefix and files table | `action⇥path` |
| doctor | one box, four sections divided by `├───┤` (toolchain, SDK, plugin dirs, load order/clashes), each with its own border role, status symbols | `check⇥status⇥detail` |
| init / import / scaffold | box with files table | `action⇥path` |
| completion, `--version`, `--help` | plain text only | same |

stderr: errors `✗ error:` (high, bold) + `hint:` (dim), compiler-style locations first; warnings `▲ warning:` (mid). Progress (TTY stderr only, operations > 2 s): one `\r`-redrawn line, `compiling mmtp_tpkt.so · 3.1s`, or a meter `■■■■■····· 52/100 packets` in `test`; cleared before the result prints. Append-only otherwise; no alternate screen, no cursor movement upward.

**Theme**: the cli-builder skill's btop roles, unchanged: `text` (terminal default), `title` (bold), `accent` (`#b54040` bold / 16-color `91` bold), `dim` (faint), `border` (`cpu_box #556d59`/`32` by default; `mem_box`, `net_box`, `proc_box` for doctor's sections), `low → mid → high` (`#77ca9b → #cbc06c → #dc4c4c` / `92 93 91`) for meters and pass/warn/fail. Statuses always print their word, so color never carries meaning alone.

**Fallbacks** (decided per stream, once, right after parsing; commands never probe the terminal):
- stdout is plain with `--json` (wins over `FORCE_COLOR`), when `TERM=dumb`, or when it is not a TTY and `FORCE_COLOR` is unset/empty/`0`. Plain = records only, tab-separated, no header, no frames or escape codes; control characters in user text escaped (`\t`, `\n`, `\xNN`, `\\`).
- Color tier: `--no-color` or non-empty `NO_COLOR` → none (no SGR at all, not even bold); `COLORTERM=truecolor|24bit` → 24-bit; `TERM=*256color*` → 256; else 16.
- Glyphs: Unicode when the stream encoding is UTF-8, else ASCII (`+ - |`, `[title]`, `#`/`.` meters, `+ ! x` statuses).
- `--help` stays plain: argparse on Python 3.10–3.13 has no styling hook, and on 3.14+ the CLI passes `color=False` so help never carries escape codes (it would otherwise follow its own environment rules).
- Guarantee: `--json`, piped and `NO_COLOR` output contain no ESC (0x1b) byte (tested).

**Implementation**: a zero-dependency module `mmt_plugin/ui/style.py` (#22) (SGR codes, the three per-stream decisions, box/table/status/meter/sparkline/error/progress renderers, each taking an explicit mode). Width function: `cell_width()` from `unicodedata` (East Asian Wide/Fullwidth = 2, combining and zero-width = 0). No `rich` dependency (D7).

**Mockup** — `mmt-plugin validate` in a project with id 900. Styled, Unicode, color tier none (with color: green border, bold title, `●` green, `▲` yellow):

```text
╭─┐validate tpkt┌────────────────────────────────────────────────╮
│ check              status    detail                            │
│ schema             ● pass    plugin.yaml, schema 1             │
│ semantics          ● pass    7 attributes, 0 hooks             │
│ sdk profile        ● pass    1.10.2 (MMT_BASE)                 │
│ id free            ● pass    900: not in SDK or installed      │
│ name free          ● pass    TPKT: not taken                   │
│ parents exist      ● pass    tcp                               │
│ load order         ● pass    after libmmt_tcpip.so             │
│ reserved id range  ▲ warn    900 outside 950-999               │
╰─┘8 checks · 7 pass · 1 warning└────────────────────────────────╯
```

ASCII glyphs:

```text
+-[validate tpkt]------------------------------------------------+
| check              status    detail                            |
| schema             + pass    plugin.yaml, schema 1             |
| semantics          + pass    7 attributes, 0 hooks             |
| sdk profile        + pass    1.10.2 (MMT_BASE)                 |
| id free            + pass    900: not in SDK or installed      |
| name free          + pass    TPKT: not taken                   |
| parents exist      + pass    tcp                               |
| load order         + pass    after libmmt_tcpip.so             |
| reserved id range  ! warn    900 outside 950-999               |
+-[8 checks, 7 pass, 1 warning]----------------------------------+
```

Plain (piped; `⇥` marks a tab): 

```text
schema⇥pass⇥plugin.yaml, schema 1
semantics⇥pass⇥7 attributes, 0 hooks
sdk-profile⇥pass⇥1.10.2 (MMT_BASE)
id-free⇥pass⇥900: not in SDK or installed
name-free⇥pass⇥TPKT: not taken
parents-exist⇥pass⇥tcp
load-order⇥pass⇥after libmmt_tcpip.so
id-range⇥warn⇥900 outside 950-999
```

`mmt-plugin test` with one failing packet (exit 6), styled, tier none:

```text
╭─┐test tpkt┌────────────────────────────────────────────────────╮
│ packet                 status    detail                        │
│ tpkt/cotp-cr           ● pass    4 attributes                  │
│ tpkt/cotp-dt           ● pass    4 attributes                  │
│ tpkt/short-header      ✗ fail    length: expected 7, got 1792  │
│ tpkt/version-3         ● pass    4 attributes                  │
│                                                                │
│ passed   ■■■■■■■■■■■■■■■·····  75%   3 of 4 packets            │
╰─┘4 packets · 1 failed · build up to date└──────────────────────╯
```

## 11. Example invocations

```sh
# 1. New plugin, then the whole loop (build and test generate/build first if stale)
mmt-plugin init tpkt --id 961 --parent tcp:port=102
cd tpkt
MMT_BASE=$HOME/mmt/opt/mmt mmt-plugin test

# 2. Agent / CI loop: every step machine-readable, exit code = class
mmt-plugin -C tpkt validate --json | jq '.diagnostics[] | select(.severity == "error")'
mmt-plugin -C tpkt test --json --sdk "$HOME/mmt/opt/mmt" > result.json; echo "exit $?"

# 3. Migrate a legacy PDL model, and generate from PDL without a project (old jar workflow)
mmt-plugin import plugins/tpkt_plugin -o tpkt/plugin.yaml
mmt-plugin generate plugins/tpkt_plugin -o /tmp/tpkt-out --sdk-profile 1.10.2

# 4. CI drift gate: fails with exit 7 if committed generated files are stale
mmt-plugin generate --check

# 5. Install into a private prefix, preview first; then check the environment
mmt-plugin install --prefix "$HOME/mmt/opt/mmt" --dry-run
mmt-plugin install --prefix "$HOME/mmt/opt/mmt"
mmt-plugin doctor --sdk "$HOME/mmt/opt/mmt"

# 6. Fuzz under sanitizers, reproducibly; completions
mmt-plugin test --sanitize --seed 42 --fuzz-count 5000
mmt-plugin completion zsh > ~/.zfunc/_mmt-plugin
```

## 12. Decisions for the maintainer

Each is where this design goes beyond the plan, conflicts with it, or follows the cli-builder skill where the plan is silent. Recommendation first.

| # | Decision | Recommendation | Alternative |
|---|---|---|---|
| D1 | Parser | **Keep argparse**: already in place and tested, stdlib (no major-version churn), full control of usage errors (needed to put them in the `--json` envelope), small fixed tree so completions are generated from it in-house. | click: built-in bash/zsh/fish completions and `CliRunner`, but a new dependency, help formatting we do not control, and the 5 existing tests rewritten. |
| D2 | Exit codes | **Table in section 5**: 0, 1 internal, 2 usage, 3 model, 4 SDK, 5 build, 6 test, 7 state, 130. Keeps the plan's five classes and the skill's 0/1/2/3/130; adds 7 for `generate --check` drift and refused overwrites. | Fold "state" into 3 (model): but then `--check` drift and a hand-edited file look like a broken model to CI and agents. |
| D3 | JSON flag | **`--json`** (plan), accepted before or after the command; no `--format`. The skill's `--format json` wording is satisfied by `--json`. | Also accept `--format json\|text`: two ways to say one thing. |
| D4 | Streams | **Human diagnostics on stderr in compiler style, result on stdout; `--json` = one envelope on stdout, usage errors included.** | Diagnostics on stdout (ruff style): mixes result and diagnostics for pipes. |
| D5 | Stage chaining | **`build` runs `generate` when stale, `test` and `install` run `build` when stale** (hash-based, reported in `result.stages`); `--no-deps` turns that off (exit 7 when stale). Shortens the agent loop; commands and their order are the plan's. | Strict stages: each command fails with exit 7 if its input is stale; the agent always runs all four. |
| D6 | Project layout | **`plugin.yaml`, `plugin.lock`, `src/<label>_impl.c` (user), `generated/` (generated, committed so `generate --check` gates CI), `tests/*.yaml`, `build/` (ignored).** The plan names `src/`, `tests/`, `plugin.lock` but not where generated code goes. | `gen/`, or generated files under `build/` (not committed; then `--check` has nothing to compare in CI). |
| D7 | Visual style | **btop style, zero-dependency module, help plain** (section 10). | `rich`: less code, but a runtime dependency with its own detection to override. Or decline the btop style (plain text only). |
| D8 | Error codes | **Dotted slugs** (`model.duplicate-name`), prefix = exit class; documented and never reused. | Numeric codes (`M201`): shorter, need a lookup table. |
| D9 | `completion` command | **Add it** (maintainer's answer), under #22. | A hidden `--completion` flag. |
| D10 | `--strict` | **Add it** on validate/import/generate/build/test (warnings fail). For CI and agents that want a warning-free model. | No flag; warnings never fail. |
| D11 | Default user install prefix | **`${XDG_DATA_HOME:-~/.local/share}/mmt`, manifest in `<prefix>/plugins/.mmt-plugin/`, `doctor` reports whether mmt-dpi scans that directory.** Checked in #21 (section 13): mmt-dpi 1.10.2 scans one directory, `MMT_DPI_PLUGINS_DIR` or the one compiled into `libmmt_core` (`/opt/mmt/plugins` in the package), and loads a plugin installed under this prefix through `MMT_DPI_PLUGINS_DIR` (load test `tests/unit/install/test_sdk.py`), so the default is kept. | Default to the detected SDK prefix (`MMT_BASE`) when writable: for the published package, extracted or not, that is not the scanned directory either, and on a host with `/opt/mmt` it would be `--system` by another name. |
| D12 | `validate` without an SDK | **Exit 4 unless `--no-sdk`**: a silently skipped id/name check is how the #2 pitfalls ship. | Skip SDK checks with a warning, exit 0. |
| D13 | `init` defaults | **`--id` = lowest free id in 950–999 from the detected SDK (950 + warning without one); `--parent` optional with a `model.no-parent` warning**, so `init <label>` alone works. | Require `--id` and `--parent`. |
| D14 | Registered commands | **Only implemented commands appear**; each issue registers its command. | Register all now as stubs exiting 1 "not implemented". |

Changes to the existing skeleton (`src/mmt_plugin/cli.py`): none breaking. `--version`, `--help`, the no-command usage error (exit 2) and `python -m` stay as they are; the epilog grows to the full exit-code table.

## 13. Where it is implemented

The contract core is in #43; each command arrives with its own issue (section 2, D14) and adds its codes to `CODES`, its `result` schema and its tests.

| Part | Module | Issue |
|---|---|---|
| Command tree, global options, stream rules (sections 2, 3, 7) | `mmt_plugin.cli`, the registry `mmt_plugin.commands` (`register(subparsers)`, `run(args, ctx) -> Outcome`) | #43 |
| Exit codes (section 5) | `mmt_plugin.exitcodes` | #43 |
| Diagnostics, `CliError`, the code registry `CODES` (sections 5, 6, D8) | `mmt_plugin.diagnostics` | #43 |
| Envelope and its schema (section 6) | `mmt_plugin.envelope`, `mmt_plugin/schemas/cli/v1/envelope.json` | #43 |
| Atomic writes, created/updated/unchanged by sha256 (section 8) | `mmt_plugin.fsio` | #43 |
| Per-stream decisions, plain records, compiler-style diagnostics (section 10) | `mmt_plugin.ui.streams`, `mmt_plugin.ui.render` | #43 |
| A command's `result` schema | `mmt_plugin/schemas/cli/v1/<command>.json` | the command's own issue (for example `validate.json` in #17, `generate.json` in #14) |
| btop style, the registry of `result` schemas and the cross-command contract tests, `completion` | `mmt_plugin.ui.style`; the schema registry `mmt_plugin/schemas/cli/v1/` (read by `mmt_plugin.schemas`); the contract tests `tests/unit/test_contract.py`; `mmt_plugin.commands.completion` | #22 |
| `plugin.lock`, `generate --check` | `mmt_plugin.commands.generate`, `mmt_plugin.lock` | #14 |
| Generated vs user code: the hooks, the scaffold `src/<label>_impl.c`, the missing-hook check (`build.missing-hook`) | `mmt_plugin.codegen` (`scaffold`, `templates/impl.c.j2`), `mmt_plugin.codegen.hooks` | #18 |
| `build`: stages, flags, compiler diagnostics, the input hash | `mmt_plugin.commands.build` | #19 |
| `test`: packet tests, the host harness, `--sanitize`'s random packets, the bench baseline | `mmt_plugin.commands.test`, `mmt_plugin.testing` | #20 |
| `install`, `uninstall`, the install manifest and prefix; `doctor` | `mmt_plugin.commands.install`, `mmt_plugin.manifest`, `mmt_plugin/schemas/install/v1/manifest.json`; `mmt_plugin.commands.doctor` | #21 |
| SDK profiles, prefix detection and profile choice (sections 6, 9), `--version`'s `sdk_profiles` | `mmt_plugin.sdk`, `mmt_plugin/sdk/profiles/<version>.json`, `mmt_plugin/schemas/sdk/v1/profile.json` | #13 |

Details fixed by #43 where section 6 or 7 leaves a choice:

- The envelope is ASCII-only JSON (non-ASCII text as `\uXXXX` escapes), two-space indented, so its bytes do not depend on the stream encoding.
- `command` is `null` when no command was dispatched (`--version`, or a usage error); `context.project` is `null` on usage errors.
- `--version --json` returns `result.sdk_profiles`, the bundled SDK profiles, oldest first: `["1.10.2"]` since #13.
- The interrupt code is `interrupted` (its class name alone).
- Diagnostics without a location sort first.
- A closed stdout keeps the run's exit code (0 for `mmt-plugin --version | head -c0`).
- The schema is closed (`additionalProperties: false`) except `context` and `result`; a new key is added to the schema in the same change.

Details fixed by #22 where sections 4, 5, 6 or 10 leave a choice:

- Human output (`Outcome`): `records` print when stdout is plain, and by a command with no `view`; `view(style)` renders the styled output with `mmt_plugin.ui.style` and is called only when stdout is styled; `text` prints as is in every mode (the completion script). A view that raises is `internal.unexpected` (exit 1). A new command adds only its view: the CLI makes the stream decisions and picks the mode. A view combines pieces with `style.join` (styled parts kept, text escaped), never `+` or an f-string.
- The stream decision also carries `width` (`COLUMNS` when a positive number, else the terminal's width, else 80) and `tty`. Boxes take the full width, at least 8 cells.
- User text is escaped with `ui.render.escape` in styled output too, backslashes included (`\\`), so a value reads the same in both modes.
- Statuses: `pass`/ok `●` (low), `warn` `▲` (mid), `fail` `✗` (high), and `skip` `○` in the dim role (ASCII `+ ! x -`). Footer items are joined by ` · ` (ASCII `, `). The meter prints its value right after the cells, three digits wide (`■■■■■····· 50%`, `■■■■■■■■■■100%`). A sparkline prints `min N  max N  last N`.
- Styled stderr: `<location or mmt-plugin>: ✗ error: <message> [<code>]` (the symbol and word high and bold, the code dim), `▲ warning:` (mid), `note:` (dim), and a dim `hint:` line. A plain stderr keeps the compiler-style lines byte for byte. A usage error is styled from `--no-color`, `NO_COLOR` and the stream, decided before parsing.
- Progress is `Context.progress(label, total=None)`: drawn after 2 s, only on a styled TTY stderr, never with `--json` or `-q`, and erased with spaces (no escape code) before the result.
- Exit codes: each command declares `exit_codes`, the codes it returns besides 0, 1, 2 and 130; its `--help` ends with an `exit codes:` list of exactly those, in the root `--help` format.
- `result` schemas are closed (`additionalProperties: false`), like the envelope. A command's is `schemas/cli/v1/<command>.json`; `--version --json` has `version.json`, so no command may be named `version` or `envelope`.
- `completion SHELL`: static scripts. Loading one only defines its functions and registers them (zsh: as an autoloaded `_mmt-plugin` from `fpath`, or `compdef` when sourced after `compinit`), and completing never runs `mmt-plugin`. Values complete from the parser: `choices`; directories for a `DIR`/`PREFIX` metavar and `--project`; files for `FILE`, `PATH`, `MODEL`, `PDL`, `PCAP`, `PACKETS`, `OUTPUT`; nothing otherwise. Options with `help=SUPPRESS` are left out. bash and zsh also complete a long option's value after `=` (`--project=DIR`). Command names, flags and choices are limited to letters, digits, `_`, `.`, `+` and `-` (the shells expand completion words, so a metacharacter could run code when completed); `completion` fails with `internal.unexpected` on any other. With `--json`: `result.shell` and `result.script`.

Details fixed by #14 where sections 4, 6 and 8 leave a choice:

- `generate` reads a PDL v1 `MODEL` (or `-`); `plugin.yaml` (the default `MODEL`, a `.yaml`/`.yml` file, or `--model-format yaml`) is `model.unsupported-format` (exit 3) until #24. With a pinned profile (`--sdk-profile` or `MMT_PLUGIN_SDK_PROFILE`) and no `--sdk`, no SDK is looked for; `context.sdk.prefix` is then `null`.
- The generated files are `<output>/<label>_mmt_plugin.h` and `.c`. `result` also carries `model` (the path, or `<stdin>`), `format` and `output`; `lock` is `{path, action, sha256}` like a file. Actions are `created`, `updated`, `unchanged`, `removed`, or `would-create`, `would-update`, `would-remove` when nothing is written (`--check`, `--dry-run`, or a refused run).
- A file in the way that `plugin.lock` does not list, or whose sha256 is neither the new one nor the lock's, is hand-edited: the run writes nothing and exits 7 (`state.modified`, one diagnostic per file) unless `--force`. `--check` reports such a file as `state.modified`, any other drift as `state.stale`. An unreadable `plugin.lock`, or one with a newer `lock_version`, is `state.invalid-lock` (exit 7); `--force` ignores it.
- A file the lock lists that is no longer generated is removed only when it is unmodified, a regular file, inside the output directory and not under `src/`; otherwise it is kept with the warning `state.kept`. `--output` under `<project>/src/` (also through a symbolic link) is `usage.invalid-value` (exit 2).
- `--strict` fails before anything is written, with the code (and so the class) of the first warning: `sdk.profile-default` is exit 4, `model.*` warnings exit 3.

Details fixed by #17 where sections 4, 5, 6 and 10 leave a choice:

- `validate` reads a PDL v1 `MODEL` (or `-`), like `generate`; `plugin.yaml` is `model.unsupported-format` (exit 3) until #24. Both read it through `mmt_plugin.commands.modelio`. Nothing is written.
- Every run reports the eight checks, in the order of section 4. When the model does not parse, the other seven are `skip`. Otherwise all of them run, and the exit code is the class of the first failing one (`schema`, `semantics`: the first error's code; `sdk-profile`: the SDK or profile error; `id-free`/`name-free`: `model.id-taken`/`model.name-taken`; `parents-exist`: `model.unknown-parent`; `load-order`: `model.load-order`). `error.message` counts the error diagnostics and names the failing checks; an SDK or profile error is reported as it is.
- `semantics` runs the semantic passes with the SDK conflicts allowed, and those conflicts are reported by `id-free` and `name-free`. The id and the name are checked against the profile (the SDK headers, `model.id-taken`/`model.name-taken` from `mmt_plugin.semantics`) and then against the run-time registry (`mmt_plugin.sdk.registry`): a child `python -I` process loads the SDK's `libmmt_core` with ctypes, calls `init_extraction()` with `MMT_DPI_PLUGINS_DIR` set to a temporary directory that links every `*.so` of the plugin directory (`$MMT_DPI_PLUGINS_DIR`, else `<prefix>/plugins`) except `mmtp_<label>.so`, so an installed copy of the plugin does not take its own id and name, and lists every registered id and name. Names are compared case-insensitively. A registry that cannot be read (no `libmmt_core`, `init_extraction()` fails, a crash, 60 s) is the warning `sdk.registry-unavailable`, and the two checks are `warn`.
- The reserved-range warning keeps its semantic code `model.id-outside-reserved-range`: `model.id-out-of-range` already means an id that is not positive and below `PROTO_MAX_IDENTIFIER` (an error), and a code is never reused for another meaning (D8). `--strict` makes it exit 3.
- With `--no-sdk` (exclusive with `--sdk`, `usage.conflicting-options`), no SDK is looked for: `id-free` and `name-free` are `skip` when the profile shows no conflict and `fail` when it does, and `parents-exist` is `skip`. Without `--no-sdk`, a missing or invalid SDK fails `sdk-profile` (exit 4) and the checks that need it are `skip`; the model is still checked against the pinned or newest profile, without the `sdk.profile-default` warning.
- `parents-exist` is `skip` for a PDL v1 model, which declares no parent; the check (`parents_check`) is ready for the explicit parents of `plugin.yaml` (#24): a parent exists when the profile names it or an installed plugin registers its name.
- `load-order` compares `mmtp_<label>.so` (lower case) with `libmmt_tcpip.so` byte by byte (the C locale) and, when the environment's `LC_COLLATE` is another available locale, with `strxfrm` in it; the process's locale is restored.
- `result.protocol` is `null` when the model does not parse; `name` is the label in upper case, the name the generated plugin registers. The styled footer counts checks, passes, warnings, failures and skips (`8 checks · 7 pass · 1 warning`).

Details fixed by #18 where sections 4, 5 and D6 leave a choice:

- Every hook the user defines is declared in the generated header `<label>_mmt_plugin.h`, and every plugin has one more, `int <label>_hook_register_parents(protocol_t *protocol_struct)` (types from the SDK profile): `init_<label>_proto_struct()` calls it once the protocol is registered, and a 0 fails the load. PDL v1 names no parent, so this is where user code attaches the protocol to its parents until `plugin.yaml` (#24) declares them.
- `mmt_plugin.codegen.scaffold(generation, profile)` renders `src/<label>_impl.c` in memory: a stub of every hook, which compiles with `-Wall -Wextra -Werror` and loads (an extraction hook extracts nothing; `register_parents` returns 1), and in `register_parents` a commented example that attaches the protocol to Ethernet with `register_classification_function_with_parent_protocol`. `init` (#23) writes it; nothing else does. `generate` never writes under `src/`, so regeneration leaves an edited scaffold as it is, and a model change that adds a hook leaves it without that hook.
- Load order: mmt-dpi loads the plugins of a directory in file name order, so a plugin whose parent is a `libmmt_tcpip` protocol must sort after `libmmt_tcpip.so` (`mmtp_<label>.so` does, as in `ndn_src/`), or the parent registration fails and the plugin does not load (`validate`'s `load-order` check). Weight: a parent runs its classification functions in increasing weight, and mmt-dpi documents 0 to 9 and 90 to 100; with mmt-dpi 1.10.2, weight 50 lost to the built-in Ethernet classifier (#55) while 1 and 5 worked, so the example uses 5.
- `mmt_plugin.codegen.hooks.missing_hooks(hooks, objects)` reads the global function symbols of the compiled user objects (ELF, with the standard library) and returns the hooks none defines; `missing_hook_error` makes them `build.missing-hook` (exit 5): one error diagnostic per hook at `src/<label>_impl.c`, whose hint gives the hook's declaration. `build` (#19) runs it after compiling and before linking.

Details fixed by #19 where sections 4, 5, 6, 7 and 8 leave a choice:

- `build` takes `MODEL` and `--model-format` like `generate` (so a PDL v1 model builds before `plugin.yaml`, #24), but not `-`: it compares the generated files with the model. It needs an SDK (`--sdk`, `MMT_BASE`, `mmt-dpi.pc`, `/opt/mmt`; none is `sdk.not-found`, exit 4), its `libmmt_core` (`sdk.invalid-prefix` without one) and the compiler `--cc` > `CC` > `gcc`, one program name or path with no arguments (so not `CC="ccache gcc"`; `sdk.cc-not-found`, exit 4, when it is not found or its `--version` fails; an empty `--cc` is `usage.invalid-value`).
- The sources are the generated `.c` (`<project>/generated/`) and every `<project>/src/*.c`, compiled one by one into `<build-dir>/obj/{generated,src}/<name>.o` with `-std=<profile c_std> -O2 -fPIC -fstack-protector-strong -U_FORTIFY_SOURCE -D_FORTIFY_SOURCE=2 -Wall -Wextra -Werror` and `-I` the generated directory, `src/` and the SDK's `dpi/include`, then linked with `-shared -Wl,-z,relro -Wl,-z,now -Wl,-z,defs` and `libmmt_core`, so every symbol resolves at link time: user code can call `libmmt_core` functions, not those only `libmmt_tcpip.so` exports. `-U_FORTIFY_SOURCE` drops a distribution's own level first (redefining it is an error with `-Werror`). `result.cflags` is the compile list, `result.ldflags` the link list.
- `result.stages` always lists `generate`, `compile`, `hooks` and `link`, each `ran`, `up-to-date`, `would-run` (`--dry-run`), `failed`, `stale` (`generate` with `--no-deps`) or `skipped` (not reached). `generate` runs `generate --check` and, when it reports `state.stale`, `generate` itself, writing the default `generated/` and `plugin.lock`; a hand-edited generated file is `state.modified` (exit 7) as for `generate`. `hooks` is `mmt_plugin.codegen.hooks` on the `src/` objects: `build.missing-hook` (exit 5), whose message says so when there is no `src/*.c` at all.
- Compiler and linker output is captured (`LC_ALL=C`): each `file:line[:column]: severity: message` line is a `build.cc` diagnostic, its file relative to the project; in a failing run a line with no location that names an error (`undefined reference`) is one without a location, so a failure always has one. A location-less `warning:` line (`ld: warning: ...`) is a warning even when the run succeeds. A failure is `build.compile-failed` or `build.link-failed` (exit 5). `--strict` applies to the warnings known before compiling (the profile's and the model's); with `-Werror` a compiler warning already fails the build. `-v` logs each command line and echoes the raw output.
- The link writes `<build-dir>/.mmtp_<label>.so.tmp`, renamed over `mmtp_<label>.so` only when it succeeds, and removed on any failure or SIGINT. The compiler runs in its own process group; SIGINT kills the group and exits 130.
- The input hash covers the tool version, the compiler's path and `--version` line, both flag lists and the command lines, the compiler's environment variables `CPATH`, `C_INCLUDE_PATH`, `GCC_EXEC_PREFIX`, `COMPILER_PATH`, `LIBRARY_PATH` and `SOURCE_DATE_EPOCH`, the profile, the SDK prefix, version, headers and `libmmt_core` (sha256), and the sha256 of every generated file and `src/*.c`/`src/*.h`. Each compile also writes a dependency file (`-MD -MF <obj>.d`, outside `result.cflags`): every file the compiler read, user headers in any directory and system headers included. After a link the hash, the plugin's sha256 and each such file's sha256 are written to `<build-dir>/.mmtp_<label>.build.json`; a build whose hash, plugin and dependencies all match it is a no-op (as with make, a new header that would shadow one the last build found elsewhere is not seen; `--rebuild` covers it) (`up_to_date`, every stage `up-to-date`, `commands` empty) unless `--rebuild`. `--dry-run` writes nothing and reports in `result.commands` (and as `command⇥…` records) the command lines it would run; their object and temporary paths are fixed, so a dry run prints the same bytes twice.
- `result.artifact` is the plugin this run built or found up to date, else `null`: a failed build keeps the previous `mmtp_<label>.so` but reports `null`. The styled view is the box `build <label>`: the stages, then the artifact, its sha256 and size, the compiler, the flags and, with `--dry-run`, the commands; the footer says `built`, `up to date`, `dry run · N commands` or which stage failed.

Details fixed by #21 where sections 4, 5, 6, 8, 9 and D11 leave a choice:

- Which plugin directories mmt-dpi 1.10.2 scans (D11). `load_plugins()` in `src/mmt_core/src/plugins_engine.c` reads one directory, `plugins_directory()`: `MMT_DPI_PLUGINS_DIR` (read with `secure_getenv`) when set and not empty, which must be absolute (a relative one loads nothing and fails `init_extraction()`), else `PLUGINS_REPOSITORY_OPT`, which `rules/common.mk` sets to `$(MMT_PLUGINS)`, `$(MMT_BASE)/plugins`, when the library is built (`private_include/plugins_engine.h` defaults it to `/opt/mmt/plugins`). The working directory is never scanned. So the published package scans `/opt/mmt/plugins` even when it is extracted into another prefix, and nothing scans `~/.local/share/mmt/plugins` by itself. An unmodified 1.10.2 `libmmt_core` does load a plugin installed under the default prefix once `MMT_DPI_PLUGINS_DIR=<prefix>/plugins` (`tests/unit/install/test_sdk.py`), so the default is kept. Because the variable replaces the compiled-in directory, the SDK's own plugins (`libmmt_tcpip.so`, ...) must be linked into `<prefix>/plugins` too for a plugin whose parents they register; `doctor` says so.
- `doctor` reads the compiled-in directory from `libmmt_core` itself: the one NUL-terminated absolute path ending in `/plugins` in the library (`mmt_plugin.sdk.registry.compiled_plugin_dir`; none or several is the warning `sdk.plugin-dir-unknown`). Its checks, in order and in four sections: `python`, `compiler`; `sdk`, `sdk-profile`; `plugin-dir` (the scanned directory: `fail` with `sdk.invalid-plugin-dir` for a relative or unreadable `MMT_DPI_PLUGINS_DIR`, `warn` with `sdk.no-tcpip-plugin` when it has no `libmmt_tcpip.so`), `install-dir` (`<prefix>/plugins`; `warn` with `sdk.install-dir-not-scanned` and the `export MMT_DPI_PLUGINS_DIR=...` and `ln -s` lines as hint when mmt-dpi does not scan it); `load-order` (every non-SDK `*.so` of the scanned and the install directory after `libmmt_tcpip.so`, else `sdk.plugin-load-order`), `registry` (`init_extraction()` with the scanned directory, `mmt_plugin.sdk.registry`; `warn` `sdk.registry-unavailable` when it cannot be read), `project` (`--model`, else `<project>/plugin.yaml` when it exists; a model that cannot be read is `warn`, not checked) and `clashes` (the install manifests of both directories and the project's model, by id and by name case-insensitively, `sdk.plugin-clash`; the project's own installed copy, same label, is not a clash). Exit 4 with the first failing check's code. `result.plugin_dirs` is `{scanned: {path, source} | null, install: {path, source, plugins, scanned, writable}}`, `result.load_order` each directory's `*.so` files in load order, `result.clashes` `[{kind, value, plugins}]`. Nothing is written.
- `install` takes `MODEL`, `--model-format`, `--sdk`, `--sdk-profile`, `--cc` and `--build-dir` as `build`, which it runs (`result.build`: `ran`, `up-to-date`, `would-run` with `--dry-run`, `stale` with `--no-deps`, exit 7, or `failed`). The prefix (`context.prefix: {path, source}`) is checked first: `<prefix>/plugins`, or its nearest existing parent, must be a directory this user can write, else `sdk.prefix-not-writable` (exit 4, `--dry-run` too). Then `mmtp_<label>.so` must sort after `libmmt_tcpip.so` (`model.load-order`, exit 3) and its id and name must not be those of another manifest of `<prefix>/plugins` (`model.id-taken`, `model.name-taken`, exit 3, even with `--force`). The plugin is written with mode 0755, then the manifest. A target with the plugin's sha256, or the one its manifest records, is replaced or kept as is; any other is `state.exists` (no manifest lists it) or `state.installed-modified` (exit 7) unless `--force`; a target that is a directory is `state.exists` even with `--force`. An own manifest that cannot be read is `state.invalid-manifest` (exit 7), rewritten with `--force`. A dry run whose plugin is not built yet reports `sha256: null`.
- The manifest is `manifest_version` 1: `tool {name, version}`, `label`, `protocol {id, name}` and `files [{path, sha256}]`, each `path` a bare file name in `<prefix>/plugins`; a manifest with any other path is `state.invalid-manifest`, so `uninstall` never removes anything outside that directory.
- `uninstall [LABEL]`: `LABEL` must match `[a-z][a-z0-9_]*` (`usage.invalid-value`); without it, the label is the one of the header `<label>_mmt_plugin.h` that `<project>/plugin.lock` (else `<project>/generated/plugin.lock`) lists, else `usage.missing-argument`. A file whose sha256 is the manifest's is removed (`--force`: any regular file or symbolic link), one already gone is `missing`, any other is `kept` with `state.installed-modified` (exit 7) and stays in the rewritten manifest; with nothing kept, the manifest goes, and `.mmt-plugin/` when it is empty. The prefix's writability is checked only when there is a manifest, so uninstalling what is not installed (`state.not-installed`) is exit 0 anywhere.
