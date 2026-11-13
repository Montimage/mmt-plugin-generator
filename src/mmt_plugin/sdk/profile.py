"""SDK profiles: what generated code uses from one mmt-dpi version.

A profile is a JSON file bundled in ``mmt_plugin/sdk/profiles/<version>.json``
(schema: ``mmt_plugin/schemas/sdk/v1/profile.json``). It lists the headers,
types, struct layouts, callback signatures, registration calls, helpers,
constants and logger macros that the generator emits, each with the header
that declares it, relative to ``<prefix>/dpi/include``. Every entry is one a
generator uses; ``mmt_plugin.sdk.headercheck`` checks them against the real
headers.

``load_profile`` parses and checks a file into frozen dataclasses. The JSON
Schema is the documentation and the test oracle; the loader repeats its
checks by hand (there are no run-time dependencies) and adds the
cross-references a schema cannot express.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from functools import cache
from importlib import resources
from pathlib import Path
from typing import Any

__all__ = [
    "SCHEMA_RESOURCE",
    "SCHEMA_VERSION",
    "Callback",
    "ClassProvider",
    "Constant",
    "Field",
    "Function",
    "Header",
    "Logger",
    "Macro",
    "Param",
    "Parents",
    "Profile",
    "ProfileError",
    "Struct",
    "TypeName",
    "bundled_versions",
    "get_bundled",
    "load_profile",
    "load_schema",
    "parse_profile",
    "version_key",
]

#: The ``schema_version`` this loader reads.
SCHEMA_VERSION = 1

#: The profile schema's path inside the package.
SCHEMA_RESOURCE = "schemas/sdk/v1/profile.json"

#: The bundled profiles' directory inside the package.
PROFILES_RESOURCE = "sdk/profiles"

_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_HEADER = re.compile(r"^[A-Za-z0-9_]+(/[A-Za-z0-9_]+)*\.h$")
_VERSION = re.compile(r"^[0-9]+(\.[0-9]+)*$")
_LAYOUTS = ("complete", "partial")


class ProfileError(ValueError):
    """A profile file that is not valid JSON or does not follow the schema."""


def version_key(version: str) -> tuple[int, ...]:
    """The sort key of a dotted numeric version: ``"1.10.2"`` -> ``(1, 10, 2)``.

    Trailing zeros do not count (``1.10`` and ``1.10.0`` are equal). Raises
    ``ValueError`` for anything but dot-separated digits.
    """
    if not _VERSION.match(version):
        raise ValueError(f"not a dotted numeric version: {version!r}")
    parts = [int(p) for p in version.split(".")]
    while len(parts) > 1 and parts[-1] == 0:
        parts.pop()
    return tuple(parts)


@dataclass(frozen=True)
class Header:
    """A header, relative to ``<prefix>/dpi/include``."""

    name: str
    doc: str


@dataclass(frozen=True)
class TypeName:
    """A type generated code names; ``definition`` is set for a scalar or
    pointer typedef, ``None`` for an opaque or enum type."""

    name: str
    header: str
    definition: str | None
    doc: str


@dataclass(frozen=True)
class Field:
    """A struct field and its C type name."""

    name: str
    type: str


@dataclass(frozen=True)
class Struct:
    """A struct type. A ``complete`` layout lists every field in order (it is
    written as a positional initializer); a ``partial`` one only the fields
    generated code reads."""

    name: str
    header: str
    layout: str
    fields: tuple[Field, ...]
    doc: str


@dataclass(frozen=True)
class Param:
    """A parameter: its name and C type name (never a function or array
    declarator, so ``f"{type} {name}"`` declares it)."""

    name: str
    type: str

    @property
    def declaration(self) -> str:
        """``type name``, as in a function definition."""
        sep = "" if self.type.endswith("*") else " "
        return f"{self.type}{sep}{self.name}"


def _args(params: Sequence[Param]) -> str:
    return ", ".join(p.type for p in params) or "void"


@dataclass(frozen=True)
class Callback:
    """A callback the generated code implements, by role, and the SDK typedef
    it must convert to."""

    role: str
    typedef: str
    header: str
    returns: str
    params: tuple[Param, ...]
    doc: str

    @property
    def function_type(self) -> str:
        """The C function type, ``int (const ipacket_t *, ...)``."""
        return f"{self.returns} ({_args(self.params)})"

    @property
    def pointer_type(self) -> str:
        """The C pointer-to-function type, ``int (*)(const ipacket_t *, ...)``."""
        return f"{self.returns} (*)({_args(self.params)})"


@dataclass(frozen=True)
class Function:
    """An SDK function generated code calls (a registration call or a helper).

    ``implements`` names the callback role a helper can stand in for (the
    ``general_*`` extraction functions are attribute extraction callbacks).
    """

    name: str
    header: str
    returns: str
    params: tuple[Param, ...]
    doc: str
    implements: str | None = None

    @property
    def function_type(self) -> str:
        """The C function type, ``bool (protocol_t *, mmt_proto_id_t)``."""
        return f"{self.returns} ({_args(self.params)})"


@dataclass(frozen=True)
class Constant:
    """An integer constant (a macro or an enumerator), with its group."""

    name: str
    header: str
    group: str
    doc: str


@dataclass(frozen=True)
class Macro:
    """A function-like macro generated code calls."""

    name: str
    header: str
    doc: str


@dataclass(frozen=True)
class Logger:
    """The logger: one macro per level, and the define that enables debug."""

    header: str
    error: str
    warn: str
    info: str
    debug: str
    debug_opt_in: str
    doc: str


@dataclass(frozen=True)
class ClassProvider:
    """The class provider: its struct, its registration call and the class
    of an unknown key."""

    header: str
    struct: str
    register: str
    unknown: str
    doc: str


@dataclass(frozen=True)
class Parents:
    """How generated code names a libmmt_tcpip parent protocol's id."""

    header: str
    declared_in: str
    id_macro: str
    examples: tuple[str, ...]
    doc: str

    def id_for(self, label: str) -> str:
        """The id macro of a parent label: ``"tcp"`` -> ``"PROTO_TCP"``."""
        return self.id_macro.replace("{LABEL}", label.upper())


@dataclass(frozen=True)
class Profile:
    """One SDK profile. ``version`` is the mmt-dpi version it describes."""

    version: str
    sdk: str
    c_std: str
    headers: tuple[Header, ...]
    types: tuple[TypeName, ...]
    structs: tuple[Struct, ...]
    callbacks: tuple[Callback, ...]
    registrations: tuple[Function, ...]
    helpers: tuple[Function, ...]
    constants: tuple[Constant, ...]
    macros: tuple[Macro, ...]
    logger: Logger
    class_provider: ClassProvider
    parents: Parents

    def callback(self, role: str) -> Callback:
        """The callback of a role; ``KeyError`` if the profile has none."""
        for cb in self.callbacks:
            if cb.role == role:
                return cb
        raise KeyError(role)

    def function(self, name: str) -> Function:
        """A registration call or helper by name; ``KeyError`` if absent."""
        for fn in (*self.registrations, *self.helpers):
            if fn.name == name:
                return fn
        raise KeyError(name)

    def struct(self, name: str) -> Struct:
        """A struct by name; ``KeyError`` if absent."""
        for st in self.structs:
            if st.name == name:
                return st
        raise KeyError(name)

    def constant(self, name: str) -> Constant:
        """A constant by name; ``KeyError`` if absent."""
        for c in self.constants:
            if c.name == name:
                return c
        raise KeyError(name)


# --- parsing -----------------------------------------------------------------


class _Reader:
    """Typed access to one JSON object, with the path for error messages."""

    def __init__(self, value: Any, where: str, keys: Sequence[str], optional: Sequence[str] = ()):
        if not isinstance(value, dict):
            raise ProfileError(f"{where}: expected an object")
        unknown = sorted(set(value) - set(keys) - set(optional) - {"$comment"})
        if unknown:
            raise ProfileError(f"{where}: unknown key {unknown[0]!r}")
        missing = [k for k in keys if k not in value]
        if missing:
            raise ProfileError(f"{where}: missing key {missing[0]!r}")
        self.value: dict[str, Any] = value
        self.where = where

    def text(self, key: str, pattern: re.Pattern[str] | None = None) -> str:
        value = self.value[key]
        if not isinstance(value, str) or not value.strip():
            raise ProfileError(f"{self.where}.{key}: expected a non-empty string")
        if pattern is not None and not pattern.match(value):
            raise ProfileError(f"{self.where}.{key}: {value!r} does not match {pattern.pattern}")
        return value

    def opt_text(self, key: str) -> str | None:
        return self.text(key) if key in self.value else None

    def array(self, key: str) -> list[Any]:
        value = self.value[key]
        if not isinstance(value, list):
            raise ProfileError(f"{self.where}.{key}: expected an array")
        return value


def _params(r: _Reader) -> tuple[Param, ...]:
    params = []
    for i, item in enumerate(r.array("params")):
        p = _Reader(item, f"{r.where}.params[{i}]", ("name", "type"))
        ptype = p.text("type")
        if "(" in ptype or "[" in ptype:
            raise ProfileError(
                f"{p.where}.type: {ptype!r} has a function or array declarator; use its typedef"
            )
        params.append(Param(p.text("name", _IDENT), ptype))
    return tuple(params)


def _function(item: Any, where: str) -> Function:
    r = _Reader(item, where, ("name", "header", "returns", "params", "doc"), ("implements",))
    return Function(
        name=r.text("name", _IDENT),
        header=r.text("header", _HEADER),
        returns=r.text("returns"),
        params=_params(r),
        doc=r.text("doc"),
        implements=r.opt_text("implements"),
    )


def _items(r: _Reader, key: str) -> list[tuple[Any, str]]:
    return [(item, f"{r.where}.{key}[{i}]") for i, item in enumerate(r.array(key))]


def parse_profile(data: Any, source: str = "<profile>") -> Profile:
    """Build a ``Profile`` from parsed JSON; raise ``ProfileError`` if it is
    not a valid profile of this schema version."""
    top = _Reader(
        data,
        source,
        (
            "schema_version",
            "profile",
            "sdk",
            "c_std",
            "headers",
            "types",
            "structs",
            "callbacks",
            "registrations",
            "helpers",
            "constants",
            "macros",
            "logger",
            "class_provider",
            "parents",
        ),
    )
    if top.value["schema_version"] != SCHEMA_VERSION:
        raise ProfileError(
            f"{source}.schema_version: {top.value['schema_version']!r} is not {SCHEMA_VERSION}"
        )
    headers = []
    for item, where in _items(top, "headers"):
        h = _Reader(item, where, ("name", "doc"))
        headers.append(Header(h.text("name", _HEADER), h.text("doc")))
    types = []
    for item, where in _items(top, "types"):
        t = _Reader(item, where, ("name", "header", "doc"), ("definition",))
        types.append(
            TypeName(
                t.text("name", _IDENT),
                t.text("header", _HEADER),
                t.opt_text("definition"),
                t.text("doc"),
            )
        )
    structs = []
    for item, where in _items(top, "structs"):
        s = _Reader(item, where, ("name", "header", "layout", "fields", "doc"))
        layout = s.text("layout")
        if layout not in _LAYOUTS:
            raise ProfileError(f"{where}.layout: {layout!r} is not one of {_LAYOUTS}")
        fields = []
        for fitem, fwhere in _items(s, "fields"):
            f = _Reader(fitem, fwhere, ("name", "type"))
            fields.append(Field(f.text("name", _IDENT), f.text("type")))
        if not fields:
            raise ProfileError(f"{where}.fields: a struct lists at least one field")
        structs.append(
            Struct(
                s.text("name", _IDENT),
                s.text("header", _HEADER),
                layout,
                tuple(fields),
                s.text("doc"),
            )
        )
    callbacks = []
    for item, where in _items(top, "callbacks"):
        c = _Reader(item, where, ("role", "typedef", "header", "returns", "params", "doc"))
        callbacks.append(
            Callback(
                role=c.text("role", _IDENT),
                typedef=c.text("typedef", _IDENT),
                header=c.text("header", _HEADER),
                returns=c.text("returns"),
                params=_params(c),
                doc=c.text("doc"),
            )
        )
    registrations = [_function(item, where) for item, where in _items(top, "registrations")]
    helpers = [_function(item, where) for item, where in _items(top, "helpers")]
    constants = []
    for item, where in _items(top, "constants"):
        k = _Reader(item, where, ("name", "header", "group", "doc"))
        constants.append(
            Constant(
                k.text("name", _IDENT),
                k.text("header", _HEADER),
                k.text("group", _IDENT),
                k.text("doc"),
            )
        )
    macros = []
    for item, where in _items(top, "macros"):
        m = _Reader(item, where, ("name", "header", "doc"))
        macros.append(Macro(m.text("name", _IDENT), m.text("header", _HEADER), m.text("doc")))
    lg = _Reader(
        top.value["logger"],
        f"{source}.logger",
        ("header", "error", "warn", "info", "debug", "debug_opt_in", "doc"),
    )
    logger = Logger(
        header=lg.text("header", _HEADER),
        error=lg.text("error", _IDENT),
        warn=lg.text("warn", _IDENT),
        info=lg.text("info", _IDENT),
        debug=lg.text("debug", _IDENT),
        debug_opt_in=lg.text("debug_opt_in", _IDENT),
        doc=lg.text("doc"),
    )
    cp = _Reader(
        top.value["class_provider"],
        f"{source}.class_provider",
        ("header", "struct", "register", "unknown", "doc"),
    )
    class_provider = ClassProvider(
        header=cp.text("header", _HEADER),
        struct=cp.text("struct", _IDENT),
        register=cp.text("register", _IDENT),
        unknown=cp.text("unknown", _IDENT),
        doc=cp.text("doc"),
    )
    pa = _Reader(
        top.value["parents"],
        f"{source}.parents",
        ("header", "declared_in", "id_macro", "examples", "doc"),
    )
    examples = []
    for i, ex in enumerate(pa.array("examples")):
        if not isinstance(ex, str) or not _IDENT.match(ex):
            raise ProfileError(f"{source}.parents.examples[{i}]: expected a C identifier")
        examples.append(ex)
    id_macro = pa.text("id_macro")
    if "{LABEL}" not in id_macro or not _IDENT.match(id_macro.replace("{LABEL}", "X")):
        raise ProfileError(f"{source}.parents.id_macro: {id_macro!r} needs one {{LABEL}}")
    parents = Parents(
        header=pa.text("header", _HEADER),
        declared_in=pa.text("declared_in", _HEADER),
        id_macro=id_macro,
        examples=tuple(examples),
        doc=pa.text("doc"),
    )
    version = top.text("profile", _VERSION)
    profile = Profile(
        version=version,
        sdk=top.text("sdk"),
        c_std=top.text("c_std"),
        headers=tuple(headers),
        types=tuple(types),
        structs=tuple(structs),
        callbacks=tuple(callbacks),
        registrations=tuple(registrations),
        helpers=tuple(helpers),
        constants=tuple(constants),
        macros=tuple(macros),
        logger=logger,
        class_provider=class_provider,
        parents=parents,
    )
    _check_references(profile, source)
    return profile


def _unique(names: Sequence[str], what: str, source: str) -> None:
    seen: set[str] = set()
    for name in names:
        if name in seen:
            raise ProfileError(f"{source}: {what} {name!r} is listed twice")
        seen.add(name)


def _check_references(p: Profile, source: str) -> None:
    """The cross-references the schema cannot express."""
    header_names = [h.name for h in p.headers]
    _unique(header_names, "header", source)
    functions = [*p.registrations, *p.helpers]
    symbols = [
        *(t.name for t in p.types),
        *(s.name for s in p.structs),
        *(c.typedef for c in p.callbacks),
        *(f.name for f in functions),
        *(c.name for c in p.constants),
        *(m.name for m in p.macros),
    ]
    _unique(symbols, "symbol", source)
    _unique([c.role for c in p.callbacks], "callback role", source)
    for struct in p.structs:
        _unique([f.name for f in struct.fields], f"field of {struct.name}", source)
    known = set(header_names)
    entries: list[tuple[str, str]] = [
        *((t.name, t.header) for t in p.types),
        *((s.name, s.header) for s in p.structs),
        *((c.typedef, c.header) for c in p.callbacks),
        *((f.name, f.header) for f in functions),
        *((c.name, c.header) for c in p.constants),
        *((m.name, m.header) for m in p.macros),
        ("logger", p.logger.header),
        ("class_provider", p.class_provider.header),
        ("parents", p.parents.header),
    ]
    for name, header in entries:
        if header not in known:
            raise ProfileError(f"{source}: {name}: header {header!r} is not in headers")
    roles = {c.role for c in p.callbacks}
    for fn in functions:
        if fn.implements is not None and fn.implements not in roles:
            raise ProfileError(
                f"{source}: {fn.name}: implements {fn.implements!r}, which is not a callback role"
            )
    macros = {m.name: m.header for m in p.macros}
    lg = p.logger
    for level, name in (
        ("error", lg.error),
        ("warn", lg.warn),
        ("info", lg.info),
        ("debug", lg.debug),
    ):
        if macros.get(name) != lg.header:
            raise ProfileError(f"{source}.logger.{level}: {name!r} is not a macro of {lg.header}")
    cp = p.class_provider
    refs = (
        ("struct", cp.struct, {s.name: s.header for s in p.structs}),
        ("register", cp.register, {f.name: f.header for f in p.registrations}),
        ("unknown", cp.unknown, {c.name: c.header for c in p.constants}),
    )
    for key, name, table in refs:
        if table.get(name) != cp.header:
            raise ProfileError(
                f"{source}.class_provider.{key}: {name!r} is not declared in {cp.header}"
            )


def load_profile(path: str | Path) -> Profile:
    """Read and parse a profile file; ``ProfileError`` if it is not valid."""
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ProfileError(f"{path}: {exc.strerror or exc}") from exc
    return _parse_text(text, str(path))


def _parse_text(text: str, source: str) -> Profile:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ProfileError(f"{source}: not JSON: {exc}") from exc
    return parse_profile(data, source)


@cache
def _bundled() -> Mapping[str, Profile]:
    folder = resources.files("mmt_plugin").joinpath(PROFILES_RESOURCE)
    found: dict[str, Profile] = {}
    for entry in folder.iterdir():
        if not entry.name.endswith(".json"):
            continue
        profile = _parse_text(
            entry.read_text(encoding="utf-8"), f"{PROFILES_RESOURCE}/{entry.name}"
        )
        if entry.name != f"{profile.version}.json":
            raise ProfileError(
                f"{PROFILES_RESOURCE}/{entry.name}: holds profile {profile.version}"
            )
        found[profile.version] = profile
    return {v: found[v] for v in sorted(found, key=version_key)}


def bundled_versions() -> list[str]:
    """The versions of the bundled profiles, oldest first."""
    return list(_bundled())


def get_bundled(version: str) -> Profile | None:
    """The bundled profile of exactly this version, or ``None``."""
    return _bundled().get(version)


def load_schema() -> dict[str, Any]:
    """Return the profile's JSON Schema, as shipped in the package."""
    path = resources.files("mmt_plugin").joinpath(SCHEMA_RESOURCE)
    schema: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return schema
