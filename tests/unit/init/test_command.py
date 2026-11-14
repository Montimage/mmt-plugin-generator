"""``mmt-plugin init`` without a real mmt-dpi: the files it creates and what
they contain, idempotency, files in the way and ``--force``, a directory that
is not a project, ``--dry-run``, the default id (from the profile and a
stubbed run-time registry), the label, ``--name`` and ``--parent`` checks,
and a project that ``build`` compiles with build's fake SDK and compiler
(``docs/design/cli.md``, sections 4, 5, 6 and 8). ``test_sdk.py`` runs
``init`` then ``test`` against a real mmt-dpi."""

from __future__ import annotations

import importlib.util
import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from mmt_plugin import schemas
from mmt_plugin.cli import main
from mmt_plugin.codegen import scaffold
from mmt_plugin.commands.build import BuildCommand
from mmt_plugin.commands.generate import make_generation
from mmt_plugin.commands.init import InitCommand, parse_selector
from mmt_plugin.diagnostics import CliError
from mmt_plugin.sdk.profile import DATA_TYPE_GROUP
from mmt_plugin.sdk.registry import RegisteredProtocol, Registry, RegistryError
from mmt_plugin.sdk.resolve import resolve_profile
from mmt_plugin.testing.packets import load

FILES = [".gitignore", "model.pdl", "src/demo_impl.c", "tests/demo-basic.yaml"]
PROFILE = ["--sdk-profile", "1.10.2"]

Run = Callable[..., tuple[int, dict[str, Any]]]


def _load_fakes() -> Any:
    # build's fake SDK and compiler (tests/unit/build/fakes.py).
    spec = importlib.util.spec_from_file_location(
        "init_build_fakes", Path(__file__).parents[1] / "build" / "fakes.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


fakes = _load_fakes()


class FakeRegistry:
    """A registry reader that returns ``protocols``, or raises ``error``;
    it records each call's keyword arguments."""

    def __init__(
        self, protocols: tuple[RegisteredProtocol, ...] = (), error: str | None = None
    ) -> None:
        self.protocols = protocols
        self.error = error
        self.calls: list[dict[str, Any]] = []

    def __call__(self, sdk: Any, **kwargs: Any) -> Registry:
        self.calls.append(kwargs)
        if self.error is not None:
            raise RegistryError(self.error)
        return Registry("/fake/plugins", ("mmtp_other.so",), self.protocols)


@pytest.fixture
def work(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """An empty current directory, and no SDK or profile in the environment."""
    cwd = tmp_path / "work"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    for name in ("MMT_PLUGIN_SDK_PROFILE", "MMT_BASE", "CC"):
        monkeypatch.delenv(name, raising=False)
    return cwd


@pytest.fixture
def registry() -> FakeRegistry:
    return FakeRegistry()


@pytest.fixture
def init(
    tmp_path: Path, work: Path, registry: FakeRegistry, capsys: pytest.CaptureFixture[str]
) -> Run:
    """``mmt-plugin --json init ARGS``, with no SDK on the search path."""
    command = InitCommand(
        pkg_config_dirs=[], default_prefix=str(tmp_path / "no-sdk"), registry_reader=registry
    )
    envelope = Draft202012Validator(schemas.load_cli_schema(schemas.ENVELOPE))
    result = Draft202012Validator(schemas.result_schema("init"))

    def go(*args: str) -> tuple[int, dict[str, Any]]:
        code = main(["--json", "init", *args], commands=[command])
        out = capsys.readouterr()
        assert out.err == ""
        doc: dict[str, Any] = json.loads(out.out)
        envelope.validate(doc)
        assert doc["exit_code"] == code
        if doc["result"] is not None:
            result.validate(doc["result"])
        return code, doc

    return go


def _codes(doc: dict[str, Any]) -> list[str]:
    return [d["code"] for d in doc["diagnostics"]]


def _actions(doc: dict[str, Any]) -> dict[str, str]:
    return {f["path"]: f["action"] for f in doc["result"]["files"]}


def _tree(root: Path) -> dict[str, bytes]:
    return {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


# --- the files ---------------------------------------------------------------


def test_init_creates_the_project(init: Run, work: Path) -> None:
    code, doc = init("demo", *PROFILE, "--id", "960", "--parent", "ethernet:ethertype=0x88b5")
    assert code == 0, doc["error"]
    assert sorted(_tree(work / "demo")) == FILES
    result = doc["result"]
    assert result["project"] == "demo"
    assert result["protocol"] == {"label": "demo", "name": "DEMO", "id": 960}
    assert result["parent"] == "ethernet:ethertype=0x88b5"
    assert result["profile"] == "1.10.2"
    assert result["model"] == "demo/model.pdl"
    assert _actions(doc) == {f"demo/{f}": "created" for f in FILES}
    assert result["dry_run"] is False
    assert result["next"] == [
        *("mmt-plugin", "-C", "demo", "test", "--model", "demo/model.pdl"),
        *PROFILE,
    ]
    assert _codes(doc) == []


def test_the_files_are_a_model_its_scaffold_and_a_packet_test_of_it(init: Run, work: Path) -> None:
    assert init("demo", *PROFILE, "--id", "960")[0] == 0
    project = work / "demo"
    assert (project / ".gitignore").read_text() == "build/\n"
    model = (project / "model.pdl").read_bytes()
    assert b'label = "demo"' in model and b'id = "960"' in model
    choice = resolve_profile("1.10.2", {}, None, None)
    generation, diagnostics, error = make_generation("model.pdl", model, choice)
    assert generation is not None, error
    assert diagnostics == []
    impl = scaffold(generation, choice.profile)
    assert (project / impl.path).read_text() == impl.text
    types = {c.name for c in choice.profile.constants if c.group == DATA_TYPE_GROUP}
    test = load(project / "tests" / "demo-basic.yaml", "tests/demo-basic.yaml", types)
    assert test.id == "demo/basic"
    assert test.data == bytes([1, 2, 0, 4])
    assert (test.protocol, test.proto_id) == (generation.name, generation.proto_id)
    assert [(a.name, a.type, a.value, a.length) for a in test.attributes] == [
        ("version", "MMT_U8_DATA", 1, 1),
        ("kind", "MMT_U8_DATA", 2, 1),
        ("length", "MMT_U16_DATA", 4, 2),
    ]


def test_the_files_do_not_depend_on_the_directory(init: Run, work: Path) -> None:
    init("demo", *PROFILE, "--id", "960")
    init("demo", *PROFILE, "--id", "960", "--dir", "elsewhere/x")
    assert _tree(work / "demo") == _tree(work / "elsewhere" / "x")


def test_a_label_that_is_the_sdk_s_own_is_exit_3_and_writes_nothing(init: Run, work: Path) -> None:
    code, doc = init("tcp", *PROFILE, "--id", "960")
    assert code == 3
    assert doc["error"]["code"] == "model.name-taken"
    assert "nothing written" in doc["error"]["message"]
    assert list(work.iterdir()) == []


@pytest.mark.parametrize("label", ["Demo", "1demo", "de-mo", "", "_x"])
def test_a_label_that_is_not_a_label_is_a_usage_error(init: Run, label: str) -> None:
    code, doc = init(label, *PROFILE)
    assert code == 2
    assert doc["error"]["code"] == "usage.invalid-value"


def test_name_must_be_the_label_upper_cased(init: Run) -> None:
    assert init("demo", *PROFILE, "--id", "960", "--name", "DEMO", "--dry-run")[0] == 0
    code, doc = init("demo", *PROFILE, "--id", "960", "--name", "OTHER")
    assert code == 2
    assert doc["error"]["code"] == "usage.invalid-value"
    assert "#24" in doc["error"]["hint"]


# --- --parent ----------------------------------------------------------------


def test_no_parent_is_a_warning(init: Run, work: Path) -> None:
    code, doc = init("demo", *PROFILE, "--id", "960")
    assert code == 0
    assert _codes(doc) == ["model.no-parent"]
    assert doc["result"]["parent"] is None
    assert "no parent yet" in (work / "demo" / "model.pdl").read_text()


def test_the_parent_is_recorded_in_the_model(init: Run, work: Path) -> None:
    init("demo", *PROFILE, "--id", "960", "--parent", "udp:port=4433")
    assert "// parent udp:port=4433: attach it in" in (work / "demo" / "model.pdl").read_text()


def test_an_unknown_parent_is_exit_3(init: Run, work: Path) -> None:
    code, doc = init("demo", *PROFILE, "--id", "960", "--parent", "nosuchproto")
    assert code == 3
    assert doc["error"]["code"] == "model.unknown-parent"
    assert list(work.iterdir()) == []


@pytest.mark.parametrize(
    "text", ["", "Udp", "udp:", "udp:port", "udp:port=", "udp:=1", "udp:port=1,", "udp:p=a b"]
)
def test_a_malformed_selector_is_a_usage_error(init: Run, text: str) -> None:
    with pytest.raises(CliError) as caught:
        parse_selector(text)
    assert caught.value.code == "usage.invalid-value"
    assert init("demo", *PROFILE, "--id", "960", "--parent", text)[0] == 2


def test_a_selector_parses_into_its_keys() -> None:
    selector = parse_selector("tcp:port=102,flag=on")
    assert (selector.proto, selector.keys) == ("tcp", (("port", "102"), ("flag", "on")))
    assert parse_selector("ethernet").keys == ()


# --- idempotency, files in the way, --force, --dry-run -----------------------


def test_re_running_is_a_no_op(init: Run, work: Path) -> None:
    init("demo", *PROFILE, "--id", "960")
    stamps = {p: os.stat(work / "demo" / p).st_mtime_ns for p in FILES}
    code, doc = init("demo", *PROFILE, "--id", "960")
    assert code == 0
    assert set(_actions(doc).values()) == {"unchanged"}
    assert stamps == {p: os.stat(work / "demo" / p).st_mtime_ns for p in FILES}


def test_a_build_does_not_make_the_project_foreign(init: Run, work: Path) -> None:
    init("demo", *PROFILE, "--id", "960")
    (work / "demo" / "build").mkdir()
    (work / "demo" / "generated").mkdir()
    code, doc = init("demo", *PROFILE, "--id", "960")
    assert code == 0, doc["error"]


def test_a_file_with_other_content_is_exit_7_and_nothing_is_written(init: Run, work: Path) -> None:
    init("demo", *PROFILE, "--id", "960")
    impl = work / "demo" / "src" / "demo_impl.c"
    impl.write_text("/* mine */\n")
    (work / "demo" / ".gitignore").unlink()
    code, doc = init("demo", *PROFILE, "--id", "961")
    assert code == 7
    assert doc["error"]["code"] == "state.file-differs"
    assert impl.read_text() == "/* mine */\n"
    assert not (work / "demo" / ".gitignore").exists()
    assert 'id = "960"' in (work / "demo" / "model.pdl").read_text()
    actions = _actions(doc)
    assert actions["demo/.gitignore"] == "would-create"
    assert actions["demo/src/demo_impl.c"] == "would-update"
    assert actions["demo/model.pdl"] == "would-update"
    located = {d["location"]["file"] for d in doc["diagnostics"] if d["location"]}
    assert located == {"demo/src/demo_impl.c", "demo/model.pdl", "demo/tests/demo-basic.yaml"}


def test_force_replaces_a_file_with_other_content(init: Run, work: Path) -> None:
    init("demo", *PROFILE, "--id", "960")
    impl = work / "demo" / "src" / "demo_impl.c"
    impl.write_text("/* mine */\n")
    code, doc = init("demo", *PROFILE, "--id", "960", "--force")
    assert code == 0
    assert _actions(doc)["demo/src/demo_impl.c"] == "updated"
    assert "state.file-differs" in _codes(doc)
    assert impl.read_text() != "/* mine */\n"


def test_force_replaces_a_symbolic_link_with_the_file(init: Run, work: Path) -> None:
    (work / "demo").mkdir()
    (work / "target").write_text("build/\n")
    (work / "demo" / ".gitignore").symlink_to(work / "target")
    assert init("demo", *PROFILE, "--id", "960")[0] == 7
    assert init("demo", *PROFILE, "--id", "960", "--force")[0] == 0
    assert not (work / "demo" / ".gitignore").is_symlink()
    assert (work / "target").read_text() == "build/\n"


def test_a_directory_in_the_way_is_exit_7_even_with_force(init: Run, work: Path) -> None:
    (work / "demo" / "model.pdl").mkdir(parents=True)
    for force in ([], ["--force"]):
        code, doc = init("demo", *PROFILE, "--id", "960", *force)
        assert code == 7
        assert doc["error"]["code"] == "state.file-differs"
    assert sorted(_tree(work / "demo")) == []


def test_a_directory_that_is_not_a_project_is_exit_7_unless_force(init: Run, work: Path) -> None:
    (work / "demo").mkdir()
    (work / "demo" / "notes.txt").write_text("hello\n")
    code, doc = init("demo", *PROFILE, "--id", "960")
    assert code == 7
    assert doc["error"]["code"] == "state.not-a-project"
    assert sorted(_tree(work / "demo")) == ["notes.txt"]
    code, doc = init("demo", *PROFILE, "--id", "960", "--force")
    assert code == 0
    assert sorted(_tree(work / "demo")) == sorted([*FILES, "notes.txt"])


def test_dir_dot_in_an_empty_directory_or_a_new_repository(init: Run, work: Path) -> None:
    (work / ".git").mkdir()
    code, doc = init("demo", *PROFILE, "--id", "960", "--dir", ".")
    assert code == 0, doc["error"]
    assert doc["result"]["project"] == "."
    assert doc["result"]["next"][:6] == ["mmt-plugin", "-C", ".", "test", "--model", "model.pdl"]
    assert (work / "model.pdl").is_file()


def test_a_dir_that_is_a_file_is_exit_7(init: Run, work: Path) -> None:
    (work / "demo").write_text("")
    for force in ([], ["--force"]):
        code, doc = init("demo", *PROFILE, "--id", "960", *force)
        assert code == 7
        assert doc["error"]["code"] == "state.not-a-project"


def test_dry_run_writes_nothing(init: Run, work: Path) -> None:
    code, doc = init("demo", *PROFILE, "--id", "960", "--dry-run")
    assert code == 0
    assert set(_actions(doc).values()) == {"would-create"}
    assert doc["result"]["dry_run"] is True
    assert list(work.iterdir()) == []


def test_paths_are_relative_to_the_project_option(init: Run, work: Path) -> None:
    (work / "top").mkdir()
    code, doc = init("-C", "top", "demo", *PROFILE, "--id", "960", "--dir", "top/demo")
    assert code == 0
    assert doc["result"]["project"] == "demo"
    assert doc["result"]["model"] == "demo/model.pdl"
    # The next command line is for the current directory.
    assert doc["result"]["next"][:6] == [
        *("mmt-plugin", "-C", "top/demo", "test", "--model", "top/demo/model.pdl")
    ]


# --- the id ------------------------------------------------------------------


def test_without_an_sdk_the_id_is_950_with_a_warning(init: Run, registry: FakeRegistry) -> None:
    code, doc = init("demo", *PROFILE, "--dry-run")
    assert code == 0
    assert doc["result"]["protocol"]["id"] == 950
    assert "sdk.id-unchecked" in _codes(doc)
    assert registry.calls == []


def test_with_an_sdk_the_id_is_the_lowest_free_one(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], work: Path
) -> None:
    sdk = fakes.fake_sdk(tmp_path / "sdk")
    taken = tuple(RegisteredProtocol(i, f"P{i}") for i in (950, 951, 953))
    reader = FakeRegistry(taken)
    command = InitCommand(
        pkg_config_dirs=[], default_prefix=str(tmp_path / "no"), registry_reader=reader
    )
    code = main(["--json", "init", "demo", "--sdk", str(sdk), "--dry-run"], commands=[command])
    doc = json.loads(capsys.readouterr().out)
    assert code == 0, doc["error"]
    assert doc["result"]["protocol"]["id"] == 952
    assert "sdk.id-unchecked" not in _codes(doc)
    assert reader.calls[0]["exclude"] == "mmtp_demo.so"
    assert doc["context"]["sdk"]["prefix"] == str(sdk)
    assert doc["result"]["next"][-2:] == ["--sdk", str(sdk)]


def test_mmt_base_is_found_when_no_id_is_given(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], work: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sdk = fakes.fake_sdk(tmp_path / "sdk")
    monkeypatch.setenv("MMT_BASE", str(sdk))
    reader = FakeRegistry()
    command = InitCommand(
        pkg_config_dirs=[], default_prefix=str(tmp_path / "no"), registry_reader=reader
    )
    assert main(["--json", "init", "demo", "--dry-run"], commands=[command]) == 0
    doc = json.loads(capsys.readouterr().out)
    assert doc["result"]["protocol"]["id"] == 950
    assert doc["context"]["sdk"]["source"] == "MMT_BASE"
    assert len(reader.calls) == 1


def _with_sdk(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], reader: FakeRegistry, *args: str
) -> tuple[int, dict[str, Any]]:
    sdk = fakes.fake_sdk(tmp_path / "sdk")
    command = InitCommand(
        pkg_config_dirs=[], default_prefix=str(tmp_path / "no"), registry_reader=reader
    )
    code = main(["--json", "init", "demo", "--sdk", str(sdk), *args], commands=[command])
    doc: dict[str, Any] = json.loads(capsys.readouterr().out)
    return code, doc


def test_every_id_taken_is_exit_3(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], work: Path
) -> None:
    reader = FakeRegistry(tuple(RegisteredProtocol(i, f"P{i}") for i in range(950, 1000)))
    code, doc = _with_sdk(tmp_path, capsys, reader)
    assert code == 3
    assert doc["error"]["code"] == "model.id-taken"
    assert "--id" in doc["error"]["hint"]


def test_an_id_an_installed_plugin_takes_is_exit_3(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], work: Path
) -> None:
    reader = FakeRegistry((RegisteredProtocol(960, "OTHER"),))
    code, doc = _with_sdk(tmp_path, capsys, reader, "--id", "960")
    assert code == 3
    assert doc["error"]["code"] == "model.id-taken"
    assert list(work.iterdir()) == []


def test_a_name_an_installed_plugin_takes_is_exit_3(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], work: Path
) -> None:
    reader = FakeRegistry((RegisteredProtocol(960, "Demo"),))
    code, doc = _with_sdk(tmp_path, capsys, reader)
    assert code == 3
    assert doc["error"]["code"] == "model.name-taken"


def test_a_registry_that_cannot_be_read_is_a_warning(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], work: Path
) -> None:
    code, doc = _with_sdk(tmp_path, capsys, FakeRegistry(error="boom"), "--dry-run")
    assert code == 0
    assert doc["result"]["protocol"]["id"] == 950
    assert "sdk.registry-unavailable" in _codes(doc)


def test_an_explicit_id_with_a_pinned_profile_looks_for_no_sdk(
    init: Run, registry: FakeRegistry, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MMT_BASE", "/nonexistent/sdk")  # an invalid SDK, never looked at
    code, doc = init("demo", *PROFILE, "--id", "960", "--dry-run")
    assert code == 0, doc["error"]
    assert doc["context"]["sdk"]["prefix"] is None
    assert registry.calls == []


def test_an_id_out_of_range_is_exit_3(init: Run, work: Path) -> None:
    code, doc = init("demo", *PROFILE, "--id", "5000")
    assert code == 3
    assert doc["error"]["code"] == "model.id-out-of-range"
    assert list(work.iterdir()) == []


def test_an_id_outside_the_third_party_range_is_a_warning(init: Run) -> None:
    code, doc = init("demo", *PROFILE, "--id", "920", "--dry-run")
    assert code == 0
    assert "model.id-outside-reserved-range" in _codes(doc)


# --- human output ------------------------------------------------------------


def test_plain_records_and_the_styled_box(
    tmp_path: Path, work: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    command = InitCommand(pkg_config_dirs=[], default_prefix=str(tmp_path / "no"))
    assert main(["init", "demo", *PROFILE, "--id", "960"], commands=[command]) == 0
    out = capsys.readouterr()
    assert out.out.splitlines() == [f"created\tdemo/{f}" for f in FILES]
    assert "[model.no-parent]" in out.err
    monkeypatch.setenv("FORCE_COLOR", "1")
    monkeypatch.setenv("COLUMNS", "100")
    assert main(["init", "demo", *PROFILE, "--id", "960"], commands=[command]) == 0
    styled = capsys.readouterr().out
    assert "init demo" in styled
    assert "next: mmt-plugin -C demo test --model demo/model.pdl --sdk-profile 1.10.2" in styled
    assert "id 960" in styled and "4 unchanged" in styled


# --- the project builds ------------------------------------------------------


def test_the_project_builds_with_the_fake_sdk(
    tmp_path: Path, work: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    sdk = fakes.fake_sdk(tmp_path / "sdk")
    cc = fakes.fake_cc(tmp_path / "bin")
    command = InitCommand(pkg_config_dirs=[], default_prefix=str(tmp_path / "no"))
    assert main(["-q", "init", "demo", *PROFILE, "--id", "960"], commands=[command]) == 0
    build = BuildCommand(pkg_config_dirs=[], default_prefix=str(tmp_path / "no"))
    argv = ["--json", "-C", "demo", "build", "demo/model.pdl", "--sdk", str(sdk), "--cc", str(cc)]
    code = main(argv, commands=[build])
    doc = json.loads(capsys.readouterr().out)
    assert code == 0, doc["error"]
    assert doc["result"]["artifact"]["path"] == "build/mmtp_demo.so"
    assert (work / "demo" / "build" / "mmtp_demo.so").is_file()


def test_an_id_the_sdk_profile_takes_is_exit_3(init: Run, work: Path) -> None:
    code, doc = init("demo", *PROFILE, "--id", "354")  # PROTO_TCP in mmt-dpi 1.10.2
    assert code == 3
    assert doc["error"]["code"] == "model.id-taken"
    assert list(work.iterdir()) == []
