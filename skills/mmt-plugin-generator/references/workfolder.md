# The work folder

Every run of the skill leaves one folder, `<work>`, with everything that
went into the plugin, not only its code: the user's request, the inputs and
where they came from, the capture, each loop run's envelopes and what was
changed after it, the capture evaluation and the final report. Someone who
opens it later (the user, or another agent) can see why the plugin is what
it is, re-run every step, and pick the work up where it stopped.

## Where it goes

- A new plugin: `<work>` is the directory the user names, else
  `./<label>-plugin/` in the current directory. The project is
  `<work>/project/`, so `<project>` in `SKILL.md` is `<work>/project`.
- An update: the project stays where it is; never move or copy the user's
  project. `<work>` is the directory the user names, else
  `<project>/../<label>-work/`. When that folder exists from an earlier
  run, keep it and add to it: new loop runs continue the numbering, and
  `REPORT.md` gets a new dated section.
- Never inside this repository's `examples/` or `skills/`, unless the user
  asks.
- `<work>` must be empty or a work folder of the same label (it has
  `request.md` naming it). Anything else: ask for another directory.

## Layout

```
<work>/
  README.md            what the folder is, the state, and how to resume (below)
  request.md           the user's request, verbatim, then the decisions
  inputs/              copies of what the user gave: spec, PDL model, notes
    SOURCES.md         each input: origin (user, URL), date, license, sha256
  capture/
    capture.pcap       the capture the plugin is evaluated on (or .pcapng)
    capture.md         how it was obtained (given, found, recorded, generated)
    payloads.txt       generated without cyberlab only: the make_pcap.py input
    make-capture.sh    the commands that rebuild or re-trim capture.pcap
    <label>-lab/       recorded or crafted through cyberlab: mission.md,
                       expect.json, the lab files (payloads.txt when crafted),
                       out/ (the trace, its provenance.json, verify.json)
    cyberlab-session   the asm lease id, released once the capture is in place
  project/             new plugin only: the mmt-plugin project
  runs/
    run-<n>/
      <command>.json   each envelope of loop run n (validate, generate, ...)
      notes.md         what failed (exit, error.code, location) and the fix
  eval/                scripts/pcap_eval.py --out: report.md, report.json,
                       frames.jsonl, drift.jsonl (with tshark),
                       baseline.json, plugin.json
                       (bin/ and plugins/ are rebuilt: no need to keep them)
  REPORT.md            the final report (SKILL.md, "Done")
  manifest.json        versions and hashes (below)
```

`request.md` lists the decisions with the reason for each: label, id,
parent selector, SDK profile, SDK prefix, compiler, and every point where
the spec was unclear and what was assumed.

`runs/run-<n>/notes.md` is written after each loop run, before the next
one: the command that stopped, its `exit_code`, `error.code` and
`location`, and the change made (the file and a one-line why). A green run
says so and gives `test`'s `result.summary`.

Save an envelope by piping the command's stdout through `tee`, so that you
still read it:
`mmt-plugin -C <project> --json validate --sdk <prefix> | tee <work>/runs/run-1/validate.json`.
Pass `-o pipefail` (or check `${PIPESTATUS[0]}`) to keep the command's exit
code.

## manifest.json

```json
{
  "schema": 1,
  "label": "telem",
  "id": 963,
  "parent": "udp:dport=5684",
  "sdk_profile": "1.10.2",
  "created": "2025-01-31T10:00:00Z",
  "updated": "2025-01-31T11:20:00Z",
  "tools": {
    "mmt-plugin": "0.1.0",
    "sdk": "/path/to/prefix (mmt-dpi 1.10.2)",
    "cc": "gcc 13.3.0",
    "tshark": "4.2.2 or null"
  },
  "files": {
    "inputs/spec.md": "<sha256>",
    "capture/capture.pcap": "<sha256>",
    "project/plugin.yaml": "<sha256>",
    "project/build/mmtp_telem.so": "<sha256>"
  },
  "loop_runs": 4,
  "eval": {
    "verdict": "PASS",
    "recall": 1.0,
    "report": "eval/report.md",
    "drift": {"checked": true, "open": 0, "accepted": 1}
  }
}
```

`eval.drift` is `report.json`'s `drift` without its items: `checked` false
without tshark.

## REPORT.md

The final report of `SKILL.md`, "Done", with a section per run of the
skill (dated, for an update). Its "Drift against tshark" part has one row
per drift of the last evaluation, from `eval/report.md`:

| Key | Kind | Frames | Status | Reason, or the fix |
|---|---|---:|---|---|
| length | field | 4 | accepted | udp.length counts the UDP header; the spec's length is the message's |
| missed | classification | 2 | fixed | `classify` matched only the client's port: run 3 |

A drift fixed in an earlier evaluation run is listed as `fixed`, with the
loop run of the fix. No drift: say "none". No tshark: "not checked: no
tshark".

Take the versions from `mmt-plugin --json --version` (`result.version`),
the SDK's `dpi/lib/libmmt_core.so.<version>`, `<cc> --version` and
`tshark --version` (first line each).

## README.md

Short, and written last:

1. One line: the protocol, the label, and whether the plugin is green and
   the evaluation passed.
2. "Re-run": the loop commands with this folder's paths, then the
   `pcap_eval.py` command of the last evaluation run, with its `--accept`
   flags (each accepted item of `drift.items` in `eval/report.json`: its
   key and reason).
3. "Resume": what is left (a failing step, an open question, a drift that
   is still a defect, a warning of the evaluation that was not explained),
   or "nothing".

## Resuming from a work folder

When the user points at a work folder (it has `request.md` and
`manifest.json`), read `README.md`, `request.md`, the last
`runs/run-<n>/notes.md` and `eval/report.md` before anything else. Then
continue from the first step that is not done: the loop if the last run
was not green, the evaluation if it has no PASS, else the update the user
asks for (`SKILL.md`, "Or: update an existing project", with
`<work>/project` as the project).
