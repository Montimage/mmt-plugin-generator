# Request

Verbatim (orchestrator task, 2026-11-17):

> run the end-to-end experiment described in ocip-plugin-brief.md — build a Cisco BroadWorks OCI-P plugin with
> plugin_generator's dev branch (in a separate worktree), install it, rewrite mmt-security rule 232 to use ocip.*
> attributes, and test it end to end (all 8 attack variants including the split-segment V7, plus 5 benign pcaps).

The brief is `inputs/ocip-plugin-brief.md`; the attributes requested are those of `inputs/dpi-request-232.md`.

## Decisions

| Decision | Value | Why |
|---|---|---|
| Label | `ocip` | brief: rules use `ocip.has_dtd`. mmt-plugin registers the label upper-cased (`OCIP`) and mmt-security names are case-sensitive, so rules write `OCIP.has_dtd` |
| Id | 960 | free in the SDK profile, the installed plugins (`init` checked) and the dev examples (976-993) |
| Parent | `tcp`, port 2208 (either side), in `ocip_hook_register_parents` | brief. Not the generated `classify`: as in `examples/ocpp`, the plugin's own TCP classification must run on every packet of its sessions to keep the per-direction state (mmt-dpi 1.10.2 runs the session data hooks only after TCP stops classifying) |
| Claim | by port only, any segment with payload | an "is it XML" sniff would be a bypass of the rule (advisor); the old rule fired on any client segment to 2208 |
| SDK profile / prefix | 1.10.2, `/sdk/mmt` in `mmt-plugin-dev:local` (Ubuntu 24.04) | the profile the dev branch ships; private prefix of the image |
| Compiler | gcc | the image's default (`MMT_GOLDEN_CC`) |
| Install target | the `rulegen` container (Ubuntu 22.04, glibc 2.35, MMT-DPI 1.10.2): `mmt-plugin install --prefix project/build/prefix`, then the same `.so` copied into the container's `/opt/mmt/plugins/` | `objdump -T` shows only `GLIBC_2.17`, so the tested 24.04 build loads there; no rebuild |
| `has_dtd` | U8 on every payload segment of the plugin: 1 on the segment where a `<!DOCTYPE` (ASCII case-insensitive, UTF-16LE, UTF-16BE) completes, with a carried per-direction tail of 17 bytes; else 0. A segment with no new bytes (retransmission, or an earlier segment arriving late) is searched alone and reports `has_dtd` and `is_request` only (changed in run 3: it reported nothing, and a reordered attack evaded it); one that falls in the direction's latest hole is also searched across the hole's edges (run 7, #137: a `<!DOCTYPE` split across two reordered segments evaded it) | never weaker than the old payload scan, independent of the XML parse and of the encoding guess |
| `dtd`, `session_id`, `command_type` | strings (63 bytes), from a bounded per-direction streaming XML tokenizer (no XML library, no entity resolution), reported on the segment where each one completes | values that span segments are rebuilt |
| `is_request` | U8 (extra attribute, not in the DPI request): 1 when the TCP destination port is 2208, 0 otherwise; absent without TCP below | rule 232 must alert on client messages only (benign server reply with a DOCTYPE) |
| OCI over SOAP (V5) | not covered by the plugin | it is HTTP on port 80; rule 232 keeps its payload-scan branch for it |
| Project place | `ocip-plugin/project` at the worktree root, not under `examples/` | `tests/unit/examples` enumerates `examples/` and expects `*_example` labels |

## Assumptions

- Legitimate OCI-P never carries a DTD (same assumption as rule 232).
- Message framing: a message ends with `</BroadsoftDocument>`; the tokenizer then re-detects the encoding of the next one.
