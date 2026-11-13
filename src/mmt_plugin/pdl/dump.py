"""A readable, stable JSON form of the typed model, for golden tests and debugging.

Each node becomes an object whose first key, ``node``, is its class name,
followed by its fields in declaration order. A span becomes the string
``"line:column-end_line:end_column"``; the file name is given once, at the
top. Enums become their PDL spelling and tuples become lists.
"""

from __future__ import annotations

import dataclasses
import json
from enum import Enum
from typing import Any

from mmt_plugin.pdl.model import Model, Span

__all__ = ["dumps", "to_data"]


def to_data(value: object) -> Any:
    """The JSON-ready form of a model node, or of any value inside one."""
    if isinstance(value, Span):
        return f"{value.line}:{value.column}-{value.end_line}:{value.end_column}"
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, tuple):
        return [to_data(item) for item in value]
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        data: dict[str, Any] = {"node": type(value).__name__}
        for f in dataclasses.fields(value):
            data[f.name] = to_data(getattr(value, f.name))
        return data
    if value is None or isinstance(value, (bool, int, str)):
        return value
    raise TypeError(f"not a model value: {value!r}")


def dumps(model: Model) -> str:
    """The model as indented JSON, ending in a newline."""
    document = {"file": model.span.file, "model": to_data(model)}
    return json.dumps(document, indent=2, ensure_ascii=False) + "\n"
