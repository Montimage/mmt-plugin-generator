# Pinned build and test container (plan task T0.3): gcc, clang, Python 3.12
# and mmt-dpi from its published GitHub Release package.
#
#   make test-container                     # build, then run the NDN check
#   make test-container CONTAINER=podman
#
# Stages: `toolchain` is that image; `release` adds a released mmt-plugin
# wheel to it (T5.3, see the end of this file and docs/releasing.md); `agent`
# adds the wheel with its agent extra, tshark, libpcap, a docker CLI and the
# read-only skills for mmt-plugin-agent (#161, docs/agent-api.md); `test`,
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
#   The build fails if the gcc, clang or Python major version changes, and
#   lists every installed package version in /usr/share/doc/mmt-test-image.
FROM ubuntu:24.04@sha256:2198e4c65076e9cb0b3d695219df667c0e3b0072da64ca3c2648aca17dcecaf5 AS toolchain

ARG MMT_DPI_TAG=v1.10.2
ARG MMT_DPI_SHA256SUMS_SHA256=

# RUN steps are POSIX sh: podman's default OCI format ignores SHELL.

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
    case "$clang" in 18.*) ;; *) fail "clang version is $clang, expected 18.x" ;; esac; \
    [ "$py" = 3.12 ] || fail "python3 is $py, expected 3.12"; \
    case "$mmt" in "${MMT_DPI_TAG#v}" | "${MMT_DPI_TAG#v}"-*) ;; \
        *) fail "mmt-dpi is $mmt, expected ${MMT_DPI_TAG#v}" ;; esac; \
    mkdir -p /usr/share/doc/mmt-test-image \
    && dpkg-query -W -f='${Package} ${Version} ${Architecture}\n' \
        > /usr/share/doc/mmt-test-image/packages.txt \
    && echo "gcc $gcc, clang $clang, python3 $py, mmt-dpi $mmt ($(dpkg --print-architecture))"

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
    org.opencontainers.image.licenses="Apache-2.0" \
    org.opencontainers.image.version="$VERSION" \
    org.opencontainers.image.revision="$REVISION"

COPY --from=installer /opt/mmt-plugin /opt/mmt-plugin
RUN ln -s /opt/mmt-plugin/bin/mmt-plugin /usr/local/bin/mmt-plugin \
    && mmt-plugin --version

WORKDIR /work
CMD ["mmt-plugin", "--help"]

# Agent image (#161): mmt-plugin-agent runs the mmt-plugin-generator skill
# headless here, the container being its sandbox (docs/agent-api.md).
#
#   make agent-image
#   docker build --target agent --build-arg WHEEL=mmt_plugin-<version>-py3-none-any.whl .
#
# - The agent extra's dependencies are uv.lock's, with their hashes.
# - The SDK is a private prefix, /opt/sdk (MMT_BASE): the skill never uses
#   /opt/mmt, so the toolchain's mmt-dpi package is moved there and purged,
#   its absolute library links made relative (AGENTS.md, "A private prefix
#   can also come from the published package").
# - The skills are root-owned and read-only in /opt/mmt-plugin-skills, and
#   the agent runs as the unprivileged user `agent`, so no shell command
#   of the agent can change them.
# - cyberlab is not in the image: it records captures through Docker, which
#   needs the host's socket (root on the host: never by default). Without it
#   the skill crafts synthetic captures, and only with leave
#   (--allow-synthetic).
FROM installer AS agent-installer

RUN cd /tmp/mmt-plugin \
    && /tmp/uv/uv export --frozen --no-dev --no-emit-project --no-header --extra agent \
        --format requirements.txt -o requirements-agent.txt > /dev/null \
    && /tmp/uv/uv pip install --python /opt/mmt-plugin/bin/python --require-hashes \
        -r requirements-agent.txt \
    && /opt/mmt-plugin/bin/mmt-plugin-agent --json --version \
        | /opt/mmt-plugin/bin/python -c 'import json, sys; assert json.load(sys.stdin)["result"]["agent_extra"]'

FROM toolchain AS agent

ARG VERSION=
ARG REVISION=
LABEL org.opencontainers.image.title="mmt-plugin-agent" \
    org.opencontainers.image.description="mmt-plugin-agent: the mmt-plugin-generator skill headless (mmt-dpi in /opt/sdk)" \
    org.opencontainers.image.source="https://github.com/Montimage/mmt-plugin-generator" \
    org.opencontainers.image.licenses="Apache-2.0" \
    org.opencontainers.image.version="$VERSION" \
    org.opencontainers.image.revision="$REVISION"

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        docker.io libpcap-dev tshark \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /opt/sdk \
    && cp -a /opt/mmt/. /opt/sdk/ \
    && for l in /opt/sdk/dpi/lib/*.so; do \
        [ -L "$l" ] && ln -sfn "$(basename "$(readlink "$l")")" "$l"; done \
    && DEBIAN_FRONTEND=noninteractive apt-get purge -y mmt-dpi \
    && rm -rf /opt/mmt \
    && [ -f /opt/sdk/dpi/include/mmt_log.h ] && [ -f /opt/sdk/plugins/libmmt_tcpip.so ] \
    && dpkg-query -W -f='${Package} ${Version} ${Architecture}\n' \
        > /usr/share/doc/mmt-test-image/packages.txt

ENV MMT_BASE=/opt/sdk MMT_PLUGIN_SKILLS=/opt/mmt-plugin-skills

COPY --from=agent-installer /opt/mmt-plugin /opt/mmt-plugin
COPY skills/ /opt/mmt-plugin-skills/
RUN ln -s /opt/mmt-plugin/bin/mmt-plugin /usr/local/bin/mmt-plugin \
    && ln -s /opt/mmt-plugin/bin/mmt-plugin-agent /usr/local/bin/mmt-plugin-agent \
    && find /opt/mmt-plugin-skills -name __pycache__ -prune -exec rm -rf {} + \
    && chown -R root:root /opt/mmt-plugin-skills \
    && chmod -R a-w,a+rX /opt/mmt-plugin-skills \
    && useradd --create-home --shell /bin/bash agent \
    && mmt-plugin --version && mmt-plugin-agent --version

USER agent
WORKDIR /home/agent
CMD ["mmt-plugin-agent", "--help"]

# The default target: the build and test image of T0.3 (`make container`,
# `docker build .`), which needs no wheel.
FROM toolchain AS test
