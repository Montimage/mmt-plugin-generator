"""The mmt-plugin-author skill and its evals, without an SDK (plan T4.2, #27).

``skills/mmt-plugin-author/evals/run_evals.py`` runs the entry and loop
commands of the skill's ``SKILL.md`` on each case; here every case runs its
no-SDK leg (``validate --no-sdk`` and ``generate``), and each envelope is
also validated against the package's JSON Schemas. The other tests keep the
skill in step with the CLI (its command blocks, its exit and error code
tables against ``mmt_plugin.exitcodes`` and ``mmt_plugin.diagnostics.CODES``)
and show that the evals fail when they should: a command that reads stdin or
opens the terminal, an envelope that breaks the contract, a fix that misses
the reported location, a deleted or rewritten packet test, a model without
an attached parent. ``test_sdk.py`` runs the cases with an SDK.
"""

from __future__ import annotations

import json
import shutil
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

import run_evals
from mmt_plugin import schemas
from mmt_plugin.diagnostics import CODES
from mmt_plugin.exitcodes import ExitCode

SKILL_TEXT = run_evals.SKILL_MD.read_text("utf-8")
CONTRACT = run_evals.load_contract(run_evals.CONTRACT_MD.read_text("utf-8"))
BLOCKS = run_evals.skill_blocks(SKILL_TEXT)
CASES = run_evals.case_dirs()


def validate_schemas(result: run_evals.CaseResult) -> None:
    """Every envelope of ``result`` against the envelope schema and its
    command's ``result`` schema."""
    envelope = Draft202012Validator(schemas.load_cli_schema(schemas.ENVELOPE))
    for step in result.steps:
        assert step.envelope is not None, step
        envelope.validate(step.envelope)
        name = step.command or "version"
        if step.envelope["result"] is not None and schemas.has_result_schema(name):
            Draft202012Validator(schemas.result_schema(name)).validate(step.envelope["result"])


def copy_case(tmp_path: Path, name: str, change: Callable[[dict[str, Any]], None]) -> Path:
    """A copy of the case ``name`` under ``tmp_path``, its ``case.json``
    changed by ``change``."""
    target = tmp_path / "cases" / name
    shutil.copytree(run_evals.CASES_DIR / name, target)
    case = json.loads((target / "case.json").read_text("utf-8"))
    change(case)
    (target / "case.json").write_text(json.dumps(case), "utf-8")
    return target


def run(case_dir: Path, tmp_path: Path) -> run_evals.CaseResult:
    work = tmp_path / "work"
    work.mkdir()
    return run_evals.run_case(case_dir, work=work)


# --- the cases ------------------------------------------------------------


@pytest.mark.parametrize("case_dir", CASES, ids=lambda p: p.name)
def test_the_case_passes_without_an_sdk(case_dir: Path, tmp_path: Path) -> None:
    result = run(case_dir, tmp_path)
    assert result.problems == []
    assert result.ok
    validate_schemas(result)
    commands = [s.command for s in result.steps if s.run > 0]
    assert set(commands) <= {"validate", "generate"}


def test_the_cases_cover_every_entry_point() -> None:
    entries = {run_evals.load_case(d)["entry"] for d in CASES}
    assert entries == {"spec", "pcap", "pdl"}
    assert {k for k in BLOCKS if k.startswith("entry ")} == {f"entry {e}" for e in entries}


@pytest.mark.parametrize("case_dir", CASES, ids=lambda p: p.name)
def test_every_case_pins_the_profile_in_its_first_run(case_dir: Path) -> None:
    case = run_evals.load_case(case_dir)
    texts = []
    for edit in case["runs"][0]["edits"]:
        if "write" in edit and edit["write"] == "plugin.yaml":
            texts.append((case_dir / edit["from"]).read_text("utf-8"))
        texts.append(str(edit.get("new", "")))
    assert any('profile: "' in t for t in texts)


# --- the skill's text against the CLI -------------------------------------


def test_the_loop_blocks_are_the_four_commands_with_json() -> None:
    sdk = BLOCKS["loop sdk"]
    assert [run_evals.command_of(a) for a in sdk] == list(run_evals.LOOP_COMMANDS)
    no_sdk = BLOCKS["loop no-sdk"]
    assert [run_evals.command_of(a) for a in no_sdk] == ["validate", "generate"]
    for args in sdk:
        assert "--sdk" in args and "<prefix>" in args
    for args in sdk[2:]:
        assert "--cc" in args
    assert "--no-sdk" in no_sdk[0]
    for args in no_sdk:
        assert "--sdk-profile" in args


@pytest.mark.parametrize("key", sorted(BLOCKS))
def test_every_block_command_is_json_and_reads_no_stdin(key: str) -> None:
    for args in BLOCKS[key]:
        assert "--json" in args
        assert "-" not in args
        assert not {"--force", "--system", "--strict"} & set(args)
        assert "/opt/mmt" not in " ".join(args)


def test_the_entry_blocks_create_a_project_then_convert_or_scaffold() -> None:
    commands = {k: [run_evals.command_of(a) for a in v] for k, v in BLOCKS.items()}
    assert commands["entry spec"] == ["init", "import"]
    assert commands["entry pcap"] == ["init", "scaffold"]
    assert commands["entry pdl"] == ["init", "import"]


def test_the_exit_tables_are_exitcodes() -> None:
    want = {code.value: code.error_class for code in ExitCode}
    assert dict(CONTRACT.classes) == want
    rows = run_evals._table(SKILL_TEXT, "Step 4: read the envelope and fix")
    assert {int(r[0]): r[1] for r in rows} == want


def test_every_registered_code_has_a_row() -> None:
    assert [code for code in CODES if not CONTRACT.documents(code)] == []


def test_every_row_names_registered_codes() -> None:
    assert len(set(CONTRACT.codes)) == len(CONTRACT.codes)
    for row in CONTRACT.codes:
        if row.endswith("*"):
            assert any(code.startswith(row[:-1]) for code in CODES), row
        else:
            assert row in CODES, row


# --- the contract checks fail when they should ----------------------------


def good_envelope() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "tool": {"name": "mmt-plugin", "version": "0"},
        "command": "validate",
        "ok": False,
        "exit_code": 3,
        "error": {"class": "model", "code": "model.schema", "message": "m", "hint": None},
        "diagnostics": [
            {
                "severity": "error",
                "code": "model.schema",
                "message": "m",
                "hint": None,
                "location": {"file": "plugin.yaml", "line": 6, "column": 13},
                "related": [],
            }
        ],
        "context": {"project": ".", "sdk": {"prefix": None}},
        "result": {},
    }


def check(env: dict[str, Any], *, stderr: str = "", code: int = 3, sdk: bool = True) -> list[str]:
    stdout = json.dumps(env) + "\n"
    return run_evals.check_envelope(stdout, stderr, code, "validate", CONTRACT, sdk=sdk)[1]


def test_a_good_envelope_has_no_problem() -> None:
    assert check(good_envelope()) == []


@pytest.mark.parametrize(
    ("change", "problem"),
    [
        (lambda e: e.update(schema_version=2), "schema_version"),
        (lambda e: e.update(ok=True), "ok is True"),
        (lambda e: e.update(exit_code=6), "process exited"),
        (lambda e: e.update(command="build"), "command is"),
        (lambda e: e["error"].update({"class": "test"}), "error.class"),
        (lambda e: e["error"].update(code="model.no-such-code"), "no row in contract.md"),
        (lambda e: e["error"].update(code="test.packet-failed"), "is not of the class"),
        (lambda e: e["diagnostics"][0].update(code="model.nope"), "no row in contract.md"),
        (lambda e: e["diagnostics"][0].update(severity="fatal"), "severity"),
        (lambda e: e["diagnostics"][0].update(location=None), "no located error"),
        (lambda e: e["diagnostics"][0]["location"].update(line=0), "location.line"),
        (lambda e: e["context"]["sdk"].update(prefix="/opt/mmt"), "has no SDK"),
    ],
)
def test_a_broken_envelope_is_reported(
    change: Callable[[dict[str, Any]], Any], problem: str
) -> None:
    env = good_envelope()
    change(env)
    problems = check(env, sdk=False)
    assert any(problem in p for p in problems), problems


def test_a_failure_the_skill_does_not_fix_at_a_location_needs_none() -> None:
    env = good_envelope()
    env["error"].update(code="model.unreadable")
    env["diagnostics"] = []
    assert check(env) == []
    env = good_envelope()
    env.update(exit_code=6)
    env["error"].update({"class": "test", "code": "test.load-failed"})
    env["diagnostics"][0].update(severity="note", code="test.load-failed", location=None)
    assert check(env, code=6) == []


def test_a_compile_failure_without_a_location_needs_none() -> None:
    # ``cc1: fatal error: ...`` has no file:line, and the hooks stage's
    # compile-failed (an object that is not ELF) has no diagnostic at all.
    env = good_envelope()
    env.update(command="build", exit_code=5)
    env["error"].update({"class": "build", "code": "build.compile-failed"})
    env["diagnostics"][0].update(code="build.cc", message="cc1: fatal error", location=None)
    stdout = json.dumps(env) + "\n"
    assert run_evals.check_envelope(stdout, "", 5, "build", CONTRACT)[1] == []
    env["diagnostics"] = []
    stdout = json.dumps(env) + "\n"
    assert run_evals.check_envelope(stdout, "", 5, "build", CONTRACT)[1] == []


def usage_envelope(command: str | None) -> dict[str, Any]:
    env = good_envelope()
    env.update(command=command, exit_code=2, result=None, diagnostics=[])
    env["error"].update({"class": "usage", "code": "usage.unknown-option"})
    return env


def test_a_usage_error_may_have_no_command() -> None:
    # The argument parser fails before it knows the command (cli.md, 5).
    assert check(usage_envelope(None), code=2) == []
    assert check(usage_envelope("validate"), code=2) == []
    assert any("command is 'build'" in p for p in check(usage_envelope("build"), code=2))
    env = good_envelope()
    env.update(command=None)
    assert any("command is None" in p for p in check(env))


def test_stderr_and_a_second_document_are_reported() -> None:
    assert any("stderr" in p for p in check(good_envelope(), stderr="warning\n"))
    stdout = json.dumps(good_envelope()) + "\n{}\n"
    env, problems = run_evals.check_envelope(stdout, "", 3, "validate", CONTRACT)
    assert env is None and any("one JSON document" in p for p in problems)


def test_an_exit_code_outside_the_table_is_reported() -> None:
    env = good_envelope()
    env.update(exit_code=9)
    assert any("exit table" in p for p in check(env, code=9))


# --- no command may read stdin or the terminal (P5) -----------------------


@pytest.mark.parametrize("code", ["input()", "import sys; sys.stdin.buffer.read()"])
def test_the_guard_fails_a_command_that_reads_stdin(code: str) -> None:
    returncode, _, _, problems = run_evals.run_cli([sys.executable, "-c", code], timeout=2)
    assert returncode is None
    assert problems and "waited for input" in problems[0]


def test_the_guard_gives_no_terminal() -> None:
    returncode, _, err, problems = run_evals.run_cli(
        [sys.executable, "-c", "open('/dev/tty')"], timeout=30
    )
    assert problems == []
    assert returncode != 0 and "OSError" in err


def test_the_guard_catches_the_cli_reading_stdin(tmp_path: Path) -> None:
    returncode, _, _, problems = run_evals.run_cli(
        [sys.executable, "-m", "mmt_plugin", "--json", "validate", "-", "--no-sdk"],
        cwd=tmp_path,
        timeout=5,
    )
    assert returncode is None and problems


# --- the evals fail when the agent's work is wrong ------------------------


def test_a_fix_that_misses_the_location_fails(tmp_path: Path) -> None:
    def change(case: dict[str, Any]) -> None:
        miss = {
            "edits": [{"replace": "plugin.yaml", "old": "# TELEM,", "new": "# TELEM (2),"}],
            "expect": case["runs"][0]["expect"],
        }
        case["runs"].insert(1, miss)

    result = run(copy_case(tmp_path, "spec-telem", change), tmp_path)
    assert "run 2: the edits do not touch plugin.yaml:6 (model.schema)" in result.problems


def test_a_run_that_stops_elsewhere_fails(tmp_path: Path) -> None:
    def change(case: dict[str, Any]) -> None:
        case["runs"][0]["expect"]["error_code"] = "model.duplicate-name"

    result = run(copy_case(tmp_path, "spec-telem", change), tmp_path)
    assert not result.ok
    assert any("fails with model.schema" in p for p in result.problems)


@pytest.mark.parametrize(
    ("edit", "problem"),
    [
        ({"remove": "tests/telem-ack.yaml"}, "deletes the packet test tests/telem-ack.yaml"),
        (
            {"replace": "tests/telem-ack.yaml", "old": "value: 42", "new": "value: 43"},
            "changes the expected values of sequence in tests/telem-ack.yaml",
        ),
        (
            {
                "regex": "tests/telem-ack.yaml",
                "pattern": '^    - name: "sequence"\\n(?:      .*\\n)*',
                "new": "",
            },
            "drops sequence but plugin.yaml keeps it in tests/telem-ack.yaml",
        ),
        (
            {
                "regex": "tests/telem-reading.yaml",
                "pattern": "value: 1\\n(.*\\n(?:.*\\n){3}.*)value: 2\\n",
                "new": "value: 2\\n\\1value: 1\\n",
            },
            "changes the expected values of version in tests/telem-reading.yaml",
        ),
        (
            {"replace": "tests/telem-ack.yaml", "old": "00 00 00 2a", "new": "00 00 00 2b"},
            "changes the bytes or the expected protocol in tests/telem-ack.yaml",
        ),
        (
            {
                "regex": "tests/telem-ack.yaml",
                "pattern": '(name: "sequence"\\n.*\\n)(?:      .*\\n)*',
                "new": '\\1      status: "absent"\\n',
            },
            "changes the expected values of sequence in tests/telem-ack.yaml",
        ),
        (
            {"regex": "plugin.yaml", "pattern": "^parents:\\n(?:  .*\\n)*", "new": ""},
            "green: plugin.yaml declares no parent",
        ),
    ],
)
def test_wrong_work_in_the_last_run_fails(
    tmp_path: Path, edit: dict[str, str], problem: str
) -> None:
    def change(case: dict[str, Any]) -> None:
        case["runs"][-1]["edits"].append(edit)

    result = run(copy_case(tmp_path, "spec-telem", change), tmp_path)
    assert not result.ok
    assert any(problem in p for p in result.problems), result.problems


def test_a_parent_the_user_code_does_not_attach_fails(tmp_path: Path) -> None:
    """P6: the tcp parent has no classify, and init's stub hook attaches nothing."""

    def change(case: dict[str, Any]) -> None:
        for run_ in case["runs"]:
            run_["edits"] = [e for e in run_["edits"] if e.get("write") != "src/rfc1006_impl.c"]

    result = run(copy_case(tmp_path, "pdl-rfc1006", change), tmp_path)
    assert not result.ok
    assert (
        "green: the parent tcp has no classify, and src/rfc1006_impl.c does not attach the "
        "protocol to it" in result.problems
    )


def commented_label_and_id(case: dict[str, Any]) -> None:
    """Give the label and id lines of ``pdl-rfc1006`` trailing comments, as
    ``references/drafting.md``'s template writes them."""
    for run_ in case["runs"]:
        for edit in run_["edits"]:
            if edit.get("new") == "  label: rfc1006\n":
                edit["new"] = "  label: rfc1006   # mmtp_rfc1006.so\n"
            elif edit.get("new") == "  id: 962\n":
                edit["new"] = "  id: 962          # 950-999\n"


def test_a_commented_label_and_id_still_pass(tmp_path: Path) -> None:
    result = run(copy_case(tmp_path, "pdl-rfc1006", commented_label_and_id), tmp_path)
    assert result.ok, result.problems
    model = (tmp_path / "work" / "rfc1006" / "plugin.yaml").read_text("utf-8")
    assert "  label: rfc1006   # mmtp_rfc1006.so\n" in model
    assert "  id: 962          # 950-999\n" in model


def test_a_commented_label_does_not_skip_the_parent_check(tmp_path: Path) -> None:
    """A trailing comment on the label line must not hide an unattached parent."""

    def change(case: dict[str, Any]) -> None:
        commented_label_and_id(case)
        for run_ in case["runs"]:
            run_["edits"] = [e for e in run_["edits"] if e.get("write") != "src/rfc1006_impl.c"]

    result = run(copy_case(tmp_path, "pdl-rfc1006", change), tmp_path)
    assert not result.ok
    assert (
        "green: the parent tcp has no classify, and src/rfc1006_impl.c does not attach the "
        "protocol to it" in result.problems
    )


@pytest.mark.parametrize(
    ("line", "label"),
    [
        ("  label: telem\n", "telem"),
        ('  label: "telem"   # quoted\n', "telem"),
        ("  label: 'telem'\n", "telem"),
        ("  label: telem           # mmtp_telem.so; registered name TELEM\n", "telem"),
        ("  label: telem#x\n", None),
        ("  label: \"telem'\n", None),
    ],
)
def test_the_label_line_may_carry_a_comment(line: str, label: str | None) -> None:
    found = run_evals._LABEL.search("protocol:\n" + line + "  id: 963   # 950-999\n")
    assert (found.group(2) if found else None) == label
    assert run_evals._ID.search("protocol:\n" + line + "  id: 963   # 950-999\n")


def test_model_names_reads_plain_and_quoted_names() -> None:
    model = (
        "attributes:\n  - name: plain\n    type: MMT_U8_DATA\n"
        "  - name: \"double\"\n  - name: 'single'   # quoted\n"
        "  - {name: flow, type: MMT_U8_DATA}\n"
        "  - name: \"odd'\n"
    )
    assert run_evals._model_names(model) == {"plain", "double", "single", "flow"}


def failed_step(file: str, line: int | None = 3) -> run_evals.Step:
    env = {
        "diagnostics": [
            {
                "severity": "error",
                "code": "build.cc",
                "message": "m",
                "location": {"file": file, "line": line, "column": None},
            }
        ]
    }
    return run_evals.Step(1, ["build"], "build", 5, "", "", env)


def test_an_error_outside_the_project_is_fixed_in_the_model_or_the_user_code() -> None:
    before = {"plugin.yaml": "a\n", "src/x_impl.c": "int x;\n", "notes.txt": "n\n"}
    header = failed_step("/sdk/dpi/include/mmt_core.h")
    for path in ("src/x_impl.c", "plugin.yaml"):
        assert run_evals._fix_problems(header, before, {**before, path: "b\n"}, 1) == []
    for after in (before, {**before, "notes.txt": "m\n"}, {**before, "src/sub/y.c": "y\n"}):
        problems = run_evals._fix_problems(header, before, after, 1)
        assert problems == [
            "run 1: the edits change neither plugin.yaml nor src/*.c for "
            "/sdk/dpi/include/mmt_core.h (build.cc)"
        ]
    # Inside the project, the edit must still be at the reported line.
    impl = failed_step("src/x_impl.c", 1)
    assert run_evals._fix_problems(impl, before, {**before, "plugin.yaml": "b\n"}, 1) == [
        "run 1: the edits do not touch src/x_impl.c:1 (build.cc)"
    ]


def test_hook_parents_reads_a_commented_parents_line() -> None:
    model = "schema: 1\nparents:   # attached by the hook\n  - protocol: tcp\n"
    assert run_evals._hook_parents(model) == ["tcp"]


def test_hook_parents_reads_the_parents_without_classify() -> None:
    model = (
        "schema: 1\nparents:\n  - protocol: udp\n    classify:\n      match: []\n"
        '  - protocol: tcp    # by the hook\n  - protocol: "ip"\nattributes: []\n'
    )
    assert run_evals._hook_parents(model) == ["tcp", "ip"]
    assert run_evals._hook_parents("schema: 1\n") == []


# --- broken cases and the script ------------------------------------------


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (
            lambda c: c["runs"][-1].update(expect=c["runs"][-2]["expect"]),
            "must be green",
        ),
        (lambda c: c["runs"][0]["edits"].append({"remove": "../x"}), "not a path inside"),
        (lambda c: c["runs"][0]["expect"].update(stop="install"), "not a loop command"),
        (lambda c: c.update(runs=c["runs"] * 4), "1 to 10"),
        (lambda c: c["params"].pop("selector"), "params.selector"),
        (lambda c: c["runs"].__setitem__(0, []), "run 1 must be an object"),
        (lambda c: c["runs"][0]["edits"].append("x"), "must be an object"),
        (lambda c: c["runs"][0]["edits"].append({"remove": 1}), "is not a path"),
        (lambda c: c["runs"][0]["edits"].append({"write": "x"}), "needs 'from'"),
        (
            lambda c: c["runs"][0]["edits"].append(
                {"write": "x", "from": "../spec-telem/spec.md"}
            ),
            "not a path inside the case directory",
        ),
        (
            lambda c: c["runs"][0]["edits"].append({"append": "x", "from": "/etc/hostname"}),
            "not a path inside the case directory",
        ),
        (lambda c: c["runs"][0]["edits"].append({"write": "x", "from": "nope"}), "no case file"),
        (lambda c: c["runs"][0]["edits"].append({"copy": "x"}), "needs 'source'"),
        (lambda c: c["runs"][0]["edits"].append({"copy": "x", "source": "../x"}), "not a path"),
        (lambda c: c["runs"][0]["edits"].append({"replace": "x", "old": "a"}), "needs 'new'"),
        (lambda c: c["runs"][0]["edits"].append({"regex": "x", "new": "a"}), "needs 'pattern'"),
        (
            lambda c: c["runs"][0]["edits"].append({"regex": "x", "pattern": "(", "new": ""}),
            "does not compile",
        ),
    ],
)
def test_a_broken_case_is_an_eval_error(
    tmp_path: Path, change: Callable[[dict[str, Any]], Any], message: str
) -> None:
    with pytest.raises(run_evals.EvalError, match=message):
        run_evals.load_case(copy_case(tmp_path, "spec-telem", change))


def test_a_bad_regex_replacement_is_an_eval_error(tmp_path: Path) -> None:
    (tmp_path / "plugin.yaml").write_text("name: x\n", "utf-8")
    edit = {"regex": "plugin.yaml", "pattern": "x", "new": r"\2"}
    with pytest.raises(run_evals.EvalError, match="not a replacement"):
        run_evals.apply_edits([edit], tmp_path, tmp_path)


def test_main_prints_one_line_per_case(capsys: pytest.CaptureFixture[str]) -> None:
    assert run_evals.main(["--case", "pdl-rfc1006"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("PASS: pdl-rfc1006 without an SDK")
