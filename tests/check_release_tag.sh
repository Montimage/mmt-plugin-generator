#!/usr/bin/env bash
# Check that a tag may release this version (plan task T5.3, #30).
#
# Usage: bash tests/check_release_tag.sh TAG VERSION [COMMIT]
#
# Run in a git checkout whose refs/remotes/origin/main and
# refs/remotes/origin/dev are fetched (the release workflow's build job
# checks out the whole history). COMMIT defaults to HEAD. It passes when:
# - TAG is v<VERSION>, VERSION being the package's version;
# - COMMIT is on origin/main, or VERSION is a PEP 440 pre-release (a, b, rc
#   or .dev) and COMMIT is on origin/dev or origin/main: a final release
#   comes from main after the release PR (T5.5), a pre-release may come
#   from dev, and no release comes from an unmerged branch.
# It prints `prerelease=true` or `prerelease=false` on stdout (for
# $GITHUB_OUTPUT) and exits 1 with a FAIL: line otherwise.
#
# This check runs from the tagged commit's own workflow, so it only guards
# against mistakes: the v* tag ruleset of docs/releasing.md is what keeps
# others from releasing.
set -euo pipefail

fail() { echo "FAIL: $*" >&2; exit 1; }

case "$#" in 2 | 3) ;; *) fail "usage: $0 TAG VERSION [COMMIT]" ;; esac
tag="$1"
version="$2"
commit="${3:-HEAD}"

[ -n "$version" ] || fail "empty version"
[ "$tag" = "v$version" ] || fail "the tag $tag is not v$version, the version in pyproject.toml"

if [[ "$version" =~ (a|b|rc|\.dev)[0-9]+ ]]; then
    prerelease=true
    branches=(main dev)
else
    prerelease=false
    branches=(main)
fi

sha="$(git rev-parse --verify --quiet "$commit^{commit}")" || fail "no commit $commit"
for branch in "${branches[@]}"; do
    ref="refs/remotes/origin/$branch"
    git rev-parse --verify --quiet "$ref" > /dev/null || continue
    if git merge-base --is-ancestor "$sha" "$ref"; then
        echo "PASS: $tag releases $version from origin/$branch ($sha)" >&2
        echo "prerelease=$prerelease"
        exit 0
    fi
done
if [ "$prerelease" = true ]; then
    fail "$sha is on neither origin/main nor origin/dev: no release from an unmerged branch"
fi
fail "$sha is not on origin/main: a final release is tagged on main"
