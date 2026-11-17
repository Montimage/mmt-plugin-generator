Run 8 (#137): the final source (run 7 plus comments in `src/ocip_impl.c`), the `.so` the capture evaluation and
`manifest.json` record. Green, `test --sanitize`: `{total: 32, passed: 32, failed: 0}`; sanitize: 32240 packets,
0 crashes. Also green with clang (`tests/unit/ocip/test_sdk.py`, `MMT_GOLDEN_CC=clang`, with `libclang-rt-18-dev`
added to the container for the sanitizer runtime). Capture evaluation: PASS, 23/23, no drift, the same frames and
values as before #137 (the capture has no reordered segment).
