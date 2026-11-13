/* Generated with MMT Plugin Generator */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "cotp_mmt_plugin.h"
#include "extraction_lib.h"




/*
 * COTP data extraction routines
 */


classified_proto_t cotp_stack_classification(ipacket_t * ipacket) {
	classified_proto_t retval;
	retval.offset = 0;
	retval.proto_id = PROTO_COTP;
	retval.status = Classified;
	return retval;
}

static attribute_metadata_t cotp_attributes_metadata[COTP_ATTRIBUTES_NB] = {

	{COTP_LENGTH, COTP_LENGTH_ALIAS, MMT_U8_DATA, sizeof(uint8_t), 0, SCOPE_PACKET, general_char_extraction},

	{COTP_PDU_TYPE, COTP_PDU_TYPE_ALIAS, MMT_U8_DATA, sizeof(uint8_t), 1, SCOPE_PACKET, general_char_extraction},

};


int init_cotp_proto_struct() {
	protocol_t * protocol_struct = init_protocol_struct_for_registration(PROTO_COTP, PROTO_COTP_ALIAS);

	if (protocol_struct != NULL) {

		int i = 0;
		for(; i < COTP_ATTRIBUTES_NB; i ++) {
			register_attribute_with_protocol(protocol_struct, &cotp_attributes_metadata[i]);
		}


		register_protocol_stack(PROTO_COTP, PROTO_COTP_ALIAS, cotp_stack_classification);
		return register_protocol(protocol_struct, PROTO_COTP);
	} else {
		return -1;
	}
}

#ifndef CORE
int init_proto() {
	return init_cotp_proto_struct();
}
#endif //CORE

