/* Generated with MMT Plugin Generator */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "abb_mmt_plugin.h"
#include "extraction_lib.h"
// Add the udp header structure
#include "extraction_lib.h"
#include "tcpip/mmt_tcpip.h"
#include <netinet/udp.h>

/*
 * ABB data extraction routines
 */

classified_proto_t abb_stack_classification(ipacket_t *ipacket)
{
  classified_proto_t retval;
  retval.offset = 0;
  retval.proto_id = PROTO_ABB;
  retval.status = Classified;
  return retval;
}

int mmt_check_abb(ipacket_t *ipacket, unsigned index)
{
  int l3_offset = get_packet_offset_at_index(ipacket, index);
  int abb_offset = get_packet_offset_at_index(ipacket, index + 1);
  classified_proto_t abb_proto = abb_stack_classification(ipacket);
  abb_proto.offset = abb_offset - l3_offset;
  char payload_len = ipacket->p_hdr->caplen - abb_offset;

  if (payload_len == 0)
  {
    return 0;
  }

  struct abb_hdr *abb_header = (struct abb_hdr *)&ipacket->data[abb_offset];
  // if(ipacket->packet_id == 30680) {
    printf("abb: found abb packet %lu\n", ipacket->packet_id);
    printf("abb: ab_header->type %u\n", ntohs(abb_header->type));
    printf("abb: ab_header->size %u\n", ntohs(abb_header->size));
  // }
  if (ntohs(abb_header->type) == 7)
  {
    struct udphdr *udp = (struct udphdr *)&ipacket->data[l3_offset];
    if (udp != NULL)
    {
      if (ntohs(udp->uh_dport) == 12118 || ntohs(udp->uh_sport) == 12118)
      {
        printf("abb: found abb packet %lu\n", ipacket->packet_id);
        return set_classified_proto(ipacket, index + 1, abb_proto);
      }
    }
  }
  return 0;
}

static attribute_metadata_t abb_attributes_metadata[ABB_ATTRIBUTES_NB] = {

    {ABB_SIZE, ABB_SIZE_ALIAS, MMT_U16_DATA, sizeof(uint16_t), 2, SCOPE_PACKET, general_int_extraction_with_ordering_change},

    {ABB_TYPE, ABB_TYPE_ALIAS, MMT_U16_DATA, sizeof(uint16_t), 6, SCOPE_PACKET, general_int_extraction_with_ordering_change},

    {ABB_FRAME_NUMBER, ABB_FRAME_NUMBER_ALIAS, MMT_U16_DATA, sizeof(uint16_t), 10, SCOPE_PACKET, general_int_extraction_with_ordering_change},

    {ABB_CAPTURE_TIME, ABB_CAPTURE_TIME_ALIAS, MMT_U16_DATA, sizeof(uint16_t), 14, SCOPE_PACKET, general_int_extraction_with_ordering_change},

    {ABB_FLAGS_CHECKSUM, ABB_FLAGS_CHECKSUM_ALIAS, MMT_U16_DATA, sizeof(uint16_t), 18, SCOPE_PACKET, general_int_extraction_with_ordering_change},

    {ABB_NUMBER_OF_MARKERS, ABB_NUMBER_OF_MARKERS_ALIAS, MMT_U16_DATA, sizeof(uint16_t), 22, SCOPE_PACKET, general_int_extraction_with_ordering_change},

    {ABB_RESERVED_TIMESTAMP, ABB_RESERVED_TIMESTAMP_ALIAS, MMT_U16_DATA, sizeof(uint16_t), 26, SCOPE_PACKET, general_int_extraction_with_ordering_change},

};

int init_abb_proto_struct()
{
  protocol_t *protocol_struct = init_protocol_struct_for_registration(PROTO_ABB, PROTO_ABB_ALIAS);

  if (protocol_struct != NULL)
  {

    int i = 0;
    for (; i < ABB_ATTRIBUTES_NB; i++)
    {
      register_attribute_with_protocol(protocol_struct, &abb_attributes_metadata[i]);
    }

    if (!register_classification_function_with_parent_protocol(PROTO_UDP, mmt_check_abb, 10))
    {
      fprintf(stderr, "[err] init_abb_proto_struct - cannot register_classification_function_with_parent_protocol\n");
    }
    register_protocol_stack(PROTO_ABB, PROTO_ABB_ALIAS, abb_stack_classification);
    return register_protocol(protocol_struct, PROTO_ABB);
  }
  else
  {
    return -1;
  }
}

#ifndef CORE
int init_proto()
{
  return init_abb_proto_struct();
}
#endif //CORE
