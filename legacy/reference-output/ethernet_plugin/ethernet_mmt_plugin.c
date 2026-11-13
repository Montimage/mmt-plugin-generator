/* Generated with MMT Plugin Generator */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "ethernet_mmt_plugin.h"
#include "extraction_lib.h"



uint16_t ethernet_h_proto_get_value(const ipacket_t * ipacket, int proto_index);



/*
 * ETHERNET data extraction routines
 */



int ethernet_src_extraction(const ipacket_t * ipacket, int proto_index,
		attribute_t * extracted_data) {
	/* Get the protocol offset */
	int proto_offset = get_packet_offset_at_index(ipacket, proto_index);


	int attribute_offset = ethernet_attributes_metadata[3].position_in_packet;


	/* Get the attribute data length */
	int attribute_length = sizeof(null);


	memcpy((u_char *) extracted_data->data, (char *) & ipacket->data[proto_offset + attribute_offset], attribute_length);



	return 1;
}



int ethernet_dst_extraction(const ipacket_t * ipacket, int proto_index,
		attribute_t * extracted_data) {
	/* Get the protocol offset */
	int proto_offset = get_packet_offset_at_index(ipacket, proto_index);


	int attribute_offset = ethernet_attributes_metadata[4].position_in_packet;


	/* Get the attribute data length */
	int attribute_length = sizeof(null);


	memcpy((u_char *) extracted_data->data, (char *) & ipacket->data[proto_offset + attribute_offset], attribute_length);



	return 1;
}


classified_proto_t ethernet_stack_classification(ipacket_t * ipacket) {
	classified_proto_t retval;
	retval.offset = 0;
	retval.proto_id = PROTO_ETHERNET;
	retval.status = Classified;
	return retval;
}

static attribute_metadata_t ethernet_attributes_metadata[ETHERNET_ATTRIBUTES_NB] = {

	{ETHERNET_H_DEST, ETHERNET_H_DEST_ALIAS, MMT_DATA_MAC_ADDR, 6, 0, SCOPE_PACKET, general_byte_to_byte_extraction},

	{ETHERNET_H_SOURCE, ETHERNET_H_SOURCE_ALIAS, MMT_DATA_MAC_ADDR, 6, 6, SCOPE_PACKET, general_byte_to_byte_extraction},

	{ETHERNET_H_PROTO, ETHERNET_H_PROTO_ALIAS, MMT_U16_DATA, sizeof(uint16_t), 12, SCOPE_PACKET, general_short_extraction_with_ordering_change},

	{ETHERNET_SRC, ETHERNET_SRC_ALIAS, MMT_DATA_MAC_ADDR, sizeof(mac_addr_t), 0, SCOPE_PACKET, ethernet_src_extraction},

	{ETHERNET_DST, ETHERNET_DST_ALIAS, MMT_DATA_MAC_ADDR, sizeof(mac_addr_t), 2, SCOPE_PACKET, ethernet_dst_extraction},

};


uint16_t ethernet_h_proto_get_value(const ipacket_t * ipacket, int proto_index) {
	uint16_t retval;
	int proto_offset = get_packet_offset_at_index(ipacket, proto_index);
	retval = ntohs(*(uint16_t *) & ipacket->data[proto_offset + ethernet_attributes_metadata[2].position_in_packet]);
	return retval;
}


int ethernet_classify_next_proto(ipacket_t * ipacket, int proto_index, void * args) {
	/* Uncomment if necessary */
	//int * classify_behaviour = (int *) args;
	//int offset = get_packet_offset_at_index(ipacket, proto_index);

	classified_proto_t retval;
	retval.offset = -1;
	retval.proto_id = -1;
	retval.status = NonClassified;


	switch(ethernet_h_proto_get_value(ipacket, proto_index)) {
		case ETH_P_IP :

			retval.proto_id = PROTO_IP; retval.status = Classified;

			retval.offset = sizeof(struct ethhdr);

			break;

		case ETH_P_ARP :

			retval.proto_id = PROTO_ARP; retval.status = Classified;

			retval.offset = sizeof(struct ethhdr);

			break;

		case ETH_P_IPV6 :

			retval.proto_id = PROTO_IP6; retval.status = Classified;

			retval.offset = sizeof(struct ethhdr);

			break;

		case ETH_P_RARP :

			retval.proto_id = PROTO_ARP; retval.status = Classified;

			retval.offset = sizeof(struct ethhdr);

			break;

		default :

			break;

	}

	return set_classified_proto(ipacket, proto_index + 1, retval);
}


int init_ethernet_proto_struct() {
	protocol_t * protocol_struct = init_protocol_struct_for_registration(PROTO_ETHERNET, PROTO_ETHERNET_ALIAS);

	if (protocol_struct != NULL) {

		int i = 0;
		for(; i < ETHERNET_ATTRIBUTES_NB; i ++) {
			register_attribute_with_protocol(protocol_struct, &ethernet_attributes_metadata[i]);
		}


		/* Classify encapsulated protocol */
		register_classification_function(protocol_struct, (generic_classification_function)ethernet_classify_next_proto);


		register_protocol_stack(PROTO_ETHERNET, PROTO_ETHERNET_ALIAS, ethernet_stack_classification);
		return register_protocol(protocol_struct, PROTO_ETHERNET);
	} else {
		return -1;
	}
}

#ifndef CORE
int init_proto() {
	return init_ethernet_proto_struct();
}
#endif //CORE

