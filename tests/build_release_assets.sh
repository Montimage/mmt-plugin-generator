#!/usr/bin/env bash
# Build the release assets of mmt-plugin (plan task T5.3, #30) into OUT_DIR:
#
#   mmt_plugin-<version>-py3-none-any.whl   the wheel (uv tool install, PyPI)
#   mmt_plugin-<version>.tar.gz             the sdist
#   mmt-plugin-schemas-<version>.tar.gz     every JSON Schema the package ships
#                                           (src/mmt_plugin/schemas/**/*.json)
#   SHA256SUMS                              sha256sum of the three files above
#
# Usage: bash tests/build_release_assets.sh OUT_DIR
#
# Run it from anywhere; it builds the checkout it belongs to with uv. OUT_DIR
# must not exist or be empty. The schemas tarball is reproducible: sorted
# members, owner 0, and the mtime of SOURCE_DATE_EPOCH (default: the time of
# the checkout's last commit). It prints the version on stdout.
#
# .github/workflows/release.yml runs it, then checks the result with
# MMT_RELEASE_DIST=OUT_DIR uv run pytest tests/unit/release/test_dist.py.
set -euo pipefail

fail() { echo "FAIL: $*" >&2; exit 1; }

[ "$#" -eq 1 ] || fail "usage: $0 OUT_DIR"
out="$1"
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [ -e "$out" ]; then
    [ -d "$out" ] || fail "$out is not a directory"
    [ -z "$(ls -A "$out")" ] || fail "$out is not empty"
fi
mkdir -p "$out"
out="$(cd "$out" && pwd)"

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

# uv build writes a .gitignore into its output directory: build elsewhere and
# copy only the two distributions.
(cd "$root" && uv build --no-progress --out-dir "$work/dist" >&2)
shopt -s nullglob
wheels=("$work"/dist/mmt_plugin-*-py3-none-any.whl)
sdists=("$work"/dist/mmt_plugin-*.tar.gz)
shopt -u nullglob
[ "${#wheels[@]}" -eq 1 ] || fail "expected one wheel, found ${#wheels[@]}"
[ "${#sdists[@]}" -eq 1 ] || fail "expected one sdist, found ${#sdists[@]}"
wheel="$(basename "${wheels[0]}")"
version="${wheel#mmt_plugin-}"
version="${version%-py3-none-any.whl}"
[ "$(basename "${sdists[0]}")" = "mmt_plugin-$version.tar.gz" ] \
    || fail "the sdist $(basename "${sdists[0]}") is not version $version"
cp "${wheels[0]}" "${sdists[0]}" "$out/"

epoch="${SOURCE_DATE_EPOCH:-$(git -C "$root" log -1 --format=%ct)}"
schemas="mmt-plugin-schemas-$version"
mkdir "$work/$schemas"
(cd "$root/src/mmt_plugin/schemas" && find . -name '*.json' -type f -print0 \
    | xargs -0 cp --parents -t "$work/$schemas")
[ -n "$(ls -A "$work/$schemas")" ] || fail "no JSON Schema under src/mmt_plugin/schemas"
tar --sort=name --mtime="@$epoch" --owner=0 --group=0 --numeric-owner \
    --mode='u=rwX,go=rX' --format=gnu -C "$work" -cf - "$schemas" \
    | gzip -9 -n > "$out/$schemas.tar.gz"

(cd "$out" && sha256sum -- "$wheel" "mmt_plugin-$version.tar.gz" "$schemas.tar.gz" \
    | LC_ALL=C sort -k 2 > SHA256SUMS)

echo "$version"
