/*
 * src/ethernet_example_impl.c: your code for the ethernet_example protocol plugin.
 *
 * Ethernet (IEEE 802.3): the generated code extracts every attribute and
 * classifies the next protocol, so the only hook is the parent registration.
 *
 * Scaffolded by mmt-plugin from ethernet_example_mmt_plugin.h, which declares the hooks
 * defined below. This file is yours: generate never writes under src/, so a
 * model change that adds a hook fails the build of the plugin until you
 * define the new hook here (its declaration is in ethernet_example_mmt_plugin.h).
 */
#include <stdbool.h>
#include <stddef.h>

#include "ethernet_example_mmt_plugin.h"

/* Attaches the protocol to the parents the generated code does not attach (the model's parents without classify); returns 1, or 0 to fail the load. */
int ethernet_example_hook_register_parents(protocol_t *protocol_struct)
{
    (void)protocol_struct;
    /* No parent: Ethernet is the link layer, which mmt-dpi classifies itself. */
    return 1;
}
