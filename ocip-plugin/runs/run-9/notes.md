Run 9 (#137, review): a `<!DOCTYPE` split between two late segments, each touching an edge of the hole, is missed
(V7 cut in three at '<!DOC' and 'TYPE', sent in reverse order: a late segment is searched with the hole's recorded
edges, never with another late one). Pinned, not fixed, as #137 allows: `session-reordered-two-late-halves` expects
`has_dtd` 0 on both late segments, and `REPORT.md` and the header of `src/ocip_impl.c` give the limit. Green,
`test --sanitize`: `{total: 33, passed: 33, failed: 0}`; sanitize: 33248 packets, 0 crashes.

Run in a clone of the commit at `/work` (`loop.sh` with `/src` read as `/work`), so the paths and the `.so` hash in
`build.json` differ from run 8's. The source changes only in comments: the `.so` built there from run 8's source and
from this one are the same bytes, so the `.so` the capture evaluation and `manifest.json` record is unchanged.
