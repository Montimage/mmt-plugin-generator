# Run 2

- validate, generate, build: exit 0 (hook `telem_hook_extract_readings` added, returns 0 = absent; see questions.md Q2).
- test: exit 3, `model.bad-packet-test` at tests/telem-ack.yaml (my own test, written this session): absent attribute `payload` lacked `type`.
- Fix: add `type: MMT_BINARY_DATA` to the absent payload entry.
