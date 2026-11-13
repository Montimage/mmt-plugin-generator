"""The PDL v1 parser: a hand-written recursive-descent parser.

Each method parses one rule of the legacy grammar
(``legacy/pdl_grammar/PluginGrammar.g``, cited as ``G:<line>``) and returns
the node of ``mmt_plugin.pdl.model`` for it. The grammar is LL(1) once words
are read in context, so one token of lookahead is enough everywhere and
every error names the token where the text stopped making sense.

Differences from the Java parser (T1.2, #11; the PR has the full table):

- Keywords are contextual: a word is a keyword only where the grammar
  expects that keyword, so a field or alias may be named ``id`` or ``len``.
- The input must end after the ``Protocol`` block (the grammar had no EOF
  anchor, G:27-33).
- There is no error recovery that produces a model. A syntax error is a
  diagnostic, and ``parse`` returns no model. To report as much as Java did,
  an error inside a quoted value skips to its closing quote and parsing
  goes on; the result is still only the diagnostics.
- Parsing checks syntax only. Duplicate names, ``val()``, ``case`` and
  ``nextencaps`` targets, struct references and value ranges are checked by
  the semantic passes (T1.3), not here.
"""

from __future__ import annotations

import contextlib
import dataclasses
import difflib
from collections.abc import Callable, Iterator, Sequence
from typing import NoReturn, TypeVar

from mmt_plugin.diagnostics import Diagnostic, Related, Severity, sorted_diagnostics
from mmt_plugin.pdl.lexer import Kind, LexError, Token, tokenize
from mmt_plugin.pdl.model import (
    C_TYPE_WORDS,
    MMT_TYPES,
    Attribute,
    AttributeElement,
    Attributes,
    BinaryOp,
    BinaryOperator,
    ByteSwap,
    Case,
    ClassifyNext,
    Conditional,
    CType,
    DataType,
    DataTypeValue,
    Default,
    Define,
    Element,
    ElementType,
    Encoding,
    EncodingValue,
    Expr,
    Flag,
    IntLiteral,
    LengthOf,
    MmtType,
    Model,
    Name,
    NextEncaps,
    NextOffset,
    OffsetOf,
    Properties,
    Scope,
    ScopeValue,
    SizeOf,
    Span,
    Statement,
    Struct,
    StructField,
    StructType,
    Switch,
    ValueOf,
)

__all__ = ["STDIN", "PdlSyntaxError", "parse"]

#: The file name of a model read from standard input.
STDIN = "<stdin>"

T = TypeVar("T")

#: Properties keys, in the order the grammar fixes (G:179).
PROPERTY_KEYS = (
    "label",
    "id",
    "context",
    "session_context",
    "session",
    "encapsulation",
    "encoding",
)

#: attribute keys, in the order the grammar fixes (G:383).
ATTRIBUTE_KEYS = ("alias", "data_type", "data_len", "offset", "scope")

#: Encoding spellings (G:250-255), plus the ``little`` alias of ``host``
#: (corpus README, Decided rules).
ENCODINGS: dict[str, Encoding] = {
    "network": Encoding.NETWORK,
    "host": Encoding.HOST,
    "little": Encoding.HOST,
    "ASCII": Encoding.ASCII,
    "UNICODE": Encoding.UNICODE,
}

#: Scope spellings (G:423-429).
SCOPES: dict[str, Scope] = {
    "SCOPE_PACKET": Scope.PACKET,
    "SCOPE_SESSION": Scope.SESSION,
    "packet": Scope.PACKET,
    "session": Scope.SESSION,
}

#: How deep parentheses and ``if`` blocks may nest, together. It keeps the
#: recursion far below Python's limit.
MAX_DEPTH = 64

#: How many operands one expression may have, counted over the whole
#: expression, inside parentheses too. A chain such as ``1+1+...+1`` parses
#: in a loop but builds a tree as deep as it is long, and ``repr``, ``==``,
#: ``hash``, ``copy.deepcopy``, ``pickle`` and ``dumps`` of the model recurse
#: through it. With this cap and ``MAX_DEPTH``, every operation works on the
#: deepest model (tested on Python 3.10, which has the lowest limits); the
#: example models use at most 4 operands.
MAX_OPERANDS = 64

#: Words that start the construct after a define's value: a missing value
#: is reported instead of taking them as a name.
_DEFINE_STOP = frozenset({"define", "Properties"})

#: Words that start the next classifynext statement or branch.
_STATEMENT_STOP = frozenset({"break", "case", "default", "nextencaps", "nextoffset"})

#: Expression functions (G:703-758).
FUNCTIONS = ("val", "sizeof", "offset", "len", "ntohs", "ntohl")

_COMPARISONS: dict[str, BinaryOperator] = {
    "==": BinaryOperator.EQ,
    "!=": BinaryOperator.NE,
    ">": BinaryOperator.GT,
    "<": BinaryOperator.LT,
    ">=": BinaryOperator.GE,
    "<=": BinaryOperator.LE,
}

_ELEMENT_TYPE_HINT = (
    "an element type is int, long, uint32_t, short, uint16_t, char, u_char or "
    "uint8_t (optionally after `unsigned`), one of those or void followed by `*`, "
    "an MMT_* type, or `struct X`"
)

_EXPRESSION_HINT = (
    "an expression is made of numbers, `+ - * /`, comparisons, AND, OR, "
    "parentheses and val(x), sizeof(T), offset(x), len(x), ntohs(n), ntohl(n)"
)

_EXPR_TYPES = (IntLiteral, BinaryOp, ValueOf, SizeOf, OffsetOf, LengthOf, ByteSwap)

_ELEMENTS_HINT = "the elements of Attributes and of if/else branches are attribute, struct and if"


class PdlSyntaxError(Exception):
    """The text is not a PDL v1 model; ``diagnostics`` says why, sorted."""

    def __init__(self, diagnostics: Sequence[Diagnostic]) -> None:
        self.diagnostics: tuple[Diagnostic, ...] = tuple(sorted_diagnostics(diagnostics))
        first = self.diagnostics[0]
        count = len(self.diagnostics)
        more = f" (and {count - 1} more)" if count > 1 else ""
        super().__init__(f"{first.location}: {first.message}{more}")


class _Fail(Exception):
    """Unwinds the parser to the nearest recovery point."""

    def __init__(self, diagnostic: Diagnostic) -> None:
        super().__init__(diagnostic.message)
        self.diagnostic = diagnostic


def _did_you_mean(word: str, choices: Sequence[str]) -> str:
    close = difflib.get_close_matches(word, choices, n=1, cutoff=0.6)
    if not close:
        close = [c for c in choices if c.lower() == word.lower()]
    return f"did you mean `{close[0]}`? " if close else ""


def _expr_or_none(value: object) -> Expr | None:
    assert value is None or isinstance(value, _EXPR_TYPES)
    return value


def _quoted_list(words: Sequence[str]) -> str:
    return ", ".join(f"`{w}`" for w in words)


class _Parser:
    def __init__(self, tokens: list[Token]) -> None:
        self.tokens = tokens
        self.i = 0
        self.errors: list[Diagnostic] = []
        self.depth = 0
        self.operands = 0

    @contextlib.contextmanager
    def nested(self, opening: Token) -> Iterator[None]:
        """One more level of parentheses or ``if`` blocks, up to ``MAX_DEPTH``."""
        if self.depth >= MAX_DEPTH:
            self.fail(
                "model.syntax.too-deep",
                f"more than {MAX_DEPTH} nested parentheses or `if` blocks",
                "flatten the expression or the conditionals; no protocol needs this depth",
                opening,
            )
        self.depth += 1
        try:
            yield
        finally:
            self.depth -= 1

    # --- Token access ---------------------------------------------------

    def peek(self, ahead: int = 0) -> Token:
        return self.tokens[min(self.i + ahead, len(self.tokens) - 1)]

    def advance(self) -> Token:
        token = self.tokens[self.i]
        if token.kind is not Kind.EOF:
            self.i += 1
        return token

    def fail(
        self,
        code: str,
        message: str,
        hint: str,
        at: Token | Span,
        related: Sequence[Related] = (),
    ) -> NoReturn:
        span = at.span if isinstance(at, Token) else at
        raise _Fail(
            Diagnostic(
                Severity.ERROR,
                code,
                message,
                hint=hint,
                location=span.location(),
                related=related,
            )
        )

    def unexpected(self, expected: str, hint: str, token: Token | None = None) -> NoReturn:
        token = token or self.peek()
        message = f"expected {expected}, found {token.describe()}"
        if token.kind is Kind.EOF:
            self.fail("model.syntax.unexpected-end", message, hint, token)
        self.fail("model.syntax.unexpected-token", message, hint, token)

    def expect(self, punct: str, hint: str, after: str = "") -> Token:
        token = self.peek()
        if not token.is_punct(punct):
            where = f" after {after}" if after else ""
            self.unexpected(f"`{punct}`{where}", hint)
        return self.advance()

    def keyword(self, word: str, hint: str) -> Token:
        token = self.peek()
        if not token.is_word(word):
            extra = ""
            if token.kind is Kind.IDENT and token.text.lower() == word.lower():
                extra = f"keywords are case-sensitive: write `{word}`; "
            self.unexpected(f"`{word}`", extra + hint)
        return self.advance()

    def name(self, what: str, hint: str) -> Name:
        token = self.peek()
        if token.kind is not Kind.IDENT:
            self.unexpected(what, hint)
        self.advance()
        return Name(token.text, token.span)

    # --- Numbers ----------------------------------------------------------

    def integer(self, what: str, hint: str, *, allow_hex: bool = True) -> IntLiteral:
        """A literal with an optional ``-``, as the grammar's ``NBSTR`` and ``HEXNB``."""
        start = self.peek()
        sign = ""
        if start.is_punct("-"):
            sign = "-"
            self.advance()
        token = self.peek()
        if token.kind is Kind.NUMBER or (allow_hex and token.kind is Kind.HEX):
            self.advance()
            digits = token.text
            magnitude = int(digits[2:], 16) if token.kind is Kind.HEX else int(digits, 10)
            value = -magnitude if sign else magnitude
            return IntLiteral(value, sign + digits, start.span.to(token.span))
        if token.kind is Kind.HEX:
            self.fail(
                "model.syntax.invalid-value",
                f"{what} must be a decimal number, found `{token.text}`",
                hint,
                token,
            )
        self.unexpected(what, hint)

    def int_or_name(
        self, what: str, hint: str, stop: frozenset[str] = frozenset()
    ) -> IntLiteral | Name:
        """A number, or a define name that is not one of the ``stop`` words.

        The ``stop`` words start the next construct, so a missing value is
        reported instead of taking that word as a name.
        """
        token = self.peek()
        if token.kind is Kind.IDENT:
            if token.text in stop:
                self.unexpected(what, hint)
            self.advance()
            return Name(token.text, token.span)
        return self.integer(what, hint)

    # --- Quoted values ----------------------------------------------------

    def quoted(self, key: Token, parse: Callable[[], T], placeholder: T) -> T:
        """``"value"`` after ``key =``, on one line.

        An error inside the value is recorded and parsing goes on after the
        value's closing quote, when that quote is on the same line; a missing
        closing quote stops the parse.
        """
        opening = self.expect(
            '"',
            f'the value of `{key.text}` is written in double quotes: {key.text}="..."',
            after=f"`{key.text} =`",
        )
        try:
            value = parse()
        except _Fail as failure:
            if self.peek().span.line != opening.span.line:
                self.unterminated(key, opening)
            if not self.skip_to_closing_quote(opening):
                raise
            self.errors.append(failure.diagnostic)
            return placeholder
        if self.peek().span.line != opening.span.line:
            self.unterminated(key, opening)
        self.expect(
            '"',
            f'add the closing `"` after the value of `{key.text}`',
            after=f"the value of `{key.text}`",
        )
        return value

    def unterminated(self, key: Token, opening: Token) -> NoReturn:
        self.fail(
            "model.syntax.unterminated-string",
            f"the value of `{key.text}` is not closed on its line",
            'add the closing `"` after the value; a quoted value cannot span lines',
            opening,
        )

    def skip_to_closing_quote(self, opening: Token) -> bool:
        """Move past the next ``"`` if it is on ``opening``'s line."""
        for ahead in range(len(self.tokens) - self.i):
            token = self.peek(ahead)
            if token.span.line != opening.span.line:
                return False
            if token.is_punct('"'):
                self.i += ahead + 1
                return True
        return False

    def quoted_word(self, what: str, hint: str) -> Token:
        token = self.peek()
        if token.kind is not Kind.IDENT:
            self.unexpected(what, hint)
        return self.advance()

    # --- Model (G:27-33) ----------------------------------------------------

    def model(self) -> Model:
        start = self.keyword("Protocol", "a PDL model starts with `Protocol {`")
        self.expect("{", "write `Protocol {` to open the model", after="`Protocol`")
        defines = []
        while self.peek().is_word("define"):
            defines.append(self.define())
        properties = self.properties()
        attributes = self.attributes()
        classify_next = None
        if self.peek().is_word("classifynext"):
            classify_next = self.classify_next()
        token = self.peek()
        if not token.is_punct("}"):
            if token.is_word("define"):
                self.fail(
                    "model.syntax.out-of-order",
                    "`define` must come before `Properties`",
                    "move the defines to the top of the `Protocol` block",
                    token,
                )
            if token.is_word("Properties") or token.is_word("Attributes"):
                self.fail(
                    "model.syntax.out-of-order",
                    f"a second `{token.text}` block, or one out of order",
                    "a model has, in this order: defines, one Properties block, "
                    "one Attributes block and at most one classifynext block",
                    token,
                )
            self.unexpected(
                "`classifynext` or the `}` that closes `Protocol`",
                "only a classifynext block may follow Attributes",
            )
        end = self.advance()
        trailing = self.peek()
        if trailing.kind is not Kind.EOF:
            self.fail(
                "model.syntax.trailing-input",
                f"unexpected {trailing.describe()} after the end of the `Protocol` block",
                "a model ends with the `}` that closes `Protocol`: remove what follows "
                "it, or put it in a comment (the Java tool ignored it silently)",
                trailing,
            )
        return Model(
            tuple(defines), properties, attributes, classify_next, start.span.to(end.span)
        )

    # --- define (G:40-60) ---------------------------------------------------

    def define(self) -> Define:
        start = self.advance()
        name = self.name("a name after `define`", "write `define NAME = value`")
        self.expect("=", "write `define NAME = value`", after=f"`define {name.text}`")
        value = self.int_or_name(
            "a number or a name",
            "a define's value is a decimal number, a hex number (0x..) or another name",
            stop=_DEFINE_STOP,
        )
        return Define(name, value, start.span.to(value.span))

    # --- Properties (G:178-255) ----------------------------------------------

    def keys(
        self,
        block: Token,
        allowed: Sequence[str],
        parse_value: Callable[[Token], object],
    ) -> tuple[dict[str, object], Token]:
        """``key = value`` pairs up to ``}``, in the grammar's order."""
        values: dict[str, object] = {}
        seen: dict[str, Token] = {}
        order_hint = f"`{block.text}` keys go in this order: {', '.join(allowed)}"
        while True:
            token = self.peek()
            if token.is_punct("}"):
                return values, self.advance()
            closing = f"a `{block.text}` key or the `}}` that closes `{block.text}`"
            if token.kind is not Kind.IDENT:
                self.unexpected(closing, order_hint)
            if token.text not in allowed and not self.peek(1).is_punct("="):
                self.unexpected(closing, order_hint)
            if token.text not in allowed:
                self.fail(
                    "model.syntax.unknown-key",
                    f"`{token.text}` is not a `{block.text}` key",
                    _did_you_mean(token.text, allowed) + order_hint,
                    token,
                )
            if token.text in seen:
                self.fail(
                    "model.syntax.duplicate-key",
                    f"`{token.text}` is given twice",
                    "remove one of the two",
                    token,
                    related=[Related("first given here", seen[token.text].span.location())],
                )
            later = [k for k in seen if allowed.index(k) > allowed.index(token.text)]
            if later:
                self.fail(
                    "model.syntax.out-of-order",
                    f"`{token.text}` must come before `{later[0]}`",
                    order_hint,
                    token,
                    related=[Related(f"`{later[0]}` is here", seen[later[0]].span.location())],
                )
            self.advance()
            seen[token.text] = token
            self.expect("=", f'write {token.text}="..."', after=f"`{token.text}`")
            values[token.text] = parse_value(token)

    def missing(self, block: Token, key: str, example: str) -> NoReturn:
        self.fail(
            "model.syntax.missing-key",
            f"`{block.text}` has no `{key}`",
            f"add {example}",
            block,
        )

    def properties(self) -> Properties:
        token = self.peek()
        if token.is_word("Attributes"):
            self.fail(
                "model.syntax.out-of-order",
                "`Attributes` must come after `Properties`",
                "a model has a Properties block before its Attributes block",
                token,
            )
        block = self.keyword(
            "Properties", "the defines are followed by the `Properties { ... }` block"
        )
        self.expect("{", "write `Properties {`", after="`Properties`")
        values, end = self.keys(block, PROPERTY_KEYS, self.property_value)
        if "label" not in values:
            self.missing(block, "label", 'label = "NAME"')
        if "id" not in values:
            self.missing(block, "id", 'id = "NUMBER"')

        def flag(key: str) -> Flag | None:
            value = values.get(key)
            assert value is None or isinstance(value, Flag)
            return value

        label, proto_id, encoding = values["label"], values["id"], values.get("encoding")
        assert isinstance(label, Name) and isinstance(proto_id, IntLiteral)
        assert encoding is None or isinstance(encoding, EncodingValue)
        return Properties(
            label,
            proto_id,
            flag("context"),
            flag("session_context"),
            flag("session"),
            flag("encapsulation"),
            encoding,
            block.span.to(end.span),
        )

    def property_value(self, key: Token) -> object:
        if key.text == "label":
            return self.quoted(key, self.label_value, Name("", key.span))
        if key.text == "id":
            return self.quoted(
                key,
                lambda: self.integer(
                    "the protocol id",
                    'the protocol id is a decimal number: id = "960"',
                    allow_hex=False,
                ),
                IntLiteral(0, "0", key.span),
            )
        if key.text == "encoding":
            return self.quoted(key, self.encoding_value, None)
        return self.quoted(key, lambda: self.flag_value(key), None)

    def label_value(self) -> Name:
        return self.name(
            "the protocol name",
            'the label is one word of letters, digits and `_`: label = "MYPROTO"',
        )

    def flag_value(self, key: Token) -> Flag:
        token = self.quoted_word("`true` or `false`", f'write {key.text} = "true" or "false"')
        if token.text not in ("true", "false"):
            self.fail(
                "model.syntax.invalid-value",
                f"`{key.text}` is `true` or `false`, not `{token.text}`",
                _did_you_mean(token.text, ["true", "false"])
                + f'write {key.text} = "true" or "false"',
                token,
            )
        return Flag(token.text == "true", token.span)

    def encoding_value(self) -> EncodingValue:
        hint = 'write encoding = "network", "host" (or its alias "little"), "ASCII" or "UNICODE"'
        token = self.peek()
        if token.kind is not Kind.IDENT:
            self.unexpected("an encoding", hint)
        if token.text not in ENCODINGS:
            self.fail(
                "model.syntax.invalid-value",
                f"`{token.text}` is not an encoding",
                _did_you_mean(token.text, list(ENCODINGS)) + hint,
                token,
            )
        self.advance()
        return EncodingValue(ENCODINGS[token.text], token.text, token.span)

    # --- Attributes (G:263-312) -----------------------------------------------

    def attributes(self) -> Attributes:
        token = self.peek()
        if token.is_word("Properties"):
            self.fail(
                "model.syntax.out-of-order",
                "a second `Properties` block",
                "a model has one Properties block, followed by one Attributes block",
                token,
            )
        if token.is_word("define"):
            self.fail(
                "model.syntax.out-of-order",
                "`define` must come before `Properties`",
                "move the defines to the top of the `Protocol` block",
                token,
            )
        block = self.keyword(
            "Attributes", "the Properties block is followed by the `Attributes { ... }` block"
        )
        self.expect("{", "write `Attributes {`", after="`Attributes`")
        elements, end = self.elements("Attributes")
        return Attributes(elements, block.span.to(end.span))

    def elements(self, where: str) -> tuple[tuple[AttributeElement, ...], Token]:
        """Attribute elements up to and including the closing ``}``."""
        elements: list[AttributeElement] = []
        while True:
            token = self.peek()
            if token.is_punct("}"):
                return tuple(elements), self.advance()
            if token.is_word("attribute"):
                elements.append(self.attribute())
            elif token.is_word("struct"):
                elements.append(self.struct())
            elif token.is_word("if"):
                elements.append(self.conditional())
            elif token.is_word("else"):
                self.fail(
                    "model.syntax.unexpected-token",
                    "`else` without a matching `if`",
                    "an `else { ... }` comes right after the `}` of an `if` block",
                    token,
                )
            else:
                self.unexpected(
                    f"`attribute`, `struct`, `if` or the `}}` that closes {where}", _ELEMENTS_HINT
                )

    def attribute(self) -> Attribute:
        block = self.advance()
        self.expect(
            "{", 'write `attribute { alias="..." data_type="..." ... }`', after="`attribute`"
        )
        values, end = self.keys(block, ATTRIBUTE_KEYS, self.attribute_value)
        if "alias" not in values:
            self.missing(block, "alias", 'alias="name"')
        if "data_type" not in values:
            self.missing(block, "data_type", 'data_type="MMT_..."')
        alias, data_type, scope = values["alias"], values["data_type"], values.get("scope")
        assert isinstance(alias, Name) and isinstance(data_type, DataTypeValue)
        assert scope is None or isinstance(scope, ScopeValue)
        return Attribute(
            alias,
            data_type,
            _expr_or_none(values.get("data_len")),
            _expr_or_none(values.get("offset")),
            scope,
            block.span.to(end.span),
        )

    def attribute_value(self, key: Token) -> object:
        if key.text == "alias":
            return self.quoted(
                key,
                lambda: self.name(
                    "an attribute name",
                    'an alias is one word of letters, digits and `_`: alias="length"',
                ),
                Name("", key.span),
            )
        if key.text == "data_type":
            return self.quoted(
                key, self.data_type_value, DataTypeValue(DataType.MMT_U8_DATA, key.span)
            )
        if key.text == "scope":
            return self.quoted(key, self.scope_value, None)
        placeholder: Expr = IntLiteral(0, "0", key.span)
        return self.quoted(key, self.expression, placeholder)

    def data_type_value(self) -> DataTypeValue:
        token = self.peek()
        hint = "a data_type is one of the MMT_* types, for example MMT_U16_DATA"
        if token.kind is not Kind.IDENT:
            self.unexpected("a data type", hint)
        if token.text not in MMT_TYPES:
            self.fail(
                "model.syntax.unknown-type",
                f"`{token.text}` is not an MMT_* data type",
                _did_you_mean(token.text, sorted(MMT_TYPES)) + hint,
                token,
            )
        self.advance()
        return DataTypeValue(DataType(token.text), token.span)

    def scope_value(self) -> ScopeValue:
        token = self.peek()
        hint = 'write scope="packet" or "session" (or SCOPE_PACKET, SCOPE_SESSION)'
        if token.kind is not Kind.IDENT:
            self.unexpected("a scope", hint)
        if token.text not in SCOPES:
            self.fail(
                "model.syntax.invalid-value",
                f"`{token.text}` is not a scope",
                _did_you_mean(token.text, list(SCOPES)) + hint,
                token,
            )
        self.advance()
        return ScopeValue(SCOPES[token.text], token.text, token.span)

    # --- struct (G:431-659) ---------------------------------------------------

    def struct(self) -> Struct:
        start = self.advance()
        name = self.name("a struct name", "write `struct NAME { ... }`")
        self.expect("{", "write `struct NAME { type field; ... }`", after=f"`struct {name.text}`")
        elements = []
        while not self.peek().is_punct("}"):
            elements.append(self.element())
        end = self.advance()
        return Struct(name, tuple(elements), start.span.to(end.span))

    def element(self) -> Element:
        element_type = self.element_type("a field type or the `}` that closes the struct")
        fields = [self.struct_field()]
        while self.peek().is_punct(","):
            self.advance()
            fields.append(self.struct_field())
        end = self.expect(
            ";",
            "a struct declaration is `type name, name:bits, ...;`",
            after=f"`{fields[-1].name.text}`",
        )
        return Element(element_type, tuple(fields), element_type.span.to(end.span))

    def struct_field(self) -> StructField:
        name = self.name("a field name", "a struct declaration is `type name, name:bits, ...;`")
        if not self.peek().is_punct(":"):
            return StructField(name, None, name.span)
        self.advance()
        width = self.integer(
            "a bit width", "a bitfield is `name:bits`, with a decimal width", allow_hex=False
        )
        return StructField(name, width, name.span.to(width.span))

    def element_type(self, what: str) -> ElementType:
        """A struct field type or a ``sizeof`` argument (G:591-648)."""
        start = self.peek()
        if start.kind is not Kind.IDENT:
            self.unexpected(what, _ELEMENT_TYPE_HINT)
        self.advance()
        if start.text == "struct":
            name = self.name("a struct name after `struct`", "write `struct NAME`")
            return StructType(name, start.span.to(name.span))
        if start.text in MMT_TYPES:
            return MmtType(DataType(start.text), start.span)
        unsigned = start.text == "unsigned"
        base = start
        if unsigned:
            base = self.peek()
            if base.kind is not Kind.IDENT or base.text not in C_TYPE_WORDS:
                self.fail(
                    "model.syntax.unknown-type",
                    f"`unsigned` cannot be followed by {base.describe()}",
                    _ELEMENT_TYPE_HINT,
                    base,
                )
            self.advance()
        if base.text not in C_TYPE_WORDS:
            self.fail(
                "model.syntax.unknown-type",
                f"`{base.text}` is not a PDL type",
                _did_you_mean(base.text, sorted(C_TYPE_WORDS | MMT_TYPES)) + _ELEMENT_TYPE_HINT,
                base,
            )
        star = self.peek()
        pointer = star.is_punct("*")
        if pointer:
            if (star.span.line, star.span.column) != (base.span.end_line, base.span.end_column):
                self.fail(
                    "model.syntax.unexpected-token",
                    f"a pointer type is written `{base.text}*`, with no space before `*`",
                    f"write `{base.text}*` (the grammar's pointer token, G:865)",
                    star,
                )
            self.advance()
        elif base.text == "void":
            self.fail(
                "model.syntax.unknown-type",
                "`void` is only a pointer base",
                "write `void*`, or use a sized type",
                base,
            )
        end = star if pointer else base
        return CType(base.text, unsigned, pointer, start.span.to(end.span))

    # --- if / else (G:314-380) --------------------------------------------------

    def conditional(self) -> Conditional:
        start = self.advance()
        with self.nested(start):
            return self.conditional_body(start)

    def conditional_body(self, start: Token) -> Conditional:
        self.expect("(", "write `if (condition) { ... }`", after="`if`")
        condition = self.expression()
        self.expect(")", "close the condition with `)`", after="the condition")
        self.expect("{", "write `if (condition) { ... }`", after="`)`")
        then_branch, end = self.elements("the `if` block")
        else_branch = None
        if self.peek().is_word("else"):
            self.advance()
            if self.peek().is_word("if"):
                self.fail(
                    "model.syntax.unexpected-token",
                    "`else if` is not PDL",
                    "nest the `if` inside the else block: `else { if (...) { ... } }`",
                    self.peek(),
                )
            self.expect("{", "write `else { ... }`", after="`else`")
            else_branch, end = self.elements("the `else` block")
        return Conditional(condition, then_branch, else_branch, start.span.to(end.span))

    # --- Expressions (G:661-758) ----------------------------------------------

    def expression(self) -> Expr:
        """A whole expression, of at most ``MAX_OPERANDS`` operands."""
        self.operands = 0
        return self.or_expr()

    def or_expr(self) -> Expr:
        """``bformula``: OR binds loosest, then AND, comparison, ``+ -``, ``* /``."""
        left = self.and_expr()
        while self.peek().is_word("OR"):
            self.advance()
            right = self.and_expr()
            left = BinaryOp(BinaryOperator.OR, left, right, left.span.to(right.span))
        return left

    def and_expr(self) -> Expr:
        left = self.comparison()
        while self.peek().is_word("AND"):
            self.advance()
            right = self.comparison()
            left = BinaryOp(BinaryOperator.AND, left, right, left.span.to(right.span))
        return left

    def comparison(self) -> Expr:
        left = self.additive()
        token = self.peek()
        if token.kind is not Kind.PUNCT or token.text not in _COMPARISONS:
            return left
        self.advance()
        right = self.additive()
        result = BinaryOp(_COMPARISONS[token.text], left, right, left.span.to(right.span))
        again = self.peek()
        if again.kind is Kind.PUNCT and again.text in _COMPARISONS:
            self.fail(
                "model.syntax.invalid-expression",
                "comparisons cannot be chained",
                "join two comparisons with AND or OR, or use parentheses",
                again,
            )
        return result

    def additive(self) -> Expr:
        left = self.multiplicative()
        while self.peek().is_punct("+") or self.peek().is_punct("-"):
            op = BinaryOperator(self.advance().text)
            right = self.multiplicative()
            left = BinaryOp(op, left, right, left.span.to(right.span))
        return left

    def multiplicative(self) -> Expr:
        left = self.atom()
        while self.peek().is_punct("*") or self.peek().is_punct("/"):
            op = BinaryOperator(self.advance().text)
            right = self.atom()
            left = BinaryOp(op, left, right, left.span.to(right.span))
        return left

    def atom(self) -> Expr:
        token = self.peek()
        if not token.is_punct("("):
            self.operands += 1
            if self.operands > MAX_OPERANDS:
                self.fail(
                    "model.syntax.too-many-operands",
                    f"more than {MAX_OPERANDS} operands in one expression",
                    "shorten the expression; no protocol needs this many operands",
                    token,
                )
        if token.kind in (Kind.NUMBER, Kind.HEX):
            return self.integer("a number", _EXPRESSION_HINT)
        if token.is_punct("-"):
            following = self.peek(1)
            if following.kind not in (Kind.NUMBER, Kind.HEX):
                self.fail(
                    "model.syntax.invalid-expression",
                    "only a number can be negated",
                    "write `0 - x` to negate an expression",
                    token,
                )
            return self.integer("a number", _EXPRESSION_HINT)
        if token.is_punct("("):
            self.advance()
            with self.nested(token):
                inner = self.or_expr()
            end = self.expect(")", "close the parenthesis", after="the expression")
            # The tree keeps the grouping; the span covers the parentheses.
            return dataclasses.replace(inner, span=token.span.to(end.span))
        if token.kind is Kind.IDENT:
            if self.peek(1).is_punct("("):
                return self.function()
            if token.text in FUNCTIONS:
                self.unexpected(
                    f"`(` after `{token.text}`", f"write `{token.text}(...)`", self.peek(1)
                )
            self.fail(
                "model.syntax.invalid-expression",
                f"`{token.text}` is not an expression",
                "a bare name has no value: write val(name) for an attribute's value, "
                "or a number; to leave an offset or length to user code, omit the key",
                token,
            )
        self.unexpected("an expression", _EXPRESSION_HINT)

    def function(self) -> Expr:
        name = self.advance()
        if name.text not in FUNCTIONS:
            self.fail(
                "model.syntax.invalid-expression",
                f"`{name.text}` is not a PDL function",
                _did_you_mean(name.text, FUNCTIONS)
                + f"the functions are {_quoted_list(FUNCTIONS)}",
                name,
            )
        self.advance()  # (
        node: Expr
        if name.text == "sizeof":
            element_type = self.element_type("a type")
            end = self.expect(")", "write `sizeof(type)`", after="the type")
            node = SizeOf(element_type, name.span.to(end.span))
        elif name.text in ("ntohs", "ntohl"):
            operand = self.peek()
            if operand.is_punct("-"):
                operand = self.peek(1)
            if operand.kind not in (Kind.NUMBER, Kind.HEX):
                self.fail(
                    "model.syntax.invalid-expression",
                    f"`{name.text}` takes a number, found {operand.describe()}",
                    f"write `{name.text}(0x0300)`; the grammar swaps only literals (G:743-758)",
                    operand,
                )
            literal = self.integer("a number", _EXPRESSION_HINT)
            end = self.expect(")", f"write `{name.text}(number)`", after="the number")
            width = 16 if name.text == "ntohs" else 32
            node = ByteSwap(width, literal, name.span.to(end.span))
        else:
            target = self.name("an attribute name", f"write `{name.text}(attribute)`")
            end = self.expect(")", f"write `{name.text}(attribute)`", after=f"`{target.text}`")
            span = name.span.to(end.span)
            if name.text == "val":
                node = ValueOf(target, span)
            elif name.text == "offset":
                node = OffsetOf(target, span)
            else:
                node = LengthOf(target, span)
        return node

    # --- classifynext (G:62-176, 760-788) -------------------------------------

    def classify_next(self) -> ClassifyNext:
        start = self.advance()
        self.expect("{", "write `classifynext { switch(...) { ... } }`", after="`classifynext`")
        switch = self.switch()
        end = self.expect(
            "}",
            "classifynext holds exactly one switch",
            after="the switch",
        )
        return ClassifyNext(switch, start.span.to(end.span))

    def switch(self) -> Switch:
        start = self.keyword("switch", "classifynext holds one `switch(expression) { ... }`")
        self.expect("(", "write `switch(expression)`", after="`switch`")
        subject = self.expression()
        self.expect(")", "close the switch expression with `)`", after="the expression")
        self.expect("{", "write `switch(expression) { case ...: ... }`", after="`)`")
        cases: list[Case] = []
        default: Default | None = None
        while True:
            token = self.peek()
            if token.is_punct("}"):
                break
            if token.is_word("case"):
                if default is not None:
                    self.fail(
                        "model.syntax.out-of-order",
                        "a `case` after `default`",
                        "`default` must be the last branch of the switch",
                        token,
                        related=[Related("`default` is here", default.span.location())],
                    )
                cases.append(self.case())
            elif token.is_word("default"):
                if default is not None:
                    self.fail(
                        "model.syntax.duplicate-key",
                        "a second `default`",
                        "a switch has at most one default branch",
                        token,
                        related=[Related("first default here", default.span.location())],
                    )
                default = self.default()
            else:
                self.unexpected(
                    "`case`, `default` or the `}` that closes the switch",
                    "a branch is `case N:` or `default:`, then nextencaps and nextoffset "
                    "statements and an optional `break`",
                )
        end = self.advance()
        return Switch(subject, tuple(cases), default, start.span.to(end.span))

    def case(self) -> Case:
        start = self.advance()
        label = self.int_or_name(
            "a case label",
            "a case label is a decimal number, a hex number or a define name",
            stop=_STATEMENT_STOP,
        )
        colon = self.expect(":", "write `case N:`", after="the case label")
        statements, has_break, end = self.statements(colon)
        return Case(label, statements, has_break, start.span.to(end))

    def default(self) -> Default:
        start = self.advance()
        colon = self.expect(":", "write `default:`", after="`default`")
        statements, has_break, end = self.statements(colon)
        return Default(statements, has_break, start.span.to(end))

    def statements(self, last: Token) -> tuple[tuple[Statement, ...], bool, Span]:
        statements: list[Statement] = []
        end = last.span
        while True:
            token = self.peek()
            if token.is_word("nextencaps"):
                self.advance()
                self.expect("=", "write `nextencaps = N`", after="`nextencaps`")
                value = self.int_or_name(
                    "a protocol id or a define name",
                    "nextencaps takes a number or a define name",
                    stop=_STATEMENT_STOP,
                )
                statements.append(NextEncaps(value, token.span.to(value.span)))
            elif token.is_word("nextoffset"):
                self.advance()
                self.expect("=", "write `nextoffset = expression`", after="`nextoffset`")
                expr = self.expression()
                statements.append(NextOffset(expr, token.span.to(expr.span)))
            else:
                break
            end = statements[-1].span
        if self.peek().is_word("break"):
            return tuple(statements), True, self.advance().span
        return tuple(statements), False, end


def parse(text: str, *, filename: str) -> Model:
    """Parse a PDL v1 model.

    ``filename`` names the text in diagnostics and spans: a path, or
    ``STDIN`` (``<stdin>``) for standard input. Parsing reads nothing and
    writes nothing.

    Raises ``PdlSyntaxError`` with ``model.syntax.*`` diagnostics, sorted,
    when the text is not a PDL v1 model.
    """
    try:
        tokens = tokenize(text, filename)
    except LexError as error:
        raise PdlSyntaxError([error.diagnostic]) from None
    parser = _Parser(tokens)
    try:
        model = parser.model()
    except _Fail as failure:
        raise PdlSyntaxError([*parser.errors, failure.diagnostic]) from None
    if parser.errors:
        raise PdlSyntaxError(parser.errors)
    return model
