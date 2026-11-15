"""Puts the skill's eval runner, ``skills/mmt-plugin-author/evals/run_evals.py``
(a stdlib script, not part of the package), on ``sys.path`` as ``run_evals``."""

from __future__ import annotations

import sys
from pathlib import Path

EVALS = Path(__file__).resolve().parents[3] / "skills" / "mmt-plugin-author" / "evals"
if str(EVALS) not in sys.path:
    sys.path.insert(0, str(EVALS))
