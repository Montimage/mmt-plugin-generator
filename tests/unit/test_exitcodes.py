"""Tests for ``mmt_plugin.exitcodes``."""

from __future__ import annotations

import pytest

from mmt_plugin.exitcodes import ExitCode, for_class


def test_exit_codes_are_the_documented_ones() -> None:
    assert {c.error_class: int(c) for c in ExitCode} == {
        "success": 0,
        "internal": 1,
        "usage": 2,
        "model": 3,
        "sdk": 4,
        "build": 5,
        "test": 6,
        "state": 7,
        "interrupted": 130,
    }


def test_every_code_has_a_meaning() -> None:
    assert all(code.meaning for code in ExitCode)


@pytest.mark.parametrize("code", [c for c in ExitCode if c is not ExitCode.SUCCESS])
def test_for_class_round_trips(code: ExitCode) -> None:
    assert for_class(code.error_class) is code


@pytest.mark.parametrize("name", ["success", "bogus", ""])
def test_for_class_rejects_non_error_classes(name: str) -> None:
    with pytest.raises(ValueError):
        for_class(name)
