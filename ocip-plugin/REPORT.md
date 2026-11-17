# ocip plugin — 2026-11-17

Cisco BroadWorks OCI-P over TCP 2208, for mmt-security rule 231 (CVE-2026-20320 XXE). Green and evaluated: PASS.

- Work folder: `ocip-plugin/` (this folder) in the worktree `plugin_generator-ocip` (branch `feat/ocip-plugin` from
  `origin/dev` d91ba5f, uncommitted). Project: `ocip-plugin/project`.
- Label `ocip`, id 960, parent `tcp` port 2208 (either side), classified by `ocip_hook_register_parents` (weight 4), SDK
  profile 1.10.2. Registered name in mmt-dpi: `OCIP` (mmt-plugin upper-cases the label; mmt-security resolves names
  case-sensitively, so rules write `OCIP.has_dtd`).
- Entry: spec (`init`), the attributes of `inputs/dpi-request-231.md` plus `is_request`; every attribute is a hook in
  `src/ocip_impl.c` (per-direction stream state, the `examples/ocpp` pattern).

## Loop runs

| Run | Stop | Fix |
|---|---|---|
| 1 | green: validate, generate, build, test exit 0 | — (first draft) |
| 2 | green, `test --sanitize` | — |
| 3 | green, `test --sanitize` | review: a segment with no new bytes (retransmission, or an earlier segment arriving late) reported nothing, so a reordered attack evaded `has_dtd` (old rule 1, new rule 0 on `attack_v10_reordered.pcap`); now searched alone. Added `session-long-split-doctype` (126 packets, past the 40 classification packets) |

Last `test` summary: `{total: 28, passed: 28, failed: 0, skipped: 0}`: 11 packet tests, each also `through`
`tcp:dport=2208`, and 8 session tests (split DOCTYPE, benign session, UTF-16 split at an odd byte, DTD in a 2nd
message plus its retransmission, two messages in one segment, a gap, a server DOCTYPE, and a 126-packet session whose
split DOCTYPE comes after 50 benign packets with 70 s idle between its halves). `--sanitize`: 28209 fuzz and
corrupted-session packets under ASan/UBSan, 0 crashes. Tests that bite: a flipped expectation and a build without the
carried tail both fail (`runs/run-1/notes.md`).

## Capture and evaluation

- Capture: `capture/capture.pcap`, **synthetic**: the 11 pcaps of `inputs/gen_pcaps.py` (attack V1-V7, benign OCI-P,
  SOAP and HTML-DOCTYPE flows), one after the other, with each file's client port moved (`capture/make-capture.sh`;
  gen_pcaps.py gives V2 and V4 the same port 41019, which merged as-is reads V4 as a retransmission of V2).
- `mmt-plugin run`: 101 frames, 50 OCIP; `has_dtd` on 23 packets (every payload segment on 2208), `dtd` 8.
- `pcap_eval.py` (with tshark 4.2.2, `-d tcp.port==2208,xml`): **PASS**, 23/23 expected frames classified, recall 1.0,
  0 problems; warning: synthetic capture.

## Drift against tshark

None (no `--field`: tshark has no OCI-P dissector; its generic XML dissector's fields do not match these attributes
one to one). Extra cross-check, `eval/tshark-crosscheck.md`: tshark's `xml.doctype` against `has_dtd` frame by frame:
22/23 agree; the one difference is frame 61 (attack V7, second segment), where tshark (no reassembly under decode-as)
sees no DOCTYPE and the plugin does.

## Not checked

- No real OCI-P capture or BroadWorks server (none public); every value comes from the wire format of
  lukebeer/broadworks-ocip.
- OCI-P over TLS (2209), OCI over SOAP (HTTP; rule 231 keeps a payload scan for it), OCI-P on another port.
- Encodings other than UTF-8/ASCII and UTF-16 (UTF-32, EBCDIC).
- `dtd`, `session_id`, `command_type` of a message are from the first one that ends in the segment; `dtd` keeps the
  declaration's first 63 bytes.
