/*
 * src/ip_example_impl.c: your code for the ip_example protocol plugin.
 *
 * IPv4 (RFC 791): the generated code extracts every attribute. The model
 * sets context and session, so it has their hooks, which keep no context and
 * no session here, and encapsulation without classify_next, so the next
 * protocol is the classify_next hook.
 *
 * That hook classifies nothing. With mmt-dpi 1.10.2, handing the payload to
 * mmt-dpi's own UDP (PROTO_UDP) after this plugin crashes libmmt_tcpip
 * (udp_pre_classification_function, SIGSEGV): its transport protocols expect
 * mmt-dpi's own IP below them. To hand the payload to a protocol of your
 * own, call set_classified_proto() with its id and the offset IHL * 4.
 *
 * Scaffolded by mmt-plugin from ip_example_mmt_plugin.h, which declares the hooks
 * defined below. This file is yours: generate never writes under src/, so a
 * model change that adds a hook fails the build of the plugin until you
 * define the new hook here (its declaration is in ip_example_mmt_plugin.h).
 */
#include <stdbool.h>
#include <stddef.h>

#include "ip_example_mmt_plugin.h"

/* Creates the protocol context (context = "true"); returns it. */
void *ip_example_hook_context_init(mmt_opaque_t protocol_context, mmt_opaque_t args)
{
    (void)protocol_context;
    (void)args;
    return NULL;
}

/* Frees the protocol context. */
void ip_example_hook_context_cleanup(mmt_opaque_t protocol_context, mmt_opaque_t args)
{
    (void)protocol_context;
    (void)args;
}

/* Finds or creates the session of a packet (session = "true"); sets *is_new. */
void *ip_example_hook_sessionizer(mmt_opaque_t protocol_context, ipacket_t *ipacket, unsigned previous_index, int *is_new)
{
    (void)protocol_context;
    (void)ipacket;
    (void)previous_index;
    (void)is_new;
    return NULL;
}

/* Frees a session when it times out. */
int ip_example_hook_session_cleanup(mmt_opaque_t protocol_context, mmt_session_t *session_context, mmt_opaque_t args)
{
    (void)protocol_context;
    (void)session_context;
    (void)args;
    return 0;
}

/* Compares two session keys. */
bool ip_example_hook_session_compare(mmt_opaque_t key_1, mmt_opaque_t key_2)
{
    (void)key_1;
    (void)key_2;
    return false;
}

/* Classifies the next protocol (encapsulation = "true" without a classifynext block): record it with set_classified_proto() and return the verdict. */
mmt_classify_verdict_t ip_example_hook_classify_next(ipacket_t *ipacket, unsigned previous_index)
{
    (void)ipacket;
    (void)previous_index;
    return MMT_CLASSIFY_SKIP;
}

/* Attaches the protocol to the parents the generated code does not attach (the model's parents without classify); returns 1, or 0 to fail the load. */
int ip_example_hook_register_parents(protocol_t *protocol_struct)
{
    (void)protocol_struct;
    /* EtherType 0x0800 (plugin.yaml's parent): the generated code attaches it. */
    return 1;
}
