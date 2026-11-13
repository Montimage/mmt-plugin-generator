/* Generated with MMT Plugin Generator */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "abb_mmt_plugin.h"
#include "extraction_lib.h"




/*
 * ABB data extraction routines
 */


classified_proto_t abb_stack_classification(ipacket_t * ipacket) {
	classified_proto_t retval;
	retval.offset = 0;
	retval.proto_id = PROTO_ABB;
	retval.status = Classified;
	return retval;
}

static attribute_metadata_t abb_attributes_metadata[ABB_ATTRIBUTES_NB] = {

	{ABB_SIZE, ABB_SIZE_ALIAS, MMT_U32_DATA, sizeof(uint32_t), 0, SCOPE_PACKET, general_int_extraction_with_ordering_change},

	{ABB_TYPE, ABB_TYPE_ALIAS, MMT_U32_DATA, sizeof(uint32_t), 4, SCOPE_PACKET, general_int_extraction_with_ordering_change},

	{ABB_FRAME_NUMBER, ABB_FRAME_NUMBER_ALIAS, MMT_U32_DATA, sizeof(uint32_t), 8, SCOPE_PACKET, general_int_extraction_with_ordering_change},

	{ABB_CAPTURE_TIME, ABB_CAPTURE_TIME_ALIAS, MMT_U32_DATA, sizeof(uint32_t), 12, SCOPE_PACKET, general_int_extraction_with_ordering_change},

	{ABB_FLAGS_CHECKSUM, ABB_FLAGS_CHECKSUM_ALIAS, MMT_U32_DATA, sizeof(uint32_t), 16, SCOPE_PACKET, general_int_extraction_with_ordering_change},

	{ABB_NUMBER_OF_MARKERS, ABB_NUMBER_OF_MARKERS_ALIAS, MMT_U32_DATA, sizeof(uint32_t), 20, SCOPE_PACKET, general_int_extraction_with_ordering_change},

	{ABB_RESERVED_TIMESTAMP, ABB_RESERVED_TIMESTAMP_ALIAS, MMT_U32_DATA, sizeof(uint32_t), 24, SCOPE_PACKET, general_int_extraction_with_ordering_change},

};


int init_abb_proto_struct() {
	protocol_t * protocol_struct = init_protocol_struct_for_registration(PROTO_ABB, PROTO_ABB_ALIAS);

	if (protocol_struct != NULL) {

		int i = 0;
		for(; i < ABB_ATTRIBUTES_NB; i ++) {
			register_attribute_with_protocol(protocol_struct, &abb_attributes_metadata[i]);
		}


		register_protocol_stack(PROTO_ABB, PROTO_ABB_ALIAS, abb_stack_classification);
		return register_protocol(protocol_struct, PROTO_ABB);
	} else {
		return -1;
	}
}

#ifndef CORE
int init_proto() {
	return init_abb_proto_struct();
}
#endif //CORE

