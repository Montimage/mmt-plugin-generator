# MMT Protocol Description #

## Requirements

- mmt-dpi **[1.10.2](https://github.com/Montimage/mmt-dpi/releases/tag/v1.10.2) or later**.
  1.10.2 is the first version whose installed headers
  ship the public logger `mmt_log.h` (Montimage/mmt-dpi#68).
- gcc (or clang) and, to generate code from a model, a Java runtime.

mmt-dpi 1.10.0 made the old unprefixed `debug()`, `log_err()`, `likely()` and
`unlikely()` macros private: a plugin that still uses them fails with
"implicit declaration" errors. Use instead:

- `#include "mmt_log.h"`, then `mmt_log_error()`, `mmt_log_warn()`,
  `mmt_log_info()` and `mmt_log_debug()` (printf-style). `mmt_log_debug()` is
  compiled in only when the plugin is built with `-DMMT_LOG_ENABLE_DEBUG`.
  Nothing is printed until the level is raised at run time with
  `MMT_DPI_LOG_LEVEL=error|warn|info|debug`;
- `MMT_LIKELY(x)` / `MMT_UNLIKELY(x)` from `mmt_utils.h` for branch hints.

## Install mmt-dpi

mmt-dpi (the "mmt-sdk") must be installed to compile and load a plugin. From
an mmt-dpi checkout, either install it system-wide into `/opt/mmt`:

```
make -C sdk -j$(nproc)
sudo make -C sdk install
```

or into a private prefix, without root:

```
make -C sdk MMT_BASE=$HOME/mmt -j$(nproc)
make -C sdk MMT_BASE=$HOME/mmt install
export LD_LIBRARY_PATH=$HOME/mmt/dpi/lib
```

The same `MMT_BASE` must be given to both commands: it is compiled into the
library as the default plugin directory (`$MMT_BASE/plugins`). Below,
`<prefix>` is `/opt/mmt` or your private prefix, always as an absolute
path (mmt-dpi refuses a relative `MMT_BASE`).

## Generate plugin code

```
#!bash

java -jar PATH_TO_JAR <plugin_model> <output folder>
```

## Compile plugin

```
gcc -Wall -fPIC -shared -o <plugin-name>.so -I <prefix>/dpi/include <path_to_plugin_c_file>
```

Add `-g` to have debug information, and `-DMMT_LOG_ENABLE_DEBUG` to compile
in the plugin's `mmt_log_debug()` calls.

## Use plugin

Copy the plugin to the plugin folder:

```
cp <plugin-name>.so <prefix>/plugins
```

or put it in a directory of your own and point `MMT_DPI_PLUGINS_DIR` at it
(an absolute path). That directory replaces `<prefix>/plugins`, so it must
also hold the built-in plugins the new one depends on, e.g. a copy or symlink
of `<prefix>/plugins/libmmt_tcpip.so`.

### Plugin load order, ids and names

mmt-dpi's loader has two behaviours that fail **silently**, so plugins in
this repo must handle them. Line numbers are from mmt-dpi v1.10.2
(commit a84a6050), under `src/mmt_core/src/`.

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
  with `lm`, e.g. `lmmt_quic.so`. Check it with
  `printf '%s\n' <plugin>.so libmmt_tcpip.so | LC_ALL=C sort`: the plugin must
  come second.
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
  this too.
- List the ids and names the SDK headers already define, and choose free
  ones:

  ```
  grep -rhE '#define[[:space:]]+PROTO_[A-Z0-9_]+[[:space:]]+[0-9]+' <prefix>/dpi/include | grep -v MAX_IDENTIFIER
  grep -rhE '#define[[:space:]]+PROTO_[A-Z0-9_]+_ALIAS[[:space:]]+"' <prefix>/dpi/include
  ```

  Some ids are defined with tabs (e.g. `PROTO_HTTP2` = 700), hence the
  `[[:space:]]` pattern. mmt-dpi 1.10.x registers many more protocols than
  older releases, so the ids used in the QUIC walkthrough below (630) and
  in several `plugins/` models now collide with built-in protocols.
- The headers list only the SDK's own protocols: any other `.so` in the
  plugin directory can take ids and names too. The reliable check is at run
  time, with every plugin you deploy in the plugin directory: after
  `init_extraction()` succeeds, `is_registered_protocol(id)` must be true
  and `get_protocol_id_by_name(name)` must return **your** id
  (`tests/ndn_load_check.c` does both). The installed
  `<prefix>/examples/proto_attributes_iterator.c` lists every registered
  protocol.

`tests/check_ndn_plugin.sh` guards the cheap parts for the NDN example: it
fails if the plugin file name (`PLUGIN_NAME`, default `ndn_example.so`)
sorts before `libmmt_tcpip.so`, or if its id or name is defined by the SDK
headers. It then runs the run-time checks above.

## NDN example and the built-in NDN dissector

`ndn_src/` holds a hand-written NDN (Named Data Networking) plugin, and
`plugins/ndn_plugin` its model. mmt-dpi now ships its own NDN dissector in
`libmmt_tcpip` (`PROTO_NDN` = 625, name `ndn`, `NDN_*` attributes), so this
example is kept only as a plugin-writing sample. To coexist with the built-in
dissector it registers as a separate protocol, `ndn_example`, id 980, and
uses `NDN_EXAMPLE_*` / `PROTO_NDN_EXAMPLE*` identifiers that do not clash with
the installed headers. (The generator upper-cases the model's label, so code
regenerated from `plugins/ndn_plugin` registers the name `NDN_EXAMPLE`, which
is the same name for mmt-dpi's case-insensitive lookups.)

Build, install and check it:

```
gcc -Wall -Werror -fPIC -shared -o ndn_example.so -I <prefix>/dpi/include ndn_src/ndn_mmt_plugin.c
cp ndn_example.so <prefix>/plugins/
MMT_BASE=<prefix> bash tests/check_ndn_plugin.sh
```

`tests/check_ndn_plugin.sh` compiles the example with `-Wall -Werror`, with
and without `-DMMT_LOG_ENABLE_DEBUG`, checks that no C source uses the
removed macros, then loads it next to `libmmt_tcpip.so` (through a temporary
`MMT_DPI_PLUGINS_DIR`) and checks that `ndn_example` (980) and the built-in
`ndn` (625) both resolve and that its classifiers are attached. It prints one
`PASS:`/`FAIL:` line per check and exits non-zero on failure.

Verified with gcc 13.3 on Linux aarch64 against mmt-dpi v1.10.2 (sources
identical to commit 9ea989d7) installed into a private prefix. The other plugin
sources under `plugins/` are not covered by this check (only comments in
three of them were updated for the new logger names); several of them do not
build against mmt-dpi 1.10.x, mostly because they redeclare protocols that
mmt-dpi now ships.

## Example

Generate `lmmt_quic.so` for using in the example of MMT-sdk project (mmt-sdk/src/example)

* Create plugin description file `quic_plugin`:

> **Note:** id 630 is `PROTO_VMWARE` in mmt-dpi 1.10.x, and a `QUIC` protocol
> is built in. Use a free id and a distinct label (see "Use plugin" above),
> otherwise `init_extraction()` fails.

```
Protocol {
	Properties {
		label = "QUIC"
		id = "630"
		context = "false"
		session = "false"
		encapsulation = "false"
		encoding = "network"
	}
	Attributes {
		attribute {
            alias="connection_id" data_type="MMT_U32_DATA" data_len="sizeof(int)" 
            offset="0" scope="SCOPE_PACKET"
        }
        attribute {
            alias="sequence" data_type="MMT_U32_DATA" data_len="sizeof(int)" 
            offset="0" scope="SCOPE_PACKET"
        }
	}
}

```

* Generate source code for QUIC plugin:

```
cd plugin_generator/plugins/
mkdir quic_src
java -jar ../dist/MMTPluginGenerator.jar quic_plugin quic_src
```

After executing the abow commands, we should have 2 source files in `quic_src/`

```
ls quic_src/
quic_mmt_plugin.c  quic_mmt_plugin.h
```

* Update plugin source code

We need to update the source code of plugin for classification and extraction.

Update `init_quic_proto_struct`:

```
int init_quic_proto_struct() {
		protocol_t * protocol_struct = init_protocol_struct_for_registration(PROTO_QUIC, PROTO_QUIC_ALIAS);

		if (protocol_struct != NULL) {

			int i = 0;
			for(; i < QUIC_ATTRIBUTES_NB; i ++) {
				register_attribute_with_protocol(protocol_struct, &quic_attributes_metadata[i]);
			}
			// Register the QUIC detection function : QUIC/UDP
			register_classification_function_with_parent_protocol(PROTO_UDP, mmt_check_quic, 50);
			register_protocol_stack(PROTO_QUIC, PROTO_QUIC_ALIAS, quic_stack_classification);
			return register_protocol(protocol_struct, PROTO_QUIC);
		} else {
			return -1;
		}
	}
```

Look in `plugin_generator/plugins/quic/` to have more detail how to **detect** QUIC protocol and how to **extract** QUIC protocol attritbutes

* Compile plugin

```
cd quic_src/
gcc -Wall -fPIC -shared -o lmmt_quic.so -I <prefix>/dpi/include quic_mmt_plugin.c
```

* Install plugin

Simple by copying new plugin into `<prefix>/plugins/`

```
mv lmmt_quic.so <prefix>/plugins
```

* Check the new plugin by executing the example 'mmt-sdk/src/examples/proto_attributes_iterator.c' (installed as `<prefix>/examples/proto_attributes_iterator.c`). We should see the information of new plugin in the output

```
Protocol id 630 --- Name QUIC
	Attribute id 1 --- Name connection_id 
	Attribute id 2 --- Name sequence 
	Attribute id 4096 --- Name p_hdr 
	Attribute id 4097 --- Name p_data 
	Attribute id 4098 --- Name p_payload 
	Attribute id 4099 --- Name packet_count 
	Attribute id 4100 --- Name data_count 
	Attribute id 4101 --- Name payload_count 
	Attribute id 4102 --- Name ip_frag_packets_count 
	Attribute id 4103 --- Name ip_frag_data_volume 
	Attribute id 4104 --- Name ip_df_packets_count 
	Attribute id 4105 --- Name ip_df_data_volume 
	Attribute id 4106 --- Name session_count 
	Attribute id 4107 --- Name a_session_count 
	Attribute id 4108 --- Name t_session_count 
	Attribute id 4109 --- Name first_packet_time 
	Attribute id 4110 --- Name last_packet_time 
	Attribute id 4111 --- Name stats 

```