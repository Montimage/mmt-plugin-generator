"""Tests for the btop style module (``docs/design/cli.md``, section 10).

``test_style_1_*`` to ``test_style_8_*`` are the eight tests of the
cli-builder skill's ``references/btop-style.md``, section 7, in its order;
their subprocess environments follow its rules (``conftest.clean_env``: no
``FORCE_COLOR``, ``NO_COLOR``, ``CLICOLOR_FORCE``, ``COLORTERM``, ``COLUMNS``,
``LC_ALL``, ``LC_CTYPE``; ``TERM=xterm-256color``, ``LANG=C.UTF-8``; plus the
variables each test names). The "box command" is ``dummy --box``.
"""

from __future__ import annotations

import io
import json
import os
import pty
import select
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

from mmt_plugin.diagnostics import CliError, Diagnostic, Location, Related, Severity
from mmt_plugin.ui import render, style
from mmt_plugin.ui.streams import ColorTier, StreamStyle
from mmt_plugin.ui.style import Level, Role, Section

RunCli = Callable[..., subprocess.CompletedProcess[bytes]]
CleanEnv = Callable[..., dict[str, str]]

ESC = "\x1b"
DUMMY_SCRIPT = Path(__file__).with_name("dummy_command.py")


def mode(
    color: ColorTier = ColorTier.NONE, *, unicode: bool = True, width: int = 60
) -> StreamStyle:
    return StreamStyle(styled=True, color=color, unicode=unicode, width=width)


PLAIN = StreamStyle(styled=False, color=ColorTier.NONE, unicode=True)
TIERS = list(ColorTier)


def sample(st: StreamStyle) -> str:
    """Every renderer at once, as a command's view would use them."""
    rows = style.table(
        ["check", "status", "n"],
        [
            ["schema", style.status("pass", Level.OK, style=st), "7"],
            ["id range", style.status("warn", Level.WARN, style=st), "900"],
            ["load order", style.status("fail", Level.FAIL, style=st), "12"],
            ["sdk", style.status("skip", Level.SKIP, style=st), "-"],
        ],
        style=st,
        width=st.width - 4,
        align=["left", "left", "right"],
    )
    body: list[str | Section] = [
        *rows,
        style.meter(72, style=st, width=20),
        style.sparkline([10, 40, 90, 20, 70], style=st, ceiling=100),
        Section([style.paint("accent", Role.ACCENT, style=st)], Role.BORDER_MEM),
    ]
    return style.box("validate tpkt", body, style=st, footer="4 checks")


# --- the eight cli-builder style tests ---------------------------------------


def test_style_1_box_command_with_captured_stdout_has_no_esc_and_no_frame(
    run_cli: RunCli,
) -> None:
    proc = run_cli(["dummy", "--box"])
    assert proc.returncode == 0, proc.stderr
    assert b"\x1b" not in proc.stdout
    assert "╭".encode() not in proc.stdout
    assert proc.stdout == b"value\thello\n"


def test_style_2_json_with_force_color_parses_and_has_no_esc(
    run_cli: RunCli, clean_env: CleanEnv
) -> None:
    proc = run_cli(["dummy", "--box", "--json"], env=clean_env(FORCE_COLOR="1"))
    assert proc.returncode == 0, proc.stderr
    assert b"\x1b" not in proc.stdout
    assert json.loads(proc.stdout)["result"]["value"] == "hello"


def test_style_3_force_color_and_no_color_have_no_esc(
    run_cli: RunCli, clean_env: CleanEnv
) -> None:
    proc = run_cli(["dummy", "--box"], env=clean_env(FORCE_COLOR="1", NO_COLOR="1"))
    assert proc.returncode == 0, proc.stderr
    assert b"\x1b" not in proc.stdout
    assert "╭─┐dummy hello┌".encode() in proc.stdout  # styled, tier none


def test_style_4_force_color_box_has_esc_and_frame(run_cli: RunCli, clean_env: CleanEnv) -> None:
    proc = run_cli(["dummy", "--box"], env=clean_env(FORCE_COLOR="1"))
    assert proc.returncode == 0, proc.stderr
    assert b"\x1b" in proc.stdout
    assert "╭─┐".encode() in proc.stdout


def test_style_5_explicit_mode_16_colors_unicode() -> None:
    out = sample(mode(ColorTier.ANSI16))
    assert "\x1b[" in out
    assert "╭─┐" in out


@pytest.mark.parametrize("tier", TIERS)
def test_style_6_ascii_glyph_set_is_all_below_0x80(tier: ColorTier) -> None:
    st = mode(tier, unicode=False)
    out = sample(st)
    out += style.format_error(CliError("internal.io", "x", "y"), prog="p", style=st)
    out += style.progress_line("packets", style=st, elapsed=3.1, done=52, total=100)
    out += style.fit("a very long title that will not fit", 10, st)
    assert all(ord(ch) < 0x80 for ch in out), [ch for ch in out if ord(ch) >= 0x80]
    assert "+-[validate tpkt]" in style.strip_sgr(out)


def test_style_7_meter_50_width_10_tier_none() -> None:
    assert style.meter(50, style=mode(), width=10) == "■" * 5 + "·" * 5 + " 50%"


def test_style_8_esc_and_tab_in_a_record_are_escaped() -> None:
    value = "evil\x1b[31mred\tcol"
    plain = render.record(["name", value, "end"])
    assert ESC not in plain
    assert plain.rstrip("\n").split("\t") == ["name", "evil\\x1b[31mred\\tcol", "end"]
    st = mode(ColorTier.NONE)
    styled = style.box(
        value, style.table(None, [["name", value, "end"]], style=st, width=56), style=st
    )
    assert ESC not in styled
    assert "\t" not in styled
    assert "evil\\x1b[31mred\\tcol" in styled


# --- color tiers and the theme ---------------------------------------------


def test_round_half_up_is_not_bankers_rounding() -> None:
    assert [style.round_half_up(x) for x in (0.5, 1.5, 2.5, 2.4999)] == [1, 2, 3, 2]


@pytest.mark.parametrize(
    ("rgb", "index"),
    [
        ((0x55, 0x6D, 0x59), 16 + 36 * 2 + 6 * 2 + 2),  # cpu_box: not grey
        ((0x80, 0x80, 0x80), 232 + 12),  # grey: 232 + round(128/11)
        ((0, 0, 0), 232),
        ((0xDC, 0x4C, 0x4C), 16 + 36 * 4 + 6 * 1 + 1),
    ],
)
def test_to_256_follows_btop(rgb: tuple[int, int, int], index: int) -> None:
    assert style.to_256(rgb) == index


@pytest.mark.parametrize(
    ("tier", "code"),
    [
        (ColorTier.NONE, ""),
        (ColorTier.ANSI16, "\x1b[1;91m"),
        (ColorTier.ANSI256, f"\x1b[1;38;5;{style.to_256((0xB5, 0x40, 0x40))}m"),
        (ColorTier.TRUECOLOR, "\x1b[1;38;2;181;64;64m"),
    ],
)
def test_accent_is_bold_in_every_color_tier(tier: ColorTier, code: str) -> None:
    assert style.sgr(Role.ACCENT, tier) == code


def test_roles_without_color_use_attributes_only() -> None:
    assert style.sgr(Role.TEXT, ColorTier.TRUECOLOR) == ""
    assert style.sgr(Role.TITLE, ColorTier.ANSI16) == "\x1b[1m"
    assert style.sgr(Role.DIM, ColorTier.ANSI256) == "\x1b[2m"
    assert style.sgr(Role.BORDER, ColorTier.ANSI16) == "\x1b[32m"
    for role in (Role.BORDER_MEM, Role.BORDER_NET, Role.BORDER_PROC):
        assert style.sgr(role, ColorTier.ANSI16) != style.sgr(Role.BORDER, ColorTier.ANSI16)


def test_no_role_sets_a_background() -> None:
    for role in Role:
        for tier in TIERS:
            assert ";48;" not in style.sgr(role, tier) and "[48;" not in style.sgr(role, tier)


def test_gradient_runs_low_mid_high() -> None:
    assert style.gradient_rgb(0) == (0x77, 0xCA, 0x9B)
    assert style.gradient_rgb(50) == (0xCB, 0xC0, 0x6C)
    assert style.gradient_rgb(100) == (0xDC, 0x4C, 0x4C)
    assert style.gradient_rgb(25) == (0xA1, 0xC5, 0x84)  # halfway low → mid, half up


@pytest.mark.parametrize("tier", TIERS)
def test_every_renderer_honours_tier_none_and_plain(tier: ColorTier) -> None:
    for st in (mode(ColorTier.NONE), PLAIN, StreamStyle(False, tier, True)):
        assert ESC not in sample(st)
    if tier is not ColorTier.NONE:
        assert ESC in sample(mode(tier))


def test_join_escapes_text_and_keeps_styled_parts() -> None:
    st = mode(ColorTier.ANSI16)
    ok = style.status("pass", Level.OK, style=st)
    joined = style.join(ok, " (3 \x1b checks)")
    assert joined == ok + " (3 \\x1b checks)"
    out = style.box("t", [joined], style=st)
    assert "\x1b[92m●\x1b[0m pass (3 \\x1b checks)" in out
    # Plain + gives a str, which the box escapes as user text.
    assert "\\x1b[92m" in style.box("t", [ok + " (3)"], style=st)


def test_paint_escapes_user_text_but_not_styled_text() -> None:
    st = mode(ColorTier.ANSI16)
    assert style.paint("a\x1bb", Role.TEXT, st) == "a\\x1bb"
    inner = style.paint("x", Role.LOW, st)
    assert style.paint(inner, Role.TEXT, st) == inner


# --- glyphs and widths -------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "width"),
    [
        ("abc", 3),
        ("日本", 4),  # East Asian Wide
        ("\uff21\uff22", 4),  # Fullwidth A and B
        ("é", 1),  # combining acute accent
        ("a​b", 2),  # zero-width space
        ("a‍b", 2),  # zero-width joiner
        ("각", 2),  # Hangul jamo: leading consonant + medial + final
        ("😀", 2),
        ("", 0),
    ],
)
def test_cell_width(text: str, width: int) -> None:
    assert style.cell_width(text) == width


def test_visible_width_ignores_sgr() -> None:
    painted = style.paint("日本", Role.ACCENT, mode(ColorTier.TRUECOLOR))
    assert ESC in painted
    assert style.visible_width(painted) == 4


def test_glyph_sets_follow_the_stream_encoding() -> None:
    assert style.glyphs(mode()) is style.UNICODE
    assert style.glyphs(mode(unicode=False)) is style.ASCII


def test_fit_cuts_by_cells_and_keeps_codes_closed() -> None:
    st = mode(ColorTier.ANSI16)
    assert style.fit("日本語テキスト", 7, st) == "日本語…"
    assert style.fit("abcdef", 4, mode(unicode=False)) == "a..."
    cut = style.fit(style.paint("abcdefgh", Role.HIGH, st), 5, st)
    assert style.visible_width(cut) == 5
    assert cut.endswith("\x1b[0m…")
    assert style.fit("short", 10, st) == "short"


# --- components --------------------------------------------------------------


def test_box_matches_the_cli_md_mockup_shape() -> None:
    out = style.box("validate tpkt", ["a"], style=mode(width=30), footer="1 check")
    assert out.splitlines() == [
        "╭─┐validate tpkt┌" + "─" * 12 + "╮",
        "│ a" + " " * 26 + "│",
        "╰─┘1 check└" + "─" * 18 + "╯",
    ]


def test_box_ascii_form() -> None:
    out = style.box("t", ["a"], style=mode(unicode=False, width=12), footer="f")
    assert out.splitlines() == ["+-[t]------+", "| a        |", "+-[f]------+"]


def test_box_lines_are_all_the_box_width() -> None:
    st = mode(ColorTier.TRUECOLOR, width=40)
    lines = sample(st).splitlines()
    assert {style.visible_width(line) for line in lines} == {40}


def test_box_sections_are_divided_in_their_own_border_role() -> None:
    st = mode(ColorTier.ANSI16, width=20)
    out = style.box("doctor", [Section(["a"]), Section(["b"], Role.BORDER_NET)], style=st)
    lines = out.splitlines()
    assert style.strip_sgr(lines[2]) == "├" + "─" * 18 + "┤"
    assert lines[2].startswith(style.sgr(Role.BORDER_NET, ColorTier.ANSI16))
    assert lines[3].startswith(style.sgr(Role.BORDER_NET, ColorTier.ANSI16))


def test_box_shortens_a_long_title_and_line() -> None:
    lines = style.box("t" * 50, ["x" * 50], style=mode(width=20)).splitlines()
    assert lines[0] == "╭─┐" + "t" * 13 + "…┌─╮"
    assert lines[1] == "│ " + "x" * 15 + "… │"


def test_box_has_a_minimum_width() -> None:
    lines = style.box("title", [], style=mode(width=3)).splitlines()
    assert all(style.visible_width(line) == style.MIN_BOX_WIDTH for line in lines)


def test_table_aligns_and_has_a_title_header() -> None:
    st = mode(ColorTier.ANSI16)
    rows = style.table(
        ["name", "n"], [["a", "1"], ["bbb", "100"]], style=st, width=40, align=["left", "right"]
    )
    assert [style.strip_sgr(r) for r in rows] == ["name    n", "a       1", "bbb   100"]
    assert rows[0].startswith("\x1b[1m")


def test_table_narrows_the_widest_column_to_fit() -> None:
    rows = style.table(None, [["id", "a long detail text"]], style=mode(), width=12)
    assert rows == ["id  a long …"]


def test_table_cells_of_wide_characters_line_up() -> None:
    rows = style.table(None, [["日本", "x"], ["ab", "y"]], style=mode(), width=20)
    assert rows == ["日本  x", "ab    y"]


@pytest.mark.parametrize(
    ("level", "symbol", "ascii"),
    [(Level.OK, "●", "+"), (Level.WARN, "▲", "!"), (Level.FAIL, "✗", "x"), (Level.SKIP, "○", "-")],
)
def test_status_prints_symbol_and_word(level: Level, symbol: str, ascii: str) -> None:
    assert style.status("word", level, style=mode()) == f"{symbol} word"
    assert style.status("word", level, style=mode(unicode=False)) == f"{ascii} word"
    colored = style.status("word", level, style=mode(ColorTier.ANSI16))
    assert colored.endswith(" word") and colored.startswith("\x1b[")


@pytest.mark.parametrize(
    ("value", "filled"), [(0, 0), (9, 0), (10, 1), (14, 1), (15, 1), (99, 9), (100, 10), (250, 10)]
)
def test_meter_fills_cell_i_when_value_reaches_its_share(value: int, filled: int) -> None:
    out = style.meter(value, style=mode(), width=10)
    assert out[:10] == "■" * filled + "·" * (10 - filled)
    assert out[10:] == f"{min(value, 100):>3}%"


def test_meter_empty_cells_are_dim_squares_with_color() -> None:
    out = style.meter(50, style=mode(ColorTier.ANSI16), width=10)
    assert "·" not in out
    assert out.count("\x1b[2m■") == 5
    assert style.strip_sgr(out) == "■" * 10 + " 50%"
    assert style.meter(30, style=mode(unicode=False), width=10) == "###....... 30%"


def test_meter_cells_run_low_to_high_in_16_colors() -> None:
    out = style.meter(100, style=mode(ColorTier.ANSI16), width=10)
    # Cell positions 10-30 are low, 40-60 mid, 70-100 high.
    colors = [92] * 3 + [93] * 3 + [91] * 4
    assert out == "".join(f"\x1b[{c}m■\x1b[0m" for c in colors) + "100%"


def test_sparkline_pairs_samples_and_prints_the_numbers() -> None:
    out = style.sparkline([0, 100, 50, 50, 100], style=mode(), ceiling=100)
    # (0, 100) → level 0 line, position 4; (50, 50) → level 2, position 2;
    # (100, 100 repeated) → level 4, position 4.
    assert out == "⢸⣤⣿  min 0  max 100  last 100"


def test_sparkline_all_zero_and_ascii_and_empty() -> None:
    # Three samples make two cells, both level 0 (a blank braille cell).
    assert style.sparkline([0, 0, 0], style=mode()) == "  " + "  min 0  max 0  last 0"
    assert style.sparkline([1.5, 3], style=mode(unicode=False)) == "min 1.5  max 3  last 3"
    assert style.sparkline([], style=mode()) == "no samples"


def test_sparkline_cells_take_the_gradient_of_their_larger_sample() -> None:
    out = style.sparkline([0, 100], style=mode(ColorTier.ANSI16), ceiling=100)
    assert out.startswith("\x1b[91m⢸")


# --- stderr: errors, diagnostics, progress ----------------------------------


def _diag() -> Diagnostic:
    return Diagnostic(
        Severity.ERROR,
        "internal.io",
        "bad \x1b[2J thing",
        hint="fix\tit",
        location=Location("plugin.yaml", 14, 9),
        related=[Related("first defined here", Location("plugin.yaml", 9, 9))],
    )


def test_error_on_a_plain_stderr_is_the_compiler_style_line() -> None:
    error = CliError("internal.io", "msg", "a hint")
    assert style.format_error(error, prog="p", style=PLAIN) == render.format_error(error, prog="p")
    assert style.format_diagnostic(_diag(), prog="p", style=PLAIN) == render.format_diagnostic(
        _diag(), prog="p"
    )


def test_styled_error_has_the_symbol_and_a_dim_hint() -> None:
    error = CliError("internal.io", "msg", "a hint")
    assert style.format_error(error, prog="p", style=mode()) == (
        "p: ✗ error: msg [internal.io]\n  hint: a hint\n"
    )
    colored = style.format_error(error, prog="p", style=mode(ColorTier.ANSI16))
    assert "\x1b[1;91m✗ error:\x1b[0m" in colored
    assert "\x1b[2mhint: a hint\x1b[0m" in colored
    assert style.format_error(error, prog="p", style=mode(unicode=False)).startswith(
        "p: x error: msg"
    )


def test_styled_diagnostic_keeps_the_location_first_and_escapes_user_text() -> None:
    out = style.format_diagnostic(_diag(), prog="p", style=mode())
    assert out.splitlines() == [
        "plugin.yaml:14:9: ✗ error: bad \\x1b[2J thing [internal.io]",
        "  plugin.yaml:9:9: note: first defined here",
        "  hint: fix\\tit",
    ]
    warning = Diagnostic(Severity.WARNING, "internal.io", "w")
    assert (
        style.format_diagnostic(warning, prog="p", style=mode())
        == "p: ▲ warning: w [internal.io]\n"
    )
    colored = style.format_diagnostic(_diag(), prog="p", style=mode(ColorTier.TRUECOLOR))
    assert "\x1b[2J" not in colored


def test_progress_line_forms() -> None:
    st = mode()
    assert style.progress_line("packets", style=st, elapsed=1, done=52, total=100) == (
        "■■■■■····· 52/100 packets"
    )
    assert style.progress_line("files", style=st, elapsed=3.14, done=1204) == "1,204 files · 3.1s"
    assert style.progress_line("compiling mmtp_tpkt.so", style=st, elapsed=3.1) == (
        "compiling mmtp_tpkt.so · 3.1s"
    )


class _Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def test_progress_shows_only_on_a_tty_after_the_delay_and_clears() -> None:
    stream = io.StringIO()
    clock = _Clock()
    tty = StreamStyle(True, ColorTier.NONE, True, width=40, tty=True)
    with style.Progress(stream, tty, "files", clock=clock) as progress:
        progress.update(1)
        assert stream.getvalue() == ""  # under 2 s: nothing
        clock.now = 2.5
        progress.update(10)
        assert stream.getvalue() == "\r10 files · 2.5s"
        clock.now = 3.0
        progress.update(9)
    assert stream.getvalue().endswith("\r9 files · 3.0s \r" + " " * 15 + "\r")


@pytest.mark.parametrize(
    "st",
    [
        StreamStyle(True, ColorTier.ANSI16, True, tty=False),  # FORCE_COLOR on a pipe
        StreamStyle(False, ColorTier.NONE, True, tty=True),  # TERM=dumb
    ],
)
def test_progress_never_shows_off_a_styled_tty(st: StreamStyle) -> None:
    stream = io.StringIO()
    clock = _Clock()
    progress = style.Progress(stream, st, "x", clock=clock)
    clock.now = 10
    progress.update(1)
    progress.clear()
    assert not progress.active
    assert stream.getvalue() == ""


# --- the real terminal path --------------------------------------------------


def _run_on_a_pty(args: list[str], env: dict[str, str]) -> bytes:
    """Run the dummy CLI with stdout on a pseudo-terminal; return what it wrote."""
    leader, follower = pty.openpty()
    try:
        proc = subprocess.Popen(
            [sys.executable, str(DUMMY_SCRIPT), *args],
            stdin=subprocess.DEVNULL,
            stdout=follower,
            stderr=subprocess.PIPE,
            env=env,
        )
        os.close(follower)
        follower = -1
        out = b""
        while True:
            ready, _, _ = select.select([leader], [], [], 30)
            if not ready:
                break
            try:
                chunk = os.read(leader, 4096)
            except OSError:  # EIO: the child closed the terminal
                break
            if not chunk:
                break
            out += chunk
        assert proc.wait(timeout=30) == 0, proc.stderr.read() if proc.stderr else b""
        if proc.stderr:
            proc.stderr.close()
        return out
    finally:
        os.close(leader)
        if follower >= 0:
            os.close(follower)


def test_a_real_terminal_gets_the_styled_box(clean_env: CleanEnv) -> None:
    out = _run_on_a_pty(["dummy", "--box"], clean_env(COLUMNS="50"))
    assert b"\x1b[" in out
    assert "╭─┐".encode() in out


def test_a_real_terminal_with_no_color_gets_no_esc(clean_env: CleanEnv) -> None:
    out = _run_on_a_pty(["dummy", "--box"], clean_env(NO_COLOR="1", COLUMNS="50"))
    assert b"\x1b" not in out
    assert "╭─┐dummy hello┌".encode() in out
    out = _run_on_a_pty(["--no-color", "dummy", "--box"], clean_env(COLUMNS="50"))
    assert b"\x1b" not in out


def test_a_real_terminal_with_json_gets_no_esc(clean_env: CleanEnv) -> None:
    out = _run_on_a_pty(["dummy", "--box", "--json"], clean_env(COLUMNS="50"))
    assert b"\x1b" not in out
    assert json.loads(out.replace(b"\r\n", b"\n"))["ok"] is True


# --- the CLI applies the style ----------------------------------------------


def test_the_view_is_sized_to_columns(run_cli: RunCli, clean_env: CleanEnv) -> None:
    proc = run_cli(["dummy", "--box"], env=clean_env(FORCE_COLOR="1", COLUMNS="44"))
    lines = proc.stdout.decode().splitlines()
    assert len(lines) > 3
    assert {style.visible_width(line) for line in lines} == {44}


def test_quiet_prints_no_view(run_cli: RunCli, clean_env: CleanEnv) -> None:
    proc = run_cli(["-q", "dummy", "--box"], env=clean_env(FORCE_COLOR="1"))
    assert proc.returncode == 0
    assert proc.stdout == b""


def test_a_failing_view_is_an_internal_error(run_cli: RunCli, clean_env: CleanEnv) -> None:
    proc = run_cli(["dummy", "--bad-view"], env=clean_env(FORCE_COLOR="1", NO_COLOR="1"))
    assert proc.returncode == 1
    assert proc.stdout == b""
    assert proc.stderr.decode() == (
        "mmt-plugin: ✗ error: unexpected error: RuntimeError: view failed [internal.unexpected]\n"
        "  hint: this is a bug in mmt-plugin: re-run with -vv for the traceback and report it\n"
    )
    # A plain stdout never calls the view.
    assert run_cli(["dummy", "--bad-view"]).returncode == 0


@pytest.mark.parametrize(
    ("env", "expected"),
    [
        ({}, b"mmt-plugin: error: dummy failure [model.test-dummy]\n  hint: dummy hint\n"),
        (
            {"FORCE_COLOR": "1", "NO_COLOR": "1"},
            "mmt-plugin: ✗ error: dummy failure [model.test-dummy]\n  hint: dummy hint\n".encode(),
        ),
        (
            {"FORCE_COLOR": "1", "TERM": "xterm"},
            "mmt-plugin: \x1b[1;91m✗ error:\x1b[0m dummy failure\x1b[2m [model.test-dummy]"
            "\x1b[0m\n  \x1b[2mhint: dummy hint\x1b[0m\n".encode(),
        ),
    ],
)
def test_stderr_errors_follow_the_stderr_decision(
    run_cli: RunCli, clean_env: CleanEnv, env: dict[str, str], expected: bytes
) -> None:
    proc = run_cli(["dummy", "--fail", "model.test-dummy"], env=clean_env(**env))
    assert proc.returncode == 3
    assert proc.stderr == expected


def test_a_usage_error_with_no_color_has_no_esc(run_cli: RunCli, clean_env: CleanEnv) -> None:
    proc = run_cli(["--no-color", "--nope"], env=clean_env(FORCE_COLOR="1"))
    assert proc.returncode == 2
    assert b"\x1b" not in proc.stderr
    assert "✗ error:".encode() in proc.stderr


def test_styled_warnings_on_stderr(run_cli: RunCli, clean_env: CleanEnv) -> None:
    proc = run_cli(["dummy", "--warn"], env=clean_env(FORCE_COLOR="1", NO_COLOR="1"))
    assert proc.returncode == 0
    assert proc.stderr.decode().splitlines()[1] == (
        "plugin.yaml:14:9: ▲ warning: a dummy warning [model.test-dummy]"
    )
