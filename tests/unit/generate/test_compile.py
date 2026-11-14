"""Compile, build and load the generated C of every corpus model against a
real mmt-dpi SDK (plan T1.7).

Every corpus model that ``generate`` accepts (``ACCEPTED``; the others
produce no output) is generated with the bundled profile of the SDK's own
version, then, with the SDK's headers and ``libmmt_core``:

- each generated source and the scaffold ``src/<label>_impl.c``
  (``mmt_plugin.codegen.scaffold``), which defines the header's hooks,
  compile ``-fsyntax-only -std=gnu11 -Wall -Wextra -Werror`` (``c_std`` of
  the SDK profile);
- the pair, linked into a program, registers every attribute
  (``init_<label>_proto_struct()`` returns 1;
  ``register_attribute_with_protocol()`` refuses a ``data_len`` the type's
  SDK size does not allow);
- the pair builds into a plugin (``-O2 -fPIC -shared -Wall -Wextra -Werror
  -Wl,-z,defs``) that ``init_extraction()`` loads from
  ``MMT_DPI_PLUGINS_DIR`` next to the SDK's ``libmmt_tcpip.so``, after which
  the protocol and each attribute resolve to their own id and name.

Another program checks the profile's data type sizes against
``get_data_size_by_data_type()``.

Generated vs user code (T2.2): a hook that a model change adds is missing
from the compiled scaffold (``mmt_plugin.codegen.hooks``) and fails the link,
and the scaffold's commented Ethernet example, filled in, classifies a corpus
packet into the plugin's protocol.

The SDK is an extracted mmt-dpi package, a private prefix (never
``/opt/mmt``)::

    deb="$(bash tests/fetch_mmt_dpi_package.sh <download dir>)"
    dpkg-deb -x "$deb" <dir>
    export MMT_GOLDEN_SDK=<dir>/opt/mmt MMT_GOLDEN_CC=clang
    uv run pytest tests/unit/generate/test_compile.py

Without ``MMT_GOLDEN_SDK`` the tests skip, unless
``MMT_REQUIRE_GOLDEN_COMPILE=1`` (CI's "Generated code" matrix job, run with
gcc and clang against the oldest and newest supported mmt-dpi) makes them
fail instead. ``MMT_GOLDEN_CC`` picks the compiler (default gcc).
"""

from __future__ import annotations

import importlib.util
import itertools
import locale
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from mmt_plugin.codegen import REGISTER_PARENTS, GeneratedFile, Generation, scaffold
from mmt_plugin.codegen.hooks import missing_hook_error, missing_hooks
from mmt_plugin.sdk.detect import read_version

from .helpers import CORPUS, generate_text, impl_stub, profile, run_model
from .test_golden import ACCEPTED
from .test_scaffold import BASE, NEW_HOOK

SDK_ENV = "MMT_GOLDEN_SDK"
CC_ENV = "MMT_GOLDEN_CC"
REQUIRE_ENV = "MMT_REQUIRE_GOLDEN_COMPILE"

#: The SDK plugin the generated plugins load next to; mmt-dpi loads
#: plugins in file name order, so theirs must sort after it.
TCPIP = "libmmt_tcpip.so"


def _sdk_prefix() -> Path:
    prefix = os.environ.get(SDK_ENV, "")
    if not prefix:
        if os.environ.get(REQUIRE_ENV) == "1":
            pytest.fail(f"{REQUIRE_ENV}=1 but {SDK_ENV} is not set")
        pytest.skip(f"{SDK_ENV} is not set (an extracted mmt-dpi prefix)")
    return Path(prefix)


def _include_dir() -> Path:
    include = _sdk_prefix() / "dpi" / "include"
    assert (include / "plugin_defs.h").is_file(), f"{include} has no plugin_defs.h"
    return include


def _sdk_version() -> str:
    """The SDK's version; it must have a bundled profile, which generates
    the code compiled here."""
    version = read_version(str(_sdk_prefix()))
    assert version is not None, f"{_sdk_prefix()} has no VERSION in mmt_core.h"
    profile(version)
    return version


def _compiler() -> str:
    cc = os.environ.get(CC_ENV, "gcc")
    if shutil.which(cc) is None:
        if os.environ.get(REQUIRE_ENV) == "1":
            pytest.fail(f"{cc} is not installed")
        pytest.skip(f"{cc} is not installed")
    return cc


def _core_library(tmp_path: Path) -> tuple[Path, Path]:
    """The SDK's ``libmmt_core`` shared object, and a directory where its
    soname resolves to it (the package's own links are absolute
    ``/opt/mmt`` paths, so they may dangle in an extracted prefix)."""
    lib = _include_dir().parent / "lib"
    found = sorted(p for p in lib.glob("libmmt_core.so.*") if p.is_file() and not p.is_symlink())
    assert found, f"{lib} has no libmmt_core.so.<version>"
    real = found[-1]
    match = re.fullmatch(r"(libmmt_core\.so\.[0-9]+)(\.[0-9]+)*", real.name)
    assert match is not None, real.name
    run_dir = tmp_path / "lib"
    if not run_dir.is_dir():
        run_dir.mkdir()
        (run_dir / match.group(1)).symlink_to(real)
    return real, run_dir


def _write_model(name: str, work: Path) -> tuple[Generation, list[Path]]:
    """Write the generated set of ``name`` (SDK's profile) and a stub impl
    into ``work``; return the generation and its C sources."""
    generation = run_model(name, _sdk_version()).generation
    assert generation is not None, f"{name} does not generate with {_sdk_version()}"
    work.mkdir(parents=True)
    for f in generation.files:
        (work / f.name).write_text(f.text)
    impl = work / f"{generation.label.lower()}_impl.c"
    impl.write_text(impl_stub(generation))
    return generation, [work / f.name for f in generation.files if f.name.endswith(".c")] + [impl]


def _header(generation: Generation) -> GeneratedFile:
    return next(f for f in generation.files if f.name.endswith(".h"))


def _build_program(
    source: Path, tmp_path: Path, *extra: Path, flags: tuple[str, ...] = ()
) -> Path:
    """Build ``source`` (and ``extra``) against the SDK headers and
    ``libmmt_core``; return the program."""
    include, cc = _include_dir(), _compiler()
    core, run_dir = _core_library(tmp_path)
    program = source.with_suffix("")
    proc = subprocess.run(
        [
            cc,
            f"-std={profile(_sdk_version()).c_std}",
            *flags,
            "-I",
            str(source.parent),
            "-I",
            str(include),
            str(source),
            *map(str, extra),
            str(core),
            f"-Wl,-rpath,{run_dir}",
            "-o",
            str(program),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, f"{cc} {source.name}:\n{proc.stderr}"
    return program


def _run(
    program: Path, cwd: Path, plugins: Path | None = None
) -> subprocess.CompletedProcess[str]:
    """Run ``program`` in ``cwd``; with ``plugins``, ``init_extraction()``
    loads the plugins of that directory (``MMT_DPI_PLUGINS_DIR``)."""
    env = dict(os.environ)
    env.pop("MMT_DPI_PLUGINS_DIR", None)
    if plugins is not None:
        env["MMT_DPI_PLUGINS_DIR"] = str(plugins)
    return subprocess.run(
        [str(program)], capture_output=True, text=True, check=False, cwd=cwd, env=env, timeout=60
    )


def _run_program(source: Path, tmp_path: Path, *extra: Path) -> str:
    """Build ``source`` (and ``extra``), run it in ``tmp_path`` and return
    its stdout."""
    # In tmp_path: init_extraction() also loads the plugins of ./plugins.
    run = _run(_build_program(source, tmp_path, *extra), tmp_path)
    assert run.returncode == 0, f"{source.name} exited {run.returncode}:\n{run.stderr}"
    return run.stdout


def test_the_profile_data_sizes_are_the_sdk_ones(tmp_path: Path) -> None:
    # Review of #14: the generator keeps data_len within these sizes, and
    # register_attribute_with_protocol() checks it against the same function.
    types = [c for c in profile(_sdk_version()).constants if c.size is not None]
    lines = [
        f'    printf("%s %u\\n", "{c.name}", (unsigned)get_data_size_by_data_type({c.name}));'
        for c in types
    ]
    source = tmp_path / "sizes.c"
    source.write_text(
        '#include <stdio.h>\n#include "mmt_core.h"\n\nint main(void)\n{\n'
        + "\n".join(lines)
        + "\n    return 0;\n}\n"
    )
    found = dict(line.split() for line in _run_program(source, tmp_path).splitlines())
    assert found == {c.name: str(c.size) for c in types}


@pytest.mark.parametrize("name", ACCEPTED)
def test_the_golden_pair_registers_with_libmmt_core(name: str, tmp_path: Path) -> None:
    generation, sources = _write_model(name, tmp_path / name)
    init = f"init_{generation.label.lower()}_proto_struct"
    main = tmp_path / name / "main.c"
    main.write_text(
        '#include <stdio.h>\n#include "mmt_core.h"\n\n'
        f"int {init}(void);\n\n"
        "int main(void)\n{\n"
        '    if (!init_extraction()) {\n        puts("init_extraction failed");\n'
        "        return 1;\n    }\n"
        f'    printf("%d\\n", {init}());\n'
        "    return 0;\n}\n"
    )
    assert _run_program(main, tmp_path, *sources).strip() == "1", f"{init}() failed"


def _flags() -> list[str]:
    return [
        "-fsyntax-only",
        f"-std={profile(_sdk_version()).c_std}",
        "-Wall",
        "-Wextra",
        "-Werror",
    ]


@pytest.mark.parametrize("name", ACCEPTED)
def test_the_golden_pair_compiles_against_the_sdk_headers(name: str, tmp_path: Path) -> None:
    include = _include_dir()
    cc = _compiler()
    work = tmp_path / name
    _, sources = _write_model(name, work)
    for source in sources:
        proc = subprocess.run(
            [cc, *_flags(), "-I", str(work), "-I", str(include), str(source)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 0, f"{cc} {source.name}:\n{proc.stderr}"
        assert proc.stderr == "", proc.stderr


def test_a_missing_hook_definition_is_a_declared_symbol(tmp_path: Path) -> None:
    # Plan decision 3: the header declares every hook, so user code that
    # lacks one still compiles; mmt_plugin.codegen.hooks finds it in the
    # objects, and the link fails (test_a_model_change_that_adds_a_hook_...).
    generation = run_model("pdl_scopes").generation
    assert generation is not None
    header = generation.file("pdl_scopes_mmt_plugin.h").text
    for hook in generation.hooks:
        assert f"{hook.declaration};" in header


# The load check (T1.7): each generated pair built as a plugin and loaded by
# init_extraction(), as mmt-dpi loads an installed plugin.

#: ``-Wl,-z,defs``: every symbol resolves at link time, so a hook the user
#: code misses, or an SDK function the profile names wrongly, fails the build.
PLUGIN_FLAGS = ("-O2", "-fPIC", "-shared", "-Wall", "-Wextra", "-Werror", "-Wl,-z,defs")
LOADER_FLAGS = ("-Wall", "-Wextra", "-Werror")

_PROTO_MACRO = re.compile(r"^#define (PROTO_\w+) ([0-9]+)$", re.MULTILINE)
_ALIAS_MACRO = re.compile(r'^#define (\w+)_ALIAS "[^"]*"$', re.MULTILINE)
_ATTRIBUTES_NB = re.compile(r"^    (\w+)_ATTRIBUTES_NB = ([0-9]+)$", re.MULTILINE)


def _loader_checks(header: GeneratedFile) -> tuple[str, list[str]]:
    """The protocol id macro of ``header`` and its attribute macros, which
    must be as many as the header's ``<LABEL>_ATTRIBUTES_NB``."""
    protos = _PROTO_MACRO.findall(header.text)
    assert len(protos) == 1, f"{header.name}: protocol id macros {protos}"
    macro = protos[0][0]
    attributes = [m for m in _ALIAS_MACRO.findall(header.text) if m != macro]
    count = _ATTRIBUTES_NB.findall(header.text)
    assert len(count) == 1, f"{header.name}: no single <LABEL>_ATTRIBUTES_NB"
    assert attributes, f"{header.name} defines no attribute name"
    assert len(attributes) == int(count[0][1]), (header.name, attributes, count)
    return macro, attributes


def _loader_source(header: GeneratedFile) -> tuple[str, int]:
    """A program that loads the plugins of ``$MMT_DPI_PLUGINS_DIR`` with
    ``init_extraction()`` and checks that the protocol of ``header`` and
    each of its attributes resolve to their own id and name; it prints one
    ``PASS:`` or ``FAIL:`` line per check. Also returns the number of
    checks."""
    macro, attributes = _loader_checks(header)
    checks = [
        f'    check(is_registered_protocol({macro}) != 0, "is_registered_protocol({macro})");',
        f"    check(get_protocol_id_by_name({macro}_ALIAS) == {macro},",
        f'          "get_protocol_id_by_name({macro}_ALIAS) == {macro}");',
    ]
    for name in attributes:
        checks += [
            f"    check(get_attribute_id_by_protocol_id_and_attribute_name({macro}, {name}_ALIAS)",
            f'              == {name}, "attribute {name}");',
        ]
    lines = [
        "#include <stdio.h>",
        '#include "mmt_core.h"',
        f'#include "{header.name}"',
        "",
        "static int failures = 0;",
        "",
        "static void check(int ok, const char *what)",
        "{",
        '    printf("%s: %s\\n", ok ? "PASS" : "FAIL", what);',
        "    if (!ok)",
        "        failures++;",
        "}",
        "",
        "int main(void)",
        "{",
        "    if (!init_extraction()) {",
        '        puts("FAIL: init_extraction()");',
        "        return 1;",
        "    }",
        '    puts("PASS: init_extraction()");',
        *checks,
        "    close_extraction();",
        "    return failures ? 1 : 0;",
        "}",
        "",
    ]
    return "\n".join(lines), 1 + 2 + len(attributes)


def _plugins_dir(tmp_path: Path) -> Path:
    """A plugin directory that holds the SDK's ``libmmt_tcpip.so``."""
    tcpip = _sdk_prefix() / "plugins" / TCPIP
    assert tcpip.is_file(), f"{tcpip} not found"
    plugins = tmp_path / "plugins"
    plugins.mkdir()
    (plugins / TCPIP).symlink_to(tcpip.resolve())
    return plugins


def _plugin_name(generation: Generation) -> str:
    """``<label>.so``, which sorts after ``libmmt_tcpip.so`` both in the C
    locale and in the current ``LC_COLLATE`` (the loader uses
    ``scandir(alphasort)``), so the parents it may name already exist."""
    name = f"{generation.label.lower()}.so"
    assert sorted([name.encode(), TCPIP.encode()])[0] == TCPIP.encode(), name
    saved = locale.setlocale(locale.LC_COLLATE)
    try:
        locale.setlocale(locale.LC_COLLATE, "")
        assert sorted([name, TCPIP], key=locale.strxfrm)[0] == TCPIP, name
    except locale.Error:
        pass  # The environment's locale is not installed: the C one applies.
    finally:
        locale.setlocale(locale.LC_COLLATE, saved)
    return name


def _build_plugin(generation: Generation, sources: list[Path], plugins: Path) -> Path:
    include, cc = _include_dir(), _compiler()
    core, _ = _core_library(plugins.parent)
    plugin = plugins / _plugin_name(generation)
    proc = subprocess.run(
        [
            cc,
            f"-std={profile(_sdk_version()).c_std}",
            *PLUGIN_FLAGS,
            "-I",
            str(sources[0].parent),
            "-I",
            str(include),
            *map(str, sources),
            str(core),
            "-o",
            str(plugin),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, f"{cc} {plugin.name}:\n{proc.stderr}"
    assert proc.stderr == "", proc.stderr
    return plugin


def _loader(generation: Generation, work: Path, tmp_path: Path) -> tuple[Path, int]:
    text, count = _loader_source(_header(generation))
    source = work / "load_check.c"
    source.write_text(text)
    return _build_program(source, tmp_path, flags=LOADER_FLAGS), count


@pytest.mark.parametrize("name", ACCEPTED)
def test_the_generated_plugin_builds_and_loads_through_init_extraction(
    name: str, tmp_path: Path
) -> None:
    work = tmp_path / name
    generation, sources = _write_model(name, work)
    plugins = _plugins_dir(tmp_path)
    _build_plugin(generation, sources, plugins)
    loader, count = _loader(generation, work, tmp_path)
    run = _run(loader, tmp_path, plugins)
    assert run.returncode == 0, f"{run.stdout}\n{run.stderr}"
    lines = run.stdout.splitlines()
    assert lines == [line for line in lines if line.startswith("PASS: ")], run.stdout
    assert len(lines) == count, run.stdout
    assert run.stderr == "", run.stderr


def test_the_load_check_fails_without_the_plugin(tmp_path: Path) -> None:
    # The checks after init_extraction() can fail: with only libmmt_tcpip.so
    # in the directory, the protocol and every attribute are unknown.
    work = tmp_path / "pdl_scopes"
    generation, _ = _write_model("pdl_scopes", work)
    plugins = _plugins_dir(tmp_path)
    loader, count = _loader(generation, work, tmp_path)
    run = _run(loader, tmp_path, plugins)
    assert run.returncode != 0, run.stdout
    lines = run.stdout.splitlines()
    assert lines[0] == "PASS: init_extraction()", run.stdout
    assert len(lines) == count, run.stdout
    assert all(line.startswith("FAIL: ") for line in lines[1:]), run.stdout


def test_the_load_check_fails_when_the_plugin_does_not_register(tmp_path: Path) -> None:
    # A plugin whose protocol id is the SDK's PROTO_TCP: init_proto() fails,
    # and mmt-dpi then fails init_extraction() as a whole.
    work = tmp_path / "pdl_scopes"
    generation, sources = _write_model("pdl_scopes", work)
    tcp = profile(_sdk_version()).parents.id_of("PROTO_TCP")
    assert tcp is not None
    header = work / _header(generation).name
    text = header.read_text()
    changed = _PROTO_MACRO.sub(lambda m: f"#define {m.group(1)} {tcp}", text)
    assert changed != text
    header.write_text(changed)
    plugins = _plugins_dir(tmp_path)
    _build_plugin(generation, sources, plugins)
    loader, _ = _loader(generation, work, tmp_path)
    run = _run(loader, tmp_path, plugins)
    assert run.returncode != 0, run.stdout
    assert run.stdout.splitlines() == ["FAIL: init_extraction()"], run.stdout
    assert "init_proto() failed" in run.stderr, run.stderr


# Generated vs user code (T2.2, #18): the scaffold builds, a hook it lacks is
# found before the link, and its parent example classifies a corpus packet.


def _objects(sources: list[Path], work: Path) -> list[Path]:
    """Compile each source of ``work`` to an object, as a build does."""
    include, cc = _include_dir(), _compiler()
    objects = []
    for source in sources:
        obj = source.with_suffix(".o")
        proc = subprocess.run(
            [
                cc,
                f"-std={profile(_sdk_version()).c_std}",
                *("-fPIC", "-Wall", "-Wextra", "-Werror", "-c"),
                *("-I", str(work), "-I", str(include)),
                *(str(source), "-o", str(obj)),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 0, f"{cc} {source.name}:\n{proc.stderr}"
        objects.append(obj)
    return objects


def test_a_model_change_that_adds_a_hook_fails_the_build(tmp_path: Path) -> None:
    # The scaffold of the old model stays in src/; the new model's header
    # declares one more hook, which the check finds in the compiled user
    # code before the link, and which -Wl,-z,defs refuses at the link.
    old = generate_text(BASE % "")
    work = tmp_path / "project"
    (work / "src").mkdir(parents=True)
    impl = work / scaffold(old, profile(_sdk_version())).path
    impl.write_text(scaffold(old, profile(_sdk_version())).text)
    new = generate_text(BASE % NEW_HOOK)
    for f in new.files:
        (work / f.name).write_text(f.text)
    generated = [work / f.name for f in new.files if f.name.endswith(".c")]
    user = _objects([impl], work)
    _objects(generated, work)
    missing = missing_hooks(new.hooks, user)
    assert [h.name for h in missing] == ["regen_hook_extract_extra"]
    error, diagnostics = missing_hook_error(missing, "src/regen_impl.c", new.header)
    assert (error.code, int(error.exit_code)) == ("build.missing-hook", 5)
    assert "regen_hook_extract_extra" in error.message
    assert error.hint is not None and "src/regen_impl.c" in error.hint
    assert [d.location.file for d in diagnostics if d.location] == ["src/regen_impl.c"]
    # The old model's own hooks are all there.
    assert missing_hooks(old.hooks, user) == ()
    plugins = tmp_path / "plugins"
    plugins.mkdir()
    include, cc = _include_dir(), _compiler()
    core, _ = _core_library(tmp_path)
    proc = subprocess.run(
        [
            cc,
            f"-std={profile(_sdk_version()).c_std}",
            *PLUGIN_FLAGS,
            *("-I", str(work), "-I", str(include)),
            *map(str, [*generated, impl]),
            *(str(core), "-o", str(plugins / "regen.so")),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode != 0
    assert "regen_hook_extract_extra" in proc.stderr, proc.stderr


#: The parents example of the scaffold: its parts follow these lines of
#: its comment.
_EXAMPLE_PARTS = (
    "add these includes at the top of this file:",
    "then this function, before this one:",
    "and, in this function:",
    "The parent must already be registered",
)


def _example(text: str, hook: str) -> tuple[str, str, str]:
    """The commented example of ``hook`` in the scaffold ``text``,
    uncommented: the includes, the classification function and the
    registration."""
    body = text.split(f"\n{hook}\n{{\n", 1)[1]
    lines = [line.strip().removeprefix("*") for line in body.splitlines()]
    starts = [next(n for n, line in enumerate(lines) if part in line) for part in _EXAMPLE_PARTS]
    parts = [
        "\n".join(line.removeprefix("    ") for line in lines[i + 1 : j]).strip() + "\n"
        for i, j in itertools.pairwise(starts)
    ]
    return parts[0], parts[1], parts[2]


def _corpus_packet(model: str, stem: str) -> dict[str, Any]:
    spec = importlib.util.spec_from_file_location("corpus_validate", CORPUS.parent / "validate.py")
    assert spec is not None and spec.loader is not None
    validator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(validator)
    packet: dict[str, Any] = validator.load_yaml(CORPUS / model / "packets" / f"{stem}.yaml")
    return packet


def _classify_source(header: GeneratedFile, frame: bytes, attribute: str) -> str:
    """A program that loads ``$MMT_DPI_PLUGINS_DIR``, processes the Ethernet
    ``frame`` and prints the protocol path and ``attribute`` (one byte)."""
    macro, _ = _loader_checks(header)
    label = macro.removeprefix("PROTO_")
    data = ", ".join(f"0x{b:02x}" for b in frame)
    return f"""#include <stdio.h>
#include <string.h>
#include "mmt_core.h"
#include "{header.name}"

static int on_packet(const ipacket_t *ipacket, mmt_opaque_t user)
{{
    const uint8_t *value;
    int i;

    (void)user;
    printf("path:");
    for (i = 0; i < ipacket->proto_hierarchy->len; i++) {{
        printf(" %d", ipacket->proto_hierarchy->proto_path[i]);
    }}
    printf("\\n");
    if (get_protocol_index_by_id(ipacket, {macro}) == MMT_NO_PROTO_INDEX) {{
        puts("classified: no");
        return 0;
    }}
    puts("classified: yes");
    value = get_attribute_extracted_data(ipacket, {macro}, {label}_{attribute.upper()});
    if (value != NULL) {{
        printf("{attribute}: %u\\n", (unsigned)*value);
    }}
    return 0;
}}

int main(void)
{{
    static const unsigned char frame[] = {{{data}}};
    char error[MMT_ERRBUF_SIZE];
    struct pkthdr header;
    mmt_handler_t *handler;

    if (!init_extraction()) {{
        puts("init_extraction failed");
        return 1;
    }}
    handler = mmt_init_handler(DLT_EN10MB, 0, error);
    if (handler == NULL) {{
        printf("mmt_init_handler: %s\\n", error);
        return 1;
    }}
    if (!register_extraction_attribute(handler, {macro}, {label}_{attribute.upper()})
        || !register_packet_handler(handler, 1, on_packet, NULL)) {{
        puts("registration failed");
        return 1;
    }}
    memset(&header, 0, sizeof(header));
    header.caplen = header.len = sizeof(frame);
    if (!packet_process(handler, &header, frame)) {{
        puts("packet_process failed");
        return 1;
    }}
    mmt_close_handler(handler);
    close_extraction();
    return 0;
}}
"""


def test_the_scaffold_parent_example_classifies_a_corpus_packet(tmp_path: Path) -> None:
    # ndn/interest: an NDN Interest over Ethernet (EtherType 0x8624). The
    # scaffold's example, with that EtherType, attaches the plugin to
    # Ethernet; loaded after libmmt_tcpip.so, the frame is classified into
    # the plugin's protocol and its packet_type is extracted.
    packet = _corpus_packet("ndn", "interest")
    assert packet["parent"]["path"] == ["ethernet"]
    ethertype = int(packet["parent"]["selector"].removeprefix("ethertype "), 16)
    payload = bytes.fromhex("".join(packet["bytes"]))
    expected = next(a for a in packet["expect"]["attributes"] if a["name"] == "packet_type")
    work = tmp_path / "ndn"
    generation, sources = _write_model("ndn", work)
    impl = sources[-1]
    hook = next(h for h in generation.hooks if h.role == REGISTER_PARENTS)
    text = impl.read_text()
    includes, classify, register = _example(text, hook.declaration)
    classify = classify.replace("0x88", f"0x{ethertype >> 8:02x}")
    classify = classify.replace("0xb5", f"0x{ethertype & 0xFF:02x}")
    assert "register_classification_function_with_parent_protocol(PROTO_ETHERNET" in register
    stub = f"\n{hook.declaration}\n{{\n"
    body = text.split(stub, 1)[1].split("\n}\n", 1)[0]
    edited = text.replace(
        stub + body + "\n}\n",
        f"\n{classify}{stub}    (void)protocol_struct;\n{register}    return 1;\n}}\n",
    )
    assert includes.splitlines()[0] == "#include <string.h>"
    edited = edited.replace("#include <stddef.h>\n", "#include <stddef.h>\n" + includes)
    impl.write_text(edited)
    plugins = _plugins_dir(tmp_path)
    plugin = _build_plugin(generation, sources, plugins)
    frame = bytes(6) + bytes([2, 0, 0, 0, 0, 1]) + ethertype.to_bytes(2, "big") + payload
    source = work / "classify.c"
    source.write_text(_classify_source(_header(generation), frame, "packet_type"))
    run = _run(_build_program(source, tmp_path, flags=LOADER_FLAGS), tmp_path, plugins)
    assert run.returncode == 0, f"{run.stdout}\n{run.stderr}"
    ethernet = profile(_sdk_version()).parents.id_of("PROTO_ETHERNET")
    proto = packet["expect"]["proto_id"]
    lines = run.stdout.splitlines()
    assert lines[0].split()[1:] == ["1", str(ethernet), str(proto)], run.stdout
    assert lines[1:] == ["classified: yes", f"packet_type: {expected['value']}"], run.stdout
    # With the scaffold as it comes (no parent), the plugin loads but the
    # same frame stays Ethernet.
    impl.write_text(text)
    plugin.unlink()
    _build_plugin(generation, sources, plugins)
    run = _run(_build_program(source, tmp_path, flags=LOADER_FLAGS), tmp_path, plugins)
    assert run.returncode == 0, f"{run.stdout}\n{run.stderr}"
    lines = run.stdout.splitlines()
    assert lines[0].split()[1:3] == ["1", str(ethernet)], run.stdout
    assert str(proto) not in lines[0].split(), run.stdout
    assert lines[1:] == ["classified: no"], run.stdout
