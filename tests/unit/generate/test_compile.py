"""Compile every golden pair against the real mmt-dpi headers.

``-fsyntax-only -std=gnu11 -Wall -Wextra -Werror`` (``c_std`` of the SDK
profile), for the generated source and for a stub ``src/<label>_impl.c``
that defines the header's hooks. Building and loading the plugin is T1.7;
here each golden pair is only linked into a program with the SDK's
``libmmt_core``, which checks that ``init_<label>_proto_struct()`` registers
every attribute (``register_attribute_with_protocol()`` refuses a
``data_len`` the type's SDK size does not allow), and another program checks
the profile's data type sizes against ``get_data_size_by_data_type()``.

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
import re
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


def _core_library(tmp_path: Path) -> tuple[Path, Path]:
    """The SDK's ``libmmt_core`` shared object, and a directory where its
    soname resolves to it (the package's own links are absolute
    ``/opt/mmt`` paths, so they may dangle in an extracted prefix)."""
    lib = _include_dir().parent / "lib"
    found = sorted(p for p in lib.glob("libmmt_core.so.*") if p.is_file() and not p.is_symlink())
    assert found, f"{lib} has no libmmt_core.so.<version>"
    real = found[-1]
    match = re.fullmatch(r"(libmmt_core\.so\.[0-9]+)(\.[0-9]+)*", real.name)
    assert match is not None, real.name
    run_dir = tmp_path / "lib"
    run_dir.mkdir()
    (run_dir / match.group(1)).symlink_to(real)
    return real, run_dir


def _run_program(source: Path, tmp_path: Path, *extra: Path) -> str:
    """Build ``source`` (and ``extra``) against the SDK headers and
    ``libmmt_core``, run it in ``tmp_path`` and return its stdout."""
    include, cc = _include_dir(), _compiler()
    core, run_dir = _core_library(tmp_path)
    program = tmp_path / "program"
    proc = subprocess.run(
        [
            cc,
            f"-std={profile().c_std}",
            "-I",
            str(source.parent),
            "-I",
            str(include),
            str(source),
            *map(str, extra),
            str(core),
            f"-Wl,-rpath,{run_dir}",
            "-o",
            str(program),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, f"{cc} {source.name}:\n{proc.stderr}"
    # In tmp_path: init_extraction() also loads the plugins of ./plugins.
    run = subprocess.run(
        [str(program)], capture_output=True, text=True, check=False, cwd=tmp_path, timeout=60
    )
    assert run.returncode == 0, f"{source.name} exited {run.returncode}:\n{run.stderr}"
    return run.stdout


def test_the_profile_data_sizes_are_the_sdk_ones(tmp_path: Path) -> None:
    # Review of #14: the generator keeps data_len within these sizes, and
    # register_attribute_with_protocol() checks it against the same function.
    types = [c for c in profile().constants if c.size is not None]
    lines = [
        f'    printf("%s %u\\n", "{c.name}", (unsigned)get_data_size_by_data_type({c.name}));'
        for c in types
    ]
    source = tmp_path / "sizes.c"
    source.write_text(
        '#include <stdio.h>\n#include "mmt_core.h"\n\nint main(void)\n{\n'
        + "\n".join(lines)
        + "\n    return 0;\n}\n"
    )
    found = dict(line.split() for line in _run_program(source, tmp_path).splitlines())
    assert found == {c.name: str(c.size) for c in types}


@pytest.mark.parametrize("name", ACCEPTED)
def test_the_golden_pair_registers_with_libmmt_core(name: str, tmp_path: Path) -> None:
    generation = run_model(name).generation
    assert generation is not None
    work = tmp_path / name
    shutil.copytree(GOLDEN / name, work)
    impl = work / f"{generation.label.lower()}_impl.c"
    impl.write_text(impl_stub(generation))
    init = f"init_{generation.label.lower()}_proto_struct"
    main = work / "main.c"
    main.write_text(
        '#include <stdio.h>\n#include "mmt_core.h"\n\n'
        f"int {init}(void);\n\n"
        "int main(void)\n{\n"
        '    if (!init_extraction()) {\n        puts("init_extraction failed");\n'
        "        return 1;\n    }\n"
        f'    printf("%d\\n", {init}());\n'
        "    return 0;\n}\n"
    )
    sources = [work / f.name for f in generation.files if f.name.endswith(".c")] + [impl]
    assert _run_program(main, tmp_path, *sources).strip() == "1", f"{init}() failed"


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
