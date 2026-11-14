"""Reading a command's ``MODEL`` argument (``docs/design/cli.md``, section 4).

Shared by ``generate`` and ``validate``: ``MODEL`` is a file, ``-`` for
stdin (named ``<stdin>`` in diagnostics), or by default
``<project>/plugin.yaml``. The format is detected from the suffix
(``.yaml``/``.yml`` is YAML, anything else PDL v1) unless ``--model-format``
says otherwise. ``plugin.yaml`` models wait for #24 and are
``model.unsupported-format`` (exit 3).
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from mmt_plugin.diagnostics import CliError
from mmt_plugin.pdl import STDIN

__all__ = [
    "FORMATS",
    "PROJECT_FILE",
    "ModelInput",
    "absolute",
    "decode_model",
    "inside",
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
    """A model as read: its name for diagnostics, its format and its bytes."""

    name: str
    format: str
    data: bytes


def read_model(given: str | None, model_format: str, project: Path) -> ModelInput:
    """Read ``MODEL`` (``given``; ``None`` is ``<project>/plugin.yaml``).

    ``project`` is absolute. Raises ``CliError`` ``model.unsupported-format``
    for a YAML model and ``model.unreadable`` for a file that cannot be read.
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
    if fmt == "yaml":
        raise CliError(
            "model.unsupported-format",
            f"{name}: plugin.yaml models are not supported yet (#24)",
            "pass a PDL v1 model file as MODEL (or - with --model-format pdl)",
        )
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
