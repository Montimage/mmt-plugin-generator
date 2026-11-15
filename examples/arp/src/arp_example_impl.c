/*
 * src/arp_example_impl.c: your code for the arp_example protocol plugin.
 *
 * ARP (RFC 826): the generated code extracts every attribute, so the only
 * hook is the parent registration.
 *
 * Scaffolded by mmt-plugin from arp_example_mmt_plugin.h, which declares the hooks
 * defined below. This file is yours: generate never writes under src/, so a
 * model change that adds a hook fails the build of the plugin until you
 * define the new hook here (its declaration is in arp_example_mmt_plugin.h).
 */
#include <stdbool.h>
#include <stddef.h>

#include "arp_example_mmt_plugin.h"

/* Attaches the protocol to the parents the generated code does not attach (the model's parents without classify); returns 1, or 0 to fail the load. */
int arp_example_hook_register_parents(protocol_t *protocol_struct)
{
    (void)protocol_struct;
    /* EtherType 0x0806 (plugin.yaml's parent): the generated code attaches it. */
    return 1;
}
