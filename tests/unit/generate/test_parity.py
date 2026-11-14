"""Parity with the Java generator (T1.6, #15).

Of the 16 ``plugins/`` models, only abb, cotp, s7com and tpkt give Java
output that compiles against mmt-dpi 1.10.2 (inventory, section 4). For each
of them this module reads the Java output pinned in ``legacy/reference-output/``
and the new output, reduces both to what they mean to mmt-dpi (``Meaning``:
the protocol id and alias, every attribute's id, alias, type, length,
position, scope and how its value is read, the header's structs and the
registration calls) and asserts the two are equal, apart from the one
difference that ``docs/behaviour-changes.md`` declares for these models:
Java's ``register_protocol_stack`` (bug 22).

The 4 models take ids that mmt-dpi 1.10.2 already has, and cotp, s7com
and tpkt its names too (bug 23), so ``generate`` refuses them; here they
are analysed with ``allow_sdk_conflicts=True``, which keeps the model and
only those errors.

The parser reads the C each generator writes, not C in general: a form it
does not know fails the test instead of being skipped.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from functools import cache

import pytest

from mmt_plugin.codegen import Generation, generate
from mmt_plugin.diagnostics import Severity
from mmt_plugin.pdl import parse
from mmt_plugin.semantics import SDK_CONFLICT_CODES, analyse

from .helpers import REPO, profile, source_text

#: The models whose Java output compiles against mmt-dpi 1.10.2.
PARITY = ("abb", "cotp", "s7com", "tpkt")

REFERENCE = REPO / "legacy" / "reference-output"
INVENTORY = REPO / "docs" / "legacy" / "java-generator-inventory.md"

#: The byte widths of the C types the outputs use in ``sizeof`` and casts.
C_SIZES = {"uint8_t": 1, "uint16_t": 2, "uint32_t": 4, "uint64_t": 8, "char": 1}

#: The SDK extraction functions the Java tables use: (width, byte order).
#: mmt-dpi's ``general_*_extraction`` read at ``position_in_packet``;
#: ``_with_ordering_change`` converts from network byte order.
JAVA_READERS = {
    "general_char_extraction": (1, None),
    "general_short_extraction_with_ordering_change": (2, "big"),
    "general_int_extraction_with_ordering_change": (4, "big"),
}

#: The registration that only the Java output makes (bug 22).
JAVA_ONLY = "register_protocol_stack"


@dataclass(frozen=True)
class Read:
    """How an attribute's value is read: ``width`` bytes at ``offset`` from
    the start of the protocol, in ``order`` (``None`` for one byte)."""

    offset: int
    width: int
    order: str | None


@dataclass(frozen=True)
class Attribute:
    """One attribute: its enum constant and id, its alias, and its row of
    the ``attribute_metadata_t`` table."""

    name: str
    id: int
    alias: str
    data_type: str
    data_len: int
    position: int
    scope: str
    read: Read


@dataclass(frozen=True)
class Meaning:
    """What a generated header and source pair means to mmt-dpi."""

    files: tuple[str, ...]
    proto: str
    proto_id: int
    alias: str
    count: int
    attributes: tuple[Attribute, ...]
    structs: tuple[tuple[str, tuple[tuple[str, str], ...]], ...]
    registrations: tuple[str, ...]


# --- reading the C ------------------------------------------------------------


def _one(pattern: str, text: str, what: str, flags: int = 0) -> re.Match[str]:
    found = list(re.finditer(pattern, text, flags))
    assert len(found) == 1, f"{len(found)} matches for {what}"
    return found[0]


def _defines(header: str) -> dict[str, str]:
    return dict(re.findall(r"^#define[ \t]+(\w+)[ \t]+(\S.*?)[ \t]*$", header, re.M))


def _string(value: str) -> str:
    assert re.fullmatch(r'"[^"\\]*"', value), value
    return value[1:-1]


def _enum(header: str) -> dict[str, int]:
    """The attributes enum, with C's implicit values filled in."""
    body = _one(r"enum \w+_attributes \{(.*?)\};", header, "the attributes enum", re.S).group(1)
    values: dict[str, int] = {}
    last = 0
    for entry in (e.strip() for e in body.split(",")):
        if not entry:
            continue
        m = re.fullmatch(r"(\w+)(?:\s*=\s*(\w+))?", entry)
        assert m, entry
        name, value = m.groups()
        if value is None:
            last += 1
        elif value.isdigit():
            last = int(value)
        else:
            last = values[value]
        values[name] = last
    return values


def _structs(header: str) -> tuple[tuple[str, tuple[tuple[str, str], ...]], ...]:
    found = []
    for name, body in re.findall(r"^\s*struct (\w+) \{\n(.*?)^\s*\};", header, re.M | re.S):
        members = tuple(re.findall(r"^\s*(\w+) (\w+)\s*;", body, re.M))
        assert len(members) == len(body.strip().splitlines()), body
        found.append((name, members))
    return tuple(found)


def _function(source: str, name: str) -> str:
    """The body of the function ``name`` defined in ``source``."""
    pattern = rf"^\S[^\n;]*\b{name}\([^;{{]*\)\s*\{{\n(.*?)^\}}"
    return _one(pattern, source, f"the definition of {name}", re.M | re.S).group(1)


def _table(source: str) -> tuple[str, str, list[str]]:
    """The attribute table: its name, its declared size and its rows."""
    m = _one(
        r"^static attribute_metadata_t (\w+)\[(\w+)\] = \{\n(.*?)^\};",
        source,
        "the attribute table",
        re.M | re.S,
    )
    lines = [line for line in m.group(3).splitlines() if line.strip()]
    rows = [re.fullmatch(r"\s*\{(.*)\},", line) for line in lines]
    assert all(rows), m.group(3)
    return m.group(1), m.group(2), [r.group(1) for r in rows if r]


def _length(value: str) -> int:
    m = re.fullmatch(r"sizeof\((\w+)\)", value)
    return C_SIZES[m.group(1)] if m else int(value)


_ROW_KEYS = ("id", "alias", "data_type", "data_len", "position_in_packet", "scope")
_ROW_KEYS_FN = (*_ROW_KEYS, "extraction_function")


def _row(row: str) -> dict[str, str]:
    """A table row as ``{field: text}``, positional (Java) or designated."""
    cells = [c.strip() for c in row.split(",")]
    if all(c.startswith(".") for c in cells):
        pairs = [re.fullmatch(r"\.(\w+) = (.+)", c) for c in cells]
        assert all(pairs), row
        fields = {p.group(1): p.group(2) for p in pairs if p}
    else:
        fields = dict(zip(_ROW_KEYS_FN, cells, strict=True))
    assert tuple(fields) == _ROW_KEYS_FN, row
    return fields


def _java_read(function: str, position: int) -> Read:
    width, order = JAVA_READERS[function]
    return Read(position, width, order)


def _new_read(source: str, function: str) -> Read:
    """Follow ``<l>_<a>_extraction`` to its get and place functions."""
    extraction = _function(source, function)
    get = _one(r"if \(!(\w+)\(packet, proto_index, &value\)\)", extraction, "the get call")
    store = _one(r"\*\((\w+) \*\) extracted_data->data = \(\1\) value;", extraction, "the store")
    getter = _function(source, get.group(1))
    place = _one(r"if \(!(\w+)\(packet, proto_index, &offset, &length\)\)", getter, "the place")
    read = _one(r"\*value = (\w+)\(p, (\d+)\);", getter, "the read")
    placed = _function(source, place.group(1))
    offset = int(_one(r"\*offset = (\d+);", placed, "the offset").group(1))
    length = int(_one(r"\*length = (\d+);", placed, "the length").group(1))
    width = int(read.group(2))
    assert length == width == C_SIZES[store.group(1)], function
    loop = _one(r"value = \(value << 8\) \| p\[(.*?)\];", _function(source, read.group(1)), "loop")
    order = {"i": "big", "width - 1 - i": "little"}[loop.group(1)]
    return Read(offset, width, None if width == 1 else order)


def _registrations(source: str, init: str, table: str, size: str) -> tuple[str, ...]:
    """The SDK registration calls of ``init``, in order. A call made for
    each row of the table is written ``<each row>``; the loop must cover
    the whole table."""
    body = _function(source, init)
    bounds = re.findall(r"for ?\([^;]*; i < ([^;]+); i ?\+\+\)", body)
    assert bounds in ([size], [f"sizeof({table}) / sizeof({table}[0])"]), bounds
    calls = []
    for name, args in re.findall(
        r"\b(init_protocol_struct_for_registration|register_\w+)\(([^;]*?)\)", body
    ):
        args = args.replace(f"&{table}[i]", "<each row>")
        calls.append(f"{name}({args})")
    return tuple(calls)


def meaning(header_name: str, header: str, source_name: str, source: str) -> Meaning:
    defines = _defines(header)
    protos = [k for k in defines if re.fullmatch(r"PROTO_\w+", k) and not k.endswith("_ALIAS")]
    assert len(protos) == 1, protos
    proto = protos[0]
    enum = _enum(header)
    counts = [k for k in enum if k.endswith("_ATTRIBUTES_NB")]
    assert len(counts) == 1, counts
    count = enum.pop(counts[0])
    table, size, rows = _table(source)
    assert size == counts[0] and len(rows) == count == len(enum) > 0, (size, len(rows), count)
    attributes = []
    for text in rows:
        row = _row(text)
        name = row["id"]
        assert row["alias"] == f"{name}_ALIAS", row
        position = int(row["position_in_packet"])
        function = row["extraction_function"]
        read = (
            _java_read(function, position)
            if function in JAVA_READERS
            else _new_read(source, function)
        )
        attributes.append(
            Attribute(
                name=name,
                id=enum[name],
                alias=_string(defines[row["alias"]]),
                data_type=row["data_type"],
                data_len=_length(row["data_len"]),
                position=position,
                scope=row["scope"],
                read=read,
            )
        )
    assert [a.name for a in attributes] == list(enum), "the table is not in enum order"
    label = proto.removeprefix("PROTO_").lower()
    return Meaning(
        files=(header_name, source_name),
        proto=proto,
        proto_id=int(defines[proto]),
        alias=_string(defines[f"{proto}_ALIAS"]),
        count=count,
        attributes=tuple(attributes),
        structs=_structs(header),
        registrations=_registrations(source, f"init_{label}_proto_struct", table, size),
    )


# --- the two outputs ------------------------------------------------------------


def _pair(files: dict[str, str]) -> tuple[str, str, str, str]:
    headers = [n for n in files if n.endswith(".h")]
    sources = [n for n in files if n.endswith(".c")]
    assert len(headers) == len(sources) == 1, sorted(files)
    return headers[0], files[headers[0]], sources[0], files[sources[0]]


def java_files(name: str) -> dict[str, str]:
    directory = REFERENCE / f"{name}_plugin"
    return {p.name: p.read_text(encoding="utf-8") for p in sorted(directory.iterdir())}


@cache
def new_generation(name: str) -> Generation:
    """The new output, analysed with the SDK id and name conflicts allowed."""
    model = parse(source_text(name), filename=f"tests/corpus/models/{name}/model.pdl")
    analysed, diagnostics = analyse(model, profile=profile(), allow_sdk_conflicts=True)
    assert analysed is not None, [d.message for d in diagnostics]
    errors = {d.code for d in diagnostics if d.severity is Severity.ERROR}
    assert errors and errors <= SDK_CONFLICT_CODES, errors
    return generate(analysed, profile())


def java_meaning(name: str) -> Meaning:
    return meaning(*_pair(java_files(name)))


def new_meaning(name: str) -> Meaning:
    return meaning(*_pair({f.name: f.text for f in new_generation(name).files}))


# --- the tests --------------------------------------------------------------------


def test_the_parity_models_are_the_ones_whose_java_output_compiles() -> None:
    row = _one(r"^\| ([^|]+) \| ok \| \*\*OK\*\* \|", INVENTORY.read_text(), "the OK row", re.M)
    assert tuple(m.strip() for m in row.group(1).split(",")) == PARITY
    for name in PARITY:
        assert (REFERENCE / f"{name}_plugin.exit").read_text().strip() == "0"
        assert (REFERENCE / f"{name}_plugin.stderr").read_text() == ""


@pytest.mark.parametrize("name", PARITY)
def test_the_new_output_means_what_the_java_output_means(name: str) -> None:
    java, new = java_meaning(name), new_meaning(name)
    # The one declared difference (bug 22): Java also registers the protocol
    # as a stack whose classification claims every packet.
    classify = f"{java.proto.removeprefix('PROTO_').lower()}_stack_classification"
    stack = [r for r in java.registrations if r.startswith(f"{JAVA_ONLY}(")]
    assert stack == [f"{JAVA_ONLY}({java.proto}, {java.proto}_ALIAS, {classify})"]
    assert not any(r.startswith(f"{JAVA_ONLY}(") for r in new.registrations)
    without = tuple(r for r in java.registrations if r not in stack)
    assert replace(java, registrations=without) == new


@pytest.mark.parametrize("name", PARITY)
def test_the_registrations_are_the_protocol_each_row_and_the_protocol_again(name: str) -> None:
    # The comparison above is not vacuous: both sides register these.
    proto = new_meaning(name).proto
    assert new_meaning(name).registrations == (
        f"init_protocol_struct_for_registration({proto}, {proto}_ALIAS)",
        "register_attribute_with_protocol(protocol_struct, <each row>)",
        f"register_protocol(protocol_struct, {proto})",
    )


@pytest.mark.parametrize("name", PARITY)
def test_the_new_init_checks_every_registration(name: str) -> None:
    # Not a numbered bug (docs/behaviour-changes.md): Java ignores a refused
    # attribute and returns -1 or register_protocol()'s result; the new
    # init returns 0 on any refusal, and refuses a name already registered.
    generation = new_generation(name)
    label = generation.label.lower()
    source = generation.file(f"{label}_mmt_plugin.c").text
    body = _function(source, f"init_{label}_proto_struct")
    assert "get_protocol_id_by_name(" in body
    for call in ("register_attribute_with_protocol(", "register_protocol("):
        assert f"if (!{call}" in body, call
    assert re.findall(r"return (-?\d+);", body) == ["0", "0", "0", "0", "1"]
    java = _function(_pair(java_files(name))[3], f"init_{label}_proto_struct")
    assert "return -1;" in java and "return register_protocol(" in java


@pytest.mark.parametrize("name", PARITY)
def test_the_new_output_reads_only_captured_bytes(name: str) -> None:
    # Not a numbered bug (docs/behaviour-changes.md): the SDK's
    # general_*_extraction read at position_in_packet without a length
    # check; the new functions read nothing past the captured packet.
    generation = new_generation(name)
    label = generation.label.lower()
    source = generation.file(f"{label}_mmt_plugin.c").text
    body = _function(source, f"{label}_bytes")
    assert "packet->p_hdr->caplen" in body
    assert "if (start > caplen - length) {\n        return NULL;" in body
    for function in re.findall(r"\.extraction_function = (\w+)\}", source):
        assert not function.startswith("general_"), function


def test_the_reader_follows_both_byte_orders() -> None:
    # The parser itself: a little-endian read helper is read as such.
    source = (
        "static uint64_t t_read(const uint8_t *p, unsigned width)\n{\n"
        "        value = (value << 8) | p[width - 1 - i];\n}\n"
        "static int t_place_a(const ipacket_t *packet, mmt_proto_index_t proto_index, "
        "int64_t *offset, int64_t *length)\n{\n    *offset = 3;\n    *length = 2;\n}\n"
        "static int t_get_a(const ipacket_t *packet, mmt_proto_index_t proto_index, "
        "uint64_t *value)\n{\n"
        "    if (!t_place_a(packet, proto_index, &offset, &length)) {\n"
        "    *value = t_read(p, 2);\n}\n"
        "static int t_a_extraction(const ipacket_t *packet, mmt_proto_index_t proto_index, "
        "attribute_t *extracted_data)\n{\n"
        "    if (!t_get_a(packet, proto_index, &value)) {\n"
        "    *(uint16_t *) extracted_data->data = (uint16_t) value;\n}\n"
    )
    assert _new_read(source, "t_a_extraction") == Read(3, 2, "little")


def test_the_reference_output_is_the_frozen_one() -> None:
    # The Java side of the comparison is legacy/reference-output/, which CI
    # regenerates from the jar (legacy/check-reference-output.sh).
    manifest = (REFERENCE / "MANIFEST").read_text()
    assert "MMTPluginGenerator.jar" in manifest
    for name in PARITY:
        files = sorted(java_files(name))
        assert files == sorted(f.name for f in new_generation(name).files), name
