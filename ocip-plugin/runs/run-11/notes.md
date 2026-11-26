Run 11 (#140), before the fix: four session tests written from the wire format (`inputs/make_tests.py`). Exit 6,
35/38: `has_dtd` is 0 on the segment sent over an in-order filler (one the server drops, a bad checksum, but the
probe keeps) in `session-inorder-filler-split-doctype` (packet 3: `...<!DOC`, the filler `xxxx`, then `TYPE` with
`back: 4`), `session-inorder-filler-overlap` (packet 3: the whole `TYPE ...` at the filler's sequence number, longer
than it) and `session-inorder-filler-whole-doctype` (packet 3: a whole `<!DOCTYPE` over a 16-byte filler). Every
other expectation of those tests passes, and the control, `session-overlap-control` (a benign retransmission, then
a segment that repeats an XXE and adds a benign message, both `has_dtd` 0), passes too.

Run in the `mmt-plugin-generator-toolchain:local` container (the repository's `Dockerfile`, with uv 0.12.10 added)
with the checkout at `/src` and `/sdk/mmt` the image's mmt-dpi 1.10.2.
