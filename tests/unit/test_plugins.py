"""``mmt_plugin.plugins``: resolving plugin.yaml's ``plugins`` into the
plugins to load, in order. ``tests/unit/packettest/test_command.py`` covers
the errors through ``mmt-plugin test``."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from mmt_plugin.pdl import Model
from mmt_plugin.plugins import NamedPlugin, PluginError, resolve
from mmt_plugin.pluginyaml import load


def _project(directory: Path, label: str, *plugins: str) -> Path:
    directory.mkdir(parents=True)
    named = "".join(f'  - "{p}"\n' for p in plugins)
    (directory / "plugin.yaml").write_text(
        f"schema: 1\nprotocol:\n  label: {label}\n  id: 990\n"
        + (f"plugins:\n{named}" if plugins else "")
    )
    return directory


def _read(path: Path) -> Model:
    return load(path.read_text(), filename=str(path)).model


def _resolve(project: Path) -> list[NamedPlugin]:
    return resolve(_read(project / "plugin.yaml"), project, str, _read)


def test_a_plugin_two_projects_need_loads_once_before_both(tmp_path: Path) -> None:
    _project(tmp_path / "base", "base")
    _project(tmp_path / "left", "left", "../base")
    _project(tmp_path / "right", "right", "../base")
    child = _project(tmp_path / "child", "child", "../left", "../right")
    found = _resolve(child)
    assert [p.label for p in found] == ["base", "left", "right"]
    assert found[0] == NamedPlugin(
        tmp_path / "base" / "build" / "mmtp_base.so",
        tmp_path / "base",
        tmp_path / "base" / "plugin.yaml",
        "base",
        990,
    )


def test_a_project_and_its_built_file_are_one_plugin(tmp_path: Path) -> None:
    parent = _project(tmp_path / "parent", "parent")
    (parent / "build").mkdir()
    (parent / "build" / "mmtp_parent.so").write_text("")
    child = _project(tmp_path / "child", "child", "../parent", "../parent/build/mmtp_parent.so")
    assert [p.project for p in _resolve(child)] == [parent]


def test_a_symbolic_link_to_a_project_is_that_project(tmp_path: Path) -> None:
    parent = _project(tmp_path / "parent", "parent")
    os.symlink(parent, tmp_path / "alias")
    child = _project(tmp_path / "child", "child", "../parent", "../alias")
    with pytest.raises(PluginError, match="named twice"):
        _resolve(child)


def test_a_model_without_plugins_names_none(tmp_path: Path) -> None:
    child = _project(tmp_path / "child", "child")
    assert _resolve(child) == []
