#!/bin/bash
# One loop run of the mmt-plugin-generator skill (SKILL.md Step 4), in the mmt-plugin-dev container:
#   docker exec ocip-plugin bash /src/ocip-plugin/loop.sh <n> [test args...]
set -o pipefail
n=$1; shift
W=/src/ocip-plugin; R=$W/runs/run-$n; mkdir -p "$R"
cd /src || exit 1
for c in validate generate build; do
  extra=(); [ "$c" = build ] && extra=(--cc gcc)
  uv run --frozen mmt-plugin -C "$W/project" --json "$c" --sdk /sdk/mmt "${extra[@]}" > "$R/$c.json"
  rc=$?; echo "$c exit=$rc"; [ $rc -ne 0 ] && exit $rc
done
uv run --frozen mmt-plugin -C "$W/project" --json test --sdk /sdk/mmt --cc gcc "$@" > "$R/test.json"
rc=$?; echo "test exit=$rc"; exit $rc
