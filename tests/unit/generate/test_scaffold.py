"""Generated vs user code (plan T2.2, #18): the hooks the generated header
declares, ``<label>_hook_register_parents``, the scaffold
``src/<label>_impl.c`` (``mmt_plugin.codegen.scaffold``), regeneration next
to an edited scaffold, and the missing-hook check
(``mmt_plugin.codegen.hooks``).

The tests that compile the scaffold against a real mmt-dpi, build it into a
plugin and classify a packet through its parent are in ``test_compile.py``;
the ones here need no SDK (the symbol-table tests need a C compiler, ``cc``
or ``MMT_GOLDEN_CC``, and skip without one).
"""

from __future__ import annotations

import json
import os
import re
import shutil
import struct
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest

from mmt_plugin.cli import main
from mmt_plugin.codegen import REGISTER_PARENTS, Hook, scaffold
from mmt_plugin.codegen.hooks import (
    MISSING_HOOK,
    ObjectFormatError,
    defined_functions,
    missing_hook_error,
    missing_hooks,
)
from mmt_plugin.commands.generate import GenerateCommand
from mmt_plugin.exitcodes import ExitCode
from mmt_plugin.fsio import sha256_file
from mmt_plugin.sdk.profile import Param

from .helpers import generate_text, profile, run_model
from .test_golden import ACCEPTED

# --- the header and the init -------------------------------------------------


@pytest.mark.parametrize("name", ACCEPTED)
def test_every_header_declares_the_register_parents_hook(name: str) -> None:
    generation = run_model(name).generation
    assert generation is not None
    lc = generation.label.lower()
    parents = [h for h in generation.hooks if h.role == REGISTER_PARENTS]
    assert [h.name for h in parents] == [f"{lc}_hook_register_parents"]
    # The signature is the profile's: init_proto's return type, protocol_t.
    p = profile()
    assert parents[0].returns == p.callback("init_proto").returns
    assert [(q.name, q.type) for q in parents[0].params] == [("protocol_struct", "protocol_t *")]
    header = generation.file(generation.header).text
    assert f"\nint {lc}_hook_register_parents(protocol_t *protocol_struct);\n" in header


@pytest.mark.parametrize("name", ACCEPTED)
def test_init_calls_the_parents_hook_after_registering_and_fails_on_0(name: str) -> None:
    generation = run_model(name).generation
    assert generation is not None
    lc = generation.label.lower()
    source = generation.file(f"{lc}_mmt_plugin.c").text
    body = source.split(f"\nint init_{lc}_proto_struct(void)\n{{\n", 1)[1].split("\n}\n", 1)[0]
    registered = body.index("if (!register_protocol(protocol_struct, ")
    called = body.index(f"    if (!{lc}_hook_register_parents(protocol_struct)) {{\n")
    assert registered < called
    tail = body[called:]
    assert tail.split("\n")[1:4] == [
        f'        mmt_log_error("init_{lc}_proto_struct: {lc}_hook_register_parents() failed");',
        "        return 0;",
        "    }",
    ]
    assert tail.rstrip().endswith("return 1;")


# --- the scaffold --------------------------------------------------------------


def _definitions(text: str) -> list[str]:
    """The function definitions of a scaffold, by name, in order."""
    return re.findall(r"^[^/\s][^\n]*?\b(\w+)\([^;{\n]*\)\n\{$", text, re.M)


@pytest.mark.parametrize("name", ACCEPTED)
def test_the_scaffold_defines_every_hook_of_the_header(name: str) -> None:
    generation = run_model(name).generation
    assert generation is not None
    found = scaffold(generation, profile())
    assert found.path == f"src/{generation.label.lower()}_impl.c"
    assert f'#include "{generation.header}"' in found.text
    assert _definitions(found.text) == [h.name for h in generation.hooks]
    for h in generation.hooks:
        assert f"\n{h.declaration}\n{{\n" in found.text, h.name
    found.data.decode("ascii")
    assert scaffold(generation, profile()) == found


def test_each_stub_returns_nothing_but_lets_the_plugin_load() -> None:
    generation = run_model("pdl_properties_all").generation
    assert generation is not None
    text = scaffold(generation, profile()).text
    returns = {}
    for h in generation.hooks:
        body = text.split(f"\n{h.declaration}\n{{\n", 1)[1].split("\n}\n", 1)[0]
        values = re.findall(r"^    return (.+);$", body, re.M)
        returns[h.role] = values[0] if values else None
        for p in h.params:
            assert f"    (void){p.name};" in body, (h.name, p.name)
    assert returns == {
        "proto_context_init": "NULL",
        "proto_context_cleanup": None,
        "session_data_init": None,
        "session_data_cleanup": None,
        "session_data_analysis": "0",
        "sessionizer": "NULL",
        "session_context_cleanup": "0",
        "session_key_comparison": "false",
        "classification": "MMT_CLASSIFY_SKIP",
        REGISTER_PARENTS: "1",
    }


def test_an_extraction_hook_stub_extracts_nothing() -> None:
    generation = run_model("pdl_scopes").generation
    assert generation is not None
    text = scaffold(generation, profile()).text
    hook = next(h for h in generation.hooks if h.attribute == "no_off")
    body = text.split(f"\n{hook.declaration}\n{{\n", 1)[1].split("\n}\n", 1)[0]
    assert body.splitlines()[-1] == "    return 0;"


def test_the_parents_example_states_the_load_order_and_the_weight() -> None:
    generation = run_model("ndn").generation
    assert generation is not None
    text = scaffold(generation, profile()).text
    body = text.split("\nint ndn_example_hook_register_parents(", 1)[1]
    flat = " ".join(line.strip(" *") for line in body.splitlines())
    assert "register_classification_function_with_parent_protocol(PROTO_ETHERNET," in flat
    assert '"tcpip/mmt_tcpip.h"' in flat
    assert "mmtp_ndn_example.so after libmmt_tcpip.so" in flat
    assert "0 to 9 and 90 to 100" in flat and "weight of 50" in flat
    assert "next.proto_id = PROTO_NDN_EXAMPLE;" in flat


def test_a_stub_for_an_unknown_return_type_is_an_error() -> None:
    generation = run_model("pdl_scopes").generation
    assert generation is not None
    odd = Hook("x_hook_odd", "odd", "struct odd", (), "An odd hook.")
    with pytest.raises(ValueError, match="x_hook_odd"):
        scaffold(replace(generation, hooks=(odd,)), profile())


# --- regeneration never touches src/ --------------------------------------------

BASE = """Protocol {
	Properties {
		label = "regen"
		id = "961"
		encoding = "network"
	}
	Attributes {
		attribute {
			alias="kind" data_type="MMT_U8_DATA" data_len="1" offset="0" scope="SCOPE_PACKET"
		}
%s	}
}
"""

PROFILE = ("--sdk-profile", "1.10.2")

#: An attribute without an offset: a new extraction hook.
NEW_HOOK = """		attribute {
			alias="extra" data_type="MMT_U8_DATA" data_len="1" scope="SCOPE_PACKET"
		}
"""


def _generate(project: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> int:
    command = GenerateCommand(pkg_config_dirs=[], default_prefix=str(tmp_path / "no-sdk"))
    code = main(
        ["--json", "-C", str(project), "generate", str(project / "model.pdl"), *PROFILE],
        commands=[command],
    )
    doc = json.loads(capsys.readouterr().out)
    assert doc["exit_code"] == code
    return code


def test_regenerating_after_editing_the_scaffold_leaves_src_alone(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("MMT_PLUGIN_SDK_PROFILE", raising=False)
    project = tmp_path / "project"
    project.mkdir()
    (project / "model.pdl").write_text(BASE % "")
    assert _generate(project, tmp_path, capsys) == 0
    generation = generate_text(BASE % "")
    impl = project / scaffold(generation, profile()).path
    impl.parent.mkdir()
    edited = scaffold(generation, profile()).text.replace(
        "    return 1;\n}", "    /* my parents */\n    return 1;\n}"
    )
    impl.write_text(edited)
    before = (sha256_file(impl), impl.stat().st_mtime_ns)
    # The model gains a hook: generate rewrites generated/, never src/.
    (project / "model.pdl").write_text(BASE % NEW_HOOK)
    assert _generate(project, tmp_path, capsys) == 0
    assert (sha256_file(impl), impl.stat().st_mtime_ns) == before
    assert sorted(p.name for p in (project / "src").iterdir()) == ["regen_impl.c"]
    header = (project / "generated" / "regen_mmt_plugin.h").read_text()
    assert "int regen_hook_extract_extra(" in header
    assert "regen_hook_extract_extra" not in impl.read_text()
    # A re-run with nothing changed writes nothing either.
    assert _generate(project, tmp_path, capsys) == 0
    assert (sha256_file(impl), impl.stat().st_mtime_ns) == before


# --- the missing-hook check -------------------------------------------------------


def _hook(name: str) -> Hook:
    return Hook(name, "attribute_extraction", "int", (Param("p", "int"),), "doc")


def test_the_missing_hook_error_names_each_hook_and_the_file() -> None:
    hooks = (_hook("x_hook_extract_a"), _hook("x_hook_register_parents"))
    error, diagnostics = missing_hook_error(hooks, "src/x_impl.c", "generated/x_mmt_plugin.h")
    assert error.code == MISSING_HOOK
    assert error.exit_code is ExitCode.BUILD
    assert int(error.exit_code) == 5
    assert error.message == "2 hooks are not defined: x_hook_extract_a, x_hook_register_parents"
    assert error.hint == "add them to src/x_impl.c, as generated/x_mmt_plugin.h declares them"
    assert [(d.code, d.message, d.location.file if d.location else None) for d in diagnostics] == [
        (MISSING_HOOK, "hook x_hook_extract_a is not defined", "src/x_impl.c"),
        (MISSING_HOOK, "hook x_hook_register_parents is not defined", "src/x_impl.c"),
    ]
    assert diagnostics[0].hint == (
        "define int x_hook_extract_a(int p) in src/x_impl.c; generated/x_mmt_plugin.h declares it"
    )
    one, _ = missing_hook_error(hooks[:1], "src/x_impl.c", "x_mmt_plugin.h")
    assert one.message == "1 hook is not defined: x_hook_extract_a"
    assert one.hint == "add it to src/x_impl.c, as x_mmt_plugin.h declares it"
    with pytest.raises(ValueError):
        missing_hook_error((), "src/x_impl.c", "x_mmt_plugin.h")


def test_a_file_that_is_not_elf_is_an_error(tmp_path: Path) -> None:
    for data in (b"", b"\x7fEL", b"MZ\x90\x00", b"\x7fELF\x03\x01" + bytes(64)):
        path = tmp_path / "x.o"
        path.write_bytes(data)
        with pytest.raises(ObjectFormatError):
            defined_functions(path)


def test_a_truncated_elf_file_is_an_error(tmp_path: Path) -> None:
    # A 64-bit little-endian header whose section table lies past the end.
    header = bytearray(64)
    header[:6] = b"\x7fELF\x02\x01"
    struct.pack_into("<Q", header, 0x28, 4096)
    struct.pack_into("<HH", header, 0x3A, 64, 3)
    path = tmp_path / "x.o"
    path.write_bytes(bytes(header))
    with pytest.raises(ObjectFormatError, match="truncated"):
        defined_functions(path)


@pytest.mark.parametrize("shoff", [2**63, 2**64 - 1])
def test_a_section_table_offset_past_any_file_is_an_error(tmp_path: Path, shoff: int) -> None:
    # struct.unpack_from raises OverflowError, not struct.error, at these.
    header = bytearray(64)
    header[:6] = b"\x7fELF\x02\x01"
    struct.pack_into("<Q", header, 0x28, shoff)
    struct.pack_into("<HH", header, 0x3A, 64, 3)
    path = tmp_path / "x.o"
    path.write_bytes(bytes(header))
    with pytest.raises(ObjectFormatError, match="truncated"):
        defined_functions(path)


# (name, binding, type, section index): STB_LOCAL 0, GLOBAL 1, WEAK 2;
# STT_OBJECT 1, FUNC 2; section 0 is undefined, 1 any defined section.
ELF_SYMBOLS = [
    ("global_fn", 1, 2, 1),
    ("weak_fn", 2, 2, 1),
    ("local_fn", 0, 2, 1),
    ("undefined_fn", 1, 2, 0),
    ("data_obj", 1, 1, 1),
]


def _elf(wide: bool, order: str, symtabs: int = 1) -> bytes:
    """A minimal relocatable ELF object: a null section, ``symtabs``
    SHT_SYMTAB sections (all over the same symbols) and a .strtab."""
    strtab = b"\0" + b"".join(n.encode() + b"\0" for n, _, _, _ in ELF_SYMBOLS)
    symbols = [(0, 0, 0)]  # the null symbol
    for name, bind, kind, shndx in ELF_SYMBOLS:
        symbols.append((strtab.index(name.encode() + b"\0"), bind << 4 | kind, shndx))
    if wide:
        ehsize, shoff_at, shnum_at = 64, 0x28, 0x3A
        sym = [struct.pack(order + "IBBHQQ", n, i, 0, x, 0, 0) for n, i, x in symbols]
        section = order + "IIQQQQIIQQ"
    else:
        ehsize, shoff_at, shnum_at = 52, 0x20, 0x2E
        sym = [struct.pack(order + "IIIBBH", n, 0, 0, i, 0, x) for n, i, x in symbols]
        section = order + "IIIIIIIIII"
    symtab = b"".join(sym)
    sym_at, str_at = ehsize, ehsize + len(symtab)
    shoff = str_at + len(strtab)
    strtab_index = 1 + symtabs
    headers = [struct.pack(section, *[0] * 10)]
    headers += [
        struct.pack(section, 0, 2, 0, 0, sym_at, len(symtab), strtab_index, 1, 8, len(sym[0]))
    ] * symtabs
    headers.append(struct.pack(section, 0, 3, 0, 0, str_at, len(strtab), 0, 0, 1, 0))
    header = bytearray(ehsize)
    header[:6] = b"\x7fELF" + bytes([2 if wide else 1, 1 if order == "<" else 2])
    struct.pack_into(order + ("Q" if wide else "I"), header, shoff_at, shoff)
    struct.pack_into(order + "HH", header, shnum_at, len(headers[0]), len(headers))
    return bytes(header) + symtab + strtab + b"".join(headers)


@pytest.mark.parametrize("wide", [False, True], ids=["elf32", "elf64"])
@pytest.mark.parametrize("order", ["<", ">"], ids=["lsb", "msb"])
def test_defined_functions_reads_either_class_and_byte_order(
    tmp_path: Path, wide: bool, order: str
) -> None:
    path = tmp_path / "x.o"
    path.write_bytes(_elf(wide, order))
    assert defined_functions(path) == {"global_fn", "weak_fn"}


def test_more_than_one_symbol_table_is_an_error(tmp_path: Path) -> None:
    path = tmp_path / "x.o"
    path.write_bytes(_elf(True, "<", symtabs=2))
    with pytest.raises(ObjectFormatError, match="more than one ELF symbol table"):
        defined_functions(path)


def _cc() -> str:
    cc = os.environ.get("MMT_GOLDEN_CC") or "cc"
    if shutil.which(cc) is None:
        pytest.skip(f"{cc} is not installed")
    return cc


SYMBOLS = """
int defined_hook(int p) { return p; }
int __attribute__((weak)) weak_hook(int p) { return p; }
static int static_hook(int p) { return p; }
int called_but_undefined(int p);
int data_symbol = 3;
int uses(int p) { return static_hook(p) + called_but_undefined(p); }
"""


@pytest.mark.parametrize("flags", [(), ("-m32",)])
def test_defined_functions_reads_the_global_function_symbols(
    tmp_path: Path, flags: tuple[str, ...]
) -> None:
    source = tmp_path / "symbols.c"
    source.write_text(SYMBOLS)
    obj = tmp_path / "symbols.o"
    proc = subprocess.run(
        [_cc(), *flags, "-c", str(source), "-o", str(obj)],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0 and flags:
        pytest.skip(f"no {' '.join(flags)} support: {proc.stderr.strip()}")
    assert proc.returncode == 0, proc.stderr
    found = defined_functions(obj)
    assert {"defined_hook", "weak_hook", "uses"} <= found
    assert not found & {"static_hook", "called_but_undefined", "data_symbol"}
    hooks = tuple(_hook(n) for n in ("defined_hook", "static_hook", "weak_hook", "absent"))
    assert [h.name for h in missing_hooks(hooks, [obj])] == ["static_hook", "absent"]
    assert missing_hooks(hooks[:1], [obj]) == ()
