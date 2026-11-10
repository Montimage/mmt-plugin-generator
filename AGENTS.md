# Agent instructions

MMT plugin generator: generates mmt-dpi protocol plugin sources (C) from a
protocol model. A Python rewrite is planned in
`docs/design/workflow-redesign.md`; what exists today is below.

## What exists today

- `src/`, `lib/`, `dist/`, `pdl_grammar/`, `nbproject/`, `build.xml`,
  `manifest.mf`: the legacy Java generator (2015, NetBeans Ant project).
  The prebuilt jar is `dist/MMTPluginGenerator.jar`.
- `plugins/`: the 16 example models (`plugins/*_plugin`) and generated or
  hand-written C sources (`*_src/`, `cotp/`, `tpkt/`, ...). Only 4 of the
  16 models (abb, cotp, s7com, tpkt) produce code that compiles against
  mmt-dpi 1.10.2.
- `ndn_src/`: the NDN example plugin, kept building against mmt-dpi 1.10.2.
- `tests/check_ndn_plugin.sh`: the only automated check (build and load the
  NDN example).
- `tests/fetch_mmt_dpi_package.sh`: downloads a published mmt-dpi package
  from its GitHub Release and verifies it (pinned `SHA256SUMS` hash, then
  `SHA256SUMS` and `manifest.json`); it never installs.
- `.github/workflows/ci.yml`: CI on PRs to `dev`/`main` and pushes to `dev`.
  Runs shellcheck on every tracked `*.sh`, and `check_ndn_plugin.sh` against
  the mmt-dpi v1.10.2 ubuntu-24.04 `.deb` (amd64 and arm64).

## Commands

Generate C sources from a model with the legacy tool (needs Java):

```
java -jar dist/MMTPluginGenerator.jar plugins/tpkt_plugin <output dir>
```

Create the output dir first: if it is missing, the tool prints
`Error in writing to file` and still exits 0.

Build and check the NDN example. It needs mmt-dpi >= 1.10.2 installed into a
private prefix (see README, "Install mmt-dpi"); pass that prefix as an
absolute path:

```
MMT_BASE=<private prefix> bash tests/check_ndn_plugin.sh
```

A private prefix can also come from the published package, without root.
The package's `libmmt_*.so` links point to absolute `/opt/mmt/...` paths, so
make them relative before linking against the prefix (`<dir>` absolute):

```
deb="$(bash tests/fetch_mmt_dpi_package.sh <download dir>)"
dpkg-deb -x "$deb" <dir>
for l in <dir>/opt/mmt/dpi/lib/*.so; do ln -sfn "$(basename "$(readlink "$l")")" "$l"; done
MMT_BASE=<dir>/opt/mmt bash tests/check_ndn_plugin.sh
```

It prints one `PASS:`/`FAIL:` line per check and exits non-zero on failure.
Always set `MMT_BASE`: the script defaults to `/opt/mmt`.

## Rules

- Never use `sudo`, and never write to `/opt/mmt`. Install mmt-dpi and
  plugins into a private prefix only.
- Branches: all plan work happens on `dev`. Fork issue branches from
  `origin/dev` and open PRs against `dev`, never `main`. `main` only receives
  `dev` through a release PR approved by the maintainer. Never force-push.
- PRs into `dev` need an independent review PASS and green CI, and are
  squash-merged with a hand-written message.
- Commits and PR bodies carry no AI co-author trailers (`Co-Authored-By: ...`)
  and no "Generated with ..." footers.
- Line endings: keep each file's existing ones. `README.md` uses CRLF; check
  with `cat -A <file>` (CRLF lines end in `^M$`) before and after editing.
