/*
 * src/topo_ind_sch_example_impl.c: your code for the topo_ind_sch_example protocol plugin.
 *
 * MSG_TOPO_IND_SCH: the generated code extracts every attribute, so the only
 * hook is the parent registration.
 *
 * Scaffolded by mmt-plugin from topo_ind_sch_example_mmt_plugin.h, which declares the hooks
 * defined below. This file is yours: generate never writes under src/, so a
 * model change that adds a hook fails the build of the plugin until you
 * define the new hook here (its declaration is in topo_ind_sch_example_mmt_plugin.h).
 */
#include <stdbool.h>
#include <stddef.h>

#include "topo_ind_sch_example_mmt_plugin.h"

/* Attaches the protocol to the parents the generated code does not attach (the model's parents without classify); returns 1, or 0 to fail the load. */
int topo_ind_sch_example_hook_register_parents(protocol_t *protocol_struct)
{
    (void)protocol_struct;
    /* No parent: the model has no published transport. */
    return 1;
}
