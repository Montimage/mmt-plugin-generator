#!/usr/bin/env bash
# Build-and-load check for the NDN example plugin (issue #1).
#
# Usage: MMT_BASE=/opt/mmt bash tests/check_ndn_plugin.sh
#
# MMT_BASE is the mmt-dpi install prefix (headers in $MMT_BASE/dpi/include,
# libraries in $MMT_BASE/dpi/lib, built-in plugins in $MMT_BASE/plugins).
set -euo pipefail

MMT_BASE="${MMT_BASE:-/opt/mmt}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$REPO_ROOT/ndn_src/ndn_mmt_plugin.c"
INC="$MMT_BASE/dpi/include"
LIB="$MMT_BASE/dpi/lib"
CFLAGS=(-Wall -Werror -I "$INC")
# The loader sorts plugins by file name: this one must sort after
# libmmt_tcpip.so so that PROTO_ETHERNET and PROTO_TCP already exist when it
# registers its classifiers. Override it to check another name.
PLUGIN_NAME="${PLUGIN_NAME:-ndn_example.so}"
HDR="$REPO_ROOT/ndn_src/ndn_mmt_plugin.h"

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

fail() { echo "FAIL: $*"; exit 1; }
pass() { echo "PASS: $*"; }

[ -f "$INC/mmt_log.h" ] || fail "$INC/mmt_log.h not found (mmt-dpi >= 1.10.2 required)"
[ -f "$MMT_BASE/plugins/libmmt_tcpip.so" ] || fail "$MMT_BASE/plugins/libmmt_tcpip.so not found"

# 0. Cheap static guards for the two silent mmt-dpi loader behaviours
#    (README, "Plugin load order, ids and names").
# 0a. mmt-dpi loads plugins in scandir(alphasort) order (strcoll, so the
#     host's LC_COLLATE can matter): the file name must sort after
#     libmmt_tcpip.so in the C locale and in the current one.
for loc in C "${LC_ALL:-${LC_COLLATE:-${LANG:-C}}}"; do
    first="$(printf '%s\n' "$PLUGIN_NAME" libmmt_tcpip.so | LC_ALL="$loc" sort | head -n1)"
    if [ "$first" != libmmt_tcpip.so ] || [ "$PLUGIN_NAME" = libmmt_tcpip.so ]; then
        fail "plugin file name $PLUGIN_NAME does not sort after libmmt_tcpip.so (LC_COLLATE=$loc)"
    fi
done
pass "plugin file name $PLUGIN_NAME sorts after libmmt_tcpip.so"

# 0b. The id and name must not be taken by an SDK protocol. Headers list only
#     the SDK's own protocols; the run-time checks in step 3 cover the rest.
PROTO_ID="$(sed -nE 's/^#define[[:space:]]+PROTO_NDN_EXAMPLE[[:space:]]+([0-9]+).*/\1/p' "$HDR")"
PROTO_NAME="$(sed -nE 's/^#define[[:space:]]+PROTO_NDN_EXAMPLE_ALIAS[[:space:]]+"([^"]*)".*/\1/p' "$HDR")"
if [ -z "$PROTO_ID" ] || [ -z "$PROTO_NAME" ]; then
    fail "cannot read PROTO_NDN_EXAMPLE(_ALIAS) from $HDR"
fi
if grep -rhE '#define[[:space:]]+PROTO_[A-Z0-9_]+[[:space:]]+[0-9]+' "$INC" | grep -v MAX_IDENTIFIER \
        | awk -v id="$PROTO_ID" '$3 == id { print; found = 1 } END { exit !found }'; then
    fail "protocol id $PROTO_ID is already defined by the SDK headers"
fi
if grep -rhE '#define[[:space:]]+PROTO_[A-Z0-9_]+_ALIAS[[:space:]]+"' "$INC" \
        | grep -iE "\"$PROTO_NAME\""; then
    fail "protocol name \"$PROTO_NAME\" is already defined by the SDK headers (case-insensitive)"
fi
pass "id $PROTO_ID and name \"$PROTO_NAME\" are not defined by the SDK headers"

# 1. The example compiles cleanly, with and without debug logging.
gcc "${CFLAGS[@]}" -fPIC -shared -o "$WORK/ndn.so" "$SRC" \
    || fail "compile ndn_mmt_plugin.c"
pass "compile ndn_mmt_plugin.c (-Wall -Werror -fPIC -shared)"
gcc "${CFLAGS[@]}" -DMMT_LOG_ENABLE_DEBUG -fPIC -shared -o "$WORK/ndn_debug.so" "$SRC" \
    || fail "compile ndn_mmt_plugin.c with -DMMT_LOG_ENABLE_DEBUG"
pass "compile ndn_mmt_plugin.c with -DMMT_LOG_ENABLE_DEBUG"

# 2. No C source uses the logging/branch macros mmt-dpi 1.10.0 made private.
if grep -rnE '\b(debug|log_err|likely|unlikely)[[:space:]]*\(' \
        --include='*.c' --include='*.h' --exclude-dir=.mmt-prefix "$REPO_ROOT"; then
    fail "unprefixed debug()/log_err()/likely()/unlikely() found (use mmt_log_* / MMT_LIKELY)"
fi
pass "no unprefixed debug()/log_err()/likely()/unlikely()"

# 3. The plugin loads next to the built-in libmmt_tcpip.so without conflict.
gcc "${CFLAGS[@]}" -o "$WORK/ndn_load_check" "$REPO_ROOT/tests/ndn_load_check.c" \
    -L "$LIB" -lmmt_core -ldl || fail "build tests/ndn_load_check.c"
mkdir "$WORK/plugins"
ln -s "$MMT_BASE/plugins/libmmt_tcpip.so" "$WORK/plugins/libmmt_tcpip.so"
cp "$WORK/ndn.so" "$WORK/plugins/$PLUGIN_NAME"
LD_LIBRARY_PATH="$LIB${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" \
    MMT_DPI_PLUGINS_DIR="$WORK/plugins" "$WORK/ndn_load_check" 2> "$WORK/load.err" \
    || { cat "$WORK/load.err"; fail "load $PLUGIN_NAME next to libmmt_tcpip.so"; }
# init_ndn_proto_struct() fails the load (and reports it on stderr) when a
# classifier cannot be attached; this grep is a second line of defence.
if grep -q 'cannot register_classification_function' "$WORK/load.err"; then
    cat "$WORK/load.err"; fail "NDN example classifiers not attached to ETHERNET/TCP"
fi
pass "classifiers attached to PROTO_ETHERNET and PROTO_TCP"

# 4. Only the debug build logs, and it logs through the public mmt-dpi logger.
nm -D "$WORK/ndn_debug.so" | grep -q ' U mmt_log_write' \
    || fail "debug build does not import mmt_log_write"
pass "debug build imports mmt_log_write"
if nm -D "$WORK/ndn.so" | grep -E ' mmt_log_'; then
    fail "release build imports mmt_log_* symbols"
fi
pass "release build imports no mmt_log_* symbol"

# 5. Informational: the debug build loads and logs through the mmt-dpi logger.
cp "$WORK/ndn_debug.so" "$WORK/plugins/$PLUGIN_NAME"
if LD_LIBRARY_PATH="$LIB${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" \
        MMT_DPI_PLUGINS_DIR="$WORK/plugins" MMT_DPI_LOG_LEVEL=debug \
        "$WORK/ndn_load_check" > /dev/null 2>&1; then
    echo "INFO: debug build loads with MMT_DPI_LOG_LEVEL=debug"
else
    echo "INFO: debug build did not load with MMT_DPI_LOG_LEVEL=debug (non-fatal)"
fi

echo "PASS: all checks"
