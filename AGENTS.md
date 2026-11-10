# Agent instructions

MMT plugin generator: generates mmt-dpi protocol plugin sources (C) from a
protocol model. A Python rewrite is planned in
`docs/design/workflow-redesign.md`; what exists today is below.

## What exists today

- `src/`, `lib/`, `dist/`, `pdl_grammar/`, `nbproject/`, `build.xml`,
  `manifest.mf`: the legacy Java generator (2015, NetBeans Ant project).
  The prebuilt jar is `dist/MMTPluginGenerator.jar`.
- `plugins/`: example models (`*_plugin`, `cotp`, `tpkt`, ...) and generated
  or hand-written C sources. Only 4 of the 16 models (abb, cotp, s7com,
  tpkt) produce code that compiles against mmt-dpi 1.10.2.
- `ndn_src/`: the NDN example plugin, kept building against mmt-dpi 1.10.2.
- `tests/check_ndn_plugin.sh`: the only automated check (build and load the
  NDN example).

## Commands

Generate C sources from a model with the legacy tool (needs Java):

```
java -jar dist/MMTPluginGenerator.jar plugins/tpkt_plugin <output dir>
```

Build and check the NDN example. It needs mmt-dpi >= 1.10.2 installed into a
private prefix (see README, "Install mmt-dpi"); pass that prefix as an
absolute path:

```
MMT_BASE=<private prefix> bash tests/check_ndn_plugin.sh
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
