/*
 * src/dns_example_impl.c: your code for the dns_example protocol plugin.
 *
 * DNS (RFC 1035): the generated code extracts every attribute. The model
 * sets session_context, so it has the session data hooks; these keep no data
 * of their own: write a DNS analysis there (a query and its answer).
 *
 * Scaffolded by mmt-plugin from dns_example_mmt_plugin.h, which declares the hooks
 * defined below. This file is yours: generate never writes under src/, so a
 * model change that adds a hook fails the build of the plugin until you
 * define the new hook here (its declaration is in dns_example_mmt_plugin.h).
 */
#include <stdbool.h>
#include <stddef.h>

#include "dns_example_mmt_plugin.h"

/* Creates the session data of a new session (session_context = "true"). */
void dns_example_hook_session_data_init(ipacket_t *ipacket, unsigned index)
{
    (void)ipacket;
    (void)index;
}

/* Frees the session data of a session. */
void dns_example_hook_session_data_cleanup(mmt_session_t *session, unsigned index)
{
    (void)session;
    (void)index;
}

/* Updates the session data from a packet. */
int dns_example_hook_session_data_analysis(ipacket_t *ipacket, unsigned index)
{
    (void)ipacket;
    (void)index;
    return 0;
}

/* Attaches the protocol to the parents the generated code does not attach (the model's parents without classify); returns 1, or 0 to fail the load. */
int dns_example_hook_register_parents(protocol_t *protocol_struct)
{
    (void)protocol_struct;
    /* UDP port 53 (plugin.yaml's parent): the generated code attaches it. */
    return 1;
}
