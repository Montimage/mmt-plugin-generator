# Run 3

Green, `test --sanitize`: `{total: 28, passed: 28, failed: 0}`; sanitize: 28209 packets, 0 crashes.

Changes before this run (after the review of run 2, not a failing envelope):
- `src/ocip_impl.c`, `ox_session_packet`: a segment with no new bytes (a retransmission, or an earlier segment that
  arrives late) was reporting nothing, so a client that sends the half holding a whole `<!DOCTYPE ...>` after the
  other half evaded `has_dtd`, while the old per-packet rule fired (verified: `attack_v10_reordered.pcap`, old rule 1
  alert, new rule 0). Now such a segment is searched alone (no tail, no tokenizer, no state change) and reports
  `has_dtd` and `is_request`.
- tests: `session-second-message.yaml`'s retransmit step now expects `has_dtd` 1 and `is_request` 1 (the decision
  changed, `request.md`); new `session-long-split-doctype.yaml`: 25 benign request/reply pairs (past mmt-dpi's 40
  classification packets, so the session data hooks run), then V7's split DOCTYPE with `idle: 70` between its halves
  (126 packets with the idle traffic).
