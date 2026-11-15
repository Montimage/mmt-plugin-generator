# Pinned build and test container (plan task T0.3): gcc, clang, Python 3.12
# and mmt-dpi from its published GitHub Release package.
#
#   make test-container                     # build, then run the NDN check
#   make test-container CONTAINER=podman
#
# Stages: `toolchain` is that image; `release` adds a released mmt-plugin
# wheel to it (T5.3, see the end of this file and docs/releasing.md); `test`,
# the default target, is the toolchain again, so `docker build .` and
# `make container` build the test image and need no wheel.
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
#   The build fails if the gcc, clang or Python major version changes, or
#   if pkg-config cannot find mmt-dpi at the package's version (a broken
#   mmt-dpi.pc), and lists every installed package version in
#   /usr/share/doc/mmt-test-image.
FROM ubuntu:24.04@sha256:2198e4c65076e9cb0b3d695219df667c0e3b0072da64ca3c2648aca17dcecaf5 AS toolchain

ARG MMT_DPI_TAG=v1.10.2
ARG MMT_DPI_SHA256SUMS_SHA256=

# RUN steps are POSIX sh: podman's default OCI format ignores SHELL.

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        ca-certificates clang curl gcc jq libc6-dev make pkg-config python3 \
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
    case "$clang" in 18.*) ;; *) fail "clang version is $clang, expected 18.x" ;; esac; \
    [ "$py" = 3.12 ] || fail "python3 is $py, expected 3.12"; \
    case "$mmt" in "${MMT_DPI_TAG#v}" | "${MMT_DPI_TAG#v}"-*) ;; \
        *) fail "mmt-dpi is $mmt, expected ${MMT_DPI_TAG#v}" ;; esac; \
    pkg-config --exists mmt-dpi || fail "pkg-config cannot find mmt-dpi"; \
    pc="$(pkg-config --modversion mmt-dpi)" || fail "pkg-config cannot read the mmt-dpi version"; \
    [ "$pc" = "${MMT_DPI_TAG#v}" ] || fail "pkg-config reports mmt-dpi $pc, expected ${MMT_DPI_TAG#v}"; \
    pcinc="$(pkg-config --variable=includedir mmt-dpi)" || fail "pkg-config cannot read the mmt-dpi includedir"; \
    [ -f "$pcinc/mmt_log.h" ] || fail "pkg-config's mmt-dpi includedir $pcinc has no mmt_log.h"; \
    mkdir -p /usr/share/doc/mmt-test-image \
    && dpkg-query -W -f='${Package} ${Version} ${Architecture}\n' \
        > /usr/share/doc/mmt-test-image/packages.txt \
    && echo "gcc $gcc, clang $clang, python3 $py, mmt-dpi $mmt (pkg-config $pc, $(dpkg --print-architecture))"

ENV MMT_BASE=/opt/mmt
WORKDIR /src

# Release image (plan task T5.3, #30): the toolchain above plus the released
# mmt-plugin wheel, so `build`, `test` and `install` work inside it.
#
#   make release-image
#   docker build --target release --build-arg WHEEL=mmt_plugin-<version>-py3-none-any.whl .
#
# WHEEL names the wheel in dist/ of the build context (.dockerignore lets in
# only dist/mmt_plugin-*.whl); .github/workflows/release.yml puts the
# release's own wheel there. Its dependencies are the versions and hashes
# uv.lock pins (--require-hashes). uv is pinned as in CI (version and sha256
# per arch) and stays in the installer stage; the venv uses the image's
# /usr/bin/python3, so the release stage can run it.
FROM toolchain AS installer

ARG UV_VERSION=0.12.10
ARG UV_SHA256_AMD64=173d95a0c32d18c896c46ba6fafbf3cf9c14ab74b033f81b76c883ef492a976b
ARG UV_SHA256_ARM64=9ff6b9d4665edcdd3a88dcc73cd1eb641754deb927f14e8c62ebfde6bf4f5f5e

RUN fail() { echo "FAIL: $*" >&2; exit 1; }; \
    case "$(dpkg --print-architecture)" in \
        amd64) target=uv-x86_64-unknown-linux-gnu; sum="$UV_SHA256_AMD64" ;; \
        arm64) target=uv-aarch64-unknown-linux-gnu; sum="$UV_SHA256_ARM64" ;; \
        *) fail "no pinned uv for $(dpkg --print-architecture)" ;; \
    esac; \
    mkdir -p /tmp/uv \
    && curl -fsSL --proto '=https' --tlsv1.2 -o "/tmp/uv/$target.tar.gz" \
        "https://github.com/astral-sh/uv/releases/download/$UV_VERSION/$target.tar.gz" \
    && echo "$sum  /tmp/uv/$target.tar.gz" | sha256sum -c - \
    && tar -xzf "/tmp/uv/$target.tar.gz" -C /tmp/uv --strip-components=1 "$target/uv" \
    && /tmp/uv/uv --version

ARG WHEEL
COPY pyproject.toml uv.lock /tmp/mmt-plugin/
COPY dist/${WHEEL} /tmp/mmt-plugin/dist/

ENV UV_NO_CACHE=1 UV_PYTHON_DOWNLOADS=never
RUN fail() { echo "FAIL: $*" >&2; exit 1; }; \
    case "$WHEEL" in mmt_plugin-*-py3-none-any.whl) ;; \
        *) fail "WHEEL is '$WHEEL', not a mmt_plugin-<version>-py3-none-any.whl in dist/" ;; esac; \
    cd /tmp/mmt-plugin \
    && /tmp/uv/uv export --frozen --no-dev --no-emit-project --no-header \
        --format requirements.txt -o requirements.txt > /dev/null \
    && /tmp/uv/uv venv --python /usr/bin/python3 /opt/mmt-plugin \
    && /tmp/uv/uv pip install --python /opt/mmt-plugin/bin/python --require-hashes \
        -r requirements.txt \
    && /tmp/uv/uv pip install --python /opt/mmt-plugin/bin/python --no-deps "dist/$WHEEL" \
    && /opt/mmt-plugin/bin/mmt-plugin --version

FROM toolchain AS release

ARG VERSION=
ARG REVISION=
LABEL org.opencontainers.image.title="mmt-plugin" \
    org.opencontainers.image.description="Generate, build and test mmt-dpi protocol plugins (gcc, clang, mmt-dpi in /opt/mmt)" \
    org.opencontainers.image.source="https://github.com/Montimage/mmt-plugin-generator" \
    org.opencontainers.image.version="$VERSION" \
    org.opencontainers.image.revision="$REVISION"

COPY --from=installer /opt/mmt-plugin /opt/mmt-plugin
RUN ln -s /opt/mmt-plugin/bin/mmt-plugin /usr/local/bin/mmt-plugin \
    && mmt-plugin --version

WORKDIR /work
CMD ["mmt-plugin", "--help"]

# The default target: the build and test image of T0.3 (`make container`,
# `docker build .`), which needs no wheel.
FROM toolchain AS test
