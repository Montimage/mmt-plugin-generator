# mmt-plugin user guide

`mmt-plugin` turns a protocol model, `plugin.yaml`, into an
[mmt-dpi](https://github.com/Montimage/mmt-dpi) protocol plugin: it
generates the C sources, builds `mmtp_<label>.so` against an installed
mmt-dpi, tests it on packets whose expected values you write down, and
installs it where mmt-dpi loads plugins. This guide walks through a project
from `init` to `install`, then covers the other commands and the
machine-readable output.

- [Install mmt-plugin](#install-mmt-plugin)
- [Get mmt-dpi](#get-mmt-dpi)
- [Create a project](#create-a-project)
- [Write the model](#write-the-model)
- [Validate and generate](#validate-and-generate)
- [Your code: the hooks](#your-code-the-hooks)
- [Build](#build)
- [Packet tests](#packet-tests)
- [Install the plugin](#install-the-plugin)
- [Draft a model from a capture](#draft-a-model-from-a-capture)
- [Start from a PDL v1 model](#start-from-a-pdl-v1-model)
- [Shell completion](#shell-completion)
- [Scripts, CI and agents: `--json`](#scripts-ci-and-agents---json)
- [Settings and where they come from](#settings-and-where-they-come-from)
- [The example projects](#the-example-projects)

The commands below run from the root of a checkout of this repository: some
use its files (`examples/`, `tests/corpus/`, a sample capture). CI runs every one
of them (`tests/unit/docs/test_commands.py`) except the blocks marked
`doc:skip`: they need the network to clone the repository or download
mmt-dpi (CI's own SDK jobs fetch and verify the package with the same
script, `tests/fetch_mmt_dpi_package.sh`), or a published release.

## Install mmt-plugin

`mmt-plugin` is not published yet: there is no PyPI package and no release
(the first release is plan task T5.5, #32). Until then, install it from a
checkout of this repository. It needs Python 3.10 or later and Linux (amd64
or arm64); building and testing plugins also need gcc or clang.

<!-- doc:skip needs the network -->
```sh
git clone https://github.com/Montimage/mmt-plugin-generator.git
cd mmt-plugin-generator
```

With [uv](https://docs.astral.sh/uv/), install the checkout as a tool, which
puts `mmt-plugin` on your `PATH` (`pipx install .` does the same with pipx):

<!-- doc:run install -->
```sh
uv tool install .
mmt-plugin --version
```

Or build a wheel and install that, for example on another machine:

<!-- doc:run install -->
```sh
uv build --wheel --out-dir dist
uv tool install --reinstall dist/mmt_plugin-*-py3-none-any.whl
mmt-plugin --version
```

Inside the checkout, `uv run mmt-plugin ...` runs the checkout's code
without installing it (that is how `AGENTS.md` runs it).

### From a release

Once a release is published ([`docs/releasing.md`](releasing.md)), each
GitHub release of this repository carries the wheel, the sdist, the JSON
Schemas of the `--json` output and of `plugin.yaml`
(`mmt-plugin-schemas-<version>.tar.gz`), a `SHA256SUMS` and a provenance
attestation. Install the wheel straight from the release, or from PyPI
when the release is also published there:

<!-- doc:skip needs a published release -->
```sh
uv tool install https://github.com/Montimage/mmt-plugin-generator/releases/download/v0.1.0/mmt_plugin-0.1.0-py3-none-any.whl
uv tool install mmt-plugin
mmt-plugin --version
```

`0.1.0` stands for the release's version. To check a downloaded asset,
`sha256sum -c SHA256SUMS`, then
`gh attestation verify <file> --repo Montimage/mmt-plugin-generator`.

The release also publishes a container image with mmt-plugin, gcc, clang
and mmt-dpi v1.10.2 in `/opt/mmt`, for amd64 and arm64. Run it on a
project directory as your uid:

<!-- doc:skip needs a published release and docker -->
```sh
docker run --rm --user "$(id -u):$(id -g)" -v "$PWD:/work" -w /work \
    ghcr.io/montimage/mmt-plugin:0.1.0 mmt-plugin -C demo test
```

## Get mmt-dpi

`generate` and `validate --no-sdk` need no SDK: the generator knows each
supported mmt-dpi version from a bundled *SDK profile* (only 1.10.2 so far).
`build`, `test`, `install` and `doctor` need mmt-dpi 1.10.2 or later
installed: its headers, `libmmt_core` and its plugins (`libmmt_tcpip.so`).

Install it into a private prefix, without root: either build it from an
mmt-dpi checkout (the [README](../README.md#install-mmt-dpi) has the
commands), or extract the published `.deb`. `tests/fetch_mmt_dpi_package.sh`
downloads the ubuntu-24.04 package and checks its hashes; the package's
library links point to `/opt/mmt`, so make them relative:

<!-- doc:skip needs the network -->
```sh
deb="$(bash tests/fetch_mmt_dpi_package.sh "$HOME/mmt-download")"
dpkg-deb -x "$deb" "$HOME/mmt"
for l in "$HOME"/mmt/opt/mmt/dpi/lib/*.so; do ln -sfn "$(basename "$(readlink "$l")")" "$l"; done
export MMT_BASE="$HOME/mmt/opt/mmt"
```

`mmt-plugin` finds the SDK from `--sdk PREFIX`, else `MMT_BASE`, else an
`mmt-dpi.pc` on pkg-config's search path, else `/opt/mmt`. The prefix must be
absolute and hold `dpi/include/mmt_log.h`. Below, `MMT_BASE` is set, and so
is `CC` when you want clang (gcc is the default).

## Create a project

`init` creates a project directory that builds and tests green: a model, the
file for your C code and one packet test.

<!-- doc:run no-sdk -->
```sh
mmt-plugin init demo --id 960 --parent udp:dport=4433 --sdk-profile 1.10.2
```

- `demo/plugin.yaml`: the model, every command's default, of a 4-byte
  header (`version`, `kind`, `length`);
- `demo/src/demo_impl.c`: your code, one function per hook;
- `demo/tests/demo-basic.yaml`: a packet test of that header;
- `demo/.gitignore`: `build/`.

The label (`demo`) names the plugin, `mmtp_demo.so`, and the registered
protocol name, `DEMO` (always the label upper-cased: `--name` accepts no
other). Third-party plugins use ids 950 to 999; with an SDK, `init` picks
the lowest free one when you leave out `--id`. Re-running `init` changes
nothing; it never replaces a file with other content unless you pass
`--force`. A project that an older `init` created, with a PDL v1
`model.pdl` and no `plugin.yaml`, is never written into, even with
`--force`: convert it with `mmt-plugin -C <dir> import <dir>/model.pdl`.

## Write the model

`init` wrote `demo/plugin.yaml`. It pins the SDK profile the scaffold is
written for, and declares the parent: `--parent udp:dport=4433` became a
`classify` that attaches the protocol to UDP destination port 4433 in
generated code. A parent that one match of its header identifies (an
EtherType, a UDP source or destination port) gets one; any other
(`tcp:port=102`, or `udp:port=4433`, which matches either port) is listed
without `classify`, for your code to attach:

```yaml
# The DEMO protocol plugin's model, created by mmt-plugin init. Every
# mmt-plugin command of the project reads it (docs/plugin-yaml.md): describe
# the protocol here, and keep the label and the id, which src/ is written for.
schema: 1
protocol:
  label: "demo"
  id: 960
  encoding: network    # big-endian integers
sdk:
  profile: "1.10.2"
parents:
  - protocol: udp    # udp:dport=4433
    classify:
      match:
        - {offset: 2, length: 2, value: 4433}
      offset: 8
attributes:
  - struct: demo_hdr    # at offset 0
    fields:
      - name: version
        type: uint8_t
      - name: kind
        type: uint8_t
      - name: length
        type: uint16_t
```

Edit it to describe your protocol. `-C demo` makes `demo` the project
directory, whose `plugin.yaml` every command reads; paths given as
arguments stay relative to where you run the command.

What goes in a model:

- `protocol`: the label, the id, the byte order, and the flags that add
  hooks (`context`, `session_context`, `session`, `encapsulation`);
- `attributes`: attributes at fixed or computed offsets, structs of packed
  fields and bitfields, and `if`/`then`/`else` blocks; an attribute without
  an `offset` is extracted by a hook;
- `classify_next`: which protocol comes next, and where;
- `parents`: what this protocol runs on. A parent with `classify` (a fixed
  header such as Ethernet or UDP) is attached by the generated code; one
  without is attached by your code;
- `sdk.profile`: the profile to generate for.

[`plugin-yaml.md`](plugin-yaml.md) explains the format with a complete
example (expressions, offsets, the YAML subset it accepts), and the
[model reference](model-reference.md), generated from the JSON Schema, lists
every key. A model error is reported at its line and column, with a code
such as `model.schema` or `model.duplicate-name` and a hint.

## Validate and generate

`validate` checks the model and reports each check as `pass`, `warn`,
`fail` or `skip`. Without an SDK, `--no-sdk` skips the checks that need one:

<!-- doc:run no-sdk -->
```sh
mmt-plugin -C demo validate --no-sdk
```

With an SDK it also checks that the id and the name are free, both in the
SDK and among the plugins installed next to it, that the parents exist and
that the plugin file loads after `libmmt_tcpip.so`:

<!-- doc:run sdk -->
```sh
mmt-plugin -C demo validate
```

`generate` writes `generated/demo_mmt_plugin.h` and `.c`, and `plugin.lock`,
which records their hashes, the tool version and the profile. Commit all
three. Re-running it on an unchanged model writes nothing, and
`generate --check` (exit 7 when something would change) is a CI check that
the committed files are current:

<!-- doc:run no-sdk -->
```sh
mmt-plugin -C demo generate
mmt-plugin -C demo generate --check
```

Never edit `generated/`: `generate` refuses to overwrite a generated file
that changed since it wrote it (exit 7) unless you pass `--force`.

## Your code: the hooks

`generate` never writes under `src/`. The generated header declares a hook
for each thing the model leaves to you, and `src/<label>_impl.c` defines
them: `init` writes it once, with every hook of the model it created. When a
model change adds a hook (an attribute without `offset`, `context: true`,
`encapsulation` without `classify_next`, ...), `build` fails with
`build.missing-hook` until you define it; its declaration is in the
generated header.

Every project has `<label>_hook_register_parents`, which the generated init
calls after attaching the parents that have `classify`. Attach the others
there (a parent whose header has a variable length, such as TCP or IPv4),
and return 0 when a registration fails, so that mmt-dpi refuses to load the
plugin instead of loading one that classifies nothing. The comment in the
scaffold shows how; `examples/tcp/` does it.

## Build

`build` compiles `build/mmtp_demo.so` from `generated/` and every
`src/*.c`, with fixed flags (`-Wall -Wextra -Werror`, hardening, and
`-Wl,-z,defs` against `libmmt_core`). It regenerates first when the
generated files are stale, and an unchanged build is a no-op (`--rebuild`
forces one). `--dry-run` prints the compiler commands:

<!-- doc:run sdk -->
```sh
mmt-plugin -C demo build --dry-run
mmt-plugin -C demo build
```

Compiler errors are reported at their file, line and column (code
`build.cc`, exit 5).

## Packet tests

A packet test is a YAML file in `tests/`: the packet's bytes (the bytes of
this protocol, from its first byte), then what the plugin must report, the
protocol, the next protocol and each attribute's value:

```yaml
schema: 1
id: "demo/basic"
summary: "One DEMO header: version 1, kind 2, length 4"
through: "udp:dport=4433"
bytes:
  - "01 02 00 04"
expect:
  protocol: "DEMO"
  proto_id: 960
  next:
    kind: "none"
  attributes:
    - name: "version"
      type: "MMT_U8_DATA"
      offset: 0
      length: 1
      value: 1
    - name: "kind"
      type: "MMT_U8_DATA"
      offset: 1
      length: 1
      value: 2
    - name: "length"
      type: "MMT_U16_DATA"
      offset: 2
      length: 2
      value: 4
```

Take the expected values from the protocol's specification, not from what
the plugin prints. The format is the test corpus's,
[`tests/corpus/README.md`](../tests/corpus/README.md#packet-files). `init`
wrote `demo/tests/demo-basic.yaml` for the model above with the id given to
`init`, so it passes as it is; it has `through` (below) because the
parent has a `classify`.

`test` builds the plugin when it is stale, loads it into a generated host
program next to the SDK's `libmmt_tcpip.so`, feeds it each packet and
compares. A failure names the attribute with its expected and actual value
(`test.packet-failed`, exit 6). `--sanitize` rebuilds with AddressSanitizer
and UndefinedBehaviorSanitizer and also runs truncated and random packets
(`--seed` and `--fuzz-count` make them reproducible); `--bench` reports
packets per second against an empty plugin and never fails:

<!-- doc:run sdk -->
```sh
mmt-plugin -C demo test
mmt-plugin -C demo test --sanitize --seed 42 --fuzz-count 200
mmt-plugin -C demo test --bench
```

For each packet test, `test` attaches the plugin to Ethernet itself
(EtherType 0x88b5), so the packets need no parent headers and the parent
classification does not run;
it is registered when the plugin loads, so a registration that fails fails
the test.

To test the parent classification too, give a packet test `through`, a
selector with `init --parent`'s syntax: `ethernet:ethertype=N`,
`ip:proto=N`, `ipv6:proto=N`, or `udp`/`tcp` with `dport` (or `port`) and
`sport`. The test then also runs as a whole frame: `test` puts the
Ethernet, IPv4 (or IPv6) and UDP or TCP headers it names in front of the
bytes and hands the frame to mmt-dpi's own stack, so your plugin must
classify it, directly above that protocol, at the offset those headers end
at (the `<parent>` failure), with the same attribute values:

```yaml
through: "udp:dport=4433"   # Ethernet, IPv4, UDP to port 4433, then bytes
bytes:
  - "01 02 00 04"
```

`init` writes it into its packet test when its parent has a `classify`,
so `test` checks the generated classification from the start. That run is
a second entry in `result.packets`, with `through`. It does
not check `next`: mmt-dpi 1.10.2 does not classify past a protocol a plugin
attached under its TCP or UDP. With `--sanitize`, its random packets run
behind the same headers.

## Install the plugin

`install` copies `mmtp_demo.so` into `<prefix>/plugins/` and records it in
the manifest `<prefix>/plugins/.mmt-plugin/demo.json`, which `uninstall`
follows; it builds first when the plugin is stale. The prefix is `--prefix`,
else `MMT_PLUGIN_PREFIX`, else `${XDG_DATA_HOME:-~/.local/share}/mmt`.
`--system` means `/opt/mmt`; `mmt-plugin` never runs `sudo`, and a prefix it
cannot write is exit 4.

mmt-dpi 1.10.2 loads the plugins of one directory: `MMT_DPI_PLUGINS_DIR`,
else the one compiled into `libmmt_core` (`/opt/mmt/plugins` in the
package). To use a private plugin directory, point `MMT_DPI_PLUGINS_DIR` at
it and put the SDK's own plugins there too, since it replaces the default
one. `doctor` reports the plugin directory mmt-dpi scans and whether it is
the install prefix's, the load order, and id or name clashes:

<!-- doc:run sdk -->
```sh
mmt-plugin -C demo install --prefix "$PWD/plugins-prefix" --dry-run
mmt-plugin -C demo install --prefix "$PWD/plugins-prefix"
ln -sf "$MMT_BASE"/plugins/*.so "$PWD/plugins-prefix/plugins/"
MMT_DPI_PLUGINS_DIR="$PWD/plugins-prefix/plugins" mmt-plugin -C demo doctor --prefix "$PWD/plugins-prefix"
mmt-plugin -C demo uninstall --prefix "$PWD/plugins-prefix"
```

Installing the same file again changes nothing. `install` refuses (exit 7)
to replace a file that no manifest lists or that changed since it was
installed, unless you pass `--force`, and refuses a plugin whose id or name
another installed plugin has (exit 3). `uninstall` removes only the files
whose hash is still the one it recorded.

## Draft a model from a capture

`scaffold --from-pcap` reads a pcap or pcapng capture, takes the payloads
under a parent (`ethernet:ethertype=`, `ip:proto=`, `ipv6:proto=`,
`udp:port=`, `udp:sport=`, `udp:dport=`, the same for `tcp`), and writes
one packet test per payload (`tests/<label>-pcap-<n>.yaml`, at most
`--max-packets`) and a proposed model, `plugin.proposed.yaml`: the fields
that every payload has, named `field_<offset>` (a length field is named
`length`), with a comment saying what it saw. It never edits `plugin.yaml`.

<!-- doc:run no-sdk -->
```sh
mmt-plugin init capture --id 961 --parent udp:dport=4433 --sdk-profile 1.10.2
mmt-plugin -C capture scaffold --from-pcap tests/unit/scaffold/data/demo-tcpdump.pcap --parent udp:dport=4433
```

The packet tests expect what the proposal extracts, so they pass against it.
Rename the fields after the protocol's specification (in the model and in
the tests), and copy what you keep into `plugin.yaml`. Here the proposal is
taken as it is, in place of `init`'s sample model, and `init`'s test, which
describes another header, is removed:

<!-- doc:run no-sdk -->
```sh
cp capture/plugin.proposed.yaml capture/plugin.yaml
rm capture/tests/capture-basic.yaml
mmt-plugin -C capture validate --no-sdk --sdk-profile 1.10.2
```

<!-- doc:run sdk -->
```sh
mmt-plugin -C capture test
```

## Start from a PDL v1 model

`import` converts a model of the Java tool to `plugin.yaml`. The
[migration guide](migration.md) covers it, and what changed from the Java
tool.

## Shell completion

`completion` prints a completion script for bash, zsh or fish, generated
from the command's parser; loading it never runs `mmt-plugin`:

<!-- doc:run no-sdk -->
```sh
mkdir -p ~/.local/share/bash-completion/completions
mmt-plugin completion bash > ~/.local/share/bash-completion/completions/mmt-plugin
```

For zsh, write `_mmt-plugin` into a directory of your `fpath` (before
`compinit`); for fish, write `~/.config/fish/completions/mmt-plugin.fish`.
`mmt-plugin completion --help` shows the three lines.

## Scripts, CI and agents: `--json`

Every command takes the global options `-C DIR` (the project), `--json`,
`--no-color`, `-q` and `-v`/`-vv`, before or after the command name. No
command ever prompts: a choice it cannot make is an error whose hint names
the option (`--force`, `--id`, ...). The result goes to stdout and
everything else (diagnostics, warnings, logs) to stderr.

With `--json`, stdout is exactly one JSON document, the *envelope*:
`schema_version` (1), `tool`, `command`, `ok`, `exit_code`, `error` (`null`,
or its `class`, `code`, `message` and `hint`), `diagnostics` (each with
`severity`, `code`, `message`, `hint` and a `location`: file, line, column),
`context` (the project and the SDK, and where each setting came from) and
`result`, which depends on the command. Decide from `exit_code` and the
codes, never from the messages:

<!-- doc:run no-sdk -->
```sh
mmt-plugin -C demo --json validate --no-sdk > validate.json
python3 -c 'import json; d = json.load(open("validate.json")); print(d["exit_code"], d["result"]["protocol"])'
```

| Exit | Class | Meaning |
|---|---|---|
| 0 | | success (warnings allowed, unless `--strict`) |
| 1 | `internal` | a bug, or an I/O error with no better class |
| 2 | `usage` | bad arguments or option combination |
| 3 | `model` | the model or the data is wrong |
| 4 | `sdk` | SDK, toolchain or install prefix problem |
| 5 | `build` | the compiler or the linker failed |
| 6 | `test` | a packet test failed, or a crash |
| 7 | `state` | files on disk are not what the command needs |
| 130 | `interrupted` | interrupted (SIGINT) |

`--strict` makes warnings fail with their class's code. Each command's
`--help` lists the codes it can return. The envelope and each command's
`result` have JSON Schemas, shipped in the package
(`mmt_plugin/schemas/cli/v1/`); the design is in
[`docs/design/cli.md`](design/cli.md#6-the---json-envelope-shared-by-every-command).
To write plugins with an AI agent, or to update an existing project, see
the [mmt-plugin-author skill](../skills/mmt-plugin-author/SKILL.md).

## Settings and where they come from

A command-line option wins over an environment variable, which wins over
`plugin.yaml`, which wins over the default. Nothing machine-specific goes in
`plugin.yaml`, which is committed.

| Setting | Option | Environment | `plugin.yaml` | Default |
|---|---|---|---|---|
| Project | `-C` | | | `.` |
| SDK prefix | `--sdk` | `MMT_BASE` | | `mmt-dpi.pc`, then `/opt/mmt` |
| SDK profile | `--sdk-profile` | `MMT_PLUGIN_SDK_PROFILE` | `sdk.profile` | the SDK's version, else the newest bundled profile (a warning) |
| Compiler | `--cc` | `CC` | | `gcc` |
| Install prefix | `--prefix`, `--system` | `MMT_PLUGIN_PREFIX` | | `${XDG_DATA_HOME:-~/.local/share}/mmt` |
| Color | `--no-color` | `NO_COLOR`, `FORCE_COLOR` | | on a terminal |

[`docs/design/cli.md`](design/cli.md#9-config-strategy-precedence-cli--env--pluginyaml--defaults)
has the details.

## The example projects

[`examples/`](../examples/README.md) holds 16 complete projects, the models
of the Java tool's examples ported to `plugin.yaml`, each with its hooks
and packet tests. Their generated files are committed:

<!-- doc:run no-sdk -->
```sh
mmt-plugin -C examples/dns generate --check
```

<!-- doc:run sdk -->
```sh
mmt-plugin -C examples/dns test --sanitize
```
