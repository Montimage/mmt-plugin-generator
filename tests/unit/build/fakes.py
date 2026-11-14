"""A fake SDK prefix and a fake compiler for the ``build`` tests that need
no real mmt-dpi (``test_command.py``).

The fake compiler is a Python script that answers like gcc where ``build``
looks: ``--version`` prints one line; ``-c SRC -o OBJ`` writes an ELF
relocatable object whose symbol table defines every function ``SRC``
defines at the start of a line (``mmt_plugin.codegen.hooks`` reads it), and
turns a ``#error`` line into a gcc-style ``SRC:LINE:2: error:`` message (exit
1); a link (``-shared ... -o OUT``) writes ``OUT``. Environment variables
steer it: ``FAKE_CC_LOG`` (append each argv as a JSON line),
``FAKE_CC_LINK_FAIL`` (the link writes half a file, prints a linker error and
exits 1), ``FAKE_CC_SLEEP`` (a path: write the pid there, then sleep).
"""

from __future__ import annotations

import struct
import sys
from collections.abc import Sequence
from pathlib import Path

__all__ = ["elf_object", "fake_cc", "fake_sdk"]


def elf_object(names: Sequence[str]) -> bytes:
    """A 64-bit little-endian ELF object with only a symbol table, which
    defines ``names`` as global functions."""
    strtab = b"\0" + b"".join(n.encode("ascii") + b"\0" for n in names)
    symbols = struct.pack("<IBBHQQ", 0, 0, 0, 0, 0, 0)
    offset = 1
    for name in names:
        symbols += struct.pack("<IBBHQQ", offset, 0x12, 0, 1, 0, 0)  # GLOBAL FUNC
        offset += len(name) + 1
    head = bytearray(64)
    head[0:7] = b"\x7fELF\x02\x01\x01"
    str_offset = len(head)
    sym_offset = str_offset + len(strtab)
    sh_offset = sym_offset + len(symbols)
    sections = struct.pack("<IIQQQQIIQQ", 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
    sections += struct.pack("<IIQQQQIIQQ", 0, 3, 0, 0, str_offset, len(strtab), 0, 0, 1, 0)
    sections += struct.pack("<IIQQQQIIQQ", 0, 2, 0, 0, sym_offset, len(symbols), 1, 1, 8, 24)
    struct.pack_into("<Q", head, 0x28, sh_offset)
    struct.pack_into("<HH", head, 0x3A, 64, 3)
    return bytes(head) + strtab + symbols + sections


_SCRIPT = r"""#!{python}
import json, os, re, sys, time
sys.path.insert(0, {here!r})
from fakes import elf_object

argv = sys.argv[1:]
if os.environ.get("FAKE_CC_LOG"):
    with open(os.environ["FAKE_CC_LOG"], "a") as log:
        log.write(json.dumps(argv) + "\n")
if argv == ["--version"]:
    print("fakecc (Fake) 1.0")
    print("not a real compiler")
    sys.exit(0)
if os.environ.get("FAKE_CC_SLEEP"):
    with open(os.environ["FAKE_CC_SLEEP"], "w") as f:
        f.write(str(os.getpid()))
    time.sleep(60)
out = argv[argv.index("-o") + 1]
if "-c" in argv:
    src = argv[argv.index("-c") + 1]
    names, failed = [], False
    with open(src) as f:
        for n, line in enumerate(f, 1):
            if line.startswith("#error"):
                print(f"{{src}}:{{n}}:2: error: {{line[1:].strip()}}", file=sys.stderr)
                failed = True
            elif line.startswith("#warning"):
                print(f"{{src}}:{{n}}:2: warning: {{line[1:].strip()}}", file=sys.stderr)
            m = re.match(r"^[A-Za-z_][^;(=]*?\b([A-Za-z_]\w*)\s*\([^;]*$", line)
            if m and not line.startswith(("static", "typedef", "struct", "enum")):
                names.append(m.group(1))
    if failed:
        sys.exit(1)
    with open(out, "wb") as f:
        f.write(elf_object(names))
    sys.exit(0)
if os.environ.get("FAKE_CC_LINK_FAIL"):
    with open(out, "wb") as f:
        f.write(b"half")
    print("/usr/bin/ld: x.o: in function `f':", file=sys.stderr)
    print("x.c:(.text+0x5): undefined reference to `nope'", file=sys.stderr)
    print("collect2: error: ld returned 1 exit status", file=sys.stderr)
    sys.exit(1)
with open(out, "wb") as f:
    f.write(b"fake shared object\n" + " ".join(argv).encode())
"""


def fake_cc(directory: Path) -> Path:
    """Write the fake compiler into ``directory``; return its path."""
    directory.mkdir(parents=True, exist_ok=True)
    cc = directory / "fakecc"
    here = str(Path(__file__).parent)
    cc.write_text(_SCRIPT.format(python=sys.executable, here=here))
    cc.chmod(0o755)
    return cc


def fake_sdk(root: Path, *, version: str = "1.10.2", core: bool = True) -> Path:
    """A fake SDK prefix: the marker header, ``mmt_core.h`` with ``VERSION``
    and, unless ``core`` is false, a ``libmmt_core.so.<version>`` file."""
    include = root / "dpi" / "include"
    include.mkdir(parents=True, exist_ok=True)
    (include / "mmt_log.h").write_text("/* fake */\n")
    (include / "mmt_core.h").write_text(f'#define VERSION "{version}"\n')
    lib = root / "dpi" / "lib"
    lib.mkdir(parents=True, exist_ok=True)
    if core:
        (lib / f"libmmt_core.so.{version}").write_bytes(b"fake core\n")
    return root
