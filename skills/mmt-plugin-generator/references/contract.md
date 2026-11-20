# The CLI contract this skill relies on

The reference is [`docs/design/cli.md`](../../../docs/design/cli.md),
sections 5 to 8, and the code in `src/mmt_plugin/exitcodes.py` and
`src/mmt_plugin/diagnostics.py`. This page lists what the skill reads and
what it does with it. `tests/unit/skill/test_evals.py` checks that the two
tables below match the code: every exit code, and every registered
diagnostic code, has a row.

## The envelope

With `--json`, every command prints exactly one JSON document on stdout,
also on a usage error, and nothing else. The skill reads these keys:

| Key | What it is | How the skill uses it |
|---|---|---|
| `schema_version` | `1` | Anything else is a CLI this skill does not know: stop. |
| `command` | the command that ran, or `null` on a usage error the argument parser caught | Check that it is the command you ran; `null` only with exit 2. |
| `ok` | `exit_code == 0` | |
| `exit_code` | the process exit code | Its class decides what to fix (table below). |
| `error` | `null` when `ok`; else `class`, `code`, `message`, `hint` | `error.code` picks the fix (table below); `hint` often names it. |
| `diagnostics[]` | every error, warning and note, sorted by file, line, column | Fix each `severity: "error"` entry. Read the warnings. |
| `diagnostics[].code` | a stable dotted code whose first part is the class | Decide from it, never from `message`. |
| `diagnostics[].location` | `{file, line, column, end_line, end_column}` or `null` | `file` is relative to the project inside it, absolute outside it (a `build.cc` error or note in an SDK header); `line` and `column` are 1-based and may be `null` (a whole file). Edit there, unless `file` is outside the project. |
| `diagnostics[].hint` | one line on how to fix it, or `null` | |
| `diagnostics[].related[]` | other places (`"first defined here"`) | |
| `result` | the command's own result, `null` on a usage error | `test`: `summary`, `packets[].failures[]` (`attribute`, `expected`, `actual`; a session test's also `packet`) and `plugins[]` (the plugins `plugins:` names, in load order: `path`, `project`, `build`). `run`: `summary`, `paths[]` (`path`, `packets`) and `protocols[].attributes[]` (`name`, `packets`). |

Keys not listed here may be added; ignore them. Paths in the envelope are
relative to the project (`-C`) when inside it, absolute otherwise.

Rules the skill relies on:

- The exit code is the class of the first stage that failed; warnings never
  change it (unless `--strict`).
- No command prompts or reads the terminal. A choice the CLI cannot make is
  exit 2 or exit 7, with a hint that names the flag.
- Re-running a command on unchanged inputs changes nothing: running the
  loop again is always safe.

Where the fix goes: at the `location` of each error, the line when it has
one, else the file. Three cases name a file whose fix is often elsewhere:

- `test.packet-failed` is located at the packet test, without a line. Its
  fix is usually in `plugin.yaml`, at the attribute that
  `result.packets[].failures[].attribute` names (an offset, a type, a bit
  order). Change the test only when the spec contradicts its expected
  value, never to match what the plugin outputs, and never a test that was
  in the project before this session (stop and report instead). A failing
  entry with `through` ran through the plugin's parent: `<protocol>` there
  (not classified) or `<parent>` is fixed in `parents:` (its `classify`) or
  in `<label>_hook_register_parents`. When `through` is a plugin parent's
  label (a project under `plugins`), the frame is that project's packet
  test (the first with `through`, or `test=<id>`): its lower layers and
  its bytes, the parent's header; a `<parent>` offset is fixed in the hook's
  classifier, or with `test=` naming a parent test whose bytes are the
  header, never in the parent's tests. An entry with `session` is a session
  test: each failure's `packet` is the index of its step in the file's
  `packets`; a value that depends on earlier packets is fixed in the
  session hooks of `src/<label>_impl.c`.
- `build.missing-hook` is located at `src/<label>_impl.c`, without a line:
  add the function there, with the declaration of the hint.
- A `build.cc` error at an absolute path is in a file outside the project,
  an SDK header: never edit it. Its cause is in the file that includes it,
  `src/<label>_impl.c`, or in `plugin.yaml` when that is `generated/`.

## Exit codes

| Exit | Class | Action |
|---|---|---|
| 0 | success | Go on. Warnings in `diagnostics` are worth reading but do not block. |
| 1 | internal | Stop: a bug in mmt-plugin, or an I/O error. Report the envelope. |
| 2 | usage | Fix the command line (an unknown option, a missing argument, two options that conflict). Change no file. |
| 3 | model | Fix the model or a packet test at each error's `location`, then run the loop again. |
| 4 | sdk | Fix the environment: the SDK prefix (`--sdk`), the profile (`--sdk-profile`, `sdk.profile`) or the compiler (`--cc`). Never the model. |
| 5 | build | Fix `src/<label>_impl.c` (or the model, when the error is in generated code) at each error's `location`. |
| 6 | test | For each failing packet in `result.packets`, compare `attribute`, `expected` and `actual` with the spec, then fix whichever of the model and the test is wrong; never a test that was in the project before this session. |
| 7 | state | Files on disk are not what the command needs: see the code. Never `--force` over a file you did not write. |
| 130 | interrupted | Run the command again. |

## Error codes

A row is a code, or a family ending in `*`. Codes are the
`diagnostics[].code` and `error.code` values; the first part is the class.

| Code | Action |
|---|---|
| `internal.*` | Stop and report: not something to fix in the project. |
| `usage.*` | Fix the arguments: compare them with `mmt-plugin <command> --help`. |
| `interrupted` | Run the command again. |
| `sdk.not-found` | Pass `--sdk <prefix>`; no SDK was found. Without one, stop after `generate`. |
| `sdk.invalid-prefix` | The prefix has no `dpi/include/mmt_log.h`: pass the directory that does (the extracted package's `opt/mmt`). |
| `sdk.invalid-pkg-config` | Pass `--sdk <prefix>` so that `mmt-dpi.pc` is not read. |
| `sdk.profile-not-found` | Use a profile from `result.sdk_profiles` of `mmt-plugin --json --version`, in `sdk.profile` or `--sdk-profile`. |
| `sdk.profile-fallback` | Warning: no profile for the SDK's version; the nearest one is used. Pin one with `sdk.profile` if it matters. |
| `sdk.profile-default` | Warning: no SDK and no pinned profile. Pin `sdk.profile` in `plugin.yaml`. |
| `sdk.cc-not-found` | Pass `--cc gcc` or `--cc clang` (one program, no arguments). |
| `sdk.tshark-not-found` | `scaffold --tshark` needs tshark on `PATH`: ask the user to install it (Wireshark's command line), or drop `--tshark` for `scaffold`'s own proposal. Nothing was written. |
| `sdk.tshark-failed` | tshark failed or printed what does not parse: check each `--decode-as` rule against the message (a protocol tshark does not know), and that tshark reads the capture (`tshark -r`). Nothing was written. |
| `sdk.registry-unavailable` | Warning: the installed plugins could not be listed, so the id and name were checked against the SDK headers only. Go on. |
| `sdk.id-unchecked` | Warning from `init` without an SDK: `validate` with `--sdk` checks the id later. |
| `sdk.prefix-not-writable` | Pass `--prefix` with a directory you own. Never `sudo`. |
| `sdk.invalid-plugin-dir` | `MMT_DPI_PLUGINS_DIR` must be an absolute, readable directory: fix or unset it. |
| `sdk.plugin-dir-unknown` | Warning from `doctor`: go on. |
| `sdk.install-dir-not-scanned` | Warning: mmt-dpi does not load the install directory; the hint gives the `export MMT_DPI_PLUGINS_DIR=...` line. Tell the user. |
| `sdk.no-tcpip-plugin` | Warning: link the SDK's `libmmt_tcpip.so` into the scanned directory (the hint says how). |
| `sdk.plugin-load-order` | An installed plugin loads before `libmmt_tcpip.so`: tell the user; do not rename their files. |
| `sdk.plugin-clash` | Another installed plugin has this id or name: change `protocol.id` or `protocol.label`. |
| `model.syntax.*` | An expression (or a PDL v1 file) does not parse: fix it at the location. Expressions are PDL v1's (`docs/plugin-yaml.md`, Expressions). |
| `model.yaml-syntax` | The text is outside the YAML subset (`docs/plugin-yaml.md`): no anchors, block scalars or multi-line flow lists; quote `yes`, `off`, `010`. |
| `model.schema` | `plugin.yaml` breaks its schema at the location: the hint lists what is allowed (an enum's values, the keys of a mapping). |
| `model.unreadable` | The model file is missing or not UTF-8: check the path. |
| `model.duplicate-name` | Rename one of the two (names are case-insensitive); `related` points at the first. |
| `model.unknown-name` | A case value or define names nothing: define it, or use a number. |
| `model.unknown-attribute` | `val()`, `offset()` or `len()` names no attribute: fix the name. |
| `model.unknown-struct` | `struct X` names no earlier struct: define it first. |
| `model.use-before-definition` | Move the definition before its use. |
| `model.conditional-reference` | A conditional attribute is used outside its branch: move the use into the branch. |
| `model.not-an-integer` | `val()` of a non-integer attribute: read an integer field instead. |
| `model.hook-reference` | `offset()` or `len()` of an attribute without an offset: give it an offset, or do not refer to it. |
| `model.hook-value` | `val()` of an attribute without an offset: give it an offset. |
| `model.missing-length` | Give the attribute a `length`: its type has no fixed width. |
| `model.no-fixed-width` | A struct field needs a fixed-width type: move it out of the struct as an attribute with a `length`. |
| `model.invalid-bitfield` | A bitfield's width must be 1 to its type's bits, of an integer type. |
| `model.bitfield-overflow` | The run of bitfields is wider than its type: widen the type or split the run. |
| `model.division-by-zero` | Fix the expression. |
| `model.out-of-range` | An offset or length is negative or too large: check it against the spec. |
| `model.duplicate-case` | Two `classify_next` cases have the same value: remove one. |
| `model.leading-zero` | Write the number without a leading zero (or in `0x` hex). |
| `model.alias-too-long` | Shorten the label or the attribute name (the hint gives the limit). |
| `model.id-out-of-range` | Use an id from 950 to 999. |
| `model.id-taken` | Use another id from 950 to 999. |
| `model.name-taken` | Use another label: an SDK protocol has this name. |
| `model.id-outside-reserved-range` | Warning: move the id into 950 to 999 if you can. |
| `model.default-scope` | Warning (PDL v1 only): give the attribute a `scope`. |
| `model.pointer-field` | Warning: a `T*` field is 4 bytes read as `MMT_DATA_POINTER`; check that the spec means a pointer. |
| `model.branch-offset-mismatch` | Warning (running offsets): give the attribute after the `if` an explicit offset. |
| `model.define-sdk-name` | A define has the name of an SDK macro, constant or type (`PROTO_IP`): rename it; to use the SDK's protocol id, name the SDK macro directly. |
| `model.data-len-width` | Warning: the `length` is not the fixed-width type's width (the message names both): use the type's width, or keep it only when the spec's field is narrower than its type (a 24-bit integer in `MMT_U32_DATA`). |
| `model.name-collision` | Two names become the same C identifier: rename one (the hint names both). |
| `model.integer-length` | An integer's `length` must be 1 to 8 bytes and fit its type: fix the type or the length. |
| `model.variable-length` | A per-packet length needs a byte type: use `MMT_BINARY_DATA`, `MMT_BINARY_VAR_DATA` or `MMT_STRING_DATA`. |
| `model.type-size` | The SDK registers this type only with length 0, or the length is too long: use another type. |
| `model.default-byte-order` | Warning: set `protocol.encoding` (`network` for big-endian). |
| `model.classifynext-without-encapsulation` | Warning: set `protocol.encapsulation: true` when `classify_next` is meant. |
| `model.classify-port` | `port`, `sport` and `dport` classify only under `protocol: tcp`: under another parent, give `match` and `offset` from the start of the parent. |
| `model.unknown-parent` | Name a parent the SDK profile or an installed plugin has (`ethernet`, `ip`, `udp`, `tcp`, ...), or another plugin's label with its project under `plugins:` in `plugin.yaml`. |
| `model.load-order` | The label must make `mmtp_<label>.so` sort after `libmmt_tcpip.so` and after the plugin file of every plugin `plugins:` names (the message names it): choose another label. |
| `model.no-parent` | Warning from `init`: add a parent to `plugin.yaml`. |
| `model.legacy-*` | Warnings from `import`: the converted model does what the spec says, not what the Java tool did. Check the attribute against the spec. |
| `model.bad-packet-test` | The packet test file is not corpus schema 1 (`tests/corpus/README.md`, Packet files): fix it at the location. |
| `model.bad-plugin` | An entry of `plugins:` in `plugin.yaml` that `test` or `validate` cannot use, at the entry: fix the path (relative to the directory of `plugin.yaml`, to a project directory with its `plugin.yaml` or to a built `.so` file), name each plugin once, never this plugin itself or a project that names this one. |
| `model.bad-pcap` | The capture cannot be read (`scaffold`, `run`): ask for another one. From `run`, a capture broken after its header still reports the counts of the frames before the break. |
| `model.unsupported-linktype` | `run`: mmt-dpi reads only Ethernet and Linux cooked captures: convert the capture (`editcap -T ether`) or get another one; never change the model for it. |
| `model.no-payloads` | Nothing in the capture is under `--parent`: check the selector (port, direction, EtherType). |
| `model.no-dissector` | `scaffold --tshark`: tshark has no dissector for the payloads (only `data`), or not the `--protocol` asked for; the message lists what it dissects there. Pass `--decode-as <layer>==<value>,<protocol>` for a protocol on a port tshark does not know, choose a listed `--protocol`, or drop `--tshark`. |
| `model.no-fields` | `scaffold --tshark`: none of the protocol's fields maps to an attribute in every payload. Drop `--tshark` and draft from the spec, or use `scaffold`'s own proposal. |
| `build.cc` | One compiler message: fix the source at its location. |
| `build.compile-failed` | Fix the `build.cc` errors in `src/<label>_impl.c`; an error in `generated/` comes from the model. A failure with no located `build.cc` error (a fatal compiler error, an object that is not ELF) is the toolchain or the SDK: check `--cc` and `--sdk`. |
| `build.link-failed` | An undefined symbol: user code may call `libmmt_core` functions only. |
| `build.missing-hook` | Add the hook to `src/<label>_impl.c` with the declaration the hint gives, returning 0. |
| `build.harness-failed` | The test harness does not compile against the SDK: check the SDK prefix and the compiler, then report. |
| `build.runner-failed` | `run`: the capture runner does not compile against the SDK: check the SDK prefix and the compiler, then report. |
| `test.packet-failed` | Compare each failure's `attribute`, `expected` and `actual` with the spec: fix the model (an offset, a type, a bit order) or the test (a wrong expected value). A test that was in the project before this session is never edited: fix the model, or stop and report when the spec contradicts the test. |
| `test.crash` | The plugin crashed on a packet: check the lengths and conditions of variable-length attributes, and the user code. From `run`, the message names the frame: write its protocol bytes as a packet test and run `test --sanitize` on it. |
| `test.load-failed` | The plugin does not load: check the hooks in `src/<label>_impl.c` (`register_parents` must return 1). When the hook attaches the protocol under another plugin's, name that plugin's project (or `.so`) under `plugins:` in `plugin.yaml`, parents first (`docs/plugin-yaml.md`, Plugins). From `run`, also each `--plugin` (a parent plugin it needs must be passed). |
| `test.no-match` | Warning from `run`: no packet of the capture has the protocol. Compare `result.paths` with the parent in `parents:` (its `classify`) or `<label>_hook_register_parents`; check that the capture carries the protocol. |
| `test.other-linktype` | Warning from `run`: frames of another link type were not processed. Go on, or split the capture by interface. |
| `test.unknown-protocol` | Warning from `run`: a `--protocol` no loaded plugin registers. Fix the name or pass its plugin with `--plugin`. |
| `test.no-packets` | Warning: write packet tests in `tests/*.yaml`; a run without one is not green. |
| `test.bench-failed` | Warning from `--bench`: go on. |
| `state.stale` | Run the command without `--no-deps` (or `generate`) to bring the files up to date. |
| `state.modified` | A file in `generated/` was edited by hand: edit the model instead; `--force` only if you made that edit. A directory where a generated file goes: ask the user (`--force` does not replace it). |
| `state.invalid-lock` | `plugin.lock` cannot be read: if you did not write it, ask; else `generate --force`. A directory named `plugin.lock`: ask the user (`--force` does not replace it). |
| `state.kept` | Warning: a file `generate` no longer writes was kept. Delete it if it is yours. |
| `state.exists` | A file no install manifest lists is at the target: ask the user. |
| `state.installed-modified` | An installed file was changed since install: ask the user. |
| `state.invalid-manifest` | An install manifest cannot be read: ask the user. |
| `state.not-installed` | Warning from `uninstall`: nothing was installed. |
| `state.file-differs` | `init`: a project file has other content. Do not `--force` over the user's files; pick another `--dir`. At a `model.pdl` (a project of an older `init`): the hint's `import` converts it; ask the user before you run it. |
| `state.not-a-project` | `init --dir` is not empty and not a project: pick an empty directory. |
| `state.output-differs` | `import` or `scaffold` would replace a file with other content: `--force` only if you wrote it. |
