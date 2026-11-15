"""Markdown helpers for the documentation tests: the tracked pages, their
fenced code blocks, and the markers that say how to run a block."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

#: An opening fence: three or more backticks or tildes, at any indentation
#: (a fence in a list item is indented by the item's width).
_FENCE = re.compile(r"^([ \t]*)(`{3,}|~{3,})([^`\n]*)$")


def tracked_markdown() -> list[Path]:
    """Every Markdown file git tracks, sorted."""
    out = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "-z", "--", "*.md"],
        capture_output=True,
        check=True,
    ).stdout
    return sorted(ROOT / name for name in out.decode("utf-8").split("\0") if name)


@dataclass(frozen=True)
class Block:
    """A fenced code block: its info string, its text, the line of its
    opening fence (1-based) and its character span in the page."""

    info: str
    text: str
    line: int
    start: int
    end: int


def blocks(text: str) -> list[Block]:
    """The fenced code blocks of ``text``, in order. A block that is not
    closed runs to the end of the page, as in CommonMark."""
    found: list[Block] = []
    lines = text.splitlines(keepends=True)
    pos = 0
    i = 0
    while i < len(lines):
        match = _FENCE.match(lines[i].rstrip("\r\n"))
        if match is None:
            pos += len(lines[i])
            i += 1
            continue
        indent, fence, info = len(match.group(1)), match.group(2), match.group(3).strip()
        start, first = pos, i
        pos += len(lines[i])
        i += 1
        body: list[str] = []
        while i < len(lines):
            close = lines[i].rstrip("\r\n").strip()
            pos += len(lines[i])
            i += 1
            if close and set(close) == {fence[0]} and len(close) >= len(fence):
                break
            line = lines[i - 1].replace("\r\n", "\n")
            # The fence's indentation is not part of the block's text.
            strip = len(line) - len(line.lstrip(" \t"))
            body.append(line[min(indent, strip) :] if line.strip() else "\n")
        found.append(Block(info, "".join(body), first + 1, start, pos))
    return found


def fenced_spans(text: str) -> list[tuple[int, int]]:
    """The character spans of the fenced code blocks of ``text``."""
    return [(b.start, b.end) for b in blocks(text)]
