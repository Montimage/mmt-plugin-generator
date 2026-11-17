"""Every packet test the user documentation shows loads as one (#29).

A ``yaml`` block of a user doc whose first line is ``schema: 1`` is a packet
test or a session test (#99): ``mmt-plugin test`` must read it
(``testing/packets.py`` and ``testing/session.py``, through the corpus YAML
subset of ``testing/yamlsubset.py``), and the guide's packet test must be
the one ``init demo --id 960 --parent udp:dport=4433`` writes, which it says
passes as it is. The guide's ``plugin.yaml`` is that ``init``'s too (#65).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mmt_plugin.commands.init import _model_text, _test_text, parent_of_selector, parse_selector
from mmt_plugin.sdk.profile import DATA_TYPE_GROUP, get_bundled
from mmt_plugin.testing.packets import PacketTest, PacketTestError
from mmt_plugin.testing.session import SessionTest, load_test

from .mdtext import ROOT, Block, blocks
from .test_commands import USER_DOCS

GUIDE = "docs/user-guide.md"


def _data_types() -> set[str]:
    profile = get_bundled("1.10.2")
    assert profile is not None
    return {c.name for c in profile.constants if c.group == DATA_TYPE_GROUP}


def packet_blocks(text: str) -> list[Block]:
    """The ``yaml`` blocks of ``text`` whose first non-empty line is ``schema: 1``."""
    found = []
    for block in blocks(text):
        lines = [line for line in block.text.splitlines() if line.strip()]
        if block.info == "yaml" and lines and lines[0].strip() == "schema: 1":
            found.append(block)
    return found


def _load(block: Block, tmp_path: Path, shown: str) -> PacketTest | SessionTest:
    path = tmp_path / f"line{block.line}.yaml"
    path.write_text(block.text, encoding="utf-8")
    return load_test(path, shown, _data_types())


def _is_session(block: Block) -> bool:
    return "\nsession:\n" in block.text


@pytest.mark.parametrize("page", USER_DOCS)
def test_every_packet_test_example_loads(page: str, tmp_path: Path) -> None:
    text = (ROOT / page).read_text(encoding="utf-8")
    for block in packet_blocks(text):
        _load(block, tmp_path, f"{page}:{block.line}")


def test_the_guide_shows_a_packet_test_and_a_session_test(tmp_path: Path) -> None:
    found = packet_blocks((ROOT / GUIDE).read_text(encoding="utf-8"))
    kinds = [type(_load(b, tmp_path, f"{GUIDE}:{b.line}")) for b in found]
    assert kinds == [PacketTest, SessionTest]
    assert [_is_session(b) for b in found] == [False, True]


def test_the_guides_packet_test_is_the_one_init_writes() -> None:
    blocks_ = packet_blocks((ROOT / GUIDE).read_text(encoding="utf-8"))
    (block,) = [b for b in blocks_ if not _is_session(b)]
    text = _test_text("demo", 960, "udp:dport=4433")
    written = "".join(line for line in text.splitlines(keepends=True) if line[:1] != "#")
    assert block.text == written


def test_the_guides_model_is_the_one_init_writes() -> None:
    # The guide's `init demo --id 960 --parent udp:dport=4433 --sdk-profile 1.10.2`.
    text = (ROOT / GUIDE).read_text(encoding="utf-8")
    assert "mmt-plugin init demo --id 960 --parent udp:dport=4433 --sdk-profile 1.10.2" in text
    parent = parent_of_selector(parse_selector("udp:dport=4433"))
    written = _model_text("demo", 960, "1.10.2", parent)
    models = [b for b in blocks(text) if b.info == "yaml" and "\nprotocol:\n" in b.text]
    assert [b.text for b in models] == [written]


def test_a_flow_mapping_attribute_does_not_load(tmp_path: Path) -> None:
    text = (
        'schema: 1\nid: "demo/basic"\nbytes:\n  - "01"\nexpect:\n'
        '  protocol: "DEMO"\n  proto_id: 960\n  next:\n    kind: "none"\n  attributes:\n'
        '    - {name: "version", type: "MMT_U8_DATA", offset: 0, length: 1, value: 1}\n'
    )
    (block,) = packet_blocks(f"```yaml\n{text}```\n")
    with pytest.raises(PacketTestError):
        _load(block, tmp_path, "example")
