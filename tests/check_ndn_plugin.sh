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
# registers its classifiers.
PLUGIN_NAME="ndn_example.so"

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

fail() { echo "FAIL: $*"; exit 1; }
pass() { echo "PASS: $*"; }

[ -f "$INC/mmt_log.h" ] || fail "$INC/mmt_log.h not found (mmt-dpi >= 1.10.2 required)"
[ -f "$MMT_BASE/plugins/libmmt_tcpip.so" ] || fail "$MMT_BASE/plugins/libmmt_tcpip.so not found"

# 1. The example compiles cleanly, with and without debug logging.
gcc "${CFLAGS[@]}" -fPIC -shared -o "$WORK/ndn.so" "$SRC" \
    || fail "compile ndn_mmt_plugin.c"
pass "compile ndn_mmt_plugin.c (-Wall -Werror -fPIC -shared)"
gcc "${CFLAGS[@]}" -DMMT_LOG_ENABLE_DEBUG -fPIC -shared -o "$WORK/ndn_debug.so" "$SRC" \
    || fail "compile ndn_mmt_plugin.c with -DMMT_LOG_ENABLE_DEBUG"
pass "compile ndn_mmt_plugin.c with -DMMT_LOG_ENABLE_DEBUG"

# 2. No C source uses the logging/branch macros mmt-dpi 1.10.0 made private.
if grep -rnE '\b(debug|log_err|likely|unlikely)\(' \
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
# init_ndn_proto_struct() reports a classifier it could not attach on stderr.
if grep -q 'cannot register_classification_function' "$WORK/load.err"; then
    cat "$WORK/load.err"; fail "NDN example classifiers not attached to ETHERNET/TCP"
fi
pass "classifiers attached to PROTO_ETHERNET and PROTO_TCP"

# 4. Informational: the debug build loads and logs through the mmt-dpi logger.
cp "$WORK/ndn_debug.so" "$WORK/plugins/$PLUGIN_NAME"
if LD_LIBRARY_PATH="$LIB${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" \
        MMT_DPI_PLUGINS_DIR="$WORK/plugins" MMT_DPI_LOG_LEVEL=debug \
        "$WORK/ndn_load_check" > /dev/null 2>&1; then
    echo "INFO: debug build loads with MMT_DPI_LOG_LEVEL=debug"
else
    echo "INFO: debug build did not load with MMT_DPI_LOG_LEVEL=debug (non-fatal)"
fi

echo "PASS: all checks"
