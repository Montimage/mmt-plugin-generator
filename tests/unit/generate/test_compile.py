"""Compile every golden pair against the real mmt-dpi headers.

``-fsyntax-only -std=gnu11 -Wall -Wextra -Werror`` (``c_std`` of the SDK
profile), for the generated source and for a stub ``src/<label>_impl.c``
that defines the header's hooks. Building and loading the plugin is T1.7.

The headers are those of the verified mmt-dpi 1.10.2 package, extracted
into a private prefix (never ``/opt/mmt``)::

    deb="$(bash tests/fetch_mmt_dpi_package.sh <download dir>)"
    dpkg-deb -x "$deb" <dir>
    export MMT_GOLDEN_SDK=<dir>/opt/mmt MMT_GOLDEN_CC=clang
    uv run pytest tests/unit/generate/test_compile.py

Without ``MMT_GOLDEN_SDK`` the tests skip, unless
``MMT_REQUIRE_GOLDEN_COMPILE=1`` (CI's "SDK profile vs mmt-dpi headers" job)
makes them fail instead. ``MMT_GOLDEN_CC`` picks the compiler (default gcc).
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from .helpers import GOLDEN, impl_stub, profile, run_model
from .test_golden import ACCEPTED

SDK_ENV = "MMT_GOLDEN_SDK"
CC_ENV = "MMT_GOLDEN_CC"
REQUIRE_ENV = "MMT_REQUIRE_GOLDEN_COMPILE"


def _include_dir() -> Path:
    prefix = os.environ.get(SDK_ENV, "")
    if not prefix:
        if os.environ.get(REQUIRE_ENV) == "1":
            pytest.fail(f"{REQUIRE_ENV}=1 but {SDK_ENV} is not set")
        pytest.skip(f"{SDK_ENV} is not set (an extracted mmt-dpi prefix)")
    include = Path(prefix) / "dpi" / "include"
    assert (include / "plugin_defs.h").is_file(), f"{include} has no plugin_defs.h"
    return include


def _compiler() -> str:
    cc = os.environ.get(CC_ENV, "gcc")
    if shutil.which(cc) is None:
        if os.environ.get(REQUIRE_ENV) == "1":
            pytest.fail(f"{cc} is not installed")
        pytest.skip(f"{cc} is not installed")
    return cc


def _flags() -> list[str]:
    return ["-fsyntax-only", f"-std={profile().c_std}", "-Wall", "-Wextra", "-Werror"]


@pytest.mark.parametrize("name", ACCEPTED)
def test_the_golden_pair_compiles_against_the_sdk_headers(name: str, tmp_path: Path) -> None:
    include = _include_dir()
    cc = _compiler()
    generation = run_model(name).generation
    assert generation is not None
    work = tmp_path / name
    shutil.copytree(GOLDEN / name, work)
    impl = work / f"{generation.label.lower()}_impl.c"
    impl.write_text(impl_stub(generation))
    sources = [work / f.name for f in generation.files if f.name.endswith(".c")] + [impl]
    for source in sources:
        proc = subprocess.run(
            [cc, *_flags(), "-I", str(work), "-I", str(include), str(source)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 0, f"{cc} {source.name}:\n{proc.stderr}"
        assert proc.stderr == "", proc.stderr


def test_a_missing_hook_definition_is_a_declared_symbol(tmp_path: Path) -> None:
    # Plan decision 3: the header declares every hook, so a stub that lacks
    # one still compiles here; the build (T2.2, T2.3) fails at link time.
    generation = run_model("pdl_scopes").generation
    assert generation is not None
    header = generation.file("pdl_scopes_mmt_plugin.h").text
    for hook in generation.hooks:
        assert f"{hook.declaration};" in header
