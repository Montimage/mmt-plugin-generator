"""Per-stream output decisions (``docs/design/cli.md``, section 10, "Fallbacks").

Made once per stream, right after parsing, from the options, the environment
and the stream itself; commands only read the result.
"""

from __future__ import annotations

import codecs
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import TextIO

__all__ = ["ColorTier", "StreamStyle", "decide"]


class ColorTier(str, Enum):
    """How many colors a stream may use. ``NONE`` means no SGR at all, not even bold."""

    NONE = "none"
    ANSI16 = "16"
    ANSI256 = "256"
    TRUECOLOR = "24bit"


@dataclass(frozen=True)
class StreamStyle:
    """The decision for one stream.

    ``styled`` False is plain mode: records only, no frames and no escape
    codes, so ``color`` is then always ``NONE``. ``unicode`` picks the glyph
    set (Unicode or ASCII).
    """

    styled: bool
    color: ColorTier
    unicode: bool

    @property
    def escapes(self) -> bool:
        """Whether the stream may carry any ESC byte."""
        return self.styled and self.color is not ColorTier.NONE


def _isatty(stream: TextIO) -> bool:
    try:
        return stream.isatty()
    except (AttributeError, ValueError, OSError):
        return False


def _is_utf8(stream: TextIO) -> bool:
    encoding = getattr(stream, "encoding", None)
    if not encoding:
        return False
    try:
        return codecs.lookup(encoding).name == "utf-8"
    except LookupError:
        return False


def _forced(env: Mapping[str, str]) -> bool:
    return env.get("FORCE_COLOR", "") not in ("", "0")


def decide(
    stream: TextIO, *, env: Mapping[str, str], no_color: bool = False, json: bool = False
) -> StreamStyle:
    """Decide how to write to ``stream``.

    - Plain when ``json`` is set (it wins over ``FORCE_COLOR``), when
      ``TERM=dumb``, or when the stream is not a TTY and ``FORCE_COLOR`` is
      unset, empty or ``0``.
    - Color: none with ``no_color`` or a non-empty ``NO_COLOR``; 24-bit with
      ``COLORTERM=truecolor|24bit``; 256 when ``TERM`` contains ``256color``;
      16 otherwise.
    - Unicode glyphs when the stream's encoding is UTF-8, ASCII otherwise.
    """
    unicode = _is_utf8(stream)
    term = env.get("TERM", "")
    if json or term == "dumb" or not (_isatty(stream) or _forced(env)):
        return StreamStyle(styled=False, color=ColorTier.NONE, unicode=unicode)
    if no_color or env.get("NO_COLOR", ""):
        color = ColorTier.NONE
    elif env.get("COLORTERM", "").lower() in ("truecolor", "24bit"):
        color = ColorTier.TRUECOLOR
    elif "256color" in term:
        color = ColorTier.ANSI256
    else:
        color = ColorTier.ANSI16
    return StreamStyle(styled=True, color=color, unicode=unicode)
