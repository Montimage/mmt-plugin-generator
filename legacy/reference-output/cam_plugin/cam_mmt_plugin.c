/* Generated with MMT Plugin Generator */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "cam_mmt_plugin.h"
#include "extraction_lib.h"




/*
 * CAM data extraction routines
 */



int cam_protocolversion_extraction(const ipacket_t * ipacket, int proto_index,
		attribute_t * extracted_data) {
	/* Get the protocol offset */
	int proto_offset = get_packet_offset_at_index(ipacket, proto_index);


	int attribute_offset = cam_attributes_metadata[0].position_in_packet;


	/* Get the attribute data length */
	int attribute_length = sizeof(MMT_U8_DATA);


	*((unsigned char *) extracted_data->data) = *((unsigned char *) & ipacket->data[proto_offset + attribute_offset]);



	return 1;
}



int cam_messageid_extraction(const ipacket_t * ipacket, int proto_index,
		attribute_t * extracted_data) {
	/* Get the protocol offset */
	int proto_offset = get_packet_offset_at_index(ipacket, proto_index);


	int attribute_offset = cam_attributes_metadata[1].position_in_packet;


	/* Get the attribute data length */
	int attribute_length = sizeof(MMT_U8_DATA);


	*((unsigned char *) extracted_data->data) = *((unsigned char *) & ipacket->data[proto_offset + attribute_offset]);



	return 1;
}



int cam_stationid_extraction(const ipacket_t * ipacket, int proto_index,
		attribute_t * extracted_data) {
	/* Get the protocol offset */
	int proto_offset = get_packet_offset_at_index(ipacket, proto_index);


	int attribute_offset = cam_attributes_metadata[2].position_in_packet;


	/* Get the attribute data length */
	int attribute_length = sizeof(MMT_U32_DATA);


	*((unsigned int *) extracted_data->data) = ntohl(*((unsigned int *) & ipacket->data[proto_offset + attribute_offset]));



	return 1;
}



int cam_generationtime_extraction(const ipacket_t * ipacket, int proto_index,
		attribute_t * extracted_data) {
	/* Get the protocol offset */
	int proto_offset = get_packet_offset_at_index(ipacket, proto_index);


	int attribute_offset = cam_attributes_metadata[3].position_in_packet;


	/* Get the attribute data length */
	int attribute_length = sizeof(MMT_U16_DATA);


	*((unsigned short *) extracted_data->data) = ntohs(*((unsigned short *) & ipacket->data[proto_offset + attribute_offset]));



	return 1;
}



int cam_mobileitsstation_extraction(const ipacket_t * ipacket, int proto_index,
		attribute_t * extracted_data) {
	/* Get the protocol offset */
	int proto_offset = get_packet_offset_at_index(ipacket, proto_index);


	int attribute_offset = cam_attributes_metadata[4].position_in_packet;


	/* Get the attribute data length */
	int attribute_length = sizeof(MMT_U8_DATA);


	*((unsigned char *) extracted_data->data) = *((unsigned char *) & ipacket->data[proto_offset + attribute_offset]);



	return 1;
}



int cam_privateitsstation_extraction(const ipacket_t * ipacket, int proto_index,
		attribute_t * extracted_data) {
	/* Get the protocol offset */
	int proto_offset = get_packet_offset_at_index(ipacket, proto_index);


	int attribute_offset = cam_attributes_metadata[5].position_in_packet;


	/* Get the attribute data length */
	int attribute_length = sizeof(MMT_U8_DATA);


	*((unsigned char *) extracted_data->data) = *((unsigned char *) & ipacket->data[proto_offset + attribute_offset]);



	return 1;
}



int cam_physicalrelevantitsstation_extraction(const ipacket_t * ipacket, int proto_index,
		attribute_t * extracted_data) {
	/* Get the protocol offset */
	int proto_offset = get_packet_offset_at_index(ipacket, proto_index);


	int attribute_offset = cam_attributes_metadata[6].position_in_packet;


	/* Get the attribute data length */
	int attribute_length = sizeof(MMT_U8_DATA);


	*((unsigned char *) extracted_data->data) = *((unsigned char *) & ipacket->data[proto_offset + attribute_offset]);



	return 1;
}



int cam_longitude_hem_extraction(const ipacket_t * ipacket, int proto_index,
		attribute_t * extracted_data) {
	/* Get the protocol offset */
	int proto_offset = get_packet_offset_at_index(ipacket, proto_index);


	int attribute_offset = cam_attributes_metadata[7].position_in_packet;


	/* Get the attribute data length */
	int attribute_length = sizeof(MMT_U32_DATA);


	*((unsigned int *) extracted_data->data) = ntohl(*((unsigned int *) & ipacket->data[proto_offset + attribute_offset]));



	return 1;
}



int cam_longitude_deg_extraction(const ipacket_t * ipacket, int proto_index,
		attribute_t * extracted_data) {
	/* Get the protocol offset */
	int proto_offset = get_packet_offset_at_index(ipacket, proto_index);


	int attribute_offset = cam_attributes_metadata[8].position_in_packet;


	/* Get the attribute data length */
	int attribute_length = sizeof(MMT_U32_DATA);


	*((unsigned int *) extracted_data->data) = ntohl(*((unsigned int *) & ipacket->data[proto_offset + attribute_offset]));



	return 1;
}



int cam_latitude_hem_extraction(const ipacket_t * ipacket, int proto_index,
		attribute_t * extracted_data) {
	/* Get the protocol offset */
	int proto_offset = get_packet_offset_at_index(ipacket, proto_index);


	int attribute_offset = cam_attributes_metadata[9].position_in_packet;


	/* Get the attribute data length */
	int attribute_length = sizeof(MMT_U32_DATA);


	*((unsigned int *) extracted_data->data) = ntohl(*((unsigned int *) & ipacket->data[proto_offset + attribute_offset]));



	return 1;
}



int cam_latitude_deg_extraction(const ipacket_t * ipacket, int proto_index,
		attribute_t * extracted_data) {
	/* Get the protocol offset */
	int proto_offset = get_packet_offset_at_index(ipacket, proto_index);


	int attribute_offset = cam_attributes_metadata[10].position_in_packet;


	/* Get the attribute data length */
	int attribute_length = sizeof(MMT_U32_DATA);


	*((unsigned int *) extracted_data->data) = ntohl(*((unsigned int *) & ipacket->data[proto_offset + attribute_offset]));



	return 1;
}



int cam_elevation_extraction(const ipacket_t * ipacket, int proto_index,
		attribute_t * extracted_data) {
	/* Get the protocol offset */
	int proto_offset = get_packet_offset_at_index(ipacket, proto_index);


	int attribute_offset = cam_attributes_metadata[11].position_in_packet;


	/* Get the attribute data length */
	int attribute_length = sizeof(MMT_U32_DATA);


	*((unsigned int *) extracted_data->data) = ntohl(*((unsigned int *) & ipacket->data[proto_offset + attribute_offset]));



	return 1;
}



int cam_direction_extraction(const ipacket_t * ipacket, int proto_index,
		attribute_t * extracted_data) {
	/* Get the protocol offset */
	int proto_offset = get_packet_offset_at_index(ipacket, proto_index);


	int attribute_offset = cam_attributes_metadata[12].position_in_packet;


	/* Get the attribute data length */
	int attribute_length = sizeof(MMT_U16_DATA);


	*((unsigned short *) extracted_data->data) = ntohs(*((unsigned short *) & ipacket->data[proto_offset + attribute_offset]));



	return 1;
}


classified_proto_t cam_stack_classification(ipacket_t * ipacket) {
	classified_proto_t retval;
	retval.offset = 0;
	retval.proto_id = PROTO_CAM;
	retval.status = Classified;
	return retval;
}

static attribute_metadata_t cam_attributes_metadata[CAM_ATTRIBUTES_NB] = {

	{CAM_PROTOCOLVERSION, CAM_PROTOCOLVERSION_ALIAS, MMT_U8_DATA, sizeof(uint8_t), 0, SCOPE_PACKET, cam_protocolversion_extraction},

	{CAM_MESSAGEID, CAM_MESSAGEID_ALIAS, MMT_U8_DATA, sizeof(uint8_t), 1, SCOPE_PACKET, cam_messageid_extraction},

	{CAM_STATIONID, CAM_STATIONID_ALIAS, MMT_U32_DATA, sizeof(uint32_t), 2, SCOPE_PACKET, cam_stationid_extraction},

	{CAM_GENERATIONTIME, CAM_GENERATIONTIME_ALIAS, MMT_U16_DATA, sizeof(uint16_t), 6, SCOPE_PACKET, cam_generationtime_extraction},

	{CAM_MOBILEITSSTATION, CAM_MOBILEITSSTATION_ALIAS, MMT_U8_DATA, sizeof(uint8_t), 10, SCOPE_PACKET, cam_mobileitsstation_extraction},

	{CAM_PRIVATEITSSTATION, CAM_PRIVATEITSSTATION_ALIAS, MMT_U8_DATA, sizeof(uint8_t), 10, SCOPE_PACKET, cam_privateitsstation_extraction},

	{CAM_PHYSICALRELEVANTITSSTATION, CAM_PHYSICALRELEVANTITSSTATION_ALIAS, MMT_U8_DATA, sizeof(uint8_t), 10, SCOPE_PACKET, cam_physicalrelevantitsstation_extraction},

	{CAM_LONGITUDE_HEM, CAM_LONGITUDE_HEM_ALIAS, MMT_U32_DATA, sizeof(uint32_t), 11, SCOPE_PACKET, cam_longitude_hem_extraction},

	{CAM_LONGITUDE_DEG, CAM_LONGITUDE_DEG_ALIAS, MMT_U32_DATA, sizeof(uint32_t), 11, SCOPE_PACKET, cam_longitude_deg_extraction},

	{CAM_LATITUDE_HEM, CAM_LATITUDE_HEM_ALIAS, MMT_U32_DATA, sizeof(uint32_t), 15, SCOPE_PACKET, cam_latitude_hem_extraction},

	{CAM_LATITUDE_DEG, CAM_LATITUDE_DEG_ALIAS, MMT_U32_DATA, sizeof(uint32_t), 15, SCOPE_PACKET, cam_latitude_deg_extraction},

	{CAM_ELEVATION, CAM_ELEVATION_ALIAS, MMT_U32_DATA, sizeof(uint32_t), 19, SCOPE_PACKET, cam_elevation_extraction},

	{CAM_DIRECTION, CAM_DIRECTION_ALIAS, MMT_U16_DATA, sizeof(uint16_t), 22, SCOPE_PACKET, cam_direction_extraction},

};


int init_cam_proto_struct() {
	protocol_t * protocol_struct = init_protocol_struct_for_registration(PROTO_CAM, PROTO_CAM_ALIAS);

	if (protocol_struct != NULL) {

		int i = 0;
		for(; i < CAM_ATTRIBUTES_NB; i ++) {
			register_attribute_with_protocol(protocol_struct, &cam_attributes_metadata[i]);
		}


		register_protocol_stack(PROTO_CAM, PROTO_CAM_ALIAS, cam_stack_classification);
		return register_protocol(protocol_struct, PROTO_CAM);
	} else {
		return -1;
	}
}

#ifndef CORE
int init_proto() {
	return init_cam_proto_struct();
}
#endif //CORE

