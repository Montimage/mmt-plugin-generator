/*
 * src/tcp_example_impl.c: your code for the tcp_example protocol plugin.
 *
 * TCP is IPv4 protocol 6 (RFC 791 section 3.1, RFC 9293). The IPv4 header
 * has a variable length (its IHL), so the generated code cannot attach the
 * protocol with a fixed offset: this hook does.
 *
 * mmt-dpi classifies TCP itself: when this plugin is installed, the weight
 * below (5) makes it run first, so IPv4 TCP packets become tcp_example
 * instead. It is an example: install it in a private prefix only.
 */
#include <stdbool.h>
#include <stddef.h>
#include <string.h>

#include "data_defs.h"
#include "plugin_defs.h"
#include "tcpip/mmt_tcpip.h"

#include "tcp_example_mmt_plugin.h"

#define IPV4_TCP 6

/* An IPv4 packet whose protocol is 6 and whose fragment offset is 0 (only
 * the first fragment starts with the TCP header). */
static mmt_classify_verdict_t classify_after_ip(ipacket_t *ipacket, unsigned previous_index)
{
    unsigned ip = (unsigned)get_packet_offset_at_index(ipacket, previous_index);
    unsigned caplen = ipacket->p_hdr->caplen;
    const u_char *data = ipacket->data;
    classified_proto_t next;
    unsigned header, fragment;

    if (ip > caplen || caplen - ip < 20 || (data[ip] >> 4) != 4) {
        return MMT_CLASSIFY_SKIP;
    }
    header = (unsigned)(data[ip] & 0x0f) * 4;
    fragment = (((unsigned)data[ip + 6] << 8) | data[ip + 7]) & 0x1fff;
    if (data[ip + 9] != IPV4_TCP || header < 20 || fragment != 0 || caplen - ip < header + 20) {
        return MMT_CLASSIFY_SKIP;
    }
    memset(&next, 0, sizeof(next));
    next.proto_id = PROTO_TCP_EXAMPLE;
    next.offset = header;
    next.status = Classified;
    if (!set_classified_proto(ipacket, previous_index + 1, next)) {
        return MMT_CLASSIFY_SKIP;
    }
    return MMT_CLASSIFY_MATCHED;
}

/* Attaches the protocol to the parents the generated code does not attach (the model's parents without classify); returns 1, or 0 to fail the load. */
int tcp_example_hook_register_parents(protocol_t *protocol_struct)
{
    (void)protocol_struct;
    return register_classification_function_with_parent_protocol(PROTO_IP, classify_after_ip, 5) ? 1 : 0;
}
