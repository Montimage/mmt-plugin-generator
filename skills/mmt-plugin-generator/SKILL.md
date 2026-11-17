---
name: mmt-plugin-generator
description: "Generate or update an mmt-dpi protocol plugin with mmt-plugin from a spec, pcap or PDL v1 model: get a capture, loop to green, evaluate on the capture, keep a work folder. Don't use for system-wide installs, mmt-dpi's built-in protocols, or editing the generator."
metadata:
  version: 0.2.0
  author: "Luong NGUYEN <luongnv89@users.noreply.github.com>"
  plan_task: T4.2
---

# mmt-plugin-generator

You write a third-party mmt-dpi protocol plugin with the `mmt-plugin` CLI.
You get a protocol specification, a capture of the protocol's traffic, or a
legacy PDL v1 model, or an existing plugin project and a change to make to
it. You produce a project whose `plugin.yaml` describes the protocol and
whose packet tests pass, evaluated on a capture of the protocol, and a work
folder that keeps everything that went into it. The work runs as a loop,
and you decide each step from the CLI's `--json` envelope, never from its
human output.

Out of scope: changing a protocol that mmt-dpi already ships (one of
`libmmt_tcpip.so`, such as `ip`, `udp` or `http`). A plugin adds a protocol
of its own, with its own label and id; it cannot change a built-in one, and
`validate` rejects a label or an id the SDK has. Say so and stop.
Installing plugins system-wide, changing mmt-dpi itself and editing the
generator are out of scope too.

The CLI contract is [`docs/design/cli.md`](../../docs/design/cli.md) in this
repository: the envelope (section 6), the exit codes (section 5) and the I/O
rules (section 7). [`references/contract.md`](references/contract.md) lists
the parts this skill relies on and what to do for each exit class and each
error code. [`references/drafting.md`](references/drafting.md) explains how
to turn a spec, a capture or a PDL model into `plugin.yaml` and packet tests.
[`references/workfolder.md`](references/workfolder.md),
[`references/capture.md`](references/capture.md) and
[`references/evaluation.md`](references/evaluation.md) cover the work
folder, getting a capture and evaluating on it.

## What you need

- `mmt-plugin` on `PATH`. In a checkout of this repository, use
  `uv run mmt-plugin`.
- An mmt-dpi SDK prefix: a directory that holds `dpi/include/mmt_log.h`,
  `dpi/lib/libmmt_core.so` and `plugins/libmmt_tcpip.so`. Use a private
  prefix, for example the published package extracted with `dpkg-deb -x`
  (`AGENTS.md`, "A private prefix can also come from the published
  package").
- A C compiler, `gcc` or `clang`, and the libpcap headers (`libpcap-dev`)
  for the capture evaluation.
- Python 3 for `scripts/`, and the Wireshark tools (`tshark`, `capinfos`,
  `editcap`, `mergecap`) to check and compare captures. tshark is the only
  reference tool for the drift check. Without tshark the evaluation still
  runs, with less, and the drift is not checked
  (`references/evaluation.md`).
- The SDK profile: the newest entry of `result.sdk_profiles` in
  `mmt-plugin --json --version`, or the version of the SDK you build
  against. In an existing project, `<profile>` is the one its `plugin.yaml`
  pins in `sdk.profile`.

Without an SDK you can still run `validate` and `generate`. `build`, `test`
and the capture evaluation need one. If you have no SDK, stop after
`generate` and say in your report that the plugin was not built, tested or
evaluated.

## Rules

1. Pass `--json` to every command, and read only stdout's single envelope.
   With `--json`, stderr is empty unless you pass `-v`.
2. Never give `-` (stdin) as an argument. No command prompts or reads the
   terminal, so never wait for input. A command that seems to wait is a bug:
   stop and report it.
3. Never use `sudo`, `--system` or a path under `/opt/mmt`. Install into a
   private prefix, and only when the user asks. Capture traffic only when
   the user can without `sudo`.
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
9. Never delete a packet test that was in the project before this
   session, that you wrote from the spec or that `scaffold` wrote, and never
   change its expected values to what the plugin outputs. It may follow a
   rename, or lose an attribute you also remove from `plugin.yaml`. Only the
   placeholder `tests/<label>-basic.yaml` that `init` wrote in this session
   may go.
10. Stop after 10 loop runs that are not green, or when the same `error.code`
   comes back at the same location twice after you changed it. Report what
   you tried and the last envelope.
11. Keep the work folder current: save each envelope and write each run's
   notes as you go, not at the end. Never present a generated capture as a
   real one.

## Step 0: open the work folder

Pick the label first (Step 2 gives its rules), then create `<work>`, as
[`references/workfolder.md`](references/workfolder.md) says: `./<label>-plugin/`
for a new plugin (its project is `<work>/project`), `<project>/../<label>-work/`
for an update, or the directory the user names. Write `request.md` (the
request, verbatim, then each decision and why) and copy the user's inputs
into `inputs/`, with their origin in `inputs/SOURCES.md`. When the user
points at an existing work folder, resume it instead
([workfolder.md](references/workfolder.md#resuming-from-a-work-folder)).

## Step 1: get a capture

The plugin is evaluated on a capture of its protocol (Step 6). Get it now,
as [`references/capture.md`](references/capture.md) says, into
`<work>/capture/capture.pcap`, with `capture.md` saying where it came from:

1. The user gave one: check it holds the protocol under the parent.
2. Else find a real one: next to the inputs, Wireshark's sample and test
   captures, public collections. Record its URL, license and sha256.
3. Else record one from a real implementation on the loopback interface,
   without `sudo`.
4. Else generate one from the spec with `scripts/make_pcap.py`: every
   example, each message type and branch, boundary values, both
   directions. It is **synthetic**: say so everywhere.
5. Else stop and ask the user for a capture, or for leave to skip the
   evaluation.

A real capture of a new protocol is also an entry: use the pcap entry of
Step 2 to let `scaffold` propose fields from it. For an update, reuse the
work folder's capture unless the user gives a new one or the revision adds
messages it lacks.

## Step 2: create the project

Pick a label (`[a-z][a-z0-9_]*`, a name no SDK protocol has) and an id from
950 to 999. `validate` checks both. `<project>` is the project directory,
`<work>/project` for a new plugin, `<selector>` the parent, for example
`udp:dport=4433`, `tcp:port=102` or `ethernet:ethertype=0x88b5`.

Run the entry commands in order and stop at the first that does not exit
0: read its `error.code` (`references/contract.md`) and never go on to the
next one.

From a protocol specification, create the project. Its `plugin.yaml` is a
sample model that you replace with the protocol's:

<!-- eval:entry spec -->
```sh
mmt-plugin --json init <label> --dir <project> --id <id> --parent <selector> --sdk-profile <profile>
```

From a capture, create the project, then let `scaffold` slice the payloads
under the parent into packet tests and propose a field skeleton,
`<project>/plugin.proposed.yaml`:

<!-- eval:entry pcap -->
```sh
mmt-plugin --json init <label> --dir <project> --id <id> --parent <selector> --sdk-profile <profile>
mmt-plugin -C <project> --json scaffold --from-pcap <pcap> --parent <selector>
```

From a legacy PDL v1 model, create the project, then convert the model
next to `init`'s, into `<project>/plugin.imported.yaml`:

<!-- eval:entry pdl -->
```sh
mmt-plugin --json init <label> --dir <project> --id <id> --parent <selector> --sdk-profile <profile>
mmt-plugin -C <project> --json import <pdl> -o <project>/plugin.imported.yaml
```

`init` writes `plugin.yaml` (a sample 4-byte header, with the profile pinned
in `sdk.profile` and the parent declared under `parents:`),
`src/<label>_impl.c` (your code: one function per hook),
`tests/<label>-basic.yaml` (a packet test of the sample header) and
`.gitignore`. A parent that one match of its header identifies (an
EtherType, a UDP source or destination port) gets a `classify`, so do TCP
ports (`tcp:port=102`: a `classify` by port), and the packet test also runs
`through` it; any other parent (`udp:port=4433`, `ip:proto=17`) is left to
`<label>_hook_register_parents`.

`import` warns with `model.legacy-*` codes about constructs that relied on
bugs of the old Java tool. Read each warning: it says what changed. Then
copy `plugin.imported.yaml` over `plugin.yaml` (you wrote it with `init` in
this session), and delete `plugin.imported.yaml`, so that the project has
one model. The imported model has no parent and pins no profile: put back
the `sdk:` and `parents:` that `init` wrote.

Keep the label and the id you gave `init` in `plugin.yaml`:
`src/<label>_impl.c` includes `<label>_mmt_plugin.h`, which `generate`
names after the label.

## Or: update an existing project

When the user gives you an existing plugin project (a directory with
`plugin.yaml`, `src/<label>_impl.c` and `tests/*.yaml`) and a change to make
(a revision of the spec, fields to add, change or remove, or a new
capture), skip Step 2. First check that `<project>` is a project whose model
reads:

<!-- eval:entry update -->
```sh
mmt-plugin -C <project> --json validate --no-sdk
```

`<profile>` is the project's pinned `sdk.profile`, not the newest one. Then,
before you edit anything, run the loop (Step 4) once on the project as it
is. If that run is not green, stop and report its envelope: a failure that
was there before you is the user's to decide, and fixing it would mix with
the change they asked for.

Then make the change, as Step 3 and
[`references/drafting.md`](references/drafting.md), "Updating an existing
project", say:

- Keep `protocol.label`, `protocol.id`, `sdk.profile` and `parents:` as
  they are, unless the request changes them.
- Keep every packet test the project has: they pin what the plugin already
  does. Write the changed behaviour in new test files whose expected values
  come from the revised spec, never from what the plugin outputs.
- Never edit an existing test's bytes or expected values to match the
  revision; only a rename or a removed field may follow in it (Rule 9).
  When the revision contradicts an existing test (a value it expects, a
  field it reads), stop and report the test and the passage of the spec:
  the user decides which is right.

## Step 3: draft plugin.yaml and the packet tests

Follow [`references/drafting.md`](references/drafting.md):

- Write each field of the spec as an attribute or a struct field, at the
  offset and with the type the spec gives. Keep the profile pinned,
  `sdk: {profile: "<profile>"}`, as `init` wrote it. Declare the parent
  with `classify` when one match of the parent's header identifies the
  protocol, or, under `tcp`, a port does.
- From a capture, in a project `init` created in this session, start
  from `plugin.proposed.yaml`: rename its fields after the spec, delete
  those that are payload, copy it over `plugin.yaml`, pin the profile
  again (the proposal pins none), and make the same changes in the packet
  tests `scaffold` wrote. An update never copies a proposal over
  `plugin.yaml`: it folds the new fields in by hand
  ([drafting.md](references/drafting.md#updating-an-existing-project)).
- Write a packet test for each example of the spec, with the values the
  spec gives, never the values the plugin outputs. Delete
  `tests/<label>-basic.yaml` once it no longer describes the protocol, if
  `init` wrote it in this session.

## Step 4: the loop

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
four: each one's envelope shows only its own stage. Save each envelope as
`<work>/runs/run-<n>/<command>.json` (pipe stdout through `tee`), and after
the run write `runs/run-<n>/notes.md`: the command that stopped, its
`error.code` and `location`, and your fix.

## Step 5: read the envelope and fix

| Exit | Class | What to do |
|---|---|---|
| 0 | success | Go to the next command. Read the warnings in `diagnostics` anyway. |
| 1 | internal | A bug in mmt-plugin. Stop and report the envelope. |
| 2 | usage | Your command line is wrong. Fix the arguments; do not change files. |
| 3 | model | Fix `plugin.yaml` or a packet test at each error's `location`. |
| 4 | sdk | Fix the SDK prefix, the profile or the compiler; never the model. |
| 5 | build | Fix `src/<label>_impl.c` at each error's `location` (`build.missing-hook`: add the hook its hint declares). |
| 6 | test | For each failing packet, check the attribute, the expected and the actual value against the spec, then fix the model or the test, whichever is wrong. A test that was in the project before this session is never edited: fix the model, or stop and report when the spec contradicts the test. |
| 7 | state | A file on disk is not what the command needs. Read `error.code`: regenerate, or ask before `--force`. |
| 130 | interrupted | Run the command again. |

[`references/contract.md`](references/contract.md) has the action for every
`error.code`.

## Step 6: evaluate on the capture

When a loop run is green, first look at what the plugin does on the
capture with `run`: it runs the plugin through mmt-dpi's stack (its own
parent classification) and reports the protocol paths with their packet
counts and, per attribute, the packets that have it. A
`test.no-match` warning, or an attribute in none of the plugin's packets,
is a problem to fix before the evaluation:

```sh
mmt-plugin -C <project> --json run <work>/capture/capture.pcap --sdk <prefix> --cc <cc>
```

Read `result.summary.classified`, `result.paths[]` and
`result.protocols[0].attributes[]`; keep the envelope in the loop run's
folder. Then evaluate the built plugin on the capture, as
[`references/evaluation.md`](references/evaluation.md) says:

```sh
python3 <skill>/scripts/pcap_eval.py --sdk <prefix> --cc <cc> \
    --plugin <project>/build/mmtp_<label>.so --label <label> --parent <selector> \
    --capture <work>/capture/capture.pcap --out <work>/eval [--field <attr>=<tshark field>] \
    [--accept <key>=<reason>] [--synthetic]
```

It runs the capture through mmt-dpi without and with the plugin and writes
`<work>/eval/report.md`. Exit 0 is PASS, 1 FAIL, 2 a wrong command, 3 the
environment (compiler, libpcap, SDK). Map every attribute that a tshark
dissector also decodes with `--field`.

Every difference from tshark is a drift: a `--field` attribute whose value
differs, expected frames the plugin misses (`missed`), claimed frames
outside the protocol's traffic (`foreign`). The report lists each one, and
`<work>/eval/drift.jsonl` each of its frames. Judge every drift from the
spec ([evaluation.md](references/evaluation.md#drift-against-tshark)): a
defect, which you fix, or an accepted difference, which you pass as
`--accept <key>=<reason>`, with the reason. A drift not accepted is a
defect, and the evaluation a FAIL. On FAIL, fix one problem
([evaluation.md](references/evaluation.md#fixing-a-fail)), write a packet
test from the frame that showed it with the spec's values, run the loop
until green, then evaluate again; stop after 3 evaluation runs that fail
with the same problem. Explain every warning of a PASS.

## Done

The plugin is green when, in one loop run, all four commands exit 0 and
`test`'s `result.summary` has `failed` 0 and `passed` equal to `total`, with
`total` at least 1 (a run with no packet test is the warning
`test.no-packets`, not green), and `validate`'s `parents-exist` check is
`pass`. It is done when it is green and the capture evaluation of that
build is PASS (no open drift: each one fixed, or accepted with its reason),
or the evaluation was skipped with the user's leave or for lack of an SDK.
Never report a plugin as done while a drift is a defect.

Write `<work>/REPORT.md`, `<work>/manifest.json` and `<work>/README.md`
([workfolder.md](references/workfolder.md)), then report:

- the work folder, the project directory, the label, the id and the
  parent;
- for an update, what changed in `plugin.yaml` and which packet tests you
  added, and that the label, the id, the profile and the parents are those
  of the project (or what the request changed);
- how many loop runs it took, and what each fix was (its `error.code` and
  `location`);
- the last `test` summary;
- the capture: where it came from (given, found with its URL, recorded,
  or synthetic), and the evaluation: its verdict, recall, field agreement
  and each warning with its explanation;
- the drift against tshark: each drift, its key, its frames, and whether
  it was fixed or accepted, with the reason;
- what you could not check (no SDK, no tshark: drift not checked, no
  tshark dissector, a field the spec leaves open, a synthetic capture).

## Evals

`evals/` holds scripted runs of this skill: each case in `evals/cases/` is a
starting point (a spec, a capture, a PDL model, or an existing project and a
revision of its spec) and the drafts an agent makes, one per loop run.
`evals/run_evals.py` runs the entry and loop commands of this file, as
written above, on each case, and fails when an envelope breaks
[`references/contract.md`](references/contract.md), when a loop run does
not stop where the case expects, when a fix does not touch the location the
envelope gave, or when a command reads stdin (each command gets an open
pipe with no data and no terminal, and a time limit). An
update case (`telem-update`) starts from a copy of its project, runs the
loop once on it, which must be green, and fails when the update changes the
label, the id, the profile or the parents, deletes or rewrites a test the
project had, or adds no packet test. With `--sdk`, it runs all four loop
commands; without, it stops after `generate`.

```sh
uv run python skills/mmt-plugin-generator/evals/run_evals.py
uv run python skills/mmt-plugin-generator/evals/run_evals.py --sdk <prefix> --cc gcc
```

`tests/unit/skill/` runs them in CI: without an SDK in every Python job,
with one in the "Generated code" job, which also generates a capture with
`scripts/make_pcap.py` and evaluates a built plugin on it with
`scripts/pcap_eval.py`.
