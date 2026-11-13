# Pinned build and test container (plan task T0.3): gcc, clang, Python 3.12
# and mmt-dpi from its published GitHub Release package.
#
#   make test-container                     # build, then run the NDN check
#   make test-container CONTAINER=podman
#
# Pinning policy:
# - Base image: the multi-arch index digest of the official ubuntu:24.04
#   image, so amd64 and arm64 both start from a fixed tag state. To update,
#   take the new digest from `docker buildx imagetools inspect ubuntu:24.04`.
# - mmt-dpi: tests/fetch_mmt_dpi_package.sh checks the Release's SHA256SUMS
#   against the hash pinned in that script, then manifest.json and the .deb
#   against SHA256SUMS. Another tag needs MMT_DPI_SHA256SUMS_SHA256.
# - apt packages: not pinned to exact versions. Ubuntu drops superseded
#   versions from noble-updates and noble-security, so exact pins stop
#   resolving, and snapshot.ubuntu.com does not serve ubuntu-ports (arm64).
#   The build fails if the gcc, clang or Python major version changes, and
#   lists every installed package version in /usr/share/doc/mmt-test-image.
FROM ubuntu:24.04@sha256:2198e4c65076e9cb0b3d695219df667c0e3b0072da64ca3c2648aca17dcecaf5

ARG MMT_DPI_TAG=v1.10.2
ARG MMT_DPI_SHA256SUMS_SHA256=

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        ca-certificates clang curl gcc jq libc6-dev make python3 \
    && rm -rf /var/lib/apt/lists/*

COPY tests/fetch_mmt_dpi_package.sh /tmp/fetch_mmt_dpi_package.sh

# The fetch script picks the package for this image's dpkg architecture.
RUN deb="$(MMT_DPI_TAG="$MMT_DPI_TAG" MMT_DPI_SHA256SUMS_SHA256="$MMT_DPI_SHA256SUMS_SHA256" \
        bash /tmp/fetch_mmt_dpi_package.sh /tmp/mmt-dpi)" \
    && apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends "$deb" \
    && rm -rf /var/lib/apt/lists/* /tmp/mmt-dpi /tmp/fetch_mmt_dpi_package.sh \
    && dpkg -L mmt-dpi | grep -qx /opt/mmt/dpi/include/mmt_log.h \
    && dpkg -L mmt-dpi | grep -qx /opt/mmt/plugins/libmmt_tcpip.so

RUN fail() { echo "FAIL: $*" >&2; exit 1; }; \
    gcc="$(gcc -dumpversion)"; clang="$(clang -dumpversion)"; \
    py="$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')"; \
    mmt="$(dpkg-query -W -f='${Version}' mmt-dpi)"; \
    [ "$gcc" = 13 ] || fail "gcc major version is $gcc, expected 13"; \
    [[ "$clang" == 18.* ]] || fail "clang version is $clang, expected 18.x"; \
    [ "$py" = 3.12 ] || fail "python3 is $py, expected 3.12"; \
    [[ "$mmt" == "${MMT_DPI_TAG#v}" || "$mmt" == "${MMT_DPI_TAG#v}-"* ]] \
        || fail "mmt-dpi is $mmt, expected ${MMT_DPI_TAG#v}"; \
    mkdir -p /usr/share/doc/mmt-test-image \
    && dpkg-query -W -f='${Package} ${Version} ${Architecture}\n' \
        > /usr/share/doc/mmt-test-image/packages.txt \
    && echo "gcc $gcc, clang $clang, python3 $py, mmt-dpi $mmt ($(dpkg --print-architecture))"

ENV MMT_BASE=/opt/mmt
WORKDIR /src
