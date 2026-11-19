# Evals

For maintainers of this skill: what `evals/run_evals.py` checks. The agent running the skill does not need it.

`evals/` holds scripted runs of this skill: each case in `evals/cases/` is a
starting point (a spec, a capture, a PDL model, or an existing project and a
revision of its spec) and the drafts an agent makes, one per loop run.
`evals/run_evals.py` runs the entry and loop commands of [`SKILL.md`](../SKILL.md), as
written there, on each case, and fails when an envelope breaks
[`references/contract.md`](contract.md), when a loop run does
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
