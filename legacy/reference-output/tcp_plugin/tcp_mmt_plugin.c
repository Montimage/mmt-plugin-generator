/* Generated with MMT Plugin Generator */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "tcp_mmt_plugin.h"
#include "extraction_lib.h"




/*
 * TCP data extraction routines
 */



int tcp_b_extraction(const ipacket_t * ipacket, int proto_index,
		attribute_t * extracted_data) {
	/* Get the protocol offset */
	int proto_offset = get_packet_offset_at_index(ipacket, proto_index);


	int attribute_offset = tcp_attributes_metadata[3].position_in_packet;



	int attribute_length = tcp_attributes_metadata[3].data_len;


	struct bcd * temp_bcd = (struct bcd *) & ipacket->data[proto_offset + attribute_offset];

	*((uint16_t *) extracted_data->data) = temp_bcd->b;



	return 1;
}



int tcp_c_extraction(const ipacket_t * ipacket, int proto_index,
		attribute_t * extracted_data) {
	/* Get the protocol offset */
	int proto_offset = get_packet_offset_at_index(ipacket, proto_index);


	int attribute_offset = tcp_attributes_metadata[4].position_in_packet;



	int attribute_length = tcp_attributes_metadata[4].data_len;


	struct bcd * temp_bcd = (struct bcd *) & ipacket->data[proto_offset + attribute_offset];

	*((uint16_t *) extracted_data->data) = temp_bcd->c;



	return 1;
}



int tcp_d_extraction(const ipacket_t * ipacket, int proto_index,
		attribute_t * extracted_data) {
	/* Get the protocol offset */
	int proto_offset = get_packet_offset_at_index(ipacket, proto_index);


	int attribute_offset = tcp_attributes_metadata[5].position_in_packet;



	int attribute_length = tcp_attributes_metadata[5].data_len;


	struct bcd * temp_bcd = (struct bcd *) & ipacket->data[proto_offset + attribute_offset];

	*((uint16_t *) extracted_data->data) = temp_bcd->d;



	return 1;
}



int tcp_f_extraction(const ipacket_t * ipacket, int proto_index,
		attribute_t * extracted_data) {
	/* Get the protocol offset */
	int proto_offset = get_packet_offset_at_index(ipacket, proto_index);


	int attribute_offset = tcp_attributes_metadata[7].position_in_packet;



	int attribute_length = tcp_attributes_metadata[7].data_len;


	struct fgh * temp_fgh = (struct fgh *) & ipacket->data[proto_offset + attribute_offset];

	*((uint16_t *) extracted_data->data) = temp_fgh->f;



	return 1;
}



int tcp_g_extraction(const ipacket_t * ipacket, int proto_index,
		attribute_t * extracted_data) {
	/* Get the protocol offset */
	int proto_offset = get_packet_offset_at_index(ipacket, proto_index);


	int attribute_offset = tcp_attributes_metadata[8].position_in_packet;



	int attribute_length = tcp_attributes_metadata[8].data_len;


	struct fgh * temp_fgh = (struct fgh *) & ipacket->data[proto_offset + attribute_offset];

	*((uint16_t *) extracted_data->data) = temp_fgh->g;



	return 1;
}



int tcp_h_extraction(const ipacket_t * ipacket, int proto_index,
		attribute_t * extracted_data) {
	/* Get the protocol offset */
	int proto_offset = get_packet_offset_at_index(ipacket, proto_index);


	int attribute_offset = tcp_attributes_metadata[9].position_in_packet;



	int attribute_length = tcp_attributes_metadata[9].data_len;


	struct fgh * temp_fgh = (struct fgh *) & ipacket->data[proto_offset + attribute_offset];

	*((uint16_t *) extracted_data->data) = temp_fgh->h;



	return 1;
}


classified_proto_t tcp_stack_classification(ipacket_t * ipacket) {
	classified_proto_t retval;
	retval.offset = 0;
	retval.proto_id = PROTO_TCP;
	retval.status = Classified;
	return retval;
}

static attribute_metadata_t tcp_attributes_metadata[TCP_ATTRIBUTES_NB] = {

	{TCP_SOURCE, TCP_SOURCE_ALIAS, MMT_U16_DATA, sizeof(uint16_t), 0, SCOPE_PACKET, general_short_extraction_with_ordering_change},

	{TCP_DEST, TCP_DEST_ALIAS, MMT_U16_DATA, sizeof(uint16_t), 2, SCOPE_PACKET, general_short_extraction_with_ordering_change},

	{TCP_A, TCP_A_ALIAS, MMT_U16_DATA, sizeof(uint16_t), 4, SCOPE_PACKET, general_short_extraction_with_ordering_change},

	{TCP_B, TCP_B_ALIAS, MMT_U16_DATA, sizeof(uint16_t), 6, SCOPE_PACKET, tcp_b_extraction},

	{TCP_C, TCP_C_ALIAS, MMT_U16_DATA, sizeof(uint16_t), 6, SCOPE_PACKET, tcp_c_extraction},

	{TCP_D, TCP_D_ALIAS, MMT_U16_DATA, sizeof(uint16_t), 6, SCOPE_PACKET, tcp_d_extraction},

	{TCP_E, TCP_E_ALIAS, MMT_U16_DATA, sizeof(uint16_t), 8, SCOPE_PACKET, general_short_extraction_with_ordering_change},

	{TCP_F, TCP_F_ALIAS, MMT_U16_DATA, sizeof(uint16_t), 10, SCOPE_PACKET, tcp_f_extraction},

	{TCP_G, TCP_G_ALIAS, MMT_U16_DATA, sizeof(uint16_t), 10, SCOPE_PACKET, tcp_g_extraction},

	{TCP_H, TCP_H_ALIAS, MMT_U16_DATA, sizeof(uint16_t), 10, SCOPE_PACKET, tcp_h_extraction},

	{TCP_SEQ, TCP_SEQ_ALIAS, MMT_U32_DATA, sizeof(uint32_t), 14, SCOPE_PACKET, general_int_extraction_with_ordering_change},

	{TCP_ACK_SEQ, TCP_ACK_SEQ_ALIAS, MMT_U32_DATA, sizeof(uint32_t), 18, SCOPE_PACKET, general_int_extraction_with_ordering_change},

	{TCP_FLAGS, TCP_FLAGS_ALIAS, MMT_U16_DATA, sizeof(uint16_t), 22, SCOPE_PACKET, general_short_extraction_with_ordering_change},

	{TCP_WINDOW, TCP_WINDOW_ALIAS, MMT_U16_DATA, sizeof(uint16_t), 24, SCOPE_PACKET, general_short_extraction_with_ordering_change},

	{TCP_CHECK, TCP_CHECK_ALIAS, MMT_U16_DATA, sizeof(uint16_t), 26, SCOPE_PACKET, general_short_extraction_with_ordering_change},

	{TCP_URG_PTR, TCP_URG_PTR_ALIAS, MMT_U16_DATA, sizeof(uint16_t), 28, SCOPE_PACKET, general_short_extraction_with_ordering_change},

};


int init_tcp_proto_struct() {
	protocol_t * protocol_struct = init_protocol_struct_for_registration(PROTO_TCP, PROTO_TCP_ALIAS);

	if (protocol_struct != NULL) {

		int i = 0;
		for(; i < TCP_ATTRIBUTES_NB; i ++) {
			register_attribute_with_protocol(protocol_struct, &tcp_attributes_metadata[i]);
		}


		register_protocol_stack(PROTO_TCP, PROTO_TCP_ALIAS, tcp_stack_classification);
		return register_protocol(protocol_struct, PROTO_TCP);
	} else {
		return -1;
	}
}

#ifndef CORE
int init_proto() {
	return init_tcp_proto_struct();
}
#endif //CORE

