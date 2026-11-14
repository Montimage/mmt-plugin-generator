"""``docs/behaviour-changes.md`` (T1.6, #15) against the inventory and the
tests: every bug of the inventory's section 5 has a row, every row names a
Java bug or where the change was decided, and every test it names exists."""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DOC = REPO / "docs" / "behaviour-changes.md"
INVENTORY = REPO / "docs" / "legacy" / "java-generator-inventory.md"

#: A table row: ``| # | difference | Java bug | tests |``.
ROW = re.compile(r"^\| (\d+) \| (.+) \| (.+) \| (.+) \|$")
TEST = re.compile(r"`(tests/unit/[\w/]+\.py)::(test_\w+)`")


def rows() -> list[tuple[int, str, str, str]]:
    found = []
    for line in DOC.read_text(encoding="utf-8").splitlines():
        m = ROW.match(line)
        if m:
            found.append((int(m.group(1)), m.group(2), m.group(3), m.group(4)))
    assert found, "no table rows"
    return found


def inventory_bugs() -> set[int]:
    text = INVENTORY.read_text(encoding="utf-8")
    section = text.split("### 5. Bugs and limitations", 1)[1].split("\n### ", 1)[0]
    return {int(n) for n in re.findall(r"^(\d+)\. ", section, re.M)}


def test_rows_are_numbered_in_order() -> None:
    assert [r[0] for r in rows()] == list(range(1, len(rows()) + 1))


def test_every_inventory_bug_has_a_row() -> None:
    bugs = inventory_bugs()
    assert bugs == set(range(1, 26))
    listed = {int(r[2]) for r in rows() if r[2].isdigit()}
    assert listed == bugs


def test_every_row_names_a_bug_or_where_it_was_decided() -> None:
    for number, _, bug, _ in rows():
        assert bug.isdigit() or re.fullmatch(r"\u2013 \(.+\)", bug), (number, bug)


def test_every_named_test_exists() -> None:
    for number, _, _, tests in rows():
        named = TEST.findall(tests)
        assert named, f"row {number} names no test"
        assert len(named) == tests.count("::"), (number, tests)
        for path, name in named:
            source = REPO / path
            assert source.is_file(), (number, path)
            assert re.search(rf"^def {name}\(", source.read_text(encoding="utf-8"), re.M), (
                number,
                path,
                name,
            )
