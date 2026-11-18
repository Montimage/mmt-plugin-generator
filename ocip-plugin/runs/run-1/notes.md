# Run 1

Green. `validate`, `generate`, `build`, `test` all exit 0; `test` `result.summary`:
`{total: 27, passed: 27, failed: 0, skipped: 0}` (11 packet tests, each also `through` `tcp:dport=2208`, and 7 session tests).

Before this run: `init` (runs/entry/init.json), `plugin.yaml` written (5 hook attributes, `session_context`, parent `tcp`
without `classify`), `src/ocip_impl.c` written, `tests/ocip-basic.yaml` (init's placeholder, this session) deleted, tests
written by `inputs/make_tests.py`.

Checks that the tests bite (not kept as tests):
- a copy of `session-split-doctype.yaml` with one expected value flipped: exit 6, `test.packet-failed` (`is_request: expected 0, got 1`).
- a copy of the project whose scan keeps no tail between segments: exit 6, `session-split-doctype` and
  `session-utf16-split` fail (`has_dtd: expected 1, got 0`).
