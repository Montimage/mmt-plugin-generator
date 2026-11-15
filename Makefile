# Container targets (plan task T0.3). Docker by default; CONTAINER=podman
# also works.
#
#   make container        build the pinned build and test image
#   make test-container   build it, then run tests/check_ndn_plugin.sh inside
#   make release-image    build this checkout's wheel into dist/, then the
#                         release image with it (T5.3, docs/releasing.md)
#
# The repo is mounted read-only and the check runs as your uid, with no
# network, so it leaves no files behind. On an SELinux host, pass
# MOUNT_OPTS=ro,z.

CONTAINER ?= docker
IMAGE ?= mmt-plugin-generator-test:local
RELEASE_IMAGE ?= mmt-plugin:local
MMT_DPI_TAG ?= v1.10.2
# Required for a tag other than v1.10.2 (see tests/fetch_mmt_dpi_package.sh).
MMT_DPI_SHA256SUMS_SHA256 ?=
MOUNT_OPTS ?= ro
# Rootless podman maps --user to a subuid unless the user namespace keeps it.
USERNS_OPT := $(if $(filter podman,$(notdir $(CONTAINER))),--userns=keep-id)

.PHONY: container test-container release-image

container:
	$(CONTAINER) build --target test --build-arg MMT_DPI_TAG=$(MMT_DPI_TAG) \
		--build-arg MMT_DPI_SHA256SUMS_SHA256=$(MMT_DPI_SHA256SUMS_SHA256) -t $(IMAGE) .

test-container: container
	$(CONTAINER) run --rm --network none --user "$$(id -u):$$(id -g)" $(USERNS_OPT) \
		-v "$(CURDIR):/src:$(MOUNT_OPTS)" -w /src $(IMAGE) \
		bash tests/check_ndn_plugin.sh

# The wheel is named after the version in pyproject.toml, so an older wheel
# left in dist/ is never the one installed.
release-image:
	uv build --wheel --out-dir dist
	version="$$(uv version --short)" && \
	$(CONTAINER) build --target release --build-arg MMT_DPI_TAG=$(MMT_DPI_TAG) \
		--build-arg MMT_DPI_SHA256SUMS_SHA256=$(MMT_DPI_SHA256SUMS_SHA256) \
		--build-arg WHEEL="mmt_plugin-$$version-py3-none-any.whl" \
		--build-arg VERSION="$$version" --build-arg REVISION="$$(git rev-parse HEAD)" \
		-t $(RELEASE_IMAGE) .
