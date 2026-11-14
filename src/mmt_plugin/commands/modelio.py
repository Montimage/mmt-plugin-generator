"""Reading a command's ``MODEL`` argument (``docs/design/cli.md``, section 4).

Shared by every command that reads a model: ``MODEL`` is a file, ``-`` for
stdin (named ``<stdin>`` in diagnostics), or by default
``<project>/plugin.yaml``. The format is detected from the suffix
(``.yaml``/``.yml`` is plugin.yaml, anything else PDL v1) unless
``--model-format`` says otherwise; ``parse_model`` reads either into the
same typed model (``mmt_plugin.pdl.model``).
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from mmt_plugin.diagnostics import CliError
from mmt_plugin.pdl import STDIN, Model, parse
from mmt_plugin.pluginyaml import load, profile_pin

__all__ = [
    "FORMATS",
    "PROJECT_FILE",
    "ModelInput",
    "absolute",
    "decode_model",
    "inside",
    "parse_model",
    "read_model",
    "show_path",
]

#: The project's model file.
PROJECT_FILE = "plugin.yaml"
#: The ``--model-format`` choices.
FORMATS = ("auto", "yaml", "pdl")
_YAML_SUFFIXES = (".yaml", ".yml")


def absolute(path: Path | str) -> Path:
    """``path`` made absolute against the current directory, without
    following symbolic links."""
    return Path(os.path.normpath(os.path.join(os.getcwd(), path)))


def inside(path: Path, directory: Path) -> bool:
    """Whether ``path`` is ``directory`` or below it (both absolute)."""
    return path == directory or directory in path.parents


def show_path(path: Path, project: Path) -> str:
    """Relative to the project when inside it (POSIX), absolute otherwise."""
    if inside(path, project):
        return Path(os.path.relpath(path, project)).as_posix()
    return path.as_posix()


@dataclass(frozen=True)
class ModelInput:
    """A model as read: its name for diagnostics, its format (``pdl`` or
    ``yaml``) and its bytes."""

    name: str
    format: str
    data: bytes

    @property
    def profile_pin(self) -> str | None:
        """plugin.yaml's ``sdk.profile``, for the profile choice (section 9);
        ``None`` for PDL v1, or when the model cannot be read (parsing it
        reports why)."""
        if self.format != "yaml":
            return None
        try:
            return profile_pin(self.data.decode("utf-8"))
        except UnicodeDecodeError:
            return None


def read_model(given: str | None, model_format: str, project: Path) -> ModelInput:
    """Read ``MODEL`` (``given``; ``None`` is ``<project>/plugin.yaml``).

    ``project`` is absolute. Raises ``CliError`` ``model.unreadable`` for a
    file that cannot be read.
    """
    if given == "-":
        fmt = "pdl" if model_format == "auto" else model_format
        name = STDIN
        path = None
    else:
        path = project / PROJECT_FILE if given is None else absolute(given)
        name = show_path(path, project)
        fmt = model_format
        if fmt == "auto":
            fmt = "yaml" if path.suffix.lower() in _YAML_SUFFIXES else "pdl"
    try:
        data = sys.stdin.buffer.read() if path is None else path.read_bytes()
    except IsADirectoryError:
        raise CliError(
            "model.unreadable", f"{name} is a directory, not a model file", "pass a file"
        ) from None
    except OSError as exc:
        raise CliError(
            "model.unreadable",
            f"cannot read {name}: {exc.strerror or exc}",
            "check the MODEL path and its permissions",
        ) from None
    return ModelInput(name, fmt, data)


def decode_model(model: ModelInput) -> str:
    """The model's text; ``CliError`` ``model.unreadable`` when it is not UTF-8."""
    try:
        return model.data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CliError(
            "model.unreadable",
            f"{model.name} is not UTF-8 text (byte {exc.start})",
            "save the model as UTF-8",
        ) from None


def parse_model(model: ModelInput) -> Model:
    """The typed model of ``model``, of either format. Raises ``CliError``
    ``model.unreadable`` when it is not UTF-8, and ``PdlSyntaxError`` (for
    plugin.yaml, its subclass ``PluginYamlError``) when it does not parse."""
    text = decode_model(model)
    if model.format == "yaml":
        return load(text, filename=model.name).model
    return parse(text, filename=model.name)
