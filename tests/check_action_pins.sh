#!/usr/bin/env bash
# Check every action pin of .github/workflows/ (plan task T5.3, #30).
#
# Usage: bash tests/check_action_pins.sh
#
# Each `uses: OWNER/REPO[/PATH]@SHA # vX.Y.Z` must name a commit, and the
# tag of its comment must resolve to that commit (an annotated tag is
# followed to its commit). A job that never runs in a dry run (the release
# workflow's publish-* jobs) never resolves its actions, so this is what
# catches a wrong pin before a release. Needs gh and the network; in CI,
# GH_TOKEN is the job's read-only token. It prints one PASS:/FAIL: line per
# pin and exits non-zero on any failure.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
status=0

# The tag's commit: follow an annotated tag object to what it points at.
tag_commit() {
    local repo="$1" tag="$2" type sha
    read -r type sha < <(gh api "repos/$repo/git/ref/tags/$tag" --jq '.object.type + " " + .object.sha')
    while [ "$type" = tag ]; do
        read -r type sha < <(gh api "repos/$repo/git/tags/$sha" --jq '.object.type + " " + .object.sha')
    done
    [ "$type" = commit ] || return 1
    echo "$sha"
}

mapfile -t pins < <(grep -hoE 'uses: [^ ]+@[^ ]+ # v[0-9][0-9.]*' "$root"/.github/workflows/*.yml | sort -u)
[ "${#pins[@]}" -gt 0 ] || { echo "FAIL: no pinned action found"; exit 1; }

for pin in "${pins[@]}"; do
    ref="${pin#uses: }"
    action="${ref%%@*}"
    rest="${ref#*@}"
    sha="${rest%% *}"
    tag="${rest##* }"
    repo="$(cut -d/ -f1-2 <<< "$action")"
    if [[ ! "$sha" =~ ^[0-9a-f]{40}$ ]]; then
        echo "FAIL: $action@$sha is not a full commit SHA"; status=1; continue
    fi
    if ! got="$(tag_commit "$repo" "$tag")"; then
        echo "FAIL: $repo has no tag $tag pointing at a commit"; status=1; continue
    fi
    if [ "$got" != "$sha" ]; then
        echo "FAIL: $action@$sha: $tag is $got"; status=1; continue
    fi
    echo "PASS: $action@$sha is $tag"
done

# Any other `uses:` line is unpinned or has no version comment.
if grep -nE '^\s*(- )?uses: ' "$root"/.github/workflows/*.yml | grep -vE 'uses: [^ ]+@[0-9a-f]{40} # v[0-9][0-9.]*$'; then
    echo "FAIL: the uses: lines above are not OWNER/REPO@SHA # vX.Y.Z"
    status=1
fi
exit "$status"
