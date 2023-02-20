/* Generated with MMT Plugin Generator 

To compile the plugin: gcc -g -Wall -fPIC -shared -o xx_proto_cotp.so -I /opt/mmt/dpi/include/ -I ../tpkt/ cotp_mmt_plugin.c

To use the plugin: Copy the file xx_proto_cotp.so to /opt/mmt/plugins/

*/

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "cotp_mmt_plugin.h"
#include "extraction_lib.h"
#include "tcpip/mmt_tcpip.h"
#include <netinet/tcp.h>
#include "../tpkt/tpkt_mmt_plugin.h"


/*
 * COTP data extraction routines
 */



classified_proto_t cotp_stack_classification(ipacket_t * ipacket) {
	classified_proto_t retval;
	retval.offset = 0;
	retval.proto_id = PROTO_COTP;
	retval.status = Classified;
	return retval;
}

static attribute_metadata_t cotp_attributes_metadata[COTP_ATTRIBUTES_NB] = {

	{COTP_LENGTH, COTP_LENGTH_ALIAS, MMT_U8_DATA, sizeof(uint8_t), 0, SCOPE_PACKET, general_char_extraction},

	{COTP_PDU_TYPE, COTP_PDU_TYPE_ALIAS, MMT_U8_DATA, sizeof(uint8_t), 1, SCOPE_PACKET, general_char_extraction},

};

int mmt_check_cotp(ipacket_t * ipacket, unsigned index) {
	int l4_offset = get_packet_offset_at_index(ipacket, index);
    int cotp_offset = l4_offset + 4;
    
	classified_proto_t cotp_proto = cotp_stack_classification(ipacket);
	cotp_proto.offset = 4;

	char payload_len = ipacket->p_hdr->caplen - cotp_offset;
	
	if(payload_len == 0){
		return 0;
	}

	struct cotphdr * cotp_header = (struct cotphdr *)&ipacket->data[cotp_offset];

	if(cotp_header->length == 2 || cotp_header->length == 17 ){
    	
    	// printf("COTP: found COTP packet %lu\n",ipacket->packet_id);
    	return set_classified_proto(ipacket, index + 1, cotp_proto);
	}
	return 0;
}



int init_cotp_proto_struct() {
	protocol_t * protocol_struct = init_protocol_struct_for_registration(PROTO_COTP, PROTO_COTP_ALIAS);

	if (protocol_struct != NULL) {

		int i = 0;
		for(; i < COTP_ATTRIBUTES_NB; i ++) {
			register_attribute_with_protocol(protocol_struct, &cotp_attributes_metadata[i]);
		}

		if (!register_classification_function_with_parent_protocol(PROTO_TPKT, mmt_check_cotp, 50)) {
			fprintf(stderr, "[err] init_cotp_proto_struct - cannot register_classification_function_with_parent_protocol\n");
		};

		// register_protocol_stack(PROTO_COTP, PROTO_COTP_ALIAS, cotp_stack_classification);
		return register_protocol(protocol_struct, PROTO_COTP);
	} else {
		return -1;
	}
}

#ifndef CORE
int init_proto() {
	return init_cotp_proto_struct();
}
#endif //CORE

