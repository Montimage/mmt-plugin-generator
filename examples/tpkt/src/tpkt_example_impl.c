/*
 * src/tpkt_example_impl.c: your code for the tpkt_example protocol plugin.
 *
 * TPKT (RFC 1006 section 6) runs over TCP port 102. The TCP header has a
 * variable length (its data offset), so the generated code cannot attach the
 * protocol with a fixed offset: this hook does, as the hand-written
 * plugins/tpkt/tpkt_mmt_plugin.c did (removed by #78; it is in the tree at
 * commit f081d43, examples/README.md).
 */
#include <stdbool.h>
#include <stddef.h>
#include <string.h>

#include "data_defs.h"
#include "plugin_defs.h"
#include "tcpip/mmt_tcpip.h"

#include "tpkt_example_mmt_plugin.h"

#define TPKT_PORT 102

/* A TCP segment to or from port 102 whose payload starts with a TPKT
 * header: version 3 (RFC 1006 section 6) and a length that covers at least
 * the header. */
static mmt_classify_verdict_t classify_after_tcp(ipacket_t *ipacket, unsigned previous_index)
{
    unsigned tcp = (unsigned)get_packet_offset_at_index(ipacket, previous_index);
    unsigned caplen = ipacket->p_hdr->caplen;
    const u_char *data = ipacket->data;
    classified_proto_t next;

    if (tcp > caplen || caplen - tcp < 20) {
        return MMT_CLASSIFY_SKIP;
    }
    unsigned sport = ((unsigned)data[tcp] << 8) | data[tcp + 1];
    unsigned dport = ((unsigned)data[tcp + 2] << 8) | data[tcp + 3];
    unsigned header = (unsigned)(data[tcp + 12] >> 4) * 4;
    if ((sport != TPKT_PORT && dport != TPKT_PORT) || header < 20
        || caplen - tcp < header + 4) {
        return MMT_CLASSIFY_SKIP;
    }
    const u_char *tpkt = data + tcp + header;
    unsigned length = ((unsigned)tpkt[2] << 8) | tpkt[3];
    if (tpkt[0] != 3 || length < 4) {
        return MMT_CLASSIFY_SKIP;
    }
    memset(&next, 0, sizeof(next));
    next.proto_id = PROTO_TPKT_EXAMPLE;
    next.offset = header;
    next.status = Classified;
    if (!set_classified_proto(ipacket, previous_index + 1, next)) {
        return MMT_CLASSIFY_SKIP;
    }
    return MMT_CLASSIFY_MATCHED;
}

/* Attaches the protocol to the parents the generated code does not attach (the model's parents without classify); returns 1, or 0 to fail the load. */
int tpkt_example_hook_register_parents(protocol_t *protocol_struct)
{
    (void)protocol_struct;
    return register_classification_function_with_parent_protocol(PROTO_TCP, classify_after_tcp, 5) ? 1 : 0;
}
