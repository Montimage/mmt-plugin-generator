"""Tests for the per-stream decisions (``docs/design/cli.md``, section 10)."""

from __future__ import annotations

import fcntl
import io
import os
import pty
import struct
import termios

import pytest

from mmt_plugin.ui.streams import ColorTier, StreamStyle, decide


class FakeStream(io.TextIOWrapper):
    def __init__(self, *, tty: bool, encoding: str = "utf-8") -> None:
        super().__init__(io.BytesIO(), encoding=encoding)
        self._tty = tty

    def isatty(self) -> bool:
        return self._tty


TTY = FakeStream(tty=True)
PIPE = FakeStream(tty=False)
TERM = {"TERM": "xterm"}


@pytest.mark.parametrize(
    ("stream", "env", "options", "expected"),
    [
        (PIPE, TERM, {}, (False, ColorTier.NONE)),
        (PIPE, {**TERM, "FORCE_COLOR": ""}, {}, (False, ColorTier.NONE)),
        (PIPE, {**TERM, "FORCE_COLOR": "0"}, {}, (False, ColorTier.NONE)),
        (PIPE, {**TERM, "FORCE_COLOR": "1"}, {}, (True, ColorTier.ANSI16)),
        (TTY, TERM, {}, (True, ColorTier.ANSI16)),
        (TTY, {"TERM": "dumb", "FORCE_COLOR": "1"}, {}, (False, ColorTier.NONE)),
        (TTY, {**TERM, "FORCE_COLOR": "1"}, {"json": True}, (False, ColorTier.NONE)),
        (TTY, {**TERM, "NO_COLOR": "1"}, {}, (True, ColorTier.NONE)),
        (TTY, {**TERM, "NO_COLOR": ""}, {}, (True, ColorTier.ANSI16)),
        (PIPE, {**TERM, "FORCE_COLOR": "1", "NO_COLOR": "1"}, {}, (True, ColorTier.NONE)),
        (TTY, TERM, {"no_color": True}, (True, ColorTier.NONE)),
        (TTY, {"TERM": "xterm-256color"}, {}, (True, ColorTier.ANSI256)),
        (
            TTY,
            {"TERM": "xterm-256color", "COLORTERM": "truecolor"},
            {},
            (True, ColorTier.TRUECOLOR),
        ),
        (TTY, {**TERM, "COLORTERM": "24bit"}, {}, (True, ColorTier.TRUECOLOR)),
    ],
)
def test_decision_table(
    stream: FakeStream,
    env: dict[str, str],
    options: dict[str, bool],
    expected: tuple[bool, ColorTier],
) -> None:
    style = decide(stream, env=env, **options)
    assert (style.styled, style.color) == expected
    assert style.escapes == (expected[0] and expected[1] is not ColorTier.NONE)


@pytest.mark.parametrize(
    ("encoding", "unicode"),
    [("utf-8", True), ("UTF8", True), ("ascii", False), ("latin-1", False)],
)
def test_glyphs_follow_the_stream_encoding(encoding: str, unicode: bool) -> None:
    assert decide(FakeStream(tty=True, encoding=encoding), env=TERM).unicode is unicode


def test_a_stream_without_isatty_is_plain() -> None:
    class Bare(io.StringIO):
        def isatty(self) -> bool:
            raise ValueError("closed")

    # StringIO has no encoding: ASCII glyphs.
    assert decide(Bare(), env=TERM) == StreamStyle(False, ColorTier.NONE, False)


@pytest.mark.parametrize(
    ("columns", "width"), [("120", 120), ("1", 1), ("0", 80), ("-5", 80), ("wide", 80), ("", 80)]
)
def test_width_comes_from_columns_else_80(columns: str, width: int) -> None:
    assert decide(PIPE, env={**TERM, "COLUMNS": columns}).width == width
    assert decide(PIPE, env=TERM).width == 80


def test_a_terminal_reports_its_own_width_and_is_a_tty() -> None:
    leader, follower = pty.openpty()
    try:
        fcntl.ioctl(follower, termios.TIOCSWINSZ, struct.pack("HHHH", 24, 101, 0, 0))
        with open(follower, "w", encoding="utf-8", closefd=False) as stream:
            style = decide(stream, env=TERM)
            assert (style.tty, style.width) == (True, 101)
            assert decide(stream, env={**TERM, "COLUMNS": "50"}).width == 50
        assert decide(PIPE, env=TERM).tty is False
    finally:
        os.close(leader)
        os.close(follower)
