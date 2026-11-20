"""``mmt-plugin validate``: one test per check, each status and exit code,
including the load-order and duplicate-name pitfalls of #2
(``docs/design/cli.md``, sections 4, 5, 6 and 10).

The SDK is a fake prefix (``mmt_log.h`` and a ``VERSION`` macro) and the
run-time registry a stub reader, so no mmt-dpi is needed;
``tests/unit/test_sdk_registry.py`` covers the real reader.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from mmt_plugin import schemas
from mmt_plugin.cli import main
from mmt_plugin.commands import validate as validate_module
from mmt_plugin.commands.validate import (
    CHECKS,
    Collation,
    ValidateCommand,
    collations,
    load_order,
    parents_check,
    parents_exist,
    plugin_file,
)
from mmt_plugin.sdk.detect import Sdk
from mmt_plugin.sdk.profile import get_bundled
from mmt_plugin.sdk.registry import RegisteredProtocol, Registry, RegistryError
from mmt_plugin.sdk.resolve import ProfileChoice, ProfileSource
from mmt_plugin.ui.streams import ColorTier, StreamStyle

Run = Callable[..., tuple[int, dict[str, Any]]]


def model_text(label: str = "contract", pid: int = 990, attribute: str = "kind") -> str:
    return f"""Protocol {{
    Properties {{ label = "{label}" id = "{pid}" encoding = "network" }}
    Attributes {{
        attribute {{ alias="{attribute}" data_type="MMT_U8_DATA" data_len="1" offset="0"
            scope="packet" }}
    }}
}}
"""


#: Two attributes with the same name, case-insensitively.
DUPLICATE = """Protocol {
    Properties { label = "contract" id = "990" encoding = "network" }
    Attributes {
        attribute { alias="kind" data_type="MMT_U8_DATA" data_len="1" offset="0" scope="packet" }
        attribute { alias="KIND" data_type="MMT_U8_DATA" data_len="1" offset="1" scope="packet" }
    }
}
"""

#: The SDK's own plugins, as a registry reader would see them.
SDK_PLUGINS = ("libmmt_tcpip.so", "libmmt_tdicom.so")


def registry(*protocols: tuple[int, str], plugins: Sequence[str] = SDK_PLUGINS) -> Registry:
    return Registry(
        "/sdk/plugins",
        tuple(plugins),
        tuple(RegisteredProtocol(pid, name) for pid, name in protocols),
    )


class Reader:
    """A stub registry reader: returns ``result`` (or raises it) and records
    its calls."""

    def __init__(self, result: Registry | RegistryError) -> None:
        self.result = result
        self.calls: list[dict[str, Any]] = []

    def __call__(self, sdk: Sdk, **kwargs: Any) -> Registry:
        self.calls.append({"sdk": sdk, **kwargs})
        if isinstance(self.result, RegistryError):
            raise self.result
        return self.result


@pytest.fixture
def sdk_prefix(tmp_path: Path) -> Path:
    """A fake mmt-dpi 1.10.2 prefix."""
    prefix = tmp_path / "sdk"
    include = prefix / "dpi" / "include"
    include.mkdir(parents=True)
    (include / "mmt_log.h").write_text("/* log */\n")
    (include / "mmt_core.h").write_text('#define VERSION "1.10.2"\n')
    return prefix


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The current directory, with ``model.pdl``; no SDK in the environment."""
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.chdir(work)
    for name in ("MMT_PLUGIN_SDK_PROFILE", "MMT_BASE", "PKG_CONFIG_PATH", "PKG_CONFIG_LIBDIR"):
        monkeypatch.delenv(name, raising=False)
    (work / "model.pdl").write_text(model_text())
    return work


@pytest.fixture
def reader() -> Reader:
    return Reader(registry((354, "tcp"), (625, "ndn")))


C_ONLY: list[Collation] = [("C", lambda s: s.encode())]


def make_command(tmp_path: Path, reader: Reader, orders: Sequence[Collation] = C_ONLY) -> Any:
    return ValidateCommand(
        pkg_config_dirs=[],
        default_prefix=str(tmp_path / "no-sdk"),
        registry_reader=reader,
        orders=lambda: orders,
    )


@pytest.fixture
def run(tmp_path: Path, reader: Reader, capsys: pytest.CaptureFixture[str], project: Path) -> Run:
    """Run ``mmt-plugin --json validate ARGS``; the exit code and the envelope,
    checked against the envelope and result schemas."""
    envelope = Draft202012Validator(schemas.load_cli_schema(schemas.ENVELOPE))
    result = Draft202012Validator(schemas.result_schema("validate"))

    def go(*args: str, command: Any = None) -> tuple[int, dict[str, Any]]:
        cmd = make_command(tmp_path, reader) if command is None else command
        code = main(["--json", "validate", *args], commands=[cmd])
        out = capsys.readouterr()
        assert out.err == ""
        doc: dict[str, Any] = json.loads(out.out)
        envelope.validate(doc)
        assert doc["exit_code"] == code
        if doc["result"] is not None:
            result.validate(doc["result"])
        return code, doc

    return go


def statuses(doc: dict[str, Any]) -> dict[str, str]:
    return {c["id"]: c["status"] for c in doc["result"]["checks"]}


def detail(doc: dict[str, Any], check: str) -> str:
    return next(str(c["detail"]) for c in doc["result"]["checks"] if c["id"] == check)


def codes(doc: dict[str, Any]) -> list[str]:
    return [d["code"] for d in doc["diagnostics"]]


# --- a clean model -----------------------------------------------------------


def test_a_clean_model_passes_every_check(run: Run, sdk_prefix: Path, reader: Reader) -> None:
    code, doc = run("model.pdl", "--sdk", str(sdk_prefix))
    assert code == 0, doc["error"]
    assert [c["id"] for c in doc["result"]["checks"]] == list(CHECKS)
    assert statuses(doc) == {
        "schema": "pass",
        "semantics": "pass",
        "sdk-profile": "pass",
        "id-free": "pass",
        "name-free": "pass",
        "parents-exist": "skip",
        "load-order": "pass",
        "id-range": "pass",
    }
    assert doc["result"]["model"] == "model.pdl"
    assert doc["result"]["format"] == "pdl"
    assert doc["result"]["protocol"] == {"label": "contract", "name": "CONTRACT", "id": 990}
    assert detail(doc, "sdk-profile") == "1.10.2 (--sdk)"
    assert detail(doc, "id-free") == "990: not in SDK 1.10.2 or 2 installed plugins"
    assert detail(doc, "semantics") == "1 attribute, 0 structs"
    assert doc["context"]["sdk"]["prefix"] == str(sdk_prefix)
    assert doc["diagnostics"] == []
    # The registry is read without the plugin's own file, so an installed
    # copy of it does not take its own id and name.
    (call,) = reader.calls
    assert call["exclude"] == "mmtp_contract.so"
    assert call["max_id"] == 1000
    assert call["sdk"].prefix == str(sdk_prefix)


def test_the_sdk_comes_from_mmt_base(
    run: Run, sdk_prefix: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MMT_BASE", str(sdk_prefix))
    code, doc = run("model.pdl")
    assert code == 0
    assert detail(doc, "sdk-profile") == "1.10.2 (MMT_BASE)"


def test_a_pinned_profile_is_reported_with_its_source(run: Run, sdk_prefix: Path) -> None:
    code, doc = run("model.pdl", "--sdk", str(sdk_prefix), "--sdk-profile", "1.10.2")
    assert code == 0
    assert detail(doc, "sdk-profile") == "1.10.2 (--sdk-profile)"


def test_stdin_is_read_as_pdl(
    run: Run, sdk_prefix: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    stdin = tmp_path / "stdin.pdl"
    stdin.write_text(model_text())
    with stdin.open("rb") as f:
        monkeypatch.setattr("sys.stdin", type("S", (), {"buffer": f})())
        code, doc = run("-", "--sdk", str(sdk_prefix))
    assert code == 0
    assert doc["result"]["model"] == "<stdin>"


# --- schema and semantics ----------------------------------------------------


def test_a_syntax_error_fails_schema_and_skips_the_rest(
    run: Run, project: Path, sdk_prefix: Path, reader: Reader
) -> None:
    (project / "model.pdl").write_text("Protocol { Properties {")
    code, doc = run("model.pdl", "--sdk", str(sdk_prefix))
    assert code == 3
    assert doc["error"]["code"].startswith("model.syntax.")
    assert doc["result"]["protocol"] is None
    assert statuses(doc) == {"schema": "fail", **{c: "skip" for c in CHECKS[1:]}}
    assert detail(doc, "id-free") == "the model does not parse"
    assert reader.calls == []


def test_a_semantic_error_fails_semantics(run: Run, project: Path, sdk_prefix: Path) -> None:
    (project / "model.pdl").write_text(DUPLICATE)
    code, doc = run("model.pdl", "--sdk", str(sdk_prefix))
    assert code == 3
    assert doc["error"]["code"] == "model.duplicate-name"
    assert doc["error"]["message"] == "1 error in model.pdl (semantics failed)"
    assert statuses(doc)["semantics"] == "fail"
    assert detail(doc, "semantics") == "1 error (model.duplicate-name)"
    # The SDK checks still run: the label and the id are known.
    assert statuses(doc)["id-free"] == "pass"


def test_a_plugin_yaml_schema_error_fails_schema(run: Run, project: Path) -> None:
    (project / "plugin.yaml").write_text("schema: 1\nprotocol:\n  label: x\n  id: '960'\n")
    code, doc = run("--no-sdk")
    assert code == 3
    assert doc["error"]["code"] == "model.schema"
    assert statuses(doc)["schema"] == "fail"
    assert detail(doc, "schema") == "plugin.yaml: plugin.yaml schema 1"
    assert doc["result"]["format"] == "yaml"
    (diagnostic,) = [d for d in doc["diagnostics"] if d["severity"] == "error"]
    assert diagnostic["code"] == "model.schema"
    assert diagnostic["location"] == {
        "file": "plugin.yaml",
        "line": 4,
        "column": 7,
        "end_line": 4,
        "end_column": 12,
    }


def test_a_plugin_yaml_model_validates_with_its_parents(
    run: Run, project: Path, sdk_prefix: Path
) -> None:
    (project / "plugin.yaml").write_text(
        "schema: 1\nprotocol:\n  label: yamlproto\n  id: 960\n  encoding: network\n"
        "sdk:\n  profile: '1.10.2'\nparents:\n  - protocol: udp\n  - protocol: Ethernet\n"
        "attributes:\n  - name: kind\n    type: MMT_U8_DATA\n    offset: 0\n"
    )
    code, doc = run("--sdk", str(sdk_prefix))
    assert code == 0, doc["error"]
    assert detail(doc, "schema") == "plugin.yaml, schema 1"
    assert statuses(doc)["parents-exist"] == "pass"
    assert detail(doc, "parents-exist") == "udp, Ethernet"
    assert doc["context"]["sdk"]["profile_source"] == "plugin.yaml"
    (project / "plugin.yaml").write_text(
        (project / "plugin.yaml").read_text().replace("protocol: udp", "protocol: nope")
    )
    code, doc = run("--sdk", str(sdk_prefix))
    assert code == 3
    assert doc["error"]["code"] == "model.unknown-parent"
    assert statuses(doc)["parents-exist"] == "fail"


def test_a_missing_model_is_unreadable(run: Run) -> None:
    code, doc = run("nope.pdl", "--no-sdk")
    assert code == 3
    assert doc["error"]["code"] == "model.unreadable"


# --- sdk-profile, --no-sdk ---------------------------------------------------


def test_without_an_sdk_validate_exits_4(run: Run, reader: Reader) -> None:
    code, doc = run("model.pdl")
    assert code == 4
    assert doc["error"]["code"] == "sdk.not-found"
    s = statuses(doc)
    assert s["sdk-profile"] == "fail"
    assert s["schema"] == s["semantics"] == "pass"
    assert s["id-free"] == s["name-free"] == "skip"
    assert detail(doc, "id-free").startswith("no SDK: 990 not in SDK 1.10.2")
    # The profile's "no SDK" warning is not added to the SDK error.
    assert "sdk.profile-default" not in codes(doc)
    assert reader.calls == []


def test_an_invalid_sdk_prefix_exits_4(run: Run, tmp_path: Path) -> None:
    code, doc = run("model.pdl", "--sdk", str(tmp_path))
    assert code == 4
    assert doc["error"]["code"] == "sdk.invalid-prefix"
    assert statuses(doc)["sdk-profile"] == "fail"


def test_an_unknown_profile_exits_4(run: Run, sdk_prefix: Path) -> None:
    code, doc = run("model.pdl", "--sdk", str(sdk_prefix), "--sdk-profile", "0.1")
    assert code == 4
    assert doc["error"]["code"] == "sdk.profile-not-found"
    s = statuses(doc)
    assert s["sdk-profile"] == "fail"
    assert s["semantics"] == s["id-free"] == s["name-free"] == "skip"


def test_no_sdk_skips_the_sdk_checks(run: Run, reader: Reader) -> None:
    code, doc = run("model.pdl", "--no-sdk", "--sdk-profile", "1.10.2")
    assert code == 0, doc["error"]
    s = statuses(doc)
    assert s["sdk-profile"] == "pass"
    assert s["id-free"] == s["name-free"] == s["parents-exist"] == "skip"
    assert s["load-order"] == s["id-range"] == "pass"
    assert detail(doc, "sdk-profile") == "1.10.2 (--sdk-profile), --no-sdk"
    assert detail(doc, "id-free") == (
        "--no-sdk: 990 not in SDK 1.10.2; installed plugins not checked"
    )
    assert doc["context"]["sdk"]["prefix"] is None
    assert reader.calls == []


def test_no_sdk_without_a_pin_warns_on_the_default_profile(run: Run) -> None:
    code, doc = run("model.pdl", "--no-sdk")
    assert code == 0
    assert statuses(doc)["sdk-profile"] == "warn"
    assert "sdk.profile-default" in codes(doc)
    code, doc = run("model.pdl", "--no-sdk", "--strict")
    assert code == 4
    assert doc["error"]["code"] == "sdk.profile-default"


def test_no_sdk_still_fails_on_a_conflict_the_profile_shows(run: Run, project: Path) -> None:
    (project / "model.pdl").write_text(model_text(pid=625))
    code, doc = run("model.pdl", "--no-sdk", "--sdk-profile", "1.10.2")
    assert code == 3
    assert statuses(doc)["id-free"] == "fail"


def test_no_sdk_and_sdk_conflict(run: Run, sdk_prefix: Path) -> None:
    code, doc = run("model.pdl", "--no-sdk", "--sdk", str(sdk_prefix))
    assert code == 2
    assert doc["error"]["code"] == "usage.conflicting-options"


# --- id-free -----------------------------------------------------------------


def test_an_id_in_the_sdk_headers_is_taken(run: Run, project: Path, sdk_prefix: Path) -> None:
    # 628 was free when the NDN example took it, then became PROTO_ORACLE (#2).
    (project / "model.pdl").write_text(model_text(pid=628))
    code, doc = run("model.pdl", "--sdk", str(sdk_prefix))
    assert code == 3
    assert doc["error"]["code"] == "model.id-taken"
    assert statuses(doc)["id-free"] == "fail"
    assert "PROTO_ORACLE" in detail(doc, "id-free")
    assert codes(doc).count("model.id-taken") == 1


def test_an_id_an_installed_plugin_registers_is_taken(
    run: Run, sdk_prefix: Path, tmp_path: Path
) -> None:
    # Not in any SDK header: only the run-time registry knows it.
    reader = Reader(registry((354, "tcp"), (990, "other_plugin"), plugins=("other.so",)))
    code, doc = run("model.pdl", "--sdk", str(sdk_prefix), command=make_command(tmp_path, reader))
    assert code == 3
    assert doc["error"]["code"] == "model.id-taken"
    assert statuses(doc)["id-free"] == "fail"
    assert statuses(doc)["name-free"] == "pass"
    (diag,) = (d for d in doc["diagnostics"] if d["code"] == "model.id-taken")
    assert (
        diag["message"] == 'protocol id 990 is already registered at run time, by "other_plugin"'
    )
    assert diag["location"]["file"] == "model.pdl"
    assert diag["location"]["line"] == 2
    assert "other.so" in diag["related"][0]["message"]


# --- name-free ---------------------------------------------------------------


def test_a_name_in_the_sdk_headers_is_taken_case_insensitively(
    run: Run, project: Path, sdk_prefix: Path
) -> None:
    # The NDN example's first name, "NDN", is the built-in ndn's (#2).
    (project / "model.pdl").write_text(model_text(label="Ndn"))
    code, doc = run("model.pdl", "--sdk", str(sdk_prefix))
    assert code == 3
    assert doc["error"]["code"] == "model.name-taken"
    assert statuses(doc)["name-free"] == "fail"
    assert statuses(doc)["id-free"] == "pass"


def test_a_name_an_installed_plugin_registers_is_taken_case_insensitively(
    run: Run, sdk_prefix: Path, tmp_path: Path
) -> None:
    # The duplicate-name pitfall: mmt-dpi silently ignores a second plugin
    # registering a name, whatever its case.
    reader = Reader(registry((970, "Contract"), plugins=("other.so",)))
    code, doc = run("model.pdl", "--sdk", str(sdk_prefix), command=make_command(tmp_path, reader))
    assert code == 3
    assert doc["error"]["code"] == "model.name-taken"
    assert statuses(doc)["name-free"] == "fail"
    assert statuses(doc)["id-free"] == "pass"
    (diag,) = (d for d in doc["diagnostics"] if d["code"] == "model.name-taken")
    assert "by id 970" in diag["message"]
    assert diag["location"]["line"] == 2


def test_both_conflicts_list_both_checks(run: Run, project: Path, sdk_prefix: Path) -> None:
    (project / "model.pdl").write_text(model_text(label="tpkt", pid=636))
    code, doc = run("model.pdl", "--sdk", str(sdk_prefix))
    assert code == 3
    assert doc["error"]["code"] == "model.id-taken"
    assert doc["error"]["message"] == "2 errors in model.pdl (id-free, name-free failed)"


# --- the registry cannot be read ---------------------------------------------


def test_an_unreadable_registry_is_a_warning(run: Run, sdk_prefix: Path, tmp_path: Path) -> None:
    reader = Reader(RegistryError("init_extraction() failed with the plugins of /sdk/plugins"))
    command = make_command(tmp_path, reader)
    code, doc = run("model.pdl", "--sdk", str(sdk_prefix), command=command)
    assert code == 0
    assert statuses(doc)["id-free"] == statuses(doc)["name-free"] == "warn"
    assert detail(doc, "id-free") == "990: not in SDK 1.10.2; installed plugins not read"
    assert codes(doc) == ["sdk.registry-unavailable"]
    code, doc = run("model.pdl", "--sdk", str(sdk_prefix), "--strict", command=command)
    assert code == 4
    assert doc["error"]["code"] == "sdk.registry-unavailable"


# --- parents-exist -----------------------------------------------------------


def test_parents_exist_in_the_profile_or_the_registry() -> None:
    profile = get_bundled("1.10.2")
    assert profile is not None
    reg = registry((990, "my_parent"))
    assert parents_exist(["tcp", "UDP", "ndn"], profile, None) == (["tcp", "UDP", "ndn"], [])
    assert parents_exist(["my_parent", "nosuch"], profile, None) == ([], ["my_parent", "nosuch"])
    assert parents_exist(["My_Parent", "nosuch"], profile, reg) == (["My_Parent"], ["nosuch"])


def test_parents_check_statuses() -> None:
    profile = get_bundled("1.10.2")
    assert profile is not None
    choice = ProfileChoice(profile, ProfileSource.CLI)
    reg = registry()
    none = parents_check((), choice, reg, None)
    assert (none.status, none.detail) == ("skip", "the model declares no parent protocol")
    ok = parents_check(["tcp"], choice, reg, None)
    assert (ok.status, ok.detail, ok.error) == ("pass", "tcp", None)
    bad = parents_check(["tcp", "nosuch"], choice, reg, None)
    assert bad.status == "fail"
    assert bad.error is not None and bad.error.code == "model.unknown-parent"
    assert bad.detail == "parent protocol nosuch is not in the SDK"
    skipped = parents_check(["tcp"], choice, None, "--no-sdk")
    assert (skipped.status, skipped.detail) == ("skip", "--no-sdk: tcp in SDK 1.10.2")
    assert parents_check(["tcp"], None, None, "no SDK").status == "skip"


def test_parents_check_with_named_projects() -> None:
    # #146: a parent that is a named project's label exists without an SDK
    # registry or an installed copy.
    profile = get_bundled("1.10.2")
    assert profile is not None
    choice = ProfileChoice(profile, ProfileSource.CLI)
    projects = {"websocket_example": "../websocket"}
    only = parents_check(["WebSocket_Example"], choice, None, "--no-sdk", projects)
    assert (only.status, only.detail) == ("pass", "WebSocket_Example (../websocket)")
    mixed = parents_check(["tcp", "websocket_example"], choice, None, "--no-sdk", projects)
    assert (mixed.status, mixed.detail) == (
        "skip",
        "--no-sdk: tcp in SDK 1.10.2; websocket_example (../websocket)",
    )
    ok = parents_check(["tcp", "websocket_example"], choice, registry(), None, projects)
    assert (ok.status, ok.detail) == ("pass", "tcp, websocket_example (../websocket)")
    bad = parents_check(["websocket_example"], choice, None, "--no-sdk", {})
    assert bad.status == "fail"
    assert bad.error is not None and bad.error.code == "model.unknown-parent"
    assert "plugins" in bad.error.hint


def plugin_yaml(label: str, *parents: str, plugins: Sequence[str] = ()) -> str:
    """A plugin.yaml model, with ``parents`` (no classify) and ``plugins``."""
    text = (
        f"schema: 1\nprotocol:\n  label: {label}\n  id: 960\n  encoding: network\n"
        "sdk:\n  profile: '1.10.2'\n"
        "attributes:\n  - name: kind\n    type: MMT_U8_DATA\n    offset: 0\n"
    )
    if parents:
        text += "parents:\n" + "".join(f"  - protocol: {p}\n" for p in parents)
    if plugins:
        text += "plugins:\n" + "".join(f'  - "{p}"\n' for p in plugins)
    return text


def write_project(directory: Path, label: str, *parents: str, plugins: Sequence[str] = ()) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "plugin.yaml").write_text(plugin_yaml(label, *parents, plugins=plugins))
    return directory


def test_a_plugin_parent_exists_from_its_named_project_with_no_sdk(
    run: Run, project: Path, reader: Reader
) -> None:
    # AC1: the parent's project is named under plugins; it is not built and
    # not installed, and there is no SDK.
    write_project(project / "websocket", "websocket_example", "tcp")
    write_project(project, "yamlchild", "websocket_example", plugins=["websocket"])
    code, doc = run("--no-sdk")
    assert code == 0, doc["error"]
    assert statuses(doc)["parents-exist"] == "pass"
    assert detail(doc, "parents-exist") == "websocket_example (websocket)"
    assert statuses(doc)["load-order"] == "pass"
    assert detail(doc, "load-order") == (
        "mmtp_yamlchild.so after libmmt_tcpip.so, mmtp_websocket_example.so (C)"
    )
    assert not (project / "websocket" / "build").exists()
    assert reader.calls == []
    # Without the entry, the same parent is unknown.
    write_project(project, "yamlchild", "websocket_example")
    code, doc = run("--no-sdk")
    assert code == 3
    assert doc["error"]["code"] == "model.unknown-parent"
    assert detail(doc, "parents-exist") == (
        "parent protocol websocket_example is not in the SDK profile 1.10.2"
    )


def test_a_plugin_parent_exists_from_its_project_without_an_installed_copy(
    run: Run, project: Path, sdk_prefix: Path, reader: Reader
) -> None:
    # The registry (the installed plugins) does not have the parent.
    write_project(project / "websocket", "websocket_example", "tcp")
    write_project(project, "yamlchild", "tcp", "websocket_example", plugins=["websocket"])
    code, doc = run("--sdk", str(sdk_prefix))
    assert code == 0, doc["error"]
    assert statuses(doc)["parents-exist"] == "pass"
    assert detail(doc, "parents-exist") == "tcp, websocket_example (websocket)"
    assert len(reader.calls) == 1


def test_a_parent_project_a_named_project_names_counts(run: Run, project: Path) -> None:
    # The plugins a named project names load too: their labels are parents.
    write_project(project / "base", "base_example", "tcp")
    write_project(project / "mid", "mid_example", "base_example", plugins=["../base"])
    write_project(project, "yamlchild", "base_example", "mid_example", plugins=["mid"])
    code, doc = run("--no-sdk")
    assert code == 0, doc["error"]
    assert detail(doc, "parents-exist") == "base_example (base), mid_example (mid)"
    assert detail(doc, "load-order") == (
        "mmtp_yamlchild.so after libmmt_tcpip.so, mmtp_base_example.so, mmtp_mid_example.so (C)"
    )


def test_a_plugin_entry_validate_cannot_use_fails_parents_exist(run: Run, project: Path) -> None:
    write_project(project, "yamlchild", "websocket_example", plugins=["nosuch"])
    code, doc = run("--no-sdk")
    assert code == 3
    assert doc["error"]["code"] == "model.bad-plugin"
    assert [c["id"] for c in doc["result"]["checks"]] == list(CHECKS)
    assert statuses(doc)["parents-exist"] == "fail"
    assert detail(doc, "parents-exist").startswith("plugins: nosuch not found")
    (bad,) = [d for d in doc["diagnostics"] if d["code"] == "model.bad-plugin"]
    assert bad["location"]["file"] == "plugin.yaml"
    assert bad["location"]["line"] == 15  # the entry
    # load-order still checks libmmt_tcpip.so.
    assert statuses(doc)["load-order"] == "pass"
    assert detail(doc, "load-order") == "mmtp_yamlchild.so after libmmt_tcpip.so (C)"
    # Also when the model has no parents.
    write_project(project, "yamlchild", plugins=["nosuch"])
    code, doc = run("--no-sdk")
    assert code == 3
    assert doc["error"]["code"] == "model.bad-plugin"
    assert statuses(doc)["parents-exist"] == "fail"


def test_plugin_entries_are_relative_to_the_model_file(
    run: Run, project: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # MODEL in another directory: its entries are relative to that one.
    other = tmp_path / "other"
    write_project(other / "websocket", "websocket_example", "tcp")
    write_project(other / "child", "yamlchild", "websocket_example", plugins=["../websocket"])
    code, doc = run(str(other / "child" / "plugin.yaml"), "--no-sdk")
    assert code == 0, doc["error"]
    assert detail(doc, "parents-exist") == f"websocket_example ({other / 'websocket'})"
    # MODEL from stdin: relative to the project directory.
    write_project(project / "websocket", "websocket_example", "tcp")
    stdin = tmp_path / "stdin.yaml"
    stdin.write_text(plugin_yaml("yamlchild", "websocket_example", plugins=["websocket"]))
    with stdin.open("rb") as f:
        monkeypatch.setattr("sys.stdin", type("S", (), {"buffer": f})())
        code, doc = run("-", "--model-format", "yaml", "--no-sdk")
    assert code == 0, doc["error"]
    assert detail(doc, "parents-exist") == "websocket_example (websocket)"


# --- load-order --------------------------------------------------------------


def test_the_plugin_file_is_mmtp_label() -> None:
    assert plugin_file("TPKT") == "mmtp_tpkt.so"


def test_load_order_in_the_c_locale() -> None:
    # #2: a plugin loaded before libmmt_tcpip.so registers, but its parents
    # do not exist yet, so it never classifies a packet.
    assert load_order("aaa_ndn.so", C_ONLY) == (
        False,
        "aaa_ndn.so sorts before libmmt_tcpip.so (C)",
    )
    # Upper case sorts before "l" in the C locale.
    assert load_order("Ndn_example.so", C_ONLY)[0] is False
    assert load_order("ndn_example.so", C_ONLY) == (
        True,
        "ndn_example.so after libmmt_tcpip.so (C)",
    )
    assert load_order("mmtp_tpkt.so", C_ONLY)[0] is True


def test_load_order_in_every_collation() -> None:
    # A locale where "N" sorts after "l" (case-insensitive): fine there, not
    # in C. Both must hold.
    folded: Collation = ("en_US.UTF-8", lambda s: s.casefold())
    assert load_order("Ndn_example.so", [folded]) == (
        True,
        "Ndn_example.so after libmmt_tcpip.so (en_US.UTF-8)",
    )
    assert load_order("Ndn_example.so", [*C_ONLY, folded]) == (
        False,
        "Ndn_example.so sorts before libmmt_tcpip.so (C)",
    )
    assert load_order("mmtp_x.so", [*C_ONLY, folded])[1] == (
        "mmtp_x.so after libmmt_tcpip.so (C and en_US.UTF-8)"
    )


def test_collations_start_with_c_and_restore_the_locale() -> None:
    import locale

    before = locale.setlocale(locale.LC_COLLATE)
    found = collations()
    assert found[0][0] == "C"
    assert locale.setlocale(locale.LC_COLLATE) == before
    for _, key in found:
        assert key("mmtp_x.so") > key("libmmt_tcpip.so")
    assert locale.setlocale(locale.LC_COLLATE) == before


def test_a_load_order_failure_exits_3(run: Run, sdk_prefix: Path, tmp_path: Path) -> None:
    # Every mmtp_ name sorts after libmmt_tcpip.so; a collation that reverses
    # the order shows the check failing.
    reverse: Collation = ("reversed", lambda s: [-ord(c) for c in s])
    command = make_command(tmp_path, Reader(registry()), orders=[reverse])
    code, doc = run("model.pdl", "--sdk", str(sdk_prefix), command=command)
    assert code == 3
    assert doc["error"]["code"] == "model.load-order"
    assert statuses(doc)["load-order"] == "fail"
    assert "model.load-order" in codes(doc)


def test_load_order_after_another_file() -> None:
    assert load_order("mmtp_ocpp_example.so", C_ONLY, "mmtp_websocket_example.so") == (
        False,
        "mmtp_ocpp_example.so sorts before mmtp_websocket_example.so (C)",
    )
    assert load_order("mmtp_ws_ocpp.so", C_ONLY, "mmtp_websocket_example.so")[0] is True


def test_a_child_that_loads_before_its_plugin_parent_fails_load_order(
    run: Run, project: Path, sdk_prefix: Path
) -> None:
    # AC2, #96's case: mmtp_ocpp_example.so sorts before
    # mmtp_websocket_example.so, so mmt-dpi loads the child first.
    write_project(project / "websocket", "websocket_example", "tcp")
    write_project(project, "ocpp_example", "websocket_example", plugins=["websocket"])
    for args in (("--no-sdk",), ("--sdk", str(sdk_prefix))):
        code, doc = run(*args)
        assert code == 3
        assert doc["error"]["code"] == "model.load-order"
        assert doc["error"]["message"] == "1 error in plugin.yaml (load-order failed)"
        assert statuses(doc)["parents-exist"] in ("pass", "skip")
        assert statuses(doc)["load-order"] == "fail"
        assert detail(doc, "load-order") == (
            "mmtp_ocpp_example.so sorts before mmtp_websocket_example.so (C)"
        )
        (d,) = [d for d in doc["diagnostics"] if d["code"] == "model.load-order"]
        assert d["message"] == (
            "mmtp_ocpp_example.so sorts before mmtp_websocket_example.so (C): the plugin"
            " file mmtp_ocpp_example.so would load before mmtp_websocket_example.so, the"
            " plugin of websocket_example (websocket): a protocol it attaches under would"
            " not be registered yet"
        )
        assert "mmtp_websocket_example.so" in d["hint"]
        assert d["location"]["line"] == 3


def test_load_order_against_a_named_plugin_file(run: Run, project: Path, tmp_path: Path) -> None:
    # A .so entry: its own file name. It names no project, so it proves no
    # parent; it still must load first.
    (project / "lib").mkdir()
    (project / "lib" / "mmtp_zzz.so").write_bytes(b"")
    write_project(project, "yamlchild", "tcp", plugins=["lib/mmtp_zzz.so"])
    folded: Collation = ("en_US.UTF-8", lambda s: s.casefold())
    command = make_command(tmp_path, Reader(registry()), orders=[*C_ONLY, folded])
    code, doc = run("--no-sdk", command=command)
    assert code == 3
    assert doc["error"]["code"] == "model.load-order"
    assert detail(doc, "load-order") == (
        "mmtp_yamlchild.so sorts before mmtp_zzz.so (C, en_US.UTF-8)"
    )
    (d,) = [d for d in doc["diagnostics"] if d["code"] == "model.load-order"]
    assert "mmtp_zzz.so, the named plugin:" in d["message"]
    # A parent the .so file would register is not known from it.
    write_project(project, "yamlchild", "zzz", plugins=["lib/mmtp_zzz.so"])
    code, doc = run("--no-sdk", command=command)
    assert statuses(doc)["parents-exist"] == "fail"
    assert doc["error"]["code"] == "model.unknown-parent"


# --- id-range ----------------------------------------------------------------


def test_an_id_outside_the_reserved_range_is_a_warning(
    run: Run, project: Path, sdk_prefix: Path
) -> None:
    (project / "model.pdl").write_text(model_text(pid=920))
    code, doc = run("model.pdl", "--sdk", str(sdk_prefix))
    assert code == 0
    assert statuses(doc)["id-range"] == "warn"
    assert detail(doc, "id-range") == "920 outside 950-999"
    assert codes(doc) == ["model.id-outside-reserved-range"]
    code, doc = run("model.pdl", "--sdk", str(sdk_prefix), "--strict")
    assert code == 3
    assert doc["error"]["code"] == "model.id-outside-reserved-range"


# --- human output ------------------------------------------------------------


def test_plain_output_is_check_status_detail_records(
    tmp_path: Path,
    reader: Reader,
    project: Path,
    sdk_prefix: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = main(
        ["validate", "model.pdl", "--sdk", str(sdk_prefix)],
        commands=[make_command(tmp_path, reader)],
    )
    out = capsys.readouterr()
    assert code == 0
    lines = out.out.splitlines()
    assert [line.split("\t")[0] for line in lines] == list(CHECKS)
    assert lines[0] == "schema\tpass\tmodel.pdl, PDL v1"
    assert lines[-1] == "id-range\tpass\t990 in 950-999"
    assert out.err == ""


def test_the_styled_view_is_a_checks_box() -> None:
    st = StreamStyle(styled=True, color=ColorTier.NONE, unicode=True, width=70)
    checks = [
        {"id": "schema", "status": "pass", "detail": "model.pdl, PDL v1"},
        {"id": "id-free", "status": "fail", "detail": "taken"},
        {"id": "parents-exist", "status": "skip", "detail": "none"},
        {"id": "id-range", "status": "warn", "detail": "900 outside 950-999"},
    ]
    lines = validate_module._view("tpkt", checks, st).splitlines()
    assert lines[0].startswith("╭─┐validate tpkt┌")
    assert "reserved id range" in lines[-2] and "▲ warn" in lines[-2]
    assert "✗ fail" in lines[3] and "id free" in lines[3]
    assert lines[-1].startswith("╰─┘4 checks · 1 pass · 1 warning · 1 failed · 1 skipped└")
    ascii_st = StreamStyle(styled=True, color=ColorTier.NONE, unicode=False, width=70)
    text = validate_module._view("tpkt", checks[:1], ascii_st)
    assert text.splitlines()[-1].startswith("+-[1 check, 1 pass]")
