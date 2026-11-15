"""The release workflow publishes only on a pushed ``v*`` tag (plan task T5.3, #30).

``.github/workflows/release.yml`` runs a dry run on every pull request, push
to ``dev`` and manual run, and publishes only from its ``publish-*`` jobs.
These tests read it as text (the project has no YAML parser, like
``tests/unit/generate/test_ci_matrix.py``) and check what keeps a dry run
from publishing: no permission at the top level; every job declares its
own; a job with any write permission, and only such a job, is a
``publish-*`` job gated on a tag push; every command or action that
publishes is in one of them; and every action of every workflow is pinned
by commit SHA (``tests/check_action_pins.sh`` checks, with the network,
that each SHA is its tag's commit).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
WORKFLOWS = REPO / ".github" / "workflows"
RELEASE = WORKFLOWS / "release.yml"

#: The condition every publishing job's ``if:`` starts with.
TAG_GATE = "github.event_name == 'push' && startsWith(github.ref, 'refs/tags/v')"

#: What publishes, or holds a credential that can: none of it may run in a
#: dry run.
PUBLISHING = (
    "gh release",
    "docker push",
    "docker login",
    "imagetools create",
    "git push",
    "git tag",
    "uv publish",
    "twine",
    "pypa/gh-action-pypi-publish",
    "actions/attest",
    "secrets.",
)

PUBLISH_JOBS = {"publish-github", "publish-image", "publish-pypi"}
DRY_RUN_JOBS = {"build", "verify", "container", "image-dry-run"}


def _text() -> str:
    return RELEASE.read_text(encoding="utf-8")


def _code(text: str) -> str:
    """``text`` without its comment lines."""
    return "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))


def _jobs() -> dict[str, str]:
    """Each job's text (comments excluded), by its id."""
    code = _code(_text())
    _, sep, body = code.partition("\njobs:\n")
    assert sep, f"no jobs in {RELEASE}"
    parts = re.split(r"^  ([\w-]+):\n", body, flags=re.MULTILINE)
    assert parts[0].strip() == ""
    return dict(zip(parts[1::2], parts[2::2], strict=True))


def _permissions(job: str) -> dict[str, str]:
    match = re.search(r"^    permissions:\n((?:      [\w-]+: \w+\n)+)", job, re.MULTILINE)
    assert match is not None, "no permissions block"
    return dict(
        line.strip().split(": ", 1) for line in match.group(1).splitlines() if line.strip()
    )


def _job_if(job: str) -> str | None:
    match = re.search(r"^    if: (.+)$", job, re.MULTILINE)
    return None if match is None else match.group(1).strip()


def gated(condition: str | None) -> bool:
    """Whether a job's ``if:`` holds only on a tag push: ``TAG_GATE``, alone
    or followed by more conditions joined with ``&&``, none of which can
    widen it."""
    if condition is None:
        return False
    if condition != TAG_GATE and not condition.startswith(f"{TAG_GATE} && "):
        return False
    widening = ("||", "always()", "!cancelled()", "failure()", "${{")
    return not any(word in condition for word in widening)


@pytest.mark.parametrize(
    "condition",
    [
        None,
        "",
        "startsWith(github.ref, 'refs/tags/v')",
        "github.event_name == 'push'",
        f"{TAG_GATE} || github.event_name == 'workflow_dispatch'",
        f"github.event_name == 'workflow_dispatch' || {TAG_GATE}",
        f"{TAG_GATE} && (vars.X == 'true' || github.event_name == 'pull_request')",
        f"{TAG_GATE} && always()",
        f"always() && {TAG_GATE}",
        f"!cancelled() && {TAG_GATE}",
        f"{TAG_GATE}x",
        f"${{{{ {TAG_GATE} }}}} || true",
    ],
)
def test_the_gate_check_refuses_a_condition_that_can_publish_elsewhere(
    condition: str | None,
) -> None:
    assert not gated(condition)


def test_the_gate_check_accepts_the_gate_and_its_narrowings() -> None:
    assert gated(TAG_GATE)
    assert gated(f"{TAG_GATE} && vars.PYPI_PUBLISH == 'true'")


def test_the_jobs_are_the_dry_run_and_the_publish_ones() -> None:
    assert set(_jobs()) == DRY_RUN_JOBS | PUBLISH_JOBS


def test_the_triggers_run_the_dry_run_and_a_tag_publishes() -> None:
    on = re.search(r"^on:\n(.*?)^\S", _code(_text()), re.MULTILINE | re.DOTALL)
    assert on is not None
    triggers = on.group(1)
    assert re.search(r"^  pull_request:\n    branches: \[dev, main\]$", triggers, re.MULTILINE)
    assert re.search(
        r"^  push:\n    branches: \[dev\]\n    tags: \['v\*'\]$", triggers, re.MULTILINE
    )
    assert re.search(r"^  workflow_dispatch:$", triggers, re.MULTILINE)
    # No trigger that runs with a write token or secrets for outside code.
    assert "pull_request_target" not in triggers
    assert "workflow_run" not in triggers


def test_the_workflow_grants_no_permission_by_default() -> None:
    assert re.search(r"^permissions: \{\}$", _text(), re.MULTILINE)


@pytest.mark.parametrize("name", sorted(DRY_RUN_JOBS))
def test_a_dry_run_job_only_reads_and_never_publishes(name: str) -> None:
    job = _jobs()[name]
    assert _permissions(job) == {"contents": "read"}
    assert _job_if(job) is None
    found = [word for word in PUBLISHING if word in job]
    assert not found, f"{name} names {found}"
    assert "environment:" not in job


@pytest.mark.parametrize("name", sorted(PUBLISH_JOBS))
def test_a_publish_job_runs_only_on_a_tag_push(name: str) -> None:
    condition = _job_if(_jobs()[name])
    assert gated(condition), f"{name}: if: {condition}"


def test_no_step_of_a_dry_run_job_is_gated_on_a_tag() -> None:
    """A dry run runs every step of its jobs: none waits for a tag."""
    for name in DRY_RUN_JOBS:
        assert "refs/tags/v')" not in "".join(
            line for line in _jobs()[name].splitlines(keepends=True) if "if:" in line
        ), name


def test_every_write_permission_is_in_a_publish_job() -> None:
    for name, job in _jobs().items():
        writes = {k for k, v in _permissions(job).items() if v == "write"}
        if name in PUBLISH_JOBS:
            assert writes, f"{name} needs no write permission"
        else:
            assert not writes, f"{name} writes {writes}"


def test_the_publish_jobs_have_the_least_permissions() -> None:
    jobs = _jobs()
    assert _permissions(jobs["publish-github"]) == {
        "contents": "write",
        "id-token": "write",
        "attestations": "write",
    }
    assert _permissions(jobs["publish-image"]) == {
        "contents": "read",
        "packages": "write",
        "id-token": "write",
        "attestations": "write",
        "artifact-metadata": "write",
    }
    assert _permissions(jobs["publish-pypi"]) == {"id-token": "write"}


def test_pypi_is_opt_in_last_and_in_its_environment() -> None:
    job = _jobs()["publish-pypi"]
    assert _job_if(job) == f"{TAG_GATE} && vars.PYPI_PUBLISH == 'true'"
    assert re.search(r"^    environment:\n      name: pypi$", job, re.MULTILINE)
    needs = re.search(r"^    needs: \[(.*)\]$", job, re.MULTILINE)
    assert needs is not None
    assert {"publish-github", "publish-image"} <= {n.strip() for n in needs.group(1).split(",")}


def test_the_publish_jobs_need_the_whole_dry_run() -> None:
    """publish-github and publish-image start only once every dry-run job
    passed on the tag, publish-pypi only once both of them did."""
    for name in ("publish-github", "publish-image"):
        needs = re.search(r"^    needs: \[(.*)\]$", _jobs()[name], re.MULTILINE)
        assert needs is not None, name
        assert {n.strip() for n in needs.group(1).split(",")} == DRY_RUN_JOBS


def test_the_dry_run_builds_checks_installs_and_builds_the_image() -> None:
    jobs = _jobs()
    assert 'bash tests/build_release_assets.sh "$RUNNER_TEMP/release"' in jobs["build"]
    assert "tests/unit/release/test_dist.py" in jobs["build"]
    assert "MMT_REQUIRE_RELEASE_DIST: '1'" in jobs["build"]
    assert "uv tool install" in jobs["verify"]
    assert "generate --check" in jobs["verify"]
    assert "docker build --target release" in jobs["container"]
    # The release's own wheel, by its exact name.
    assert '--build-arg WHEEL="mmt_plugin-$VERSION-py3-none-any.whl"' in jobs["container"]
    # init writes plugin.yaml, test's default model (#65).
    assert "mmt-plugin init demo && mmt-plugin -C demo test'" in jobs["container"]
    assert "bash tests/push_release_image.sh" in jobs["image-dry-run"]
    assert "localhost:5000/mmt-plugin" in jobs["image-dry-run"]
    assert re.search(r"^        image: registry@sha256:[0-9a-f]{64}$", jobs["image-dry-run"], re.M)
    assert "bash tests/check_action_pins.sh" in jobs["build"]
    # publish-image pushes with the script image-dry-run ran.
    assert (
        'bash tests/push_release_image.sh "$RUNNER_TEMP/images" "$IMAGE"' in jobs["publish-image"]
    )


def test_the_release_tag_must_be_the_package_version() -> None:
    build = _jobs()["build"]
    assert 'bash tests/check_release_tag.sh "${REF#refs/tags/}" "$VERSION"' in build
    # The whole history, so origin/main and origin/dev are there to check.
    assert "fetch-depth: 0" in build


@pytest.mark.parametrize("path", sorted(WORKFLOWS.glob("*.yml")), ids=lambda p: p.name)
def test_every_action_is_pinned_by_commit_sha(path: Path) -> None:
    uses = re.findall(r"^\s*(?:- )?uses: (\S+)(.*)$", path.read_text(encoding="utf-8"), re.M)
    assert uses, f"no action in {path.name}"
    for action, rest in uses:
        assert re.fullmatch(r"[\w.-]+/[\w./-]+@[0-9a-f]{40}", action), action
        assert re.fullmatch(r" # v\d+(\.\d+)*", rest), f"{action}: no version comment"


@pytest.mark.parametrize("path", sorted(WORKFLOWS.glob("*.yml")), ids=lambda p: p.name)
def test_every_action_is_github_owned(path: Path) -> None:
    """The repository's Actions policy allows only GitHub-owned actions: any
    other one fails the whole workflow at startup."""
    uses = re.findall(r"^\s*(?:- )?uses: ([^@\s]+)@", path.read_text(encoding="utf-8"), re.M)
    assert uses
    for action in uses:
        assert action.split("/", 1)[0] in {"actions", "github"}, action


def test_pypi_uses_trusted_publishing() -> None:
    job = _jobs()["publish-pypi"]
    assert "uv publish --trusted-publishing always" in job
    assert "secrets." not in job


@pytest.mark.parametrize("path", sorted(WORKFLOWS.glob("*.yml")), ids=lambda p: p.name)
def test_no_checkout_keeps_its_credentials(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    checkouts = re.findall(r"uses: actions/checkout@\S+.*\n((?:\s+.*\n){0,4})", text)
    assert checkouts
    for after in checkouts:
        assert "persist-credentials: false" in after
