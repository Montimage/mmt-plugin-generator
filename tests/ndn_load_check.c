/*
 * Load check for the NDN example plugin (issue #1).
 *
 * Run with MMT_DPI_PLUGINS_DIR pointing at a directory that holds the
 * installed libmmt_tcpip.so and the built example plugin. Exits non-zero
 * if init_extraction() fails or if the example and the built-in NDN
 * dissector do not both resolve to their own id and name.
 */
#include <stdio.h>
#include <string.h>
#include "mmt_core.h"
#include "tcpip/mmt_tcpip.h"
#include "../ndn_src/ndn_mmt_plugin.h"

static int failures = 0;

static void check(int ok, const char *what)
{
    printf("%s: %s\n", ok ? "PASS" : "FAIL", what);
    if (!ok)
        failures++;
}

int main(void)
{
    if (!init_extraction()) {
        printf("FAIL: init_extraction()\n");
        return 1;
    }
    check(1, "init_extraction()");

    const char *name = get_protocol_name_by_id(PROTO_NDN_EXAMPLE);
    check(get_protocol_id_by_name(PROTO_NDN_EXAMPLE_ALIAS) == PROTO_NDN_EXAMPLE,
          "get_protocol_id_by_name(\"ndn_example\") == 980");
    check(is_registered_protocol(PROTO_NDN_EXAMPLE) != 0,
          "is_registered_protocol(980)");
    check(name != NULL && strcmp(name, PROTO_NDN_EXAMPLE_ALIAS) == 0,
          "get_protocol_name_by_id(980) == \"ndn_example\"");
    check(get_protocol_id_by_name(PROTO_NDN_ALIAS) == PROTO_NDN,
          "built-in get_protocol_id_by_name(\"ndn\") == 625");

    close_extraction();
    return failures ? 1 : 0;
}
