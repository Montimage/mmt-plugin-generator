/* Generated with MMT Plugin Generator */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "cpm_mmt_plugin.h"
#include "extraction_lib.h"




/*
 * CPM data extraction routines
 */



int cpm_protocolversion_extraction(const ipacket_t * ipacket, int proto_index,
		attribute_t * extracted_data) {
	/* Get the protocol offset */
	int proto_offset = get_packet_offset_at_index(ipacket, proto_index);


	int attribute_offset = cpm_attributes_metadata[0].position_in_packet;


	/* Get the attribute data length */
	int attribute_length = sizeof(MMT_U8_DATA);


	*((unsigned char *) extracted_data->data) = *((unsigned char *) & ipacket->data[proto_offset + attribute_offset]);



	return 1;
}



int cpm_messageid_extraction(const ipacket_t * ipacket, int proto_index,
		attribute_t * extracted_data) {
	/* Get the protocol offset */
	int proto_offset = get_packet_offset_at_index(ipacket, proto_index);


	int attribute_offset = cpm_attributes_metadata[1].position_in_packet;


	/* Get the attribute data length */
	int attribute_length = sizeof(MMT_U8_DATA);


	*((unsigned char *) extracted_data->data) = *((unsigned char *) & ipacket->data[proto_offset + attribute_offset]);



	return 1;
}



int cpm_stationid_extraction(const ipacket_t * ipacket, int proto_index,
		attribute_t * extracted_data) {
	/* Get the protocol offset */
	int proto_offset = get_packet_offset_at_index(ipacket, proto_index);


	int attribute_offset = cpm_attributes_metadata[2].position_in_packet;


	/* Get the attribute data length */
	int attribute_length = sizeof(MMT_U32_DATA);


	*((unsigned int *) extracted_data->data) = ntohl(*((unsigned int *) & ipacket->data[proto_offset + attribute_offset]));



	return 1;
}



int cpm_generationtime_extraction(const ipacket_t * ipacket, int proto_index,
		attribute_t * extracted_data) {
	/* Get the protocol offset */
	int proto_offset = get_packet_offset_at_index(ipacket, proto_index);


	int attribute_offset = cpm_attributes_metadata[3].position_in_packet;


	/* Get the attribute data length */
	int attribute_length = sizeof(MMT_U16_DATA);


	*((unsigned short *) extracted_data->data) = ntohs(*((unsigned short *) & ipacket->data[proto_offset + attribute_offset]));



	return 1;
}


classified_proto_t cpm_stack_classification(ipacket_t * ipacket) {
	classified_proto_t retval;
	retval.offset = 0;
	retval.proto_id = PROTO_CPM;
	retval.status = Classified;
	return retval;
}

static attribute_metadata_t cpm_attributes_metadata[CPM_ATTRIBUTES_NB] = {

	{CPM_PROTOCOLVERSION, CPM_PROTOCOLVERSION_ALIAS, MMT_U8_DATA, sizeof(uint8_t), 0, SCOPE_PACKET, cpm_protocolversion_extraction},

	{CPM_MESSAGEID, CPM_MESSAGEID_ALIAS, MMT_U8_DATA, sizeof(uint8_t), 1, SCOPE_PACKET, cpm_messageid_extraction},

	{CPM_STATIONID, CPM_STATIONID_ALIAS, MMT_U32_DATA, sizeof(uint32_t), 2, SCOPE_PACKET, cpm_stationid_extraction},

	{CPM_GENERATIONTIME, CPM_GENERATIONTIME_ALIAS, MMT_U16_DATA, sizeof(uint16_t), 6, SCOPE_PACKET, cpm_generationtime_extraction},

};


int init_cpm_proto_struct() {
	protocol_t * protocol_struct = init_protocol_struct_for_registration(PROTO_CPM, PROTO_CPM_ALIAS);

	if (protocol_struct != NULL) {

		int i = 0;
		for(; i < CPM_ATTRIBUTES_NB; i ++) {
			register_attribute_with_protocol(protocol_struct, &cpm_attributes_metadata[i]);
		}


		register_protocol_stack(PROTO_CPM, PROTO_CPM_ALIAS, cpm_stack_classification);
		return register_protocol(protocol_struct, PROTO_CPM);
	} else {
		return -1;
	}
}

#ifndef CORE
int init_proto() {
	return init_cpm_proto_struct();
}
#endif //CORE

