/* Generated with MMT Plugin Generator */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "abb_camera_mmt_plugin.h"
#include "extraction_lib.h"

#include "tcpip/mmt_tcpip.h"
#include <netinet/udp.h>

/*
 * ABB_CAMERA data extraction routines
 */

classified_proto_t abb_camera_stack_classification(ipacket_t *ipacket)
{
	classified_proto_t retval;
	retval.offset = 0;
	retval.proto_id = PROTO_ABB_CAMERA;
	retval.status = Classified;
	return retval;
}

int mmt_check_abb(ipacket_t *ipacket, unsigned index)
{

	//fprintf(stderr,"mmt_check_abb fucntion\n");

	//printf("[inf] mmt_check_abb: %lu - %d\n", ipacket->packet_id, index );
	int l4_offset = get_packet_offset_at_index(ipacket, index);
	// int l4_packet_len = ipacket->p_hdr->caplen - l4_offset;
	struct udphdr *udp = NULL;
	udp = (struct udphdr *)&ipacket->data[l4_offset];
	int abb_offset = l4_offset + sizeof(struct udphdr);
	classified_proto_t abb_proto = abb_camera_stack_classification(ipacket);
	abb_proto.offset = abb_offset;

	if (udp != NULL)
	{
		uint16_t sport = ntohs(udp->source), dport = ntohs(udp->dest);
		// debug("QUIC: Calculating QUIC over UDP");
		if (((sport == 4868) && (dport == 12118))) //Clasification of packet
		{
			struct abbcamera *abb_header = (struct abbcamera *)&ipacket->data[abb_offset];

			printf("[inf] mmt_check_abb: %lu - %d\n", ipacket->packet_id, index);
			printf("Size: %i bytes, type: %i, Marker number: %i \n ", ntohl(abb_header->size), ntohl(abb_header->type), ntohl(abb_header->marker_number));
			fprintf(stderr, "[PROTO_ABB_CAMERA] %lu mmt_check_abb: FOUND ABB!\n", ipacket->packet_id);

			return set_classified_proto(ipacket, index + 1, abb_proto);
		}
	}
	//fprintf(stderr, "[PROTO_ABB_CAMERA] %lu mmt_check_abb: Not ABB!\n", ipacket->packet_id);
	return 0;
}

static attribute_metadata_t abb_camera_attributes_metadata[ABB_CAMERA_ATTRIBUTES_NB] = {

		{ABB_CAMERA_SIZE, ABB_CAMERA_SIZE_ALIAS, MMT_U32_DATA, sizeof(int), 0, SCOPE_PACKET, general_int_extraction_with_ordering_change},

		{ABB_CAMERA_TYPE, ABB_CAMERA_TYPE_ALIAS, MMT_U32_DATA, sizeof(int), 4, SCOPE_PACKET, general_int_extraction_with_ordering_change},

		{ABB_CAMERA_FRAME_NUMBER, ABB_CAMERA_FRAME_NUMBER_ALIAS, MMT_U32_DATA, sizeof(int), 8, SCOPE_PACKET, general_int_extraction_with_ordering_change},

		{ABB_CAMERA_TIME01, ABB_CAMERA_TIME01_ALIAS, MMT_U32_DATA, sizeof(int), 12, SCOPE_PACKET, general_int_extraction_with_ordering_change},

		{ABB_CAMERA_TIME02, ABB_CAMERA_TIME02_ALIAS, MMT_U32_DATA, sizeof(int), 16, SCOPE_PACKET, general_int_extraction_with_ordering_change},

		{ABB_CAMERA_FLAGS_CHECKSUM, ABB_CAMERA_FLAGS_CHECKSUM_ALIAS, MMT_U32_DATA, sizeof(int), 20, SCOPE_PACKET, general_int_extraction_with_ordering_change},

		{ABB_CAMERA_MARKER_NUMBER, ABB_CAMERA_MARKER_NUMBER_ALIAS, MMT_U32_DATA, sizeof(int), 24, SCOPE_PACKET, general_int_extraction_with_ordering_change},

		{ABB_CAMERA_RESERVED0, ABB_CAMERA_RESERVED0_ALIAS, MMT_U32_DATA, sizeof(int), 28, SCOPE_PACKET, general_int_extraction_with_ordering_change},

		{ABB_CAMERA_RESERVED1, ABB_CAMERA_RESERVED1_ALIAS, MMT_U32_DATA, sizeof(int), 32, SCOPE_PACKET, general_int_extraction_with_ordering_change},

		{ABB_CAMERA_MARKERS, ABB_CAMERA_MARKERS_ALIAS, MMT_DATA_POINTER, 4, 36, SCOPE_PACKET, general_byte_to_byte_extraction},

};

int init_abb_camera_proto_struct()
{
	protocol_t *protocol_struct = init_protocol_struct_for_registration(PROTO_ABB_CAMERA, PROTO_ABB_CAMERA_ALIAS);

	if (protocol_struct != NULL)
	{
		int i = 0;
		for (; i < ABB_CAMERA_ATTRIBUTES_NB; i++)
		{
			register_attribute_with_protocol(protocol_struct, &abb_camera_attributes_metadata[i]);
		}

		if (!register_classification_function_with_parent_protocol(PROTO_UDP, mmt_check_abb, 10))
		{
			fprintf(stderr, "[err] init_abb_camera_proto_struct - cannot register_classification_function_with_parent_protocol\n");
		};
		//register_protocol_stack(PROTO_ABB_CAMERA, PROTO_ABB_CAMERA_ALIAS, abb_camera_stack_classification);
		return register_protocol(protocol_struct, PROTO_ABB_CAMERA);
	}
	else
	{
		return -1;
	}
}

#ifndef CORE
int init_proto()
{

	return init_abb_camera_proto_struct();
}
#endif //CORE
