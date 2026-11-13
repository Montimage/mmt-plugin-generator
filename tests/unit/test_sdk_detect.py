"""Tests for ``mmt_plugin.sdk.detect``: one per step of the prefix precedence
(``--sdk`` > ``MMT_BASE`` > ``mmt-dpi.pc`` > ``/opt/mmt``), all on temporary
prefixes; the ``forbid_system_sdk`` guard (conftest) fails any test that
touches the host's SDK."""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

import pytest

from mmt_plugin.diagnostics import CliError
from mmt_plugin.exitcodes import ExitCode
from mmt_plugin.sdk.detect import (
    DEFAULT_PREFIX,
    PC_FILE,
    Sdk,
    SdkSource,
    default_pkg_config_dirs,
    find_pc_file,
    find_sdk,
    parse_pc,
    read_version,
    require_sdk,
)

MakePrefix = Callable[..., Path]
MakePc = Callable[..., Path]

#: What the conftest guard raises (an AssertionError subclass).
GUARD = r"^a test (opened|looked at) "


@pytest.fixture
def setup(tmp_path: Path, make_prefix: MakePrefix, make_pc: MakePc) -> dict[str, Path]:
    """Four valid prefixes, one per source, and a pkg-config dir for the third."""
    paths = {name: make_prefix(tmp_path / name) for name in ("cli", "env", "pc", "default")}
    paths["pcdir"] = tmp_path / "pkgconfig"
    make_pc(paths["pcdir"], f"{paths['pc']}/dpi/include")
    return paths


def _find(
    setup: dict[str, Path], cli: str | None = None, env: dict[str, str] | None = None
) -> Sdk | None:
    return find_sdk(
        cli,
        {} if env is None else env,
        pkg_config_dirs=[str(setup["pcdir"])],
        default_prefix=str(setup["default"]),
    )


# --- precedence --------------------------------------------------------------


def test_sdk_option_comes_first(setup: dict[str, Path]) -> None:
    sdk = _find(setup, str(setup["cli"]), {"MMT_BASE": str(setup["env"])})
    assert sdk == Sdk(str(setup["cli"]), SdkSource.CLI, "1.10.2")


def test_mmt_base_comes_second(setup: dict[str, Path]) -> None:
    sdk = _find(setup, None, {"MMT_BASE": str(setup["env"])})
    assert sdk == Sdk(str(setup["env"]), SdkSource.ENV, "1.10.2")


def test_pkg_config_file_comes_third(setup: dict[str, Path]) -> None:
    sdk = _find(setup)
    pc = str(setup["pcdir"] / PC_FILE)
    assert sdk == Sdk(str(setup["pc"]), SdkSource.PKG_CONFIG, "1.10.2", pc_file=pc)


def test_opt_mmt_comes_last(setup: dict[str, Path]) -> None:
    (setup["pcdir"] / PC_FILE).unlink()
    sdk = _find(setup)
    assert sdk == Sdk(str(setup["default"]), SdkSource.DEFAULT, "1.10.2")


def test_no_sdk_at_all(tmp_path: Path) -> None:
    kwargs = {"pkg_config_dirs": [str(tmp_path)], "default_prefix": str(tmp_path / "none")}
    assert find_sdk(None, {}, **kwargs) is None  # type: ignore[arg-type]
    with pytest.raises(CliError) as info:
        require_sdk(None, {}, **kwargs)  # type: ignore[arg-type]
    assert info.value.code == "sdk.not-found"
    assert info.value.exit_code is ExitCode.SDK
    assert info.value.hint and "--sdk" in info.value.hint and "MMT_BASE" in info.value.hint
    assert str(tmp_path / "none") in info.value.message


def test_require_sdk_returns_the_sdk(setup: dict[str, Path]) -> None:
    sdk = require_sdk(
        None, {}, pkg_config_dirs=[str(setup["pcdir"])], default_prefix=str(setup["default"])
    )
    assert sdk.source is SdkSource.PKG_CONFIG


def test_an_empty_mmt_base_is_unset(setup: dict[str, Path]) -> None:
    sdk = _find(setup, None, {"MMT_BASE": ""})
    assert sdk is not None and sdk.source is SdkSource.PKG_CONFIG


# --- relative paths ----------------------------------------------------------


def test_relative_sdk_and_mmt_base_are_made_absolute(
    setup: dict[str, Path], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    (tmp_path / "work").mkdir()
    monkeypatch.chdir(tmp_path / "work")
    sdk = _find(setup, "../cli/./")
    assert sdk is not None and sdk.prefix == str(setup["cli"]) and os.path.isabs(sdk.prefix)
    sdk = _find(setup, None, {"MMT_BASE": "../env"})
    assert sdk is not None and sdk.prefix == str(setup["env"])


def test_relative_paths_use_the_given_cwd(setup: dict[str, Path], tmp_path: Path) -> None:
    sdk = find_sdk("cli", {}, pkg_config_dirs=[], default_prefix="none", cwd=str(tmp_path))
    assert sdk is not None and sdk.prefix == str(setup["cli"])
    pc = find_pc_file({"PKG_CONFIG_PATH": "pkgconfig"}, [], cwd=str(tmp_path))
    assert pc == str(setup["pcdir"] / PC_FILE)


# --- pkg-config ----------------------------------------------------------------


def test_pkg_config_path_comes_before_the_default_dirs(
    tmp_path: Path, make_prefix: MakePrefix, make_pc: MakePc
) -> None:
    first = make_prefix(tmp_path / "first")
    second = make_prefix(tmp_path / "second")
    make_pc(tmp_path / "env-dir", f"{first}/dpi/include")
    make_pc(tmp_path / "std-dir", f"{second}/dpi/include")
    env = {"PKG_CONFIG_PATH": f"{tmp_path / 'missing'}::{tmp_path / 'env-dir'}"}
    sdk = find_sdk(
        None, env, pkg_config_dirs=[str(tmp_path / "std-dir")], default_prefix="/nonexistent"
    )
    assert sdk is not None and sdk.prefix == str(first)


def test_pkg_config_libdir_replaces_the_default_dirs(
    tmp_path: Path, make_prefix: MakePrefix, make_pc: MakePc
) -> None:
    prefix = make_prefix(tmp_path / "p")
    make_pc(tmp_path / "std-dir", f"{prefix}/dpi/include")
    dirs = [str(tmp_path / "std-dir")]
    assert find_pc_file({}, dirs) == str(tmp_path / "std-dir" / PC_FILE)
    assert find_pc_file({"PKG_CONFIG_LIBDIR": ""}, dirs) is None
    assert find_pc_file({"PKG_CONFIG_LIBDIR": str(tmp_path / "std-dir")}, []) is not None


def test_the_real_pc_file_layout(tmp_path: Path, make_prefix: MakePrefix, make_pc: MakePc) -> None:
    # The published file has no prefix variable: includedir is absolute.
    prefix = make_prefix(tmp_path / "opt" / "mmt")
    pc = make_pc(tmp_path / "pc", f"{prefix}/dpi/include", prefix_var=False)
    variables, fields = parse_pc(pc.read_text(), str(pc))
    assert variables["includedir"] == f"{prefix}/dpi/include"
    assert variables["rpath"] == "-Wl,-rpath,/opt/mmt/dpi/lib"
    assert fields["Version"] == "1.10.2"
    assert fields["Cflags"] == f"-I{prefix}/dpi/include"


def test_pc_variables(tmp_path: Path) -> None:
    text = (
        "# comment\nprefix=${pcfiledir}/../..\nincludedir=${prefix}/dpi/include # trailing\n"
        "price=$$5\nCflags: -DX=1 -I${includedir}\nweird=a:b\n"
    )
    pc = str(tmp_path / "lib" / "pkgconfig" / PC_FILE)
    variables, fields = parse_pc(text, pc)
    assert variables["includedir"] == f"{tmp_path}/lib/pkgconfig/../../dpi/include"
    assert variables["price"] == "$5"
    assert variables["weird"] == "a:b"
    assert fields["Cflags"] == f"-DX=1 -I{variables['includedir']}"
    with pytest.raises(ValueError, match="undefined variable"):
        parse_pc("includedir=${nowhere}/x\n", pc)


def test_a_relocatable_pc_file(tmp_path: Path, make_prefix: MakePrefix) -> None:
    prefix = make_prefix(tmp_path / "sdk")
    pcdir = prefix / "dpi" / "lib" / "pkgconfig"
    pcdir.mkdir(parents=True)
    (pcdir / PC_FILE).write_text(
        "prefix=${pcfiledir}/../../..\nincludedir=${prefix}/dpi/include\n"
    )
    sdk = find_sdk(None, {}, pkg_config_dirs=[str(pcdir)], default_prefix="/nonexistent")
    assert sdk is not None and sdk.prefix == str(prefix)


@pytest.mark.parametrize(
    "text",
    [
        "libdir=/x\n",  # no includedir
        "includedir=relative/dpi/include\n",
        "includedir=/somewhere/include\n",
        "includedir=${undefined}/dpi/include\n",
    ],
)
def test_a_bad_pc_file(tmp_path: Path, text: str) -> None:
    (tmp_path / PC_FILE).write_text(text)
    with pytest.raises(CliError) as info:
        find_sdk(None, {}, pkg_config_dirs=[str(tmp_path)], default_prefix="/nonexistent")
    assert info.value.code == "sdk.invalid-pkg-config"
    assert info.value.exit_code is ExitCode.SDK
    assert info.value.hint and str(tmp_path / PC_FILE) in info.value.hint


def test_an_unreadable_pc_file(tmp_path: Path) -> None:
    (tmp_path / PC_FILE).mkdir()  # a directory is not a file: skipped
    assert find_pc_file({}, [str(tmp_path)]) is None


# --- invalid prefixes ----------------------------------------------------------


@pytest.mark.parametrize("source", ["--sdk", "MMT_BASE"])
def test_an_explicit_prefix_without_mmt_log_h_does_not_fall_through(
    setup: dict[str, Path], make_prefix: MakePrefix, tmp_path: Path, source: str
) -> None:
    bad = str(make_prefix(tmp_path / "old", marker=False))
    with pytest.raises(CliError) as info:
        if source == "--sdk":
            _find(setup, bad, {"MMT_BASE": str(setup["env"])})
        else:
            _find(setup, None, {"MMT_BASE": bad})
    assert info.value.code == "sdk.invalid-prefix"
    assert info.value.exit_code is ExitCode.SDK
    assert info.value.message.startswith(f"{source} {bad}: no dpi/include/mmt_log.h")
    assert info.value.hint and "mmt_log.h" in info.value.hint


def test_a_missing_explicit_prefix_is_invalid(setup: dict[str, Path], tmp_path: Path) -> None:
    with pytest.raises(CliError) as info:
        _find(setup, "does-not-exist")
    assert info.value.code == "sdk.invalid-prefix"
    assert f"({os.getcwd()}/does-not-exist)" in info.value.message


def test_a_pc_file_pointing_to_an_invalid_prefix(
    tmp_path: Path, make_prefix: MakePrefix, make_pc: MakePc
) -> None:
    bad = make_prefix(tmp_path / "bad", marker=False)
    pc = make_pc(tmp_path / "pc", f"{bad}/dpi/include")
    with pytest.raises(CliError) as info:
        find_sdk(None, {}, pkg_config_dirs=[str(tmp_path / "pc")], default_prefix="/nonexistent")
    assert info.value.code == "sdk.invalid-prefix"
    assert info.value.message.startswith(f"{PC_FILE} ({pc}) points to {bad}:")


def test_a_default_prefix_without_mmt_log_h(tmp_path: Path, make_prefix: MakePrefix) -> None:
    old = make_prefix(tmp_path / "opt-mmt", marker=False)
    with pytest.raises(CliError) as info:
        find_sdk(None, {}, pkg_config_dirs=[], default_prefix=str(old))
    assert info.value.code == "sdk.invalid-prefix"
    assert info.value.message.startswith(f"{old}: no dpi/include/mmt_log.h")


# --- version ----------------------------------------------------------------------


def test_version_comes_from_mmt_core_h(tmp_path: Path, make_prefix: MakePrefix) -> None:
    assert read_version(str(make_prefix(tmp_path / "a", version="1.11.0"))) == "1.11.0"
    assert read_version(str(make_prefix(tmp_path / "b", version=None))) is None
    assert read_version(str(make_prefix(tmp_path / "c", core=False))) is None
    assert read_version(str(make_prefix(tmp_path / "d", version=""))) is None
    spaced = make_prefix(tmp_path / "e", core=False) / "dpi" / "include" / "mmt_core.h"
    spaced.write_text('  #  define\tVERSION   "1.10.3" \n')
    assert read_version(str(tmp_path / "e")) == "1.10.3"


def test_an_sdk_with_an_unknown_version(tmp_path: Path, make_prefix: MakePrefix) -> None:
    prefix = make_prefix(tmp_path / "p", core=False)
    sdk = find_sdk(str(prefix), {})
    assert sdk == Sdk(str(prefix), SdkSource.CLI, None)
    assert sdk.include_dir == f"{prefix}/dpi/include"


# --- the guard ----------------------------------------------------------------------


def test_default_search_path_ends_with_the_fhs_directory() -> None:
    dirs = default_pkg_config_dirs()
    assert dirs[-1] == "/usr/share/pkgconfig"
    assert "/usr/lib/pkgconfig" in dirs and "/usr/local/lib/pkgconfig" in dirs
    assert DEFAULT_PREFIX == "/opt/mmt"


def test_the_guard_fails_a_test_that_reads_the_real_sdk() -> None:
    """Detection with its real defaults looks at the host's pkg-config dirs and
    /opt/mmt: under the guard that raises, so a test that forgot to inject
    its paths fails instead of reading the host."""
    with pytest.raises(AssertionError, match=GUARD):
        find_sdk(None, {})
    with pytest.raises(AssertionError, match=GUARD):
        os.path.isdir(DEFAULT_PREFIX)
    with pytest.raises(AssertionError, match=GUARD):
        os.path.isfile(f"{DEFAULT_PREFIX}/dpi/include/mmt_log.h")
    with pytest.raises(AssertionError, match=GUARD):
        open(f"{DEFAULT_PREFIX}/dpi/include/mmt_core.h")  # noqa: SIM115
    with pytest.raises(AssertionError, match=GUARD):
        os.listdir("/usr/share/pkgconfig")


def test_explicit_sources_never_look_at_the_defaults(setup: dict[str, Path]) -> None:
    # Under the guard: --sdk and MMT_BASE stop before pkg-config and /opt/mmt.
    assert find_sdk(str(setup["cli"]), {}) is not None
    assert find_sdk(None, {"MMT_BASE": str(setup["env"])}) is not None
