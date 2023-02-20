/* Generated with MMT Plugin Generator */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "mongodb_mmt_plugin.h"
#include "extraction_lib.h"
#include "tcpip/mmt_tcpip.h"

/*
 * mongodbwire data extraction routines
 */

int mongodb_message_length_extraction(const ipacket_t * ipacket, int proto_index,
		attribute_t * extracted_data) {
	/* Get the protocol offset */
	int mongodbwire_offset = get_packet_offset_at_index(ipacket, proto_index);
	
	// Check if the packet has a payload. If the packet has not a payload then it is not a mongodb packet (perhaps it is a TCP ACK for a previous mongodb packet)
	// This prevents the extraction of the same data regarding the packet the ACK was referring to
	if((ipacket->p_hdr->caplen - mongodbwire_offset) == 0){
		return 0;
	}
	
	*((uint32_t *) extracted_data->data) = ((struct mongodb_header *) & ipacket->data[mongodbwire_offset])->message_length;

	return 1;
}



int mongodb_request_id_extraction(const ipacket_t * ipacket, int proto_index,
		attribute_t * extracted_data) {
	/* Get the protocol offset */
	int mongodbwire_offset = get_packet_offset_at_index(ipacket, proto_index);
	
	if((ipacket->p_hdr->caplen - mongodbwire_offset) == 0){
		return 0;
	}	
	
	*((uint32_t *) extracted_data->data) = ((struct mongodb_header *) & ipacket->data[mongodbwire_offset])->request_id;

	return 1;
}



int mongodb_response_to_extraction(const ipacket_t * ipacket, int proto_index,
		attribute_t * extracted_data) {
	/* Get the protocol offset */
	int mongodbwire_offset = get_packet_offset_at_index(ipacket, proto_index);
	
	if((ipacket->p_hdr->caplen - mongodbwire_offset) == 0){
		return 0;
	}
	
	*((uint32_t *) extracted_data->data) = ((struct mongodb_header *) & ipacket->data[mongodbwire_offset])->response_to;

	return 1;
}



int mongodb_op_code_extraction(const ipacket_t * ipacket, int proto_index,
		attribute_t * extracted_data) {
	/* Get the protocol offset */
	int mongodbwire_offset = get_packet_offset_at_index(ipacket, proto_index);
	
	if((ipacket->p_hdr->caplen - mongodbwire_offset) == 0){
		return 0;
	}
	
	*((uint32_t *) extracted_data->data) = ((struct mongodb_header *) & ipacket->data[mongodbwire_offset])->op_code;

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

	{MONGODB_MESSAGE_LENGTH, MONGODB_MESSAGE_LENGTH_ALIAS, MMT_U32_DATA, sizeof(uint32_t), POSITION_NOT_KNOWN, SCOPE_PACKET, mongodb_message_length_extraction},
	{MONGODB_REQUEST_ID, MONGODB_REQUEST_ID_ALIAS, MMT_U32_DATA, sizeof(uint32_t), POSITION_NOT_KNOWN, SCOPE_PACKET, mongodb_request_id_extraction},
	{MONGODB_RESPONSE_TO, MONGODB_RESPONSE_TO_ALIAS, MMT_U32_DATA, sizeof(uint32_t), POSITION_NOT_KNOWN, SCOPE_PACKET, mongodb_response_to_extraction},
	{MONGODB_OP_CODE, MONGODB_OP_CODE_ALIAS, MMT_U32_DATA, sizeof(uint32_t), POSITION_NOT_KNOWN, SCOPE_PACKET, mongodb_op_code_extraction},

};

/*
 * mongodbwire classification routine
 */

int mmt_check_mongodb_tcp(ipacket_t * ipacket, unsigned index) {
	//debug("\n[MONGODBWIRE: Classification] Checking packet with ID: %lu", ipacket->packet_id);

	// Get the offset for the packet to be classified
	int l4_offset = get_packet_offset_at_index(ipacket, index);
	int mongodbwire_offset = get_packet_offset_at_index(ipacket, index + 1);

	uint32_t op_code = ((struct mongodb_header *) & ipacket->data[mongodbwire_offset])->op_code;

	classified_proto_t retval;
	retval.offset = -1;
	retval.proto_id = -1;
	retval.status = NonClassified;
	
	// This prevents the classification of a TCP ACK as a mongodb packet. A TCP ACK has not a payload unlike a mongodb packet.
	if((ipacket->p_hdr->caplen - mongodbwire_offset) == 0){
		op_code = -1;
	}
	
	// This allows the classification of ONLY the FIRST segment of a fragmented TCP packet. This is because the first segment provides the mongodb header.
	// If the packet is a fragment of a TCP PDU
	// Take the TCP payload
	// Access to the op_code data
	// Set op_code accordingly

	// IF op_code is equal to 1 OR 2001-2007 OR 2010-2011 OR 2013
		// THEN the packet is a mongodbwire packet
	// ELSE
		// the packet is not a mongodbwire packet	
	switch(op_code){
		case OP_REPLY:
		case OP_UPDATE:
		case OP_INSERT:
		case OP_QUERY:
		case OP_GET_MORE:
		case OP_DELETE:
		case OP_KILL_CURSORS:
		case OP_COMMAND:
		case OP_COMMANDREPLY:
		case OP_MSG:
			//debug("[MONGODBWIRE: Classification] Packet %lu is mongodbwire!", ipacket->packet_id);
			retval = mongodb_stack_classification(ipacket);
			retval.offset = mongodbwire_offset - l4_offset;
			break;
		default:
			//debug("[MONGODBWIRE: Classification] Packet %lu is NOT mongodbwire!", ipacket->packet_id);
			break;
	}
	
	return set_classified_proto(ipacket, index + 1, retval);
}


int init_mongodb_proto_struct() {
	protocol_t * protocol_struct = init_protocol_struct_for_registration(PROTO_MONGODB, PROTO_MONGODB_ALIAS);

	if (protocol_struct != NULL) {

		int i = 0;
		for(; i < MONGODB_ATTRIBUTES_NB; i ++) {
			register_attribute_with_protocol(protocol_struct, &mongodb_attributes_metadata[i]);
		}

		// Register classification function of MONGODB protocol after TCP
		if(!register_classification_function_with_parent_protocol(PROTO_TCP, mmt_check_mongodb_tcp, 50)){
				fprintf(stderr, "\n[err] init_mongodb_proto_struct - cannot register_classification_function_with_parent_protocol: PROTO_TCP\n");
		};

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

