/* Generated with MMT Plugin Generator */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "msg_topo_ind_sch_mmt_plugin.h"
#include "extraction_lib.h"



uint8_t msg_topo_ind_sch_lc_channels_nb_get_value(const ipacket_t * ipacket, int proto_index);


uint8_t msg_topo_ind_sch_lp_stations_nb_get_value(const ipacket_t * ipacket, int proto_index);



/*
 * MSG_TOPO_IND_SCH data extraction routines
 */



int msg_topo_ind_sch_management_status_extraction(const ipacket_t * ipacket, int proto_index,
		attribute_t * extracted_data) {
	/* Get the protocol offset */
	int proto_offset = get_packet_offset_at_index(ipacket, proto_index);


	int attribute_offset = msg_topo_ind_sch_attributes_metadata[0].position_in_packet;



	int attribute_length = msg_topo_ind_sch_attributes_metadata[0].data_len;


	struct management_statusreserve_bloc0_byte1 * temp_management_statusreserve_bloc0_byte1 = (struct management_statusreserve_bloc0_byte1 *) & ipacket->data[proto_offset + attribute_offset];

	*((uint8_t *) extracted_data->data) = temp_management_statusreserve_bloc0_byte1->management_status;



	return 1;
}



int msg_topo_ind_sch_reserve_bloc0_byte1_extraction(const ipacket_t * ipacket, int proto_index,
		attribute_t * extracted_data) {
	/* Get the protocol offset */
	int proto_offset = get_packet_offset_at_index(ipacket, proto_index);


	int attribute_offset = msg_topo_ind_sch_attributes_metadata[1].position_in_packet;



	int attribute_length = msg_topo_ind_sch_attributes_metadata[1].data_len;


	struct management_statusreserve_bloc0_byte1 * temp_management_statusreserve_bloc0_byte1 = (struct management_statusreserve_bloc0_byte1 *) & ipacket->data[proto_offset + attribute_offset];

	*((uint8_t *) extracted_data->data) = temp_management_statusreserve_bloc0_byte1->reserve_bloc0_byte1;



	return 1;
}



int msg_topo_ind_sch_reserve_bloc0_byte2_extraction(const ipacket_t * ipacket, int proto_index,
		attribute_t * extracted_data) {
	/* Get the protocol offset */
	int proto_offset = get_packet_offset_at_index(ipacket, proto_index);


	int attribute_offset = msg_topo_ind_sch_attributes_metadata[2].position_in_packet;



	int attribute_length = msg_topo_ind_sch_attributes_metadata[2].data_len;


	struct reserve_bloc0_byte2channel_presencestatusmandatory * temp_reserve_bloc0_byte2channel_presencestatusmandatory = (struct reserve_bloc0_byte2channel_presencestatusmandatory *) & ipacket->data[proto_offset + attribute_offset];

	*((uint8_t *) extracted_data->data) = temp_reserve_bloc0_byte2channel_presencestatusmandatory->reserve_bloc0_byte2;



	return 1;
}



int msg_topo_ind_sch_channel_presence_extraction(const ipacket_t * ipacket, int proto_index,
		attribute_t * extracted_data) {
	/* Get the protocol offset */
	int proto_offset = get_packet_offset_at_index(ipacket, proto_index);


	int attribute_offset = msg_topo_ind_sch_attributes_metadata[3].position_in_packet;



	int attribute_length = msg_topo_ind_sch_attributes_metadata[3].data_len;


	struct reserve_bloc0_byte2channel_presencestatusmandatory * temp_reserve_bloc0_byte2channel_presencestatusmandatory = (struct reserve_bloc0_byte2channel_presencestatusmandatory *) & ipacket->data[proto_offset + attribute_offset];

	*((uint8_t *) extracted_data->data) = temp_reserve_bloc0_byte2channel_presencestatusmandatory->channel_presence;



	return 1;
}



int msg_topo_ind_sch_status_extraction(const ipacket_t * ipacket, int proto_index,
		attribute_t * extracted_data) {
	/* Get the protocol offset */
	int proto_offset = get_packet_offset_at_index(ipacket, proto_index);


	int attribute_offset = msg_topo_ind_sch_attributes_metadata[4].position_in_packet;



	int attribute_length = msg_topo_ind_sch_attributes_metadata[4].data_len;


	struct reserve_bloc0_byte2channel_presencestatusmandatory * temp_reserve_bloc0_byte2channel_presencestatusmandatory = (struct reserve_bloc0_byte2channel_presencestatusmandatory *) & ipacket->data[proto_offset + attribute_offset];

	*((uint8_t *) extracted_data->data) = temp_reserve_bloc0_byte2channel_presencestatusmandatory->status;



	return 1;
}



int msg_topo_ind_sch_mandatory_extraction(const ipacket_t * ipacket, int proto_index,
		attribute_t * extracted_data) {
	/* Get the protocol offset */
	int proto_offset = get_packet_offset_at_index(ipacket, proto_index);


	int attribute_offset = msg_topo_ind_sch_attributes_metadata[5].position_in_packet;



	int attribute_length = msg_topo_ind_sch_attributes_metadata[5].data_len;


	struct reserve_bloc0_byte2channel_presencestatusmandatory * temp_reserve_bloc0_byte2channel_presencestatusmandatory = (struct reserve_bloc0_byte2channel_presencestatusmandatory *) & ipacket->data[proto_offset + attribute_offset];

	*((uint8_t *) extracted_data->data) = temp_reserve_bloc0_byte2channel_presencestatusmandatory->mandatory;



	return 1;
}


classified_proto_t msg_topo_ind_sch_stack_classification(ipacket_t * ipacket) {
	classified_proto_t retval;
	retval.offset = 0;
	retval.proto_id = PROTO_MSG_TOPO_IND_SCH;
	retval.status = Classified;
	return retval;
}

static attribute_metadata_t msg_topo_ind_sch_attributes_metadata[MSG_TOPO_IND_SCH_ATTRIBUTES_NB] = {

	{MSG_TOPO_IND_SCH_MANAGEMENT_STATUS, MSG_TOPO_IND_SCH_MANAGEMENT_STATUS_ALIAS, MMT_U8_DATA, sizeof(uint8_t), 0, SCOPE_PACKET, msg_topo_ind_sch_management_status_extraction},

	{MSG_TOPO_IND_SCH_RESERVE_BLOC0_BYTE1, MSG_TOPO_IND_SCH_RESERVE_BLOC0_BYTE1_ALIAS, MMT_U8_DATA, sizeof(uint8_t), 0, SCOPE_PACKET, msg_topo_ind_sch_reserve_bloc0_byte1_extraction},

	{MSG_TOPO_IND_SCH_RESERVE_BLOC0_BYTE2, MSG_TOPO_IND_SCH_RESERVE_BLOC0_BYTE2_ALIAS, MMT_U8_DATA, sizeof(uint8_t), 1, SCOPE_PACKET, msg_topo_ind_sch_reserve_bloc0_byte2_extraction},

	{MSG_TOPO_IND_SCH_CHANNEL_PRESENCE, MSG_TOPO_IND_SCH_CHANNEL_PRESENCE_ALIAS, MMT_U8_DATA, sizeof(uint8_t), 1, SCOPE_PACKET, msg_topo_ind_sch_channel_presence_extraction},

	{MSG_TOPO_IND_SCH_STATUS, MSG_TOPO_IND_SCH_STATUS_ALIAS, MMT_U8_DATA, sizeof(uint8_t), 1, SCOPE_PACKET, msg_topo_ind_sch_status_extraction},

	{MSG_TOPO_IND_SCH_MANDATORY, MSG_TOPO_IND_SCH_MANDATORY_ALIAS, MMT_U8_DATA, sizeof(uint8_t), 1, SCOPE_PACKET, msg_topo_ind_sch_mandatory_extraction},

	{MSG_TOPO_IND_SCH_NEIGHBORS_NB, MSG_TOPO_IND_SCH_NEIGHBORS_NB_ALIAS, MMT_U8_DATA, sizeof(uint8_t), 3, SCOPE_PACKET, general_char_extraction},

	{MSG_TOPO_IND_SCH_ELEM_K_ALLOC, MSG_TOPO_IND_SCH_ELEM_K_ALLOC_ALIAS, MMT_U8_DATA, sizeof(uint8_t), 4, SCOPE_PACKET, general_char_extraction},

	{MSG_TOPO_IND_SCH_ELEM_J_ALLOC, MSG_TOPO_IND_SCH_ELEM_J_ALLOC_ALIAS, MMT_U8_DATA, sizeof(uint8_t), 5, SCOPE_PACKET, general_char_extraction},

	{MSG_TOPO_IND_SCH_ELEM_C_ALLOC, MSG_TOPO_IND_SCH_ELEM_C_ALLOC_ALIAS, MMT_U8_DATA, sizeof(uint8_t), 6, SCOPE_PACKET, general_char_extraction},

	{MSG_TOPO_IND_SCH_LC_CHANNELS_NB, MSG_TOPO_IND_SCH_LC_CHANNELS_NB_ALIAS, MMT_U8_DATA, sizeof(uint8_t), 7, SCOPE_PACKET, general_char_extraction},

	{MSG_TOPO_IND_SCH_LP_STATIONS_NB, MSG_TOPO_IND_SCH_LP_STATIONS_NB_ALIAS, MMT_U8_DATA, sizeof(uint8_t), 18, SCOPE_PACKET, general_char_extraction},

	{MSG_TOPO_IND_SCH_BLOC0, MSG_TOPO_IND_SCH_BLOC0_ALIAS, MMT_BINARY_DATA, 3, 12, SCOPE_PACKET, general_byte_to_byte_extraction},

	{MSG_TOPO_IND_SCH_BLOC1, MSG_TOPO_IND_SCH_BLOC1_ALIAS, MMT_BINARY_DATA, 3, 18, SCOPE_PACKET, general_byte_to_byte_extraction},

	{MSG_TOPO_IND_SCH_BLOC2, MSG_TOPO_IND_SCH_BLOC2_ALIAS, MMT_BINARY_DATA, 1, 24, SCOPE_PACKET, general_byte_to_byte_extraction},

	{MSG_TOPO_IND_SCH_BLOC3, MSG_TOPO_IND_SCH_BLOC3_ALIAS, MMT_BINARY_DATA, 1, 26, SCOPE_PACKET, general_byte_to_byte_extraction},

};


uint8_t msg_topo_ind_sch_lc_channels_nb_get_value(const ipacket_t * ipacket, int proto_index) {
	uint8_t retval;
	int proto_offset = get_packet_offset_at_index(ipacket, proto_index);
	retval = *(uint8_t *) & ipacket->data[proto_offset + msg_topo_ind_sch_attributes_metadata[10].position_in_packet];
	return retval;
}


uint8_t msg_topo_ind_sch_lp_stations_nb_get_value(const ipacket_t * ipacket, int proto_index) {
	uint8_t retval;
	int proto_offset = get_packet_offset_at_index(ipacket, proto_index);
	retval = *(uint8_t *) & ipacket->data[proto_offset + msg_topo_ind_sch_attributes_metadata[11].position_in_packet];
	return retval;
}


int init_msg_topo_ind_sch_proto_struct() {
	protocol_t * protocol_struct = init_protocol_struct_for_registration(PROTO_MSG_TOPO_IND_SCH, PROTO_MSG_TOPO_IND_SCH_ALIAS);

	if (protocol_struct != NULL) {

		int i = 0;
		for(; i < MSG_TOPO_IND_SCH_ATTRIBUTES_NB; i ++) {
			register_attribute_with_protocol(protocol_struct, &msg_topo_ind_sch_attributes_metadata[i]);
		}


		register_protocol_stack(PROTO_MSG_TOPO_IND_SCH, PROTO_MSG_TOPO_IND_SCH_ALIAS, msg_topo_ind_sch_stack_classification);
		return register_protocol(protocol_struct, PROTO_MSG_TOPO_IND_SCH);
	} else {
		return -1;
	}
}

#ifndef CORE
int init_proto() {
	return init_msg_topo_ind_sch_proto_struct();
}
#endif //CORE

