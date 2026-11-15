"""The release assets hold the package and its JSON Schemas (plan task T5.3, #30).

``tests/build_release_assets.sh OUT_DIR`` builds the assets of a release;
with ``MMT_RELEASE_DIST=OUT_DIR`` these tests check them: exactly the wheel,
the sdist, the schemas tarball and ``SHA256SUMS``, each named with this
checkout's version (``mmt_plugin.__version__``); every file of
``src/mmt_plugin/`` in the wheel and the sdist, byte for byte, so every JSON
Schema (``schemas/cli/v1/`` included) ships in both; the wheel's metadata
and console script; every schema in the schemas tarball, reproducibly
packed; and ``SHA256SUMS`` matching the files. Without the variable they
skip, unless ``MMT_REQUIRE_RELEASE_DIST=1`` (``.github/workflows/release.yml``)::

    bash tests/build_release_assets.sh <dir>
    MMT_RELEASE_DIST=<dir> uv run pytest tests/unit/release/test_dist.py
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import tarfile
import zipfile
from email.parser import Parser
from pathlib import Path

import pytest

from mmt_plugin import __version__

REPO = Path(__file__).resolve().parents[3]
PACKAGE = REPO / "src" / "mmt_plugin"
DIST_ENV = "MMT_RELEASE_DIST"
REQUIRE_ENV = "MMT_REQUIRE_RELEASE_DIST"

WHEEL = f"mmt_plugin-{__version__}-py3-none-any.whl"
SDIST = f"mmt_plugin-{__version__}.tar.gz"
SCHEMAS = f"mmt-plugin-schemas-{__version__}.tar.gz"
SUMS = "SHA256SUMS"


@pytest.fixture(scope="module")
def dist() -> Path:
    value = os.environ.get(DIST_ENV)
    if not value:
        if os.environ.get(REQUIRE_ENV) == "1":
            pytest.fail(f"{REQUIRE_ENV}=1 but {DIST_ENV} is not set")
        pytest.skip(f"{DIST_ENV} is not set (the output of tests/build_release_assets.sh)")
    path = Path(value)
    assert path.is_dir(), f"{DIST_ENV}={value} is not a directory"
    return path


def _package_files() -> dict[str, bytes]:
    """The package's tracked files, by path relative to ``src/``."""
    listed = subprocess.run(
        ["git", "-C", str(REPO), "ls-files", "-z", "--", "src/mmt_plugin"],
        check=True,
        capture_output=True,
    ).stdout.decode()
    files = {}
    for name in filter(None, listed.split("\0")):
        files[name.removeprefix("src/")] = (REPO / name).read_bytes()
    assert files, "git ls-files lists nothing under src/mmt_plugin"
    return files


def _schemas() -> dict[str, bytes]:
    """Every JSON Schema the package ships, by path relative to ``schemas/``."""
    root = PACKAGE / "schemas"
    found = {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*.json")}
    assert any(name.startswith("cli/v1/") for name in found), found
    return found


def test_the_assets_are_the_four_release_files(dist: Path) -> None:
    assert sorted(p.name for p in dist.iterdir()) == sorted([WHEEL, SDIST, SCHEMAS, SUMS])


def test_the_wheel_holds_every_package_file(dist: Path) -> None:
    with zipfile.ZipFile(dist / WHEEL) as wheel:
        names = {n for n in wheel.namelist() if not n.endswith("/")}
        for name, data in _package_files().items():
            assert name in names, f"{name} is not in {WHEEL}"
            assert wheel.read(name) == data, f"{name} differs in {WHEEL}"
        for name in _schemas():
            assert f"mmt_plugin/schemas/{name}" in names
        unexpected = {
            n
            for n in names
            if not n.startswith((f"mmt_plugin-{__version__}.dist-info/", "mmt_plugin/"))
        }
        assert not unexpected, unexpected


def test_the_wheel_metadata_and_console_script(dist: Path) -> None:
    info = f"mmt_plugin-{__version__}.dist-info"
    with zipfile.ZipFile(dist / WHEEL) as wheel:
        metadata = Parser().parsestr(wheel.read(f"{info}/METADATA").decode())
        entry_points = wheel.read(f"{info}/entry_points.txt").decode()
    assert metadata["Name"] == "mmt-plugin"
    assert metadata["Version"] == __version__
    assert metadata["Requires-Python"] == ">=3.10"
    assert [r.split(">")[0].split("<")[0] for r in metadata.get_all("Requires-Dist", [])] == [
        "jinja2"
    ]
    assert "[console_scripts]" in entry_points
    assert "mmt-plugin = mmt_plugin.cli:main" in entry_points


def test_the_sdist_holds_every_package_file(dist: Path) -> None:
    top = f"mmt_plugin-{__version__}"
    with tarfile.open(dist / SDIST) as sdist:
        names = {m.name for m in sdist.getmembers() if m.isfile()}
        for name, data in _package_files().items():
            member = f"{top}/src/{name}"
            assert member in names, f"{member} is not in {SDIST}"
            extracted = sdist.extractfile(member)
            assert extracted is not None
            assert extracted.read() == data, f"{member} differs in {SDIST}"
        assert f"{top}/pyproject.toml" in names
        assert f"{top}/PKG-INFO" in names


def test_the_schemas_tarball_holds_every_schema(dist: Path) -> None:
    top = f"mmt-plugin-schemas-{__version__}"
    expected = _schemas()
    with tarfile.open(dist / SCHEMAS) as tar:
        members = tar.getmembers()
        files = {m.name.removeprefix(f"{top}/"): m for m in members if m.isfile()}
        assert sorted(files) == sorted(expected)
        for name, member in files.items():
            extracted = tar.extractfile(member)
            assert extracted is not None
            assert extracted.read() == expected[name], name
    for member in members:
        assert member.name == top or member.name.startswith(f"{top}/"), member.name
        assert member.isfile() or member.isdir(), member.name
        # Reproducible: no owner, one mtime for every member.
        assert (member.uid, member.gid, member.uname, member.gname) == (0, 0, "", ""), member.name
        assert member.mtime == members[0].mtime, member.name
    assert [m.name for m in members] == sorted(m.name for m in members)


def test_sha256sums_lists_every_other_asset(dist: Path) -> None:
    lines = (dist / SUMS).read_text(encoding="utf-8").splitlines()
    sums = {}
    for line in lines:
        digest, _, name = line.partition("  ")
        sums[name] = digest
    assert sorted(sums) == sorted([WHEEL, SDIST, SCHEMAS])
    assert list(sums) == sorted(sums)
    for name, digest in sums.items():
        assert hashlib.sha256((dist / name).read_bytes()).hexdigest() == digest, name
