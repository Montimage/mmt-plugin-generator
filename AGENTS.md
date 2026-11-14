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
- `Dockerfile`, `Makefile`: the pinned build and test container (T0.3):
  ubuntu:24.04 by digest, gcc, clang, Python 3.12 and the verified mmt-dpi
  v1.10.2 `.deb`. `make test-container` builds it and runs the NDN check.
- `pyproject.toml`, `uv.lock`, `src/`, `tests/unit/`: the Python rewrite
  (T1.1 onwards). The package `mmt_plugin` is in `src/mmt_plugin/` (uv_build's
  default layout) and its unit tests in `tests/unit/`. The `mmt-plugin` CLI
  has the contract core of `docs/design/cli.md` (exit codes in
  `exitcodes.py`, diagnostic codes in `diagnostics.py`, the `--json`
  envelope and its schema) and two commands, `generate` (T1.5) and
  `completion {bash,zsh,fish}` (T2.6); each other command registers itself
  in `src/mmt_plugin/commands/` with its own issue, declaring its
  `exit_codes` and shipping its `result` schema as
  `src/mmt_plugin/schemas/cli/v1/<command>.json`. Styled (btop)
  output goes through `src/mmt_plugin/ui/style.py`: a command returns a
  `view` in its `Outcome`. `tests/unit/test_contract.py` checks every
  registered command's `--json` envelope, `result` schema and `--help` exit
  codes; `tests/unit/test_style.py` holds the cli-builder style tests.
- `src/mmt_plugin/pdl/` (T1.2): the PDL v1 lexer and parser.
  `parse(text, filename=...)` returns a typed model (`pdl/model.py`) or
  raises `PdlSyntaxError` with `model.syntax.*` diagnostics. It checks syntax
  only; names, layouts and values are T1.3. Its tests are in
  `tests/unit/pdl/`, with golden model dumps in `tests/unit/pdl/golden/`
  (regenerate with `MMT_UPDATE_GOLDEN=1 uv run pytest tests/unit/pdl`).
- `src/mmt_plugin/sdk/`: the SDK profiles (T1.4), one JSON file per mmt-dpi
  version in `sdk/profiles/` (only 1.10.2 so far; schema in
  `schemas/sdk/v1/profile.json`), SDK prefix detection and profile choice.
  Plain functions for the commands to call; no command of its own.
- `src/mmt_plugin/semantics/` (T1.3): the semantic passes.
  `analyse(model, profile=...)` returns the analysed model
  (`semantics/model.py`: types, offsets, bitfields, folded expressions,
  resolved references, defaults) and `model.*` diagnostics; no file I/O.
  The model is `None` on any error, including an id or name the SDK already
  takes; `allow_sdk_conflicts=True` still returns it with those two errors
  (T1.6). Tests in `tests/unit/semantics/`, including the layout of every
  corpus fixture.
- `src/mmt_plugin/codegen/` (T1.5): `generate(analysed, profile)` renders the
  Jinja2 templates `codegen/templates/plugin.{h,c}.j2` (the package's only
  run-time dependency) into the plugin header and source, in memory; every
  SDK name comes from the profile. `mmt-plugin generate`
  (`commands/generate.py`) writes them and `plugin.lock` (`lock.py`, schema
  `schemas/lock/v1/plugin-lock.json`). Tests in `tests/unit/generate/`, with
  golden C for every corpus model the semantics accept in
  `tests/unit/generate/golden/` (regenerate with
  `MMT_UPDATE_GOLDEN=1 uv run pytest tests/unit/generate`).
- `.github/workflows/ci.yml`: CI on PRs to `dev`/`main` and pushes to `dev`.
  Runs shellcheck on every tracked `*.sh`, the corpus validator,
  `check_ndn_plugin.sh` against the mmt-dpi v1.10.2 ubuntu-24.04 `.deb`
  (amd64 and arm64), `make test-container` on both arches, the Python
  checks below (Python 3.10, 3.12 and 3.14; the 3.12 job installs zsh and
  fish and sets `MMT_REQUIRE_SHELLS=1`, so their completion tests fail
  instead of skipping), and the SDK profile header check (amd64 and arm64),
  which also compiles the golden generated C with gcc and clang.

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

Or run the same check in the pinned container (docker, or
`CONTAINER=podman`); it needs no mmt-dpi on the host and no root:

```
make test-container
```

Check the test corpus (Python 3.8+, no dependencies). Run it after any change
under `tests/corpus/` or to a `plugins/*_plugin` model, since the corpus holds
byte-identical copies of those models:

```
python3 tests/corpus/validate.py
```

Python package (needs [uv](https://docs.astral.sh/uv/); CI pins uv 0.12.10).
Python >= 3.10; `.python-version` picks 3.12 locally, as in the build
container. Run these checks before pushing a change under `src/`,
`tests/unit/` or to `pyproject.toml`; after a dependency change, commit the
updated `uv.lock`:

```
uv sync
uv run ruff check
uv run ruff format --check
uv run mypy
uv run pytest
uv run mmt-plugin --version
```

Check the bundled SDK profile against real mmt-dpi headers (needs gcc or
clang; `<dir>` is the extracted package of "A private prefix can also come
from the published package"). It prints one `PASS:`/`FAIL:` line per check
and exits non-zero on failure:

```
uv run python -m mmt_plugin.sdk.headercheck --sdk <dir>/opt/mmt --cc gcc
```

Check that it fails on broken scratch copies of those headers (an
unprototyped declaration, a wrong `Max_Alias_Len`); same output and exit:

```
bash tests/check_headercheck_mutations.sh <dir>/opt/mmt gcc
```

Compile every golden generated pair (and a stub `src/<label>_impl.c`) against
those headers, `-fsyntax-only -std=gnu11 -Wall -Wextra -Werror`; without
`MMT_GOLDEN_SDK` the test skips:

```
MMT_GOLDEN_SDK=<dir>/opt/mmt MMT_GOLDEN_CC=gcc uv run pytest tests/unit/generate/test_compile.py
```

Generate a model's C sources (no installed SDK needed with a pinned profile):

```
uv run mmt-plugin generate tests/corpus/models/pdl_bitfields/model.pdl -o <dir> --sdk-profile 1.10.2
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
