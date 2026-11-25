"""``mmt-plugin-agent``: run the mmt-plugin-generator skill headless.

It calls only the public API of ``mmt_plugin_agent`` (its ``__all__``).
With ``--json`` it prints one envelope in the style of
``docs/design/cli.md``, sections 5 and 6: ``schema_version`` 1, ``ok``,
``exit_code``, ``error`` (``class``, ``code``, ``message``, ``hint``),
``diagnostics``, ``context`` and ``result``
(``mmt_plugin_agent/schemas/v1/``).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Any, NoReturn

from mmt_plugin.exitcodes import ExitCode
from mmt_plugin_agent import (
    AgentError,
    AgentEvent,
    AgentResult,
    PluginAgent,
    Question,
    __version__,
    extra_missing,
    run_model_evals,
)

__all__ = ["main"]

TOOL = "mmt-plugin-agent"

#: The exit code and error code of each status that is not a success.
_FAILED_STATUS = {
    "not_green": ("agent.not-green", "the loop is not green", "read REPORT.md and runs/"),
    "eval_failed": (
        "agent.eval-failed",
        "the plugin is green, but its evaluation on the capture failed",
        "read eval/report.md in the work folder",
    ),
    "blocked": (
        "agent.blocked",
        "the run stopped BLOCKED: a question has no safe default",
        "read REPORT.md and questions.md, answer, then run update on the project",
    ),
    "failed": (
        "agent.skills-modified",
        "the run changed the skills directory; it was restored and the run failed",
        "run in the agent container, where the skills are read-only",
    ),
    "waiting": (
        "agent.waiting",
        "the run is waiting for an answer",
        "run with --interactive on a terminal",
    ),
}


class _UsageError(Exception):
    pass


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        raise _UsageError(message)


def _envelope(
    command: str | None,
    *,
    error: AgentError | None = None,
    diagnostics: Sequence[dict[str, Any]] = (),
    context: dict[str, Any] | None = None,
    result: Any = None,
) -> dict[str, Any]:
    exit_code = ExitCode.SUCCESS if error is None else error.exit_code
    return {
        "schema_version": 1,
        "tool": {"name": TOOL, "version": __version__},
        "command": command,
        "ok": exit_code is ExitCode.SUCCESS,
        "exit_code": int(exit_code),
        "error": None if error is None else error.to_json(),
        "diagnostics": list(diagnostics),
        "context": context or {},
        "result": None if exit_code is ExitCode.USAGE else result,
    }


def _run_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--sdk", metavar="PREFIX", help="the mmt-dpi prefix (default: MMT_BASE)")
    parser.add_argument("--cc", help="the compiler, gcc or clang (default: CC, else gcc)")
    parser.add_argument(
        "--work", metavar="DIR", help="the work folder (default: a new one in this directory)"
    )
    parser.add_argument(
        "--model",
        metavar="PROVIDER:MODEL",
        help="the chat model (default: MMT_PLUGIN_AGENT_MODEL), e.g. anthropic:<model>",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--unattended",
        dest="mode",
        action="store_const",
        const="unattended",
        help="no user answers: questions go to questions.md (the default)",
    )
    mode.add_argument(
        "--interactive",
        dest="mode",
        action="store_const",
        const="interactive",
        help="ask each question on the terminal and wait for the answer",
    )
    parser.set_defaults(mode="unattended")
    parser.add_argument("--capture", metavar="FILE", help="a capture of the protocol")
    parser.add_argument(
        "--allow-synthetic",
        action="store_true",
        help="allow a synthetic capture when none is given or found",
    )
    parser.add_argument("--no-eval", action="store_true", help="skip the capture evaluation")
    parser.add_argument("--skills", metavar="DIR", help="the skills directory")
    parser.add_argument("--thread-id", metavar="ID", help="the run's thread id")
    parser.add_argument("--instructions", metavar="TEXT", help="more instructions for the request")


def _parser() -> argparse.ArgumentParser:
    common = _Parser(add_help=False)
    common.add_argument(
        "--json", action="store_true", default=argparse.SUPPRESS, help="print one JSON envelope"
    )
    parser = _Parser(
        prog=TOOL,
        description="Run the mmt-plugin-generator skill headless, with any LLM provider.",
        epilog=(
            "exit codes: 0 done, 2 usage, 3 input, 4 environment, 6 not green or failed, "
            "7 state, 130 interrupted"
        ),
        parents=[common],
    )
    parser.add_argument("--version", action="store_true", help="print the version and exit")
    sub = parser.add_subparsers(dest="command", parser_class=_Parser)
    new = sub.add_parser("new", parents=[common], help="write a new plugin")
    entry = new.add_mutually_exclusive_group(required=True)
    entry.add_argument("--spec", metavar="FILE", help="from a protocol specification")
    entry.add_argument("--pcap", metavar="FILE", help="from a capture")
    entry.add_argument("--pdl", metavar="FILE", help="from a legacy PDL v1 model")
    _run_options(new)
    update = sub.add_parser("update", parents=[common], help="update an existing project")
    update.add_argument("project", metavar="PROJECT", help="the project directory")
    update.add_argument(
        "--change", required=True, metavar="FILE|TEXT", help="the change: a file or its text"
    )
    _run_options(update)
    doctor = sub.add_parser("doctor", parents=[common], help="check what a run needs")
    doctor.add_argument("--sdk", metavar="PREFIX", help="the mmt-dpi prefix (default: MMT_BASE)")
    doctor.add_argument("--cc", help="the compiler (default: CC, else gcc)")
    doctor.add_argument("--skills", metavar="DIR", help="the skills directory")
    doctor.add_argument("--model", metavar="PROVIDER:MODEL", help="the chat model")
    evals = sub.add_parser("eval", parents=[common], help="run the skill's eval cases per model")
    evals.add_argument(
        "--model", action="append", required=True, metavar="PROVIDER:MODEL", help="repeatable"
    )
    evals.add_argument("--out", required=True, metavar="FILE", help="the results table (.md)")
    evals.add_argument("--case", action="append", default=[], help="only this case")
    evals.add_argument("--cases", metavar="DIR", help="the cases directory")
    evals.add_argument("--sdk", metavar="PREFIX", help="the mmt-dpi prefix (default: MMT_BASE)")
    evals.add_argument("--cc", default="gcc", help="the compiler (default: gcc)")
    evals.add_argument("--skills", metavar="DIR", help="the skills directory")
    evals.add_argument("--work", metavar="DIR", help="keep the cases' work folders here")
    return parser


def _progress(event: AgentEvent) -> None:
    if event.kind in ("command", "loop", "question") and sys.stderr.isatty():
        print(f"[{event.kind}] {event.message}", file=sys.stderr)


def _consume(events: Iterator[AgentEvent], json_out: bool) -> AgentResult:
    result = None
    for event in events:
        if not json_out:
            _progress(event)
        result = event.result or result
    if result is None:
        raise AgentError(ExitCode.INTERNAL, "agent.internal", "the run returned no result")
    return result


def _answer(question: Question) -> str:
    """Ask on the terminal: the question on stderr, the answer from stdin."""
    print(f"\n{question.text}\nRecommended: {question.recommended}", file=sys.stderr)
    print("> ", end="", file=sys.stderr, flush=True)
    line = sys.stdin.readline()
    if not line:
        raise AgentError(
            ExitCode.USAGE,
            "agent.no-answer",
            "stdin ended before the question was answered",
            "answer on a terminal, or run --unattended",
        )
    return line.strip() or question.recommended


def _agent(args: argparse.Namespace) -> PluginAgent:
    return PluginAgent(
        args.model,
        sdk=args.sdk,
        cc=args.cc,
        work_dir=args.work,
        mode=args.mode,
        capture=args.capture,
        allow_synthetic=args.allow_synthetic,
        no_eval=args.no_eval,
        skills_dir=args.skills,
    )


def _run(args: argparse.Namespace, json_out: bool) -> AgentResult:
    agent = _agent(args)
    if args.command == "new":
        events = agent.stream(
            spec=args.spec,
            pcap=args.pcap,
            pdl=args.pdl,
            instructions=args.instructions,
            thread_id=args.thread_id,
        )
    else:
        events = agent.stream(
            project=args.project,
            change=args.change,
            instructions=args.instructions,
            thread_id=args.thread_id,
        )
    result = _consume(events, json_out)
    while result.status == "waiting" and result.question is not None:
        try:
            answer = _answer(result.question)
        except BaseException:
            # No answer (stdin ended, Ctrl-C): the run will not be resumed.
            agent.release(result.thread_id)
            raise
        result = _consume(agent.stream_resume(result.thread_id, answer), json_out)
    return result


def _outcome(result: AgentResult) -> tuple[AgentError | None, list[dict[str, Any]]]:
    diagnostics: list[dict[str, Any]] = []
    if result.skipped_with_leave:
        flag = "--capture" if result.eval_leave == "capture" else "--allow-synthetic"
        return AgentError(
            ExitCode.TEST,
            "agent.evaluation-skipped",
            f"the plugin is green, but the model skipped the evaluation it had leave for ({flag})",
            "read REPORT.md and manifest.json, then run update on the project to evaluate it",
        ), diagnostics
    if result.status == "incomplete":
        diagnostics.append(
            {
                "severity": "warning",
                "code": "agent.evaluation-not-done",
                "message": "the plugin is green; its evaluation was not done",
                "hint": "give --capture or --allow-synthetic",
            }
        )
    if result.status not in _FAILED_STATUS:
        return None, diagnostics
    code, message, hint = _FAILED_STATUS[result.status]
    return AgentError(ExitCode.TEST, code, message, hint), diagnostics


def _human_result(result: AgentResult) -> None:
    print(f"{result.status}: {result.message or '(no final message)'}")
    print(f"work folder: {result.work}")
    if result.project is not None:
        print(f"project: {result.project}")
    if result.loop is not None:
        state = "green" if result.loop.green(result.with_sdk) else "not green"
        print(f"loop runs: {result.loop_runs}, the last one {state}")
    print(f"evaluation: {result.evaluation}")
    for item in result.unchecked:
        print(f"not checked: {item}")
    if result.questions_path is not None:
        print(f"questions: {result.questions_path}")
    for path in result.skills_modified:
        print(f"skills file changed and restored: {path}")


def _dispatch(args: argparse.Namespace, json_out: bool) -> dict[str, Any]:
    command = args.command
    if command == "doctor":
        report = PluginAgent(args.model, sdk=args.sdk, cc=args.cc, skills_dir=args.skills).doctor()
        if not json_out:
            for check in report.checks:
                print(f"{check.status.upper():4} {check.id}: {check.detail}")
                if check.hint:
                    print(f"     fix: {check.hint}")
        error = None
        if not report.ok:
            failed = ", ".join(c.id for c in report.checks if c.status == "fail")
            error = AgentError(
                ExitCode.SDK, "agent.doctor-failed", f"failed checks: {failed}", "see each hint"
            )
        return _envelope(command, error=error, result=report.to_json())
    if command == "eval":
        why = extra_missing()
        if why is not None:
            raise AgentError(
                ExitCode.SDK,
                "agent.needs-extra",
                f"mmt-plugin-agent needs Python 3.11+ and the agent extra ({why})",
                "install it with Python 3.11+: pip install 'mmt-plugin[agent]'",
            )
        evaluated = run_model_evals(
            args.model,
            out=args.out,
            sdk=args.sdk,
            cc=args.cc,
            cases=args.case,
            cases_dir=args.cases,
            skills_dir=args.skills,
            work_root=args.work,
        )
        if not json_out:
            print(evaluated.markdown(), end="")
            print(f"table: {Path(args.out).resolve()}")
        error = (
            None
            if evaluated.ok
            else AgentError(
                ExitCode.TEST, "agent.eval-cases-failed", "a case failed", f"read {args.out}"
            )
        )
        return _envelope(command, error=error, result=evaluated.to_json())
    result = _run(args, json_out)
    error, diagnostics = _outcome(result)
    if not json_out:
        _human_result(result)
    context = {"work": str(result.work), "thread_id": result.thread_id}
    return _envelope(
        command, error=error, diagnostics=diagnostics, context=context, result=result.to_json()
    )


def main(argv: Sequence[str] | None = None) -> int:
    args_list = list(sys.argv[1:] if argv is None else argv)
    json_out = "--json" in args_list
    parser = _parser()
    try:
        args = parser.parse_args(args_list)
    except _UsageError as exc:
        envelope = _envelope(
            None, error=AgentError(ExitCode.USAGE, "agent.usage", str(exc), f"{TOOL} --help")
        )
        return _emit(envelope, json_out)
    if args.version:
        version: dict[str, Any] = {
            "version": __version__,
            "python": sys.version.split()[0],
            "agent_extra": extra_missing() is None,
        }
        if not json_out:
            print(f"{TOOL} {__version__}")
        return _emit(_envelope("version", result=version), json_out, quiet=True)
    if args.command is None:
        if json_out:
            error = AgentError(ExitCode.USAGE, "agent.usage", "no command given", f"{TOOL} --help")
            return _emit(_envelope(None, error=error), json_out)
        parser.print_help(sys.stderr)
        return int(ExitCode.USAGE)
    try:
        envelope = _dispatch(args, json_out)
    except AgentError as exc:
        envelope = _envelope(args.command, error=exc)
    except KeyboardInterrupt:
        envelope = _envelope(
            args.command,
            error=AgentError(ExitCode.INTERRUPTED, "interrupted", "interrupted", None),
        )
    except Exception as exc:
        # The model's provider (a bad key, a rate limit, an endpoint down) or
        # an I/O error: still one envelope, its message without secrets.
        envelope = _envelope(args.command, error=AgentError.unexpected(exc))
    return _emit(envelope, json_out, quiet=True)


def _emit(envelope: dict[str, Any], json_out: bool, quiet: bool = False) -> int:
    if json_out:
        sys.stdout.write(json.dumps(envelope, ensure_ascii=True, indent=2) + "\n")
    elif envelope["error"] is not None and not (quiet and envelope["ok"]):
        error = envelope["error"]
        print(f"{TOOL}: error: {error['message']}", file=sys.stderr)
        if error.get("hint"):
            print(f"hint: {error['hint']}", file=sys.stderr)
    code: int = envelope["exit_code"]
    return code
