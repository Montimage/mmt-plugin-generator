# MMT Protocol Description #

## Requirements

- mmt-dpi **1.10.2 or later** (at the time of writing, mmt-dpi `main`; 1.10.2
  is not released yet). 1.10.2 is the first version whose installed headers
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
`<prefix>` is `/opt/mmt` or your private prefix.

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

`init_extraction()` loads every `*.so` of the plugin directory in file-name
order (`alphasort`), and fails if one of them fails to load. A plugin that
registers its classifier under a built-in protocol (TCP, UDP, Ethernet...)
must therefore have a file name that sorts **after** `libmmt_tcpip.so`
(for example `ndn_example.so` or `lmmt_quic.so`): a name such as
`aaa_ndn.so` loads first, before TCP and Ethernet exist, and its classifiers
are not attached.

Pick a protocol id that no loaded protocol uses (`0 < id < 1000`) and a name
that is unique (names are compared case-insensitively). A duplicate id makes
`init_extraction()` fail; a duplicate name is silently ignored. mmt-dpi 1.10.x
registers many more protocols than older releases, so the ids used in the
QUIC walkthrough below (630) and in several `plugins/` models now collide
with built-in protocols: check `<prefix>/dpi/include/*/*_protocols.h` and
choose a free id.

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

Verified with gcc 13.3 on Linux aarch64 against mmt-dpi `main` at commit
9ea989d7 (version 1.10.2) installed into a private prefix. The other plugin
sources under `plugins/` were not changed and are not covered by this check.

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