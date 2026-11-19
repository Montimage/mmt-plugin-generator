"""The YAML subset of ``plugin.yaml``, read into nodes with positions.

``mmt-plugin`` has no YAML dependency (``docs/design/workflow-redesign.md``,
decision 1), and every schema error must point at the line and column of the
node it is about, so this module reads the subset of YAML that a model needs,
and keeps where each node is:

- block mappings and block sequences, indented with spaces;
- flow sequences (``[a, b]``) and flow mappings (``{a: 1, b: 2}``) of
  scalars, on one line, with a space (or ``,``, ``}``) after each key's
  ``:``;
- plain, single-quoted and double-quoted scalars, and ``#`` comments;
- an optional ``---`` before the document and ``...`` after it.

Scalars are resolved as in YAML 1.2's core schema, made unambiguous: a
decimal integer (no leading zero) or ``0x`` hex one is an integer, ``true``/``false`` a boolean,
``null``/``~`` (or an empty value) null, anything else a string. A plain
word that YAML 1.1 reads otherwise (``yes``, ``off``, ``0o17``, ...) is an
error asking for quotes, so that every YAML library reads a valid file the
same way. Anchors, aliases, tags, block scalars, several documents and tabs in
the indentation are errors (``YamlError``).
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from dataclasses import dataclass
from typing import TypeAlias

__all__ = ["Mapping", "Node", "Scalar", "ScalarValue", "Sequence", "YamlError", "parse", "to_data"]

ScalarValue: TypeAlias = str | int | float | bool | None

_INT = re.compile(r"-?[0-9]+")
_HEX = re.compile(r"0x[0-9A-Fa-f]+")
_FLOAT = re.compile(
    r"[-+]?(\.[0-9]+|[0-9]+\.[0-9]*)([eE][-+]?[0-9]+)?|[-+]?[0-9]+[eE][-+]?[0-9]+"
    r"|[-+]?\.(inf|Inf|INF)|\.(nan|NaN|NAN)"
)
_TRUE = frozenset({"true", "True", "TRUE"})
_FALSE = frozenset({"false", "False", "FALSE"})
_NULL = frozenset({"null", "Null", "NULL", "~"})
#: Plain words that YAML 1.1 reads as booleans, and numbers it reads in
#: other bases: quoting them is the only reading every library agrees on.
_AMBIGUOUS = frozenset(
    {"y", "Y", "yes", "Yes", "YES", "n", "N", "no", "No", "NO"}
    | {"on", "On", "ON", "off", "Off", "OFF"}
)
_OTHER_BASE = re.compile(
    r"[-+]?0[oObB][0-9A-Fa-f_]+|[-+]?[0-9][0-9_]*(:[0-5]?[0-9])+|\+[0-9]+|-?0[0-9]+"
    r"|[-+]0x[0-9A-Fa-f]+"
)
_KEY = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]*")
#: Characters that cannot start a plain scalar (YAML indicators).
_INDICATORS = "&*!|>%@`"


class YamlError(ValueError):
    """The text is not in the subset, at ``line``:``column`` (1-based)."""

    def __init__(self, message: str, line: int, column: int) -> None:
        super().__init__(f"{line}:{column}: {message}")
        self.message = message
        self.line = line
        self.column = column


@dataclass(frozen=True)
class Scalar:
    """A scalar: its resolved ``value``, and its ``text`` (the plain text as
    written, or the decoded string of a quoted scalar). ``quoted`` tells a
    quoted ``"12"`` (a string) from a plain ``12`` (an integer). The position
    is the scalar's first character (its quote, if any) and just past its
    last."""

    value: ScalarValue
    text: str
    quoted: bool
    line: int
    column: int
    end_line: int
    end_column: int

    @property
    def value_column(self) -> int:
        """The column of the first character of the value inside its quotes."""
        return self.column + 1 if self.quoted else self.column


@dataclass(frozen=True)
class Mapping:
    """A mapping: its ``(key, value)`` pairs in document order."""

    items: tuple[tuple[Scalar, Node], ...]
    line: int
    column: int
    end_line: int
    end_column: int

    def get(self, key: str) -> Node | None:
        """The value of ``key``, or ``None``."""
        for k, v in self.items:
            if k.text == key:
                return v
        return None

    def key(self, key: str) -> Scalar | None:
        """The key node ``key``, or ``None``."""
        for k, _ in self.items:
            if k.text == key:
                return k
        return None


@dataclass(frozen=True)
class Sequence:
    """A sequence: its items in order."""

    items: tuple[Node, ...]
    line: int
    column: int
    end_line: int
    end_column: int


Node: TypeAlias = Scalar | Mapping | Sequence


def to_data(node: Node) -> object:
    """The plain Python value of ``node`` (dicts, lists and scalars), for a
    JSON Schema validator."""
    if isinstance(node, Scalar):
        return node.value
    if isinstance(node, Sequence):
        return [to_data(item) for item in node.items]
    return {k.text: to_data(v) for k, v in node.items}


# --- lines -------------------------------------------------------------------


@dataclass(frozen=True)
class _Line:
    """A significant line: its number, the column of its first non-space
    character, and its text from there to the end (the comment included)."""

    number: int
    column: int
    text: str


def _lines(text: str) -> list[_Line]:
    if text.startswith("﻿"):
        text = text[1:]
    out: list[_Line] = []
    started = ended = False
    for number, raw in enumerate(text.split("\n"), 1):
        raw = raw.removesuffix("\r")
        if "\r" in raw:
            raise YamlError("a carriage return inside a line", number, raw.index("\r") + 1)
        stripped = raw.lstrip(" ")
        column = len(raw) - len(stripped) + 1
        if stripped.startswith("\t"):
            raise YamlError("a tab in the indentation (indent with spaces)", number, column)
        body = stripped.rstrip(" \t")
        if not body or body.startswith("#"):
            continue
        if ended:
            raise YamlError("text after the end of the document (`...`)", number, column)
        if column == 1 and (body == "---" or body.startswith("--- ")):
            if started or out:
                raise YamlError("a second document (`---`): plugin.yaml holds one", number, column)
            started = True
            rest = body[3:].strip()
            if rest and not rest.startswith("#"):
                raise YamlError(
                    "text after `---` (start the document on the next line)", number, column + 4
                )
            continue
        if column == 1 and (body == "..." or body.startswith("... ")):
            ended = True
            continue
        if body.startswith("%"):
            raise YamlError("YAML directives (`%`) are not supported", number, column)
        out.append(_Line(number, column, body))
    return out


# --- scalars -----------------------------------------------------------------


def _resolve(text: str, line: int, column: int) -> ScalarValue:
    """The value of a plain scalar."""
    if text in _AMBIGUOUS or _OTHER_BASE.fullmatch(text):
        raise YamlError(
            f"`{text}` is read differently by YAML 1.1 and YAML 1.2: quote it"
            f' ("{text}") for a string, or write a number in decimal (without leading'
            " zeros) or 0x hex",
            line,
            column,
        )
    if _INT.fullmatch(text):
        return int(text, 10)
    if _HEX.fullmatch(text):
        return int(text, 16)
    if text in _TRUE:
        return True
    if text in _FALSE:
        return False
    if text in _NULL:
        return None
    if _FLOAT.fullmatch(text):
        return float(text.lower().replace(".inf", "inf").replace(".nan", "nan"))
    return text


def _comment_or_end(text: str, i: int, line: int, column: int, what: str) -> None:
    """Only spaces and a comment may follow ``what`` at ``text[i:]``."""
    rest = text[i:]
    stripped = rest.lstrip(" \t")
    if stripped and not (stripped.startswith("#") and len(stripped) < len(rest)):
        raise YamlError(
            f"unexpected text after {what}", line, column + i + len(rest) - len(stripped)
        )


def _double_quoted(text: str, i: int, line: int, column: int) -> tuple[str, int]:
    """The string of the double-quoted scalar at ``text[i]``, and the index
    just past its closing quote."""
    j = i + 1
    while j < len(text):
        if text[j] == "\\":
            j += 2
            continue
        if text[j] == '"':
            try:
                value = json.loads(text[i : j + 1])
            except ValueError:
                raise YamlError(
                    "a bad escape in a double-quoted string (use JSON escapes)",
                    line,
                    column + i,
                ) from None
            return str(value), j + 1
        j += 1
    raise YamlError("a double-quoted string does not end on its line", line, column + i)


def _single_quoted(text: str, i: int, line: int, column: int) -> tuple[str, int]:
    j = i + 1
    out = []
    while j < len(text):
        if text[j] == "'":
            if j + 1 < len(text) and text[j + 1] == "'":
                out.append("'")
                j += 2
                continue
            return "".join(out), j + 1
        out.append(text[j])
        j += 1
    raise YamlError("a single-quoted string does not end on its line", line, column + i)


def _plain_end(text: str, i: int, flow: bool) -> int:
    """The end of the plain scalar at ``text[i]``: a comment, the line's end
    or, in a flow collection, a ``,``, ``]`` or ``}``."""
    j = i
    while j < len(text):
        c = text[j]
        if c == "#" and j > i and text[j - 1] in " \t":
            break
        if flow and c in ",]}":
            break
        if flow and c == ":" and (j + 1 == len(text) or text[j + 1] in " \t,]}"):
            break
        j += 1
    while j > i and text[j - 1] in " \t":
        j -= 1
    return j


def _scalar_at(text: str, i: int, line: int, column: int, flow: bool) -> tuple[Scalar, int]:
    """The scalar at ``text[i]`` (``column`` is the column of ``text[0]``),
    and the index just past it."""
    c = text[i]
    start = column + i
    if c == '"':
        value, j = _double_quoted(text, i, line, column)
        return Scalar(value, value, True, line, start, line, column + j), j
    if c == "'":
        value, j = _single_quoted(text, i, line, column)
        return Scalar(value, value, True, line, start, line, column + j), j
    if c in _INDICATORS:
        what = {
            "&": "anchors (`&`)",
            "*": "aliases (`*`)",
            "!": "tags (`!`)",
            "|": "block scalars (`|`)",
            ">": "block scalars (`>`)",
        }.get(c, f"`{c}` at the start of a value")
        raise YamlError(f"{what} are not supported (quote the value)", line, start)
    if c in "[{":
        raise YamlError("a flow collection inside a flow collection", line, start)
    if c in "-?:" and (i + 1 == len(text) or text[i + 1] in " \t"):
        raise YamlError(f"`{c} ` cannot start a value here (quote it)", line, start)
    j = _plain_end(text, i, flow)
    if j == i:
        raise YamlError("an empty value", line, start)
    raw = text[i:j]
    if not flow and (": " in raw or ":\t" in raw or raw.endswith(":")):
        at = raw.index(":", raw.find(": ") if ": " in raw else 0)
        raise YamlError(
            "`:` followed by a space inside a plain value (quote the value)", line, start + at
        )
    return Scalar(_resolve(raw, line, start), raw, False, line, start, line, column + j), j


def _flow(text: str, line: int, column: int) -> Node:
    """A flow sequence or mapping of scalars that fills ``text``."""
    opening = text[0]
    closing = "]" if opening == "[" else "}"
    items: list[Node] = []
    pairs: list[tuple[Scalar, Node]] = []
    i = 1

    def skip(i: int) -> int:
        while i < len(text) and text[i] in " \t":
            i += 1
        return i

    i = skip(i)
    if i < len(text) and text[i] == closing:
        i += 1
    else:
        while True:
            if i >= len(text):
                raise YamlError(f"`{opening}` is not closed on its line", line, column)
            if opening == "{":
                m = _KEY.match(text, i)
                if m is None:
                    raise YamlError("a key must be a word", line, column + i)
                key = Scalar(m.group(), m.group(), False, line, column + i, line, column + m.end())
                i = skip(m.end())
                if i >= len(text) or text[i] != ":":
                    raise YamlError("expected `:` after a key of a flow mapping", line, column + i)
                if i + 1 < len(text) and text[i + 1] not in " \t,}":
                    # YAML 1.2 reads `{a:1}` as the key `a:1` with no value.
                    raise YamlError(
                        "a space must follow `:` after a key of a flow mapping", line, column + i
                    )
                if any(k.text == key.text for k, _ in pairs):
                    raise YamlError(f"duplicate key `{key.text}`", line, key.column)
                i = skip(i + 1)
                if i >= len(text):
                    raise YamlError(f"`{opening}` is not closed on its line", line, column)
                if text[i] in ",}":
                    value = Scalar(None, "", False, line, column + i, line, column + i)
                else:
                    value, i = _scalar_at(text, i, line, column, flow=True)
                    i = skip(i)
                pairs.append((key, value))
            else:
                item, i = _scalar_at(text, i, line, column, flow=True)
                i = skip(i)
                items.append(item)
            if i >= len(text):
                raise YamlError(f"`{opening}` is not closed on its line", line, column)
            if text[i] == closing:
                i += 1
                break
            if text[i] != ",":
                raise YamlError(f"expected `,` or `{closing}`", line, column + i)
            i = skip(i + 1)
    _comment_or_end(text, i, line, column, f"`{closing}`")
    end = column + i
    if opening == "[":
        return Sequence(tuple(items), line, column, line, end)
    return Mapping(tuple(pairs), line, column, line, end)


def _inline(text: str, line: int, column: int) -> Node:
    """The value that fills ``text`` (a line's rest, starting at ``column``)."""
    if text[0] in "[{":
        return _flow(text, line, column)
    scalar, i = _scalar_at(text, 0, line, column, flow=False)
    _comment_or_end(text, i, line, column, "the value")
    return scalar


# --- blocks ------------------------------------------------------------------


def _is_item(text: str) -> bool:
    return text == "-" or text.startswith(("- ", "-\t"))


def _split_key(text: str, line: int, column: int) -> tuple[Scalar, str, int] | None:
    """``key: rest`` at ``text``: the key, the rest and the column of the
    rest; ``None`` when the text is no key."""
    if text[0] == '"' or text[0] == "'":
        value, j = (_double_quoted if text[0] == '"' else _single_quoted)(text, 0, line, column)
        if text[j : j + 1] != ":" or (j + 1 < len(text) and text[j + 1] not in " \t"):
            return None
        key = Scalar(value, value, True, line, column, line, column + j)
    else:
        m = _KEY.match(text)
        if m is None:
            return None
        j = m.end()
        if text[j : j + 1] != ":" or (j + 1 < len(text) and text[j + 1] not in " \t"):
            return None
        key = Scalar(m.group(), m.group(), False, line, column, line, column + j)
    rest = text[j + 1 :]
    stripped = rest.lstrip(" \t")
    return key, stripped, column + j + 1 + len(rest) - len(stripped)


class _Reader:
    def __init__(self, lines: list[_Line]) -> None:
        self.lines = lines
        self.pos = 0

    def peek(self) -> _Line | None:
        return self.lines[self.pos] if self.pos < len(self.lines) else None

    def block(self, column: int) -> Node:
        line = self.peek()
        assert line is not None and line.column == column
        if _is_item(line.text):
            return self.sequence(column)
        return self.mapping(column, None)

    def mapping(self, column: int, first: _Line | None) -> Mapping:
        pairs: list[tuple[Scalar, Node]] = []
        start: tuple[int, int] | None = None
        while True:
            if first is not None:
                line, first = first, None
            else:
                nxt = self.peek()
                if nxt is None or nxt.column < column:
                    break
                if nxt.column > column:
                    raise YamlError("unexpected indentation", nxt.number, nxt.column)
                if _is_item(nxt.text):
                    raise YamlError(
                        "a sequence item where a mapping key was expected", nxt.number, nxt.column
                    )
                line = nxt
                self.pos += 1
            split = _split_key(line.text, line.number, line.column)
            if split is None:
                raise YamlError(
                    "expected `key: value` (a key is a word followed by `:`)",
                    line.number,
                    line.column,
                )
            key, rest, rest_column = split
            if any(k.text == key.text for k, _ in pairs):
                raise YamlError(f"duplicate key `{key.text}`", key.line, key.column)
            if start is None:
                start = (key.line, key.column)
            value: Node
            if rest and not rest.startswith("#"):
                value = _inline(rest, line.number, rest_column)
            else:
                nxt = self.peek()
                if nxt is not None and (
                    nxt.column > column or (nxt.column == column and _is_item(nxt.text))
                ):
                    value = self.block(nxt.column)
                else:
                    value = Scalar(
                        None, "", False, key.line, key.end_column + 1, key.line, key.end_column + 1
                    )
            pairs.append((key, value))
        assert start is not None
        last = pairs[-1][1]
        return Mapping(tuple(pairs), start[0], start[1], last.end_line, last.end_column)

    def sequence(self, column: int) -> Sequence:
        items: list[Node] = []
        first = self.peek()
        assert first is not None
        while True:
            line = self.peek()
            if line is None or line.column < column:
                break
            if line.column > column:
                raise YamlError("unexpected indentation", line.number, line.column)
            if not _is_item(line.text):
                break
            self.pos += 1
            rest = line.text[1:]
            stripped = rest.lstrip(" \t")
            item_column = line.column + 1 + len(rest) - len(stripped)
            if not stripped or stripped.startswith("#"):
                nxt = self.peek()
                if nxt is not None and nxt.column > column:
                    items.append(self.block(nxt.column))
                else:
                    items.append(
                        Scalar(
                            None,
                            "",
                            False,
                            line.number,
                            line.column + 1,
                            line.number,
                            line.column + 1,
                        )
                    )
                continue
            if _is_item(stripped):
                raise YamlError(
                    "a sequence directly inside a sequence item is not supported",
                    line.number,
                    item_column,
                )
            if _split_key(stripped, line.number, item_column) is not None:
                items.append(self.mapping(item_column, _Line(line.number, item_column, stripped)))
                continue
            items.append(_inline(stripped, line.number, item_column))
        last = items[-1]
        return Sequence(tuple(items), first.number, first.column, last.end_line, last.end_column)


def parse(text: str) -> Node:
    """The node of the one document in ``text``; ``YamlError`` when the text
    is not in the subset. The document must be a mapping or a sequence."""
    lines = _lines(text)
    if not lines:
        raise YamlError("the file is empty", 1, 1)
    first = lines[0]
    reader = _Reader(lines)
    if _is_item(first.text) or _split_key(first.text, first.number, first.column) is not None:
        node = reader.block(first.column)
    else:
        raise YamlError("expected `key: value` at the top of the file", first.number, first.column)
    rest = reader.peek()
    if rest is not None:
        raise YamlError("unexpected indentation", rest.number, rest.column)
    return node


def walk(node: Node) -> Iterator[Node]:
    """``node`` and every node inside it, in document order."""
    yield node
    if isinstance(node, Mapping):
        for k, v in node.items:
            yield k
            yield from walk(v)
    elif isinstance(node, Sequence):
        for item in node.items:
            yield from walk(item)
