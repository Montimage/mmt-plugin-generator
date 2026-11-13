#!/usr/bin/env bash
# Check (default) or write the reference output of the legacy Java generator.
#
#   bash legacy/check-reference-output.sh           # regenerate into a temp dir
#                                                   # and diff against
#                                                   # legacy/reference-output/
#   bash legacy/check-reference-output.sh --write   # regenerate
#                                                   # legacy/reference-output/
#
# For every plugins/*_plugin model it runs, from the repository root:
#
#   java -jar legacy/dist/MMTPluginGenerator.jar plugins/<model> <out>/<model>
#
# and records <out>/<model>.exit, <model>.stdout and <model>.stderr next to the
# generated files. The output dir is created first: the tool exits 0 even on
# errors, and prints "Error in writing to file" when the dir is missing.
#
# The output has no timestamps or paths, and two runs are byte-identical, so
# the generated files are not normalised. One thing is: a model that generates
# nothing (ip_plugin) leaves an empty output dir, which git cannot store, so
# empty dirs are dropped from the fresh output before `diff -r`. MANIFEST still
# records that model, with status no-output.
#
# Environment:
#   JAVA  the java binary to run (default: java). Use a Java 8 runtime: the
#         order of some generated blocks follows java.util.HashMap iteration
#         order, which another HashMap implementation may change.
#
# Exits non-zero on any difference.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
JAR_REL="legacy/dist/MMTPluginGenerator.jar"
REF="$SCRIPT_DIR/reference-output"
JAVA="${JAVA:-java}"

# The generator lower-cases names with the default locale; pin it.
export LC_ALL=C

mode="check"
case "${1:-}" in
    "") ;;
    --write) mode="write" ;;
    *) echo "usage: $0 [--write]" >&2; exit 2 ;;
esac

fail=0
pass() { echo "PASS: $*"; }
fail() { echo "FAIL: $*"; fail=1; }

# List the models, one name per line, in C-locale order.
models() {
    local f
    for f in "$REPO_ROOT"/plugins/*_plugin; do
        if [ -f "$f" ]; then basename "$f"; fi
    done
}

# generate <out root>: run the jar on every model into <out root>/<model>/.
generate() {
    local out="$1" m
    while IFS= read -r m; do
        mkdir -p "$out/$m"
        set +e
        (cd "$REPO_ROOT" && "$JAVA" -jar "$JAR_REL" "plugins/$m" "$out/$m") \
            > "$out/$m.stdout" 2> "$out/$m.stderr"
        echo "$?" > "$out/$m.exit"
        set -e
    done < <(models)
}

# model_line <out root> <model>: "<model> <status> <file>=<sha256> ...".
# Status: ok (files, empty stderr), parse-errors (files, stderr not empty),
# no-output (no file generated), exit-<n> (non-zero exit code).
model_line() {
    local out="$1" m="$2" status code nfiles f line
    code="$(cat "$out/$m.exit")"
    nfiles="$(find "$out/$m" -type f | wc -l)"
    if [ "$code" != 0 ]; then
        status="exit-$code"
    elif [ "$nfiles" -eq 0 ]; then
        status=no-output
    elif [ -s "$out/$m.stderr" ]; then
        status=parse-errors
    else
        status=ok
    fi
    line="$m $status"
    while IFS= read -r f; do
        line="$line $f=$(sha256sum "$out/$f" | cut -d' ' -f1)"
    done < <(cd "$out" && { find "$m" -type f; printf '%s\n' "$m.exit" "$m.stdout" "$m.stderr"; } | sort)
    echo "$line"
}

model_lines() {
    local m
    while IFS= read -r m; do
        model_line "$1" "$m"
    done < <(models)
}

java_version() {
    "$JAVA" -version 2>&1 | paste -sd'|' - | sed 's/|/ | /g'
}

jar_sha256() {
    sha256sum "$REPO_ROOT/$JAR_REL" | cut -d' ' -f1
}

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

echo "java: $(java_version)"
generate "$tmp/out"
model_lines "$tmp/out" > "$tmp/model-lines"
# Normalisation: git cannot store an empty dir (see the header).
find "$tmp/out" -mindepth 1 -type d -empty -delete

if [ "$mode" = write ]; then
    command -v unzip > /dev/null || { echo "unzip is needed to read the jar's manifest" >&2; exit 1; }
    version="$(unzip -p "$REPO_ROOT/$JAR_REL" META-INF/MANIFEST.MF \
        | tr -d '\r' | sed -n 's/^Implementation-Version: *//p')"
    {
        echo "# Reference output of the legacy Java generator (plan task T0.5)."
        echo "# Written by: bash legacy/check-reference-output.sh --write"
        echo "# Checked by: bash legacy/check-reference-output.sh"
        echo "# Model line: <model> <status> <file>=<sha256> ..."
        echo "# Status: ok, parse-errors (stderr not empty), no-output, exit-<n>."
        echo "generator: $JAR_REL"
        echo "generator-sha256: $(jar_sha256)"
        echo "generator-version: ${version:-none (META-INF/MANIFEST.MF has no Implementation-Version)}"
        echo "java: $(java_version)"
        echo "platform: $(uname -sm)"
        echo "date: $(date -u +%Y-%m-%d)"
        echo "normalised: empty output dirs are dropped (git cannot store them); generated files are compared as is"
        cat "$tmp/model-lines"
    } > "$tmp/out/MANIFEST"
    rm -rf "$REF"
    cp -R "$tmp/out" "$REF"
    echo "wrote $REF ($(models | wc -l) models)"
    exit 0
fi

[ -f "$REF/MANIFEST" ] || { fail "missing $REF/MANIFEST"; exit 1; }

want="$(sed -n 's/^generator-sha256: //p' "$REF/MANIFEST")"
got="$(jar_sha256)"
if [ "$want" = "$got" ]; then
    pass "jar sha256 matches MANIFEST ($got)"
else
    fail "jar sha256 is $got, MANIFEST records ${want:-nothing}"
fi

if diff -r -x MANIFEST "$REF" "$tmp/out"; then
    pass "fresh output of $(models | wc -l) models matches reference-output/ byte for byte"
else
    fail "fresh output differs from reference-output/ (diff above: < stored, > fresh)"
fi

if diff <(grep -E '^[a-z0-9_]+_plugin ' "$REF/MANIFEST") "$tmp/model-lines"; then
    pass "MANIFEST model lines match the fresh output"
else
    fail "MANIFEST model lines differ from the fresh output (< stored, > fresh)"
fi

exit "$fail"
