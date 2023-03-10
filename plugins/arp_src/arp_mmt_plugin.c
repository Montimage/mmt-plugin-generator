/* Generated with MMT Plugin Generator */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "arp_mmt_plugin.h"
#include "extraction_lib.h"
#include "tcpip/mmt_tcpip.h"



uint16_t arp_ar_hrd_get_value(const ipacket_t * ipacket, int proto_index);


uint16_t arp_ar_pro_get_value(const ipacket_t * ipacket, int proto_index);


uint8_t arp_ar_hln_get_value(const ipacket_t * ipacket, int proto_index);


uint8_t arp_ar_pln_get_value(const ipacket_t * ipacket, int proto_index);


uint32_t  arp_ar_sha_get_offset(const ipacket_t * ipacket, int proto_index);


uint32_t  arp_ar_sha_get_length(const ipacket_t * ipacket, int proto_index);


uint32_t arp_ar_sip_get_value(const ipacket_t * ipacket, int proto_index);


uint32_t  arp_ar_sip_get_offset(const ipacket_t * ipacket, int proto_index);


uint32_t  arp_ar_sip_get_length(const ipacket_t * ipacket, int proto_index);


uint32_t  arp_ar_tha_get_offset(const ipacket_t * ipacket, int proto_index);


uint32_t  arp_ar_tha_get_length(const ipacket_t * ipacket, int proto_index);


uint32_t arp_ar_tip_get_value(const ipacket_t * ipacket, int proto_index);


uint32_t  arp_ar_tip_get_offset(const ipacket_t * ipacket, int proto_index);


uint32_t  arp_ar_tip_get_length(const ipacket_t * ipacket, int proto_index);


uint32_t  arp_ar_pro_get_offset(const ipacket_t * ipacket, int proto_index);


uint32_t  arp_ar_pro_get_length(const ipacket_t * ipacket, int proto_index);


uint32_t  arp_src_proto_get_offset(const ipacket_t * ipacket, int proto_index);


uint32_t  arp_src_proto_get_length(const ipacket_t * ipacket, int proto_index);


uint32_t  arp_dst_hard_get_offset(const ipacket_t * ipacket, int proto_index);


uint32_t  arp_dst_hard_get_length(const ipacket_t * ipacket, int proto_index);


uint32_t  arp_dst_proto_get_offset(const ipacket_t * ipacket, int proto_index);


uint32_t  arp_dst_proto_get_length(const ipacket_t * ipacket, int proto_index);



// /*
//  * ARP data extraction routines
//  */



int arp_ar_sha_extraction(const ipacket_t * ipacket, int proto_index,
		attribute_t * extracted_data) {
	/* Get the protocol offset */
	int proto_offset = get_packet_offset_at_index(ipacket, proto_index);


	if(arp_ar_hrd_get_value(ipacket, proto_index) == 0x0001 && arp_ar_pro_get_value(ipacket, proto_index) == 0x0800) {


	int attribute_offset = 8;



	int attribute_length = 6;


	memcpy((u_char *) extracted_data->data, (char *) & ipacket->data[proto_offset + attribute_offset], attribute_length);


	return 1;


	}


	return 0;
}



int arp_ar_sip_extraction(const ipacket_t * ipacket, int proto_index,
		attribute_t * extracted_data) {
	/* Get the protocol offset */
	int proto_offset = get_packet_offset_at_index(ipacket, proto_index);


	if(arp_ar_hrd_get_value(ipacket, proto_index) == 0x0001 && arp_ar_pro_get_value(ipacket, proto_index) == 0x0800) {


	int attribute_offset = 14;



	// int attribute_length = 4;


	*((unsigned int *) extracted_data->data) = ntohl(*((unsigned int *) & ipacket->data[proto_offset + attribute_offset]));


	return 1;


	}


	return 0;
}



int arp_ar_tha_extraction(const ipacket_t * ipacket, int proto_index,
		attribute_t * extracted_data) {
	/* Get the protocol offset */
	int proto_offset = get_packet_offset_at_index(ipacket, proto_index);


	if(arp_ar_hrd_get_value(ipacket, proto_index) == 0x0001 && arp_ar_pro_get_value(ipacket, proto_index) == 0x0800) {


	int attribute_offset = 18;



	int attribute_length = 6;


	memcpy((u_char *) extracted_data->data, (char *) & ipacket->data[proto_offset + attribute_offset], attribute_length);


	return 1;


	}


	return 0;
}



int arp_ar_tip_extraction(const ipacket_t * ipacket, int proto_index,
		attribute_t * extracted_data) {
	/* Get the protocol offset */
	int proto_offset = get_packet_offset_at_index(ipacket, proto_index);


	if(arp_ar_hrd_get_value(ipacket, proto_index) == 0x0001 && arp_ar_pro_get_value(ipacket, proto_index) == 0x0800) {


	int attribute_offset = 24;



	// int attribute_length = 4;


	*((unsigned int *) extracted_data->data) = ntohl(*((unsigned int *) & ipacket->data[proto_offset + attribute_offset]));


	return 1;


	}


	return 0;
}



int arp_ar_pro_extraction(const ipacket_t * ipacket, int proto_index,
		attribute_t * extracted_data) {
	/* Get the protocol offset */
	int proto_offset = get_packet_offset_at_index(ipacket, proto_index);


	if(arp_ar_hrd_get_value(ipacket, proto_index) == 0x0001 && arp_ar_pro_get_value(ipacket, proto_index) == 0x0800) {


	} else { 

	/* Get the attribute offset (relative the to protocol) */
	int attribute_offset = sizeof(struct arphdr);

	/* Get the attribute data length */
	int attribute_length = arp_ar_hln_get_value(ipacket, proto_index);


	*((unsigned int *) extracted_data->data) = attribute_length;
 	memcpy(& ((u_char *) extracted_data->data)[sizeof (int) ], & ipacket->data[proto_offset + attribute_offset], attribute_length);


	return 1;


	}


	return 0;
}



int arp_src_proto_extraction(const ipacket_t * ipacket, int proto_index,
		attribute_t * extracted_data) {
	/* Get the protocol offset */
	int proto_offset = get_packet_offset_at_index(ipacket, proto_index);


	if(arp_ar_hrd_get_value(ipacket, proto_index) == 0x0001 && arp_ar_pro_get_value(ipacket, proto_index) == 0x0800) {


	} else { 

	/* Get the attribute offset (relative the to protocol) */
	int attribute_offset = sizeof(struct arphdr) + arp_ar_hln_get_value(ipacket, proto_index);

	/* Get the attribute data length */
	int attribute_length = arp_ar_pln_get_value(ipacket, proto_index);


	*((unsigned int *) extracted_data->data) = attribute_length;
 	memcpy(& ((u_char *) extracted_data->data)[sizeof (int) ], & ipacket->data[proto_offset + attribute_offset], attribute_length);


	return 1;


	}


	return 0;
}



int arp_dst_hard_extraction(const ipacket_t * ipacket, int proto_index,
		attribute_t * extracted_data) {
	/* Get the protocol offset */
	int proto_offset = get_packet_offset_at_index(ipacket, proto_index);


	if(arp_ar_hrd_get_value(ipacket, proto_index) == 0x0001 && arp_ar_pro_get_value(ipacket, proto_index) == 0x0800) {


	} else { 

	/* Get the attribute offset (relative the to protocol) */
	int attribute_offset = sizeof(struct arphdr) + arp_ar_pln_get_value(ipacket, proto_index) + arp_ar_hln_get_value(ipacket, proto_index);

	/* Get the attribute data length */
	int attribute_length = arp_ar_hln_get_value(ipacket, proto_index);


	*((unsigned int *) extracted_data->data) = attribute_length;
 	memcpy(& ((u_char *) extracted_data->data)[sizeof (int) ], & ipacket->data[proto_offset + attribute_offset], attribute_length);


	return 1;


	}


	return 0;
}



int arp_dst_proto_extraction(const ipacket_t * ipacket, int proto_index,
		attribute_t * extracted_data) {
	/* Get the protocol offset */
	int proto_offset = get_packet_offset_at_index(ipacket, proto_index);


	if(arp_ar_hrd_get_value(ipacket, proto_index) == 0x0001 && arp_ar_pro_get_value(ipacket, proto_index) == 0x0800) {


	} else { 

	/* Get the attribute offset (relative the to protocol) */
	int attribute_offset = sizeof(struct arphdr) + arp_ar_pln_get_value(ipacket, proto_index) + 2 * arp_ar_hln_get_value(ipacket, proto_index);

	/* Get the attribute data length */
	int attribute_length = arp_ar_pln_get_value(ipacket, proto_index);


	*((unsigned int *) extracted_data->data) = attribute_length;
 	memcpy(& ((u_char *) extracted_data->data)[sizeof (int) ], & ipacket->data[proto_offset + attribute_offset], attribute_length);


	return 1;


	}


	return 0;
}


classified_proto_t arp_stack_classification(ipacket_t * ipacket) {
	classified_proto_t retval;
	retval.offset = 0;
	retval.proto_id = PROTO_ARP;
	retval.status = Classified;
	return retval;
}

static attribute_metadata_t arp_attributes_metadata[ARP_ATTRIBUTES_NB] = {

	{ARP_AR_HRD, ARP_AR_HRD_ALIAS, MMT_U16_DATA, sizeof(uint16_t), 0, SCOPE_PACKET, general_short_extraction_with_ordering_change},

	{ARP_AR_PRO, ARP_AR_PRO_ALIAS, MMT_U16_DATA, sizeof(uint16_t), 2, SCOPE_PACKET, general_short_extraction_with_ordering_change},

	{ARP_AR_HLN, ARP_AR_HLN_ALIAS, MMT_U8_DATA, sizeof(uint8_t), 4, SCOPE_PACKET, general_char_extraction},

	{ARP_AR_PLN, ARP_AR_PLN_ALIAS, MMT_U8_DATA, sizeof(uint8_t), 5, SCOPE_PACKET, general_char_extraction},

	{ARP_AR_OP, ARP_AR_OP_ALIAS, MMT_U16_DATA, sizeof(uint16_t), 6, SCOPE_PACKET, general_short_extraction_with_ordering_change},

	{ARP_AR_SHA, ARP_AR_SHA_ALIAS, MMT_DATA_MAC_ADDR, sizeof(mac_addr_t), -1, SCOPE_PACKET, arp_ar_sha_extraction},

	{ARP_AR_SIP, ARP_AR_SIP_ALIAS, MMT_U32_DATA, sizeof(uint32_t), -1, SCOPE_PACKET, arp_ar_sip_extraction},

	{ARP_AR_THA, ARP_AR_THA_ALIAS, MMT_DATA_MAC_ADDR, sizeof(mac_addr_t), -1, SCOPE_PACKET, arp_ar_tha_extraction},

	{ARP_AR_TIP, ARP_AR_TIP_ALIAS, MMT_U32_DATA, sizeof(uint32_t), -1, SCOPE_PACKET, arp_ar_tip_extraction},

	{ARP_AR_PRO, ARP_AR_PRO_ALIAS, MMT_BINARY_DATA, BINARY_64DATA_TYPE_LEN, -1, SCOPE_PACKET, arp_ar_pro_extraction},

	{ARP_SRC_PROTO, ARP_SRC_PROTO_ALIAS, MMT_BINARY_DATA, BINARY_64DATA_TYPE_LEN, -1, SCOPE_PACKET, arp_src_proto_extraction},

	{ARP_DST_HARD, ARP_DST_HARD_ALIAS, MMT_BINARY_DATA, BINARY_64DATA_TYPE_LEN, -1, SCOPE_PACKET, arp_dst_hard_extraction},

	{ARP_DST_PROTO, ARP_DST_PROTO_ALIAS, MMT_BINARY_DATA, BINARY_64DATA_TYPE_LEN, -1, SCOPE_PACKET, arp_dst_proto_extraction},

};


uint16_t arp_ar_hrd_get_value(const ipacket_t * ipacket, int proto_index) {
	uint16_t retval;
	int proto_offset = get_packet_offset_at_index(ipacket, proto_index);
	retval = ntohs(*(uint16_t *) & ipacket->data[proto_offset + arp_attributes_metadata[0].position_in_packet]);
	return retval;
}


uint16_t arp_ar_pro_get_value(const ipacket_t * ipacket, int proto_index) {
	uint16_t retval;
	int proto_offset = get_packet_offset_at_index(ipacket, proto_index);
	retval = ntohs(*(uint16_t *) & ipacket->data[proto_offset + arp_attributes_metadata[1].position_in_packet]);
	return retval;
}


uint8_t arp_ar_hln_get_value(const ipacket_t * ipacket, int proto_index) {
	uint8_t retval;
	int proto_offset = get_packet_offset_at_index(ipacket, proto_index);
	retval = *(uint8_t *) & ipacket->data[proto_offset + arp_attributes_metadata[2].position_in_packet];
	return retval;
}


uint8_t arp_ar_pln_get_value(const ipacket_t * ipacket, int proto_index) {
	uint8_t retval;
	int proto_offset = get_packet_offset_at_index(ipacket, proto_index);
	retval = *(uint8_t *) & ipacket->data[proto_offset + arp_attributes_metadata[3].position_in_packet];
	return retval;
}


uint32_t arp_ar_sha_get_offset(const ipacket_t * ipacket, int proto_index) {
	uint32_t retval;
	//uint32_t proto_offset = get_packet_offset_at_index(ipacket, proto_index);



	if(arp_ar_hrd_get_value(ipacket, proto_index) == 0x0001 && arp_ar_pro_get_value(ipacket, proto_index) == 0x0800) {


	retval = 8;



	}


	return retval;
}


uint32_t arp_ar_sha_get_length(const ipacket_t * ipacket, int proto_index) {
	uint32_t retval;
	//int proto_offset = get_packet_offset_at_index(ipacket, proto_index);



	if(arp_ar_hrd_get_value(ipacket, proto_index) == 0x0001 && arp_ar_pro_get_value(ipacket, proto_index) == 0x0800) {


	retval = 6;



	}


	return retval;
}


uint32_t arp_ar_sip_get_value(const ipacket_t * ipacket, int proto_index) {
	uint32_t retval;
	int proto_offset = get_packet_offset_at_index(ipacket, proto_index);



	if(arp_ar_hrd_get_value(ipacket, proto_index) == 0x0001 && arp_ar_pro_get_value(ipacket, proto_index) == 0x0800) {


	int attribute_offset = 14;


	retval = ntohl(*((unsigned int *) & ipacket->data[proto_offset + attribute_offset]));



	}


	return retval;
}


uint32_t arp_ar_sip_get_offset(const ipacket_t * ipacket, int proto_index) {
	uint32_t retval;
	//uint32_t proto_offset = get_packet_offset_at_index(ipacket, proto_index);



	if(arp_ar_hrd_get_value(ipacket, proto_index) == 0x0001 && arp_ar_pro_get_value(ipacket, proto_index) == 0x0800) {


	retval = 14;



	}


	return retval;
}


uint32_t arp_ar_sip_get_length(const ipacket_t * ipacket, int proto_index) {
	uint32_t retval;
	//int proto_offset = get_packet_offset_at_index(ipacket, proto_index);



	if(arp_ar_hrd_get_value(ipacket, proto_index) == 0x0001 && arp_ar_pro_get_value(ipacket, proto_index) == 0x0800) {


	retval = 4;



	}


	return retval;
}


uint32_t arp_ar_tha_get_offset(const ipacket_t * ipacket, int proto_index) {
	uint32_t retval;
	//uint32_t proto_offset = get_packet_offset_at_index(ipacket, proto_index);



	if(arp_ar_hrd_get_value(ipacket, proto_index) == 0x0001 && arp_ar_pro_get_value(ipacket, proto_index) == 0x0800) {


	retval = 18;



	}


	return retval;
}


uint32_t arp_ar_tha_get_length(const ipacket_t * ipacket, int proto_index) {
	uint32_t retval;
	//int proto_offset = get_packet_offset_at_index(ipacket, proto_index);



	if(arp_ar_hrd_get_value(ipacket, proto_index) == 0x0001 && arp_ar_pro_get_value(ipacket, proto_index) == 0x0800) {


	retval = 6;



	}


	return retval;
}


uint32_t arp_ar_tip_get_value(const ipacket_t * ipacket, int proto_index) {
	uint32_t retval;
	int proto_offset = get_packet_offset_at_index(ipacket, proto_index);



	if(arp_ar_hrd_get_value(ipacket, proto_index) == 0x0001 && arp_ar_pro_get_value(ipacket, proto_index) == 0x0800) {


	int attribute_offset = 24;


	retval = ntohl(*((unsigned int *) & ipacket->data[proto_offset + attribute_offset]));



	}


	return retval;
}


uint32_t arp_ar_tip_get_offset(const ipacket_t * ipacket, int proto_index) {
	uint32_t retval;
	//uint32_t proto_offset = get_packet_offset_at_index(ipacket, proto_index);



	if(arp_ar_hrd_get_value(ipacket, proto_index) == 0x0001 && arp_ar_pro_get_value(ipacket, proto_index) == 0x0800) {


	retval = 24;



	}


	return retval;
}


uint32_t arp_ar_tip_get_length(const ipacket_t * ipacket, int proto_index) {
	uint32_t retval;
	//int proto_offset = get_packet_offset_at_index(ipacket, proto_index);



	if(arp_ar_hrd_get_value(ipacket, proto_index) == 0x0001 && arp_ar_pro_get_value(ipacket, proto_index) == 0x0800) {


	retval = 4;



	}


	return retval;
}


uint32_t arp_ar_pro_get_offset(const ipacket_t * ipacket, int proto_index) {
	uint32_t retval;
	//uint32_t proto_offset = get_packet_offset_at_index(ipacket, proto_index);



	if(arp_ar_hrd_get_value(ipacket, proto_index) == 0x0001 && arp_ar_pro_get_value(ipacket, proto_index) == 0x0800) {


	} else { 

	/* Get the attribute offset (relative the to protocol) */
	uint32_t retval = sizeof(struct arphdr);


	}


	return retval;
}


uint32_t arp_ar_pro_get_length(const ipacket_t * ipacket, int proto_index) {
	uint32_t retval;
	//int proto_offset = get_packet_offset_at_index(ipacket, proto_index);



	if(arp_ar_hrd_get_value(ipacket, proto_index) == 0x0001 && arp_ar_pro_get_value(ipacket, proto_index) == 0x0800) {


	} else { 

	/* Get the attribute length (relative the to protocol) */
	uint32_t retval = arp_ar_hln_get_value(ipacket, proto_index);


	}


	return retval;
}


uint32_t arp_src_proto_get_offset(const ipacket_t * ipacket, int proto_index) {
	uint32_t retval;
	//uint32_t proto_offset = get_packet_offset_at_index(ipacket, proto_index);



	if(arp_ar_hrd_get_value(ipacket, proto_index) == 0x0001 && arp_ar_pro_get_value(ipacket, proto_index) == 0x0800) {


	} else { 

	/* Get the attribute offset (relative the to protocol) */
	uint32_t retval = sizeof(struct arphdr) + arp_ar_hln_get_value(ipacket, proto_index);


	}


	return retval;
}


uint32_t arp_src_proto_get_length(const ipacket_t * ipacket, int proto_index) {
	uint32_t retval;
	//int proto_offset = get_packet_offset_at_index(ipacket, proto_index);



	if(arp_ar_hrd_get_value(ipacket, proto_index) == 0x0001 && arp_ar_pro_get_value(ipacket, proto_index) == 0x0800) {


	} else { 

	/* Get the attribute length (relative the to protocol) */
	uint32_t retval = arp_ar_pln_get_value(ipacket, proto_index);


	}


	return retval;
}


uint32_t arp_dst_hard_get_offset(const ipacket_t * ipacket, int proto_index) {
	uint32_t retval;
	//uint32_t proto_offset = get_packet_offset_at_index(ipacket, proto_index);



	if(arp_ar_hrd_get_value(ipacket, proto_index) == 0x0001 && arp_ar_pro_get_value(ipacket, proto_index) == 0x0800) {


	} else { 

	/* Get the attribute offset (relative the to protocol) */
	uint32_t retval = sizeof(struct arphdr) + arp_ar_pln_get_value(ipacket, proto_index) + arp_ar_hln_get_value(ipacket, proto_index);


	}


	return retval;
}


uint32_t arp_dst_hard_get_length(const ipacket_t * ipacket, int proto_index) {
	uint32_t retval;
	//int proto_offset = get_packet_offset_at_index(ipacket, proto_index);



	if(arp_ar_hrd_get_value(ipacket, proto_index) == 0x0001 && arp_ar_pro_get_value(ipacket, proto_index) == 0x0800) {


	} else { 

	/* Get the attribute length (relative the to protocol) */
	uint32_t retval = arp_ar_hln_get_value(ipacket, proto_index);


	}


	return retval;
}


uint32_t arp_dst_proto_get_offset(const ipacket_t * ipacket, int proto_index) {
	uint32_t retval;
	//uint32_t proto_offset = get_packet_offset_at_index(ipacket, proto_index);



	if(arp_ar_hrd_get_value(ipacket, proto_index) == 0x0001 && arp_ar_pro_get_value(ipacket, proto_index) == 0x0800) {


	} else { 

	/* Get the attribute offset (relative the to protocol) */
	uint32_t retval = sizeof(struct arphdr) + arp_ar_pln_get_value(ipacket, proto_index) + 2 * arp_ar_hln_get_value(ipacket, proto_index);


	}


	return retval;
}


uint32_t arp_dst_proto_get_length(const ipacket_t * ipacket, int proto_index) {
	uint32_t retval;
	//int proto_offset = get_packet_offset_at_index(ipacket, proto_index);



	if(arp_ar_hrd_get_value(ipacket, proto_index) == 0x0001 && arp_ar_pro_get_value(ipacket, proto_index) == 0x0800) {


	} else { 

	/* Get the attribute length (relative the to protocol) */
	uint32_t retval = arp_ar_pln_get_value(ipacket, proto_index);


	}


	return retval;
}

int mmt_check_arp(ipacket_t * ipacket, unsigned index) {
    
    int offset = get_packet_offset_at_index(ipacket, index);

    const struct ether_header *ethernet = (struct ether_header *) & ipacket->data[offset];

    classified_proto_t retval;
    retval.offset = -1;
    retval.proto_id = -1;
    retval.status = NonClassified;
    if(ntohs(ethernet->ether_type) == 0x0806){
    	retval.proto_id = PROTO_ARP;
        retval.offset = sizeof (struct ether_header);
        retval.status = Classified;	
    }	
    return set_classified_proto(ipacket, index + 1, retval);
    //return retval;
}


int init_arp_proto_struct() {
	protocol_t * protocol_struct = init_protocol_struct_for_registration(PROTO_ARP, PROTO_ARP_ALIAS);

	if (protocol_struct != NULL) {

		int i = 0;
		for(; i < ARP_ATTRIBUTES_NB; i ++) {
			register_attribute_with_protocol(protocol_struct, &arp_attributes_metadata[i]);
		}

		register_classification_function_with_parent_protocol(PROTO_ETHERNET, mmt_check_arp, 50);
		register_protocol_stack(PROTO_ARP, PROTO_ARP_ALIAS, arp_stack_classification);
		return register_protocol(protocol_struct, PROTO_ARP);
	} else {
		return -1;
	}
}

#ifndef CORE
int init_proto() {
	return init_arp_proto_struct();
}
#endif //CORE

