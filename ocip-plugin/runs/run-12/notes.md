Run 12 (#140), after the fix: green, `test --sanitize`: `{total: 38, passed: 38, failed: 0}`; sanitize: 38297
packets, 0 crashes. Also green with clang (`tests/unit/ocip/test_sdk.py`, `MMT_GOLDEN_CC=clang`).

`src/ocip_impl.c`: each direction records where its last scanned bytes start, the 17 bytes of the tail before them
and whether that segment reported `has_dtd`. A segment that starts at or before those bytes and has bytes from their
start on (no new bytes, or an overlap with new bytes past them) is also searched, with no state change, as those 17
bytes followed by its bytes from that start on: the server's stream when the last bytes were a filler it dropped.
The search is skipped when the last segment reported `has_dtd`, so `session-overlap-control`'s segment that repeats
an XXE and adds new bytes still reports 0; without that guard it reports 1 (checked on a copy of the project). Run 11
is the failing run of the same tests.

`run.json`: `mmt-plugin run capture/capture.pcap` with this run's `.so`: 101 frames, 50 OCIP, `has_dtd` on 23
packets, `dtd` on 8, as in run 3 (the counts `eval/` reports). `pcap_eval.py` was not re-run: `eval/` comes from the
`.so` of run 8.
