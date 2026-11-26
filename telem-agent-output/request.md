# Request

Write a new mmt-dpi plugin from the protocol specification /in/spec.md.

Use the label telem, the id 963 and the parent udp:dport=5684. For every mmt-plugin loop command and every pcap_eval.py command, use exactly one simple command per execute call, with literal absolute paths: no shell variables, assignments, cd, semicolons, &&, substitutions, redirections, or compound commands; the only allowed extra is the single trailing tee documented in SKILL.md.

Run mode: unattended. SDK /opt/sdk, compiler gcc, no capture given, synthetic capture allowed. Evaluation requested.

# Decisions

- Label telem, id 963, parent `udp:dport=5684` (given).
- SDK profile 1.10.2 (only one available).
- Capture: cyberlab unavailable (no asm, no CYBERLAB_DIR); synthetic capture with scripts/make_pcap.py, allowed by the request. Origin: synthetic.
- Spec ambiguities / assumptions:
  - `flags` bit 1 = battery low; others reserved: modelled as a 4-bit `flags` field, value tested whole.
  - `readings` is a per-session counter not in the packet: attribute without offset, extracted by hook `telem_hook_extract_readings` (returns 0 / a counter in the user code).
  - `payload` only present when msg_type == 1, at offset 8, length `length - 8`.
