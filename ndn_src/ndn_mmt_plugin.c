/* Generated with MMT Plugin Generator */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "ndn_mmt_plugin.h"
#include "extraction_lib.h"
#include "tcpip/mmt_tcpip.h"
#include <netinet/tcp.h>


int ndn_TLV_check_type(int type){

    if(type==1) return 1;
    
    if(type < 5 || type > 29 || type == 11) return 0;
    
    return 1;
}

ndn_tlv_t * ndn_TLV_init(){
    ndn_tlv_t *ndn_tlv;
    ndn_tlv = (ndn_tlv_t *)malloc(sizeof(ndn_tlv_t));
    ndn_tlv->type = 0;
    ndn_tlv->length = 0;
    ndn_tlv->nb_octets = 0;
    ndn_tlv->node_offset = 0;
    ndn_tlv->data_offset = 0;
    ndn_tlv->next = NULL;
    return ndn_tlv;
}
 
void ndn_TLV_free(ndn_tlv_t * ndn){

    if(ndn == NULL) return;

    if(ndn->next) ndn_TLV_free(ndn->next);

    free(ndn);
}

ndn_tlv_t * ndn_TLV_parser(char *payload, int offset, int total_length){

    if(payload == NULL) return NULL;

    int type = ndn_TLV_check_type(payload[offset]);

    if(type == 0) {
        debug("Wrong type : %d\n",payload[offset]);
        return NULL;
    }
    
    int first_octet = hex2int(payload[offset + 1]);

    ndn_tlv_t * ndn_new_node = NULL;
    
    if(first_octet == 0 ){
        if(offset + 2 == total_length){
            ndn_new_node = ndn_TLV_init();
            ndn_new_node->type = hex2int(payload[offset]);
            ndn_new_node->length = 0;
            ndn_new_node->node_offset = offset;
            ndn_new_node->data_offset = offset + 2;
            return ndn_new_node;
        }else{
            debug("First octet : %d\n",first_octet);
            // ndn_TLV_free(ndn_new_node);
            return NULL;
        }
    }
    
    ndn_new_node = ndn_TLV_init();
    ndn_new_node->type = hex2int(payload[offset]);
    ndn_new_node->node_offset = offset;
    switch(first_octet){
        // fd
        // 2 octets - 05 ab xx xx 07 yy yy:
        case 253:
        ndn_new_node->nb_octets = 2;
        break;
        // fe
        // 4 octets - 05 ab xx xx xx xx 07 yy yy
        case 254:
        ndn_new_node->nb_octets = 4;
        break;
        // ff
        // 8 octets - 05 ab xx xx xx xx xx xx xx xx 07 yy yy
        case 255:
        ndn_new_node->nb_octets = 8;
        break;
        // 1 octets - 05 xx 07
        default:
        ndn_new_node->nb_octets = 0;
        ndn_new_node->length = first_octet;
        break;
    }
    if(ndn_new_node->nb_octets>0){
        ndn_new_node->length = str_hex2int(payload,offset + 2, offset + 2 + ndn_new_node->nb_octets-1);    
    }
    ndn_new_node->data_offset = offset + 2 + ndn_new_node->nb_octets;

    if(total_length < ndn_new_node->data_offset + ndn_new_node->length){
        // log_err("Not correct length value : %d #  %lu\n",total_length,(ndn_new_node->data_offset + ndn_new_node->length));
        ndn_TLV_free(ndn_new_node);
        return NULL;
    }

    return ndn_new_node;
}


int mmt_check_ndn_payload(char* payload, int packet_len){
    // fprintf(stderr, "\n[debug] NDN - mmt_check_ndn_payload: packet_len - %d",packet_len);
	if(packet_len < 3) return 0;

    // Check the first condition: 05 - interest packet, 06 - data packet
	if (payload[0] != 5 && payload[0] != 6) return 0;

    // Check the second condition: length
	ndn_tlv_t *root  = ndn_TLV_parser(payload, 0, packet_len);

	if(root == NULL)
		return 0;
	if( packet_len != root->data_offset + root->length){
		ndn_TLV_free(root);
		return 0;
	}

	if(payload[root->data_offset] != 7){
		ndn_TLV_free(root);
		return 0;
	}
	return 1;
}

classified_proto_t ndn_stack_classification(ipacket_t * ipacket) {
        classified_proto_t retval;
        retval.offset = 0;
        retval.proto_id = PROTO_NDN;
        retval.status = Classified;
        return retval;
    }

int mmt_check_ndn_tcp(ipacket_t * ipacket, unsigned index) {
	int l3_offset = get_packet_offset_at_index(ipacket, index);
    int ndn_offset = get_packet_offset_at_index(ipacket, index + 1);
    char * payload = (char*)&ipacket->data[ndn_offset];
	classified_proto_t ndn_proto = ndn_stack_classification(ipacket);
	ndn_proto.offset = ndn_offset - l3_offset;
    char payload_len = ipacket->p_hdr->caplen - ndn_offset;
	if(mmt_check_ndn_payload(payload,payload_len)!=0){
		debug("NDN: found ndn packet %lu",ipacket->packet_id);
		return set_classified_proto(ipacket, index + 1, ndn_proto);
	}
	return 0;
}



/**
 * Classify NDN over ETHERNET
 * @param  ipacket packet
 * @param  index   protocol index
 */
int mmt_check_ndn_ethernet(ipacket_t * ipacket, unsigned index) {
    
    int offset = get_packet_offset_at_index(ipacket, index);

    const struct ether_header *ethernet = (struct ether_header *) & ipacket->data[offset];

    classified_proto_t retval;
    retval.offset = -1;
    retval.proto_id = -1;
    retval.status = NonClassified;
    if(ntohs(ethernet->ether_type) == 0x8624){
    	retval.proto_id = PROTO_NDN;
        retval.offset = sizeof (struct ether_header);
        retval.status = Classified;	
    }	
    return set_classified_proto(ipacket, index + 1, retval);
}


/*
 * NDN data extraction routines
 */

int ndn_packet_type_extraction(const ipacket_t * ipacket, unsigned proto_index,
    attribute_t * extracted_data){
    int offset = get_packet_offset_at_index(ipacket, proto_index);
    char *payload = (char*)&ipacket->data[offset];
    uint32_t payload_len = 0;
    payload_len = ipacket->p_hdr->caplen - offset;

    if(payload_len == 0){
        return 0;
    }

    uint8_t ret_v = NDN_UNKNOWN_PACKET;
    if(payload[0] == 5) ret_v = NDN_INTEREST_PACKET;
    else if(payload[0] == 6) ret_v = NDN_DATA_PACKET;
    *((uint8_t*)extracted_data->data) = ret_v;
    return 1;
}

	static attribute_metadata_t ndn_attributes_metadata[NDN_ATTRIBUTES_NB] = {

		{NDN_PACKET_TYPE, NDN_PACKET_TYPE_ALIAS, MMT_U8_DATA, sizeof(uint8_t), 0, SCOPE_PACKET, ndn_packet_type_extraction},

	};


	int init_ndn_proto_struct() {
		protocol_t * protocol_struct = init_protocol_struct_for_registration(PROTO_NDN, PROTO_NDN_ALIAS);

		if (protocol_struct != NULL) {

			int i = 0;
			for(; i < NDN_ATTRIBUTES_NB; i ++) {
				register_attribute_with_protocol(protocol_struct, &ndn_attributes_metadata[i]);
			}
			if(register_classification_function_with_parent_protocol(PROTO_ETHERNET, mmt_check_ndn_ethernet, 50)){
				fprintf(stderr, "\n[err] init_ndn_proto_struct - cannot register_classification_function_with_parent_protocol: PROTO_ETHERNET\n");	
			};
            // Register classification function of NDN protocol after TCP
            if(!register_classification_function_with_parent_protocol(PROTO_TCP, mmt_check_ndn_tcp, 50)){
                fprintf(stderr, "\n[err] init_ndn_proto_struct - cannot register_classification_function_with_parent_protocol: PROTO_TCP\n");
            };
			register_protocol_stack(PROTO_NDN, PROTO_NDN_ALIAS, ndn_stack_classification);
			return register_protocol(protocol_struct, PROTO_NDN);
		} else {
			return -1;
		}
	}

#ifndef CORE
	int init_proto() {
		return init_ndn_proto_struct();
	}
#endif //CORE

