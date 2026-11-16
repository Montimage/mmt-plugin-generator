"""Puts the skill's scripts on ``sys.path``: its eval runner,
``skills/mmt-plugin-generator/evals/run_evals.py``, as ``run_evals``, and its
capture scripts, ``skills/mmt-plugin-generator/scripts/``, as ``make_pcap``
and ``pcap_eval`` (stdlib scripts, not part of the package)."""

from __future__ import annotations

import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parents[3] / "skills" / "mmt-plugin-generator"
EVALS = SKILL / "evals"
SCRIPTS = SKILL / "scripts"
for path in (EVALS, SCRIPTS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
