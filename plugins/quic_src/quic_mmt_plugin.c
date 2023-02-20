/* Generated with MMT Plugin Generator */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "quic_mmt_plugin.h"
#include "extraction_lib.h"
#include "tcpip/mmt_tcpip.h"
#include <netinet/udp.h>


#define QUIC_NO_V_RES_RSV 0xC3  // 1100 0011

#define QUIC_CID_MASK 0x0C      // 0000 1100
#define QUIC_VER_MASK 0x01      // 0000 0001
#define QUIC_SEQ_MASK 0x30      // 0011 0000

#define CID_LEN_8 0x0C          // 0000 1100
#define CID_LEN_4 0x08          // 0000 1000
#define CID_LEN_1 0x04          // 0000 0100
#define CID_LEN_0 0x00          // 0000 0000

#define SEQ_LEN_6 0x30          // 0011 0000
#define SEQ_LEN_4 0x20          // 0010 0000
#define SEQ_LEN_2 0x10          // 0001 0000
#define SEQ_LEN_1 0x00          // 0000 0000

#define SEQ_CONV(ARR) (ARR[0] | ARR[1] | ARR[2] | ARR[3] | ARR[4] | ARR[5] << 8)


classified_proto_t quic_stack_classification(ipacket_t * ipacket) {
  classified_proto_t retval;
  retval.offset = 0;
  retval.proto_id = PROTO_QUIC;
  retval.status = Classified;
  return retval;
}


static int connect_id(char pflags)
{
  u_int cid_len;

  // Check CID length.
  switch (pflags & QUIC_CID_MASK)
  {
  case CID_LEN_8: cid_len = 8; break;
  case CID_LEN_4: cid_len = 4; break;
  case CID_LEN_1: cid_len = 1; break;
  case CID_LEN_0: cid_len = 0; break;
  default:
    return -1;

  }
  // Return offset.
  return cid_len + 1;
}

static int sequence(char *payload)
{
  unsigned char conv[6] = {0};
  u_int seq_value = -1;
  int seq_lens;
  int cid_offs;
  int i;

  // Search SEQ bytes length.
  switch (payload[0] & QUIC_SEQ_MASK)
  {
  case SEQ_LEN_6: seq_lens = 6; break;
  case SEQ_LEN_4: seq_lens = 4; break;
  case SEQ_LEN_2: seq_lens = 2; break;
  case SEQ_LEN_1: seq_lens = 1; break;
  default:
    return -1;
  }
  // Retrieve SEQ offset.
  cid_offs = connect_id(payload[0]);

  if (cid_offs >= 0 && seq_lens > 0)
  {
    for (i = 0; i < seq_lens; i++)
      conv[i] = payload[cid_offs + i];

    seq_value = SEQ_CONV(conv);
  }

  // Return SEQ dec value;
  return seq_value;
}

int mmt_check_quic(ipacket_t * ipacket, unsigned index)
{
  printf("[inf] mmt_check_quic: %lu - %d\n", ipacket->packet_id, index );
  int l4_offset = get_packet_offset_at_index(ipacket, index);
  // int l4_packet_len = ipacket->p_hdr->caplen - l4_offset;
  struct udphdr * udp = NULL;
  udp = (struct udphdr *) & ipacket->data[l4_offset];
  char * payload = (char*) &ipacket->data[l4_offset + sizeof(struct udphdr)];
  int quic_offset = l4_offset + sizeof(struct udphdr);
  classified_proto_t quic_proto = quic_stack_classification(ipacket);
  quic_proto.offset = quic_offset;
  int ver_offs;
  if (udp != NULL) {
    uint16_t sport = ntohs(udp->source), dport = ntohs(udp->dest);
    // debug("QUIC: Calculating QUIC over UDP");
    if ((((sport == 80) || (dport == 80) || (sport == 443) || (dport == 443))))
    {
      // Settings without version. First check if PUBLIC FLAGS & SEQ bytes are 0x0. SEQ must be 1 at least.
      if ((payload[0] == 0x00 && payload[1] != 0x00) || ((payload[0] & QUIC_NO_V_RES_RSV) == 0))
      {
        int seq = sequence(payload);
        fprintf(stderr, "[PROTO_QUIC] %lu sequence: %d!\n", ipacket->packet_id, seq);
        if (seq < 1)
        {
          fprintf(stderr, "[PROTO_QUIC] %lu mmt_check_quic: Not QUIC!\n", ipacket->packet_id);
        }

        fprintf(stderr, "[PROTO_QUIC] %lu mmt_check_quic: FOUND QUIC!\n", ipacket->packet_id);
        return set_classified_proto(ipacket, index + 1, quic_proto);
      }

      // Check if version, than the CID length.
      else if (payload[0] & QUIC_VER_MASK)
      {
        // Skip CID length.
        ver_offs = connect_id(payload[0]);
        fprintf(stderr, "[PROTO_QUIC] %lu connection id: %d!\n", ipacket->packet_id, ver_offs);
        if (ver_offs >= 0)
        {
          unsigned char vers[] = {payload[ver_offs], payload[ver_offs + 1],
                                  payload[ver_offs + 2], payload[ver_offs + 3]
                                 };

          // Version Match.
          if ((vers[0] == 'Q' && vers[1] == '0') &&
              ((vers[2] == '2' && (vers[3] == '5' || vers[3] == '4' || vers[3] == '3' || vers[3] == '2' ||
                                   vers[3] == '1' || vers[3] == '0')) ||
               (vers[2] == '1' && (vers[3] == '9' || vers[3] == '8' || vers[3] == '7' || vers[3] == '6' ||
                                   vers[3] == '5' || vers[3] == '4' || vers[3] == '3' || vers[3] == '2' ||
                                   vers[3] == '1' || vers[3] == '0')) ||
               (vers[2] == '0' && vers[3] == '9')))

          {
            fprintf(stderr, "[PROTO_QUIC] %lu mmt_check_quic: FOUND QUIC!\n", ipacket->packet_id);
            return set_classified_proto(ipacket, index + 1, quic_proto);
          }
        }
      }
    }
    else
    {
      fprintf(stderr, "[PROTO_QUIC] %lu mmt_check_quic: Not QUIC!\n", ipacket->packet_id);
    }
  }
  fprintf(stderr, "[PROTO_QUIC] %lu mmt_check_quic: Not QUIC!\n", ipacket->packet_id);
  return 0;
}



int mmt_connection_id_extraction(const ipacket_t * ipacket, unsigned proto_index,
                                 attribute_t * extracted_data) {
  int l4_offset = get_packet_offset_at_index(ipacket, proto_index);
  char * payload = (char*) &ipacket->data[l4_offset + sizeof(struct udphdr)];
  int conn_id = connect_id(payload[0]);
  *((uint32_t *) extracted_data->data) = conn_id;
  return 1;
}

int mmt_sequence_extraction(const ipacket_t * ipacket, unsigned proto_index,
                            attribute_t * extracted_data) {
  int l4_offset = get_packet_offset_at_index(ipacket, proto_index);
  char * payload = (char*) &ipacket->data[l4_offset + sizeof(struct udphdr)];
  int seq = sequence(payload);
  *((uint32_t *) extracted_data->data) = seq;
  return 1;
}

static attribute_metadata_t quic_attributes_metadata[QUIC_ATTRIBUTES_NB] = {

  {QUIC_CONNECTION_ID, QUIC_CONNECTION_ID_ALIAS, MMT_U32_DATA, sizeof(uint32_t), 0, SCOPE_PACKET, mmt_connection_id_extraction},

  {QUIC_SEQUENCE, QUIC_SEQUENCE_ALIAS, MMT_U32_DATA, sizeof(uint32_t), 0, SCOPE_PACKET, mmt_sequence_extraction},

};

int init_quic_proto_struct() {
  protocol_t * protocol_struct = init_protocol_struct_for_registration(PROTO_QUIC, PROTO_QUIC_ALIAS);

  if (protocol_struct != NULL) {

    int i = 0;
    for (; i < QUIC_ATTRIBUTES_NB; i ++) {
      register_attribute_with_protocol(protocol_struct, &quic_attributes_metadata[i]);
    }

    if (!register_classification_function_with_parent_protocol(PROTO_UDP, mmt_check_quic, 50)) {
      fprintf(stderr, "[err] init_quic_proto_struct - cannot register_classification_function_with_parent_protocol\n");
    };

    // register_protocol_stack(PROTO_QUIC, PROTO_QUIC_ALIAS, quic_stack_classification);
    return register_protocol(protocol_struct, PROTO_QUIC);
  } else {
    return -1;
  }
}

#ifndef CORE
int init_proto() {
  return init_quic_proto_struct();
}
#endif //CORE

