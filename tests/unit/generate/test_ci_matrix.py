"""The CI "Generated code" job covers what plan T1.7 asks (#16).

``test_compile.py`` compiles, builds and loads the generated C against one
SDK; the ``generated-code`` job of ``.github/workflows/ci.yml`` runs it per
compiler (gcc and clang) and per mmt-dpi, which must include the oldest and
the newest version with a bundled SDK profile. The project has no YAML
parser, so the job is read as text.
"""

from __future__ import annotations

import re

from mmt_plugin.sdk import bundled_versions
from mmt_plugin.sdk.profile import version_key

from .helpers import REPO

WORKFLOW = REPO / ".github" / "workflows" / "ci.yml"
JOB = "generated-code"


def _job(job: str = JOB) -> str:
    """The text of the job, up to the next job (or the end)."""
    text = WORKFLOW.read_text(encoding="utf-8")
    match = re.search(rf"^  {job}:\n(.*?)(?=^  [\w-]+:\n|\Z)", text, re.MULTILINE | re.DOTALL)
    assert match is not None, f"no {job} job in {WORKFLOW}"
    return match.group(1)


def test_the_matrix_covers_the_oldest_and_newest_supported_mmt_dpi() -> None:
    tags = re.findall(r"^          - tag: (v[0-9.]+)$", _job(), re.MULTILINE)
    assert tags, "no mmt_dpi tag in the matrix"
    versions = sorted(bundled_versions(), key=version_key)
    assert f"v{versions[0]}" in tags
    assert f"v{versions[-1]}" in tags
    # Every tag is one generate supports, so test_compile.py finds its profile.
    assert {t[1:] for t in tags} <= set(versions), tags


def test_the_matrix_covers_gcc_and_clang() -> None:
    cc = re.search(r"^        cc: \[(.*)\]$", _job(), re.MULTILINE)
    assert cc is not None
    assert {c.strip() for c in cc.group(1).split(",")} == {"gcc", "clang"}


def _commands(job: str = JOB) -> str:
    """The job without its comment lines: a step's comment naming a test
    file must not stand in for the command that runs it."""
    return "\n".join(line for line in _job(job).splitlines() if not line.lstrip().startswith("#"))


def _step(name: str, job: str = JOB) -> str:
    """The text of the job's step ``name`` (comments excluded), up to the next step."""
    match = re.search(
        rf"^      - name: {re.escape(name)}\n(.*?)(?=^      - |\Z)",
        _commands(job),
        re.MULTILINE | re.DOTALL,
    )
    assert match is not None, f"no step {name!r} in the {job} job"
    return match.group(1)


def test_the_job_requires_the_compile_and_load_tests() -> None:
    job = _commands()
    assert "MMT_REQUIRE_GOLDEN_COMPILE: '1'" in job
    assert "MMT_GOLDEN_CC: ${{ matrix.cc }}" in job
    assert "MMT_DPI_TAG: ${{ matrix.mmt_dpi.tag }}" in job
    assert "tests/unit/generate/test_compile.py" in job
    assert "tests/unit/build/test_sdk.py" in job  # build (#19): every corpus model
    assert "tests/unit/packettest/test_sdk.py" in job  # test (#20): every corpus model
    assert "tests/unit/examples/test_sdk.py" in job  # the ported examples (#28)
    assert "tests/unit/pluginyaml/test_sdk.py" in job  # plugin.yaml parents (#24)
    assert "tests/unit/scaffold/test_sdk.py" in job  # scaffold on sample pcaps (#26)
    assert "tests/unit/skill/test_sdk.py" in job  # the mmt-plugin-generator evals (#27)
    assert "tests/unit/docs/test_commands.py" in job  # the user docs' commands (#29)
    assert "tests/unit/run/test_sdk.py" in job  # run over captures (#103, #115)


def test_the_examples_step_runs_their_sdk_tests_and_requires_them() -> None:
    # #28: CI builds and tests every ported example; without the variables the
    # tests would skip instead of failing.
    step = _step("Build and test every ported example")
    assert "MMT_REQUIRE_GOLDEN_COMPILE: '1'" in step
    assert "MMT_GOLDEN_CC: ${{ matrix.cc }}" in step
    assert 'MMT_GOLDEN_SDK="$SDK_PREFIX"' in step
    # The command is a whole line (no `|| true`), and nothing skips the step
    # or lets it fail without failing the job.
    lines = [line.strip() for line in step.splitlines()]
    assert "uv run pytest -v -rA -p no:cacheprovider tests/unit/examples/test_sdk.py" in lines
    assert not re.search(r"^        (if|continue-on-error):", step, re.MULTILINE)


def test_the_docs_step_runs_every_doc_command_and_requires_the_sdk() -> None:
    # #29: every example command of the user docs runs in CI; the sdk blocks
    # only run here, and without the variables they would skip.
    step = _step("Run the user documentation's commands")
    assert "MMT_REQUIRE_GOLDEN_COMPILE: '1'" in step
    assert "MMT_GOLDEN_CC: ${{ matrix.cc }}" in step
    assert "MMT_DOCS_INSTALL: '1'" in step
    assert 'MMT_GOLDEN_SDK="$SDK_PREFIX"' in step
    lines = [line.strip() for line in step.splitlines()]
    assert "uv run pytest -v -rA -p no:cacheprovider tests/unit/docs/test_commands.py" in lines
    assert not re.search(r"^        (if|continue-on-error):", step, re.MULTILINE)


def test_the_run_step_runs_its_sdk_tests_and_requires_them() -> None:
    # #115: mmt-plugin run's real-SDK tests (#103) run on every leg of the
    # matrix; without the variables they would skip instead of failing.
    step = _step("Run plugins over captures with mmt-plugin run")
    assert "MMT_REQUIRE_GOLDEN_COMPILE: '1'" in step
    assert "MMT_GOLDEN_CC: ${{ matrix.cc }}" in step
    assert 'MMT_GOLDEN_SDK="$SDK_PREFIX"' in step
    lines = [line.strip() for line in step.splitlines()]
    assert "uv run pytest -v -rA -p no:cacheprovider tests/unit/run/test_sdk.py" in lines
    assert not re.search(r"^        (if|continue-on-error):", step, re.MULTILINE)


def test_the_tshark_tests_run_with_the_real_tshark_and_require_it() -> None:
    # #128: every leg of the matrix installs the distribution's tshark,
    # without prompts, before the scaffold --tshark test (#125) and the
    # skill's drift check against tshark (#123) run; MMT_REQUIRE_TSHARK makes
    # them fail instead of skipping when tshark is missing.
    install = _step("Install tshark")
    assert not re.search(r"^        (if|continue-on-error):", install, re.MULTILINE)
    lines = [line.strip() for line in install.splitlines()]
    assert "apt-get install -y --no-install-recommends tshark" in lines
    assert "sudo env DEBIAN_FRONTEND=noninteractive \\" in lines
    assert "| sudo debconf-set-selections" in lines
    assert "tshark --version | head -n 1" in lines
    job = _commands()
    for name, test in [
        ("Scaffold packet tests from sample pcaps and test the proposal", "scaffold"),
        ("Run the mmt-plugin-generator skill's evals", "skill"),
    ]:
        step = _step(name)
        assert "MMT_REQUIRE_TSHARK: '1'" in step
        assert "MMT_REQUIRE_GOLDEN_COMPILE: '1'" in step
        assert "MMT_GOLDEN_CC: ${{ matrix.cc }}" in step
        assert 'MMT_GOLDEN_SDK="$SDK_PREFIX"' in step
        command = f"uv run pytest -v -rA -p no:cacheprovider tests/unit/{test}/test_sdk.py"
        assert command in [line.strip() for line in step.splitlines()]
        assert not re.search(r"^        (if|continue-on-error):", step, re.MULTILINE)
        assert job.index("name: Install tshark") < job.index(f"name: {name}")
    # Both arches, both compilers: the install step has no condition.
    assert "arch: [amd64, arm64]" in job


def test_the_sdk_profile_job_checks_the_run_time_registry() -> None:
    # #115: the run-time cross-check of the profile's ids (#50) runs in the
    # sdk-profile job, on both arches. The test skips on an SDK it cannot
    # check, so the step fails unless pytest reports it PASSED.
    test = "tests/unit/test_sdk_registry.py::test_the_real_registry_is_the_profile"
    step = _step("Check the profile's ids against the run-time registry", job="sdk-profile")
    assert "MMT_REQUIRE_GOLDEN_COMPILE: '1'" in step
    assert 'MMT_GOLDEN_SDK="$SDK_PREFIX"' in step
    assert f"{test} \\" in [line.strip() for line in step.splitlines()]
    assert f"grep -qxF 'PASSED {test}'" in step
    assert '[ "$status" -eq 0 ] || exit "$status"' in step
    assert not re.search(r"^        (if|continue-on-error):", step, re.MULTILINE)
    # It runs after the headers check, in a job with both arches.
    job = _commands("sdk-profile")
    assert job.index("name: Check the profile's ids") > job.index(
        "name: Check that broken copies of the headers fail"
    )
    assert "arch: amd64" in job
    assert "arch: arm64" in job


def test_the_python_job_runs_the_docs_install_blocks() -> None:
    # #29: the uv tool install blocks run in the Python 3.12 job (the
    # network is there) and fail instead of skipping.
    text = WORKFLOW.read_text(encoding="utf-8")
    assert re.search(
        r"^          - python: '3.12'\n            shells: true\n"
        r"            docs_install: true$",
        text,
        re.MULTILINE,
    )
    assert "MMT_DOCS_INSTALL: ${{ matrix.docs_install && '1' || '0' }}" in text
