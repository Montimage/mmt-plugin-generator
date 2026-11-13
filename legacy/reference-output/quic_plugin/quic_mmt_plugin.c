/* Generated with MMT Plugin Generator */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "quic_mmt_plugin.h"
#include "extraction_lib.h"




/*
 * QUIC data extraction routines
 */



int quic_connection_id_extraction(const ipacket_t * ipacket, int proto_index,
		attribute_t * extracted_data) {
	/* Get the protocol offset */
	int proto_offset = get_packet_offset_at_index(ipacket, proto_index);


	int attribute_offset = quic_attributes_metadata[0].position_in_packet;


	/* Get the attribute data length */
	int attribute_length = sizeof(MMT_U32_DATA);


	*((unsigned int *) extracted_data->data) = ntohl(*((unsigned int *) & ipacket->data[proto_offset + attribute_offset]));



	return 1;
}



int quic_sequence_extraction(const ipacket_t * ipacket, int proto_index,
		attribute_t * extracted_data) {
	/* Get the protocol offset */
	int proto_offset = get_packet_offset_at_index(ipacket, proto_index);


	int attribute_offset = quic_attributes_metadata[1].position_in_packet;


	/* Get the attribute data length */
	int attribute_length = sizeof(MMT_U32_DATA);


	*((unsigned int *) extracted_data->data) = ntohl(*((unsigned int *) & ipacket->data[proto_offset + attribute_offset]));



	return 1;
}


classified_proto_t quic_stack_classification(ipacket_t * ipacket) {
	classified_proto_t retval;
	retval.offset = 0;
	retval.proto_id = PROTO_QUIC;
	retval.status = Classified;
	return retval;
}

static attribute_metadata_t quic_attributes_metadata[QUIC_ATTRIBUTES_NB] = {

	{QUIC_CONNECTION_ID, QUIC_CONNECTION_ID_ALIAS, MMT_U32_DATA, sizeof(uint32_t), 0, SCOPE_PACKET, quic_connection_id_extraction},

	{QUIC_SEQUENCE, QUIC_SEQUENCE_ALIAS, MMT_U32_DATA, sizeof(uint32_t), 0, SCOPE_PACKET, quic_sequence_extraction},

};


int init_quic_proto_struct() {
	protocol_t * protocol_struct = init_protocol_struct_for_registration(PROTO_QUIC, PROTO_QUIC_ALIAS);

	if (protocol_struct != NULL) {

		int i = 0;
		for(; i < QUIC_ATTRIBUTES_NB; i ++) {
			register_attribute_with_protocol(protocol_struct, &quic_attributes_metadata[i]);
		}


		register_protocol_stack(PROTO_QUIC, PROTO_QUIC_ALIAS, quic_stack_classification);
		return register_protocol(protocol_struct, PROTO_QUIC);
	} else {
		return -1;
	}
}

#ifndef CORE
int init_proto() {
	return init_quic_proto_struct();
}
#endif //CORE

