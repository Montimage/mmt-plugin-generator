---
name: mmt-plugin-author
description: "Write an mmt-dpi protocol plugin with mmt-plugin from a protocol spec, a pcap capture or a legacy PDL v1 model: draft plugin.yaml and packet tests, then run validate, generate, build and test with --json until they pass. Don't use for installing plugins system-wide, changing mmt-dpi itself, or editing the generator."
metadata:
  version: 0.1.0
  plan_task: T4.2
---

# mmt-plugin-author

You write a third-party mmt-dpi protocol plugin with the `mmt-plugin` CLI.
You get a protocol specification, a capture of the protocol's traffic, or a
legacy PDL v1 model. You produce a project whose `plugin.yaml` describes the
protocol and whose packet tests pass. The work runs as a loop, and you decide
each step from the CLI's `--json` envelope, never from its human output.

The CLI contract is [`docs/design/cli.md`](../../docs/design/cli.md) in this
repository: the envelope (section 6), the exit codes (section 5) and the I/O
rules (section 7). [`references/contract.md`](references/contract.md) lists
the parts this skill relies on and what to do for each exit class and each
error code. [`references/drafting.md`](references/drafting.md) explains how
to turn a spec, a capture or a PDL model into `plugin.yaml` and packet tests.

## What you need

- `mmt-plugin` on `PATH`. In a checkout of this repository, use
  `uv run mmt-plugin`.
- An mmt-dpi SDK prefix: a directory that holds `dpi/include/mmt_log.h`,
  `dpi/lib/libmmt_core.so` and `plugins/libmmt_tcpip.so`. Use a private
  prefix, for example the published package extracted with `dpkg-deb -x`
  (`AGENTS.md`, "A private prefix can also come from the published
  package").
- A C compiler, `gcc` or `clang`.
- The SDK profile: the newest entry of `result.sdk_profiles` in
  `mmt-plugin --json --version`, or the version of the SDK you build
  against.

Without an SDK you can still run `validate` and `generate`. `build` and
`test` need one. If you have no SDK, stop after `generate` and say in your
report that the plugin was not built or tested.

## Rules

1. Pass `--json` to every command, and read only stdout's single envelope.
   With `--json`, stderr is empty unless you pass `-v`.
2. Never give `-` (stdin) as an argument. No command prompts or reads the
   terminal, so never wait for input. A command that seems to wait is a bug:
   stop and report it.
3. Never use `sudo`, `--system` or a path under `/opt/mmt`. Install into a
   private prefix, and only when the user asks.
4. Use `--force` only to overwrite a file you wrote in this session. A file
   you did not write and that exit 7 refuses to replace belongs to the
   user: ask them.
5. Run the loop in its order and stop at the first command that does not
   exit 0. Fix that failure, then start the loop again from `validate`.
6. Decide from the envelope, in this order: `exit_code` (its class),
   `error.code`, then each error in `diagnostics` with its `location`.
   Never decide from `error.message` or `diagnostics[].message`: their
   wording can change, the codes cannot.
7. Never edit `generated/` or `plugin.lock`. `generate` writes them. Your
   code goes in `src/<label>_impl.c`.
8. Change one thing per loop run when you can, so the next envelope shows
   whether the change worked.
9. Never delete a packet test you wrote from the spec or that `scaffold`
   wrote, and never change its expected values to what the plugin outputs.
   It may follow a rename, or lose an attribute you also remove from
   `plugin.yaml`. Only `init`'s placeholder `tests/<label>-basic.yaml` may
   go.
10. Stop after 10 loop runs that are not green, or when the same `error.code`
   comes back at the same location twice after you changed it. Report what
   you tried and the last envelope.

## Step 1: create the project

Pick a label (`[a-z][a-z0-9_]*`, a name no SDK protocol has) and an id from
950 to 999. `validate` checks both. `<project>` is the project directory,
`<selector>` the parent, for example `udp:dport=4433`, `tcp:port=102` or
`ethernet:ethertype=0x88b5`.

From a protocol specification, create the project and turn its sample model
into `plugin.yaml`:

<!-- eval:entry spec -->
```sh
mmt-plugin --json init <label> --dir <project> --id <id> --parent <selector> --sdk-profile <profile>
mmt-plugin -C <project> --json import <project>/model.pdl -o <project>/plugin.yaml
```

From a capture, create the project, then let `scaffold` slice the payloads
under the parent into packet tests and propose a field skeleton,
`<project>/plugin.proposed.yaml`:

<!-- eval:entry pcap -->
```sh
mmt-plugin --json init <label> --dir <project> --id <id> --parent <selector> --sdk-profile <profile>
mmt-plugin -C <project> --json scaffold --from-pcap <pcap> --parent <selector> --model <project>/model.pdl
```

From a legacy PDL v1 model, create the project, then convert the model:

<!-- eval:entry pdl -->
```sh
mmt-plugin --json init <label> --dir <project> --id <id> --parent <selector> --sdk-profile <profile>
mmt-plugin -C <project> --json import <pdl> -o <project>/plugin.yaml
```

`init` writes `model.pdl` (a sample 4-byte header), `src/<label>_impl.c`
(your code: one function per hook), `tests/<label>-basic.yaml` (a packet
test of the sample header) and `.gitignore`. Once `plugin.yaml` exists,
delete `model.pdl`, so that the project has one model. `import` warns with
`model.legacy-*` codes about constructs that relied on bugs of the old Java
tool. Read each warning: it says what changed.

Two things `init` does not carry over:

- `--parent` is only a comment in `model.pdl`, and `import` drops it. Write
  the parent into `plugin.yaml` yourself (`parents:`), or `validate`
  reports `parents-exist` as `skip` and the plugin is never handed a
  packet.
- Nothing pins the profile. Add `sdk: {profile: "<profile>"}` to
  `plugin.yaml` after `import` or after copying the proposal.

Keep the label and the id you gave `init` in `plugin.yaml`:
`src/<label>_impl.c` includes `<label>_mmt_plugin.h`, which `generate`
names after the label.

## Step 2: draft plugin.yaml and the packet tests

Follow [`references/drafting.md`](references/drafting.md):

- Write each field of the spec as an attribute or a struct field, at the
  offset and with the type the spec gives. Pin the profile with
  `sdk: {profile: "<profile>"}`. Declare the parent with `classify` when
  one match of the parent's header identifies the protocol.
- From a capture, start from `plugin.proposed.yaml`: rename its fields
  after the spec, delete those that are payload, copy it over
  `plugin.yaml`, and make the same changes in the packet tests `scaffold`
  wrote.
- Write a packet test for each example of the spec, with the values the
  spec gives, never the values the plugin outputs. Delete
  `tests/<label>-basic.yaml` once it no longer describes the protocol.

## Step 3: the loop

Run these four commands in order, with the SDK prefix and the compiler.
Stop at the first one that does not exit 0:

<!-- eval:loop sdk -->
```sh
mmt-plugin -C <project> --json validate --sdk <prefix>
mmt-plugin -C <project> --json generate --sdk <prefix>
mmt-plugin -C <project> --json build --sdk <prefix> --cc <cc>
mmt-plugin -C <project> --json test --sdk <prefix> --cc <cc>
```

Without an SDK, run the first two only, with the profile pinned:

<!-- eval:loop no-sdk -->
```sh
mmt-plugin -C <project> --json validate --no-sdk --sdk-profile <profile>
mmt-plugin -C <project> --json generate --sdk-profile <profile>
```

`build` generates and `test` builds when their input is stale, but run all
four: each one's envelope shows only its own stage.

## Step 4: read the envelope and fix

| Exit | Class | What to do |
|---|---|---|
| 0 | success | Go to the next command. Read the warnings in `diagnostics` anyway. |
| 1 | internal | A bug in mmt-plugin. Stop and report the envelope. |
| 2 | usage | Your command line is wrong. Fix the arguments; do not change files. |
| 3 | model | Fix `plugin.yaml` or a packet test at each error's `location`. |
| 4 | sdk | Fix the SDK prefix, the profile or the compiler; never the model. |
| 5 | build | Fix `src/<label>_impl.c` at each error's `location` (`build.missing-hook`: add the hook its hint declares). |
| 6 | test | For each failing packet, check the attribute, the expected and the actual value against the spec, then fix the model or the test, whichever is wrong. |
| 7 | state | A file on disk is not what the command needs. Read `error.code`: regenerate, or ask before `--force`. |
| 130 | interrupted | Run the command again. |

[`references/contract.md`](references/contract.md) has the action for every
`error.code`.

## Done

The plugin is green when, in one loop run, all four commands exit 0 and
`test`'s `result.summary` has `failed` 0 and `passed` equal to `total`, with
`total` at least 1 (a run with no packet test is the warning
`test.no-packets`, not green), and `validate`'s `parents-exist` check is
`pass`.

Report:

- the project directory, the label, the id and the parent;
- how many loop runs it took, and what each fix was (its `error.code` and
  `location`);
- the last `test` summary;
- what you could not check (no SDK, a field the spec leaves open).

## Evals

`evals/` holds scripted runs of this skill: each case in `evals/cases/` is a
starting point (a spec, a capture or a PDL model) and the drafts an agent
makes, one per loop run. `evals/run_evals.py` runs the entry and loop
commands of this file, as written above, on each case, and fails when an
envelope breaks [`references/contract.md`](references/contract.md), when a
loop run does not stop where the case expects, when a fix does not touch the
location the envelope gave, or when a command reads stdin (each command
gets an open pipe with no data and no terminal, and a time limit). With
`--sdk`, it runs all four loop commands; without, it stops after
`generate`.

```sh
uv run python skills/mmt-plugin-author/evals/run_evals.py
uv run python skills/mmt-plugin-author/evals/run_evals.py --sdk <prefix> --cc gcc
```

`tests/unit/skill/` runs them in CI: without an SDK in every Python job,
with one in the "Generated code" job.
