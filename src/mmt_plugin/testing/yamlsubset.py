"""The strict YAML subset of the packet tests (``tests/corpus/README.md``,
"File format").

The same subset as ``tests/corpus/validate.py``'s loader, so that ``test``
needs no YAML library: block mappings and sequences indented with spaces;
double-quoted strings (JSON escapes), decimal integers without leading
zeros, ``true``, ``false``, ``null`` and plain words; flow sequences of
scalars; ``#`` comments. Anything else (anchors, tags, block scalars,
several documents, tabs, CRLF) is a ``LoadError``. A unit test checks that
both loaders read every corpus fixture to the same data.
"""

from __future__ import annotations

import json
import re
from typing import Any

__all__ = ["LoadError", "loads"]

_KEY = re.compile(r"^([A-Za-z_][A-Za-z0-9_.-]*):(?: (.*))?$")
_INT = re.compile(r"^-?(0|[1-9][0-9]*)$")
_PLAIN = re.compile(r"^[A-Za-z_/][A-Za-z0-9_./+-]*$")
#: Plain words that YAML 1.1 reads as booleans or null: they must be quoted.
_YAML11_SPECIAL = frozenset({"y", "n", "yes", "no", "on", "off", "true", "false", "null", "~"})

#: One significant line: its number, its indentation and its stripped text.
_Line = tuple[int, int, str]


class LoadError(ValueError):
    """The text is not in the subset; ``line`` is 1-based, ``None`` for the
    whole file."""

    def __init__(self, message: str, line: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.line = line


def _string_end(text: str, line: int) -> int:
    i = 1
    while i < len(text):
        if text[i] == "\\":
            i += 2
            continue
        if text[i] == '"':
            return i
        i += 1
    raise LoadError("unterminated string", line)


def _scalar(text: str, line: int) -> Any:
    text = text.strip()
    if not text:
        raise LoadError("empty value", line)
    if text[0] == '"':
        end = _string_end(text, line)
        rest = text[end + 1 :].strip()
        if rest and not rest.startswith("#"):
            raise LoadError("text after a quoted string", line)
        try:
            return json.loads(text[: end + 1])
        except ValueError as exc:
            raise LoadError(f"bad quoted string: {exc}", line) from None
    if text[0] == "[":
        return _flow_seq(text, line)
    text = re.sub(r"\s+#.*$", "", text)
    if _INT.match(text):
        return int(text)
    if text == "true":
        return True
    if text == "false":
        return False
    if text == "null":
        return None
    if _PLAIN.match(text) and text.lower() not in _YAML11_SPECIAL:
        return text
    raise LoadError(f"unsupported scalar {text!r} (quote it)", line)


def _flow_seq(text: str, line: int) -> list[Any]:
    end = text.rfind("]")
    if end < 0:
        raise LoadError("unterminated flow sequence", line)
    rest = text[end + 1 :].strip()
    if rest and not rest.startswith("#"):
        raise LoadError("text after a flow sequence", line)
    body = text[1:end].strip()
    if not body:
        return []
    items: list[str] = []
    cur = ""
    i = 0
    while i < len(body):
        c = body[i]
        if c == '"':
            j = _string_end(body[i:], line) + i
            cur += body[i : j + 1]
            i = j + 1
            continue
        if c in "[]{}":
            raise LoadError("nested flow collections are not allowed", line)
        if c == ",":
            items.append(cur)
            cur = ""
        else:
            cur += c
        i += 1
    items.append(cur)
    return [_scalar(item, line) for item in items]


def loads(data: bytes) -> Any:
    """The value of one document in the subset; ``LoadError`` otherwise."""
    if b"\r" in data:
        raise LoadError("CRLF line endings (use LF)")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise LoadError(f"not UTF-8 text (byte {exc.start})") from None
    lines: list[_Line] = []
    for no, line in enumerate(text.split("\n"), 1):
        if "\t" in line:
            raise LoadError("tab character", no)
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped in ("---", "...") or stripped[0] in "&*!|>%@`{":
            raise LoadError("unsupported YAML syntax", no)
        lines.append((no, len(line) - len(line.lstrip(" ")), stripped))
    if not lines:
        raise LoadError("empty file")
    value, pos = _block(lines, 0, lines[0][1])
    if pos != len(lines):
        raise LoadError("unexpected indentation", lines[pos][0])
    return value


def _block(lines: list[_Line], pos: int, indent: int) -> tuple[Any, int]:
    if lines[pos][2].startswith("- ") or lines[pos][2] == "-":
        return _seq(lines, pos, indent)
    return _map(lines, pos, indent)


def _map(
    lines: list[_Line], pos: int, indent: int, first: str | None = None
) -> tuple[dict[str, Any], int]:
    out: dict[str, Any] = {}
    while pos < len(lines):
        no, ind, text = lines[pos] if first is None else (lines[pos][0], indent, first)
        first = None
        if ind < indent:
            break
        if ind > indent:
            raise LoadError("unexpected indentation", no)
        m = _KEY.match(text)
        if not m:
            raise LoadError("expected 'key: value'", no)
        key, rest = m.group(1), m.group(2)
        if key in out:
            raise LoadError(f"duplicate key {key!r}", no)
        pos += 1
        if rest is None or not rest.strip() or rest.strip().startswith("#"):
            if pos < len(lines) and (
                lines[pos][1] > indent
                or (lines[pos][1] == indent and lines[pos][2].startswith("- "))
            ):
                out[key], pos = _block(lines, pos, lines[pos][1])
            else:
                raise LoadError(f"key {key!r} has no value", no)
        else:
            out[key] = _scalar(rest, no)
    return out, pos


def _seq(lines: list[_Line], pos: int, indent: int) -> tuple[list[Any], int]:
    out: list[Any] = []
    while pos < len(lines):
        no, ind, text = lines[pos]
        if ind < indent:
            break
        if ind > indent or not (text.startswith("- ") or text == "-"):
            if ind == indent:
                break
            raise LoadError("unexpected indentation", no)
        item = text[1:].strip()
        value: Any
        if not item:
            pos += 1
            if pos >= len(lines) or lines[pos][1] <= indent:
                raise LoadError("empty sequence item", no)
            value, pos = _block(lines, pos, lines[pos][1])
        elif _KEY.match(item) and not item.startswith('"'):
            value, pos = _map(lines, pos, indent + 2, first=item)
        else:
            value = _scalar(item, no)
            pos += 1
        out.append(value)
    return out, pos
