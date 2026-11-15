/*
 * src/cam_example_impl.c: your code for the cam_example protocol plugin.
 *
 * ETSI CAM: the generated code extracts every attribute, so the only hook is
 * the parent registration.
 *
 * Scaffolded by mmt-plugin from cam_example_mmt_plugin.h, which declares the hooks
 * defined below. This file is yours: generate never writes under src/, so a
 * model change that adds a hook fails the build of the plugin until you
 * define the new hook here (its declaration is in cam_example_mmt_plugin.h).
 */
#include <stdbool.h>
#include <stddef.h>

#include "cam_example_mmt_plugin.h"

/* Attaches the protocol to the parents the generated code does not attach (the model's parents without classify); returns 1, or 0 to fail the load. */
int cam_example_hook_register_parents(protocol_t *protocol_struct)
{
    (void)protocol_struct;
    /* UDP payloads that start 02 02 (plugin.yaml's parent): the generated code attaches it. */
    return 1;
}
