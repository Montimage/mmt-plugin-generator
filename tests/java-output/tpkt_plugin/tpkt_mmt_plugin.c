/* Generated with MMT Plugin Generator */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "tpkt_mmt_plugin.h"
#include "extraction_lib.h"




/*
 * TPKT data extraction routines
 */


classified_proto_t tpkt_stack_classification(ipacket_t * ipacket) {
	classified_proto_t retval;
	retval.offset = 0;
	retval.proto_id = PROTO_TPKT;
	retval.status = Classified;
	return retval;
}

static attribute_metadata_t tpkt_attributes_metadata[TPKT_ATTRIBUTES_NB] = {

	{TPKT_VERSION, TPKT_VERSION_ALIAS, MMT_U8_DATA, sizeof(uint8_t), 0, SCOPE_PACKET, general_char_extraction},

	{TPKT_RESERVED, TPKT_RESERVED_ALIAS, MMT_U8_DATA, sizeof(uint8_t), 1, SCOPE_PACKET, general_char_extraction},

	{TPKT_LENGTH, TPKT_LENGTH_ALIAS, MMT_U16_DATA, sizeof(uint16_t), 2, SCOPE_PACKET, general_short_extraction_with_ordering_change},

};


int init_tpkt_proto_struct() {
	protocol_t * protocol_struct = init_protocol_struct_for_registration(PROTO_TPKT, PROTO_TPKT_ALIAS);

	if (protocol_struct != NULL) {

		int i = 0;
		for(; i < TPKT_ATTRIBUTES_NB; i ++) {
			register_attribute_with_protocol(protocol_struct, &tpkt_attributes_metadata[i]);
		}


		register_protocol_stack(PROTO_TPKT, PROTO_TPKT_ALIAS, tpkt_stack_classification);
		return register_protocol(protocol_struct, PROTO_TPKT);
	} else {
		return -1;
	}
}

#ifndef CORE
int init_proto() {
	return init_tpkt_proto_struct();
}
#endif //CORE

