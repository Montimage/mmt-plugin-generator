"""The other plugins a model names: plugin.yaml's ``plugins`` (#145).

A plugin whose parent is another plugin (its
``<label>_hook_register_parents`` attaches it to that plugin's protocol)
loads only after that plugin. ``plugins`` lists them, a parent first, each a
path relative to the directory of the model file:

- a project directory, which holds a ``plugin.yaml``: its plugin is
  ``<dir>/build/mmtp_<label>.so``, which ``mmt-plugin test`` builds when it
  is stale; the plugins that project names load before it;
- a built plugin, a file whose name ends in ``.so``.

``resolve`` follows them, depth first, and returns every plugin to load
before the model's own, in load order. A plugin two projects need is
loaded once, at its first place. It refuses, with ``model.bad-plugin`` at
the entry (exit 3), a path that does not exist or is neither a project nor a
``.so`` file, a project whose ``plugin.yaml`` cannot be read, a path one
list names twice, a project that names one of the projects that name it (a
cycle, the model's own directory included), and a plugin with the model's
label or another named project's (mmt-dpi registers a protocol name once).

``validate`` (#146) and ``through`` selectors (#147) read the same list.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from mmt_plugin.diagnostics import CliError, Diagnostic, Severity
from mmt_plugin.pdl import Model, PdlSyntaxError
from mmt_plugin.pdl.model import PluginRef

__all__ = ["DIAGNOSTIC_CODES", "PROJECT_FILE", "NamedPlugin", "PluginError", "resolve"]

#: The codes of resolving ``plugins``.
DIAGNOSTIC_CODES = ("model.bad-plugin",)

#: A project's model file.
PROJECT_FILE = "plugin.yaml"
#: A project's build directory, where its plugin is.
BUILD_DIR = "build"
#: The suffix of a plugin file (mmt-dpi loads only ``*.so``).
SUFFIX = ".so"

HINT = (
    "each entry of plugins: is a path relative to the directory of plugin.yaml, to a"
    " project directory (with its plugin.yaml) or to a built .so file, parents first"
    " (docs/plugin-yaml.md, Plugins)"
)


class PluginError(Exception):
    """A ``plugins`` entry that cannot be used: ``diagnostic`` says why,
    at the entry."""

    def __init__(self, diagnostic: Diagnostic) -> None:
        super().__init__(diagnostic.message)
        self.diagnostic = diagnostic


@dataclass(frozen=True)
class NamedPlugin:
    """A plugin to load before the model's own: ``plugin``, the ``.so``
    file (absolute), and for a project its directory, its model file, its
    label and its protocol id (``None`` for a ``.so`` file named directly)."""

    plugin: Path
    project: Path | None = None
    model: Path | None = None
    label: str | None = None
    proto_id: int | None = None


def _error(ref: PluginRef, message: str, hint: str = HINT) -> PluginError:
    return PluginError(
        Diagnostic(Severity.ERROR, "model.bad-plugin", message, hint, ref.span.location())
    )


def resolve(
    model: Model,
    model_dir: Path,
    show: Callable[[Path], str],
    read: Callable[[Path], Model],
) -> list[NamedPlugin]:
    """The plugins ``model`` (read from a file in ``model_dir``, absolute)
    names, and the ones those projects name, in load order. ``show`` gives
    a path as diagnostics write it; ``read(path)`` reads a project's
    ``plugin.yaml``, raising ``PdlSyntaxError`` or
    ``mmt_plugin.diagnostics.CliError``."""
    own = model.properties.label.text.lower()
    resolver = _Resolver(show, read, own)
    resolver.walk(model.plugins, model_dir, [os.path.realpath(model_dir)])
    return resolver.out


class _Resolver:
    def __init__(
        self, show: Callable[[Path], str], read: Callable[[Path], Model], own: str
    ) -> None:
        self.show = show
        self.read = read
        self.own = own
        self.out: list[NamedPlugin] = []
        self.files: set[str] = set()
        #: Each named project's label, with its directory.
        self.labels: dict[str, str] = {}

    def walk(self, refs: Sequence[PluginRef], base: Path, stack: list[str]) -> None:
        named: set[str] = set()
        for ref in refs:
            if os.path.isabs(ref.path):
                raise _error(ref, f"plugins: {ref.path} is an absolute path")
            target = Path(os.path.normpath(base / ref.path))
            real = os.path.realpath(target)
            if real in named:
                raise _error(ref, f"plugins: {ref.path} is named twice", "name each plugin once")
            named.add(real)
            if target.is_dir():
                self.project(ref, target, real, stack)
            elif target.is_file() and target.name.endswith(SUFFIX):
                if target.name == f"mmtp_{self.own}{SUFFIX}":
                    raise _error(
                        ref,
                        f"plugins: {ref.path} is the plugin's own file name, mmtp_{self.own}.so",
                        "name the other plugins only, never the plugin itself",
                    )
                self.add(NamedPlugin(target), real)
            elif target.exists():
                raise _error(
                    ref,
                    f"plugins: {ref.path} is neither a project directory nor a .so file",
                )
            else:
                raise _error(ref, f"plugins: {ref.path} not found ({self.show(target)})")

    def project(self, ref: PluginRef, target: Path, real: str, stack: list[str]) -> None:
        if real in stack:
            raise _error(
                ref,
                f"plugins: {ref.path} is a project that loads this one: a cycle",
                "a plugin names its parents, never a plugin that needs it",
            )
        model_file = target / PROJECT_FILE
        if not model_file.is_file():
            raise _error(
                ref,
                f"plugins: {ref.path} is a directory without a {PROJECT_FILE}, not a project",
            )
        name = self.show(model_file)
        try:
            model = self.read(model_file)
        except PdlSyntaxError as exc:
            first = exc.diagnostics[0] if exc.diagnostics else None
            why = first.message if first is not None else str(exc)
            raise _error(
                ref,
                f"plugins: cannot read {name}: {why}",
                f"run mmt-plugin -C {self.show(target)} validate --no-sdk",
            ) from None
        except CliError as exc:  # unreadable, or not UTF-8
            raise _error(ref, f"plugins: cannot read {name}: {exc.message}") from None
        label = model.properties.label.text.lower()
        if label == self.own:
            raise _error(
                ref,
                f"plugins: {ref.path} is a project with this plugin's label, {label}",
                "name the other plugins only; mmt-dpi registers a protocol name once",
            )
        seen = self.labels.get(label)
        if seen is not None and seen != real:
            raise _error(
                ref,
                f"plugins: {ref.path} has the label {label} of another named project",
                "mmt-dpi registers a protocol name once: name one of them",
            )
        self.labels[label] = real
        self.walk(model.plugins, target, [*stack, real])
        plugin = target / BUILD_DIR / f"mmtp_{label}{SUFFIX}"
        named = NamedPlugin(plugin, target, model_file, label, model.properties.id.value)
        self.add(named, os.path.realpath(plugin))

    def add(self, plugin: NamedPlugin, real: str) -> None:
        if real in self.files:
            return
        self.files.add(real)
        self.out.append(plugin)
