"""The PDL v1 lexer.

Tokens follow the legacy lexer (``legacy/pdl_grammar/PluginGrammar.g``,
G:791-878) with these differences, each a decision of T1.2 (#11):

- Words are not reserved. Every word is an ``IDENT`` token, and the parser
  reads keywords from context, so a field may be called ``id`` or ``len``.
  The word shape is the grammar's ``STNAME`` (G:872): a letter, then
  letters, digits and ``_``.
- A number never carries a sign. The grammar's ``NBSTR`` swallows a leading
  ``-`` (G:871), so ``val(x)-4`` lexed as ``val(x)`` and ``-4`` and failed;
  here ``-`` is always its own token and the parser reads negative literals.
- A number must not run into a word: ``12abc`` and ``0x`` are errors (the
  Java lexer split the first and crashed on the second).
- Comments: ``// ...`` to the end of the line and ``/* ... */``, which does
  not nest. The grammar has none (inventory section 1).
- Newlines are whitespace (the parser checks that a quoted value ends on
  its line). ``\\r\\n`` is a newline; a lone ``\\r`` is an error, as in the
  grammar (G:876).
- A leading byte order mark is skipped and does not count as a column.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from mmt_plugin.diagnostics import Diagnostic, Severity
from mmt_plugin.pdl.model import Span

__all__ = ["PUNCTUATION", "Kind", "LexError", "Token", "tokenize"]


#: The most digits a number may have. It keeps every value far below
#: CPython's limit on integer-string conversions (4300 digits).
MAX_DIGITS = 100


class Kind(str, Enum):
    """A token kind."""

    IDENT = "identifier"
    NUMBER = "number"
    HEX = "hex number"
    PUNCT = "punctuation"
    EOF = "end of input"


#: Punctuation tokens, longest first (G:33-788 literals).
PUNCTUATION: tuple[str, ...] = (
    "==",
    "!=",
    ">=",
    "<=",
    "{",
    "}",
    "(",
    ")",
    "=",
    '"',
    ",",
    ";",
    ":",
    "*",
    "/",
    "+",
    "-",
    ">",
    "<",
)


@dataclass(frozen=True)
class Token:
    """One token; ``text`` is exactly what the source says."""

    kind: Kind
    text: str
    span: Span

    def is_punct(self, text: str) -> bool:
        """Whether this is the punctuation token ``text``."""
        return self.kind is Kind.PUNCT and self.text == text

    def is_word(self, text: str) -> bool:
        """Whether this is the word ``text`` (keywords are case-sensitive)."""
        return self.kind is Kind.IDENT and self.text == text

    def describe(self) -> str:
        """How a message names this token."""
        if self.kind is Kind.EOF:
            return "the end of the input"
        return f"`{self.text}`"


class LexError(Exception):
    """A text that is not a sequence of PDL tokens."""

    def __init__(self, diagnostic: Diagnostic) -> None:
        super().__init__(diagnostic.message)
        self.diagnostic = diagnostic


def _is_letter(ch: str) -> bool:
    return ("a" <= ch <= "z") or ("A" <= ch <= "Z")


def _is_digit(ch: str) -> bool:
    return "0" <= ch <= "9"


def _is_word_char(ch: str) -> bool:
    return _is_letter(ch) or _is_digit(ch) or ch == "_"


def _is_hex_digit(ch: str) -> bool:
    return _is_digit(ch) or ("a" <= ch <= "f") or ("A" <= ch <= "F")


class _Lexer:
    def __init__(self, text: str, filename: str) -> None:
        self.text = text
        self.file = filename
        self.pos = 0
        self.line = 1
        self.line_start = 0
        if text.startswith("﻿"):
            self.pos = self.line_start = 1
        self.tokens: list[Token] = []

    def span(self, line: int, col: int) -> Span:
        """From ``line``:``col`` to the current position."""
        return Span(self.file, line, col, self.line, self.column())

    def column(self) -> int:
        return self.pos - self.line_start + 1

    def point(self, length: int = 1) -> Span:
        col = self.column()
        return Span(self.file, self.line, col, self.line, col + length)

    def newline(self) -> None:
        self.line += 1
        self.line_start = self.pos

    def run(self) -> list[Token]:
        text = self.text
        n = len(text)
        while self.pos < n:
            ch = text[self.pos]
            if ch in " \t":
                self.pos += 1
            elif ch == "\n":
                self.pos += 1
                self.newline()
            elif ch == "\r":
                if self.pos + 1 < n and text[self.pos + 1] == "\n":
                    self.pos += 2
                    self.newline()
                else:
                    self.bad_char("a carriage return that is not followed by a newline")
            elif text.startswith("//", self.pos):
                end = text.find("\n", self.pos)
                end = n if end < 0 else end
                if end > self.pos and text[end - 1] == "\r":
                    end -= 1
                self.pos = end
            elif text.startswith("/*", self.pos):
                self.block_comment()
            elif _is_letter(ch):
                self.word()
            elif _is_digit(ch):
                self.number()
            else:
                self.punct()
        self.tokens.append(Token(Kind.EOF, "", self.point(0)))
        return self.tokens

    def block_comment(self) -> None:
        start = self.point(2)
        end = self.text.find("*/", self.pos + 2)
        if end < 0:
            raise LexError(
                Diagnostic(
                    Severity.ERROR,
                    "model.syntax.unterminated-comment",
                    "this comment is not closed",
                    hint="close the comment with `*/`; block comments do not nest",
                    location=start.location(),
                )
            )
        stop = end + 2
        while True:
            nl = self.text.find("\n", self.pos, stop)
            if nl < 0:
                break
            self.pos = nl + 1
            self.newline()
        self.pos = stop

    def word(self) -> None:
        start, col = self.pos, self.column()
        while self.pos < len(self.text) and _is_word_char(self.text[self.pos]):
            self.pos += 1
        self.add(Kind.IDENT, start, col)

    def number(self) -> None:
        text = self.text
        start, col = self.pos, self.column()
        kind = Kind.NUMBER
        if text.startswith("0x", self.pos):
            kind = Kind.HEX
            self.pos += 2
            while self.pos < len(text) and _is_hex_digit(text[self.pos]):
                self.pos += 1
            digits = self.pos - start - 2
        else:
            while self.pos < len(text) and _is_digit(text[self.pos]):
                self.pos += 1
            digits = self.pos - start
        tail = self.pos
        while tail < len(text) and _is_word_char(text[tail]):
            tail += 1
        if digits > MAX_DIGITS:
            raise LexError(
                Diagnostic(
                    Severity.ERROR,
                    "model.syntax.invalid-number",
                    f"a number with {digits} digits is too long",
                    hint=f"PDL numbers have at most {MAX_DIGITS} digits; "
                    "no protocol field needs more",
                    location=self.span(self.line, col).location(),
                )
            )
        if digits == 0 or tail > self.pos:
            spelled = text[start:tail]
            self.pos = tail
            raise LexError(
                Diagnostic(
                    Severity.ERROR,
                    "model.syntax.invalid-number",
                    f"`{spelled}` is not a number",
                    hint="write a decimal number (`12`) or a hex number with at least "
                    "one digit (`0x0C`), followed by a space or an operator",
                    location=self.span(self.line, col).location(),
                )
            )
        self.add(kind, start, col)

    def punct(self) -> None:
        for p in PUNCTUATION:
            if self.text.startswith(p, self.pos):
                start, col = self.pos, self.column()
                self.pos += len(p)
                self.add(Kind.PUNCT, start, col)
                return
        ch = self.text[self.pos]
        self.bad_char(f"`{ch}` (U+{ord(ch):04X})" if ch.isprintable() else f"U+{ord(ch):04X}")

    def bad_char(self, what: str) -> None:
        raise LexError(
            Diagnostic(
                Severity.ERROR,
                "model.syntax.unexpected-character",
                f"unexpected character {what}",
                hint="PDL text is ASCII words, numbers and the punctuation "
                '`{ } ( ) = " , ; : * / + - == != > < >= <=`; '
                "other text can only appear in a comment",
                location=self.point().location(),
            )
        )

    def add(self, kind: Kind, start: int, col: int) -> Token:
        token = Token(kind, self.text[start : self.pos], self.span(self.line, col))
        self.tokens.append(token)
        return token


def tokenize(text: str, filename: str) -> list[Token]:
    """Split ``text`` into tokens, ending with one ``EOF`` token.

    Raises ``LexError`` with a ``model.syntax.*`` diagnostic at the first
    text that is not a token.
    """
    return _Lexer(text, filename).run()
