# MMT plugin generator

`mmt-plugin` generates, builds, tests and installs protocol plugins for
[mmt-dpi](https://github.com/Montimage/mmt-dpi), Montimage's deep packet
inspection library. You describe a protocol in `plugin.yaml` (its fields,
how to find the next protocol, what it runs on), write C only for what the
model cannot say, and check the plugin on packets whose expected values come
from the protocol's specification.

It replaces the 2015 Java generator (`MMTPluginGenerator.jar`), which was
removed in #31 (its sources and jar are in `legacy/` at commit 4076899).
Coming from the Java tool? Read the [migration guide](docs/migration.md).

**Status:** 0.1.0 is the first release of the Python tool
([changelog](CHANGELOG.md)). Until it is published (plan task T5.5, #32, in
[`docs/design/workflow-redesign.md`](docs/design/workflow-redesign.md))
there is no PyPI package and no GitHub release: install it from a checkout
of this repository (below). [`docs/releasing.md`](docs/releasing.md)
describes how a release is published.

## Documentation

- [User guide](docs/user-guide.md): installing, a project from `init` to
  `install`, every command, the `--json` output and exit codes.
- [`plugin.yaml`](docs/plugin-yaml.md): the model format, with an example,
  and the [model reference](docs/model-reference.md), generated from its
  JSON Schema.
- [Migration guide](docs/migration.md): from the Java tool and PDL v1, and
  [what behaves differently](docs/behaviour-changes.md).
- [Examples](examples/README.md): 18 complete plugin projects, the Java
  tool's 16 examples ported, a WebSocket (RFC 6455) plugin and an OCPP
  1.6-J plugin.
- [Use case: WebSocket and OCPP 1.6-J](docs/use-cases/websocket-ocpp.md):
  the workflow on two real protocols, and the two plugins against tshark
  on public OCPP captures.
- [CLI design](docs/design/cli.md): the command contract in full.
- [Releasing](docs/releasing.md): the release assets, the dry run and
  how a release is published; the [changelog](CHANGELOG.md) lists what
  each release changed.
- [mmt-plugin-generator](skills/mmt-plugin-generator/SKILL.md): the agent skill
  that writes a plugin from a spec, a capture or a PDL v1 model, or updates
  an existing plugin project, evaluates it on a capture of the protocol
  (found, or generated when there is none), and keeps everything that made
  it in a work folder.
- [Contributing](CONTRIBUTING.md), and [`AGENTS.md`](AGENTS.md) for the
  repository's layout and checks.

## Requirements

- Linux (amd64 or arm64) and Python 3.10 or later.
- mmt-dpi **[1.10.2](https://github.com/Montimage/mmt-dpi/releases/tag/v1.10.2) or later**,
  to build, test and install plugins (generating code needs no SDK).
  1.10.2 is the first version whose installed headers ship the public logger
  `mmt_log.h` (Montimage/mmt-dpi#68).
- gcc or clang.

## Install

With [uv](https://docs.astral.sh/uv/), from the root of a checkout
(`pipx install .` works too):

<!-- doc:run install -->
```sh
uv tool install .
mmt-plugin --version
```

The [user guide](docs/user-guide.md#install-mmt-plugin) shows how to install
a built wheel instead.

Once a release is published, install it from PyPI, or from the wheel
attached to its [GitHub release](docs/user-guide.md#from-a-release), or run
its container image (mmt-plugin with gcc, clang and mmt-dpi):

<!-- doc:skip needs a published release -->
```sh
uv tool install mmt-plugin
docker run --rm ghcr.io/montimage/mmt-plugin:0.1.0 mmt-plugin --version
```

## Quick start

Create a project, whose model `quick/plugin.yaml` pins the SDK profile and
attaches the protocol to UDP port 4433 in generated code, then check it and
generate its C sources (no SDK needed for these):

<!-- doc:run no-sdk -->
```sh
mmt-plugin init quick --id 960 --parent udp:dport=4433 --sdk-profile 1.10.2
mmt-plugin -C quick validate --no-sdk
mmt-plugin -C quick generate
```

With mmt-dpi in a private prefix (below) and `MMT_BASE` set to it, build
the plugin and run its packet test, then install it into a prefix of your
own:

<!-- doc:run sdk -->
```sh
mmt-plugin -C quick test
mmt-plugin -C quick install --prefix "$PWD/quick-prefix"
```

The [user guide](docs/user-guide.md) goes on from here: writing the model,
the hooks in `src/`, packet tests, installing where mmt-dpi loads plugins,
and drafting a model from a capture.

## Install mmt-dpi

mmt-dpi (the "mmt-sdk") must be installed to compile and load a plugin. From
an mmt-dpi checkout, install it into a private prefix, without root:

<!-- doc:skip needs an mmt-dpi checkout -->
```sh
make -C sdk MMT_BASE=$HOME/mmt -j$(nproc)
make -C sdk MMT_BASE=$HOME/mmt install
export LD_LIBRARY_PATH=$HOME/mmt/dpi/lib
```

or system-wide, into `/opt/mmt` (`mmt-plugin` itself never needs root):

<!-- doc:skip needs root and an mmt-dpi checkout -->
```sh
make -C sdk -j$(nproc)
sudo make -C sdk install
```

The same `MMT_BASE` must be given to both commands: it is compiled into the
library as the default plugin directory (`$MMT_BASE/plugins`). Below,
`<prefix>` is `/opt/mmt` or your private prefix, always as an absolute
path (mmt-dpi refuses a relative `MMT_BASE`); `mmt-plugin` finds it through
`--sdk`, `MMT_BASE`, `mmt-dpi.pc` or `/opt/mmt`, in that order.

Prebuilt `.deb` and `.rpm` packages for several distributions are attached
to each mmt-dpi Release (see `manifest.json` and `SHA256SUMS` there). They
install into `/opt/mmt`. CI extracts the ubuntu-24.04 one into a private
prefix after `tests/fetch_mmt_dpi_package.sh` has verified it; the
[user guide](docs/user-guide.md#get-mmt-dpi) and `AGENTS.md` show how.

## Build and test container

`Dockerfile` builds an Ubuntu 24.04 image, pinned by digest, with gcc, clang,
Python 3.12 and mmt-dpi v1.10.2 installed in `/opt/mmt` from the Release
`.deb` that `tests/fetch_mmt_dpi_package.sh` verified. To build it and run
`tests/check_ndn_plugin.sh` inside it (no root on the host, nothing written
to the checkout):

<!-- doc:skip needs docker or podman, and the network -->
```sh
make test-container
make test-container CONTAINER=podman
```

The repo is mounted read-only and the check runs as your uid with no
network; on an SELinux host add `MOUNT_OPTS=ro,z`. apt packages are not
pinned to exact versions (see the policy at the top of `Dockerfile`): the
build fails if the gcc, clang or Python major version changes, or if
pkg-config cannot find mmt-dpi at the package's version (a broken
`mmt-dpi.pc`), and the image lists every installed version in
`/usr/share/doc/mmt-test-image/packages.txt`. CI runs the same target on
amd64 and arm64: it is CI's NDN check. The release image is the
`release` target of the same `Dockerfile`, this image plus mmt-plugin
(`make release-image`, [`docs/releasing.md`](docs/releasing.md)).

## Writing plugin code for mmt-dpi 1.10

mmt-dpi 1.10.0 made the old unprefixed `debug()`, `log_err()`, `likely()` and
`unlikely()` macros private: a plugin that still uses them fails with
"implicit declaration" errors. Use instead:

- `#include "mmt_log.h"`, then `mmt_log_error()`, `mmt_log_warn()`,
  `mmt_log_info()` and `mmt_log_debug()` (printf-style). `mmt_log_debug()` is
  compiled in only when the plugin is built with `-DMMT_LOG_ENABLE_DEBUG`.
  Nothing is printed until the level is raised at run time with
  `MMT_DPI_LOG_LEVEL=error|warn|info|debug`;
- `MMT_LIKELY(x)` / `MMT_UNLIKELY(x)` from `mmt_utils.h` for branch hints.

## Plugin load order, ids and names

mmt-dpi's loader has two behaviours that fail **silently**. `mmt-plugin`
handles both for you (the plugin file is `mmtp_<label>.so`, `validate` and
`doctor` check the order and the ids and names, and the generated init
returns 0 when a registration fails); this section explains them for
hand-written plugins. Line numbers are from mmt-dpi v1.10.2 (commit
a84a6050), under `src/mmt_core/src/`.

**(a) Load order: name the plugin file so it sorts after `libmmt_tcpip.so`.**

- `init_extraction()` loads every `*.so` of the plugin directory in
  file-name order: `scandir(dir, ..., alphasort)` (`plugins_engine.c:71`).
  `alphasort` compares with `strcoll`, so if the host program calls
  `setlocale()` the order follows its `LC_COLLATE`.
- The first plugin that fails to load or whose `init_proto()` returns `<= 0`
  stops the load, and `init_extraction()` fails
  (`plugins_engine.c:84-99`, `:149-150`; `packet_registry.c:668`).
- A plugin that attaches its classifier under a built-in protocol (TCP, UDP,
  Ethernet...) calls `register_classification_function_with_parent_protocol()`.
  That function returns 0 when the parent protocol is not registered yet
  (`packet_registry_classify.c:209-219`, through
  `get_protocol_struct_by_protocol_id()`, `packet_registry.c:188-196`).
- So a plugin loaded **before** `libmmt_tcpip.so` (e.g. `aaa_ndn.so`) still
  registers its protocol, and `init_extraction()` still succeeds, but the
  plugin never classifies a packet. Nothing reports it unless the plugin
  checks that return value.

What to do:

- Give the file a name that sorts after `libmmt_tcpip.so` in the C locale
  and in the host's locale: start it with a lowercase letter after `l`
  (upper case sorts before `l` in the C locale), e.g. `ndn_example.so`, or
  with `lm`, e.g. `lmmt_quic.so`. Check it with `sort`: the plugin must come
  second.

  <!-- doc:run no-sdk -->
  ```sh
  printf '%s\n' mmtp_demo.so libmmt_tcpip.so | LC_ALL=C sort
  ```

- In `init_proto()`, check the return value of every
  `register_classification_function_with_parent_protocol()` call and return
  0 when it fails. `init_extraction()` then fails with
  `<path>: init_proto() failed (0)` instead of running with a plugin that
  never classifies anything. The NDN example does this
  (`ndn_src/ndn_mmt_plugin.c`, `init_ndn_proto_struct()`).

**(b) Ids and names: pick a unique id AND a unique name.**

- **Duplicate id: `init_extraction()` fails.**
  `init_protocol_struct_for_registration()` returns NULL for an id that is
  out of range (`>= PROTO_MAX_IDENTIFIER`, 1000) or already registered
  (`packet_registry.c:381-389`, `:440-447`). The plugin's `init_proto()`
  then returns `<= 0`, which fails the load, as in (a).
- **Duplicate name: silently ignored.** `register_protocol()` adds the name
  to the name index only if it is not there yet, and still returns
  `PROTO_REGISTERED` (`packet_registry.c:555-559`). Names are compared
  case-insensitively (`:74-76`). `get_protocol_id_by_name()` then returns
  the protocol that registered the name first (`:810-813`), so anything that
  looks your protocol up by name gets the other one.

What to do:

- Before registering, refuse a name that is already taken:
  `if (get_protocol_id_by_name(MY_ALIAS) != 0) return 0;`. This catches the
  built-in protocols and plugins that loaded earlier. The NDN example does
  this too, and so does the code `mmt-plugin` generates.
- Choose an id from 950 to 999, the range for third-party plugins, and a
  name the SDK does not have. `mmt-plugin validate` checks both against the
  SDK headers and the installed plugins. By hand, list the ids and names the
  SDK headers define (some ids are defined with tabs, e.g. `PROTO_HTTP2` =
  700, hence the `[[:space:]]` pattern):

  <!-- doc:run sdk -->
  ```sh
  grep -rhE '#define[[:space:]]+PROTO_[A-Z0-9_]+[[:space:]]+[0-9]+' "$MMT_BASE"/dpi/include | grep -v MAX_IDENTIFIER
  grep -rhE '#define[[:space:]]+PROTO_[A-Z0-9_]+_ALIAS[[:space:]]+"' "$MMT_BASE"/dpi/include
  ```

  mmt-dpi 1.10.x registers many more protocols than older releases, so
  several of the Java tool's example models now collide with built-in
  protocols.
- The headers list only the SDK's own protocols: any other `.so` in the
  plugin directory can take ids and names too. The reliable check is at run
  time, with every plugin you deploy in the plugin directory: after
  `init_extraction()` succeeds, `is_registered_protocol(id)` must be true
  and `get_protocol_id_by_name(name)` must return **your** id
  (`tests/ndn_load_check.c` does both; `mmt-plugin doctor` reports the
  clashes among installed plugins). The installed
  `<prefix>/examples/proto_attributes_iterator.c` lists every registered
  protocol.

To use a plugin directory of your own, point `MMT_DPI_PLUGINS_DIR` at it (an
absolute path). That directory replaces `<prefix>/plugins`, so it must also
hold the built-in plugins the new one depends on, e.g. a copy or symlink of
`<prefix>/plugins/libmmt_tcpip.so`.

## NDN example and the built-in NDN dissector

`ndn_src/` holds a hand-written NDN (Named Data Networking) plugin, and
`tests/corpus/models/ndn/model.pdl` its model (ported to
[`examples/ndn/`](examples/ndn/)).
mmt-dpi now ships its own NDN dissector in `libmmt_tcpip` (`PROTO_NDN` =
625, name `ndn`, `NDN_*` attributes), so this example is kept only as a
plugin-writing sample. To coexist with the built-in dissector it registers
as a separate protocol, `ndn_example`, id 980, and uses `NDN_EXAMPLE_*` /
`PROTO_NDN_EXAMPLE*` identifiers that do not clash with the installed
headers.

Build it:

<!-- doc:run sdk -->
```sh
gcc -Wall -Werror -fPIC -shared -o ndn_example.so -I "$MMT_BASE"/dpi/include ndn_src/ndn_mmt_plugin.c
```

and check it, with `MMT_BASE` set to the prefix:

<!-- doc:skip CI runs it in the build and test container, make test-container -->
```sh
bash tests/check_ndn_plugin.sh
```

`tests/check_ndn_plugin.sh` compiles the
example with `-Wall -Werror`, with and without `-DMMT_LOG_ENABLE_DEBUG`,
checks that no C source or C template (`*.c`, `*.h`, `*.c.j2`, `*.h.j2`
under its `SCAN_DIRS`) uses the removed macros, then loads it next to
`libmmt_tcpip.so` (through a temporary `MMT_DPI_PLUGINS_DIR`) and checks
that `ndn_example` (980) and the built-in `ndn` (625) both resolve and that
its classifiers are attached. It also fails if the plugin file name
(`PLUGIN_NAME`, default `ndn_example.so`) sorts before `libmmt_tcpip.so`, or
if its id or name is defined by the SDK headers. It prints one
`PASS:`/`FAIL:` line per check and exits non-zero on failure.

The other example plugins are the projects of [`examples/`](examples/README.md),
which build and test against mmt-dpi 1.10.2; this check also scans their C
for the removed macros. The Java tool's other plugin sources, in `plugins/`,
were removed in #78 (several did not build against mmt-dpi 1.10.x, mostly
because they redeclare protocols that mmt-dpi now ships);
[`examples/README.md`](examples/README.md#the-java-tools-c-sources) says
where they are and what replaced them.
