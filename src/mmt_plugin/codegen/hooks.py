"""Missing hooks (plan T2.2, decision 3): which hooks of the generated
header the compiled user code does not define.

``generate`` never writes under ``src/``, so a model change that adds a hook
leaves ``src/<label>_impl.c`` without it. The build (``mmt-plugin build``,
#19) compiles the user code, then calls ``missing_hooks(hooks, objects)``
before it links: every hook must be a global function symbol defined by one
of the user objects. ``missing_hook_error`` turns what is missing into
``build.missing-hook`` (exit 5), one diagnostic per hook that names it, its
declaration and the file to define it in.

The symbols are read from the objects' ELF symbol tables (32 or 64 bits,
either byte order) with the standard library, so the check needs no ``nm``
and does not depend on how the linker words an undefined reference.
"""

from __future__ import annotations

import struct
from collections.abc import Iterable, Sequence
from pathlib import Path

from mmt_plugin.codegen.cgen import Hook
from mmt_plugin.diagnostics import CliError, Diagnostic, Location, Severity

__all__ = [
    "MISSING_HOOK",
    "ObjectFormatError",
    "defined_functions",
    "missing_hook_error",
    "missing_hooks",
]

#: The code of a hook the user code does not define (class ``build``, exit 5).
MISSING_HOOK = "build.missing-hook"

_SHT_SYMTAB = 2
_STT_FUNC = 2
_STB_GLOBAL = 1
_STB_WEAK = 2
_SHN_UNDEF = 0
#: The longest symbol name read; no hook name comes close.
_MAX_NAME = 4096


class ObjectFormatError(ValueError):
    """A file that is not an ELF object, or whose symbol table is cut short."""


def _unpack(fmt: str, data: bytes, offset: int, path: Path) -> tuple[int, ...]:
    # Checked here, not left to struct: an offset past 2**63 (from a 64-bit
    # field) makes unpack_from raise OverflowError instead of struct.error.
    if offset + struct.calcsize(fmt) > len(data):
        raise ObjectFormatError(f"{path}: truncated ELF file")
    try:
        return struct.unpack_from(fmt, data, offset)
    except struct.error:
        raise ObjectFormatError(f"{path}: truncated ELF file") from None


def defined_functions(path: Path) -> frozenset[str]:
    """The global (or weak) function symbols that the ELF object ``path``
    defines. Raises ``ObjectFormatError`` when it is not an ELF file."""
    data = path.read_bytes()
    if data[:4] != b"\x7fELF" or len(data) < 6 or data[4] not in (1, 2) or data[5] not in (1, 2):
        raise ObjectFormatError(f"{path}: not an ELF object")
    wide = data[4] == 2
    order = "<" if data[5] == 1 else ">"
    if wide:
        (shoff,) = _unpack(order + "Q", data, 0x28, path)
        shentsize, shnum = _unpack(order + "HH", data, 0x3A, path)
        section = order + "IIQQQQIIQQ"
        symbol = order + "IBBHQQ"
    else:
        (shoff,) = _unpack(order + "I", data, 0x20, path)
        shentsize, shnum = _unpack(order + "HH", data, 0x2E, path)
        section = order + "IIIIIIIIII"
        symbol = order + "IIIBBH"
    if shoff == 0:
        return frozenset()
    if shentsize != struct.calcsize(section):
        raise ObjectFormatError(f"{path}: unexpected ELF section header size {shentsize}")
    if shnum == 0:
        # Extended numbering: the count is section 0's sh_size.
        shnum = _unpack(section, data, shoff, path)[5]
    headers = [_unpack(section, data, shoff + i * shentsize, path) for i in range(shnum)]
    names: set[str] = set()
    seen_symtab = False
    for _, sh_type, _, _, sh_offset, sh_size, sh_link, _, _, sh_entsize in headers:
        if sh_type != _SHT_SYMTAB:
            continue
        # The gABI allows one symbol table per object; walking many that
        # share one region would take time quadratic in the file size.
        if seen_symtab:
            raise ObjectFormatError(f"{path}: more than one ELF symbol table")
        seen_symtab = True
        if sh_link >= len(headers) or sh_entsize != struct.calcsize(symbol):
            raise ObjectFormatError(f"{path}: malformed ELF symbol table")
        str_offset, str_size = headers[sh_link][4], headers[sh_link][5]
        strings = data[str_offset : str_offset + str_size]
        for i in range(sh_size // sh_entsize):
            fields = _unpack(symbol, data, sh_offset + i * sh_entsize, path)
            if wide:
                name, info, _, shndx = fields[0], fields[1], fields[2], fields[3]
            else:
                name, info, shndx = fields[0], fields[3], fields[5]
            if shndx == _SHN_UNDEF or info & 0xF != _STT_FUNC:
                continue
            if info >> 4 not in (_STB_GLOBAL, _STB_WEAK):
                continue
            # Bounded, so crafted input with many symbols in one unterminated
            # run costs linear time; such a name cannot be a hook: skip it.
            end = strings.find(b"\0", name, name + _MAX_NAME + 1)
            if end < 0:
                continue
            names.add(strings[name:end].decode("ascii", "replace"))
    return frozenset(names)


def missing_hooks(hooks: Sequence[Hook], objects: Iterable[Path]) -> tuple[Hook, ...]:
    """The hooks, in header order, that none of the user ``objects``
    defines as a global function."""
    defined: set[str] = set()
    for obj in objects:
        defined |= defined_functions(obj)
    return tuple(h for h in hooks if h.name not in defined)


def missing_hook_error(
    missing: Sequence[Hook], impl: str, header: str
) -> tuple[CliError, list[Diagnostic]]:
    """``build.missing-hook`` for the ``missing`` hooks (not empty): the
    error, and one diagnostic per hook located at ``impl`` (the user file,
    ``src/<label>_impl.c``); ``header`` is the generated header, as shown."""
    if not missing:
        raise ValueError("no missing hook")
    diagnostics = [
        Diagnostic(
            Severity.ERROR,
            MISSING_HOOK,
            f"hook {h.name} is not defined",
            hint=f"define {h.declaration} in {impl}; {header} declares it",
            location=Location(impl),
        )
        for h in missing
    ]
    names = ", ".join(h.name for h in missing)
    count = "1 hook is" if len(missing) == 1 else f"{len(missing)} hooks are"
    error = CliError(
        MISSING_HOOK,
        f"{count} not defined: {names}",
        f"add {'it' if len(missing) == 1 else 'them'} to {impl}, as {header} declares"
        f" {'it' if len(missing) == 1 else 'them'}",
    )
    return error, diagnostics
