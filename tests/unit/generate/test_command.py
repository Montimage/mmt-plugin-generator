"""``mmt-plugin generate``: plugin.lock, --check, --force, --dry-run, removal,
``src/`` protection and the model and SDK stages, each on a tmp_path project
(``docs/design/cli.md``, sections 4, 5, 6 and 8)."""

from __future__ import annotations

import io
import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from mmt_plugin import fsio, schemas
from mmt_plugin.cli import main
from mmt_plugin.commands import generate as generate_module
from mmt_plugin.commands.generate import GenerateCommand
from mmt_plugin.fsio import sha256_file
from mmt_plugin.lock import load_schema, parse_lock
from mmt_plugin.ui.streams import ColorTier, StreamStyle

from .helpers import GOLDEN, source_text

MODEL = "pdl_conditionals"
H = "pdl_conditionals_mmt_plugin.h"
C = "pdl_conditionals_mmt_plugin.c"
PROFILE = ["--sdk-profile", "1.10.2"]

Run = Callable[..., tuple[int, dict[str, Any]]]


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """An empty directory, the current one; ``model.pdl`` holds a corpus model."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("MMT_PLUGIN_SDK_PROFILE", raising=False)
    monkeypatch.delenv("MMT_BASE", raising=False)
    (tmp_path / "model.pdl").write_text(source_text(MODEL))
    return tmp_path


@pytest.fixture
def command(tmp_path: Path) -> GenerateCommand:
    # SDK detection that finds nothing: no pkg-config file, no default prefix.
    return GenerateCommand(pkg_config_dirs=[], default_prefix=str(tmp_path / "no-sdk"))


@pytest.fixture
def run(command: GenerateCommand, capsys: pytest.CaptureFixture[str]) -> Run:
    """Run ``mmt-plugin --json generate ARGS``; the exit code and the envelope,
    checked against the envelope and result schemas."""
    envelope = Draft202012Validator(schemas.load_cli_schema(schemas.ENVELOPE))
    result = Draft202012Validator(schemas.result_schema("generate"))

    def go(*args: str) -> tuple[int, dict[str, Any]]:
        code = main(["--json", "generate", *args], commands=[command])
        out = capsys.readouterr()
        assert out.err == ""
        doc: dict[str, Any] = json.loads(out.out)
        envelope.validate(doc)
        assert doc["exit_code"] == code
        if doc["result"] is not None:
            result.validate(doc["result"])
        return code, doc

    return go


def snapshot(directory: Path) -> dict[str, tuple[str | None, int]]:
    """Every file below ``directory``: its sha256 and mtime (ns)."""
    return {
        p.relative_to(directory).as_posix(): (sha256_file(p), p.stat().st_mtime_ns)
        for p in sorted(directory.rglob("*"))
        if p.is_file()
    }


def actions(doc: dict[str, Any]) -> dict[str, str]:
    out = {f["path"]: f["action"] for f in doc["result"]["files"]}
    out[doc["result"]["lock"]["path"]] = doc["result"]["lock"]["action"]
    return out


def codes(doc: dict[str, Any]) -> list[str]:
    return [d["code"] for d in doc["diagnostics"]]


# --- writing and plugin.lock -------------------------------------------------


def test_outside_a_project_the_files_and_lock_go_to_the_output_dir(
    project: Path, run: Run
) -> None:
    code, doc = run("model.pdl", "-o", "out", *PROFILE)
    assert code == 0, doc["error"]
    assert actions(doc) == {
        "out/" + H: "created",
        "out/" + C: "created",
        "out/plugin.lock": "created",
    }
    for name in (H, C):
        assert (project / "out" / name).read_bytes() == (GOLDEN / MODEL / name).read_bytes()
    text = (project / "out" / "plugin.lock").read_text()
    Draft202012Validator(load_schema()).validate(json.loads(text))
    lock = parse_lock(text)
    assert lock.sdk_profile == "1.10.2" and lock.generator == "mmt-plugin"
    assert lock.model_format == "pdl"
    assert lock.model_sha256 == sha256_file(project / "model.pdl")
    assert [(f.path, f.sha256) for f in lock.files] == [
        (C, sha256_file(project / "out" / C)),
        (H, sha256_file(project / "out" / H)),
    ]
    assert doc["result"]["profile"] == "1.10.2"
    assert doc["context"]["sdk"]["profile_source"] == "--sdk-profile"
    assert doc["context"]["sdk"]["prefix"] is None  # pinned: no SDK looked for


def test_in_a_project_the_lock_is_at_the_root_and_output_defaults_to_generated(
    project: Path, run: Run
) -> None:
    (project / "plugin.yaml").write_text("# a project\n")
    code, doc = run("model.pdl", *PROFILE)
    assert code == 0, doc["error"]
    assert sorted(actions(doc)) == ["generated/" + C, "generated/" + H, "plugin.lock"]
    lock = parse_lock((project / "plugin.lock").read_text())
    assert [f.path for f in lock.files] == ["generated/" + C, "generated/" + H]
    assert not (project / "generated" / "plugin.lock").exists()


def test_a_rerun_rewrites_nothing_and_keeps_mtimes(project: Path, run: Run) -> None:
    assert run("model.pdl", "-o", "out", *PROFILE)[0] == 0
    for p in (project / "out").iterdir():
        os.utime(p, ns=(1_000_000_000, 1_000_000_000))
    before = snapshot(project / "out")
    code, doc = run("model.pdl", "-o", "out", *PROFILE)
    assert code == 0
    assert set(actions(doc).values()) == {"unchanged"}
    assert snapshot(project / "out") == before


def test_two_runs_give_the_same_bytes(project: Path, run: Run) -> None:
    assert run("model.pdl", "-o", "a", *PROFILE)[0] == 0
    assert run("model.pdl", "-o", "b", *PROFILE)[0] == 0
    a = {k: v[0] for k, v in snapshot(project / "a").items()}
    b = {k: v[0] for k, v in snapshot(project / "b").items()}
    assert a == b


# --- --check and --dry-run ---------------------------------------------------


def test_check_exits_0_when_up_to_date_and_7_when_stale(project: Path, run: Run) -> None:
    code, doc = run("model.pdl", "-o", "out", *PROFILE, "--check")
    assert code == 7 and doc["error"]["code"] == "state.stale"
    assert not (project / "out").exists()  # nothing written
    assert set(actions(doc).values()) == {"would-create"}
    assert doc["result"]["check"] is True

    assert run("model.pdl", "-o", "out", *PROFILE)[0] == 0
    code, doc = run("model.pdl", "-o", "out", *PROFILE, "--check")
    assert code == 0 and doc["error"] is None
    assert set(actions(doc).values()) == {"unchanged"}

    # A model change: the files and the lock would change.
    before = snapshot(project / "out")
    (project / "model.pdl").write_text(source_text(MODEL).replace('offset="7"', 'offset="8"'))
    code, doc = run("model.pdl", "-o", "out", *PROFILE, "--check")
    assert code == 7 and doc["error"]["code"] == "state.stale"
    assert actions(doc)["out/" + C] == "would-update"
    assert actions(doc)["out/plugin.lock"] == "would-update"
    assert snapshot(project / "out") == before


def test_check_is_stale_when_only_the_lock_would_change(project: Path, run: Run) -> None:
    assert run("model.pdl", "-o", "out", *PROFILE)[0] == 0
    lock = project / "out" / "plugin.lock"
    lock.write_text(lock.read_text().replace('"0.1', '"0.0'))  # another generator version
    code, doc = run("model.pdl", "-o", "out", *PROFILE, "--check")
    assert code == 7 and doc["error"]["code"] == "state.stale"
    assert actions(doc)["out/" + C] == "unchanged"


def test_dry_run_reports_would_actions_and_writes_nothing(project: Path, run: Run) -> None:
    code, doc = run("model.pdl", "-o", "out", *PROFILE, "--dry-run")
    assert code == 0
    assert set(actions(doc).values()) == {"would-create"}
    assert doc["result"]["dry_run"] is True
    assert not (project / "out").exists()


# --- hand-edited files, --force and removal ----------------------------------


def test_a_hand_edited_file_is_not_overwritten_without_force(project: Path, run: Run) -> None:
    assert run("model.pdl", "-o", "out", *PROFILE)[0] == 0
    edited = project / "out" / C
    edited.write_text(edited.read_text() + "/* my change */\n")
    # A model change too: the other file and the lock would change, but a
    # refused run writes nothing at all.
    (project / "model.pdl").write_text(source_text(MODEL).replace('offset="7"', 'offset="8"'))
    before = snapshot(project / "out")
    code, doc = run("model.pdl", "-o", "out", *PROFILE)
    assert code == 7 and doc["error"]["code"] == "state.modified"
    assert snapshot(project / "out") == before
    (diag,) = [d for d in doc["diagnostics"] if d["code"] == "state.modified"]
    assert diag["severity"] == "error" and diag["location"]["file"] == "out/" + C

    code, doc = run("model.pdl", "-o", "out", *PROFILE, "--force")
    assert code == 0
    assert actions(doc)["out/" + C] == "updated"
    assert "my change" not in edited.read_text()
    assert codes(doc) == ["state.modified"]  # a warning: overwritten (--force)
    assert run("model.pdl", "-o", "out", *PROFILE, "--check")[0] == 0


def test_check_reports_a_hand_edited_file_as_modified(project: Path, run: Run) -> None:
    assert run("model.pdl", "-o", "out", *PROFILE)[0] == 0
    (project / "out" / H).write_text("/* edited */\n")
    code, doc = run("model.pdl", "-o", "out", *PROFILE, "--check")
    assert code == 7 and doc["error"]["code"] == "state.modified"


def test_a_file_in_the_way_that_the_lock_does_not_list_is_not_overwritten(
    project: Path, run: Run
) -> None:
    (project / "out").mkdir()
    (project / "out" / H).write_text("/* someone else's */\n")
    code, doc = run("model.pdl", "-o", "out", *PROFILE)
    assert code == 7 and doc["error"]["code"] == "state.modified"
    assert not (project / "out" / C).exists()
    assert (project / "out" / H).read_text() == "/* someone else's */\n"


def test_an_identical_file_without_a_lock_is_adopted(project: Path, run: Run) -> None:
    (project / "out").mkdir()
    (project / "out" / H).write_bytes((GOLDEN / MODEL / H).read_bytes())
    code, doc = run("model.pdl", "-o", "out", *PROFILE)
    assert code == 0
    assert actions(doc)["out/" + H] == "unchanged"


def _relabel(project: Path, label: str) -> None:
    (project / "model.pdl").write_text(
        source_text(MODEL).replace('label = "pdl_conditionals"', f'label = "{label}"')
    )


def test_a_file_no_longer_generated_is_removed_when_unmodified(project: Path, run: Run) -> None:
    assert run("model.pdl", "-o", "out", *PROFILE)[0] == 0
    _relabel(project, "renamed")
    code, doc = run("model.pdl", "-o", "out", *PROFILE)
    assert code == 0
    assert actions(doc) == {
        "out/" + C: "removed",
        "out/" + H: "removed",
        "out/renamed_mmt_plugin.c": "created",
        "out/renamed_mmt_plugin.h": "created",
        "out/plugin.lock": "updated",
    }
    assert sorted(p.name for p in (project / "out").iterdir()) == [
        "plugin.lock",
        "renamed_mmt_plugin.c",
        "renamed_mmt_plugin.h",
    ]
    lock = parse_lock((project / "out" / "plugin.lock").read_text())
    assert [f.path for f in lock.files] == ["renamed_mmt_plugin.c", "renamed_mmt_plugin.h"]


def test_a_modified_file_no_longer_generated_is_kept_without_force(
    project: Path, run: Run
) -> None:
    assert run("model.pdl", "-o", "out", *PROFILE)[0] == 0
    (project / "out" / C).write_text("/* mine now */\n")
    _relabel(project, "renamed")
    code, doc = run("model.pdl", "-o", "out", *PROFILE)
    assert code == 7 and doc["error"]["code"] == "state.modified"
    assert (project / "out" / C).read_text() == "/* mine now */\n"
    assert not (project / "out" / "renamed_mmt_plugin.c").exists()
    code, doc = run("model.pdl", "-o", "out", *PROFILE, "--force")
    assert code == 0 and not (project / "out" / C).exists()


def test_a_locked_file_outside_the_output_dir_is_never_removed(project: Path, run: Run) -> None:
    assert run("model.pdl", "-o", "out", *PROFILE)[0] == 0
    outside = project / "precious.c"
    outside.write_text("/* not generated */\n")
    lock_path = project / "out" / "plugin.lock"
    data = json.loads(lock_path.read_text())
    data["files"].append({"path": "../precious.c", "sha256": sha256_file(outside)})
    lock_path.write_text(json.dumps(data))
    code, doc = run("model.pdl", "-o", "out", *PROFILE)
    assert code == 0
    assert outside.read_text() == "/* not generated */\n"
    assert codes(doc) == ["state.kept"]
    assert [f.path for f in parse_lock(lock_path.read_text()).files] == [C, H]


# --- src/ is the user's ------------------------------------------------------


@pytest.mark.parametrize("output", ["src", "src/generated", "./src/../src/x"])
def test_nothing_is_written_under_src(project: Path, run: Run, output: str) -> None:
    (project / "src").mkdir()
    code, doc = run("model.pdl", "-o", output, *PROFILE)
    assert code == 2 and doc["error"]["code"] == "usage.invalid-value"
    assert list((project / "src").iterdir()) == []


def test_an_output_dir_linked_into_src_is_refused(project: Path, run: Run) -> None:
    (project / "src").mkdir()
    (project / "out").symlink_to(project / "src")
    code, doc = run("model.pdl", "-o", "out", *PROFILE)
    assert code == 2 and doc["error"]["code"] == "usage.invalid-value"
    assert list((project / "src").iterdir()) == []


def test_a_locked_file_under_src_is_never_removed(project: Path, run: Run) -> None:
    (project / "plugin.yaml").write_text("# a project\n")
    assert run("model.pdl", *PROFILE)[0] == 0
    (project / "src").mkdir()
    user = project / "src" / "t_impl.c"
    user.write_text("/* user code */\n")
    data = json.loads((project / "plugin.lock").read_text())
    data["files"].append({"path": "src/t_impl.c", "sha256": sha256_file(user)})
    (project / "plugin.lock").write_text(json.dumps(data))
    code, doc = run("model.pdl", *PROFILE)
    assert code == 0 and user.read_text() == "/* user code */\n"
    assert codes(doc) == ["state.kept"]


# --- an interrupted run ------------------------------------------------------


def test_an_interrupted_run_leaves_the_previous_state_recoverable(
    project: Path, run: Run, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert run("model.pdl", "-o", "out", *PROFILE)[0] == 0
    old_lock = (project / "out" / "plugin.lock").read_bytes()
    (project / "model.pdl").write_text(source_text(MODEL).replace('offset="7"', 'offset="8"'))
    real = fsio.write_atomic
    calls: list[Path] = []

    def interrupted(path: Path | str, data: bytes | str, **kwargs: Any) -> Any:
        calls.append(Path(path))
        if len(calls) == 2:
            raise KeyboardInterrupt
        return real(path, data, **kwargs)

    monkeypatch.setattr(generate_module, "write_atomic", interrupted)
    code, _ = run("model.pdl", "-o", "out", *PROFILE)
    assert code == 130
    # The lock is the old one: it is written last.
    assert (project / "out" / "plugin.lock").read_bytes() == old_lock
    assert not [p for p in (project / "out").iterdir() if p.name.endswith(".tmp")]
    monkeypatch.setattr(generate_module, "write_atomic", real)
    code, doc = run("model.pdl", "-o", "out", *PROFILE, "--check")
    assert code == 7  # the old lock shows what changed
    code, doc = run("model.pdl", "-o", "out", *PROFILE)
    assert code == 0, doc["error"]
    assert run("model.pdl", "-o", "out", *PROFILE, "--check")[0] == 0


# --- the model stage ---------------------------------------------------------


def test_a_model_on_stdin_is_named_stdin(
    project: Path, run: Run, monkeypatch: pytest.MonkeyPatch
) -> None:
    text = source_text(MODEL).replace('data_len="1" offset="7"', 'data_len="1" offset="7x"')
    monkeypatch.setattr("sys.stdin", io.TextIOWrapper(io.BytesIO(text.encode())))
    code, doc = run("-", "-o", "out", *PROFILE)
    assert code == 3
    assert doc["diagnostics"][0]["location"]["file"] == "<stdin>"
    monkeypatch.setattr("sys.stdin", io.TextIOWrapper(io.BytesIO(source_text(MODEL).encode())))
    code, doc = run("-", "-o", "out", *PROFILE)
    assert code == 0 and doc["result"]["model"] == "<stdin>"


@pytest.mark.parametrize(
    "args",
    [[], ["model.yaml"], ["plugin.yml"], ["model.pdl", "--model-format", "yaml"]],
)
def test_plugin_yaml_waits_for_24(project: Path, run: Run, args: list[str]) -> None:
    code, doc = run(*args, *PROFILE)
    assert code == 3 and doc["error"]["code"] == "model.unsupported-format"
    assert doc["result"] is None


def test_an_sdk_id_or_name_conflict_is_exit_3_with_no_output(project: Path, run: Run) -> None:
    (project / "model.pdl").write_text(source_text("tpkt"))
    code, doc = run("model.pdl", "-o", "out", *PROFILE)
    assert code == 3 and doc["error"]["code"] in ("model.id-taken", "model.name-taken")
    assert sorted(codes(doc)) == ["model.id-taken", "model.name-taken"]
    assert not (project / "out").exists()


def test_a_syntax_error_is_exit_3_with_no_output(project: Path, run: Run) -> None:
    (project / "model.pdl").write_text(source_text("ethernet"))
    code, doc = run("model.pdl", "-o", "out", *PROFILE)
    assert code == 3 and doc["error"]["code"] == "model.syntax.unknown-type"
    assert doc["diagnostics"][0]["location"]["file"] == "model.pdl"
    assert not (project / "out").exists()


def test_an_unreadable_model_is_exit_3(project: Path, run: Run) -> None:
    code, doc = run("missing.pdl", *PROFILE)
    assert code == 3 and doc["error"]["code"] == "model.unreadable"
    (project / "bad.pdl").write_bytes(b"Protocol {\xff")
    code, doc = run("bad.pdl", *PROFILE)
    assert code == 3 and doc["error"]["code"] == "model.unreadable"
    code, doc = run(".", *PROFILE)
    assert code == 3 and doc["error"]["code"] == "model.unreadable"


def test_an_invalid_lock_is_exit_7_unless_force(project: Path, run: Run) -> None:
    (project / "out").mkdir()
    (project / "out" / "plugin.lock").write_text("{not json")
    code, doc = run("model.pdl", "-o", "out", *PROFILE)
    assert code == 7 and doc["error"]["code"] == "state.invalid-lock"
    code, doc = run("model.pdl", "-o", "out", *PROFILE, "--force")
    assert code == 0 and codes(doc) == ["state.invalid-lock"]
    parse_lock((project / "out" / "plugin.lock").read_text())


def test_a_lock_from_a_newer_generator_is_refused(project: Path, run: Run) -> None:
    assert run("model.pdl", "-o", "out", *PROFILE)[0] == 0
    lock = project / "out" / "plugin.lock"
    lock.write_text(lock.read_text().replace('"lock_version": 1', '"lock_version": 2'))
    code, doc = run("model.pdl", "-o", "out", *PROFILE)
    assert code == 7 and "newer mmt-plugin" in doc["error"]["message"]


# --- the SDK stage and --strict ----------------------------------------------


def test_without_an_sdk_or_a_pin_the_newest_profile_is_used_with_a_warning(
    project: Path, run: Run
) -> None:
    code, doc = run("model.pdl", "-o", "out")
    assert code == 0 and codes(doc) == ["sdk.profile-default"]
    assert doc["context"]["sdk"]["profile_source"] == "default"
    code, doc = run("model.pdl", "-o", "out2", "--strict")
    assert code == 4 and doc["error"]["code"] == "sdk.profile-default"
    assert not (project / "out2").exists()


def test_the_profile_of_an_sdk_prefix(
    project: Path, run: Run, make_prefix: Callable[..., Path]
) -> None:
    prefix = make_prefix(project / "sdk")
    code, doc = run("model.pdl", "-o", "out", "--sdk", str(prefix))
    assert code == 0, doc["error"]
    assert doc["context"]["sdk"]["profile_source"] == "sdk"
    assert doc["context"]["sdk"]["source"] == "--sdk"
    code, doc = run("model.pdl", "-o", "out", "--sdk", str(project / "nothing"))
    assert code == 4 and doc["error"]["code"] == "sdk.invalid-prefix"
    code, doc = run("model.pdl", "-o", "out", "--sdk-profile", "9.9")
    assert code == 4 and doc["error"]["code"] == "sdk.profile-not-found"


def test_strict_fails_on_a_model_warning_with_its_class(project: Path, run: Run) -> None:
    text = source_text(MODEL).replace(' scope="SCOPE_PACKET"', "", 1)  # model.default-scope
    (project / "model.pdl").write_text(text)
    code, doc = run("model.pdl", "-o", "out", *PROFILE)
    assert code == 0 and codes(doc) == ["model.default-scope"]
    code, doc = run("model.pdl", "-o", "out2", *PROFILE, "--strict")
    assert code == 3 and doc["error"]["code"] == "model.default-scope"
    assert not (project / "out2").exists()


# --- human output ------------------------------------------------------------


def test_plain_records_are_action_tab_path(
    project: Path, command: GenerateCommand, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["generate", "model.pdl", "-o", "out", *PROFILE], commands=[command]) == 0
    out = capsys.readouterr().out
    assert out.splitlines() == [
        f"created\tout/{C}",
        f"created\tout/{H}",
        "created\tout/plugin.lock",
    ]


def test_the_styled_view_is_a_generate_box() -> None:
    files = [
        {"path": "generated/x.c", "action": "created", "sha256": "0" * 64},
        {"path": "generated/x.h", "action": "unchanged", "sha256": "0" * 64},
    ]
    lock = {"path": "plugin.lock", "action": "updated", "sha256": "0" * 64}
    st = StreamStyle(styled=True, color=ColorTier.NONE, unicode=True, width=60)
    text = generate_module._view("x", files, lock, False, st)
    lines = text.splitlines()
    assert lines[0].startswith("╭─┐generate x┌")
    assert "● created    generated/x.c" in text
    assert "● unchanged  generated/x.h" in text
    assert "▲ updated    plugin.lock" in text
    assert "3 files · 1 created · 1 updated · 1 unchanged" in lines[-1]
    stale = [{**f, "action": "would-update"} for f in files]
    text = generate_module._view("x", stale, lock, True, st)
    (row,) = [line for line in text.splitlines() if "generated/x.c" in line]
    assert "✗ stale" in row
    assert "3 files · 1 updated · 2 stale" in text.splitlines()[-1]
    assert "\x1b" not in text
