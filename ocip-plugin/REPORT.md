# ocip plugin — 2026-11-17

> Renumbered 2026-11-19: this rule was id 231 when the experiment ran; it is now 232 because 231 is used by the OCPP 1.6-J charging-limit rule (Montimage/mmt-security PR #25). Logs and directory names keep the original id.

Cisco BroadWorks OCI-P over TCP 2208, for mmt-security rule 232 (CVE-2026-20320 XXE). Green and evaluated: PASS.

- Work folder: `ocip-plugin/` (this folder) in the worktree `plugin_generator-ocip` (branch `feat/ocip-plugin` from
  `origin/dev` d91ba5f, uncommitted). Project: `ocip-plugin/project`.
- Label `ocip`, id 960, parent `tcp` port 2208 (either side), classified by `ocip_hook_register_parents` (weight 4), SDK
  profile 1.10.2. Registered name in mmt-dpi: `OCIP` (mmt-plugin upper-cases the label; mmt-security resolves names
  case-sensitively, so rules write `OCIP.has_dtd`).
- Entry: spec (`init`), the attributes of `inputs/dpi-request-232.md` plus `is_request`; every attribute is a hook in
  `src/ocip_impl.c` (per-direction stream state, the `examples/ocpp` pattern).

## Loop runs

| Run | Stop | Fix |
|---|---|---|
| 1 | green: validate, generate, build, test exit 0 | — (first draft) |
| 2 | green, `test --sanitize` | — |
| 3 | green, `test --sanitize` | review: a segment with no new bytes (retransmission, or an earlier segment arriving late) reported nothing, so a reordered attack evaded `has_dtd` (old rule 1, new rule 0 on `attack_v10_reordered.pcap`); now searched alone. Added `session-long-split-doctype` (126 packets, past the 40 classification packets) |
| 4 | green | — (re-run after `loop.sh` was made shellcheck-clean) |
| 5 | green, `test --sanitize` | — (baseline on `dev` 1b54ba6 before #137) |
| 6 | exit 6, 29/32 | #137: four reordered session tests (new session key `back`); `has_dtd` 0 where a late segment completes a `<!DOCTYPE` split across a hole |
| 7 | green, `test --sanitize` | #137: each direction records its latest hole; a late segment is searched across the hole's edges, and a filler sent into the hole first hides nothing |
| 8 | green, `test --sanitize` | — (#137's final source: comments only; the `.so` evaluated below; also green with clang) |
| 9 | green, `test --sanitize` | review of #137: a `<!DOCTYPE` split between two late segments is missed; pinned by `session-reordered-two-late-halves` and documented below (comments only in the source, the same `.so`) |
| 10 | green, `test --sanitize` | review of #137: a late segment is searched once, with the hole's edges as they stand then, so a `<!DOCTYPE` that needs bytes after the hole that arrive later is missed; pinned by `session-reordered-short-after-edge` and documented below (comments only in the source) |
| 11 | exit 6, 35/38 | #140: four session tests of an in-order filler (one the server drops, the probe keeps) followed by the real bytes at its sequence number; `has_dtd` 0 where those bytes complete a `<!DOCTYPE` in the server's stream |
| 12 | green, `test --sanitize` | #140: a segment sent over a direction's last scanned bytes is also searched after the 17 bytes before them, unless that segment reported `has_dtd`; also green with clang |

Last `test` summary: `{total: 38, passed: 38, failed: 0, skipped: 0}`: 10 packet tests, each also `through`
`tcp:dport=2208`, and 18 session tests (split DOCTYPE, benign session, UTF-16 split at an odd byte, DTD in a 2nd
message plus its retransmission, two messages in one segment, a gap, a server DOCTYPE, a 126-packet session whose
split DOCTYPE comes after 50 benign packets with 70 s idle between its halves, six reordered ones: V7's halves
in reverse order, the same after a filler sent into the hole, a 2-byte late segment between both halves, a whole
DOCTYPE in the segment that arrives first, and two misses pinned as limits: V7 cut in three in reverse order, and
a late byte whose keyword ends in bytes after the hole that arrive later; and four of an in-order filler, #140:
`TYPE` sent over a filler after `...<!DOC`, the whole `TYPE ...` over it and past it, a whole `<!DOCTYPE` over a
16-byte filler, and a control: a benign retransmission and a segment that repeats an XXE and adds new bytes, both
`has_dtd` 0).
`--sanitize`: 38297 fuzz and corrupted-session packets under ASan/UBSan, 0 crashes. Tests that bite: a flipped expectation and a build without the
carried tail both fail (`runs/run-1/notes.md`).

## Capture and evaluation

- Capture: `capture/capture.pcap`, **synthetic**: the 11 pcaps of `inputs/gen_pcaps.py` (attack V1-V7, benign OCI-P,
  SOAP and HTML-DOCTYPE flows), one after the other, with each file's client port moved (`capture/make-capture.sh`;
  gen_pcaps.py gives V2 and V4 the same port 41019, which merged as-is reads V4 as a retransmission of V2).
- `mmt-plugin run`: 101 frames, 50 OCIP; `has_dtd` on 23 packets (every payload segment on 2208), `dtd` 8; the same
  counts with run 12's `.so` (`runs/run-12/run.json`).
- `pcap_eval.py` (with tshark 4.2.2, `-d tcp.port==2208,xml`, run 8's `.so`; not re-run after #140): **PASS**,
  23/23 expected frames classified, recall 1.0, 0 problems; warning: synthetic capture.

## Drift against tshark

None (no `--field`: tshark has no OCI-P dissector; its generic XML dissector's fields do not match these attributes
one to one). Extra cross-check, `eval/tshark-crosscheck.md`: tshark's `xml.doctype` against `has_dtd` frame by frame:
22/23 agree; the one difference is frame 61 (attack V7, second segment), where tshark (no reassembly under decode-as)
sees no DOCTYPE and the plugin does.

## Not checked

- No real OCI-P capture or BroadWorks server (none public); every value comes from the wire format of
  lukebeer/broadworks-ocip.
- OCI-P over TLS (2209), OCI over SOAP (HTTP; rule 232 keeps a payload scan for it), OCI-P on another port.
- Encodings other than UTF-8/ASCII and UTF-16 (UTF-32, EBCDIC).
- `dtd`, `session_id`, `command_type` of a message are from the first one that ends in the segment; `dtd` keeps the
  declaration's first 63 bytes.
- Reordered and inserted segments (#137): a segment that arrives late in a hole reports `has_dtd` (searched alone
  and across the hole's edges) and `is_request` only; `dtd`, `session_id` and `command_type` are not rebuilt across
  a reordering. Only a direction's latest hole is kept, so a keyword split around an earlier hole is missed. A late
  segment is searched once, with the hole's edges as they stand when it arrives, so a keyword is found only when its
  bytes are in that late segment and in the edges already recorded: it is missed when it needs bytes after the hole
  that arrive later (`session-reordered-short-after-edge` pins the miss), or bytes of another late segment
  (`session-reordered-two-late-halves`). The old payload-scan rule 232 misses these too.
- Overlapping segments, an in-order filler (#140): a filler the server drops (a bad checksum) but the probe keeps can
  arrive in order, before the real bytes at the same sequence number. A segment that starts at or before a
  direction's last scanned bytes and has bytes from their start on is also searched for `has_dtd`, with no state
  change, after the 17 bytes before those bytes (the server's stream), unless the last segment reported `has_dtd`:
  a segment that repeats an attack segment and adds new bytes reports it no more than before (a retransmitted attack
  segment still reports it again), and a plain retransmission of a benign segment reports 0. `dtd`, `session_id`
  and `command_type` keep following the bytes the probe took first. Still missed: a filler of several segments
  (only the last one's start is kept), a segment that starts inside the last bytes, and, after a filler, a keyword
  that needs bytes of the real segment and of the segments after it.
