/*
 * src/rfc1006_impl.c: your code for the rfc1006 protocol plugin.
 *
 * Scaffolded by mmt-plugin from rfc1006_mmt_plugin.h, then edited (an eval
 * fixture of the mmt-plugin-generator skill): the parent tcp has no classify in
 * plugin.yaml (a classify by port would generate the same), so this hook
 * attaches RFC 1006 to TCP port 102 (RFC 1006 section 5).
 */
#include <stdbool.h>
#include <stddef.h>
#include <string.h>

#include "data_defs.h"
#include "plugin_defs.h"
#include "tcpip/mmt_tcpip.h"

#include "rfc1006_mmt_plugin.h"

#define RFC1006_PORT 102

/* A TCP segment to or from port 102 with a payload: RFC 1006 starts after
 * the TCP header, whose length is the data offset (byte 12, high 4 bits). */
static mmt_classify_verdict_t classify_after_tcp(ipacket_t *ipacket, unsigned previous_index)
{
    unsigned offset = get_packet_offset_at_index(ipacket, previous_index);
    const unsigned char *tcp = ipacket->data + offset;
    unsigned header, sport, dport;
    classified_proto_t next;

    if (ipacket->p_hdr->caplen < offset + 20) {
        return MMT_CLASSIFY_SKIP;
    }
    sport = ((unsigned)tcp[0] << 8) | tcp[1];
    dport = ((unsigned)tcp[2] << 8) | tcp[3];
    header = (unsigned)(tcp[12] >> 4) * 4;
    if ((sport != RFC1006_PORT && dport != RFC1006_PORT) || header < 20
        || ipacket->p_hdr->caplen <= offset + header) {
        return MMT_CLASSIFY_SKIP;
    }
    memset(&next, 0, sizeof(next));
    next.proto_id = PROTO_RFC1006;
    next.offset = header;
    next.status = Classified;
    if (!set_classified_proto(ipacket, previous_index + 1, next)) {
        return MMT_CLASSIFY_SKIP;
    }
    return MMT_CLASSIFY_MATCHED;
}

/* Attaches the protocol to the parents the generated code does not attach (the model's parents without classify); returns 1, or 0 to fail the load. */
int rfc1006_hook_register_parents(protocol_t *protocol_struct)
{
    (void)protocol_struct;
    if (!register_classification_function_with_parent_protocol(PROTO_TCP, classify_after_tcp, 5)) {
        return 0;
    }
    return 1;
}
