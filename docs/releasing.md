# Releasing mmt-plugin

How a release of `mmt-plugin` is built, checked and published (plan task
T5.3, #30). The first release is T5.5 (#32) and needs the maintainer's
explicit OK; nothing below has been published yet.

## What a release contains

`.github/workflows/release.yml` builds, for version `V`:

| Asset | Where it goes | How it is installed |
|-------|---------------|---------------------|
| `mmt_plugin-V-py3-none-any.whl` | GitHub release; PyPI when enabled | `uv tool install mmt-plugin` (PyPI), or `uv tool install <wheel URL or file>` |
| `mmt_plugin-V.tar.gz` (sdist) | GitHub release; PyPI when enabled | `uv tool install <sdist>` builds it |
| `mmt-plugin-schemas-V.tar.gz` | GitHub release | every JSON Schema of the package: `cli/v1/` (the `--json` envelope and each command's `result`), `model/v1/plugin.json`, `lock/v1/`, `install/v1/` and `sdk/v1/` |
| `SHA256SUMS` | GitHub release | `sha256sum -c SHA256SUMS` |
| `mmt-plugin-V.sigstore.json` | GitHub release | the provenance attestation of the three files above (Sigstore bundle) |
| `ghcr.io/montimage/mmt-plugin:V` | GitHub Container Registry (amd64 and arm64; `latest` for a final release) | `docker run ghcr.io/montimage/mmt-plugin:V mmt-plugin --version` |

The wheel and the sdist also carry every schema, under
`mmt_plugin/schemas/`, as `docs/design/cli.md` requires.
`tests/build_release_assets.sh OUT_DIR` builds the first four files and
`tests/unit/release/test_dist.py` checks them.

### The container image

The release image is the `release` target of the repository's `Dockerfile`:
the pinned build and test image of T0.3 (Ubuntu 24.04 by digest, gcc,
clang, Python 3.12 and the verified mmt-dpi v1.10.2 package in `/opt/mmt`)
plus the release's own wheel, installed in `/opt/mmt-plugin` with the
dependency versions and hashes of `uv.lock`. It is not a separate
Python-only image because `build`, `test` and `install` need a compiler and
an SDK: an image without them would only `generate` and `validate --no-sdk`,
which `uv tool install` already gives. Sharing the stage also means the
image CI tests on every pull request (`make test-container`) is the base of
the one that is released. The default target is still the test image, so
`make container` and `docker build .` are unchanged. Build the release image
locally with:

```sh
make release-image
docker run --rm mmt-plugin:local mmt-plugin --version
```

## The dry run

Every pull request to `dev` or `main`, every push to `dev` and every manual
run (*Run workflow* on the Actions tab) runs the whole release except
publishing:

1. `build`: the four assets, checked by `test_dist.py` (every package file
   and schema in the wheel and the sdist, the metadata, the schemas tarball,
   `SHA256SUMS`), and uploaded as the run's `release-assets` artifact.
2. `verify`: `uv tool install` of the wheel, then of the sdist, on Python
   3.10 and 3.14; each installed `mmt-plugin` reports the version and runs
   `generate --check` on every example.
   `build` also runs `tests/check_release_tag.sh` for the tag `vV` on the
   branch it would come from, and `tests/check_action_pins.sh`, which
   checks that every pinned action SHA is its tag's commit, the publish
   jobs' actions included (a dry run never resolves those).
3. `container`: the release image on amd64 and arm64, its version label,
   then `mmt-plugin init demo` and `mmt-plugin -C demo test` inside it, as
   the runner's uid and with no network.
4. `image-dry-run`: `tests/push_release_image.sh`, the script
   `publish-image` runs, pushes both images and their multi-arch index to a
   registry service that lives only in that job.

Nothing is attested, pushed or uploaded outside the run. What a dry run
cannot reach is the attestations, the GitHub release, ghcr.io and PyPI.
Run the asset checks locally with:

```sh
bash tests/build_release_assets.sh /tmp/mmt-plugin-release
MMT_RELEASE_DIST=/tmp/mmt-plugin-release uv run pytest tests/unit/release/test_dist.py
uv tool install --reinstall /tmp/mmt-plugin-release/mmt_plugin-*-py3-none-any.whl
mmt-plugin --version
```

## Publishing

Only a pushed tag `vV`, where `V` is the version in `pyproject.toml`,
publishes. The `build` job (`tests/check_release_tag.sh`) refuses any other
tag, a tag of a final version (no `a`, `b`, `rc` or `.dev` part) whose
commit is not on `main`, and a tag of a pre-release whose commit is on
neither `dev` nor `main`. That check runs from the tagged commit's own
workflow, so it catches mistakes, not someone who can push a tag with a
changed workflow: only the tag ruleset below does that.
After `build`, `verify`, `container` and `image-dry-run` pass on that tag:

- `publish-github` attests the provenance of the wheel, the sdist and the
  schemas tarball (`actions/attest`: SLSA build provenance, signed with
  Sigstore and stored by GitHub) and creates the GitHub release with
  generated notes (a pre-release for a pre-release version).
- `publish-image` pushes the two images tested by `container`, makes the
  multi-arch tag `V` (and `latest` for a final version) and attests the
  image's digest, the attestation pushed to the registry next to it.
- `publish-pypi`, only when the repository variable `PYPI_PUBLISH` is
  `true`, uploads the wheel and the sdist with `uv publish` and trusted
  publishing (OIDC, no token). It runs last because PyPI never accepts the
  same version twice. Their provenance is the GitHub attestation of the
  same files (`gh attestation verify` works on a wheel downloaded from
  PyPI). The repository allows only GitHub-owned actions, so the workflow
  uses `uv publish` rather than `pypa/gh-action-pypi-publish`; allowing
  that action would also add PEP 740 attestations on PyPI.

`tests/unit/release/test_workflow.py` checks that only these three jobs hold
write permissions and that each of them runs only on a tag push.

### Setup before the first release

Once, by a repository admin:

1. **Tag protection.** A tag ruleset for `v*` that only maintainers can
   create, update or delete, since a tag push publishes. Until it exists,
   anyone with write access can publish a GitHub release and an image.
2. **PyPI** (optional; without it the release is GitHub only):
   - register a trusted publisher for the project `mmt-plugin` on PyPI
     (a *pending* publisher before the first upload): owner `Montimage`,
     repository `mmt-plugin-generator`, workflow `release.yml`,
     environment `pypi`;
   - create the environment `pypi` (Settings, Environments) with required
     reviewers, so every upload waits for an approval, and deployment tags
     limited to `v*`;
   - set the repository variable `PYPI_PUBLISH` to `true`.
3. **Container image.** After the first push, make the package
   `mmt-plugin` public (organization Packages, Package settings) and link it
   to this repository if GitHub did not.
4. **License.** The repository has no license yet, so the package has no
   license metadata and the image no license label; the image also
   redistributes the mmt-dpi package. Choose one (a `LICENSE` file, then
   `license` and `readme` in `pyproject.toml`) before the first release,
   and keep `PYPI_PUBLISH` unset and the image private until then.

No secret is needed: the workflow uses its `GITHUB_TOKEN` and OIDC.

### Cutting a release

1. On a branch from `dev`, set the version and regenerate the examples
   and the OCI-P project `ocip-plugin/project`, whose `plugin.lock`
   records the generator version (`generate --check` fails on each one
   otherwise; CI's Python job and the release's `verify` job both check
   it):

   ```sh
   uv version 0.1.0
   for d in examples/*/ ocip-plugin/project/; do uv run mmt-plugin -C "$d" generate; done
   git diff --stat
   ```

   `uv version` updates `pyproject.toml` and `uv.lock`; the examples and
   the OCI-P project change only in `plugin.lock`. Run `uv version` with the uv that CI pins
   (`UV_VERSION` in `.github/workflows/release.yml`): a newer uv may also
   raise the `revision` of `uv.lock`. Add the release's section to
   [`CHANGELOG.md`](../CHANGELOG.md), then open the PR against `dev`.
   A final version on `dev` keeps the dry run green: it checks the tag
   against the tip of `main`, where a final release is tagged.
2. Open the release PR from `dev` to `main` (T5.5); its CI runs the dry run.
3. Once it is merged, tag the merge commit on `main` and push the tag:

   ```sh
   git fetch origin
   git tag -a v0.1.0 -m "mmt-plugin 0.1.0" origin/main
   git push origin v0.1.0
   ```

4. Approve the `pypi` deployment when the workflow asks.
5. Set `dev` to the next development version (`uv version 0.2.0.dev0`,
   then regenerate the examples and the OCI-P project again).

### Verifying a release

```sh
gh release download v0.1.0 --repo Montimage/mmt-plugin-generator
sha256sum -c SHA256SUMS
gh attestation verify mmt_plugin-0.1.0-py3-none-any.whl --repo Montimage/mmt-plugin-generator
gh attestation verify oci://ghcr.io/montimage/mmt-plugin:0.1.0 --repo Montimage/mmt-plugin-generator
```

A failed run publishes nothing after its failing job: re-run it from the
Actions tab. A job that already published (a GitHub release, an image tag)
must be undone by hand before a re-run, and a PyPI version can only be
replaced by a new version.
