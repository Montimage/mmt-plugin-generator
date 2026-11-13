"""Finding the mmt-dpi SDK prefix (``docs/design/cli.md``, section 9).

A prefix is the directory that holds ``dpi/include``, ``dpi/lib`` and
``plugins/`` (``/opt/mmt`` for the published packages). It is taken from the
first of:

1. ``--sdk PREFIX`` (the ``cli_prefix`` argument);
2. the ``MMT_BASE`` environment variable (ignored when empty);
3. the pkg-config file ``mmt-dpi.pc``, read (not run: no ``pkg-config``
   binary and no shell are needed) from the directories of
   ``PKG_CONFIG_PATH``, then of ``PKG_CONFIG_LIBDIR`` when set or else
   pkg-config's default search path (``default_pkg_config_dirs``). The prefix
   is its ``includedir`` variable without the final ``/dpi/include``. The
   mmt-dpi package installs ``/usr/share/pkgconfig/mmt-dpi.pc``;
4. ``/opt/mmt``, when that directory exists.

Relative paths (``--sdk``, ``MMT_BASE``, ``PKG_CONFIG_PATH`` entries) are
resolved against the current directory, without following symlinks. A
prefix without ``dpi/include/mmt_log.h`` (mmt-dpi >= 1.10.0 installs it) is
``sdk.invalid-prefix``; finding none is ``sdk.not-found`` for the commands
that need one (``require_sdk``).

The version is read from the SDK itself: the ``VERSION`` string macro of
``dpi/include/mmt_core.h`` (``#define VERSION "1.10.2"``), which every
install method ships with the headers the compiler uses. It is ``None`` when
the header has none.

File access goes through ``os.path.isfile``/``os.path.isdir`` and ``open``,
so the unit tests can prove that nothing outside their temporary prefixes is
read.
"""

from __future__ import annotations

import os
import re
import sysconfig
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum

from mmt_plugin.diagnostics import CliError

__all__ = [
    "DEFAULT_PREFIX",
    "MARKER_HEADER",
    "PC_FILE",
    "VERSION_HEADER",
    "Sdk",
    "SdkSource",
    "default_pkg_config_dirs",
    "find_pc_file",
    "find_sdk",
    "parse_pc",
    "read_version",
    "require_sdk",
]

#: The last place looked at.
DEFAULT_PREFIX = "/opt/mmt"
#: The pkg-config file of mmt-dpi.
PC_FILE = "mmt-dpi.pc"
#: A prefix is valid when it has this file.
MARKER_HEADER = "dpi/include/mmt_log.h"
#: The header whose ``VERSION`` macro gives the SDK version.
VERSION_HEADER = "dpi/include/mmt_core.h"

_INCLUDE_SUFFIX = "/dpi/include"
_VERSION_MACRO = re.compile(r'^[ \t]*#[ \t]*define[ \t]+VERSION[ \t]+"([^"\n]*)"', re.MULTILINE)
_PC_VARIABLE = re.compile(r"^([A-Za-z0-9_.]+)[ \t]*=(.*)$")
_PC_FIELD = re.compile(r"^([A-Za-z0-9_.]+)[ \t]*:(.*)$")
_PC_REFERENCE = re.compile(r"\$\{([A-Za-z0-9_.]+)\}")

_HINT_PREFIX = (
    "pass the prefix that holds dpi/include/mmt_log.h (mmt-dpi >= 1.10.0) with --sdk or MMT_BASE"
)


class SdkSource(str, Enum):
    """Where the prefix came from, as reported in ``context.sdk.source``."""

    CLI = "--sdk"
    ENV = "MMT_BASE"
    PKG_CONFIG = "pkg-config"
    DEFAULT = "/opt/mmt"


@dataclass(frozen=True)
class Sdk:
    """A found SDK: its absolute ``prefix``, where it came from, its version
    (``None`` when unknown), and the ``.pc`` file when pkg-config found it."""

    prefix: str
    source: SdkSource
    version: str | None
    pc_file: str | None = None

    @property
    def include_dir(self) -> str:
        """``<prefix>/dpi/include``, the ``-I`` directory."""
        return f"{self.prefix}/dpi/include"


def _absolute(path: str, cwd: str | None) -> str:
    base = os.getcwd() if cwd is None else cwd
    return os.path.normpath(os.path.join(base, path))


def default_pkg_config_dirs() -> tuple[str, ...]:
    """pkg-config's default search path on Linux, multiarch directories
    included when Python knows the triplet (``x86_64-linux-gnu``)."""
    multiarch = sysconfig.get_config_var("MULTIARCH")
    dirs = ["/usr/local/lib/pkgconfig", "/usr/local/share/pkgconfig"]
    if isinstance(multiarch, str) and multiarch:
        dirs.insert(0, f"/usr/local/lib/{multiarch}/pkgconfig")
        dirs.append(f"/usr/lib/{multiarch}/pkgconfig")
    dirs += ["/usr/lib64/pkgconfig", "/usr/lib/pkgconfig", "/usr/share/pkgconfig"]
    return tuple(dirs)


def find_pc_file(
    env: Mapping[str, str], default_dirs: Sequence[str], *, cwd: str | None = None
) -> str | None:
    """The first ``mmt-dpi.pc`` on pkg-config's search path, or ``None``.

    The path is ``PKG_CONFIG_PATH``, then ``PKG_CONFIG_LIBDIR`` if it is set
    (even empty), else ``default_dirs``; empty entries are skipped.
    """
    dirs = env.get("PKG_CONFIG_PATH", "").split(os.pathsep)
    libdir = env.get("PKG_CONFIG_LIBDIR")
    dirs += list(default_dirs) if libdir is None else libdir.split(os.pathsep)
    for d in dirs:
        if not d:
            continue
        candidate = os.path.join(_absolute(d, cwd), PC_FILE)
        if os.path.isfile(candidate):
            return candidate
    return None


def parse_pc(text: str, pc_file: str) -> tuple[dict[str, str], dict[str, str]]:
    """The variables and fields of a ``.pc`` file, variables expanded.

    ``${pcfiledir}`` is the file's directory, as in pkg-config. Raises
    ``ValueError`` on a reference to an undefined variable.
    """
    variables = {"pcfiledir": os.path.dirname(pc_file)}
    fields: dict[str, str] = {}

    def expand(value: str) -> str:
        def sub(match: re.Match[str]) -> str:
            name = match.group(1)
            if name not in variables:
                raise ValueError(f"undefined variable ${{{name}}}")
            return variables[name]

        return _PC_REFERENCE.sub(sub, value.replace("$$", "\0")).replace("\0", "$")

    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        var = _PC_VARIABLE.match(line)
        field = _PC_FIELD.match(line)
        # "a=b:c" is a variable, "Cflags: -DX=1" a field: the first separator wins.
        if var and (field is None or line.index("=") < line.index(":")):
            variables[var.group(1)] = expand(var.group(2).strip())
        elif field:
            fields[field.group(1)] = expand(field.group(2).strip())
    return variables, fields


def _read_text(path: str) -> str:
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read()


def read_version(prefix: str) -> str | None:
    """The ``VERSION`` macro of ``<prefix>/dpi/include/mmt_core.h``, or ``None``."""
    path = os.path.join(prefix, VERSION_HEADER)
    if not os.path.isfile(path):
        return None
    try:
        match = _VERSION_MACRO.search(_read_text(path))
    except OSError:
        return None
    if match is None:
        return None
    return match.group(1).strip() or None


def _sdk_at(prefix: str, source: SdkSource, given: str, pc_file: str | None = None) -> Sdk:
    """The SDK at ``prefix``; ``sdk.invalid-prefix`` when it has no marker header."""
    if not os.path.isfile(os.path.join(prefix, MARKER_HEADER)):
        if pc_file is not None:
            where = f"{PC_FILE} ({pc_file}) points to {prefix}"
        elif source is SdkSource.DEFAULT:
            where = prefix
        else:
            where = f"{source.value} {given}" + ("" if given == prefix else f" ({prefix})")
        raise CliError(
            "sdk.invalid-prefix",
            f"{where}: no {MARKER_HEADER}, so not an mmt-dpi >= 1.10.0 SDK prefix",
            _HINT_PREFIX,
        )
    return Sdk(prefix=prefix, source=source, version=read_version(prefix), pc_file=pc_file)


def _from_pc(pc_file: str) -> Sdk:
    hint = f"fix or remove {pc_file}, or pass the SDK prefix with --sdk or MMT_BASE"
    try:
        variables, _ = parse_pc(_read_text(pc_file), pc_file)
    except (OSError, ValueError) as exc:
        raise CliError("sdk.invalid-pkg-config", f"cannot read {pc_file}: {exc}", hint) from exc
    includedir = os.path.normpath(variables.get("includedir", ""))
    if not os.path.isabs(includedir) or not includedir.endswith(_INCLUDE_SUFFIX):
        raise CliError(
            "sdk.invalid-pkg-config",
            f"{pc_file}: includedir {variables.get('includedir', '')!r} is not an absolute"
            f" <prefix>{_INCLUDE_SUFFIX} path",
            hint,
        )
    prefix = includedir[: -len(_INCLUDE_SUFFIX)] or "/"
    return _sdk_at(prefix, SdkSource.PKG_CONFIG, prefix, pc_file)


def find_sdk(
    cli_prefix: str | None,
    env: Mapping[str, str],
    *,
    pkg_config_dirs: Sequence[str] | None = None,
    default_prefix: str = DEFAULT_PREFIX,
    cwd: str | None = None,
) -> Sdk | None:
    """Find the SDK in precedence order; ``None`` when there is none.

    ``env`` is the environment (``os.environ``); ``pkg_config_dirs`` replaces
    pkg-config's default search path and ``default_prefix`` the final
    ``/opt/mmt`` (tests point both into temporary directories); ``cwd`` is
    the directory relative paths are resolved against (default: the current
    one). An explicit prefix (``--sdk``, ``MMT_BASE``, the ``.pc`` file) that
    is not valid raises ``CliError`` (class sdk, exit 4) instead of falling
    through to the next source: silently using another SDK would hide the
    mistake.
    """
    if cli_prefix is not None:
        return _sdk_at(_absolute(cli_prefix, cwd), SdkSource.CLI, cli_prefix)
    env_prefix = env.get("MMT_BASE", "")
    if env_prefix:
        return _sdk_at(_absolute(env_prefix, cwd), SdkSource.ENV, env_prefix)
    dirs = default_pkg_config_dirs() if pkg_config_dirs is None else pkg_config_dirs
    pc_file = find_pc_file(env, dirs, cwd=cwd)
    if pc_file is not None:
        return _from_pc(pc_file)
    default = _absolute(default_prefix, cwd)
    if os.path.isdir(default):
        return _sdk_at(default, SdkSource.DEFAULT, default_prefix)
    return None


def require_sdk(
    cli_prefix: str | None,
    env: Mapping[str, str],
    *,
    pkg_config_dirs: Sequence[str] | None = None,
    default_prefix: str = DEFAULT_PREFIX,
    cwd: str | None = None,
) -> Sdk:
    """``find_sdk``, but no SDK is ``sdk.not-found`` (exit 4)."""
    sdk = find_sdk(
        cli_prefix, env, pkg_config_dirs=pkg_config_dirs, default_prefix=default_prefix, cwd=cwd
    )
    if sdk is None:
        raise CliError(
            "sdk.not-found",
            f"no mmt-dpi SDK found (--sdk, MMT_BASE, {PC_FILE}, {default_prefix})",
            "install mmt-dpi >= 1.10.2 and pass its prefix (the directory that holds"
            " dpi/include) with --sdk PREFIX or MMT_BASE=PREFIX",
        )
    return sdk
