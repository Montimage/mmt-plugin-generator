"""The YAML subset of plugin.yaml (``mmt_plugin.pluginyaml.nodes``): what it
reads, where each node is, and what it refuses, with the line and column."""

from __future__ import annotations

import pytest

from mmt_plugin.pluginyaml.nodes import Mapping, Scalar, Sequence, YamlError, parse, to_data

DOCUMENT = """\
# a comment
---
schema: 1
protocol:
  label: tpkt   # a trailing comment
  id: 0x3BC
  flags: [a, "b c", 3, 'it''s']
attributes:
  - name: a0
    offset: val(x) + 2
  - {name: b, length: 3, scope: }
  -
    name: c
    empty:
list:
- -4
- "x: y"
- true
- ~
...
"""


def test_the_subset_reads_block_and_flow_collections_and_scalars() -> None:
    assert to_data(parse(DOCUMENT)) == {
        "schema": 1,
        "protocol": {"label": "tpkt", "id": 956, "flags": ["a", "b c", 3, "it's"]},
        "attributes": [
            {"name": "a0", "offset": "val(x) + 2"},
            {"name": "b", "length": 3, "scope": None},
            {"name": "c", "empty": None},
        ],
        "list": [-4, "x: y", True, None],
    }


def test_every_node_has_its_position() -> None:
    root = parse(DOCUMENT)
    assert isinstance(root, Mapping)
    assert (root.line, root.column) == (3, 1)
    protocol = root.get("protocol")
    assert isinstance(protocol, Mapping)
    label = protocol.get("label")
    assert isinstance(label, Scalar)
    assert (label.line, label.column, label.end_line, label.end_column) == (5, 10, 5, 14)
    pid = protocol.get("id")
    assert isinstance(pid, Scalar) and pid.text == "0x3BC" and pid.value == 956
    flags = protocol.get("flags")
    assert isinstance(flags, Sequence)
    quoted = flags.items[1]
    assert isinstance(quoted, Scalar) and quoted.quoted
    assert (quoted.column, quoted.value_column, quoted.end_column) == (14, 15, 19)
    attributes = root.get("attributes")
    assert isinstance(attributes, Sequence)
    first = attributes.items[0]
    assert isinstance(first, Mapping) and (first.line, first.column) == (9, 5)
    offset = first.get("offset")
    assert isinstance(offset, Scalar)
    assert (offset.line, offset.column, offset.end_column) == (10, 13, 23)
    key = first.key("offset")
    assert key is not None and (key.line, key.column) == (10, 5)


@pytest.mark.parametrize(
    ("text", "value"),
    [
        ("0", 0),
        ("-0", 0),
        ("12", 12),
        ("-12", -12),
        ("0x1f", 31),
        ("0x1F", 31),
        ("true", True),
        ("False", False),
        ("null", None),
        ("~", None),
        ("1.5", 1.5),
        ("0X10", "0X10"),
        ("x:y", "x:y"),
        ("a#b", "a#b"),
        ("val(a) == 1 # c", "val(a) == 1"),
        ("1.10.2", "1.10.2"),
        ('"yes"', "yes"),
        ('"\\u00e9"', "\u00e9"),
    ],
)
def test_scalars_resolve_as_yaml_1_2_core(text: str, value: object) -> None:
    root = parse(f"k: {text}\n")
    assert isinstance(root, Mapping)
    node = root.get("k")
    assert isinstance(node, Scalar)
    assert node.value == value and type(node.value) is type(value)


@pytest.mark.parametrize(
    ("text", "line", "column", "message"),
    [
        ("k: yes\n", 1, 4, "read differently by YAML 1.1 and YAML 1.2"),
        ("k: off\n", 1, 4, "read differently"),
        ("k: 010\n", 1, 4, "leading"),
        ("k: 0o17\n", 1, 4, "read differently"),
        ("k: -0x10\n", 1, 4, "read differently"),
        ("k: 1:30\n", 1, 4, "read differently"),
        ("k: &a 1\n", 1, 4, "anchors"),
        ("k: *a\n", 1, 4, "aliases"),
        ("k: !!str 1\n", 1, 4, "tags"),
        ("k: |\n  text\n", 1, 4, "block scalars"),
        ("k:\n\tv: 1\n", 2, 1, "tab"),
        ("k: 1\nk: 2\n", 2, 1, "duplicate key `k`"),
        ("k: {a: 1, a: 2}\n", 1, 11, "duplicate key `a`"),
        ("k: a: b\n", 1, 5, "`:` followed by a space"),
        ("k: [1, [2]]\n", 1, 8, "inside a flow collection"),
        ("k: [1, 2\n", 1, 4, "not closed"),
        ('k: "x\n', 1, 4, "does not end on its line"),
        ("k: 'x\n", 1, 4, "does not end on its line"),
        ('k: "\\q"\n', 1, 4, "bad escape"),
        ("k: 1\n  j: 2\n", 2, 3, "unexpected indentation"),
        ("- a\nk: 1\n", 2, 1, "unexpected indentation"),
        ("k:\n  - a\n  j: 1\n", 3, 3, "unexpected indentation"),
        ("k: 1\n---\nj: 2\n", 2, 1, "a second document"),
        ("k: 1\n...\nj: 2\n", 3, 1, "after the end of the document"),
        ("%YAML 1.2\nk: 1\n", 1, 1, "directives"),
        ("just text\n", 1, 1, "expected `key: value`"),
        ("k: 1\nnot a key\n", 2, 1, "expected `key: value`"),
        ("", 1, 1, "empty"),
        ("# only a comment\n", 1, 1, "empty"),
        ("k:\n  - - a\n", 2, 5, "a sequence directly inside"),
        ("k: 1 2: 3\n", 1, 7, "`:` followed by a space"),
        ('k: "a" b\n', 1, 8, "unexpected text after"),
    ],
)
def test_text_outside_the_subset_is_an_error_at_its_place(
    text: str, line: int, column: int, message: str
) -> None:
    with pytest.raises(YamlError) as info:
        parse(text)
    assert (info.value.line, info.value.column) == (line, column)
    assert message in info.value.message


def test_crlf_and_a_bom_are_read() -> None:
    root = parse("\ufeffk: 1\r\nj: [a, b]\r\n")
    assert to_data(root) == {"k": 1, "j": ["a", "b"]}


def test_quoted_keys_and_a_sequence_at_the_key_indentation() -> None:
    assert to_data(parse('"yes": 1\nk:\n- a\n- b\n')) == {"yes": 1, "k": ["a", "b"]}
