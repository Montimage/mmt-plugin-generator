"""The mmt-plugin-author skill's evals against a real mmt-dpi SDK (plan T4.2,
#27, "Verify: the evals pass").

Every case of ``skills/mmt-plugin-author/evals/cases/`` runs the whole loop of
the skill's ``SKILL.md``, ``validate``, ``generate``, ``build`` and ``test``,
each with ``--json``, until its last run is green: every packet test passes,
``validate``'s ``parents-exist`` is ``pass``, and every envelope keeps the
contract of ``references/contract.md`` (and the package's JSON Schemas). The
SDK is an extracted mmt-dpi package, a private prefix (never
``/opt/mmt``)::

    MMT_GOLDEN_SDK=<dir>/opt/mmt MMT_GOLDEN_CC=gcc uv run pytest tests/unit/skill/test_sdk.py

Without ``MMT_GOLDEN_SDK`` the tests skip, unless
``MMT_REQUIRE_GOLDEN_COMPILE=1`` (CI's "Generated code" job) makes them fail.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

import run_evals

from .test_evals import CASES, validate_schemas

SDK_ENV = "MMT_GOLDEN_SDK"
CC_ENV = "MMT_GOLDEN_CC"
REQUIRE_ENV = "MMT_REQUIRE_GOLDEN_COMPILE"


def _skip_or_fail(why: str) -> None:
    if os.environ.get(REQUIRE_ENV) == "1":
        pytest.fail(f"{REQUIRE_ENV}=1 but {why}")
    pytest.skip(why)


def _sdk() -> Path:
    prefix = os.environ.get(SDK_ENV, "")
    if not prefix:
        _skip_or_fail(f"{SDK_ENV} is not set (an extracted mmt-dpi prefix)")
    return Path(prefix).resolve()


def _cc() -> str:
    cc = os.environ.get(CC_ENV, "gcc")
    if shutil.which(cc) is None:
        _skip_or_fail(f"{cc} is not installed")
    return cc


@pytest.mark.parametrize("case_dir", CASES, ids=lambda p: p.name)
def test_the_case_goes_green_with_the_sdk(case_dir: Path, tmp_path: Path) -> None:
    sdk, cc = _sdk(), _cc()
    result = run_evals.run_case(case_dir, work=tmp_path, sdk=sdk, cc=cc)
    assert result.problems == []
    assert result.ok
    validate_schemas(result)
    last = max(s.run for s in result.steps)
    assert [s.command for s in result.steps if s.run == last] == list(run_evals.LOOP_COMMANDS)
    # Every loop run that is not the last one stopped on a failure.
    for n in range(1, last):
        assert any(s.run == n and s.returncode != 0 for s in result.steps), n
