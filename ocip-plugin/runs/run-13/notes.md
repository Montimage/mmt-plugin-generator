Run 13 (#140, review): green, `test --sanitize`: `{total: 39, passed: 39, failed: 0}`; sanitize: 39305 packets,
0 crashes. Also green with clang (`tests/unit/ocip/test_sdk.py`, `MMT_GOLDEN_CC=clang`).

Changes after the review of run 12:
- A limit, pinned, not fixed: only the last scanned segment's start is kept, so `...<!DOC`, a filler in order, the
  rest of the message in order, then the real `TYPE` at the filler's sequence number is missed (the real bytes end
  before the last segment's start and are searched alone; the server reads `<!DOCTYPE`).
  `session-inorder-filler-then-rest` expects `has_dtd` 0 on every packet; `REPORT.md` and the header of
  `src/ocip_impl.c` give the limit.
- `src/ocip_impl.c`: a segment whose capture ends inside the overlap (no new byte captured) now reports what the
  search over the last bytes found (`has_dtd` 1 and `is_request`) instead of nothing.

`run.json`: `mmt-plugin run capture/capture.pcap` with this run's `.so`: 101 frames, 50 OCIP, `has_dtd` on 23
packets, `dtd` on 8, as before. `pcap_eval.py` re-run with this `.so` (tshark 4.2.2, the command of `README.md`, in
the `mmt-plugin-generator-toolchain:local` container with tshark and libpcap-dev added): PASS, 23/23, recall 1.0, no
drift; `eval/` is that run: only the `.so`'s sha256 and the packet pointers in `frames.jsonl` and `plugin.json`
changed.

After the second review: comments only in `src/ocip_impl.c` (the limit worded more exactly, and a segment whose
capture ends inside the bytes already seen reports nothing unless the search over the last bytes finds a keyword; no
session test can build such a cut frame). `build --rebuild` gives the same `.so` bytes (`1f9aceb0...`), so the
evaluation and `manifest.json`'s `.so` hash still hold.
