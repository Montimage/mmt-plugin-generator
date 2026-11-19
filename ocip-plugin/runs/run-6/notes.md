Run 6 (#137), before the fix: the four reordered session tests written from the wire format
(`inputs/make_tests.py`, new session key `back`). Exit 6, 29/32: `has_dtd` is 0 on the late segment that
completes a split `<!DOCTYPE` in `session-reordered-split-doctype` (packet 2), `session-reordered-filler`
(packets 5 and 6, after a filler over the hole) and `session-reordered-short-middle` (packet 4, a 2-byte
late segment between both halves). `session-reordered-whole-doctype` passes (no second report).

Before this recorded run, two expectations of the new tests were corrected against the documented behaviour (a
first try of run 6, not kept): the segment that arrives first after a hole starts a new message, so it reports
`session_id` and `command_type` (`session-reordered-short-middle`, packet 3), and `dtd` keeps 63 bytes
(`session-reordered-whole-doctype`, packet 1).
