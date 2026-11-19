"""Shared helpers for the PDL parser tests: building small models and parsing them."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from mmt_plugin.diagnostics import Diagnostic
from mmt_plugin.pdl import Model, PdlSyntaxError, parse

#: The name the tests give their inline models.
FILE = "test.pdl"

Build = Callable[..., str]
Parse = Callable[[str], Model]
Errors = Callable[[str], tuple[Diagnostic, ...]]


def build(
    attributes: str = "",
    *,
    defines: str = "",
    properties: str = 'label = "p"\n\t\tid = "960"',
    classify: str = "",
) -> str:
    """A whole model around the given parts, one part per block."""
    return (
        "Protocol {\n"
        f"{defines}"
        f"\tProperties {{\n\t\t{properties}\n\t}}\n"
        f"\tAttributes {{\n{attributes}\n\t}}\n"
        f"{classify}"
        "}\n"
    )


def parse_ok(text: str) -> Model:
    """Parse ``text``, which must be a valid model."""
    return parse(text, filename=FILE)


def errors_of(text: str) -> tuple[Diagnostic, ...]:
    """The diagnostics of ``text``, which must not parse; each has a hint."""
    with pytest.raises(PdlSyntaxError) as caught:
        parse(text, filename=FILE)
    diagnostics = caught.value.diagnostics
    assert diagnostics
    for d in diagnostics:
        assert d.hint, f"{d.code} has no hint"
        assert d.location is not None and d.location.file == FILE
    return diagnostics


@pytest.fixture
def model() -> Build:
    """``build``, as a fixture."""
    return build


@pytest.fixture
def ok() -> Parse:
    """``parse_ok``, as a fixture."""
    return parse_ok


@pytest.fixture
def errors() -> Errors:
    """``errors_of``, as a fixture."""
    return errors_of
