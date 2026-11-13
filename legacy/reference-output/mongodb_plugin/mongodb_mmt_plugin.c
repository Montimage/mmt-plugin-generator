/* Generated with MMT Plugin Generator */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "mongodb_mmt_plugin.h"
#include "extraction_lib.h"




/*
 * MONGODB data extraction routines
 */



int mongodb_message_length_extraction(const ipacket_t * ipacket, int proto_index,
		attribute_t * extracted_data) {
	/* Get the protocol offset */
	int proto_offset = get_packet_offset_at_index(ipacket, proto_index);

	/* Get the attribute offset (relative the to protocol) */
	int attribute_offset = null;

	/* Get the attribute data length */
	int attribute_length = sizeof(MMT_U32_DATA);


	*((unsigned int *) extracted_data->data) = ntohl(*((unsigned int *) & ipacket->data[proto_offset + attribute_offset]));



	return 1;
}



int mongodb_request_id_extraction(const ipacket_t * ipacket, int proto_index,
		attribute_t * extracted_data) {
	/* Get the protocol offset */
	int proto_offset = get_packet_offset_at_index(ipacket, proto_index);

	/* Get the attribute offset (relative the to protocol) */
	int attribute_offset = null;

	/* Get the attribute data length */
	int attribute_length = sizeof(MMT_U32_DATA);


	*((unsigned int *) extracted_data->data) = ntohl(*((unsigned int *) & ipacket->data[proto_offset + attribute_offset]));



	return 1;
}



int mongodb_response_to_extraction(const ipacket_t * ipacket, int proto_index,
		attribute_t * extracted_data) {
	/* Get the protocol offset */
	int proto_offset = get_packet_offset_at_index(ipacket, proto_index);

	/* Get the attribute offset (relative the to protocol) */
	int attribute_offset = null;

	/* Get the attribute data length */
	int attribute_length = sizeof(MMT_U32_DATA);


	*((unsigned int *) extracted_data->data) = ntohl(*((unsigned int *) & ipacket->data[proto_offset + attribute_offset]));



	return 1;
}



int mongodb_op_code_extraction(const ipacket_t * ipacket, int proto_index,
		attribute_t * extracted_data) {
	/* Get the protocol offset */
	int proto_offset = get_packet_offset_at_index(ipacket, proto_index);

	/* Get the attribute offset (relative the to protocol) */
	int attribute_offset = null;

	/* Get the attribute data length */
	int attribute_length = sizeof(MMT_U32_DATA);


	*((unsigned int *) extracted_data->data) = ntohl(*((unsigned int *) & ipacket->data[proto_offset + attribute_offset]));



	return 1;
}


classified_proto_t mongodb_stack_classification(ipacket_t * ipacket) {
	classified_proto_t retval;
	retval.offset = 0;
	retval.proto_id = PROTO_MONGODB;
	retval.status = Classified;
	return retval;
}

static attribute_metadata_t mongodb_attributes_metadata[MONGODB_ATTRIBUTES_NB] = {

	{MONGODB_MESSAGE_LENGTH, MONGODB_MESSAGE_LENGTH_ALIAS, MMT_U32_DATA, sizeof(uint32_t), -2, SCOPE_PACKET, mongodb_message_length_extraction},

	{MONGODB_REQUEST_ID, MONGODB_REQUEST_ID_ALIAS, MMT_U32_DATA, sizeof(uint32_t), -2, SCOPE_PACKET, mongodb_request_id_extraction},

	{MONGODB_RESPONSE_TO, MONGODB_RESPONSE_TO_ALIAS, MMT_U32_DATA, sizeof(uint32_t), -2, SCOPE_PACKET, mongodb_response_to_extraction},

	{MONGODB_OP_CODE, MONGODB_OP_CODE_ALIAS, MMT_U32_DATA, sizeof(uint32_t), -2, SCOPE_PACKET, mongodb_op_code_extraction},

};


int init_mongodb_proto_struct() {
	protocol_t * protocol_struct = init_protocol_struct_for_registration(PROTO_MONGODB, PROTO_MONGODB_ALIAS);

	if (protocol_struct != NULL) {

		int i = 0;
		for(; i < MONGODB_ATTRIBUTES_NB; i ++) {
			register_attribute_with_protocol(protocol_struct, &mongodb_attributes_metadata[i]);
		}


		register_protocol_stack(PROTO_MONGODB, PROTO_MONGODB_ALIAS, mongodb_stack_classification);
		return register_protocol(protocol_struct, PROTO_MONGODB);
	} else {
		return -1;
	}
}

#ifndef CORE
int init_proto() {
	return init_mongodb_proto_struct();
}
#endif //CORE

