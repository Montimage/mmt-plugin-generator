# Brief — OCI-P mmt-dpi plugin + rule 231 end-to-end experiment

## Goal
Build an MMT-DPI plugin for Cisco BroadWorks OCI-P with plugin_generator's **dev** branch (`mmt-plugin` Python CLI + its
`skills/mmt-plugin-generator` skill), install it, rewrite mmt-security rule 231 to use the plugin's attributes instead of a raw
payload scan, and test end to end. Success = the new rule alerts on all 8 attack variants **including V7 (`<!DOCTYPE` split
across two TCP segments, which the current rule misses)** and 0 on all benign pcaps.

## Background (already done — read, don't redo)
- Rule 231 run (PARTIAL, payload-scan workaround): `/Users/montimage/workspace/montimage/mmt/mmt-security-rule-generator-skill/experiments/2026-11-17-broadworks-oci-xxe/`
  — read `README.md`, `report.md`, `rules/231.broadworks_oci_xxe.xml`, and especially `docs/dpi-requests/231.broadworks_oci_xxe.md`
  (the requested attributes: `has_dtd` U8, `dtd` string, `command_type` string, `session_id` string; OCI-P wire format; acceptance check).
- Pcaps + Scapy generator: that bundle's `lab/gen_pcaps.py` and `lab/pcaps/` (attack_v1..v7, benign_ocip, benign_soap, benign_html_doctype).
- OCI-P wire format: XML doc `<?xml ...?><BroadsoftDocument protocol="OCI" xmlns="C" ...><sessionId>..</sessionId><command xsi:type="X">..</command></BroadsoftDocument>`
  terminated by `\n`, TCP 2208 cleartext (source: github.com/lukebeer/broadworks-ocip Builder.php / TCPTransport.php).
- Sandbox mmt-security (upstream main a78a4fd, rule 231 already added and registered in check/):
  `/Users/montimage/.cache/mmt-rule-generator/20261117-153111/mmt-security`. Docker image `mmt-rulegen-dev:local`
  (FROM mmt/mmt-security:e2e-probe18, MMT-DPI 1.10.2 in /opt/mmt, has python3/scapy/xmllint/valgrind/tshark). Run it as:
  `docker run -d --name rulegen -v /Users/montimage/.cache/mmt-rule-generator/20261117-153111:/work -v <rule-skill>/mmt-rule-generator:/skill:ro -w /work/mmt-security --entrypoint sleep mmt-rulegen-dev:local infinity`
  and `docker exec -e MMT_SEC_REPO=/work/mmt-security rulegen ...`. Rule skill scripts are in `<rule-skill>/mmt-rule-generator/scripts/`
  (`test_rule.sh`, `probe_attrs.sh`, `dpi_lookup.py`, `add_check.sh`, `regression.sh`; each has `--help`).
- Regression baseline: only `19.SQLI 13` fails pre-existing.

## Hard rules
- **MMT C code builds/runs only in Linux Docker containers**, never on the macOS host (see /Users/montimage/workspace/montimage/mmt/CLAUDE.md).
- `/Users/montimage/workspace/montimage/mmt/plugin_generator` is on `main` with **uncommitted work — do not touch it**.
  Create a separate worktree from `origin/dev`: `git -C .../plugin_generator worktree add ../plugin_generator-ocip -b feat/ocip-plugin origin/dev`
  and work only there. Read its `AGENTS.md`/`CLAUDE.md` first and follow them, then follow `skills/mmt-plugin-generator/SKILL.md`.
- Closest precedent: `examples/ocpp` (text protocol over TCP, per-session state for messages split across segments — mmt-dpi gives plugins
  no TCP reassembly). Do the same for OCI-P: carry a small per-direction tail so `<!DOC|TYPE` across segments is detected.
- Plugin label `ocip`, so rules can use `ocip.has_dtd`. Pick a free protocol id (not used by the SDK or the dev examples). Parent: tcp port 2208.
  Never use an XML library that resolves entities; bounded scanning only.
- Build/test the plugin with `mmt-plugin` in a container against mmt-dpi 1.10.2 (image `mmt-plugin-dev:local` may already fit; check it, else
  follow the dev branch's Dockerfile / AGENTS.md). Include packet tests and session tests (split DOCTYPE, benign session, UTF-16), `test --sanitize`.
- Install the plugin into the `rulegen` container's mmt-dpi plugin dir (or via `MMT_DPI_PLUGINS_DIR`), run `make gen_dpi` in the sandbox,
  confirm `dpi_lookup.py check ocip.has_dtd ...` prints OK and `probe_attrs.sh` shows the expected values on the pcaps.
- Write the plugin-based rule as a **new file next to the old one for comparison** (e.g. `rules/231.broadworks_oci_xxe.xml` updated in a copy
  of the sandbox, or keep the old one as `..._payload.xml` in the bundle) — keep id 231. Run `test_rule.sh` (last run `--valgrind`) with all 8
  attack + 5 benign pcaps (V7 now in `--attack`), compare old vs new rule alert counts, then `add_check.sh` (refresh expect) + `regression.sh`.
- Do not commit, push or open PRs. Never put "Co-Authored-By: Claude" anywhere. Don't touch `/Users/montimage/workspace/montimage/mmt/mmt-security`.

## Deliverables
1. Plugin project in the worktree (`feat/ocip-plugin`, uncommitted), with tests passing.
2. Experiment bundle `/Users/montimage/workspace/montimage/mmt/mmt-security-rule-generator-skill/experiments/2026-11-17-ocip-plugin-rule231/`
   (same layout style as the 2026-11-16 and 2026-11-17 bundles): README.md (result first line), report.md (check table with commands + counts,
   old vs new rule comparison, provenance: crafted pcaps), plugin copy (plugin.yaml, src/, tests/), new rule, pcaps used, regression before/after,
   and a row in `experiments/README.md`.
3. A short final reply (≤ 15 lines): result (COMPLETE/PARTIAL/BLOCKED), per-variant old vs new alert counts, any limits, paths.
   If blocked on a decision, stop and say what you need instead of guessing.
