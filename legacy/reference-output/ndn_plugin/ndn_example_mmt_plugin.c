/* Generated with MMT Plugin Generator */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "ndn_example_mmt_plugin.h"
#include "extraction_lib.h"




/*
 * NDN_EXAMPLE data extraction routines
 */



int ndn_example_packet_type_extraction(const ipacket_t * ipacket, int proto_index,
		attribute_t * extracted_data) {
	/* Get the protocol offset */
	int proto_offset = get_packet_offset_at_index(ipacket, proto_index);


	int attribute_offset = ndn_example_attributes_metadata[0].position_in_packet;


	/* Get the attribute data length */
	int attribute_length = sizeof(MMT_U8_DATA);


	*((unsigned char *) extracted_data->data) = *((unsigned char *) & ipacket->data[proto_offset + attribute_offset]);



	return 1;
}


classified_proto_t ndn_example_stack_classification(ipacket_t * ipacket) {
	classified_proto_t retval;
	retval.offset = 0;
	retval.proto_id = PROTO_NDN_EXAMPLE;
	retval.status = Classified;
	return retval;
}

static attribute_metadata_t ndn_example_attributes_metadata[NDN_EXAMPLE_ATTRIBUTES_NB] = {

	{NDN_EXAMPLE_PACKET_TYPE, NDN_EXAMPLE_PACKET_TYPE_ALIAS, MMT_U8_DATA, sizeof(uint8_t), 0, SCOPE_PACKET, ndn_example_packet_type_extraction},

};


void * ndn_example_sessionizer(void * protocol_context, ipacket_t * ipacket, int index, int * is_new_session) {
	/* User specific code goes here */
}

int ndn_example_session_cleanup_on_timeout(void * protocol_context, mmt_session_t * timedout_session, void * args) {
	/* User specific code goes here */
}

bool ndn_example_session_comp(void * key1, void * key2) {
	/* User specific code goes here */
	/* return true if key1 is lower than key2. The comparison MUST be implemented here */
	return false;
}


int init_ndn_example_proto_struct() {
	protocol_t * protocol_struct = init_protocol_struct_for_registration(PROTO_NDN_EXAMPLE, PROTO_NDN_EXAMPLE_ALIAS);

	if (protocol_struct != NULL) {

		int i = 0;
		for(; i < NDN_EXAMPLE_ATTRIBUTES_NB; i ++) {
			register_attribute_with_protocol(protocol_struct, &ndn_example_attributes_metadata[i]);
		}


		/* Register Session management routines */
		register_sessionizer_function(protocol_struct, ndn_example_sessionizer, ndn_example_session_cleanup_on_timeout, ndn_example_session_comp);


		register_protocol_stack(PROTO_NDN_EXAMPLE, PROTO_NDN_EXAMPLE_ALIAS, ndn_example_stack_classification);
		return register_protocol(protocol_struct, PROTO_NDN_EXAMPLE);
	} else {
		return -1;
	}
}

#ifndef CORE
int init_proto() {
	return init_ndn_example_proto_struct();
}
#endif //CORE

