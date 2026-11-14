"""Cross-command contract tests (``docs/design/cli.md``, sections 5 and 6).

They iterate the real parser, ``build_parser`` over the registry
(``mmt_plugin.commands.COMMANDS``) plus the test-only ``dummy``, and the
built-ins (``--version``, the no-command usage error), so a command that a
later issue registers is checked without a new test:

- ``--json`` before and after the command name prints exactly one envelope,
  the same bytes either way, valid against ``envelope.json`` and against the
  command's own ``result`` schema;
- each command's ``--help`` lists exactly the exit codes it can return;
- every command declares its exit codes and ships a ``result`` schema
  (``contract_problems`` fails otherwise);
- ``--json`` output carries no ESC byte, even with ``FORCE_COLOR``.

A command whose shortest successful run needs input files (``generate``
and ``validate`` need a model, ``build`` and ``test`` also an SDK and a
compiler) gets them from ``SETUP``. ``result.stats`` holds the only timings
(section 6), so the two runs are compared without it. With zero real commands the loop
still runs: the built-ins and ``dummy``.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from collections.abc import Callable, Iterator, Sequence
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from mmt_plugin import schemas
from mmt_plugin.cli import ALWAYS, build_parser, exit_codes_of, main
from mmt_plugin.codegen import scaffold
from mmt_plugin.commands import COMMANDS, Command
from mmt_plugin.commands.generate import make_generation
from mmt_plugin.exitcodes import ExitCode
from mmt_plugin.sdk.resolve import resolve_profile

DUMMY_RESULT_SCHEMA = Path(__file__).with_name("dummy_result.json")
CleanEnv = Callable[..., dict[str, str]]


def subparsers_of(parser: argparse.ArgumentParser) -> dict[str, argparse.ArgumentParser]:
    """The command parsers of ``parser``, by name (empty with no command)."""
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return dict(action.choices)
    return {}


def minimal_args(parser: argparse.ArgumentParser) -> list[str]:
    """The fewest arguments ``parser`` accepts: its first choice (or ``x``) for
    every required positional and required option."""
    args: list[str] = []
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            continue
        value = str(next(iter(action.choices))) if action.choices else "x"
        if not action.option_strings and action.nargs not in ("?", "*"):
            args.append(value)
        elif action.option_strings and action.required:
            args += [action.option_strings[0], *([value] if action.nargs != 0 else [])]
    return args


def result_schema_of(name: str) -> dict[str, Any]:
    if name == "dummy":
        schema: dict[str, Any] = json.loads(DUMMY_RESULT_SCHEMA.read_text())
        return schema
    return schemas.result_schema(name)


def contract_problems(commands: Sequence[object]) -> list[str]:
    """What each command lacks of the contract: a name, an exit-code list made
    of ``ExitCode``s, a ``result`` schema."""
    problems = []
    for command in commands:
        name = getattr(command, "name", None)
        if not isinstance(name, str) or not name:
            problems.append(f"{command!r}: no name")
            continue
        codes = getattr(command, "exit_codes", None)
        if codes is None or not all(isinstance(c, ExitCode) for c in codes):
            problems.append(f"{name}: no exit_codes list of ExitCode")
        if name in schemas.BUILTIN_RESULTS or name == schemas.ENVELOPE:
            problems.append(f"{name}: the name of a built-in schema")
        elif name != "dummy" and not schemas.has_result_schema(name):
            problems.append(f"{name}: no result schema {schemas.CLI_SCHEMA_DIR}/{name}.json")
    return problems


@pytest.fixture(autouse=True)
def in_tmp_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Run every case in an empty directory, so no command writes into the repo."""
    monkeypatch.chdir(tmp_path)


@pytest.fixture
def commands(dummy: Command) -> list[Command]:
    """The real registry plus the test-only dummy."""
    return [*COMMANDS, dummy]


def _registered(commands: Sequence[Command]) -> list[str]:
    return list(subparsers_of(build_parser(commands)))


def _run(
    argv: list[str], commands: Sequence[Command], capsys: pytest.CaptureFixture[str]
) -> tuple[int, str, str]:
    code = main(argv, commands=commands)
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def _one_envelope(out: str) -> dict[str, Any]:
    """``out`` is exactly one JSON document and one final newline."""
    assert out.endswith("}\n") and not out.endswith("\n\n")
    doc, end = json.JSONDecoder().raw_decode(out)
    assert out[end:] == "\n", "more than one document on stdout"
    assert isinstance(doc, dict)
    return doc


@pytest.fixture
def envelope_validator() -> Draft202012Validator:
    return Draft202012Validator(schemas.load_cli_schema(schemas.ENVELOPE))


# --- the registry ------------------------------------------------------------


def test_every_registered_command_declares_its_contract(commands: list[Command]) -> None:
    assert contract_problems(commands) == []


def test_contract_problems_catch_a_command_without_codes_or_schema() -> None:
    class NoCodes:
        name = "nocodes"

    class NoSchema:
        name = "noschema"
        exit_codes = (ExitCode.MODEL,)

    class BadCodes:
        name = "completion"
        exit_codes = (3,)

    class Builtin:
        name = "version"
        exit_codes = ()

    assert contract_problems([NoCodes(), NoSchema(), BadCodes(), Builtin()]) == [
        "nocodes: no exit_codes list of ExitCode",
        "nocodes: no result schema schemas/cli/v1/nocodes.json",
        "noschema: no result schema schemas/cli/v1/noschema.json",
        "completion: no exit_codes list of ExitCode",
        "version: the name of a built-in schema",
    ]


def test_the_parser_registers_exactly_the_registry(commands: list[Command]) -> None:
    assert _registered(commands) == [c.name for c in commands]
    assert _registered(list(COMMANDS)) == [c.name for c in COMMANDS]
    assert "completion" in _registered(list(COMMANDS))


def test_every_schema_in_the_registry_is_valid_json_schema() -> None:
    names = schemas.schema_names()
    assert {"envelope", "version", "completion"} <= set(names)
    for name in names:
        Draft202012Validator.check_schema(schemas.load_cli_schema(name))
    Draft202012Validator.check_schema(json.loads(DUMMY_RESULT_SCHEMA.read_text()))
    with pytest.raises(KeyError):
        schemas.result_schema("envelope")
    with pytest.raises(KeyError):
        schemas.result_schema("no-such-command")


def test_every_result_schema_belongs_to_a_command_or_a_builtin() -> None:
    known = {c.name for c in COMMANDS} | set(schemas.BUILTIN_RESULTS) | {schemas.ENVELOPE}
    assert set(schemas.schema_names()) <= known


# --- --json before and after the command -------------------------------------


#: A minimal model that generate accepts: no SDK conflict, no warning.
CONTRACT_MODEL = """Protocol {
    Properties { label = "contract" id = "990" encoding = "network" }
    Attributes {
        attribute { alias="kind" data_type="MMT_U8_DATA" data_len="1" offset="0" scope="packet" }
    }
}
"""


def _generate_args(directory: Path) -> list[str]:
    # A model file, a pinned profile (no SDK is looked for) and --dry-run, so
    # the run writes nothing and a second run prints the same envelope.
    (directory / "model.pdl").write_text(CONTRACT_MODEL)
    return ["model.pdl", "--sdk-profile", "1.10.2", "--dry-run"]


#: The commands whose shortest successful run needs input files: what to
#: write into the run's directory (the cwd), and the arguments to pass.
def _validate_args(directory: Path) -> list[str]:
    # No SDK is looked for (--no-sdk) and the profile is pinned: no warning.
    (directory / "model.pdl").write_text(CONTRACT_MODEL)
    return ["model.pdl", "--no-sdk", "--sdk-profile", "1.10.2"]


def _build_args(directory: Path) -> list[str]:
    # A fake SDK (headers and libmmt_core, never loaded) and a fake compiler
    # that only answers --version: --dry-run runs nothing else and writes
    # nothing, so a second run prints the same envelope.
    (directory / "model.pdl").write_text(CONTRACT_MODEL)
    sdk = directory / "sdk"
    (sdk / "dpi" / "include").mkdir(parents=True, exist_ok=True)
    (sdk / "dpi" / "include" / "mmt_log.h").write_text("")
    (sdk / "dpi" / "include" / "mmt_core.h").write_text('#define VERSION "1.10.2"\n')
    (sdk / "dpi" / "lib").mkdir(exist_ok=True)
    (sdk / "dpi" / "lib" / "libmmt_core.so.1.10.2").write_text("")
    cc = directory / "cc"
    cc.write_text("#!/bin/sh\necho 'fake cc 1.0'\n")
    cc.chmod(0o755)
    return ["model.pdl", "--sdk", str(sdk), "--cc", str(cc), "--dry-run"]


def _test_args(directory: Path) -> list[str]:
    # build's fake compiler (tests/unit/build/fakes.py), which compiles and
    # links, and a build made here, quietly: test finds the plugin up to date
    # and, with no packet test (a test.no-packets warning), runs no harness,
    # so a second run prints the same envelope.
    spec = importlib.util.spec_from_file_location(
        "contract_build_fakes", Path(__file__).parent / "build" / "fakes.py"
    )
    assert spec is not None and spec.loader is not None
    fakes = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fakes)
    (directory / "model.pdl").write_text(CONTRACT_MODEL)
    sdk = fakes.fake_sdk(directory / "sdk")
    (sdk / "plugins").mkdir()
    (sdk / "plugins" / "libmmt_tcpip.so").write_text("")
    cc = fakes.fake_cc(directory / "bin")
    choice = resolve_profile("1.10.2", {}, None, None)
    generation, _, _ = make_generation("model.pdl", CONTRACT_MODEL.encode(), choice)
    assert generation is not None
    impl = scaffold(generation, choice.profile)
    (directory / impl.path).parent.mkdir(exist_ok=True)
    (directory / impl.path).write_text(impl.text)
    args = ["--model", "model.pdl", "--sdk", str(sdk), "--cc", str(cc)]
    assert main(["-q", "build", "model.pdl", *args[2:]]) == 0
    return args


SETUP: dict[str, Callable[[Path], list[str]]] = {
    "generate": _generate_args,
    "validate": _validate_args,
    "build": _build_args,
    "test": _test_args,
}


def _cases(commands: Sequence[Command]) -> Iterator[tuple[str, list[str]]]:
    parser = build_parser(commands)
    for name, sub in subparsers_of(parser).items():
        setup = SETUP.get(name)
        args = minimal_args(sub) if setup is None else setup(Path.cwd())
        yield name, [name, *args]


def _without_stats(run: tuple[int, str, str]) -> tuple[int, Any, str]:
    """A run with its envelope's ``result.stats`` (timings) dropped."""
    code, out, err = run
    try:
        doc = json.loads(out)
    except ValueError:
        return code, out, err
    if isinstance(doc.get("result"), dict):
        doc["result"].pop("stats", None)
    return code, doc, err


def _check_command_envelopes(
    commands: Sequence[Command],
    capsys: pytest.CaptureFixture[str],
    validator: Draft202012Validator,
) -> list[str]:
    seen = []
    for name, argv in _cases(commands):
        before = _run(["--json", *argv], commands, capsys)
        after = _run([*argv, "--json"], commands, capsys)
        assert _without_stats(before) == _without_stats(after), name
        code, out, err = before
        assert err == "", (name, err)
        doc = _one_envelope(out)
        validator.validate(doc)
        assert doc["command"] == name
        assert doc["exit_code"] == code == 0, (name, doc["error"])
        Draft202012Validator(result_schema_of(name)).validate(doc["result"])
        seen.append(name)
    return seen


def test_every_command_prints_one_valid_envelope_with_json_before_or_after(
    commands: list[Command],
    capsys: pytest.CaptureFixture[str],
    envelope_validator: Draft202012Validator,
) -> None:
    seen = _check_command_envelopes(commands, capsys, envelope_validator)
    assert seen == [c.name for c in commands]


@pytest.mark.parametrize(
    ("argv", "schema", "code"),
    [
        (["--json", "--version"], "version", 0),
        (["--version", "--json"], "version", 0),
        (["--json"], None, 2),
        (["--json", "no-such-command"], None, 2),
    ],
)
def test_builtins_print_one_valid_envelope(
    commands: list[Command],
    capsys: pytest.CaptureFixture[str],
    envelope_validator: Draft202012Validator,
    argv: list[str],
    schema: str | None,
    code: int,
) -> None:
    for registry in (commands, []):  # also with zero commands
        exit_code, out, err = _run(argv, registry, capsys)
        assert err == ""
        doc = _one_envelope(out)
        envelope_validator.validate(doc)
        assert doc["command"] is None
        assert exit_code == doc["exit_code"] == code
        if schema is None:
            assert doc["result"] is None
        else:
            Draft202012Validator(schemas.result_schema(schema)).validate(doc["result"])


def test_the_loop_runs_with_zero_commands(
    capsys: pytest.CaptureFixture[str], envelope_validator: Draft202012Validator
) -> None:
    assert _check_command_envelopes([], capsys, envelope_validator) == []
    assert _registered([]) == []


def test_failing_commands_still_print_one_valid_envelope(
    dummy: Command,
    capsys: pytest.CaptureFixture[str],
    envelope_validator: Draft202012Validator,
) -> None:
    for code in exit_codes_of(dummy):
        if code in ALWAYS:
            continue
        argv = ["dummy", "--fail", f"{code.error_class}.test-dummy"]
        for args in (["--json", *argv], [*argv, "--json"]):
            exit_code, out, _ = _run(args, [dummy], capsys)
            doc = _one_envelope(out)
            envelope_validator.validate(doc)
            assert exit_code == doc["exit_code"] == int(code)


def test_json_output_has_no_esc_even_with_force_color(
    run_cli: Callable[..., subprocess.CompletedProcess[bytes]], clean_env: CleanEnv
) -> None:
    env = clean_env(FORCE_COLOR="1", COLORTERM="truecolor")
    for argv in (
        ["--json", "dummy", "--box"],
        ["dummy", "--json", "--fail", "model.test-dummy"],
        ["--json", "--version"],
        ["--json", "nope"],
    ):
        proc = run_cli(argv, env=env)
        assert b"\x1b" not in proc.stdout + proc.stderr, argv
        json.loads(proc.stdout)


@pytest.mark.parametrize("before", [True, False])
def test_the_real_registry_in_a_subprocess(
    clean_env: CleanEnv, before: bool, envelope_validator: Draft202012Validator
) -> None:
    """``python -m mmt_plugin``: the shipped registry, not the test's."""
    for name, argv in _cases(list(COMMANDS)):
        args = ["--json", *argv] if before else [*argv, "--json"]
        proc = subprocess.run(
            [sys.executable, "-m", "mmt_plugin", *args],
            capture_output=True,
            env=clean_env(FORCE_COLOR="1"),
            check=False,
        )
        assert proc.returncode == 0, proc.stderr
        assert proc.stderr == b""
        doc = _one_envelope(proc.stdout.decode("ascii"))
        envelope_validator.validate(doc)
        Draft202012Validator(schemas.result_schema(name)).validate(doc["result"])


# --- exit codes in --help ----------------------------------------------------


def _help(argv: list[str], commands: Sequence[Command], capsys: pytest.CaptureFixture[str]) -> str:
    with pytest.raises(SystemExit) as exc:
        main(argv, commands=commands)
    assert exc.value.code == 0
    return capsys.readouterr().out


def _listed_codes(help_text: str) -> list[int]:
    _, sep, tail = help_text.partition("\nexit codes:\n")
    assert sep, "no exit codes section"
    codes = []
    for line in tail.splitlines():
        if not line.startswith("  "):
            break
        codes.append(int(line.split()[0]))
    return codes


def test_each_command_help_lists_exactly_its_exit_codes(
    commands: list[Command], capsys: pytest.CaptureFixture[str]
) -> None:
    for command in commands:
        out = _help([command.name, "--help"], commands, capsys)
        expected = exit_codes_of(command)
        assert _listed_codes(out) == [int(c) for c in expected], command.name
        for code in expected:
            assert f"\n  {int(code):<4} {code.meaning}\n" in out


def test_every_command_can_return_the_universal_codes(commands: list[Command]) -> None:
    for command in commands:
        assert set(ALWAYS) <= set(exit_codes_of(command))
    completion = next(c for c in commands if c.name == "completion")
    assert exit_codes_of(completion) == ALWAYS  # completion adds none
    dummy = commands[-1]
    assert exit_codes_of(dummy) == tuple(ExitCode)


def test_root_help_lists_every_exit_code(
    commands: list[Command], capsys: pytest.CaptureFixture[str]
) -> None:
    assert _listed_codes(_help(["--help"], commands, capsys)) == [int(c) for c in ExitCode]
