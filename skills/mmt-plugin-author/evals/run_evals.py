"""Scripted evals of the mmt-plugin-author skill (plan task T4.2, #27).

No language model and no network: each case in ``cases/<id>/`` plays the
agent's part with fixed drafts, and this runner plays the skill's. It runs the
entry and loop commands of ``SKILL.md`` exactly as that file writes them (the
fenced blocks after ``<!-- eval:entry ... -->`` and ``<!-- eval:loop ... -->``),
with their ``<placeholders>`` filled in, and checks every envelope against
``references/contract.md``.

A case is ``case.json`` and the files it names:

- ``entry``: ``spec``, ``pcap`` or ``pdl``, the entry block of ``SKILL.md``;
  ``params``: its placeholders (``label``, ``id``, ``selector``, ``pcap``,
  ``pdl``), where ``{case}`` is the case directory; ``input``: what the agent
  starts from (a spec, notes, a PDL model).
- ``runs``: one per loop run, at most ``MAX_RUNS``. Each has ``edits``, made
  in the project before the loop runs (``write``/``append`` a case file,
  ``copy`` a project file, ``remove``, ``replace`` a string or ``regex`` a
  pattern in files that a glob names, relative to the project), and
  ``expect``: ``stop``, the loop command that does not exit 0 (``null``: the
  run is green), with its ``exit_code``, ``error_code`` and, for
  ``test.packet-failed``, the failing attributes of each packet
  (``failures``). The last run is green.

What fails a case (each is one line of ``CaseResult.problems``):

- an envelope that breaks the contract (``check_envelope``): stdout not
  exactly one JSON document, a non-empty stderr, ``schema_version`` not 1,
  ``ok``/``exit_code``/``error`` that disagree with each other or with the
  process, an exit code or class not in the contract's exit table, an
  ``error.code`` or ``diagnostics[].code`` the contract does not document, a
  failure the skill fixes at a location (``LOCATED``) with no located error;
  and, without an SDK, an
  envelope whose ``context.sdk.prefix`` is set;
- a command that does not end within the time limit. Every command gets an
  open pipe with no data as stdin and runs in a new session (no controlling
  terminal), so a command that reads stdin or prompts waits until the limit;
- a loop run that does not stop where the case expects;
- a fix that does not touch what the envelope pointed at: each located error
  of a failed run must be in a file the next run's edits change, at its line
  when it has one; a ``test.packet-failed`` is also fixed by a change to a
  ``plugin.yaml`` line that names a failing attribute;
- a packet test the case or the entry commands wrote that is deleted, or
  whose bytes, protocol or expected attributes change, other than an
  attribute renamed or dropped in the test and in ``plugin.yaml`` alike
  (``_test_rewrites``); only ``init``'s placeholder
  ``tests/<label>-basic.yaml`` may go;
- a final run that is not green: with an SDK, every loop command exits 0,
  ``validate``'s ``parents-exist`` is ``pass`` and ``test`` passes at least
  one packet, every protected test among them, with no ``test.no-packets``;
  without one, ``validate`` and ``generate`` exit 0, and the run's model
  pins ``sdk.profile``, declares a parent and every attribute its tests
  expect, under the label and id the tests expect.

Run it from a checkout (``uv run`` puts ``mmt_plugin`` on the path)::

    uv run python skills/mmt-plugin-author/evals/run_evals.py
    uv run python skills/mmt-plugin-author/evals/run_evals.py --sdk <prefix> --cc gcc

It prints one ``PASS:``/``FAIL:`` line per case (and one line per problem)
and exits 1 when a case fails. ``tests/unit/skill/`` runs it under pytest.
Stdlib only.
"""

from __future__ import annotations

import argparse
import contextlib
import difflib
import json
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

__all__ = [
    "CASES_DIR",
    "CONTRACT_MD",
    "LOOP_COMMANDS",
    "MAX_RUNS",
    "SKILL_MD",
    "CaseResult",
    "Contract",
    "EvalError",
    "Step",
    "case_dirs",
    "check_envelope",
    "command_of",
    "load_case",
    "load_contract",
    "main",
    "run_case",
    "run_cli",
    "skill_blocks",
]

SKILL_DIR = Path(__file__).resolve().parent.parent
SKILL_MD = SKILL_DIR / "SKILL.md"
CONTRACT_MD = SKILL_DIR / "references" / "contract.md"
CASES_DIR = SKILL_DIR / "evals" / "cases"

#: The loop of ``SKILL.md`` with an SDK, in order; without one, the first two.
LOOP_COMMANDS = ("validate", "generate", "build", "test")
#: The skill's cap on loop runs (``SKILL.md``, Rules).
MAX_RUNS = 10
#: Seconds a command may take; a command that waits for input reaches it.
DEFAULT_TIMEOUT = 600.0
#: The environment the runner removes, so that only the command line picks
#: the SDK, the profile, the compiler and the plugin directory.
SCRUBBED_ENV = (
    "MMT_BASE",
    "MMT_PLUGIN_SDK_PROFILE",
    "MMT_DPI_PLUGINS_DIR",
    "MMT_PLUGIN_PREFIX",
    "PKG_CONFIG_PATH",
    "PKG_CONFIG_LIBDIR",
    "CC",
    "FORCE_COLOR",
)
#: The failures whose fix the skill puts at a location (contract.md), so
#: whose envelope must locate an error; others (``model.unreadable``,
#: ``test.load-failed``) may have none.
LOCATED = (
    "model.schema",
    "model.yaml-syntax",
    "model.syntax.",
    "model.duplicate-name",
    "build.compile-failed",
    "build.missing-hook",
    "test.packet-failed",
)
EDIT_KINDS = ("write", "append", "copy", "remove", "replace", "regex")
SEVERITIES = ("error", "warning", "note")
_MARKER = re.compile(r"^<!-- eval:(entry|loop) ([a-z-]+) -->$")
_PLACEHOLDER = re.compile(r"<([a-z]+)>")
_ROW = re.compile(r"^\|(.*)\|\s*$")
_TEST_NAME = re.compile(r'^\s*- name: "?([A-Za-z_][A-Za-z0-9_]*)"?\s*$')
_TEST_VALUE = re.compile(r"^\s*value: (.*?)\s*$")
# The end of a ``plugin.yaml`` line: an optional comment, then spaces.
_EOL = r"(?:[ \t]+#[^\n]*)?[ \t]*$"
_LABEL = re.compile(rf"^  label: ([\"']?)([a-z][a-z0-9_]*)\1{_EOL}", re.M)
_ID = re.compile(rf"^  id: (\d+){_EOL}", re.M)
_PARENTS = re.compile(rf"^parents:{_EOL}\n", re.M)


class EvalError(Exception):
    """A case, ``SKILL.md`` or ``contract.md`` that the runner cannot use:
    a broken eval, not a contract failure."""


# --------------------------------------------------------------------------
# What the skill says: its command blocks and its contract tables.


def skill_blocks(text: str) -> dict[str, list[list[str]]]:
    """The command blocks of ``SKILL.md``, by marker (``"loop sdk"``,
    ``"entry pcap"``): each line of the fenced block after the marker, split
    like a shell would, without its leading ``mmt-plugin``."""
    blocks: dict[str, list[list[str]]] = {}
    lines = text.splitlines()
    for i, line in enumerate(lines):
        m = _MARKER.match(line.strip())
        if not m:
            continue
        key = f"{m.group(1)} {m.group(2)}"
        if key in blocks:
            raise EvalError(f"SKILL.md: two blocks marked {key!r}")
        if i + 1 >= len(lines) or not lines[i + 1].startswith("```"):
            raise EvalError(f"SKILL.md: the marker {key!r} is not followed by a fenced block")
        commands: list[list[str]] = []
        for body in lines[i + 2 :]:
            if body.startswith("```"):
                break
            if not body.strip():
                continue
            argv = shlex.split(body)
            if argv[0] != "mmt-plugin":
                raise EvalError(f"SKILL.md, block {key!r}: {body!r} is not an mmt-plugin command")
            commands.append(argv[1:])
        else:
            raise EvalError(f"SKILL.md: the block {key!r} is not closed")
        if not commands:
            raise EvalError(f"SKILL.md: the block {key!r} is empty")
        blocks[key] = commands
    return blocks


def _table(text: str, heading: str) -> list[list[str]]:
    """The body rows of the first table under ``## <heading>``, as cells."""
    rows: list[list[str]] = []
    inside = False
    for line in text.splitlines():
        if line.startswith("## "):
            if inside:
                break
            inside = line[3:].strip() == heading
            continue
        if not inside:
            continue
        m = _ROW.match(line.strip())
        if m:
            rows.append([c.strip() for c in m.group(1).split("|")])
        elif rows:
            break
    if len(rows) < 3:
        raise EvalError(f"no table under '## {heading}'")
    return rows[2:]  # the header and the |---| line


@dataclass(frozen=True)
class Contract:
    """The tables of ``contract.md``: the class of each exit code, and the
    documented codes (exact, or a family ending in ``*``)."""

    classes: Mapping[int, str]
    codes: tuple[str, ...]

    def documents(self, code: str) -> bool:
        return any(code.startswith(c[:-1]) if c.endswith("*") else code == c for c in self.codes)


def load_contract(text: str) -> Contract:
    classes: dict[int, str] = {}
    for cells in _table(text, "Exit codes"):
        classes[int(cells[0])] = cells[1]
    codes = []
    for cells in _table(text, "Error codes"):
        code = cells[0].strip("`")
        if not code:
            raise EvalError(f"contract.md: an error code row has no code: {cells}")
        codes.append(code)
    return Contract(classes, tuple(codes))


def command_of(args: Sequence[str]) -> str | None:
    """The command name in an argv without the program: the first word that
    is neither an option nor ``-C``'s value."""
    skip = False
    for arg in args:
        if skip:
            skip = False
        elif arg in ("-C", "--project"):
            skip = True
        elif not arg.startswith("-"):
            return arg
    return None


# --------------------------------------------------------------------------
# Running one command.


@dataclass
class Step:
    """One command: where it ran (``run`` 0 for the entry, else the loop run),
    what it returned and what broke the contract."""

    run: int
    args: list[str]
    command: str | None
    returncode: int | None
    stdout: str
    stderr: str
    envelope: dict[str, Any] | None
    problems: list[str] = field(default_factory=list)


def run_cli(
    argv: Sequence[str],
    *,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> tuple[int | None, str, str, list[str]]:
    """Run ``argv`` with no input and no terminal: stdin is a pipe that stays
    open and gets no data, and the process starts a new session. A process
    that reads stdin, or waits for an answer, blocks until ``timeout``; it is
    then killed (its whole process group) and reported. Returns the exit code
    (``None`` when killed), stdout, stderr and the problems."""
    read_end, write_end = os.pipe()
    try:
        proc = subprocess.Popen(
            list(argv),
            stdin=read_end,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=cwd,
            env=dict(env) if env is not None else None,
            start_new_session=True,
        )
    finally:
        os.close(read_end)
    try:
        out, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(proc.pid, signal.SIGKILL)
        out, err = proc.communicate()
        return (
            None,
            out.decode("utf-8", "replace"),
            err.decode("utf-8", "replace"),
            [
                f"did not end within {timeout:g} s: it waited for input (stdin is an open "
                "pipe with no data, and there is no terminal) or hung"
            ],
        )
    finally:
        os.close(write_end)
    return proc.returncode, out.decode("utf-8", "replace"), err.decode("utf-8", "replace"), []


def check_envelope(
    stdout: str,
    stderr: str,
    returncode: int | None,
    command: str | None,
    contract: Contract,
    *,
    sdk: bool = True,
) -> tuple[dict[str, Any] | None, list[str]]:
    """Check one command's output against the contract; return the envelope
    (``None`` when stdout is not one) and the problems."""
    problems: list[str] = []
    if stderr:
        problems.append(f"stderr is not empty with --json: {stderr[:200]!r}")
    if not stdout.endswith("\n"):
        problems.append("stdout does not end with a newline")
    try:
        env = json.loads(stdout)
    except ValueError as exc:
        return None, [*problems, f"stdout is not one JSON document ({exc}): {stdout[:200]!r}"]
    if not isinstance(env, dict):
        return None, [*problems, "the envelope is not a JSON object"]
    if env.get("schema_version") != 1:
        problems.append(f"schema_version is {env.get('schema_version')!r}, not 1")
    tool = env.get("tool")
    if not isinstance(tool, dict) or tool.get("name") != "mmt-plugin":
        problems.append(f"tool is {tool!r}, not mmt-plugin's")
    if env.get("command") != command:
        problems.append(f"command is {env.get('command')!r}, not {command!r}")
    exit_code = env.get("exit_code")
    if exit_code != returncode:
        problems.append(f"exit_code is {exit_code!r} but the process exited {returncode!r}")
    if env.get("ok") is not (exit_code == 0):
        problems.append(f"ok is {env.get('ok')!r} with exit_code {exit_code!r}")
    cls = contract.classes.get(exit_code) if isinstance(exit_code, int) else None
    if cls is None:
        problems.append(f"exit code {exit_code!r} is not in the contract's exit table")
    error = env.get("error")
    if exit_code == 0:
        if error is not None:
            problems.append("error is not null on success")
    elif not isinstance(error, dict):
        problems.append(f"error is {error!r} on exit {exit_code!r}")
    else:
        code = error.get("code")
        if error.get("class") != cls:
            problems.append(f"error.class is {error.get('class')!r}, the exit table says {cls!r}")
        if not isinstance(code, str) or not (code == cls or code.startswith(f"{cls}.")):
            problems.append(f"error.code {code!r} is not of the class {cls!r}")
        elif not contract.documents(code):
            problems.append(f"error.code {code!r} has no row in contract.md")
    diagnostics = env.get("diagnostics")
    if not isinstance(diagnostics, list):
        problems.append("diagnostics is not a list")
        diagnostics = []
    located = False
    for i, diag in enumerate(diagnostics):
        if not isinstance(diag, dict):
            problems.append(f"diagnostics[{i}] is not an object")
            continue
        code = diag.get("code")
        if diag.get("severity") not in SEVERITIES:
            problems.append(f"diagnostics[{i}].severity is {diag.get('severity')!r}")
        if not isinstance(code, str) or not contract.documents(code):
            problems.append(f"diagnostics[{i}].code {code!r} has no row in contract.md")
        loc = diag.get("location")
        if loc is None:
            continue
        if not isinstance(loc, dict) or not isinstance(loc.get("file"), str):
            problems.append(f"diagnostics[{i}].location is {loc!r}")
            continue
        line = loc.get("line")
        if line is not None and (not isinstance(line, int) or line < 1):
            problems.append(f"diagnostics[{i}].location.line is {line!r}")
        if diag.get("severity") == "error":
            located = True
    code = error.get("code") if isinstance(error, dict) else None
    if isinstance(code, str) and code.startswith(LOCATED) and not located:
        problems.append(f"a {code} failure with no located error in diagnostics")
    if exit_code == 0 and not isinstance(env.get("result"), dict):
        problems.append("result is not an object on success")
    context = env.get("context")
    if not sdk and isinstance(context, dict) and isinstance(context.get("sdk"), dict):
        prefix = context["sdk"].get("prefix")
        if prefix is not None:
            problems.append(f"the run has no SDK, but the command used {prefix!r}")
    return env, problems


# --------------------------------------------------------------------------
# Cases.


def case_dirs(root: Path = CASES_DIR) -> list[Path]:
    """Every case directory (one holding ``case.json``), by name."""
    return sorted(p.parent for p in root.glob("*/case.json"))


def _relative(path: str, what: str) -> str:
    pure = PurePosixPath(path)
    if not path or pure.is_absolute() or ".." in pure.parts:
        raise EvalError(f"{what}: {path!r} is not a path inside the project")
    return path


def load_case(case_dir: Path) -> dict[str, Any]:
    """Read and check ``case.json`` (``EvalError`` when it is not usable)."""
    where = f"{case_dir.name}/case.json"
    try:
        case: dict[str, Any] = json.loads((case_dir / "case.json").read_text("utf-8"))
    except (OSError, ValueError) as exc:
        raise EvalError(f"{where}: {exc}") from None
    for key, kind in (("id", str), ("entry", str), ("input", str), ("params", dict)):
        if not isinstance(case.get(key), kind):
            raise EvalError(f"{where}: {key!r} must be a {kind.__name__}")
    if case["id"] != case_dir.name:
        raise EvalError(f"{where}: id {case['id']!r} is not the directory's name")
    if not (case_dir / case["input"]).is_file():
        raise EvalError(f"{where}: no input file {case['input']!r}")
    for key in ("label", "id", "selector"):
        if not isinstance(case["params"].get(key), str):
            raise EvalError(f"{where}: params.{key} must be a string")
    runs = case.get("runs")
    if not isinstance(runs, list) or not 1 <= len(runs) <= MAX_RUNS:
        raise EvalError(f"{where}: 'runs' must list 1 to {MAX_RUNS} loop runs")
    for n, run in enumerate(runs, 1):
        edits, expect = run.get("edits"), run.get("expect")
        if not isinstance(edits, list) or not isinstance(expect, dict):
            raise EvalError(f"{where}: run {n} needs 'edits' (a list) and 'expect'")
        for edit in edits:
            kinds = [k for k in EDIT_KINDS if k in edit]
            if len(kinds) != 1:
                raise EvalError(f"{where}: run {n}: an edit needs one of {EDIT_KINDS}: {edit}")
            _relative(edit[kinds[0]], f"{where}: run {n}")
            if kinds[0] in ("write", "append") and not (case_dir / edit["from"]).is_file():
                raise EvalError(f"{where}: run {n}: no case file {edit['from']!r}")
        stop = expect.get("stop")
        if stop is not None and stop not in LOOP_COMMANDS:
            raise EvalError(f"{where}: run {n}: stop {stop!r} is not a loop command")
        if stop is not None and not (
            isinstance(expect.get("exit_code"), int) and isinstance(expect.get("error_code"), str)
        ):
            raise EvalError(f"{where}: run {n}: a stop needs exit_code and error_code")
    if runs[-1]["expect"].get("stop") is not None:
        raise EvalError(f"{where}: the last run must be green (stop null)")
    return case


def _files(project: Path, pattern: str) -> list[Path]:
    found = sorted(p for p in project.glob(pattern) if p.is_file())
    if not found:
        raise EvalError(f"no project file matches {pattern!r}")
    return found


def apply_edits(edits: Iterable[Mapping[str, Any]], case_dir: Path, project: Path) -> None:
    """Make a run's edits in the project, in order (``EvalError`` when one
    does not apply: a broken case)."""
    for edit in edits:
        if "write" in edit or "append" in edit:
            target = project / edit.get("write", edit.get("append", ""))
            text = (case_dir / edit["from"]).read_text("utf-8")
            if "append" in edit:
                text = target.read_text("utf-8") + text
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, "utf-8")
        elif "copy" in edit:
            source = project / _relative(edit["source"], "copy")
            shutil.copyfile(source, project / edit["copy"])
        elif "remove" in edit:
            for path in _files(project, edit["remove"]):
                path.unlink()
        elif "replace" in edit:
            for path in _files(project, edit["replace"]):
                text = path.read_text("utf-8")
                if edit["old"] not in text:
                    raise EvalError(f"replace: {edit['old']!r} is not in {path.name}")
                path.write_text(text.replace(edit["old"], edit["new"]), "utf-8")
        else:
            for path in _files(project, edit["regex"]):
                text, count = re.subn(
                    edit["pattern"], edit["new"], path.read_text("utf-8"), flags=re.M
                )
                if not count:
                    raise EvalError(f"regex: {edit['pattern']!r} matches nothing in {path.name}")
                path.write_text(text, "utf-8")


def _snapshot(project: Path) -> dict[str, str]:
    """The project's text files, by path, outside what the tool writes."""
    out: dict[str, str] = {}
    for path in sorted(project.rglob("*")):
        rel = path.relative_to(project).as_posix()
        if not path.is_file() or rel.split("/")[0] in ("build", "generated"):
            continue
        try:
            out[rel] = path.read_text("utf-8")
        except (OSError, UnicodeDecodeError):
            continue
    return out


def _changed(before: str | None, after: str | None) -> tuple[set[int], list[str]]:
    """The lines of ``before`` that an edit changed or removed, an insertion
    counting for the lines around it, and the text of every changed line on
    both sides."""
    old = (before or "").splitlines()
    new = (after or "").splitlines()
    lines: set[int] = set()
    texts: list[str] = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(
        None, old, new, autojunk=False
    ).get_opcodes():
        if tag == "equal":
            continue
        lines.update(range(i1 + 1, i2 + 1) if i2 > i1 else (i1, i1 + 1))
        texts += old[i1:i2] + new[j1:j2]
    return lines, texts


def _fix_problems(
    failure: Step, before: Mapping[str, str], after: Mapping[str, str], run: int
) -> list[str]:
    """Whether run ``run``'s edits touch every located error of ``failure``."""
    env = failure.envelope or {}
    failing: dict[str, set[str]] = {}
    result = env.get("result")
    if isinstance(result, dict):
        for packet in result.get("packets") or []:
            names = {f["attribute"] for f in packet.get("failures") or []}
            failing.setdefault(packet.get("file", ""), set()).update(names)
    _, model_texts = _changed(before.get("plugin.yaml"), after.get("plugin.yaml"))
    problems = []
    for diag in env.get("diagnostics") or []:
        loc = diag.get("location")
        if diag.get("severity") != "error" or not loc:
            continue
        file, line = loc["file"], loc.get("line")
        if file.startswith("generated/"):
            # Generated code comes from the model: the fix is in plugin.yaml.
            file, line = "plugin.yaml", None
        lines, _ = _changed(before.get(file), after.get(file))
        touched = before.get(file) != after.get(file) and (line is None or line in lines)
        if diag["code"] == "test.packet-failed" and not touched:
            names = failing.get(file, set())
            touched = any(
                re.search(rf"\b{re.escape(name)}\b", text)
                for name in names
                for text in model_texts
            )
        if not touched:
            where = f"{file}:{line}" if line else file
            problems.append(f"run {run}: the edits do not touch {where} ({diag['code']})")
    return problems


def _test_values(text: str) -> tuple[list[str], list[str]]:
    """The attribute names and the expected values of a packet test."""
    names, values = [], []
    for line in text.splitlines():
        if m := _TEST_NAME.match(line):
            names.append(m.group(1))
        elif m := _TEST_VALUE.match(line):
            values.append(m.group(1))
    return names, values


_INFORMATIONAL = re.compile(r"^\s*(-\s+)?(summary|source|bytes_source):")


def _parse_test(text: str) -> tuple[list[str], list[dict[str, str]]]:
    """A packet test as its checked lines outside ``expect.attributes`` (the
    bytes, the protocol, the id, the next protocol, ...) and its expected
    attributes, each a mapping of its keys to their text; comments and the
    informational keys (``summary``, ``source``, ``bytes_source``) left out."""
    header: list[str] = []
    attrs: list[dict[str, str]] = []
    inside = False
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#") or _INFORMATIONAL.match(line):
            continue
        if line == "  attributes:":
            inside = True
            continue
        if inside and line.startswith("    - "):
            attrs.append({})
            line = "      " + line[6:]
        if inside and line.startswith("      ") and attrs:
            key, _, value = line.strip().partition(":")
            attrs[-1][key] = value.strip()
            continue
        inside = False
        header.append(line.rstrip())
    return header, attrs


def _test_rewrites(before: str, after: str, model_names: set[str]) -> list[str]:
    """How an edit of a protected packet test changed what it checks. Allowed:
    an attribute dropped from the test whose name the model no longer has,
    and a rename (every key but ``name`` the same, the old name gone from the
    model, the new one in it). Anything else is a rewrite."""
    old_header, old_attrs = _parse_test(before)
    new_header, new_attrs = _parse_test(after)
    problems = []
    if old_header != new_header:
        problems.append("changes the bytes or the expected protocol")

    def rest(attr: Mapping[str, str]) -> dict[str, str]:
        return {k: v for k, v in attr.items() if k != "name"}

    def name(attr: Mapping[str, str]) -> str:
        return attr.get("name", "?").strip('"')

    def dropped(attrs: Sequence[Mapping[str, str]]) -> None:
        problems.extend(
            f"drops {name(a)} but plugin.yaml keeps it" for a in attrs if name(a) in model_names
        )

    def same(old: Mapping[str, str], new: Mapping[str, str]) -> bool:
        renamed = name(old) not in model_names and name(new) in model_names
        return rest(old) == rest(new) and (name(old) == name(new) or renamed)

    i = 0
    for new in new_attrs:
        j = next((j for j in range(i, len(old_attrs)) if same(old_attrs[j], new)), None)
        if j is None:
            problems.append(f"changes the expected values of {name(new)}")
            if i < len(old_attrs) and name(old_attrs[i]) == name(new):
                i += 1
            continue
        dropped(old_attrs[i:j])
        i = j + 1
    dropped(old_attrs[i:])
    return problems


def _hook_parents(model: str) -> list[str]:
    """The parents of a ``plugin.yaml`` without ``classify``: those that
    ``<label>_hook_register_parents`` must attach."""
    block = re.search(_PARENTS.pattern + r"((?:  .*\n|\s*\n)*)", model, re.M)
    if not block:
        return []
    entries = re.split(r"^  - ", block.group(1), flags=re.M)[1:]
    out = []
    for entry in entries:
        m = re.match(r"protocol: \"?([A-Za-z0-9_]+)", entry)
        if m and not re.search(r"^    classify:", entry, re.M):
            out.append(m.group(1))
    return out


def _strip_c_comments(code: str) -> str:
    return re.sub(r"//[^\n]*", "", re.sub(r"/\*.*?\*/", "", code, flags=re.S))


def _model_names(text: str) -> set[str]:
    return set(re.findall(r"\bname: ([A-Za-z_][A-Za-z0-9_]*)", text))


@dataclass
class CaseResult:
    """One case in one mode: every step, the problems, and whether its last
    run was green."""

    case: str
    sdk: bool
    steps: list[Step] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    green: bool = False

    @property
    def ok(self) -> bool:
        return not self.problems and self.green


class _Runner:
    def __init__(
        self,
        case_dir: Path,
        *,
        cli: Sequence[str],
        work: Path,
        sdk: Path | None,
        cc: str,
        timeout: float,
    ) -> None:
        self.case_dir = case_dir
        self.case = load_case(case_dir)
        self.cli = list(cli)
        self.sdk = sdk
        self.timeout = timeout
        self.contract = load_contract(CONTRACT_MD.read_text("utf-8"))
        self.blocks = skill_blocks(SKILL_MD.read_text("utf-8"))
        self.work = work
        self.project = work / self.case["params"]["label"]
        home = work / ".home"
        home.mkdir(parents=True, exist_ok=True)
        self.env = {k: v for k, v in os.environ.items() if k not in SCRUBBED_ENV}
        self.env.update(HOME=str(home), XDG_DATA_HOME=str(home / "share"), NO_COLOR="1")
        self.values: dict[str, str] = {
            k: str(v).replace("{case}", str(case_dir)) for k, v in self.case["params"].items()
        }
        self.values.update(project=str(self.project), cc=cc)
        if sdk is not None:
            self.values["prefix"] = str(sdk)
        self.result = CaseResult(self.case["id"], sdk is not None)

    def fill(self, args: Sequence[str]) -> list[str]:
        def one(m: re.Match[str]) -> str:
            if m.group(1) not in self.values:
                raise EvalError(f"{self.case['id']}: no value for <{m.group(1)}>")
            return self.values[m.group(1)]

        return [_PLACEHOLDER.sub(one, a) for a in args]

    def execute(self, run: int, args: Sequence[str]) -> Step:
        args = self.fill(args)
        command = command_of(args)
        code, out, err, problems = run_cli(
            [*self.cli, *args], cwd=self.work, env=self.env, timeout=self.timeout
        )
        env, more = (
            (None, [])
            if code is None
            else check_envelope(out, err, code, command, self.contract, sdk=self.sdk is not None)
        )
        step = Step(run, args, command, code, out, err, env, problems + more)
        self.result.steps.append(step)
        where = "entry" if run == 0 else f"run {run}"
        self.result.problems += [f"{where}: {command}: {p}" for p in step.problems]
        return step

    def profile(self) -> str:
        step = self.execute(0, ["--json", "--version"])
        profiles = ((step.envelope or {}).get("result") or {}).get("sdk_profiles") or []
        if not profiles:
            raise EvalError("mmt-plugin --json --version lists no SDK profile")
        return str(profiles[-1])

    def run(self) -> CaseResult:
        self.values["profile"] = self.profile()
        entry = self.blocks.get(f"entry {self.case['entry']}")
        if entry is None:
            raise EvalError(
                f"{self.case['id']}: SKILL.md has no entry block {self.case['entry']!r}"
            )
        for args in entry:
            if self.execute(0, args).returncode != 0:
                self.result.problems.append("entry: a command failed")
                return self.result
        label = self.case["params"]["label"]
        basic = f"tests/{label}-basic.yaml"
        protected = {p for p in _snapshot(self.project) if p.startswith("tests/") and p != basic}
        loop = self.blocks["loop sdk" if self.sdk is not None else "loop no-sdk"]
        failure: Step | None = None
        steps: list[Step] = []
        for n, run in enumerate(self.case["runs"], 1):
            before = _snapshot(self.project)
            apply_edits(run["edits"], self.case_dir, self.project)
            after = _snapshot(self.project)
            protected |= {
                e["write"]
                for e in run["edits"]
                if "write" in e and e["write"].startswith("tests/")
            }
            self.check_tests(n, protected, before, after)
            if failure is not None:
                self.result.problems += _fix_problems(failure, before, after, n)
            steps, failure = [], None
            for args in loop:
                step = self.execute(n, args)
                steps.append(step)
                if step.returncode != 0:
                    failure = step
                    break
            self.check_stop(n, run["expect"], failure)
        self.check_green(steps, failure, protected)
        return self.result

    def check_tests(
        self, run: int, protected: set[str], before: Mapping[str, str], after: Mapping[str, str]
    ) -> None:
        model = after.get("plugin.yaml", "")
        for path in sorted(protected):
            if path in before and path not in after:
                self.result.problems.append(f"run {run}: deletes the packet test {path}")
            if path not in before or path not in after:
                continue
            self.result.problems += [
                f"run {run}: {p} in {path}"
                for p in _test_rewrites(before[path], after[path], _model_names(model))
            ]

    def check_stop(self, run: int, expect: Mapping[str, Any], failure: Step | None) -> None:
        want = expect.get("stop")
        if self.sdk is None and want in ("build", "test"):
            want = None  # the no-SDK loop ends after generate
        got = failure.command if failure else None
        if got != want:
            seen = (failure.envelope or {}).get("error") if failure else None
            self.result.problems.append(
                f"run {run}: the loop stops at {got or 'nothing (green)'}, the case expects "
                f"{want or 'green'} ({seen})"
            )
            return
        if failure is None or failure.envelope is None:
            return
        env = failure.envelope
        if env.get("exit_code") != expect["exit_code"]:
            self.result.problems.append(
                f"run {run}: {got} exits {env.get('exit_code')}, the case expects "
                f"{expect['exit_code']}"
            )
        code = (env.get("error") or {}).get("code")
        if code != expect["error_code"]:
            self.result.problems.append(
                f"run {run}: {got} fails with {code}, the case expects {expect['error_code']}"
            )
        if "failures" in expect:
            seen_failures = {
                p["id"]: sorted({f["attribute"] for f in p["failures"]})
                for p in (env.get("result") or {}).get("packets") or []
                if p.get("status") != "pass"
            }
            wanted = {k: sorted(v) for k, v in expect["failures"].items()}
            if seen_failures != wanted:
                self.result.problems.append(
                    f"run {run}: failing packets {seen_failures}, the case expects {wanted}"
                )

    def check_green(
        self, steps: Sequence[Step], failure: Step | None, protected: set[str]
    ) -> None:
        if failure is not None:
            return  # check_stop reported it
        model = (self.project / "plugin.yaml").read_text("utf-8")
        problems = self.result.problems
        if 'profile: "' not in model:
            problems.append("green: plugin.yaml pins no sdk.profile")
        if not re.search(_PARENTS.pattern + r"  - protocol: ", model, re.M):
            problems.append("green: plugin.yaml declares no parent")
        found = _LABEL.search(model)
        label = found.group(2) if found else None
        if label is None:
            problems.append("green: cannot read protocol.label from plugin.yaml")
        else:
            impl = self.project / "src" / f"{label}_impl.c"
            code = _strip_c_comments(impl.read_text("utf-8")) if impl.is_file() else ""
            for parent in _hook_parents(model):
                if f"PROTO_{parent.upper()}" not in code:
                    problems.append(
                        f"green: the parent {parent} has no classify, and "
                        f"src/{impl.name} does not attach the protocol to it"
                    )
        found = _ID.search(model)
        ident = found.group(1) if found else None
        if ident is None:
            problems.append("green: cannot read protocol.id from plugin.yaml")
        names = _model_names(model)
        for path in sorted(self.project.glob("tests/*.yaml")):
            text = path.read_text("utf-8")
            rel = f"tests/{path.name}"
            want_names, _ = _test_values(text)
            if missing := set(want_names) - names:
                problems.append(f"green: {rel} expects {sorted(missing)}, not in plugin.yaml")
            if label and f'protocol: "{label.upper()}"' not in text:
                problems.append(f"green: {rel} does not expect the protocol {label}")
            if ident and f"proto_id: {ident}\n" not in text:
                problems.append(f"green: {rel} does not expect the id {ident}")
        if self.sdk is None:
            return
        by_command = {s.command: s.envelope or {} for s in steps}
        checks = (by_command.get("validate", {}).get("result") or {}).get("checks") or []
        parents = [c.get("status") for c in checks if c.get("id") == "parents-exist"]
        if parents != ["pass"]:
            problems.append(f"green: validate's parents-exist is {parents}, not pass")
        test = by_command.get("test", {})
        summary = (test.get("result") or {}).get("summary") or {}
        if not (summary.get("total", 0) >= 1 and summary.get("passed") == summary.get("total")):
            problems.append(f"green: test passes {summary}, not every packet of at least one")
        if any(d.get("code") == "test.no-packets" for d in test.get("diagnostics") or []):
            problems.append("green: test found no packet test")
        passed = {
            p.get("file")
            for p in (test.get("result") or {}).get("packets") or []
            if p.get("status") == "pass"
        }
        for path in sorted(protected - passed):
            problems.append(f"green: the packet test {path} did not run and pass")
        self.result.green = not problems
        return

    def finish(self) -> None:
        if self.sdk is None and not self.result.problems:
            self.result.green = True


def run_case(
    case_dir: Path,
    *,
    work: Path,
    sdk: Path | None = None,
    cc: str = "gcc",
    cli: Sequence[str] | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> CaseResult:
    """Run one case in ``work`` (an empty directory): with ``sdk``, every loop
    command; without, ``validate`` and ``generate``."""
    runner = _Runner(
        case_dir,
        cli=cli or [sys.executable, "-m", "mmt_plugin"],
        work=work,
        sdk=sdk,
        cc=cc,
        timeout=timeout,
    )
    result = runner.run()
    runner.finish()
    return result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--sdk", type=Path, help="an mmt-dpi SDK prefix: run build and test too")
    parser.add_argument("--cc", default="gcc", help="the compiler for build and test (gcc)")
    parser.add_argument("--case", action="append", help="run only this case (repeatable)")
    parser.add_argument("--cli", help="the mmt-plugin command (default: python -m mmt_plugin)")
    parser.add_argument(
        "--workdir", type=Path, help="keep the projects here (default: a temp dir)"
    )
    parser.add_argument(
        "--timeout", type=float, default=DEFAULT_TIMEOUT, help="seconds per command"
    )
    args = parser.parse_args(argv)
    dirs = [d for d in case_dirs() if not args.case or d.name in args.case]
    if not dirs:
        parser.error("no case to run")
    cli = shlex.split(args.cli) if args.cli else None
    failed = 0
    with tempfile.TemporaryDirectory(prefix="mmt-plugin-evals-") as tmp:
        root = args.workdir or Path(tmp)
        for case_dir in dirs:
            work = root / case_dir.name
            work.mkdir(parents=True)
            sdk = args.sdk.resolve() if args.sdk else None
            try:
                result = run_case(
                    case_dir, work=work, sdk=sdk, cc=args.cc, cli=cli, timeout=args.timeout
                )
            except EvalError as exc:
                print(f"FAIL: {case_dir.name}: broken eval: {exc}")
                failed += 1
                continue
            mode = "with the SDK" if result.sdk else "without an SDK (validate, generate)"
            if result.ok:
                print(f"PASS: {result.case} {mode}, {len(result.steps)} commands")
            else:
                failed += 1
                print(f"FAIL: {result.case} {mode}")
                for problem in result.problems or ["the last run is not green"]:
                    print(f"  {problem}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
