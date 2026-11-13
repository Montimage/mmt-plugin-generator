"""Golden dumps of the typed model for representative models.

Each ``golden/<name>.json`` is ``mmt_plugin.pdl.dump.dumps`` of the model.
After a deliberate change to the model, regenerate them with
``MMT_UPDATE_GOLDEN=1 uv run pytest tests/unit/pdl/test_golden.py`` and review
the diff.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from mmt_plugin.pdl import parse
from mmt_plugin.pdl.dump import dumps, to_data

ROOT = Path(__file__).parents[3]
GOLDEN = Path(__file__).with_name("golden")

MODELS = {
    "tpkt": "plugins/tpkt_plugin",
    "cotp": "plugins/cotp_plugin",
    "pdl_bitfields": "tests/corpus/models/pdl_bitfields/model.pdl",
    "pdl_expressions": "tests/corpus/models/pdl_expressions/model.pdl",
    "pdl_conditionals": "tests/corpus/models/pdl_conditionals/model.pdl",
    "pdl_classifynext": "tests/corpus/models/pdl_classifynext/model.pdl",
    "pdl_defines": "tests/corpus/models/pdl_defines/model.pdl",
    "pdl_struct_types": "tests/corpus/models/pdl_struct_types/model.pdl",
}


@pytest.mark.parametrize("name", MODELS)
def test_golden(name: str) -> None:
    source = MODELS[name]
    text = (ROOT / source).read_text(encoding="utf-8")
    dumped = dumps(parse(text, filename=source))
    golden = GOLDEN / f"{name}.json"
    if os.environ.get("MMT_UPDATE_GOLDEN") == "1":
        golden.write_text(dumped, encoding="utf-8")
    assert dumped == golden.read_text(encoding="utf-8")
    assert json.loads(dumped)["file"] == source


def test_every_golden_file_is_checked() -> None:
    assert sorted(p.stem for p in GOLDEN.glob("*.json")) == sorted(MODELS)


def test_to_data_rejects_foreign_values() -> None:
    with pytest.raises(TypeError, match="not a model value"):
        to_data(1.5)
