"""The btop style (``docs/design/cli.md``, section 10), with no dependency.

Theme roles, the four color tiers, the Unicode and ASCII glyph sets, the
width function ``cell_width``, and the renderers: ``box``, ``table``,
``status``, ``meter``, ``sparkline``, the stderr ``format_error`` and
``format_diagnostic``, and ``Progress``.

Every renderer takes the stream decision (``StreamStyle``) explicitly, so a
test renders any mode without a terminal, and none of them probes the
terminal. With color tier none, or on a plain stream, they write no escape
code at all, not even bold.

User text is escaped with ``ui.render.escape`` before it is placed, in every
mode: a plain ``str`` given to a renderer is user text. The renderers return
``Styled`` strings, whose escape codes are their own and whose user text is
already escaped, so they can be nested (a status inside a table inside a box)
without being escaped twice. Command code names roles, never escape codes.
"""

from __future__ import annotations

import math
import re
import time
import unicodedata
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from enum import Enum
from typing import TextIO

from mmt_plugin.diagnostics import CliError, Diagnostic, Severity
from mmt_plugin.ui import render
from mmt_plugin.ui.streams import ColorTier, StreamStyle

__all__ = [
    "ASCII",
    "UNICODE",
    "Glyphs",
    "Level",
    "Progress",
    "Role",
    "Section",
    "Styled",
    "box",
    "cell_width",
    "fit",
    "format_diagnostic",
    "format_error",
    "glyphs",
    "gradient_rgb",
    "meter",
    "paint",
    "progress_line",
    "round_half_up",
    "sgr",
    "sparkline",
    "status",
    "strip_sgr",
    "table",
    "to_256",
    "visible_width",
]


class Styled(str):
    """Text a renderer wrote: placed as is, never escaped again."""


#: The escape sequences this module writes (SGR only).
_SGR = re.compile(r"\x1b\[[0-9;]*m")
_SGR_SPLIT = re.compile(r"(\x1b\[[0-9;]*m)")
_RESET = "\x1b[0m"


def _safe(text: str) -> Styled:
    """``text`` ready to place: a ``Styled`` as is, user text escaped."""
    return text if isinstance(text, Styled) else Styled(render.escape(text))


# --- width ---------------------------------------------------------------


def _char_width(ch: str) -> int:
    code = ord(ch)
    if unicodedata.combining(ch) or 0x1160 <= code <= 0x11FF:
        return 0  # combining marks; Hangul medial vowels and final consonants
    if unicodedata.category(ch) in ("Mn", "Me", "Cf", "Cc"):
        return 0  # other marks, zero-width and format characters, controls
    if unicodedata.east_asian_width(ch) in ("W", "F"):
        return 2
    return 1


def cell_width(text: str) -> int:
    """The terminal cells ``text`` takes: East Asian Wide and Fullwidth count 2,
    combining marks and zero-width characters 0, everything else 1."""
    return sum(_char_width(ch) for ch in text)


def strip_sgr(text: str) -> str:
    """``text`` without its SGR escape codes."""
    return _SGR.sub("", text)


def visible_width(text: str) -> int:
    """The cells ``text`` takes on screen, its SGR codes ignored."""
    return cell_width(strip_sgr(text))


# --- theme ---------------------------------------------------------------


class Role(str, Enum):
    """The theme roles of the cli-builder btop style."""

    TEXT = "text"
    TITLE = "title"
    ACCENT = "accent"
    DIM = "dim"
    BORDER = "border"  # cpu_box, the default border
    BORDER_MEM = "mem_box"
    BORDER_NET = "net_box"
    BORDER_PROC = "proc_box"
    LOW = "low"
    MID = "mid"
    HIGH = "high"


RGB = tuple[int, int, int]


@dataclass(frozen=True)
class _Paint:
    rgb: RGB | None = None
    ansi16: int | None = None
    bold: bool = False
    faint: bool = False


_LOW: RGB = (0x77, 0xCA, 0x9B)
_MID: RGB = (0xCB, 0xC0, 0x6C)
_HIGH: RGB = (0xDC, 0x4C, 0x4C)

#: btop's default theme; text keeps the terminal's colors, and no role ever
#: sets a background.
THEME: dict[Role, _Paint] = {
    Role.TEXT: _Paint(),
    Role.TITLE: _Paint(bold=True),
    Role.ACCENT: _Paint((0xB5, 0x40, 0x40), 91, bold=True),
    Role.DIM: _Paint(faint=True),
    Role.BORDER: _Paint((0x55, 0x6D, 0x59), 32),
    Role.BORDER_MEM: _Paint((0x6C, 0x6C, 0x4B), 33),
    Role.BORDER_NET: _Paint((0x5C, 0x58, 0x8D), 35),
    Role.BORDER_PROC: _Paint((0x80, 0x52, 0x52), 31),
    Role.LOW: _Paint(_LOW, 92),
    Role.MID: _Paint(_MID, 93),
    Role.HIGH: _Paint(_HIGH, 91),
}


def round_half_up(x: float) -> int:
    """Round as btop's C++ does (Python's ``round`` rounds half to even)."""
    return math.floor(x + 0.5)


def to_256(rgb: RGB) -> int:
    """The 256-color index btop uses for a 24-bit color."""
    r, g, b = (round_half_up(c / 11) for c in rgb)
    if r == g == b:
        return 232 + r
    r, g, b = (round_half_up(c / 51) for c in rgb)
    return 16 + 36 * r + 6 * g + b


def _color(rgb: RGB, ansi16: int, tier: ColorTier) -> str:
    if tier is ColorTier.TRUECOLOR:
        return "38;2;{};{};{}".format(*rgb)
    if tier is ColorTier.ANSI256:
        return f"38;5;{to_256(rgb)}"
    return str(ansi16)


def _codes(spec: _Paint, tier: ColorTier, *, bold: bool = False) -> str:
    if tier is ColorTier.NONE:
        return ""
    params = []
    if spec.bold or bold:
        params.append("1")
    if spec.faint:
        params.append("2")
    if spec.rgb is not None and spec.ansi16 is not None:
        params.append(_color(spec.rgb, spec.ansi16, tier))
    return f"\x1b[{';'.join(params)}m" if params else ""


def sgr(role: Role, tier: ColorTier, *, bold: bool = False) -> str:
    """The escape code that starts ``role`` in ``tier`` ("" for tier none)."""
    return _codes(THEME[role], tier, bold=bold)


def _tier(style: StreamStyle) -> ColorTier:
    return style.color if style.escapes else ColorTier.NONE


def _wrap(text: str, code: str) -> Styled:
    return Styled(f"{code}{text}{_RESET}" if code and text else text)


def paint(text: str, role: Role, style: StreamStyle, *, bold: bool = False) -> Styled:
    """``text`` (escaped unless ``Styled``) in ``role``."""
    return _wrap(_safe(text), sgr(role, _tier(style), bold=bold))


def gradient_rgb(percent: float) -> RGB:
    """The low → mid → high gradient at ``percent`` (0-100, one of 101 steps)."""
    step = max(0, min(100, round_half_up(percent)))
    start, end, t = (_LOW, _MID, step / 50) if step <= 50 else (_MID, _HIGH, (step - 50) / 50)
    r, g, b = (round_half_up(a + (z - a) * t) for a, z in zip(start, end, strict=True))
    return (r, g, b)


def _gradient(percent: float, tier: ColorTier) -> str:
    if tier is ColorTier.NONE:
        return ""
    step = max(0, min(100, round_half_up(percent)))
    if tier is ColorTier.ANSI16:
        return f"\x1b[{92 if step <= 33 else 93 if step <= 66 else 91}m"
    return f"\x1b[{_color(gradient_rgb(step), 0, tier)}m"


# --- glyphs --------------------------------------------------------------


@dataclass(frozen=True)
class Glyphs:
    """One glyph set: box drawing, meters, statuses and separators."""

    top_left: str
    top_right: str
    bottom_left: str
    bottom_right: str
    horizontal: str
    vertical: str
    title_open: str  # after "╭─": "┐"
    title_close: str  # before the rest of the line: "┌"
    footer_open: str
    footer_close: str
    tee_left: str
    tee_right: str
    ellipsis: str
    full: str  # a filled meter cell
    empty: str  # an empty meter cell, drawn dim
    empty_no_color: str  # an empty cell when there is no color to tell it apart
    separator: str  # between footer items: "3 checks · 1 warning"
    ok: str
    warn: str
    fail: str
    skip: str


UNICODE = Glyphs(
    *("╭", "╮", "╰", "╯", "─", "│", "┐", "┌", "┘", "└", "├", "┤", "…"),
    *("■", "■", "·", " · ", "●", "▲", "✗", "○"),
)
ASCII = Glyphs(
    *("+", "+", "+", "+", "-", "|", "[", "]", "[", "]", "+", "+", "..."),
    *("#", ".", ".", ", ", "+", "!", "x", "-"),
)


def glyphs(style: StreamStyle) -> Glyphs:
    """The glyph set of ``style``."""
    return UNICODE if style.unicode else ASCII


# --- layout --------------------------------------------------------------


def fit(text: str, width: int, style: StreamStyle) -> Styled:
    """``text`` (escaped unless ``Styled``) cut to at most ``width`` cells; a
    cut text ends with the ellipsis glyph and keeps its escape codes closed."""
    text = _safe(text)
    width = max(0, width)
    if visible_width(text) <= width:
        return text
    ellipsis = glyphs(style).ellipsis
    if width < cell_width(ellipsis):
        ellipsis = ellipsis[:1] * width
    budget = width - cell_width(ellipsis)
    out: list[str] = []
    used = 0
    coded = False
    for part in _SGR_SPLIT.split(text):
        if _SGR.fullmatch(part):
            out.append(part)
            coded = True
            continue
        for ch in part:
            w = _char_width(ch)
            if used + w > budget:
                break
            out.append(ch)
            used += w
        else:
            continue
        break
    if coded:
        out.append(_RESET)
    return Styled("".join(out) + ellipsis)


def _pad(text: Styled, width: int, align: str = "left") -> Styled:
    gap = " " * max(0, width - visible_width(text))
    return Styled(gap + text if align == "right" else text + gap)


def _join(parts: Iterable[str]) -> Styled:
    return Styled("".join(parts))


@dataclass(frozen=True)
class Section:
    """Lines of a box drawn with their own border role; sections are divided
    by a ``├───┤`` line."""

    lines: Sequence[str]
    border: Role = Role.BORDER


#: The narrowest box drawn: corners, notches and one cell of title.
MIN_BOX_WIDTH = 8


def box(
    title: str,
    body: Sequence[str | Section],
    *,
    style: StreamStyle,
    footer: str | None = None,
    border: Role = Role.BORDER,
    width: int | None = None,
) -> Styled:
    """A rounded box with ``title`` in the top border and ``footer`` in the
    bottom one, ``style.width`` (or ``width``) cells wide.

    ``body`` holds lines (escaped unless ``Styled``; a line that does not fit
    ends with an ellipsis) and ``Section``s; lines between sections form a
    section of their own, in the ``border`` role.
    """
    g = glyphs(style)
    total = max(MIN_BOX_WIDTH, style.width if width is None else width)
    inner = total - 4

    def line(text: str, role: Role) -> Styled:
        return paint(Styled(text), role, style)

    def edge(left: str, open_: str, label: str | None, close: str, right: str, role: Role) -> str:
        if not label:
            return line(left + g.horizontal * (total - 2) + right, border)
        shown = fit(label, total - 6, style)
        rest = total - 5 - visible_width(shown)
        return _join(
            (
                line(left + g.horizontal + open_, border),
                paint(shown, role, style),
                line(close + g.horizontal * rest + right, border),
            )
        )

    sections: list[Section] = []
    loose: list[str] = []
    for item in body:
        if isinstance(item, Section):
            if loose:
                sections.append(Section(loose, border))
                loose = []
            sections.append(item)
        else:
            loose.append(item)
    if loose or not sections:
        sections.append(Section(loose, border))

    out = [edge(g.top_left, g.title_open, title, g.title_close, g.top_right, Role.TITLE)]
    for index, section in enumerate(sections):
        if index:
            rule = g.tee_left + g.horizontal * (total - 2) + g.tee_right
            out.append(line(rule, section.border))
        bar = paint(Styled(g.vertical), section.border, style)
        for text in section.lines:
            out.append(_join((bar, " ", _pad(fit(text, inner, style), inner), " ", bar)))
    out.append(
        edge(g.bottom_left, g.footer_open, footer, g.footer_close, g.bottom_right, Role.TEXT)
    )
    return Styled("\n".join(out) + "\n")


def table(
    header: Sequence[str] | None,
    rows: Sequence[Sequence[str]],
    *,
    style: StreamStyle,
    width: int,
    align: Sequence[str] = (),
    gap: int = 2,
) -> list[Styled]:
    """Rows of cells in columns, at most ``width`` cells wide.

    The header (if any) is in the ``title`` role, with no rule under it.
    ``align`` gives ``"left"`` or ``"right"`` per column (numbers right);
    missing entries are left. Cells are escaped unless ``Styled``. When the
    columns do not fit, the widest is narrowed first and its cells end with
    an ellipsis.
    """
    lines = [list(header)] if header is not None else []
    lines += [list(row) for row in rows]
    if not lines:
        return []
    count = max(len(line) for line in lines)
    cells = [[_safe(c) for c in line] + [Styled("")] * (count - len(line)) for line in lines]
    widths = [max(visible_width(line[i]) for line in cells) for i in range(count)]
    excess = sum(widths) + gap * (count - 1) - max(1, width)
    while excess > 0 and max(widths) > 1:
        widest = widths.index(max(widths))
        widths[widest] -= 1
        excess -= 1
    aligns = [*align, *["left"] * count][:count]
    out: list[Styled] = []
    for n, line in enumerate(cells):
        parts: list[str] = []
        for i, cell in enumerate(line):
            shown = fit(cell, widths[i], style)
            last = i == count - 1
            if not (last and aligns[i] == "left"):
                shown = _pad(shown, widths[i], aligns[i])
            if n == 0 and header is not None:
                shown = paint(shown, Role.TITLE, style)
            parts.append(shown if last else shown + " " * gap)
        out.append(_join(parts))
    return out


class Level(str, Enum):
    """A status level: the symbol and its color."""

    OK = "ok"
    WARN = "warn"
    FAIL = "fail"
    SKIP = "skip"


_LEVEL_ROLE = {
    Level.OK: Role.LOW,
    Level.WARN: Role.MID,
    Level.FAIL: Role.HIGH,
    Level.SKIP: Role.DIM,
}


def _symbol(level: Level, g: Glyphs) -> str:
    return {Level.OK: g.ok, Level.WARN: g.warn, Level.FAIL: g.fail, Level.SKIP: g.skip}[level]


def status(word: str, level: Level, *, style: StreamStyle) -> Styled:
    """``● pass``: the level's symbol in its color, then ``word`` as text, so
    color never carries the meaning alone."""
    symbol = paint(Styled(_symbol(level, glyphs(style))), _LEVEL_ROLE[level], style)
    return _join((symbol, " ", _safe(word)))


def _cells(value: float, width: int, style: StreamStyle) -> Styled:
    g = glyphs(style)
    tier = _tier(style)
    empty = g.empty if tier is not ColorTier.NONE else g.empty_no_color
    out: list[str] = []
    for i in range(1, width + 1):
        position = round_half_up(i * 100 / width)
        if value >= position:
            out.append(_wrap(g.full, _gradient(position, tier)))
        else:
            out.append(_wrap(empty, sgr(Role.DIM, tier)))
    return _join(out)


def meter(value: float, *, style: StreamStyle, width: int = 10) -> Styled:
    """``width`` cells, then the value right-aligned: ``■■■■■····· 50%``.

    Cell ``i`` (1-based) is filled when ``value >= round(i * 100 / width)``, in
    the gradient color of its position; empty cells are dim ``■``, or ``·``
    when there is no color.
    """
    value = max(0.0, min(100.0, float(value)))
    return _join((_cells(value, max(1, width), style), f"{round_half_up(value):>3}%"))


BRAILLE_UP = (" ⢀⢠⢰⢸", "⡀⣀⣠⣰⣸", "⡄⣄⣤⣴⣼", "⡆⣆⣦⣶⣾", "⡇⣇⣧⣷⣿")


def _number(x: float) -> str:
    return str(int(x)) if float(x).is_integer() else f"{x:g}"


def sparkline(
    samples: Sequence[float], *, style: StreamStyle, ceiling: float | None = None
) -> Styled:
    """Braille cells of two samples each, then ``min N  max N  last N``.

    Levels are ``round(sample / ceiling * 4)``, clamped to 0-4; ``ceiling`` is
    the known maximum (100 for percentages), else the series maximum. Each
    cell has the gradient color of its larger sample. With ASCII glyphs only
    the numbers print: the numbers carry the data in every mode.
    """
    if not samples:
        return Styled("no samples")
    numbers = (
        f"min {_number(min(samples))}  max {_number(max(samples))}  last {_number(samples[-1])}"
    )
    if not style.unicode:
        return Styled(numbers)
    top = max(samples) if ceiling is None else ceiling
    tier = _tier(style)
    series = list(samples) + ([samples[-1]] if len(samples) % 2 else [])

    def level(x: float) -> int:
        return 0 if top <= 0 else max(0, min(4, round_half_up(x / top * 4)))

    cells = []
    for first, second in zip(series[::2], series[1::2], strict=True):
        share = 0.0 if top <= 0 else min(100.0, max(first, second) / top * 100)
        cells.append(_wrap(BRAILLE_UP[level(first)][level(second)], _gradient(share, tier)))
    return _join((*cells, "  ", numbers))


# --- stderr --------------------------------------------------------------


def _label(severity: Severity, style: StreamStyle) -> Styled:
    g = glyphs(style)
    if severity is Severity.ERROR:
        return paint(Styled(f"{g.fail} error:"), Role.HIGH, style, bold=True)
    if severity is Severity.WARNING:
        return paint(Styled(f"{g.warn} warning:"), Role.MID, style)
    return paint(Styled("note:"), Role.DIM, style)


def _line(where: str, severity: Severity, message: str, code: str | None, s: StreamStyle) -> str:
    suffix = paint(Styled(f" [{code}]"), Role.DIM, s) if code else ""
    return f"{_safe(where)}: {_label(severity, s)} {_safe(message)}{suffix}\n"


def _hint(hint: str | None, style: StreamStyle) -> str:
    return f"  {paint(Styled('hint: ' + render.escape(hint)), Role.DIM, style)}\n" if hint else ""


def format_diagnostic(diagnostic: Diagnostic, *, prog: str, style: StreamStyle) -> str:
    """A diagnostic for stderr: compiler style, the location first.

    On a plain stream this is exactly ``ui.render.format_diagnostic``; styled,
    the severity becomes ``✗ error:`` (high, bold), ``▲ warning:`` (mid) or a
    dim ``note:``, and the code and the hint are dim.
    """
    if not style.styled:
        return render.format_diagnostic(diagnostic, prog=prog)
    loc = diagnostic.location
    out = [
        _line(
            prog if loc is None else str(loc),
            diagnostic.severity,
            diagnostic.message,
            diagnostic.code,
            style,
        )
    ]
    for related in diagnostic.related:
        where = prog if related.location is None else str(related.location)
        out.append("  " + _line(where, Severity.NOTE, related.message, None, style))
    out.append(_hint(diagnostic.hint, style))
    return "".join(out)


def format_error(error: CliError, *, prog: str, style: StreamStyle) -> str:
    """The error that ended the run, styled like ``format_diagnostic``."""
    if not style.styled:
        return render.format_error(error, prog=prog)
    return _line(prog, Severity.ERROR, error.message, error.code, style) + _hint(error.hint, style)


def progress_line(
    label: str,
    *,
    style: StreamStyle,
    elapsed: float,
    done: int | None = None,
    total: int | None = None,
) -> Styled:
    """One progress line: ``■■■■■····· 52/100 packets`` when the total is
    known, else ``1,204 files · 3.1s`` or ``compiling mmtp_tpkt.so · 3.1s``."""
    g = glyphs(style)
    name = _safe(label)
    if total:
        count = 0 if done is None else done
        bar = _cells(count * 100 / total, 10, style)
        return _join((bar, f" {count:,}/{total:,} ", name))
    seconds = f"{g.separator}{elapsed:.1f}s"
    if done is not None:
        return _join((f"{done:,} ", name, seconds))
    return _join((name, seconds))


class Progress:
    """A progress line on stderr, redrawn in place with ``\\r``.

    It shows only on a terminal (``style.tty`` and ``style.styled``), and
    only once ``delay`` seconds have passed, so short operations print
    nothing. ``clear`` (or leaving the ``with`` block) erases it before the
    result prints. It never moves the cursor up.
    """

    def __init__(
        self,
        stream: TextIO,
        style: StreamStyle,
        label: str,
        *,
        total: int | None = None,
        enabled: bool = True,
        delay: float = 2.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._stream = stream
        self._style = style
        self._label = label
        self._total = total
        self._active = enabled and style.tty and style.styled
        self._delay = delay
        self._clock = clock
        self._start = clock()
        self._shown = 0

    @property
    def active(self) -> bool:
        """Whether this progress can show at all."""
        return self._active

    def update(self, done: int | None = None) -> None:
        """Redraw the line with ``done`` items, once the delay has passed."""
        if not self._active:
            return
        elapsed = self._clock() - self._start
        if elapsed < self._delay:
            return
        text = progress_line(
            self._label, style=self._style, elapsed=elapsed, done=done, total=self._total
        )
        text = fit(text, max(1, self._style.width - 1), self._style)
        width = visible_width(text)
        self._stream.write("\r" + text + " " * max(0, self._shown - width))
        self._stream.flush()
        self._shown = max(width, self._shown)

    def clear(self) -> None:
        """Erase the line, if it was drawn."""
        if self._shown:
            self._stream.write("\r" + " " * self._shown + "\r")
            self._stream.flush()
            self._shown = 0

    def __enter__(self) -> Progress:
        return self

    def __exit__(self, *exc: object) -> None:
        self.clear()
