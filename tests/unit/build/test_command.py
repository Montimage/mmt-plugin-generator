"""``mmt-plugin build`` with a fake SDK and a fake compiler (``fakes.py``):
the stages, generate chaining and ``--no-deps``, the no-op on unchanged
inputs, ``--rebuild``, ``--dry-run``, the atomic link, compiler diagnostics,
the missing-hook check, the setup errors and SIGINT (``docs/design/cli.md``,
sections 4, 5, 6, 7 and 8). ``test_sdk.py`` builds every corpus model
against a real mmt-dpi."""

from __future__ import annotations

import json
import os
import shlex
import signal
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from mmt_plugin import schemas
from mmt_plugin.cli import main
from mmt_plugin.codegen import scaffold
from mmt_plugin.commands import build as build_module
from mmt_plugin.commands.build import CFLAGS, LDFLAGS, BuildCommand, parse_compiler_output
from mmt_plugin.commands.generate import make_generation
from mmt_plugin.diagnostics import Severity
from mmt_plugin.sdk.resolve import resolve_profile
from mmt_plugin.ui.streams import ColorTier, StreamStyle

from .fakes import fake_cc, fake_sdk

#: A model with a user hook (an attribute without an offset), so the scaffold
#: defines two hooks: the attribute's and register_parents.
MODEL = """Protocol {
    Properties { label = "fakeproto" id = "991" encoding = "network" }
    Attributes {
        attribute { alias="kind" data_type="MMT_U8_DATA" data_len="1" offset="0" scope="packet" }
        attribute { alias="extra" data_type="MMT_U32_DATA" data_len="4" scope="packet" }
    }
}
"""
IMPL = "src/fakeproto_impl.c"
SO = "build/mmtp_fakeproto.so"

Run = Callable[..., tuple[int, dict[str, Any]]]


def _scaffold(text: str = MODEL) -> str:
    choice = resolve_profile("1.10.2", {}, None, None)
    generation, _, error = make_generation("model.pdl", text.encode(), choice)
    assert generation is not None, error
    return scaffold(generation, choice.profile).text


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The current directory: ``model.pdl`` and its scaffold in ``src/``; a
    fake SDK and compiler outside it; ``FAKE_CC_LOG`` records each call."""
    work = tmp_path / "project"
    (work / "src").mkdir(parents=True)
    (work / "model.pdl").write_text(MODEL)
    (work / IMPL).write_text(_scaffold())
    monkeypatch.chdir(work)
    for name in ("MMT_PLUGIN_SDK_PROFILE", "MMT_BASE", "CC", "FAKE_CC_LINK_FAIL", "FAKE_CC_SLEEP"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("FAKE_CC_LOG", str(tmp_path / "cc.log"))
    return work


@pytest.fixture
def sdk(tmp_path: Path) -> Path:
    return fake_sdk(tmp_path / "sdk")


@pytest.fixture
def cc(tmp_path: Path) -> Path:
    return fake_cc(tmp_path / "bin")


def _calls(project: Path) -> list[list[str]]:
    """The fake compiler's calls since the last one, ``--version`` excluded."""
    log = project.parent / "cc.log"
    if not log.exists():
        return []
    calls = [json.loads(line) for line in log.read_text().splitlines()]
    log.unlink()
    return [c for c in calls if c != ["--version"]]


@pytest.fixture
def run(tmp_path: Path, sdk: Path, cc: Path, capsys: pytest.CaptureFixture[str]) -> Run:
    """``mmt-plugin --json build model.pdl --sdk SDK --cc CC ARGS``: the exit
    code and the envelope, checked against the envelope and result schemas."""
    envelope = Draft202012Validator(schemas.load_cli_schema(schemas.ENVELOPE))
    result = Draft202012Validator(schemas.result_schema("build"))
    command = BuildCommand(pkg_config_dirs=[], default_prefix=str(tmp_path / "no-sdk"))

    def go(*args: str, model: str | None = "model.pdl", tool: bool = True) -> tuple[int, Any]:
        argv = ["--json", "build", *([model] if model else [])]
        if tool:
            argv += ["--sdk", str(sdk), "--cc", str(cc)]
        code = main([*argv, *args], commands=[command])
        out = capsys.readouterr()
        assert out.err == ""
        doc: dict[str, Any] = json.loads(out.out)
        envelope.validate(doc)
        assert doc["exit_code"] == code
        if doc["result"] is not None:
            result.validate(doc["result"])
        return code, doc

    return go


def _stages(doc: dict[str, Any]) -> dict[str, str]:
    return {s["name"]: s["status"] for s in doc["result"]["stages"]}


def _codes(doc: dict[str, Any]) -> list[str]:
    return [d["code"] for d in doc["diagnostics"]]


# --- a build, and the no-op -------------------------------------------------


def test_a_build_generates_compiles_checks_the_hooks_and_links(
    project: Path, run: Run, cc: Path, sdk: Path
) -> None:
    code, doc = run()
    assert code == 0, doc["error"]
    result = doc["result"]
    assert _stages(doc) == dict.fromkeys(("generate", "compile", "hooks", "link"), "ran")
    assert (project / "generated" / "fakeproto_mmt_plugin.c").is_file()
    assert (project / "plugin.lock").exists() or (project / "generated" / "plugin.lock").exists()
    so = project / SO
    assert so.is_file()
    assert result["artifact"]["path"] == SO
    assert len(result["artifact"]["sha256"]) == 64
    assert result["up_to_date"] is False and result["dry_run"] is False
    assert result["cc"] == {"path": str(cc), "version": "fakecc (Fake) 1.0"}
    assert result["cflags"] == ["-std=gnu11", *CFLAGS]
    assert result["ldflags"] == list(LDFLAGS)
    calls = _calls(project)
    assert len(calls) == 3  # the generated source, src/fakeproto_impl.c, the link
    includes = ["-I", f"{project}/generated", "-I", f"{project}/src", "-I", f"{sdk}/dpi/include"]
    for call in calls[:2]:
        call[call.index("-MF") + 1] = "DEPFILE"
    assert calls[0] == [
        *result["cflags"],
        *includes,
        "-MD",
        "-MF",
        "DEPFILE",
        "-c",
        f"{project}/generated/fakeproto_mmt_plugin.c",
        "-o",
        f"{project}/build/obj/generated/fakeproto_mmt_plugin.o",
    ]
    assert calls[1] == [
        *result["cflags"],
        *includes,
        "-MD",
        "-MF",
        "DEPFILE",
        "-c",
        f"{project}/{IMPL}",
        "-o",
        f"{project}/build/obj/src/fakeproto_impl.o",
    ]
    assert calls[2] == [
        *LDFLAGS,
        f"{project}/build/obj/generated/fakeproto_mmt_plugin.o",
        f"{project}/build/obj/src/fakeproto_impl.o",
        f"{sdk}/dpi/lib/libmmt_core.so.1.10.2",
        "-o",
        f"{project}/build/.mmtp_fakeproto.so.tmp",
    ]
    assert len(result["commands"]) == 3
    assert result["commands"][2] == shlex.join([str(cc), *calls[2]])
    # Only the plugin, its stamp and the objects are left in build/.
    left = sorted(
        p.relative_to(project / "build").as_posix() for p in (project / "build").rglob("*")
    )
    assert left == [
        ".mmtp_fakeproto.build.json",
        "mmtp_fakeproto.so",
        "obj",
        "obj/generated",
        "obj/generated/fakeproto_mmt_plugin.d",
        "obj/generated/fakeproto_mmt_plugin.o",
        "obj/src",
        "obj/src/fakeproto_impl.d",
        "obj/src/fakeproto_impl.o",
    ]


def test_unchanged_inputs_are_a_no_op_and_rebuild_forces_it(project: Path, run: Run) -> None:
    assert run()[0] == 0
    _calls(project)
    so = project / SO
    before = so.stat().st_mtime_ns
    code, doc = run()
    assert code == 0
    assert doc["result"]["up_to_date"] is True
    assert _stages(doc) == dict.fromkeys(("generate", "compile", "hooks", "link"), "up-to-date")
    assert doc["result"]["commands"] == []
    assert doc["result"]["artifact"]["path"] == SO
    assert _calls(project) == []
    assert so.stat().st_mtime_ns == before
    code, doc = run("--rebuild")
    assert code == 0 and doc["result"]["up_to_date"] is False
    assert len(_calls(project)) == 3


@pytest.mark.parametrize(
    "change",
    [
        "user source",
        "user header",
        "nested header",
        "outside header",
        "model",
        "artifact",
        "flags",
    ],
)
def test_a_changed_input_rebuilds(
    project: Path, run: Run, change: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert run()[0] == 0
    _calls(project)
    if change == "user source":
        impl = project / IMPL
        impl.write_text(impl.read_text() + "\n/* edited */\n")
    elif change == "user header":
        (project / "src" / "extra.h").write_text("#define EXTRA 1\n")
    elif change in ("nested header", "outside header"):
        # Review of #19: a header below src/ or outside the project is an
        # input too, found through the compiler's dependency file.
        header = project / "src" / "inc" / "x.h"
        if change == "outside header":
            header = project.parent / "common" / "x.h"
        rel = os.path.relpath(header, project / "src")
        header.parent.mkdir(parents=True, exist_ok=True)
        header.write_text("#define X 1\n")
        impl = project / IMPL
        impl.write_text(f'#include "{rel}"\n' + impl.read_text())
        assert run()[0] == 0
        _calls(project)
        assert run()[1]["result"]["up_to_date"] is True
        header.write_text("#define X 2\n")
    elif change == "model":
        (project / "model.pdl").write_text(MODEL.replace('id = "991"', 'id = "992"'))
    elif change == "artifact":
        (project / SO).write_bytes(b"replaced by hand")
    else:
        monkeypatch.setattr(build_module, "CFLAGS", (*CFLAGS, "-g"))
    code, doc = run()
    assert code == 0, doc["error"]
    assert doc["result"]["up_to_date"] is False
    assert _stages(doc)["link"] == "ran"
    assert len(_calls(project)) == 3
    if change == "model":
        assert _stages(doc)["generate"] == "ran"


def test_another_compiler_rebuilds(project: Path, run: Run, tmp_path: Path) -> None:
    assert run()[0] == 0
    _calls(project)
    other = fake_cc(tmp_path / "other")
    code, doc = run("--cc", str(other))
    assert code == 0
    assert doc["result"]["up_to_date"] is False
    assert doc["result"]["cc"]["path"] == str(other)


def test_the_cc_environment_variable_picks_the_compiler(
    project: Path, run: Run, cc: Path, sdk: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CC", str(cc))
    code, doc = run("--sdk", str(sdk), tool=False)
    assert code == 0, doc["error"]
    assert doc["result"]["cc"]["path"] == str(cc)


def test_the_build_dir_option(project: Path, run: Run, tmp_path: Path) -> None:
    out = tmp_path / "elsewhere"
    code, doc = run("--build-dir", str(out))
    assert code == 0
    assert (out / "mmtp_fakeproto.so").is_file()
    assert doc["result"]["build_dir"] == out.as_posix()
    assert doc["result"]["artifact"]["path"] == (out / "mmtp_fakeproto.so").as_posix()
    assert not (project / "build").exists()


# --- --dry-run, generate chaining and --no-deps -----------------------------


def test_dry_run_prints_the_commands_and_writes_nothing(project: Path, run: Run) -> None:
    before = sorted(p.as_posix() for p in project.rglob("*"))
    code, doc = run("--dry-run")
    assert code == 0
    assert sorted(p.as_posix() for p in project.rglob("*")) == before
    assert _calls(project) == []
    result = doc["result"]
    assert result["dry_run"] is True and result["artifact"] is None
    assert _stages(doc) == dict.fromkeys(("generate", "compile", "hooks", "link"), "would-run")
    assert len(result["commands"]) == 3
    assert result["commands"][0].endswith("build/obj/generated/fakeproto_mmt_plugin.o")
    assert result["commands"][2].endswith("build/.mmtp_fakeproto.so.tmp")
    # The same bytes on a re-run.
    assert run("--dry-run")[1] == doc


def test_dry_run_after_a_build_is_up_to_date(project: Path, run: Run) -> None:
    assert run()[0] == 0
    code, doc = run("--dry-run")
    assert code == 0 and doc["result"]["up_to_date"] is True
    assert doc["result"]["commands"] == []


def test_no_deps_refuses_stale_generated_files(
    project: Path, run: Run, capsys: pytest.CaptureFixture[str]
) -> None:
    code, doc = run("--no-deps")
    assert code == 7
    assert doc["error"]["code"] == "state.stale"
    assert _stages(doc) == {
        "generate": "stale",
        "compile": "skipped",
        "hooks": "skipped",
        "link": "skipped",
    }
    assert not (project / "generated").exists()
    assert _calls(project) == []
    # Once generated, --no-deps builds.
    assert main(["generate", "model.pdl", "--sdk-profile", "1.10.2"]) == 0
    capsys.readouterr()
    code, doc = run("--no-deps")
    assert code == 0, doc["error"]
    assert _stages(doc)["generate"] == "up-to-date"


def test_a_hand_edited_generated_file_is_refused(project: Path, run: Run) -> None:
    assert run()[0] == 0
    source = project / "generated" / "fakeproto_mmt_plugin.c"
    source.write_text(source.read_text() + "/* by hand */\n")
    code, doc = run()
    assert code == 7
    assert doc["error"]["code"] == "state.modified"
    assert _stages(doc)["generate"] == "failed"
    assert "state.modified" in _codes(doc)


# --- failures ---------------------------------------------------------------


def test_a_missing_hook_fails_before_the_link(project: Path, run: Run) -> None:
    impl = project / IMPL
    text = impl.read_text()
    start = text.index("int fakeproto_hook_register_parents(")
    impl.write_text(text[:start])
    code, doc = run()
    assert code == 5
    assert doc["error"]["code"] == "build.missing-hook"
    assert "fakeproto_hook_register_parents" in doc["error"]["message"]
    missing = [d for d in doc["diagnostics"] if d["code"] == "build.missing-hook"]
    assert len(missing) == 1
    assert missing[0]["location"]["file"] == IMPL
    assert "int fakeproto_hook_register_parents(protocol_t *protocol_struct)" in missing[0]["hint"]
    assert _stages(doc) == {
        "generate": "ran",
        "compile": "ran",
        "hooks": "failed",
        "link": "skipped",
    }
    assert not (project / SO).exists()
    assert doc["result"]["artifact"] is None
    assert len(_calls(project)) == 2  # no link


def test_no_user_code_misses_every_hook(project: Path, run: Run) -> None:
    (project / IMPL).unlink()
    code, doc = run()
    assert code == 5
    assert doc["error"]["code"] == "build.missing-hook"
    assert "there is no src/*.c" in doc["error"]["message"]
    assert "mmt-plugin init" in doc["error"]["hint"]
    assert _codes(doc).count("build.missing-hook") == 2


def _at(file: str, line: int, column: int) -> dict[str, Any]:
    return {"file": file, "line": line, "column": column, "end_line": None, "end_column": None}


def test_a_compile_error_is_a_located_diagnostic(project: Path, run: Run) -> None:
    impl = project / IMPL
    impl.write_text("#warning careful\n" + impl.read_text() + "#error boom\n")
    lines = impl.read_text().count("\n")
    code, doc = run()
    assert code == 5
    assert doc["error"]["code"] == "build.compile-failed"
    assert IMPL in doc["error"]["message"]
    cc = [d for d in doc["diagnostics"] if d["code"] == "build.cc"]
    assert [(d["severity"], d["message"], d["location"]) for d in cc] == [
        ("warning", "warning careful", _at(IMPL, 1, 2)),
        ("error", "error boom", _at(IMPL, lines, 2)),
    ]
    assert _stages(doc)["compile"] == "failed"
    assert _stages(doc)["link"] == "skipped"
    assert not (project / SO).exists()


def test_a_failed_link_keeps_the_previous_plugin(
    project: Path, run: Run, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert run()[0] == 0
    so = project / SO
    good = so.read_bytes()
    impl = project / IMPL
    impl.write_text(impl.read_text() + "\n/* changed */\n")
    monkeypatch.setenv("FAKE_CC_LINK_FAIL", "1")
    code, doc = run()
    assert code == 5
    assert doc["error"]["code"] == "build.link-failed"
    assert so.read_bytes() == good
    assert not (project / "build" / ".mmtp_fakeproto.so.tmp").exists()
    messages = [d["message"] for d in doc["diagnostics"] if d["code"] == "build.cc"]
    assert "x.c:(.text+0x5): undefined reference to `nope'" in messages
    assert "collect2: error: ld returned 1 exit status" in messages
    assert all(d["location"] is None for d in doc["diagnostics"] if d["code"] == "build.cc")
    # The failed build did not record its inputs: the next one builds.
    monkeypatch.delenv("FAKE_CC_LINK_FAIL")
    code, doc = run()
    assert code == 0 and doc["result"]["up_to_date"] is False


def test_a_model_error_stops_at_generate(project: Path, run: Run) -> None:
    (project / "model.pdl").write_text("Protocol {")
    code, doc = run()
    assert code == 3
    assert _stages(doc) == {
        "generate": "failed",
        "compile": "skipped",
        "hooks": "skipped",
        "link": "skipped",
    }
    assert not (project / "generated").exists()


def test_strict_fails_on_a_model_warning(project: Path, run: Run) -> None:
    (project / "model.pdl").write_text(MODEL.replace(' offset="0" scope="packet"', ' offset="0"'))
    code, doc = run("--strict")
    assert code == 3
    assert doc["error"]["code"] == "model.default-scope"
    assert not (project / "generated").exists()
    assert run()[0] == 0  # a warning only, without --strict


def test_no_sdk_is_exit_4(project: Path, run: Run, cc: Path) -> None:
    code, doc = run("--cc", str(cc), tool=False)
    assert code == 4
    assert doc["error"]["code"] == "sdk.not-found"


def test_an_sdk_without_libmmt_core_is_exit_4(project: Path, run: Run, tmp_path: Path) -> None:
    bare = fake_sdk(tmp_path / "bare", core=False)
    code, doc = run("--sdk", str(bare))
    assert code == 4
    assert doc["error"]["code"] == "sdk.invalid-prefix"
    assert "libmmt_core" in doc["error"]["message"]


def test_a_missing_compiler_is_exit_4(project: Path, run: Run, sdk: Path, tmp_path: Path) -> None:
    code, doc = run("--sdk", str(sdk), "--cc", str(tmp_path / "no-such-cc"), tool=False)
    assert code == 4
    assert doc["error"]["code"] == "sdk.cc-not-found"
    broken = tmp_path / "broken-cc"
    broken.write_text("#!/bin/sh\nexit 3\n")
    broken.chmod(0o755)
    code, doc = run("--sdk", str(sdk), "--cc", str(broken), tool=False)
    assert code == 4
    assert doc["error"]["code"] == "sdk.cc-not-found"


def test_an_empty_cc_or_stdin_model_is_a_usage_error(project: Path, run: Run, sdk: Path) -> None:
    code, doc = run("--sdk", str(sdk), "--cc", "", tool=False)
    assert code == 2
    assert doc["error"]["code"] == "usage.invalid-value"
    code, doc = run(model="-")
    assert code == 2
    assert "stdin" in doc["error"]["message"]


def test_the_default_model_waits_for_plugin_yaml(project: Path, run: Run) -> None:
    code, doc = run(model=None)
    assert code == 3
    assert doc["error"]["code"] == "model.unsupported-format"


# --- SIGINT -----------------------------------------------------------------


def test_sigint_kills_the_compiler_and_exits_130(
    project: Path, sdk: Path, cc: Path, tmp_path: Path
) -> None:
    pid_file = tmp_path / "cc.pid"
    env = {**os.environ, "FAKE_CC_SLEEP": str(pid_file)}
    argv = ["build", "model.pdl", "--sdk", str(sdk), "--cc", str(cc)]
    proc = subprocess.Popen(
        [sys.executable, "-m", "mmt_plugin", *argv],
        cwd=project,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        deadline = time.monotonic() + 30
        while not (pid_file.exists() and pid_file.read_text()):
            assert proc.poll() is None, proc.communicate()
            assert time.monotonic() < deadline, "the compiler never started"
            time.sleep(0.05)
        child = int(pid_file.read_text())
        proc.send_signal(signal.SIGINT)
        _, err = proc.communicate(timeout=30)
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()
    assert proc.returncode == 130, err
    deadline = time.monotonic() + 10
    while True:
        try:
            os.kill(child, 0)
        except ProcessLookupError:
            break
        assert time.monotonic() < deadline, "the compiler is still running"
        time.sleep(0.05)
    assert not (project / SO).exists()
    assert not (project / "build" / ".mmtp_fakeproto.so.tmp").exists()


# --- human output -----------------------------------------------------------


def test_plain_output_lists_the_stages_then_the_artifact(
    project: Path, sdk: Path, cc: Path, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    command = BuildCommand(pkg_config_dirs=[], default_prefix=str(tmp_path / "no-sdk"))
    argv = ["build", "model.pdl", "--sdk", str(sdk), "--cc", str(cc)]
    assert main(argv, commands=[command]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[:4] == ["generate\tran", "compile\tran", "hooks\tran", "link\tran"]
    assert lines[4].startswith(f"artifact\t{SO}\t")
    assert len(lines) == 5
    assert main([*argv, "--dry-run", "--rebuild"], commands=[command]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[1] == "compile\twould-run"
    assert [line.split("\t")[0] for line in lines[4:]] == ["command"] * 3


def _result(**changes: Any) -> dict[str, Any]:
    result: dict[str, Any] = {
        "stages": [{"name": n, "status": "ran"} for n in ("generate", "compile", "hooks", "link")],
        "artifact": {"path": SO, "sha256": "ab" * 32},
        "cc": {"path": "/usr/bin/gcc", "version": "gcc 13"},
        "cflags": ["-O2", "-Werror"],
        "ldflags": ["-shared"],
        "commands": ["gcc -c x.c"],
        "up_to_date": False,
        "dry_run": False,
    }
    result.update(changes)
    return result


def test_the_styled_view() -> None:
    st = StreamStyle(styled=True, color=ColorTier.NONE, unicode=True, width=100)
    text = build_module._view("fakeproto", _result(), 1234, st)
    lines = text.splitlines()
    assert lines[0].startswith("╭─┐build fakeproto┌")
    assert "● ran" in text
    assert f"artifact  {SO}" in text
    assert "size      1234 bytes" in text
    assert "cc        /usr/bin/gcc (gcc 13)" in text
    assert "cflags    -O2 -Werror" in text
    assert "gcc -c x.c" not in text
    assert "built" in lines[-1]
    dry = build_module._view(
        "fakeproto",
        _result(
            artifact=None,
            dry_run=True,
            stages=[{"name": "generate", "status": "would-run"}],
        ),
        None,
        st,
    )
    assert "gcc -c x.c" in dry
    assert "dry run · 1 command" in dry.splitlines()[-1]
    failed = build_module._view(
        "fakeproto",
        _result(artifact=None, stages=[{"name": "hooks", "status": "failed"}]),
        None,
        st,
    )
    assert "✗ failed" in failed
    assert "hooks failed" in failed.splitlines()[-1]
    assert "up to date" in build_module._view("x", _result(up_to_date=True), 1, st)


# --- the compiler's output --------------------------------------------------


def test_a_linker_warning_is_kept_when_the_link_succeeds(tmp_path: Path) -> None:
    out = "/usr/bin/ld: warning: x.o: missing .note.GNU-stack section\nchatter\n"
    found = parse_compiler_output(out, tmp_path, tmp_path, failed=False)
    assert [(d.severity, d.message, d.location) for d in found] == [
        (Severity.WARNING, out.splitlines()[0], None)
    ]


def test_compiler_output_becomes_located_diagnostics(tmp_path: Path) -> None:
    output = "\n".join(
        [
            "In file included from src/a.c:1:",
            f"{tmp_path}/generated/x.h:3:5: error: unknown type name 'foo'",
            "src/a.c:10:1: warning: unused variable 'y' [-Wunused-variable]",
            "src/a.c:12: note: a note without a column",
            "/elsewhere/b.h:1:1: fatal error: missing.h: No such file or directory",
            "compilation terminated.",
        ]
    )
    found = parse_compiler_output(output, tmp_path, tmp_path, failed=True)
    assert [(d.severity, d.message, str(d.location)) for d in found] == [
        (Severity.ERROR, "unknown type name 'foo'", "generated/x.h:3:5"),
        (Severity.WARNING, "unused variable 'y' [-Wunused-variable]", "src/a.c:10:1"),
        (Severity.NOTE, "a note without a column", "src/a.c:12"),
        (Severity.ERROR, "missing.h: No such file or directory", "/elsewhere/b.h:1:1"),
    ]
    assert {d.code for d in found} == {"build.cc"}


def test_a_failure_always_says_something(tmp_path: Path) -> None:
    found = parse_compiler_output("something odd\nlast words\n", tmp_path, tmp_path, failed=True)
    assert [(d.severity, d.message, d.location) for d in found] == [
        (Severity.ERROR, "last words", None)
    ]
    found = parse_compiler_output("", tmp_path, tmp_path, failed=True)
    assert [d.message for d in found] == ["the compiler failed with no message"]
    assert parse_compiler_output("chatter\n", tmp_path, tmp_path, failed=False) == []
