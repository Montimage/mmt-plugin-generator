#!/usr/bin/env bash
# Check that the SDK header check (python -m mmt_plugin.sdk.headercheck)
# fails on deliberately broken copies of real mmt-dpi headers:
#
# - unprototyped: plugin_defs.h declares register_protocol() and the
#   generic_init_proto typedef with empty parentheses, which gnu11 accepts
#   as compatible with any parameter list;
# - alias-len: data_defs.h defines Max_Alias_Len as 32, not the 64 the
#   profile records;
# - plugin-ids: dicom/dicom.h gives PROTO_DICOM another id and alias than the
#   profile records;
# - unlisted-id: mobile/mmt_mobile.h defines a protocol id, PROTO_NEW_PLUGIN,
#   that parents.ids does not list.
#
# Usage: bash tests/check_headercheck_mutations.sh PREFIX [CC]
#
# PREFIX is an extracted mmt-dpi 1.10.2 package's opt/mmt (never /opt/mmt
# itself: only scratch copies are changed). It needs the C compiler CC
# (default gcc) and runs the check with $PYTHON (default: uv run python). It
# prints one PASS:/FAIL: line per check and exits non-zero on failure.
set -euo pipefail

prefix="${1:?usage: $0 PREFIX [CC]}"
cc="${2:-gcc}"
include="$prefix/dpi/include"
read -ra python <<< "${PYTHON:-uv run python}"
[ -f "$include/plugin_defs.h" ] || { echo "FAIL: no $include/plugin_defs.h"; exit 1; }

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
failed=0

pass() { echo "PASS: $*"; }
fail() { echo "FAIL: $*"; failed=1; }

# mutate NAME HEADER PERL_SUBSTITUTION...: a scratch prefix named NAME whose
# HEADER has each substitution applied; a substitution that changes nothing
# is an error, so the check cannot pass on a header that moved on.
mutate() {
    local name="$1" header="$2"
    shift 2
    mkdir -p "$work/$name/dpi"
    cp -R "$include" "$work/$name/dpi/"
    local file="$work/$name/dpi/include/$header"
    local expr
    for expr in "$@"; do
        cp "$file" "$file.orig"
        perl -0pi -e "$expr" "$file"
        if cmp -s "$file" "$file.orig"; then
            echo "FAIL: $name: '$expr' does not apply to $header"
            exit 1
        fi
        rm "$file.orig"
    done
}

# expect_failure NAME MESSAGE...: the check of scratch prefix NAME exits 1
# and reports every MESSAGE.
expect_failure() {
    local name="$1" status=0 message
    shift
    "${python[@]}" -m mmt_plugin.sdk.headercheck --sdk "$work/$name" --cc "$cc" \
        > "$work/$name.txt" 2>&1 || status=$?
    grep '^FAIL\|^    .*error' "$work/$name.txt" | sed "s|$work/||g; s|^|    > |" || true
    if [ "$status" -eq 1 ]; then
        pass "$name: the header check exits 1 ($cc)"
    else
        fail "$name: the header check exits $status, expected 1 ($cc)"
    fi
    for message in "$@"; do
        if grep -qF "$message" "$work/$name.txt"; then
            pass "$name: reports '$message'"
        else
            fail "$name: does not report '$message'"
        fi
    done
}

mutate unprototyped plugin_defs.h \
    's/\bregister_protocol\(\s*protocol_t \*protocol_struct,\s*mmt_proto_id_t proto_id\s*\);/register_protocol();/' \
    's/typedef int \(\*generic_init_proto\) \(void\);/typedef int (*generic_init_proto) ();/'
expect_failure unprototyped \
    'registrations.register_protocol is not prototyped' \
    'callbacks.init_proto: generic_init_proto is not prototyped'

mutate alias-len data_defs.h 's/#define Max_Alias_Len 64\b/#define Max_Alias_Len 32/'
expect_failure alias-len 'constants.Max_Alias_Len is not 64'

mutate plugin-ids dicom/dicom.h \
    's/#define PROTO_DICOM 701\b/#define PROTO_DICOM 702/' \
    's/#define PROTO_DICOM_ALIAS "dicom"/#define PROTO_DICOM_ALIAS "dicom2"/'
expect_failure plugin-ids \
    'parents.ids.PROTO_DICOM is not 701' \
    'parents.ids.PROTO_DICOM: PROTO_DICOM_ALIAS is "dicom2", not "dicom"'

mutate unlisted-id mobile/mmt_mobile.h \
    's/#define PROTO_NAS5G_ALIAS "nas_5g"\n\K/#define PROTO_NEW_PLUGIN 905\n/'
expect_failure unlisted-id 'not in the profile: PROTO_NEW_PLUGIN'

exit "$failed"
