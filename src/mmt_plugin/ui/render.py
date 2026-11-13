"""Plain renderers: tab-separated records and compiler-style diagnostics.

Plain output never carries a raw control character: user text is escaped
(``\\t``, ``\\n``, ``\\\\``, and ``\\xNN`` for every other C0/C1 control
character and DEL), so a record always keeps its field count and no ESC byte
reaches the terminal from user data.
"""

from __future__ import annotations

from collections.abc import Iterable

from mmt_plugin.diagnostics import CliError, Diagnostic, Severity

__all__ = ["escape", "format_diagnostic", "format_error", "record"]


def _escape_char(ch: str) -> str:
    if ch == "\\":
        return "\\\\"
    if ch == "\t":
        return "\\t"
    if ch == "\n":
        return "\\n"
    code = ord(ch)
    if code < 0x20 or 0x7F <= code <= 0x9F:
        return f"\\x{code:02x}"
    return ch


def escape(text: str) -> str:
    """Escape backslashes and control characters in ``text``."""
    if text.isprintable() and "\\" not in text:
        return text
    return "".join(_escape_char(ch) for ch in text)


def record(fields: Iterable[str]) -> str:
    """One plain record: escaped fields joined by tabs, ending in a newline."""
    return "\t".join(escape(f) for f in fields) + "\n"


def _line(prefix: str, severity: str, message: str, code: str | None) -> str:
    suffix = f" [{code}]" if code else ""
    return f"{escape(prefix)}: {severity}: {escape(message)}{suffix}\n"


def format_diagnostic(diagnostic: Diagnostic, *, prog: str) -> str:
    """A diagnostic in compiler style, for stderr::

        plugin.yaml:14:9: error: attribute name "LEN" is already used [model.duplicate-name]
          plugin.yaml:9:9: note: first defined here
          hint: rename one of the two attributes

    A diagnostic with no location starts with ``prog`` instead of a file.
    """
    loc = diagnostic.location
    out = [
        _line(
            prog if loc is None else str(loc),
            diagnostic.severity.value,
            diagnostic.message,
            diagnostic.code,
        )
    ]
    for related in diagnostic.related:
        where = prog if related.location is None else str(related.location)
        out.append("  " + _line(where, Severity.NOTE.value, related.message, None))
    if diagnostic.hint:
        out.append(f"  hint: {escape(diagnostic.hint)}\n")
    return "".join(out)


def format_error(error: CliError, *, prog: str) -> str:
    """The error that ended the run, in the same style as a diagnostic."""
    out = _line(prog, Severity.ERROR.value, error.message, error.code)
    if error.hint:
        out += f"  hint: {escape(error.hint)}\n"
    return out
