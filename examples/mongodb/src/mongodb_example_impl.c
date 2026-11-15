/*
 * src/mongodb_example_impl.c: your code for the mongodb_example protocol plugin.
 *
 * MongoDB runs over TCP, port 27017 by default. The TCP header has a
 * variable length (its data offset), so the generated code cannot attach
 * the protocol with a fixed offset: this hook does, as the hand-written
 * plugins/mongodb_src/mongodb_mmt_plugin.c did.
 */
#include <stdbool.h>
#include <stddef.h>
#include <string.h>

#include "data_defs.h"
#include "plugin_defs.h"
#include "tcpip/mmt_tcpip.h"

#include "mongodb_example_mmt_plugin.h"

#define MONGODB_PORT 27017
/* The standard message header: messageLength, requestID, responseTo, opCode. */
#define MONGODB_HEADER 16

/* A TCP segment to or from port 27017 whose payload starts with a message
 * header: messageLength, little-endian, covers at least the header. */
static mmt_classify_verdict_t classify_after_tcp(ipacket_t *ipacket, unsigned previous_index)
{
    unsigned tcp = (unsigned)get_packet_offset_at_index(ipacket, previous_index);
    unsigned caplen = ipacket->p_hdr->caplen;
    const u_char *data = ipacket->data;
    classified_proto_t next;
    unsigned sport, dport, header;
    unsigned long length;

    if (tcp > caplen || caplen - tcp < 20) {
        return MMT_CLASSIFY_SKIP;
    }
    sport = ((unsigned)data[tcp] << 8) | data[tcp + 1];
    dport = ((unsigned)data[tcp + 2] << 8) | data[tcp + 3];
    header = (unsigned)(data[tcp + 12] >> 4) * 4;
    if ((sport != MONGODB_PORT && dport != MONGODB_PORT) || header < 20
        || caplen - tcp < header + MONGODB_HEADER) {
        return MMT_CLASSIFY_SKIP;
    }
    data += tcp + header;
    length = (unsigned long)data[0] | ((unsigned long)data[1] << 8) | ((unsigned long)data[2] << 16)
             | ((unsigned long)data[3] << 24);
    if (length < MONGODB_HEADER) {
        return MMT_CLASSIFY_SKIP;
    }
    memset(&next, 0, sizeof(next));
    next.proto_id = PROTO_MONGODB_EXAMPLE;
    next.offset = header;
    next.status = Classified;
    if (!set_classified_proto(ipacket, previous_index + 1, next)) {
        return MMT_CLASSIFY_SKIP;
    }
    return MMT_CLASSIFY_MATCHED;
}

/* Attaches the protocol to the parents the generated code does not attach (the model's parents without classify); returns 1, or 0 to fail the load. */
int mongodb_example_hook_register_parents(protocol_t *protocol_struct)
{
    (void)protocol_struct;
    return register_classification_function_with_parent_protocol(PROTO_TCP, classify_after_tcp, 5) ? 1 : 0;
}
