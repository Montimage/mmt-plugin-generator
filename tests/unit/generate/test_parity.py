"""Parity with the Java generator (T1.6, #15).

Of the 16 ``plugins/`` models, only abb, cotp, s7com and tpkt give Java
output that compiles against mmt-dpi 1.10.2 (inventory, section 4). For each
of them this module reads the Java output pinned in ``legacy/reference-output/``
and the new output, reduces both to what they mean to mmt-dpi (``Meaning``:
the protocol id and alias, every attribute's id, alias, type, length,
position, scope and how its value is read, the header's structs and the
registration calls) and asserts the two are equal, apart from the two
differences that ``docs/behaviour-changes.md`` declares for these models:
Java's ``register_protocol_stack`` (bug 22), and the new init's call of the
user hook ``<l>_hook_register_parents`` (T2.2).

The 4 models take ids that mmt-dpi 1.10.2 already has, and cotp, s7com
and tpkt its names too (bug 23), so ``generate`` refuses them; here they
are analysed with ``allow_sdk_conflicts=True``, which keeps the model and
only those errors.

The parser reads the C each generator writes, not C in general. Every
function it follows (the new output's extraction, get, place, bytes and read
functions of each attribute, and both outputs' ``init_<l>_proto_struct`` and
``init_proto``) must match, whole and statement for statement, the shape
that generator writes (``SHAPES``), comments and whitespace aside: an extra,
missing or altered statement fails the test instead of being skipped. What
it does not follow (Java's stack classification, the new ``_Static_assert``
lines) is not compared.
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

#: The call that only the new init makes, after registering the protocol:
#: the user hook that attaches it to its parents (T2.2, #18).
NEW_ONLY = "_hook_register_parents"


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


#: The definitions the parser follows, as each generator writes them. A
#: ``@slot@`` stands for a name (or a number, or one of ``_SLOTS``), the same
#: text wherever it recurs.
SHAPES = {
    "extraction": """
        static int @name@(const ipacket_t *packet, mmt_proto_index_t proto_index,
            attribute_t *extracted_data)
        {
        uint64_t value;
        if (!@get@(packet, proto_index, &value)) {
        return 0;
        }
        *(@ctype@ *) extracted_data->data = (@ctype@) value;
        return 1;
        }
    """,
    "get": """
        static int @name@(const ipacket_t *packet, mmt_proto_index_t proto_index, uint64_t *value)
        {
        int64_t offset, length;
        const uint8_t *p;
        if (!@place@(packet, proto_index, &offset, &length)) {
        return 0;
        }
        p = @bytes@(packet, proto_index, offset, length);
        if (p == NULL) {
        return 0;
        }
        *value = @read@(p, @width@);
        return 1;
        }
    """,
    "place": """
        static int @name@(const ipacket_t *packet, mmt_proto_index_t proto_index,
            int64_t *offset, int64_t *length)
        {
        int ok = 1;
        (void) packet;
        (void) proto_index;
        *offset = @offset@;
        *length = @length@;
        return ok;
        }
    """,
    "bytes": """
        static const uint8_t *@name@(const ipacket_t *packet, mmt_proto_index_t proto_index,
            int64_t offset, int64_t length)
        {
        int64_t caplen = (int64_t) packet->p_hdr->caplen;
        int64_t start = (int64_t) get_packet_offset_at_index(packet, proto_index);
        if (start < 0 || offset < 0 || length < 0 || offset > caplen || length > caplen) {
        return NULL;
        }
        start += offset;
        if (start > caplen - length) {
        return NULL;
        }
        return &packet->data[start];
        }
    """,
    "read": """
        static uint64_t @name@(const uint8_t *p, unsigned width)
        {
        uint64_t value = 0;
        unsigned i;
        for (i = 0; i < width; i++) {
        value = (value << 8) | p[@index@];
        }
        return value;
        }
    """,
    "new init": """
        int @name@(void)
        {
        protocol_t *protocol_struct;
        size_t i;
        if (get_protocol_id_by_name(@proto@_ALIAS) != 0) {
        mmt_log_error("@name@: protocol name %s is already registered", @proto@_ALIAS);
        return 0;
        }
        protocol_struct = init_protocol_struct_for_registration(@proto@, @proto@_ALIAS);
        if (protocol_struct == NULL) {
        mmt_log_error("@name@: protocol id %d is out of range or already registered", @proto@);
        return 0;
        }
        for (i = 0; i < sizeof(@table@) / sizeof(@table@[0]); i++) {
        if (!register_attribute_with_protocol(protocol_struct, &@table@[i])) {
        mmt_log_error("@name@: cannot register attribute %s", @table@[i].alias);
        return 0;
        }
        }
        if (!register_protocol(protocol_struct, @proto@)) {
        mmt_log_error("@name@: cannot register protocol %d", @proto@);
        return 0;
        }
        if (!@parents@(protocol_struct)) {
        mmt_log_error("@name@: @parents@() failed");
        return 0;
        }
        return 1;
        }
    """,
    "java init": """
        int @name@() {
        protocol_t * protocol_struct =
            init_protocol_struct_for_registration(@proto@, @proto@_ALIAS);
        if (protocol_struct != NULL) {
        int i = 0;
        for(; i < @size@; i ++) {
        register_attribute_with_protocol(protocol_struct, &@table@[i]);
        }
        register_protocol_stack(@proto@, @proto@_ALIAS, @classify@);
        return register_protocol(protocol_struct, @proto@);
        } else {
        return -1;
        }
        }
    """,
    "new init_proto": """
        int @name@(void)
        {
        return @init@();
        }
    """,
    "java init_proto": """
        int @name@() {
        return @init@();
        }
    """,
}

#: The slots that are not a plain name.
_SLOTS = {
    "offset": r"\d+",
    "length": r"\d+",
    "width": r"\d+",
    "index": r"i|width - 1 - i",
}


def _normalise(text: str) -> str:
    """``text`` without comments, with one space for each run of whitespace
    (line breaks included: they mean nothing to C outside a string)."""
    return re.sub(r"\s+", " ", re.sub(r"/\*.*?\*/", " ", text, flags=re.S)).strip()


def _definition(source: str, name: str) -> str:
    """The whole definition of the function ``name`` in ``source``."""
    pattern = rf"^\S[^\n;]*\b{name}\([^;{{]*\)\s*\{{\n.*?^\}}"
    return _one(pattern, source, f"the definition of {name}", re.M | re.S).group(0)


def _shape(source: str, name: str, shape: str) -> dict[str, str]:
    """The slots of the definition of ``name``, which must be ``SHAPES[shape]``
    whole: any other statement fails."""
    template = _normalise(SHAPES[shape])
    parts, seen, pos = [], set(), 0
    for slot in re.finditer(r"@(\w+)@", template):
        parts.append(re.escape(template[pos : slot.start()]))
        key = slot.group(1)
        if key in seen:
            parts.append(f"(?P={key})")
        else:
            seen.add(key)
            parts.append(f"(?P<{key}>{_SLOTS.get(key, '[A-Za-z_][A-Za-z0-9_]*')})")
        pos = slot.end()
    parts.append(re.escape(template[pos:]))
    text = _normalise(_definition(source, name))
    m = re.fullmatch("".join(parts), text)
    assert m, f"{name} is not a {shape} function:\n{text}"
    assert m.group("name") == name, (name, m.group("name"))
    return m.groupdict()


def _new_read(source: str, function: str) -> Read:
    """Follow ``<l>_<a>_extraction`` to its get, place, bytes and read
    functions, each of which must have its shape."""
    extraction = _shape(source, function, "extraction")
    getter = _shape(source, extraction["get"], "get")
    placed = _shape(source, getter["place"], "place")
    _shape(source, getter["bytes"], "bytes")
    loop = _shape(source, getter["read"], "read")
    offset, length, width = (int(v) for v in (placed["offset"], placed["length"], getter["width"]))
    assert length == width == C_SIZES[extraction["ctype"]], function
    order = {"i": "big", "width - 1 - i": "little"}[loop["index"]]
    return Read(offset, width, None if width == 1 else order)


def _registrations(source: str, init: str, table: str, size: str) -> tuple[str, ...]:
    """The SDK registration calls of ``init``, in order, which with
    ``init_proto`` must have the shape of one of the two generators. A call
    made for each row of the table is written ``<each row>``."""
    java = _normalise(_definition(source, init)).startswith(f"int {init}() {{ protocol_t * ")
    kind = "java" if java else "new"
    found = _shape(source, init, f"{kind} init")
    assert _shape(source, "init_proto", f"{kind} init_proto")["init"] == init
    assert found["table"] == table, (found["table"], table)
    proto = found["proto"]
    calls = [f"init_protocol_struct_for_registration({proto}, {proto}_ALIAS)"]
    calls.append("register_attribute_with_protocol(protocol_struct, <each row>)")
    if java:
        assert found["size"] == size, (found["size"], size)
        calls.append(f"{JAVA_ONLY}({proto}, {proto}_ALIAS, {found['classify']})")
    calls.append(f"register_protocol(protocol_struct, {proto})")
    if not java:
        calls.append(f"{found['parents']}(protocol_struct)")
    return tuple(calls)


def _without_new_only(meaning: Meaning) -> Meaning:
    """``meaning`` without the new init's call of the parents hook."""
    calls = tuple(r for r in meaning.registrations if NEW_ONLY not in r)
    return replace(meaning, registrations=calls)


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
    # The other (T2.2): the new init then calls the user hook that attaches
    # the protocol to its parents, which Java never did.
    label = java.proto.removeprefix("PROTO_").lower()
    assert new.registrations[-1] == f"{label}{NEW_ONLY}(protocol_struct)"
    assert not any(NEW_ONLY in r for r in java.registrations)
    without = tuple(r for r in java.registrations if r not in stack)
    assert replace(java, registrations=without) == _without_new_only(new)


@pytest.mark.parametrize("name", PARITY)
def test_the_registrations_are_the_protocol_each_row_and_the_protocol_again(name: str) -> None:
    # The comparison above is not vacuous: both sides register these.
    proto = new_meaning(name).proto
    assert new_meaning(name).registrations == (
        f"init_protocol_struct_for_registration({proto}, {proto}_ALIAS)",
        "register_attribute_with_protocol(protocol_struct, <each row>)",
        f"register_protocol(protocol_struct, {proto})",
        f"{proto.removeprefix('PROTO_').lower()}{NEW_ONLY}(protocol_struct)",
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
    for call in ("register_attribute_with_protocol(", "register_protocol(", f"{label}{NEW_ONLY}("):
        assert f"if (!{call}" in body, call
    assert re.findall(r"return (-?\d+);", body) == ["0", "0", "0", "0", "0", "1"]
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
        "static const uint8_t *t_bytes(const ipacket_t *packet, mmt_proto_index_t proto_index, "
        "int64_t offset, int64_t length)\n{\n"
        "    int64_t caplen = (int64_t) packet->p_hdr->caplen;\n"
        "    int64_t start = (int64_t) get_packet_offset_at_index(packet, proto_index);\n"
        "    if (start < 0 || offset < 0 || length < 0 || offset > caplen || length > caplen) {\n"
        "        return NULL;\n    }\n    start += offset;\n"
        "    if (start > caplen - length) {\n        return NULL;\n    }\n"
        "    return &packet->data[start];\n}\n"
        "static uint64_t t_read(const uint8_t *p, unsigned width)\n{\n"
        "    uint64_t value = 0;\n    unsigned i;\n"
        "    for (i = 0; i < width; i++) {\n"
        "        value = (value << 8) | p[width - 1 - i];\n    }\n    return value;\n}\n"
        "static int t_place_a(const ipacket_t *packet, mmt_proto_index_t proto_index, "
        "int64_t *offset, int64_t *length)\n{\n"
        "    int ok = 1;\n    (void) packet;\n    (void) proto_index;\n"
        "    *offset = 3;\n    *length = 2;\n    return ok;\n}\n"
        "static int t_get_a(const ipacket_t *packet, mmt_proto_index_t proto_index, "
        "uint64_t *value)\n{\n"
        "    int64_t offset, length;\n    const uint8_t *p;\n"
        "    if (!t_place_a(packet, proto_index, &offset, &length)) {\n        return 0;\n    }\n"
        "    p = t_bytes(packet, proto_index, offset, length);\n"
        "    if (p == NULL) {\n        return 0;\n    }\n"
        "    *value = t_read(p, 2);\n    return 1;\n}\n"
        "static int t_a_extraction(const ipacket_t *packet, mmt_proto_index_t proto_index, "
        "attribute_t *extracted_data)\n{\n"
        "    uint64_t value;\n"
        "    if (!t_get_a(packet, proto_index, &value)) {\n        return 0;\n    }\n"
        "    *(uint16_t *) extracted_data->data = (uint16_t) value;\n    return 1;\n}\n"
    )
    assert _new_read(source, "t_a_extraction") == Read(3, 2, "little")


#: Changes to the new tpkt source that alter what it means to mmt-dpi:
#: (old text, new text), the old text found once.
MUTATIONS = {
    "bytes ignores the offset": ("    start += offset;\n", ""),
    "a getter shifts the offset": (
        "offset, length);\n    if (p == NULL) {\n        return 0;\n    }\n"
        "    *value = tpkt_read(p, 2);",
        "offset + 1, length);\n    if (p == NULL) {\n        return 0;\n    }\n"
        "    *value = tpkt_read(p, 2);",
    ),
    "a getter shifts the value": (
        "    *value = tpkt_read(p, 2);\n",
        "    *value = tpkt_read(p, 2);\n    *value >>= 8;\n",
    ),
    "a place moves the offset": ("    *length = 2;\n", "    *length = 2;\n    *offset += 1;\n"),
    "the read loop skips a byte": ("for (i = 0; i < width; i++)", "for (i = 1; i < width; i++)"),
    "the read loop is little-endian": ("p[i];", "p[width - 1 - i];"),
    "the registration loop skips a row": (
        "for (i = 0; i < sizeof(",
        "for (i = 1; i < sizeof(",
    ),
    "init returns before registering": ("    size_t i;\n", "    size_t i;\n\n    return 1;\n"),
    "init_proto does not init": ("    return init_tpkt_proto_struct();\n", "    return 1;\n"),
    "init ignores the parents hook": (
        "    if (!tpkt_hook_register_parents(protocol_struct)) {",
        "    if (!tpkt_hook_register_parents(protocol_struct) && 0) {",
    ),
    "a position moves": (".position_in_packet = 2", ".position_in_packet = 3"),
}


@pytest.mark.parametrize("mutation", MUTATIONS)
def test_the_parser_fails_on_any_other_new_output(mutation: str) -> None:
    # The parser accounts for every statement it follows: a mutated tpkt
    # source either does not parse or does not mean what Java's means.
    old, new = MUTATIONS[mutation]
    files = {f.name: f.text for f in new_generation("tpkt").files}
    source = files["tpkt_mmt_plugin.c"]
    assert source.count(old) == 1, old
    files["tpkt_mmt_plugin.c"] = source.replace(old, new)
    java = java_meaning("tpkt")
    without = tuple(r for r in java.registrations if not r.startswith(f"{JAVA_ONLY}("))
    try:
        mutated = meaning(*_pair(files))
    except AssertionError:
        return
    assert _without_new_only(mutated) != replace(java, registrations=without)


def test_the_reference_output_is_the_frozen_one() -> None:
    # The Java side of the comparison is legacy/reference-output/, which CI
    # regenerates from the jar (legacy/check-reference-output.sh).
    manifest = (REFERENCE / "MANIFEST").read_text()
    assert "MMTPluginGenerator.jar" in manifest
    for name in PARITY:
        files = sorted(java_files(name))
        assert files == sorted(f.name for f in new_generation(name).files), name
