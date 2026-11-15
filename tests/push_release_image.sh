#!/usr/bin/env bash
# Push the release images and their multi-arch index (plan task T5.3, #30).
#
# Usage: bash tests/push_release_image.sh IMAGES_DIR REPOSITORY VERSION PRERELEASE
#
# IMAGES_DIR holds image-amd64.tar.gz and image-arm64.tar.gz, the `docker
# save` of mmt-plugin:release-amd64 and mmt-plugin:release-arm64 (the
# release workflow's container job). It loads them, pushes
# REPOSITORY:VERSION-amd64 and REPOSITORY:VERSION-arm64, then the index
# REPOSITORY:VERSION (and REPOSITORY:latest when PRERELEASE is false), and
# checks that the index lists exactly the images linux/amd64 and
# linux/arm64. It prints
# `digest=sha256:...`, the index digest, on stdout (for $GITHUB_OUTPUT).
#
# The caller logs in first. The release workflow runs it against
# ghcr.io/montimage/mmt-plugin on a release tag, and against a registry
# service on localhost in every dry run.
set -euo pipefail

fail() { echo "FAIL: $*" >&2; exit 1; }

[ "$#" -eq 4 ] || fail "usage: $0 IMAGES_DIR REPOSITORY VERSION PRERELEASE"
dir="$1"
repo="$2"
version="$3"
prerelease="$4"
case "$prerelease" in true | false) ;; *) fail "PRERELEASE is $prerelease, not true or false" ;; esac
[ -n "$version" ] || fail "empty version"

arches=(amd64 arm64)
for arch in "${arches[@]}"; do
    [ -f "$dir/image-$arch.tar.gz" ] || fail "no $dir/image-$arch.tar.gz"
    gunzip -c "$dir/image-$arch.tar.gz" | docker load >&2
    got="$(docker image inspect -f '{{.Os}}/{{.Architecture}}' "mmt-plugin:release-$arch")"
    [ "$got" = "linux/$arch" ] || fail "mmt-plugin:release-$arch is $got"
    docker tag "mmt-plugin:release-$arch" "$repo:$version-$arch"
    docker push "$repo:$version-$arch" >&2
done

tags=(-t "$repo:$version")
if [ "$prerelease" = false ]; then tags+=(-t "$repo:latest"); fi
docker buildx imagetools create "${tags[@]}" "$repo:$version-amd64" "$repo:$version-arm64" >&2

index="$(docker buildx imagetools inspect "$repo:$version" --format '{{json .Manifest}}')"
digest="$(jq -r .digest <<< "$index")"
[[ "$digest" =~ ^sha256:[0-9a-f]{64}$ ]] || fail "no index digest for $repo:$version: $digest"
# BuildKit's attestation manifests (platform unknown/unknown), if the
# images carry any, stay in the index; the images are the other entries.
platforms="$(jq -r '[.manifests[]
    | select((.annotations // {})["vnd.docker.reference.type"] != "attestation-manifest")
    | .platform | "\(.os)/\(.architecture)"] | sort | join(" ")' <<< "$index")"
[ "$platforms" = "linux/amd64 linux/arm64" ] \
    || fail "the index $repo:$version lists $platforms, not linux/amd64 linux/arm64"
echo "PASS: $repo:$version is $digest ($platforms)" >&2
echo "digest=$digest"
