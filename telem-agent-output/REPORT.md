# TELEM plugin report

- Work folder: /work/plugin-work-5c743542; project: /work/plugin-work-5c743542/project
- Label `telem`, id 963, parent `udp:dport=5684`, SDK profile 1.10.2 (SDK /opt/sdk, gcc 13.3.0)
- Result: **DONE** (green; capture evaluation PASS on a **synthetic** capture)

## Loop runs: 3

| Run | Stopped at | error.code / location | Fix |
|---|---|---|---|
| 1 | build (exit 5) | `build.missing-hook` at src/telem_impl.c | defined `telem_hook_extract_readings` (returns 0 = absent) |
| 2 | test (exit 3) | `model.bad-packet-test` at tests/telem-ack.yaml (my own test: absent `payload` lacked `type`) | added `type: MMT_BINARY_DATA` |
| 3 | green | - | validate, generate, build, test all exit 0 |

Last `test` summary: total 4, passed 4, failed 0, skipped 0 (telem/reading and telem/ack, each also `through: udp:dport=5684`). `validate` `parents-exist`: pass.

## Model

Struct `telem_hdr` (bitfields `version`:4, `flags`:4; `msg_type` u8; `length` u16; `sequence` u32, big-endian), `payload` (MMT_BINARY_DATA, offset 8, length `length - 8`) only `if msg_type == 1`, and `readings` (MMT_U32_DATA, no offset, hook). Parent: `classify` on UDP destination port 5684, protocol at UDP offset 8.

Packet tests: both spec examples (`tests/telem-reading.yaml`, `tests/telem-ack.yaml`); the init placeholder `telem-basic.yaml` was removed.

## Capture and evaluation

- Capture: **synthetic** (not a real one), 9 frames made by scripts/make_pcap.py from payloads.txt (written from the spec before the plugin existed): both spec examples, flags 0/1/2/0xf, empty and non-empty payloads, extreme sequence values, both directions. cyberlab was unavailable (no `asm`, no `$CYBERLAB_DIR`); the request allows a synthetic capture. See capture/capture.md.
- `run`: 9/9 frames classified, path `meta.ethernet.ip.udp.TELEM`; attributes in 9 packets each, `payload` in 5 (the readings), `readings` in 0.
- `pcap_eval.py --synthetic`: **PASS**, 9/9 expected frames claimed, recall 1.0, 0 open drifts.
- Warnings, explained:
  - `attributes never extracted: readings`: by design. The spec gives `readings` as a per-session counter that is not in the packet and says nothing about how it is kept or reported; the hook reports it absent (questions.md Q2). Not implemented: counting per session.
  - `synthetic capture`: it shows that the plugin loads, classifies under its parent and extracts every attribute on mmt-dpi's path, not that the spec was read right, nor real traffic.
- Acknowledgements are sent from port 5684 (source) in the capture; mmt-dpi classifies them as part of the session (all 9 frames claimed), so no `missed` drift. The spec states only that a sensor sends to destination port 5684; the port of an acknowledgement is an assumption of the capture.

## Drift against tshark

None reported (0 open, 0 accepted). It is limited: tshark has no TELEM dissector (it decodes port 5684 as DTLS), so no `--field` comparison exists; only the `missed` and `foreign` checks (from the parent's filters) ran.

## Could not check

- The `readings` session counter (spec leaves its semantics open; reported absent).
- Field values against a reference tool (no TELEM dissector in tshark).
- Real-traffic behaviour (synthetic capture).
- `flags` is a whole 4-bit value; the spec only defines bit 1 (battery low), so no separate battery bit attribute.

## Questions (questions.md)

- Q1: may a synthetic capture be used (cyberlab unavailable)? Taken: yes (the request grants it).
- Q2: how to treat `readings`? Taken: declared, hook returns 0 (absent).
