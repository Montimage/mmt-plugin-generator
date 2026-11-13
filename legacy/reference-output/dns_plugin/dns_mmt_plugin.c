/* Generated with MMT Plugin Generator */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "dns_mmt_plugin.h"
#include "extraction_lib.h"




/*
 * DNS data extraction routines
 */



int dns_qr_extraction(const ipacket_t * ipacket, int proto_index,
		attribute_t * extracted_data) {
	/* Get the protocol offset */
	int proto_offset = get_packet_offset_at_index(ipacket, proto_index);


	int attribute_offset = dns_attributes_metadata[1].position_in_packet;



	int attribute_length = dns_attributes_metadata[1].data_len;


	struct qropcodeaatcrdrazans_authdata_authrcode * temp_qropcodeaatcrdrazans_authdata_authrcode = (struct qropcodeaatcrdrazans_authdata_authrcode *) & ipacket->data[proto_offset + attribute_offset];

	*((uint16_t *) extracted_data->data) = temp_qropcodeaatcrdrazans_authdata_authrcode->qr;



	return 1;
}



int dns_opcode_extraction(const ipacket_t * ipacket, int proto_index,
		attribute_t * extracted_data) {
	/* Get the protocol offset */
	int proto_offset = get_packet_offset_at_index(ipacket, proto_index);


	int attribute_offset = dns_attributes_metadata[2].position_in_packet;



	int attribute_length = dns_attributes_metadata[2].data_len;


	struct qropcodeaatcrdrazans_authdata_authrcode * temp_qropcodeaatcrdrazans_authdata_authrcode = (struct qropcodeaatcrdrazans_authdata_authrcode *) & ipacket->data[proto_offset + attribute_offset];

	*((uint16_t *) extracted_data->data) = temp_qropcodeaatcrdrazans_authdata_authrcode->opcode;



	return 1;
}



int dns_aa_extraction(const ipacket_t * ipacket, int proto_index,
		attribute_t * extracted_data) {
	/* Get the protocol offset */
	int proto_offset = get_packet_offset_at_index(ipacket, proto_index);


	int attribute_offset = dns_attributes_metadata[3].position_in_packet;



	int attribute_length = dns_attributes_metadata[3].data_len;


	struct qropcodeaatcrdrazans_authdata_authrcode * temp_qropcodeaatcrdrazans_authdata_authrcode = (struct qropcodeaatcrdrazans_authdata_authrcode *) & ipacket->data[proto_offset + attribute_offset];

	*((uint16_t *) extracted_data->data) = temp_qropcodeaatcrdrazans_authdata_authrcode->aa;



	return 1;
}



int dns_tc_extraction(const ipacket_t * ipacket, int proto_index,
		attribute_t * extracted_data) {
	/* Get the protocol offset */
	int proto_offset = get_packet_offset_at_index(ipacket, proto_index);


	int attribute_offset = dns_attributes_metadata[4].position_in_packet;



	int attribute_length = dns_attributes_metadata[4].data_len;


	struct qropcodeaatcrdrazans_authdata_authrcode * temp_qropcodeaatcrdrazans_authdata_authrcode = (struct qropcodeaatcrdrazans_authdata_authrcode *) & ipacket->data[proto_offset + attribute_offset];

	*((uint16_t *) extracted_data->data) = temp_qropcodeaatcrdrazans_authdata_authrcode->tc;



	return 1;
}



int dns_rd_extraction(const ipacket_t * ipacket, int proto_index,
		attribute_t * extracted_data) {
	/* Get the protocol offset */
	int proto_offset = get_packet_offset_at_index(ipacket, proto_index);


	int attribute_offset = dns_attributes_metadata[5].position_in_packet;



	int attribute_length = dns_attributes_metadata[5].data_len;


	struct qropcodeaatcrdrazans_authdata_authrcode * temp_qropcodeaatcrdrazans_authdata_authrcode = (struct qropcodeaatcrdrazans_authdata_authrcode *) & ipacket->data[proto_offset + attribute_offset];

	*((uint16_t *) extracted_data->data) = temp_qropcodeaatcrdrazans_authdata_authrcode->rd;



	return 1;
}



int dns_ra_extraction(const ipacket_t * ipacket, int proto_index,
		attribute_t * extracted_data) {
	/* Get the protocol offset */
	int proto_offset = get_packet_offset_at_index(ipacket, proto_index);


	int attribute_offset = dns_attributes_metadata[6].position_in_packet;



	int attribute_length = dns_attributes_metadata[6].data_len;


	struct qropcodeaatcrdrazans_authdata_authrcode * temp_qropcodeaatcrdrazans_authdata_authrcode = (struct qropcodeaatcrdrazans_authdata_authrcode *) & ipacket->data[proto_offset + attribute_offset];

	*((uint16_t *) extracted_data->data) = temp_qropcodeaatcrdrazans_authdata_authrcode->ra;



	return 1;
}



int dns_z_extraction(const ipacket_t * ipacket, int proto_index,
		attribute_t * extracted_data) {
	/* Get the protocol offset */
	int proto_offset = get_packet_offset_at_index(ipacket, proto_index);


	int attribute_offset = dns_attributes_metadata[7].position_in_packet;



	int attribute_length = dns_attributes_metadata[7].data_len;


	struct qropcodeaatcrdrazans_authdata_authrcode * temp_qropcodeaatcrdrazans_authdata_authrcode = (struct qropcodeaatcrdrazans_authdata_authrcode *) & ipacket->data[proto_offset + attribute_offset];

	*((uint16_t *) extracted_data->data) = temp_qropcodeaatcrdrazans_authdata_authrcode->z;



	return 1;
}



int dns_ans_auth_extraction(const ipacket_t * ipacket, int proto_index,
		attribute_t * extracted_data) {
	/* Get the protocol offset */
	int proto_offset = get_packet_offset_at_index(ipacket, proto_index);


	int attribute_offset = dns_attributes_metadata[8].position_in_packet;



	int attribute_length = dns_attributes_metadata[8].data_len;


	struct qropcodeaatcrdrazans_authdata_authrcode * temp_qropcodeaatcrdrazans_authdata_authrcode = (struct qropcodeaatcrdrazans_authdata_authrcode *) & ipacket->data[proto_offset + attribute_offset];

	*((uint16_t *) extracted_data->data) = temp_qropcodeaatcrdrazans_authdata_authrcode->ans_auth;



	return 1;
}



int dns_data_auth_extraction(const ipacket_t * ipacket, int proto_index,
		attribute_t * extracted_data) {
	/* Get the protocol offset */
	int proto_offset = get_packet_offset_at_index(ipacket, proto_index);


	int attribute_offset = dns_attributes_metadata[9].position_in_packet;



	int attribute_length = dns_attributes_metadata[9].data_len;


	struct qropcodeaatcrdrazans_authdata_authrcode * temp_qropcodeaatcrdrazans_authdata_authrcode = (struct qropcodeaatcrdrazans_authdata_authrcode *) & ipacket->data[proto_offset + attribute_offset];

	*((uint16_t *) extracted_data->data) = temp_qropcodeaatcrdrazans_authdata_authrcode->data_auth;



	return 1;
}



int dns_rcode_extraction(const ipacket_t * ipacket, int proto_index,
		attribute_t * extracted_data) {
	/* Get the protocol offset */
	int proto_offset = get_packet_offset_at_index(ipacket, proto_index);


	int attribute_offset = dns_attributes_metadata[10].position_in_packet;



	int attribute_length = dns_attributes_metadata[10].data_len;


	struct qropcodeaatcrdrazans_authdata_authrcode * temp_qropcodeaatcrdrazans_authdata_authrcode = (struct qropcodeaatcrdrazans_authdata_authrcode *) & ipacket->data[proto_offset + attribute_offset];

	*((uint16_t *) extracted_data->data) = temp_qropcodeaatcrdrazans_authdata_authrcode->rcode;



	return 1;
}


classified_proto_t dns_stack_classification(ipacket_t * ipacket) {
	classified_proto_t retval;
	retval.offset = 0;
	retval.proto_id = PROTO_DNS;
	retval.status = Classified;
	return retval;
}

static attribute_metadata_t dns_attributes_metadata[DNS_ATTRIBUTES_NB] = {

	{DNS_TID, DNS_TID_ALIAS, MMT_U16_DATA, sizeof(uint16_t), 0, SCOPE_PACKET, general_short_extraction_with_ordering_change},

	{DNS_QR, DNS_QR_ALIAS, MMT_U16_DATA, sizeof(uint16_t), 2, SCOPE_PACKET, dns_qr_extraction},

	{DNS_OPCODE, DNS_OPCODE_ALIAS, MMT_U16_DATA, sizeof(uint16_t), 2, SCOPE_PACKET, dns_opcode_extraction},

	{DNS_AA, DNS_AA_ALIAS, MMT_U16_DATA, sizeof(uint16_t), 2, SCOPE_PACKET, dns_aa_extraction},

	{DNS_TC, DNS_TC_ALIAS, MMT_U16_DATA, sizeof(uint16_t), 2, SCOPE_PACKET, dns_tc_extraction},

	{DNS_RD, DNS_RD_ALIAS, MMT_U16_DATA, sizeof(uint16_t), 2, SCOPE_PACKET, dns_rd_extraction},

	{DNS_RA, DNS_RA_ALIAS, MMT_U16_DATA, sizeof(uint16_t), 2, SCOPE_PACKET, dns_ra_extraction},

	{DNS_Z, DNS_Z_ALIAS, MMT_U16_DATA, sizeof(uint16_t), 2, SCOPE_PACKET, dns_z_extraction},

	{DNS_ANS_AUTH, DNS_ANS_AUTH_ALIAS, MMT_U16_DATA, sizeof(uint16_t), 2, SCOPE_PACKET, dns_ans_auth_extraction},

	{DNS_DATA_AUTH, DNS_DATA_AUTH_ALIAS, MMT_U16_DATA, sizeof(uint16_t), 2, SCOPE_PACKET, dns_data_auth_extraction},

	{DNS_RCODE, DNS_RCODE_ALIAS, MMT_U16_DATA, sizeof(uint16_t), 2, SCOPE_PACKET, dns_rcode_extraction},

	{DNS_QDCOUNT, DNS_QDCOUNT_ALIAS, MMT_U16_DATA, sizeof(uint16_t), 6, SCOPE_PACKET, general_short_extraction_with_ordering_change},

	{DNS_ANCOUNT, DNS_ANCOUNT_ALIAS, MMT_U16_DATA, sizeof(uint16_t), 8, SCOPE_PACKET, general_short_extraction_with_ordering_change},

	{DNS_NSCOUNT, DNS_NSCOUNT_ALIAS, MMT_U16_DATA, sizeof(uint16_t), 10, SCOPE_PACKET, general_short_extraction_with_ordering_change},

	{DNS_ARCOUNT, DNS_ARCOUNT_ALIAS, MMT_U16_DATA, sizeof(uint16_t), 12, SCOPE_PACKET, general_short_extraction_with_ordering_change},

};



void dns_session_data_init(ipacket_t * ipacket, int index) {
	/* User specific code goes here */
}

void dns_session_data_cleanup(mmt_session_t * session, int index) {
	/* User specific code goes here */
}
void dns_session_data_analysis(ipacket_t * ipacket, int index) {
	/* User specific code goes here */
}

int init_dns_proto_struct() {
	protocol_t * protocol_struct = init_protocol_struct_for_registration(PROTO_DNS, PROTO_DNS_ALIAS);

	if (protocol_struct != NULL) {

		int i = 0;
		for(; i < DNS_ATTRIBUTES_NB; i ++) {
			register_attribute_with_protocol(protocol_struct, &dns_attributes_metadata[i]);
		}


		 /* Session context specific initializations */
		register_session_data_initialization_function(protocol_struct, dns_session_data_init);
		register_session_data_cleanup_function(protocol_struct, dns_session_data_cleanup);
		register_session_data_analysis_function(protocol_struct, dns_session_data_analysis);

		register_protocol_stack(PROTO_DNS, PROTO_DNS_ALIAS, dns_stack_classification);
		return register_protocol(protocol_struct, PROTO_DNS);
	} else {
		return -1;
	}
}

#ifndef CORE
int init_proto() {
	return init_dns_proto_struct();
}
#endif //CORE

