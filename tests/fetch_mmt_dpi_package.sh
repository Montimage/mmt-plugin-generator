#!/usr/bin/env bash
# Download a published mmt-dpi package from its GitHub Release and verify it.
#
# Usage: bash tests/fetch_mmt_dpi_package.sh <output dir>
#
# Prints the path of the verified package on stdout. It only downloads and
# verifies: installing is up to the caller (CI runs `sudo apt-get install`;
# without root, `dpkg-deb -x <package> <dir>` gives a private prefix at
# <dir>/opt/mmt).
#
# Environment:
#   MMT_DPI_TAG     Release tag (default v1.10.2).
#   MMT_DPI_DISTRO  distro in the Release's manifest.json (default ubuntu-24.04).
#   MMT_DPI_ARCH    arch in manifest.json, amd64 or arm64
#                   (default: dpkg --print-architecture).
#   MMT_DPI_SHA256SUMS_SHA256
#                   expected sha256 of the Release's SHA256SUMS file. Pinned
#                   below for v1.10.2; required for any other tag.
#
# Chain of trust: SHA256SUMS is checked against the pinned hash, manifest.json
# and the package against SHA256SUMS, and the package against manifest.json.
set -euo pipefail

TAG="${MMT_DPI_TAG:-v1.10.2}"
DISTRO="${MMT_DPI_DISTRO:-ubuntu-24.04}"
ARCH="${MMT_DPI_ARCH:-$(dpkg --print-architecture)}"
PINNED_TAG=v1.10.2
PINNED_SUMS_SHA256=07b796d1d7fea1586e06f5b2872fc6c69b65543ae7c091eb2a70fe73d096306c
BASE_URL="https://github.com/Montimage/mmt-dpi/releases/download/$TAG"

fail() { echo "FAIL: $*" >&2; exit 1; }

[ "$#" -eq 1 ] || fail "usage: $0 <output dir>"
OUT="$1"

if [ -n "${MMT_DPI_SHA256SUMS_SHA256:-}" ]; then
    SUMS_SHA256="$MMT_DPI_SHA256SUMS_SHA256"
elif [ "$TAG" = "$PINNED_TAG" ]; then
    SUMS_SHA256="$PINNED_SUMS_SHA256"
else
    fail "MMT_DPI_SHA256SUMS_SHA256 must be set for tag $TAG"
fi

mkdir -p "$OUT"
cd "$OUT"

fetch() {
    curl -fsSL --proto '=https' --tlsv1.2 --retry 3 -o "$1" "$BASE_URL/$1" \
        || fail "download $BASE_URL/$1"
}

# Checks $1 against its single line in SHA256SUMS.
check_sum() {
    awk -v f="$1" '$2 == f' SHA256SUMS > "$1.sha256"
    [ "$(wc -l < "$1.sha256")" -eq 1 ] || fail "$1 is not listed exactly once in SHA256SUMS"
    sha256sum --quiet -c "$1.sha256" >&2 || fail "$1 does not match SHA256SUMS"
}

fetch SHA256SUMS
echo "$SUMS_SHA256  SHA256SUMS" | sha256sum --quiet -c - >&2 \
    || fail "SHA256SUMS of $TAG does not match the pinned hash"

fetch manifest.json
check_sum manifest.json

PKG="$(jq -r --arg d "$DISTRO" --arg a "$ARCH" \
    '[.packages[] | select(.distro == $d and .arch == $a and .package == "mmt-dpi")]
     | if length == 1 then .[0] | "\(.file) \(.sha256)" else empty end' manifest.json)"
[ -n "$PKG" ] || fail "manifest.json has no single mmt-dpi package for $DISTRO/$ARCH"
FILE="${PKG% *}"
MANIFEST_SHA256="${PKG#* }"
[[ "$FILE" =~ ^[A-Za-z0-9._-]+$ ]] || fail "unexpected package file name: $FILE"

fetch "$FILE"
check_sum "$FILE"
[ "$(sha256sum "$FILE" | cut -d' ' -f1)" = "$MANIFEST_SHA256" ] \
    || fail "$FILE does not match manifest.json"

if [[ "$FILE" == *.deb ]]; then
    version="$(dpkg-deb -f "$FILE" Version)"
    [[ "$version" == "${TAG#v}" || "$version" == "${TAG#v}-"* ]] \
        || fail "$FILE has version $version, expected ${TAG#v}"
    [ "$(dpkg-deb -f "$FILE" Architecture)" = "$ARCH" ] \
        || fail "$FILE is not built for $ARCH"
fi

echo "verified $FILE ($TAG, $DISTRO/$ARCH)" >&2
echo "$PWD/$FILE"
