Run 7 (#137), after the fix: green, `test --sanitize`: `{total: 32, passed: 32, failed: 0}`; sanitize: 32240
packets, 0 crashes.

`src/ocip_impl.c`: each direction records its latest hole (`struct ox_hole`): where it ends, its length (unknown
before the direction's first segment), the 17 bytes before it and the first 17 bytes after it. A segment with no new
bytes that falls in the hole is searched across its edges (the bytes before it when it starts where the hole starts,
the bytes after it when it ends where the hole ends), a match counted only when it has a byte of the late segment.
The hole is not consumed, so a filler sent into it first hides nothing. Run 6 is the failing run of the same tests.
