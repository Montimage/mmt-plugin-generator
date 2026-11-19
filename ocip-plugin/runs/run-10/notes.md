Run 10 (#137, review): a late segment is searched once, with the hole's edges as they stand when it arrives, so a
`<!DOCTYPE` that needs bytes after the hole that arrive later is missed (V7's `...<!DOC`, then `Y` after a 1-byte
hole, then the late `T`, then `PE ...` in order: when `T` arrives the bytes after the hole are only `Y`, and nothing
searches `T` again). Pinned, not fixed, as #137 allows: `session-reordered-short-after-edge` expects `has_dtd` 0 on
every packet, and `REPORT.md` and the header of `src/ocip_impl.c` give the limit. Green, `test --sanitize`:
`{total: 34, passed: 34, failed: 0}`; sanitize: 34256 packets, 0 crashes.

Run, as run 9, in a clone of the commit at `/work` (`loop.sh` with `/src` read as `/work`). The source changes only in
comments: the `.so` built there from run 9's source and from this one are the same bytes, so the `.so` the capture
evaluation and `manifest.json` record is unchanged.
