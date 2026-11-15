/* Generated with MMT Plugin Generator */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "s7comm_mmt_plugin.h"
#include "extraction_lib.h"




/*
 * S7COMM data extraction routines
 */


classified_proto_t s7comm_stack_classification(ipacket_t * ipacket) {
	classified_proto_t retval;
	retval.offset = 0;
	retval.proto_id = PROTO_S7COMM;
	retval.status = Classified;
	return retval;
}

static attribute_metadata_t s7comm_attributes_metadata[S7COMM_ATTRIBUTES_NB] = {

	{S7COMM_PROTO_ID, S7COMM_PROTO_ID_ALIAS, MMT_U8_DATA, sizeof(uint8_t), 0, SCOPE_PACKET, general_char_extraction},

	{S7COMM_ROSCTR, S7COMM_ROSCTR_ALIAS, MMT_U8_DATA, sizeof(uint8_t), 1, SCOPE_PACKET, general_char_extraction},

	{S7COMM_RESERVED, S7COMM_RESERVED_ALIAS, MMT_U16_DATA, sizeof(uint16_t), 2, SCOPE_PACKET, general_short_extraction_with_ordering_change},

	{S7COMM_PDUR, S7COMM_PDUR_ALIAS, MMT_U16_DATA, sizeof(uint16_t), 4, SCOPE_PACKET, general_short_extraction_with_ordering_change},

	{S7COMM_PARAM_LENGTH, S7COMM_PARAM_LENGTH_ALIAS, MMT_U16_DATA, sizeof(uint16_t), 6, SCOPE_PACKET, general_short_extraction_with_ordering_change},

	{S7COMM_DATA_LENGTH, S7COMM_DATA_LENGTH_ALIAS, MMT_U16_DATA, sizeof(uint16_t), 8, SCOPE_PACKET, general_short_extraction_with_ordering_change},

};


int init_s7comm_proto_struct() {
	protocol_t * protocol_struct = init_protocol_struct_for_registration(PROTO_S7COMM, PROTO_S7COMM_ALIAS);

	if (protocol_struct != NULL) {

		int i = 0;
		for(; i < S7COMM_ATTRIBUTES_NB; i ++) {
			register_attribute_with_protocol(protocol_struct, &s7comm_attributes_metadata[i]);
		}


		register_protocol_stack(PROTO_S7COMM, PROTO_S7COMM_ALIAS, s7comm_stack_classification);
		return register_protocol(protocol_struct, PROTO_S7COMM);
	} else {
		return -1;
	}
}

#ifndef CORE
int init_proto() {
	return init_s7comm_proto_struct();
}
#endif //CORE

