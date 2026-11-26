/*
 * src/telem_impl.c: your code for the telem protocol plugin.
 *
 * Scaffolded by mmt-plugin from telem_mmt_plugin.h, which declares the hooks
 * defined below. This file is yours: generate never writes under src/, so a
 * model change that adds a hook fails the build of the plugin until you
 * define the new hook here (its declaration is in telem_mmt_plugin.h).
 */
#include <stdbool.h>
#include <stddef.h>

#include "telem_mmt_plugin.h"

/*
 * readings: a per-session counter of the readings seen. It is not in the
 * packet, and the spec does not say how a session's counter is kept or when
 * it is reported (questions.md, Q2). Until it does, report it absent: 0.
 */
int telem_hook_extract_readings(const ipacket_t *packet, mmt_proto_index_t proto_index, attribute_t *extracted_data)
{
    (void)packet;
    (void)proto_index;
    (void)extracted_data;
    return 0;
}

/* Attaches the protocol to the parents the generated code does not attach (the model's parents without classify); returns 1, or 0 to fail the load. */
int telem_hook_register_parents(protocol_t *protocol_struct)
{
    (void)protocol_struct;
    /*
     * Attach PROTO_TELEM to its parents here. For example, to classify
     * the Ethernet frames whose EtherType is 0x88b5 (IEEE 802 local
     * experimental), add these includes at the top of this file:
     *
     *     #include <string.h>
     *     #include "data_defs.h"
     *     #include "plugin_defs.h"
     *     #include "tcpip/mmt_tcpip.h"
     *
     * then this function, before this one:
     *
     *     static mmt_classify_verdict_t classify_after_ethernet(ipacket_t *ipacket, unsigned previous_index)
     *     {
     *         unsigned offset = get_packet_offset_at_index(ipacket, previous_index);
     *         classified_proto_t next;
     *
     *         if (ipacket->p_hdr->caplen < offset + 14
     *             || ipacket->data[offset + 12] != 0x88
     *             || ipacket->data[offset + 13] != 0xb5) {
     *             return MMT_CLASSIFY_SKIP;
     *         }
     *         memset(&next, 0, sizeof(next));
     *         next.proto_id = PROTO_TELEM;
     *         next.offset = 14;
     *         next.status = Classified;
     *         if (!set_classified_proto(ipacket, previous_index + 1, next)) {
     *             return MMT_CLASSIFY_SKIP;
     *         }
     *         return MMT_CLASSIFY_MATCHED;
     *     }
     *
     * and, in this function:
     *
     *     if (!register_classification_function_with_parent_protocol(PROTO_ETHERNET, classify_after_ethernet, 5)) {
     *         return 0;
     *     }
     *
     * The parent must already be registered: mmt-dpi loads the plugins of a
     * directory in file name order, so the plugin's file must sort after its
     * parent's library (mmtp_telem.so after libmmt_tcpip.so). Otherwise
     * the registration fails, and so does the load.
     *
     * The weight (5 above): a parent runs its classification functions in
     * increasing weight, and mmt-dpi documents weights 0 to 9 and 90 to 100.
     * With mmt-dpi 1.10.2 and a weight of 50, the built-in Ethernet
     * classifier ran first and the frame stayed "ethernet unknown"; 1 and 5
     * worked.
     *
     * Returning 1 without registering a parent loads the plugin, but nothing
     * ever classifies PROTO_TELEM.
     */
    return 1;
}
