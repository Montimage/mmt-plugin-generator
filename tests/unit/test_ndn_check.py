"""The NDN check and the CI chain that runs it (#42).

``tests/check_ndn_plugin.sh`` scans the directories of ``SCAN_DIRS`` for the
logging and branch macros mmt-dpi 1.10.0 made private, so every maintained C
source or C template must lie under one of them. CI runs the script in one
place only, the ``container`` job of ``.github/workflows/ci.yml``
(``make test-container`` on amd64 and arm64), in the image the
``Dockerfile`` builds, whose build checks that pkg-config finds mmt-dpi. The
project has no YAML parser, so the workflow, the Makefile and the Dockerfile
are read as text, without their comment lines, so that a comment cannot
stand in for what it describes.
"""

from __future__ import annotations

import re
import shlex
import subprocess
from pathlib import Path, PurePosixPath

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "tests" / "check_ndn_plugin.sh"
WORKFLOW = REPO / ".github" / "workflows" / "ci.yml"
MAKEFILE = REPO / "Makefile"
DOCKERFILE = REPO / "Dockerfile"
C_GLOBS = ("*.c", "*.h", "*.c.j2", "*.h.j2")
JOB = "container"


def _uncommented(path: Path) -> str:
    """The file without its comment lines."""
    lines = path.read_text(encoding="utf-8").splitlines()
    return "\n".join(line for line in lines if not line.lstrip().startswith("#"))


def _scan_dirs() -> list[str]:
    match = re.search(r"^SCAN_DIRS=\((.*)\)$", _uncommented(SCRIPT), re.MULTILINE)
    assert match is not None, f"no SCAN_DIRS=(...) in {SCRIPT}"
    return shlex.split(match.group(1))


def _tracked_c() -> list[str]:
    out = subprocess.run(
        ["git", "-C", str(REPO), "ls-files", "-z", "--", *C_GLOBS],
        capture_output=True,
        check=True,
    ).stdout
    return sorted(name for name in out.decode("utf-8").split("\0") if name)


def test_scan_dirs_exist() -> None:
    dirs = _scan_dirs()
    assert dirs, "SCAN_DIRS is empty"
    for name in dirs:
        assert (REPO / name).is_dir(), f"SCAN_DIRS entry {name!r} is not a directory"


def test_every_maintained_c_file_is_under_a_scan_dir() -> None:
    # A new directory of C sources or C templates must be added to SCAN_DIRS.
    dirs = _scan_dirs()
    files = _tracked_c()
    assert files, "git ls-files lists no C file"
    outside = [f for f in files if PurePosixPath(f).parts[0] not in dirs]
    assert not outside, f"C files outside SCAN_DIRS {dirs}: {outside}"


def test_the_scan_includes_every_c_glob() -> None:
    script = _uncommented(SCRIPT)
    for glob in C_GLOBS:
        assert f"--include='{glob}'" in script, f"the macro scan does not include {glob}"


def _job(name: str) -> str | None:
    """The text of the workflow's job ``name`` (comments excluded), up to the next job."""
    match = re.search(
        rf"^  {re.escape(name)}:\n(.*?)(?=^  [\w-]+:\n|\Z)",
        _uncommented(WORKFLOW),
        re.MULTILINE | re.DOTALL,
    )
    return None if match is None else match.group(1)


def test_the_container_job_is_the_ndn_check_on_both_arches() -> None:
    job = _job(JOB)
    assert job is not None, f"no {JOB} job in {WORKFLOW}"
    rows = re.findall(r"^          - runner: (\S+)\n            arch: (\S+)$", job, re.MULTILINE)
    assert set(rows) == {("ubuntu-24.04", "amd64"), ("ubuntu-24.04-arm", "arm64")}, rows
    assert re.search(
        r'^        run: make test-container MMT_DPI_TAG="\$MMT_DPI_TAG"$', job, re.MULTILINE
    ), f"the {JOB} job does not run make test-container"
    # It must not be skippable or allowed to fail.
    assert not re.search(r"^\s+(-\s+)?(if|continue-on-error):", job, re.MULTILINE), job


def test_no_runner_ndn_job_remains() -> None:
    # #42: the container job is the single NDN check.
    assert _job("ndn-check") is None
    assert "check_ndn_plugin.sh" not in _uncommented(WORKFLOW)


def test_make_test_container_runs_the_ndn_check() -> None:
    match = re.search(r"^test-container:.*\n((?:\t.*\n?)+)", _uncommented(MAKEFILE), re.MULTILINE)
    assert match is not None, f"no test-container recipe in {MAKEFILE}"
    assert "bash tests/check_ndn_plugin.sh" in match.group(1)


def test_the_image_build_fails_when_pkg_config_cannot_find_mmt_dpi() -> None:
    dockerfile = _uncommented(DOCKERFILE)
    install = re.search(
        r"apt-get install -y --no-install-recommends \\\n\s+([^\\\n]*)", dockerfile
    )
    assert install is not None, "no apt-get install of the toolchain"
    assert "pkg-config" in install.group(1).split()
    assert re.search(r"pkg-config --exists mmt-dpi \|\| fail ", dockerfile)
    assert re.search(r'\[ "\$pc" = "\$\{MMT_DPI_TAG#v\}" \] \|\| fail ', dockerfile)
