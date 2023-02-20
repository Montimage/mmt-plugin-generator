/* Generated with MMT Plugin Generator 

To compile the plugin: gcc -g -Wall -fPIC -shared -o x_proto_tpkt.so -I /opt/mmt/dpi/include/ -I . tpkt_mmt_plugin.c

To use the plugin: Copy the file x_proto_tpkt.so to /opt/mmt/plugins/
*/


#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "tpkt_mmt_plugin.h"
#include "extraction_lib.h"
#include "tcpip/mmt_tcpip.h"
#include <netinet/tcp.h>



/*
 * TPKT data extraction routines
 */


classified_proto_t tpkt_stack_classification(ipacket_t * ipacket) {
	classified_proto_t retval;
	retval.offset = 0;
	retval.proto_id = PROTO_TPKT;
	retval.status = Classified;
	return retval;
}

int mmt_check_tpkt(ipacket_t * ipacket, unsigned index) {
	int l3_offset = get_packet_offset_at_index(ipacket, index);
    int tpkt_offset = get_packet_offset_at_index(ipacket, index + 1);
	classified_proto_t tpkt_proto = tpkt_stack_classification(ipacket);
	tpkt_proto.offset = tpkt_offset - l3_offset;
	char payload_len = ipacket->p_hdr->caplen - tpkt_offset;
	
	if(payload_len == 0){
		return 0;
	}

	struct tpkthdr * tpkt_header = (struct tpkthdr *)&ipacket->data[tpkt_offset];

	if(ntohs(tpkt_header->length) == payload_len){
		struct tcphdr * tcp = (struct tcphdr*)&ipacket->data[l3_offset];
    	if(tcp!=NULL){
    		if(ntohs(tcp->th_dport) == 102 || ntohs(tcp->th_sport) == 102 ){
    			// printf("TPKT: found TPKT packet %lu\n",ipacket->packet_id);
    			return set_classified_proto(ipacket, index + 1, tpkt_proto);	
    		}
    	}	
	}
	return 0;
}

static attribute_metadata_t tpkt_attributes_metadata[TPKT_ATTRIBUTES_NB] = {

	{TPKT_VERSION, TPKT_VERSION_ALIAS, MMT_U8_DATA, sizeof(uint8_t), 0, SCOPE_PACKET, general_char_extraction},

	{TPKT_RESERVED, TPKT_RESERVED_ALIAS, MMT_U8_DATA, sizeof(uint8_t), 1, SCOPE_PACKET, general_char_extraction},

	{TPKT_LENGTH, TPKT_LENGTH_ALIAS, MMT_U16_DATA, sizeof(uint16_t), 2, SCOPE_PACKET, general_short_extraction_with_ordering_change},

};


int init_tpkt_proto_struct() {
	protocol_t * protocol_struct = init_protocol_struct_for_registration(PROTO_TPKT, PROTO_TPKT_ALIAS);

	if (protocol_struct != NULL) {

		int i = 0;
		for(; i < TPKT_ATTRIBUTES_NB; i ++) {
			register_attribute_with_protocol(protocol_struct, &tpkt_attributes_metadata[i]);
		}
		// register_protocol_stack(PROTO_TPKT, PROTO_TPKT_ALIAS, tpkt_stack_classification);
		if (!register_classification_function_with_parent_protocol(PROTO_TCP, mmt_check_tpkt, 10)) {
			fprintf(stderr, "[err] init_tpkt_proto_struct - cannot register_classification_function_with_parent_protocol\n");
		};
		return register_protocol(protocol_struct, PROTO_TPKT);
	} else {
		return -1;
	}
}

#ifndef CORE
int init_proto() {
	return init_tpkt_proto_struct();
}
#endif //CORE

