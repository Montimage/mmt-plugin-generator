# Agent instructions

MMT plugin generator: generates mmt-dpi protocol plugin sources (C) from a
protocol model. A Python rewrite is planned in
`docs/design/workflow-redesign.md`; what exists today is below.

## What exists today

- `legacy/`: the legacy Java generator (2015, NetBeans Ant project), frozen
  by T0.5: `src/`, `lib/`, `dist/`, `pdl_grammar/`, `nbproject/`,
  `build.xml`, `manifest.mf`. The prebuilt jar is
  `legacy/dist/MMTPluginGenerator.jar`. `legacy/reference-output/` holds its
  output for every `plugins/*_plugin` model (exit code, stdout and stderr
  included) and a `MANIFEST` with the jar's sha256; CI regenerates it with
  `legacy/check-reference-output.sh`. `docs/legacy/java-generator-inventory.md`
  describes the tool's behaviour.
- `plugins/`: the 16 example models (`plugins/*_plugin`) and generated or
  hand-written C sources (`*_src/`, `cotp/`, `tpkt/`, ...). Only 4 of the
  16 models (abb, cotp, s7com, tpkt) produce code that compiles against
  mmt-dpi 1.10.2.
- `ndn_src/`: the NDN example plugin, kept building against mmt-dpi 1.10.2.
- `tests/check_ndn_plugin.sh`: builds and loads the NDN example.
- `tests/corpus/`: the test corpus (T0.4): every `plugins/` model plus
  targeted per-construct models, each with packet fixtures whose expected
  values come from the protocol specs. `tests/corpus/README.md` defines the
  format and the extraction rules; `tests/corpus/validate.py` checks it.
- `tests/fetch_mmt_dpi_package.sh`: downloads a published mmt-dpi package
  from its GitHub Release and verifies it (pinned `SHA256SUMS` hash, then
  `SHA256SUMS` and `manifest.json`); it never installs.
- `pyproject.toml`, `uv.lock`, `python/`: the Python rewrite (T1.1 onwards).
  The package `mmt_plugin` is in `python/src/mmt_plugin/` (uv_build
  `module-root = "python/src"`, since `src/` is still the Java tool) and its
  unit tests in `python/tests/`. The `mmt-plugin` CLI only has `--help` and
  `--version` so far; exit codes are in `python/src/mmt_plugin/cli.py`.
- `.github/workflows/ci.yml`: CI on PRs to `dev`/`main` and pushes to `dev`.
  Runs shellcheck on every tracked `*.sh`, the corpus validator, and
  `check_ndn_plugin.sh` against the mmt-dpi v1.10.2 ubuntu-24.04 `.deb`
  (amd64 and arm64), and the Python checks below (Python 3.10 and 3.12).

## Commands

Generate C sources from a model with the legacy tool (needs Java):

```
java -jar legacy/dist/MMTPluginGenerator.jar plugins/tpkt_plugin <output dir>
```

Create the output dir first: if it is missing, the tool prints
`Error in writing to file` and still exits 0.

Check that the jar still reproduces `legacy/reference-output/` byte for byte
(needs a Java 8 runtime; set `JAVA` to pick one). It exits non-zero on any
difference; `--write` regenerates the reference instead:

```
bash legacy/check-reference-output.sh
```

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

Check the test corpus (Python 3.8+, no dependencies). Run it after any change
under `tests/corpus/` or to a `plugins/*_plugin` model, since the corpus holds
byte-identical copies of those models:

```
python3 tests/corpus/validate.py
```

Python package (needs [uv](https://docs.astral.sh/uv/); CI pins uv 0.12.10).
Python >= 3.10; `.python-version` picks 3.12 locally, as in the build
container. Run these checks before pushing a change under `python/` or to
`pyproject.toml`; after a dependency change, commit the updated `uv.lock`:

```
uv sync
uv run ruff check
uv run ruff format --check
uv run mypy
uv run pytest
uv run mmt-plugin --version
```

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
