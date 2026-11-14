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


def _job() -> str:
    """The text of the job, up to the next job (or the end)."""
    text = WORKFLOW.read_text(encoding="utf-8")
    match = re.search(rf"^  {JOB}:\n(.*?)(?=^  [\w-]+:\n|\Z)", text, re.MULTILINE | re.DOTALL)
    assert match is not None, f"no {JOB} job in {WORKFLOW}"
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


def test_the_job_requires_the_compile_and_load_tests() -> None:
    job = _job()
    assert "MMT_REQUIRE_GOLDEN_COMPILE: '1'" in job
    assert "MMT_GOLDEN_CC: ${{ matrix.cc }}" in job
    assert "MMT_DPI_TAG: ${{ matrix.mmt_dpi.tag }}" in job
    assert "tests/unit/generate/test_compile.py" in job
    assert "tests/unit/build/test_sdk.py" in job  # build (#19): every corpus model
    assert "tests/unit/packettest/test_sdk.py" in job  # test (#20): every corpus model
