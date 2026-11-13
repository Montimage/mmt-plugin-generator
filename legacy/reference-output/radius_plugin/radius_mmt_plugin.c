/* Generated with MMT Plugin Generator */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "radius_mmt_plugin.h"
#include "extraction_lib.h"




/*
 * RADIUS data extraction routines
 */



int radius_authenticator_extraction(const ipacket_t * ipacket, int proto_index,
		attribute_t * extracted_data) {
	/* Get the protocol offset */
	int proto_offset = get_packet_offset_at_index(ipacket, proto_index);

	/* Get the attribute offset (relative the to protocol) */
	int attribute_offset = sizeof(struct radiushdr);


	int attribute_length = radius_attributes_metadata[3].data_len;


	*((unsigned int *) extracted_data->data) = attribute_length;
 	memcpy(& ((u_char *) extracted_data->data)[sizeof (int) ], & ipacket->data[proto_offset + attribute_offset], attribute_length);



	return 1;
}



int radius_user_name_extraction(const ipacket_t * ipacket, int proto_index,
		attribute_t * extracted_data) {
	/* Get the protocol offset */
	int proto_offset = get_packet_offset_at_index(ipacket, proto_index);

	/* Get the attribute offset (relative the to protocol) */
	int attribute_offset = null;

	/* Get the attribute data length */
	int attribute_length = null;


	*((unsigned int *) extracted_data->data) = attribute_length;
 	memcpy(& ((u_char *) extracted_data->data)[sizeof (int) ], & ipacket->data[proto_offset + attribute_offset], attribute_length);



	return 1;
}



int radius_user_password_extraction(const ipacket_t * ipacket, int proto_index,
		attribute_t * extracted_data) {
	/* Get the protocol offset */
	int proto_offset = get_packet_offset_at_index(ipacket, proto_index);

	/* Get the attribute offset (relative the to protocol) */
	int attribute_offset = null;

	/* Get the attribute data length */
	int attribute_length = null;


	*((unsigned int *) extracted_data->data) = attribute_length;
 	memcpy(& ((u_char *) extracted_data->data)[sizeof (int) ], & ipacket->data[proto_offset + attribute_offset], attribute_length);



	return 1;
}



int radius_chap_password_extraction(const ipacket_t * ipacket, int proto_index,
		attribute_t * extracted_data) {
	/* Get the protocol offset */
	int proto_offset = get_packet_offset_at_index(ipacket, proto_index);

	/* Get the attribute offset (relative the to protocol) */
	int attribute_offset = null;

	/* Get the attribute data length */
	int attribute_length = null;


	*((unsigned int *) extracted_data->data) = attribute_length;
 	memcpy(& ((u_char *) extracted_data->data)[sizeof (int) ], & ipacket->data[proto_offset + attribute_offset], attribute_length);



	return 1;
}



int radius_nas_ip_address_extraction(const ipacket_t * ipacket, int proto_index,
		attribute_t * extracted_data) {
	/* Get the protocol offset */
	int proto_offset = get_packet_offset_at_index(ipacket, proto_index);

	/* Get the attribute offset (relative the to protocol) */
	int attribute_offset = null;

	/* Get the attribute data length */
	int attribute_length = null;


	*((unsigned int *) extracted_data->data) = ntohl(*((unsigned int *) & ipacket->data[proto_offset + attribute_offset]));



	return 1;
}



int radius_nas_port_extraction(const ipacket_t * ipacket, int proto_index,
		attribute_t * extracted_data) {
	/* Get the protocol offset */
	int proto_offset = get_packet_offset_at_index(ipacket, proto_index);

	/* Get the attribute offset (relative the to protocol) */
	int attribute_offset = null;

	/* Get the attribute data length */
	int attribute_length = null;


	*((unsigned int *) extracted_data->data) = ntohl(*((unsigned int *) & ipacket->data[proto_offset + attribute_offset]));



	return 1;
}



int radius_service_type_extraction(const ipacket_t * ipacket, int proto_index,
		attribute_t * extracted_data) {
	/* Get the protocol offset */
	int proto_offset = get_packet_offset_at_index(ipacket, proto_index);

	/* Get the attribute offset (relative the to protocol) */
	int attribute_offset = null;

	/* Get the attribute data length */
	int attribute_length = null;


	*((unsigned int *) extracted_data->data) = ntohl(*((unsigned int *) & ipacket->data[proto_offset + attribute_offset]));



	return 1;
}



int radius_framed_protocol_extraction(const ipacket_t * ipacket, int proto_index,
		attribute_t * extracted_data) {
	/* Get the protocol offset */
	int proto_offset = get_packet_offset_at_index(ipacket, proto_index);

	/* Get the attribute offset (relative the to protocol) */
	int attribute_offset = null;

	/* Get the attribute data length */
	int attribute_length = null;


	*((unsigned int *) extracted_data->data) = ntohl(*((unsigned int *) & ipacket->data[proto_offset + attribute_offset]));



	return 1;
}



int radius_framed_ip_address_extraction(const ipacket_t * ipacket, int proto_index,
		attribute_t * extracted_data) {
	/* Get the protocol offset */
	int proto_offset = get_packet_offset_at_index(ipacket, proto_index);

	/* Get the attribute offset (relative the to protocol) */
	int attribute_offset = null;

	/* Get the attribute data length */
	int attribute_length = null;


	*((unsigned int *) extracted_data->data) = ntohl(*((unsigned int *) & ipacket->data[proto_offset + attribute_offset]));



	return 1;
}



int radius_framed_ip_netmask_extraction(const ipacket_t * ipacket, int proto_index,
		attribute_t * extracted_data) {
	/* Get the protocol offset */
	int proto_offset = get_packet_offset_at_index(ipacket, proto_index);

	/* Get the attribute offset (relative the to protocol) */
	int attribute_offset = null;

	/* Get the attribute data length */
	int attribute_length = null;


	*((unsigned int *) extracted_data->data) = ntohl(*((unsigned int *) & ipacket->data[proto_offset + attribute_offset]));



	return 1;
}



int radius_framed_mtu_extraction(const ipacket_t * ipacket, int proto_index,
		attribute_t * extracted_data) {
	/* Get the protocol offset */
	int proto_offset = get_packet_offset_at_index(ipacket, proto_index);

	/* Get the attribute offset (relative the to protocol) */
	int attribute_offset = null;

	/* Get the attribute data length */
	int attribute_length = null;


	*((unsigned int *) extracted_data->data) = ntohl(*((unsigned int *) & ipacket->data[proto_offset + attribute_offset]));



	return 1;
}



int radius_callback_number_extraction(const ipacket_t * ipacket, int proto_index,
		attribute_t * extracted_data) {
	/* Get the protocol offset */
	int proto_offset = get_packet_offset_at_index(ipacket, proto_index);

	/* Get the attribute offset (relative the to protocol) */
	int attribute_offset = null;

	/* Get the attribute data length */
	int attribute_length = null;


	*((unsigned int *) extracted_data->data) = attribute_length;
 	memcpy(& ((u_char *) extracted_data->data)[sizeof (int) ], & ipacket->data[proto_offset + attribute_offset], attribute_length);



	return 1;
}



int radius_callback_id_extraction(const ipacket_t * ipacket, int proto_index,
		attribute_t * extracted_data) {
	/* Get the protocol offset */
	int proto_offset = get_packet_offset_at_index(ipacket, proto_index);

	/* Get the attribute offset (relative the to protocol) */
	int attribute_offset = null;

	/* Get the attribute data length */
	int attribute_length = null;


	*((unsigned int *) extracted_data->data) = attribute_length;
 	memcpy(& ((u_char *) extracted_data->data)[sizeof (int) ], & ipacket->data[proto_offset + attribute_offset], attribute_length);



	return 1;
}



int radius_state_extraction(const ipacket_t * ipacket, int proto_index,
		attribute_t * extracted_data) {
	/* Get the protocol offset */
	int proto_offset = get_packet_offset_at_index(ipacket, proto_index);

	/* Get the attribute offset (relative the to protocol) */
	int attribute_offset = null;

	/* Get the attribute data length */
	int attribute_length = null;


	*((unsigned int *) extracted_data->data) = attribute_length;
 	memcpy(& ((u_char *) extracted_data->data)[sizeof (int) ], & ipacket->data[proto_offset + attribute_offset], attribute_length);



	return 1;
}



int radius_class_extraction(const ipacket_t * ipacket, int proto_index,
		attribute_t * extracted_data) {
	/* Get the protocol offset */
	int proto_offset = get_packet_offset_at_index(ipacket, proto_index);

	/* Get the attribute offset (relative the to protocol) */
	int attribute_offset = null;

	/* Get the attribute data length */
	int attribute_length = null;


	*((unsigned int *) extracted_data->data) = attribute_length;
 	memcpy(& ((u_char *) extracted_data->data)[sizeof (int) ], & ipacket->data[proto_offset + attribute_offset], attribute_length);



	return 1;
}



int radius_session_timeout_extraction(const ipacket_t * ipacket, int proto_index,
		attribute_t * extracted_data) {
	/* Get the protocol offset */
	int proto_offset = get_packet_offset_at_index(ipacket, proto_index);

	/* Get the attribute offset (relative the to protocol) */
	int attribute_offset = null;

	/* Get the attribute data length */
	int attribute_length = null;


	*((unsigned int *) extracted_data->data) = ntohl(*((unsigned int *) & ipacket->data[proto_offset + attribute_offset]));



	return 1;
}



int radius_idle_timeout_extraction(const ipacket_t * ipacket, int proto_index,
		attribute_t * extracted_data) {
	/* Get the protocol offset */
	int proto_offset = get_packet_offset_at_index(ipacket, proto_index);

	/* Get the attribute offset (relative the to protocol) */
	int attribute_offset = null;

	/* Get the attribute data length */
	int attribute_length = null;


	*((unsigned int *) extracted_data->data) = ntohl(*((unsigned int *) & ipacket->data[proto_offset + attribute_offset]));



	return 1;
}



int radius_called_station_id_extraction(const ipacket_t * ipacket, int proto_index,
		attribute_t * extracted_data) {
	/* Get the protocol offset */
	int proto_offset = get_packet_offset_at_index(ipacket, proto_index);

	/* Get the attribute offset (relative the to protocol) */
	int attribute_offset = null;

	/* Get the attribute data length */
	int attribute_length = null;


	*((unsigned int *) extracted_data->data) = attribute_length;
 	memcpy(& ((u_char *) extracted_data->data)[sizeof (int) ], & ipacket->data[proto_offset + attribute_offset], attribute_length);



	return 1;
}



int radius_calling_station_id_extraction(const ipacket_t * ipacket, int proto_index,
		attribute_t * extracted_data) {
	/* Get the protocol offset */
	int proto_offset = get_packet_offset_at_index(ipacket, proto_index);

	/* Get the attribute offset (relative the to protocol) */
	int attribute_offset = null;

	/* Get the attribute data length */
	int attribute_length = null;


	*((unsigned int *) extracted_data->data) = attribute_length;
 	memcpy(& ((u_char *) extracted_data->data)[sizeof (int) ], & ipacket->data[proto_offset + attribute_offset], attribute_length);



	return 1;
}



int radius_nas_identifier_extraction(const ipacket_t * ipacket, int proto_index,
		attribute_t * extracted_data) {
	/* Get the protocol offset */
	int proto_offset = get_packet_offset_at_index(ipacket, proto_index);

	/* Get the attribute offset (relative the to protocol) */
	int attribute_offset = null;

	/* Get the attribute data length */
	int attribute_length = null;


	*((unsigned int *) extracted_data->data) = attribute_length;
 	memcpy(& ((u_char *) extracted_data->data)[sizeof (int) ], & ipacket->data[proto_offset + attribute_offset], attribute_length);



	return 1;
}



int radius_acct_status_type_extraction(const ipacket_t * ipacket, int proto_index,
		attribute_t * extracted_data) {
	/* Get the protocol offset */
	int proto_offset = get_packet_offset_at_index(ipacket, proto_index);

	/* Get the attribute offset (relative the to protocol) */
	int attribute_offset = null;

	/* Get the attribute data length */
	int attribute_length = null;


	*((unsigned int *) extracted_data->data) = ntohl(*((unsigned int *) & ipacket->data[proto_offset + attribute_offset]));



	return 1;
}



int radius_acct_delay_time_extraction(const ipacket_t * ipacket, int proto_index,
		attribute_t * extracted_data) {
	/* Get the protocol offset */
	int proto_offset = get_packet_offset_at_index(ipacket, proto_index);

	/* Get the attribute offset (relative the to protocol) */
	int attribute_offset = null;

	/* Get the attribute data length */
	int attribute_length = null;


	*((unsigned int *) extracted_data->data) = ntohl(*((unsigned int *) & ipacket->data[proto_offset + attribute_offset]));



	return 1;
}



int radius_acct_input_octets_extraction(const ipacket_t * ipacket, int proto_index,
		attribute_t * extracted_data) {
	/* Get the protocol offset */
	int proto_offset = get_packet_offset_at_index(ipacket, proto_index);

	/* Get the attribute offset (relative the to protocol) */
	int attribute_offset = null;

	/* Get the attribute data length */
	int attribute_length = null;


	*((unsigned int *) extracted_data->data) = ntohl(*((unsigned int *) & ipacket->data[proto_offset + attribute_offset]));



	return 1;
}



int radius_acct_output_octets_extraction(const ipacket_t * ipacket, int proto_index,
		attribute_t * extracted_data) {
	/* Get the protocol offset */
	int proto_offset = get_packet_offset_at_index(ipacket, proto_index);

	/* Get the attribute offset (relative the to protocol) */
	int attribute_offset = null;

	/* Get the attribute data length */
	int attribute_length = null;


	*((unsigned int *) extracted_data->data) = ntohl(*((unsigned int *) & ipacket->data[proto_offset + attribute_offset]));



	return 1;
}



int radius_acct_session_id_extraction(const ipacket_t * ipacket, int proto_index,
		attribute_t * extracted_data) {
	/* Get the protocol offset */
	int proto_offset = get_packet_offset_at_index(ipacket, proto_index);

	/* Get the attribute offset (relative the to protocol) */
	int attribute_offset = null;

	/* Get the attribute data length */
	int attribute_length = null;


	*((unsigned int *) extracted_data->data) = attribute_length;
 	memcpy(& ((u_char *) extracted_data->data)[sizeof (int) ], & ipacket->data[proto_offset + attribute_offset], attribute_length);



	return 1;
}



int radius_acct_authentic_extraction(const ipacket_t * ipacket, int proto_index,
		attribute_t * extracted_data) {
	/* Get the protocol offset */
	int proto_offset = get_packet_offset_at_index(ipacket, proto_index);

	/* Get the attribute offset (relative the to protocol) */
	int attribute_offset = null;

	/* Get the attribute data length */
	int attribute_length = null;


	*((unsigned int *) extracted_data->data) = ntohl(*((unsigned int *) & ipacket->data[proto_offset + attribute_offset]));



	return 1;
}



int radius_acct_session_time_extraction(const ipacket_t * ipacket, int proto_index,
		attribute_t * extracted_data) {
	/* Get the protocol offset */
	int proto_offset = get_packet_offset_at_index(ipacket, proto_index);

	/* Get the attribute offset (relative the to protocol) */
	int attribute_offset = null;

	/* Get the attribute data length */
	int attribute_length = null;


	*((unsigned int *) extracted_data->data) = ntohl(*((unsigned int *) & ipacket->data[proto_offset + attribute_offset]));



	return 1;
}



int radius_acct_input_packets_extraction(const ipacket_t * ipacket, int proto_index,
		attribute_t * extracted_data) {
	/* Get the protocol offset */
	int proto_offset = get_packet_offset_at_index(ipacket, proto_index);

	/* Get the attribute offset (relative the to protocol) */
	int attribute_offset = null;

	/* Get the attribute data length */
	int attribute_length = null;


	*((unsigned int *) extracted_data->data) = ntohl(*((unsigned int *) & ipacket->data[proto_offset + attribute_offset]));



	return 1;
}



int radius_acct_output_packets_extraction(const ipacket_t * ipacket, int proto_index,
		attribute_t * extracted_data) {
	/* Get the protocol offset */
	int proto_offset = get_packet_offset_at_index(ipacket, proto_index);

	/* Get the attribute offset (relative the to protocol) */
	int attribute_offset = null;

	/* Get the attribute data length */
	int attribute_length = null;


	*((unsigned int *) extracted_data->data) = ntohl(*((unsigned int *) & ipacket->data[proto_offset + attribute_offset]));



	return 1;
}



int radius_acct_terminate_cause_extraction(const ipacket_t * ipacket, int proto_index,
		attribute_t * extracted_data) {
	/* Get the protocol offset */
	int proto_offset = get_packet_offset_at_index(ipacket, proto_index);

	/* Get the attribute offset (relative the to protocol) */
	int attribute_offset = null;

	/* Get the attribute data length */
	int attribute_length = null;


	*((unsigned int *) extracted_data->data) = ntohl(*((unsigned int *) & ipacket->data[proto_offset + attribute_offset]));



	return 1;
}



int radius_event_timestamp_extraction(const ipacket_t * ipacket, int proto_index,
		attribute_t * extracted_data) {
	/* Get the protocol offset */
	int proto_offset = get_packet_offset_at_index(ipacket, proto_index);

	/* Get the attribute offset (relative the to protocol) */
	int attribute_offset = null;

	/* Get the attribute data length */
	int attribute_length = null;


	*((unsigned int *) extracted_data->data) = ntohl(*((unsigned int *) & ipacket->data[proto_offset + attribute_offset]));



	return 1;
}



int radius_nas_port_type_extraction(const ipacket_t * ipacket, int proto_index,
		attribute_t * extracted_data) {
	/* Get the protocol offset */
	int proto_offset = get_packet_offset_at_index(ipacket, proto_index);

	/* Get the attribute offset (relative the to protocol) */
	int attribute_offset = null;

	/* Get the attribute data length */
	int attribute_length = null;


	*((unsigned int *) extracted_data->data) = ntohl(*((unsigned int *) & ipacket->data[proto_offset + attribute_offset]));



	return 1;
}



int radius_message_authenticator_extraction(const ipacket_t * ipacket, int proto_index,
		attribute_t * extracted_data) {
	/* Get the protocol offset */
	int proto_offset = get_packet_offset_at_index(ipacket, proto_index);

	/* Get the attribute offset (relative the to protocol) */
	int attribute_offset = null;

	/* Get the attribute data length */
	int attribute_length = null;


	*((unsigned int *) extracted_data->data) = attribute_length;
 	memcpy(& ((u_char *) extracted_data->data)[sizeof (int) ], & ipacket->data[proto_offset + attribute_offset], attribute_length);



	return 1;
}



int radius_nas_port_id_extraction(const ipacket_t * ipacket, int proto_index,
		attribute_t * extracted_data) {
	/* Get the protocol offset */
	int proto_offset = get_packet_offset_at_index(ipacket, proto_index);

	/* Get the attribute offset (relative the to protocol) */
	int attribute_offset = null;

	/* Get the attribute data length */
	int attribute_length = null;


	*((unsigned int *) extracted_data->data) = attribute_length;
 	memcpy(& ((u_char *) extracted_data->data)[sizeof (int) ], & ipacket->data[proto_offset + attribute_offset], attribute_length);



	return 1;
}



int radius_nas_ipv6_address_extraction(const ipacket_t * ipacket, int proto_index,
		attribute_t * extracted_data) {
	/* Get the protocol offset */
	int proto_offset = get_packet_offset_at_index(ipacket, proto_index);

	/* Get the attribute offset (relative the to protocol) */
	int attribute_offset = null;

	/* Get the attribute data length */
	int attribute_length = null;


	memcpy((u_char *) extracted_data->data, (char *) & ipacket->data[proto_offset + attribute_offset], attribute_length);



	return 1;
}



int radius_framed_interface_id_extraction(const ipacket_t * ipacket, int proto_index,
		attribute_t * extracted_data) {
	/* Get the protocol offset */
	int proto_offset = get_packet_offset_at_index(ipacket, proto_index);

	/* Get the attribute offset (relative the to protocol) */
	int attribute_offset = null;

	/* Get the attribute data length */
	int attribute_length = null;


	memcpy((u_char *) extracted_data->data, (char *) & ipacket->data[proto_offset + attribute_offset], attribute_length);



	return 1;
}



int radius_framed_ipv6_prefix_extraction(const ipacket_t * ipacket, int proto_index,
		attribute_t * extracted_data) {
	/* Get the protocol offset */
	int proto_offset = get_packet_offset_at_index(ipacket, proto_index);

	/* Get the attribute offset (relative the to protocol) */
	int attribute_offset = null;

	/* Get the attribute data length */
	int attribute_length = null;


	memcpy((u_char *) extracted_data->data, (char *) & ipacket->data[proto_offset + attribute_offset], attribute_length);



	return 1;
}



int radius_framed_ipv6_pool_extraction(const ipacket_t * ipacket, int proto_index,
		attribute_t * extracted_data) {
	/* Get the protocol offset */
	int proto_offset = get_packet_offset_at_index(ipacket, proto_index);

	/* Get the attribute offset (relative the to protocol) */
	int attribute_offset = null;

	/* Get the attribute data length */
	int attribute_length = null;


	*((unsigned int *) extracted_data->data) = attribute_length;
 	memcpy(& ((u_char *) extracted_data->data)[sizeof (int) ], & ipacket->data[proto_offset + attribute_offset], attribute_length);



	return 1;
}


classified_proto_t radius_stack_classification(ipacket_t * ipacket) {
	classified_proto_t retval;
	retval.offset = 0;
	retval.proto_id = PROTO_RADIUS;
	retval.status = Classified;
	return retval;
}

static attribute_metadata_t radius_attributes_metadata[RADIUS_ATTRIBUTES_NB] = {

	{RADIUS_CODE, RADIUS_CODE_ALIAS, MMT_U8_DATA, sizeof(uint8_t), 0, SCOPE_PACKET, general_char_extraction},

	{RADIUS_RID, RADIUS_RID_ALIAS, MMT_U8_DATA, sizeof(uint8_t), 1, SCOPE_PACKET, general_char_extraction},

	{RADIUS_RLEN, RADIUS_RLEN_ALIAS, MMT_U16_DATA, sizeof(uint16_t), 2, SCOPE_PACKET, general_short_extraction_with_ordering_change},

	{RADIUS_AUTHENTICATOR, RADIUS_AUTHENTICATOR_ALIAS, MMT_BINARY_DATA, BINARY_64DATA_TYPE_LEN, -2, SCOPE_PACKET, radius_authenticator_extraction},

	{RADIUS_USER_NAME, RADIUS_USER_NAME_ALIAS, MMT_BINARY_DATA, BINARY_64DATA_TYPE_LEN, -2, SCOPE_PACKET, radius_user_name_extraction},

	{RADIUS_USER_PASSWORD, RADIUS_USER_PASSWORD_ALIAS, MMT_BINARY_DATA, BINARY_64DATA_TYPE_LEN, -2, SCOPE_PACKET, radius_user_password_extraction},

	{RADIUS_CHAP_PASSWORD, RADIUS_CHAP_PASSWORD_ALIAS, MMT_BINARY_DATA, BINARY_64DATA_TYPE_LEN, -2, SCOPE_PACKET, radius_chap_password_extraction},

	{RADIUS_NAS_IP_ADDRESS, RADIUS_NAS_IP_ADDRESS_ALIAS, MMT_U32_DATA, sizeof(uint32_t), -2, SCOPE_PACKET, radius_nas_ip_address_extraction},

	{RADIUS_NAS_PORT, RADIUS_NAS_PORT_ALIAS, MMT_U32_DATA, sizeof(uint32_t), -2, SCOPE_PACKET, radius_nas_port_extraction},

	{RADIUS_SERVICE_TYPE, RADIUS_SERVICE_TYPE_ALIAS, MMT_U32_DATA, sizeof(uint32_t), -2, SCOPE_PACKET, radius_service_type_extraction},

	{RADIUS_FRAMED_PROTOCOL, RADIUS_FRAMED_PROTOCOL_ALIAS, MMT_U32_DATA, sizeof(uint32_t), -2, SCOPE_PACKET, radius_framed_protocol_extraction},

	{RADIUS_FRAMED_IP_ADDRESS, RADIUS_FRAMED_IP_ADDRESS_ALIAS, MMT_U32_DATA, sizeof(uint32_t), -2, SCOPE_PACKET, radius_framed_ip_address_extraction},

	{RADIUS_FRAMED_IP_NETMASK, RADIUS_FRAMED_IP_NETMASK_ALIAS, MMT_U32_DATA, sizeof(uint32_t), -2, SCOPE_PACKET, radius_framed_ip_netmask_extraction},

	{RADIUS_FRAMED_MTU, RADIUS_FRAMED_MTU_ALIAS, MMT_U32_DATA, sizeof(uint32_t), -2, SCOPE_PACKET, radius_framed_mtu_extraction},

	{RADIUS_CALLBACK_NUMBER, RADIUS_CALLBACK_NUMBER_ALIAS, MMT_BINARY_DATA, BINARY_64DATA_TYPE_LEN, -2, SCOPE_PACKET, radius_callback_number_extraction},

	{RADIUS_CALLBACK_ID, RADIUS_CALLBACK_ID_ALIAS, MMT_BINARY_DATA, BINARY_64DATA_TYPE_LEN, -2, SCOPE_PACKET, radius_callback_id_extraction},

	{RADIUS_STATE, RADIUS_STATE_ALIAS, MMT_BINARY_DATA, BINARY_64DATA_TYPE_LEN, -2, SCOPE_PACKET, radius_state_extraction},

	{RADIUS_CLASS, RADIUS_CLASS_ALIAS, MMT_BINARY_DATA, BINARY_64DATA_TYPE_LEN, -2, SCOPE_PACKET, radius_class_extraction},

	{RADIUS_SESSION_TIMEOUT, RADIUS_SESSION_TIMEOUT_ALIAS, MMT_U32_DATA, sizeof(uint32_t), -2, SCOPE_PACKET, radius_session_timeout_extraction},

	{RADIUS_IDLE_TIMEOUT, RADIUS_IDLE_TIMEOUT_ALIAS, MMT_U32_DATA, sizeof(uint32_t), -2, SCOPE_PACKET, radius_idle_timeout_extraction},

	{RADIUS_CALLED_STATION_ID, RADIUS_CALLED_STATION_ID_ALIAS, MMT_BINARY_DATA, BINARY_64DATA_TYPE_LEN, -2, SCOPE_PACKET, radius_called_station_id_extraction},

	{RADIUS_CALLING_STATION_ID, RADIUS_CALLING_STATION_ID_ALIAS, MMT_BINARY_DATA, BINARY_64DATA_TYPE_LEN, -2, SCOPE_PACKET, radius_calling_station_id_extraction},

	{RADIUS_NAS_IDENTIFIER, RADIUS_NAS_IDENTIFIER_ALIAS, MMT_BINARY_DATA, BINARY_64DATA_TYPE_LEN, -2, SCOPE_PACKET, radius_nas_identifier_extraction},

	{RADIUS_ACCT_STATUS_TYPE, RADIUS_ACCT_STATUS_TYPE_ALIAS, MMT_U32_DATA, sizeof(uint32_t), -2, SCOPE_PACKET, radius_acct_status_type_extraction},

	{RADIUS_ACCT_DELAY_TIME, RADIUS_ACCT_DELAY_TIME_ALIAS, MMT_U32_DATA, sizeof(uint32_t), -2, SCOPE_PACKET, radius_acct_delay_time_extraction},

	{RADIUS_ACCT_INPUT_OCTETS, RADIUS_ACCT_INPUT_OCTETS_ALIAS, MMT_U32_DATA, sizeof(uint32_t), -2, SCOPE_PACKET, radius_acct_input_octets_extraction},

	{RADIUS_ACCT_OUTPUT_OCTETS, RADIUS_ACCT_OUTPUT_OCTETS_ALIAS, MMT_U32_DATA, sizeof(uint32_t), -2, SCOPE_PACKET, radius_acct_output_octets_extraction},

	{RADIUS_ACCT_SESSION_ID, RADIUS_ACCT_SESSION_ID_ALIAS, MMT_BINARY_DATA, BINARY_64DATA_TYPE_LEN, -2, SCOPE_PACKET, radius_acct_session_id_extraction},

	{RADIUS_ACCT_AUTHENTIC, RADIUS_ACCT_AUTHENTIC_ALIAS, MMT_U32_DATA, sizeof(uint32_t), -2, SCOPE_PACKET, radius_acct_authentic_extraction},

	{RADIUS_ACCT_SESSION_TIME, RADIUS_ACCT_SESSION_TIME_ALIAS, MMT_U32_DATA, sizeof(uint32_t), -2, SCOPE_PACKET, radius_acct_session_time_extraction},

	{RADIUS_ACCT_INPUT_PACKETS, RADIUS_ACCT_INPUT_PACKETS_ALIAS, MMT_U32_DATA, sizeof(uint32_t), -2, SCOPE_PACKET, radius_acct_input_packets_extraction},

	{RADIUS_ACCT_OUTPUT_PACKETS, RADIUS_ACCT_OUTPUT_PACKETS_ALIAS, MMT_U32_DATA, sizeof(uint32_t), -2, SCOPE_PACKET, radius_acct_output_packets_extraction},

	{RADIUS_ACCT_TERMINATE_CAUSE, RADIUS_ACCT_TERMINATE_CAUSE_ALIAS, MMT_U32_DATA, sizeof(uint32_t), -2, SCOPE_PACKET, radius_acct_terminate_cause_extraction},

	{RADIUS_EVENT_TIMESTAMP, RADIUS_EVENT_TIMESTAMP_ALIAS, MMT_U32_DATA, sizeof(uint32_t), -2, SCOPE_PACKET, radius_event_timestamp_extraction},

	{RADIUS_NAS_PORT_TYPE, RADIUS_NAS_PORT_TYPE_ALIAS, MMT_U32_DATA, sizeof(uint32_t), -2, SCOPE_PACKET, radius_nas_port_type_extraction},

	{RADIUS_MESSAGE_AUTHENTICATOR, RADIUS_MESSAGE_AUTHENTICATOR_ALIAS, MMT_BINARY_DATA, BINARY_64DATA_TYPE_LEN, -2, SCOPE_PACKET, radius_message_authenticator_extraction},

	{RADIUS_NAS_PORT_ID, RADIUS_NAS_PORT_ID_ALIAS, MMT_BINARY_DATA, BINARY_64DATA_TYPE_LEN, -2, SCOPE_PACKET, radius_nas_port_id_extraction},

	{RADIUS_NAS_IPV6_ADDRESS, RADIUS_NAS_IPV6_ADDRESS_ALIAS, MMT_DATA_IP6_ADDR, IPv6_ALEN, -2, SCOPE_PACKET, radius_nas_ipv6_address_extraction},

	{RADIUS_FRAMED_INTERFACE_ID, RADIUS_FRAMED_INTERFACE_ID_ALIAS, MMT_DATA_IP6_ADDR, IPv6_ALEN, -2, SCOPE_PACKET, radius_framed_interface_id_extraction},

	{RADIUS_FRAMED_IPV6_PREFIX, RADIUS_FRAMED_IPV6_PREFIX_ALIAS, MMT_DATA_IP6_ADDR, IPv6_ALEN, -2, SCOPE_PACKET, radius_framed_ipv6_prefix_extraction},

	{RADIUS_FRAMED_IPV6_POOL, RADIUS_FRAMED_IPV6_POOL_ALIAS, MMT_BINARY_DATA, BINARY_64DATA_TYPE_LEN, -2, SCOPE_PACKET, radius_framed_ipv6_pool_extraction},

};


int init_radius_proto_struct() {
	protocol_t * protocol_struct = init_protocol_struct_for_registration(PROTO_RADIUS, PROTO_RADIUS_ALIAS);

	if (protocol_struct != NULL) {

		int i = 0;
		for(; i < RADIUS_ATTRIBUTES_NB; i ++) {
			register_attribute_with_protocol(protocol_struct, &radius_attributes_metadata[i]);
		}


		register_protocol_stack(PROTO_RADIUS, PROTO_RADIUS_ALIAS, radius_stack_classification);
		return register_protocol(protocol_struct, PROTO_RADIUS);
	} else {
		return -1;
	}
}

#ifndef CORE
int init_proto() {
	return init_radius_proto_struct();
}
#endif //CORE

