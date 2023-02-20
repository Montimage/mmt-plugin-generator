# MMT Protocol Description #

## Install mmt-sdk

mmt-sdk need to be installed to be able to compile the plugin

## Generate plugin code

```
#!bash

java -jar PATH_TO_JAR <plugin_model> <output folder>
```

## Compile plugin

```
gcc -Wall -fPIC -shared -o <plugin-name>.so -I /opt/mmt/dpi/include/ <path_to_plugin_c_file>
```

Add `-g` to have debug information

## Use plugin

Copy plugin to the plugin folder: 

```
cp <plugin-name>.so /opt/mmt/plugins
```

## Example

Generate `lmmt_quic.so` for using in the example of MMT-sdk project (mmt-sdk/src/example)

* Create plugin description file `quic_plugin`:

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
gcc -Wall -fPIC -shared -o lmmt_quic.so -I /opt/mmt/dpi/include/ quic_mmt_plugin.c
```

* Install plugin

Simple by copying new plugin into `/opt/mmt/plugins/`

```
mv lmmt_quic.so /opt/mmt/plugins
```

* Check the new plugin by executing the example 'mmt-sdk/src/examples/proto_attributes_iterator.c'. We should see the information of new plugin in the output

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