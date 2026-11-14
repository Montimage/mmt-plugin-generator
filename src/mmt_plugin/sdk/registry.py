"""The run-time protocol registry of an installed SDK (``validate``, #17).

The SDK headers (the bundled profile) list only the SDK's own protocols: any
other plugin in the plugin directory can take ids and names too, and the
only reliable list is what mmt-dpi registers once it has loaded them
(README, "Plugin load order, ids and names"). ``read_registry`` gets it:

1. the plugin directory is ``$MMT_DPI_PLUGINS_DIR`` when set (it replaces
   ``<prefix>/plugins`` for every mmt-dpi program), else
   ``<prefix>/plugins``;
2. its ``*.so`` files, except ``exclude`` (the plugin being validated, whose
   installed copy would otherwise take its own id and name), are linked into
   a temporary directory;
3. a child Python process (``_registry_probe.py``, run with ``-I``) loads
   the SDK's ``libmmt_core`` with ``MMT_DPI_PLUGINS_DIR`` set to that
   directory, calls ``init_extraction()`` and prints every registered id and
   name as JSON.

Loading plugins runs their native code: the child process keeps a crash, a
hang (``timeout``) or stray output away from the CLI. Any failure is a
``RegistryError``; ``validate`` reports it as a warning
(``sdk.registry-unavailable``), the profile's checks still applying.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from mmt_plugin.sdk.detect import Sdk

__all__ = [
    "PLUGINS_DIR_ENV",
    "RegisteredProtocol",
    "Registry",
    "RegistryError",
    "compiled_plugin_dir",
    "core_library",
    "plugin_dir",
    "read_registry",
    "scanned_plugin_dir",
]

#: The environment variable that replaces ``<prefix>/plugins`` in mmt-dpi.
PLUGINS_DIR_ENV = "MMT_DPI_PLUGINS_DIR"

_PROBE = Path(__file__).with_name("_registry_probe.py")
_CORE_VERSIONED = re.compile(r"^libmmt_core\.so(\.[0-9]+)+$")


class RegistryError(Exception):
    """The registry could not be read; the message says why."""


@dataclass(frozen=True)
class RegisteredProtocol:
    """A protocol registered at run time: its id and name."""

    id: int
    name: str


@dataclass(frozen=True)
class Registry:
    """What mmt-dpi registers with the plugins of ``plugin_dir`` (absolute),
    minus the excluded file: ``plugins`` are the file names loaded, in
    load (C byte) order, and ``protocols`` every registered protocol, by id.
    """

    plugin_dir: str
    plugins: tuple[str, ...]
    protocols: tuple[RegisteredProtocol, ...]

    def by_id(self, pid: int) -> RegisteredProtocol | None:
        """The protocol registered with id ``pid``, or ``None``."""
        return next((p for p in self.protocols if p.id == pid), None)

    def by_name(self, name: str) -> RegisteredProtocol | None:
        """The protocol registered as ``name``, compared case-insensitively
        as mmt-dpi does, or ``None``."""
        key = name.casefold()
        return next((p for p in self.protocols if p.name.casefold() == key), None)


def plugin_dir(sdk: Sdk, env: Mapping[str, str]) -> str:
    """The plugin directory mmt-dpi programs load: ``$MMT_DPI_PLUGINS_DIR``
    (made absolute) when set and not empty, else ``<prefix>/plugins``."""
    given = env.get(PLUGINS_DIR_ENV, "")
    if given:
        return os.path.normpath(os.path.join(os.getcwd(), given))
    return os.path.join(sdk.prefix, "plugins")


#: An absolute directory ending in ``/plugins``, as a NUL-terminated string
#: of a shared object's read-only data.
_PLUGINS_LITERAL = re.compile(rb"(?<=\x00)/[\x21-\x7e]*/plugins(?=\x00)")


def compiled_plugin_dir(core: str) -> str | None:
    """The plugin directory compiled into ``libmmt_core`` (``core``), or
    ``None`` when it cannot be told.

    mmt-dpi 1.10.2 (``src/mmt_core/src/plugins_engine.c``) scans exactly one
    directory: ``$MMT_DPI_PLUGINS_DIR`` when set (absolute, else nothing
    loads), else ``PLUGINS_REPOSITORY_OPT``, which ``rules/common.mk`` sets
    to ``$(MMT_BASE)/plugins`` when the library is built (``/opt/mmt/plugins``
    in the published package, also when it is extracted elsewhere). That
    string is in the library's read-only data; it is the one absolute path
    there ending in ``/plugins``. Several different ones, or none, is
    ``None``.
    """
    try:
        with open(core, "rb") as f:
            data = f.read()
    except OSError:
        return None
    found = {m.group(0).decode("ascii") for m in _PLUGINS_LITERAL.finditer(data)}
    return found.pop() if len(found) == 1 else None


def scanned_plugin_dir(sdk: Sdk | None, env: Mapping[str, str]) -> tuple[str | None, str]:
    """The directory mmt-dpi programs scan for plugins, and where that comes
    from: ``MMT_DPI_PLUGINS_DIR`` (as given: mmt-dpi refuses a relative one)
    or ``libmmt_core`` (``compiled_plugin_dir``); ``(None, "unknown")`` when
    neither tells."""
    given = env.get(PLUGINS_DIR_ENV, "")
    if given:
        return given, PLUGINS_DIR_ENV
    core = core_library(sdk) if sdk is not None else None
    compiled = compiled_plugin_dir(core) if core is not None else None
    if compiled is not None:
        return compiled, "libmmt_core"
    return None, "unknown"


def core_library(sdk: Sdk) -> str | None:
    """The SDK's ``libmmt_core`` shared object: the newest
    ``dpi/lib/libmmt_core.so.<version>`` regular file (the package's own
    links are absolute ``/opt/mmt`` paths, so they may dangle in an extracted
    prefix), else ``dpi/lib/libmmt_core.so`` when it resolves; ``None``
    without one."""
    lib = Path(sdk.prefix, "dpi", "lib")
    try:
        entries = list(lib.iterdir())
    except OSError:
        return None
    found = [
        p for p in entries if _CORE_VERSIONED.match(p.name) and p.is_file() and not p.is_symlink()
    ]
    if found:

        def key(p: Path) -> tuple[int, ...]:
            return tuple(int(n) for n in p.name.split(".so.", 1)[1].split("."))

        return str(max(found, key=key))
    plain = lib / "libmmt_core.so"
    return str(plain) if plain.is_file() else None


def _plugins(directory: str, exclude: str | None) -> list[str]:
    try:
        names = os.listdir(directory)
    except OSError as exc:
        raise RegistryError(
            f"cannot list the plugin directory {directory}: {exc.strerror or exc}"
        ) from None
    names = [n for n in names if n.endswith(".so") and n != exclude]
    return sorted(names, key=lambda n: n.encode("utf-8", "surrogateescape"))


def read_registry(
    sdk: Sdk,
    *,
    env: Mapping[str, str],
    max_id: int,
    exclude: str | None = None,
    timeout: float = 60.0,
) -> Registry:
    """The protocols the SDK registers with the installed plugins (see the
    module docstring); ids from 0 to ``max_id - 1`` (``PROTO_MAX_IDENTIFIER``).

    ``env`` is the environment the child process inherits (``os.environ``).
    Raises ``RegistryError``.
    """
    directory = plugin_dir(sdk, env)
    core = core_library(sdk)
    if core is None:
        raise RegistryError(f"no libmmt_core shared object in {sdk.prefix}/dpi/lib")
    plugins = _plugins(directory, exclude)
    with tempfile.TemporaryDirectory(prefix="mmt-plugin-registry-") as tmp:
        for name in plugins:
            os.symlink(os.path.realpath(os.path.join(directory, name)), os.path.join(tmp, name))
        child_env = dict(env)
        child_env[PLUGINS_DIR_ENV] = tmp
        try:
            proc = subprocess.run(
                [sys.executable, "-I", str(_PROBE), core, str(max_id)],
                cwd=tmp,
                env=child_env,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired:
            raise RegistryError(
                f"loading the plugins of {directory} took more than {timeout:g} s"
            ) from None
        except OSError as exc:
            raise RegistryError(f"cannot run {sys.executable}: {exc.strerror or exc}") from None
    report = _report(proc.stdout)
    if report is None:
        code = proc.returncode
        why = f"signal {-code}" if code < 0 else f"exit code {code}"
        raise RegistryError(f"loading the plugins of {directory} failed ({why})")
    if isinstance(report, str):
        raise RegistryError(f"{report} with the plugins of {directory}")
    return Registry(directory, tuple(plugins), report)


def _report(stdout: bytes) -> tuple[RegisteredProtocol, ...] | str | None:
    """The probe's protocols, its error message, or ``None`` for output that
    is not a probe report."""
    try:
        doc = json.loads(stdout.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return None
    if not isinstance(doc, dict):
        return None
    if doc.get("ok") is not True:
        error = doc.get("error")
        return error if isinstance(error, str) and error else None
    raw = doc.get("protocols")
    if not isinstance(raw, list):
        return None
    protocols = []
    for item in raw:
        if not (
            isinstance(item, list)
            and len(item) == 2
            and isinstance(item[0], int)
            and isinstance(item[1], str)
        ):
            return None
        protocols.append(RegisteredProtocol(item[0], item[1]))
    return tuple(protocols)
