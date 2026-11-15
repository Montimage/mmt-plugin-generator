/*
 * src/ndn_example_impl.c: your code for the ndn_example protocol plugin.
 *
 * NDN: the generated code extracts every attribute. The model sets session,
 * so it has the session hooks; these keep no session (the sessionizer finds
 * none): write NDN's own session key there (the Name, for example).
 *
 * Scaffolded by mmt-plugin from ndn_example_mmt_plugin.h, which declares the hooks
 * defined below. This file is yours: generate never writes under src/, so a
 * model change that adds a hook fails the build of the plugin until you
 * define the new hook here (its declaration is in ndn_example_mmt_plugin.h).
 */
#include <stdbool.h>
#include <stddef.h>

#include "ndn_example_mmt_plugin.h"

/* Finds or creates the session of a packet (session = "true"); sets *is_new. */
void *ndn_example_hook_sessionizer(mmt_opaque_t protocol_context, ipacket_t *ipacket, unsigned previous_index, int *is_new)
{
    (void)protocol_context;
    (void)ipacket;
    (void)previous_index;
    (void)is_new;
    return NULL;
}

/* Frees a session when it times out. */
int ndn_example_hook_session_cleanup(mmt_opaque_t protocol_context, mmt_session_t *session_context, mmt_opaque_t args)
{
    (void)protocol_context;
    (void)session_context;
    (void)args;
    return 0;
}

/* Compares two session keys. */
bool ndn_example_hook_session_compare(mmt_opaque_t key_1, mmt_opaque_t key_2)
{
    (void)key_1;
    (void)key_2;
    return false;
}

/* Attaches the protocol to the parents the generated code does not attach (the model's parents without classify); returns 1, or 0 to fail the load. */
int ndn_example_hook_register_parents(protocol_t *protocol_struct)
{
    (void)protocol_struct;
    /* EtherType 0x8624 (plugin.yaml's parent): the generated code attaches it. */
    return 1;
}
