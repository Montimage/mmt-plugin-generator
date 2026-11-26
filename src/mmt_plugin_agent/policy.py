"""What the agent's shell and file tools may do (no deepagents needed).

The checks here are defence in depth, not a sandbox: a shell command can
always reach what the user running it can. The container is the sandbox
(``docs/agent-api.md``, "The sandbox").
"""

from __future__ import annotations

import ctypes
import os
import re
import shlex
import sys
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

__all__ = [
    "LOOP_COMMANDS",
    "CommandCheck",
    "check_command",
    "environ_failure",
    "evaluation_args",
    "hide_environ",
    "is_secret",
    "is_system_prefix",
    "is_within",
    "loop_subcommand",
    "mmt_plugin_command",
    "readable_ancestors",
    "realpath_of",
    "shell_env",
    "trusted_invocation",
]

#: The four loop commands of the skill (SKILL.md, Step 4), in order.
LOOP_COMMANDS = ("validate", "generate", "build", "test")

#: mmt-plugin's options that come before the command and take a value.
_GLOBAL_WITH_VALUE = frozenset({"-C", "--project"})

#: The variables the agent's shell inherits, by name or prefix (``*``).
_ENV_ALLOWED = (
    "PATH",
    "HOME",
    "USER",
    "LOGNAME",
    "SHELL",
    "TMPDIR",
    "LANG",
    "LC_*",
    "TERM",
    "CC",
    "DOCKER_HOST",
    "DOCKER_TLS_VERIFY",
    "DOCKER_CERT_PATH",
    "DOCKER_CONFIG",
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "NO_PROXY",
    "http_proxy",
    "https_proxy",
    "no_proxy",
    "SSL_CERT_FILE",
    "SSL_CERT_DIR",
    "REQUESTS_CA_BUNDLE",
    "PKG_CONFIG_*",
    # uv's own settings, not its index URLs (they can hold a password).
    "UV_CACHE_DIR",
    "UV_LOCKED",
    "UV_NO_CACHE",
    "UV_OFFLINE",
    "UV_PYTHON",
    "UV_TOOL_DIR",
    "UV_TOOL_BIN_DIR",
    "XDG_*",
    "MMT_*",
    "CYBERLAB_DIR",
)

#: Names never passed on, even when allowed above: the model's provider
#: keys and any other credential.
_ENV_SECRET = re.compile(r"_API_KEY$|_TOKEN$|SECRET|PASSWORD|CREDENTIAL", re.IGNORECASE)

#: The proxy variables: a URL whose user name alone can be a token.
_PROXIES = frozenset({"HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"})

#: One URL of a value (a list is separated by commas or white space).
_URL_ITEM = re.compile(r"[^,\s]+")

#: The system prefix the skill never uses (SKILL.md, Rule 3).
_SYSTEM_PREFIX = PurePosixPath("/opt/mmt")


def is_secret(name: str) -> bool:
    """Whether a variable named ``name`` holds a key or another credential."""
    return _ENV_SECRET.search(name) is not None


def _without_userinfo(item: str, proxy: bool) -> str:
    """``item`` without the ``user:password@`` of its URL: always for a
    proxy (also without a scheme, ``u:p@host:3128``) and an http(s) URL
    (a user name alone can be a token), else only when it has a password
    (``DOCKER_HOST=ssh://user@host`` stays)."""
    scheme, sep, rest = item.partition("://")
    if not sep:
        if not proxy:
            return item
        scheme, rest = "", item
    end = len(rest)
    for c in "/?#":
        found = rest.find(c)
        if found != -1:
            end = min(end, found)
    authority = rest[:end]
    if "@" not in authority:
        return item
    userinfo, host = authority.rsplit("@", 1)
    if not proxy and ":" not in userinfo and scheme.lower() not in ("http", "https"):
        return item
    return f"{scheme}{sep}{host}{rest[end:]}"


def shell_env(environ: Mapping[str, str]) -> dict[str, str]:
    """The environment of the agent's shell: the allowed names of
    ``environ``, without secrets (by name, and a URL's password, a
    proxy's user name too), and no byte-code files."""
    out = {}
    for name, value in environ.items():
        allowed = any(
            name.startswith(rule[:-1]) if rule.endswith("*") else name == rule
            for rule in _ENV_ALLOWED
        )
        if allowed and not is_secret(name):
            proxy = name in _PROXIES
            items = [
                (m.span(), _without_userinfo(m.group(0), proxy)) for m in _URL_ITEM.finditer(value)
            ]
            for (start, end), item in reversed(items):
                value = value[:start] + item + value[end:]
            out[name] = value
    out["PYTHONDONTWRITEBYTECODE"] = "1"
    return out


#: Whether this is Linux (a variable: mypy checks one platform's branch only).
_LINUX: bool = sys.platform.startswith("linux")

_PR_GET_DUMPABLE = 3
_PR_SET_DUMPABLE = 4

#: What ``hide_environ()`` found, once it ran: None (hidden) or why not.
_HIDDEN: dict[str, str | None] = {}


def _make_non_dumpable() -> str | None:
    if not _LINUX:
        return (
            f"not Linux ({sys.platform}): a process of the same user can read the "
            "agent's environment, its provider keys with it"
        )
    try:
        libc = ctypes.CDLL(None, use_errno=True)
        if libc.prctl(_PR_SET_DUMPABLE, 0, 0, 0, 0) != 0:
            return f"prctl(PR_SET_DUMPABLE, 0) failed: {os.strerror(ctypes.get_errno())}"
        if libc.prctl(_PR_GET_DUMPABLE, 0, 0, 0, 0) != 0:
            return "prctl(PR_SET_DUMPABLE, 0) did not make the process non-dumpable"
    except (OSError, AttributeError) as exc:
        return f"prctl is not available: {exc}"
    return None


def hide_environ() -> str | None:
    """Make this process non-dumpable (Linux ``prctl(PR_SET_DUMPABLE, 0)``),
    so that ``/proc/<pid>/environ`` is root's: the agent's shell, as the
    same user, cannot read the provider keys ``shell_env()`` keeps from it.
    A child is dumpable again after its ``exec``, but holds only
    ``shell_env()``. Done once; None when it worked, else why not (off
    Linux, always)."""
    if "result" not in _HIDDEN:
        _HIDDEN["result"] = _make_non_dumpable()
    return _HIDDEN["result"]


#: How many parents ``readable_ancestors()`` follows at most.
_MAX_ANCESTORS = 64


def _parent_of(proc: Path, pid: int) -> int | None:
    """The parent pid of ``pid`` from ``<proc>/<pid>/stat`` (its command
    name, in parentheses, may hold spaces and parentheses), or None."""
    try:
        stat = (proc / str(pid) / "stat").read_text("utf-8", errors="replace")
        return int(stat.rpartition(")")[2].split()[1])
    except (OSError, IndexError, ValueError):
        return None


def readable_ancestors(
    proc: Path = Path("/proc"), start: int | None = None
) -> list[tuple[int, str, list[str]]]:
    """Each ancestor of this process, from its parent (``start``, by
    default ``os.getppid()``) up to PID 1, whose ``<proc>/<pid>/environ``
    this user can read and holds a variable ``is_secret()`` names: its pid,
    its command name and those variables' names, never their values.
    ``hide_environ()`` hides only this process: a parent that holds the key
    (``uv run``, a wrapper script) stays readable by the agent's shell.
    Empty without ``/proc`` (off Linux)."""
    found: list[tuple[int, str, list[str]]] = []
    pid = os.getppid() if start is None else start
    seen: set[int] = set()
    while pid >= 1 and pid not in seen and len(seen) < _MAX_ANCESTORS:
        seen.add(pid)
        base = proc / str(pid)
        try:
            data = (base / "environ").read_bytes()
        except OSError:
            data = b""
        names = sorted(
            {
                name
                for item in data.split(b"\0")
                if (name := item.partition(b"=")[0].decode("utf-8", "replace")) and is_secret(name)
            }
        )
        if names:
            try:
                comm = (base / "comm").read_text("utf-8", errors="replace").strip()
            except OSError:
                comm = "?"
            found.append((pid, comm, names))
        if pid == 1:
            break
        parent = _parent_of(proc, pid)
        if parent is None:
            break
        pid = parent
    return found


def environ_failure() -> str | None:
    """Why ``hide_environ()`` failed on Linux, when it ran there and did;
    else None (it worked, did not run, or the host is not Linux)."""
    if not _LINUX:
        return None
    return _HIDDEN.get("result")


def is_within(path: Path, root: Path) -> bool:
    """Whether ``path`` is ``root`` or below it (both already resolved)."""
    return path == root or root in path.parents


@dataclass(frozen=True)
class CommandCheck:
    """The verdict on one shell command: ``refused`` is why it may not run;
    ``force`` is true when it passes ``--force`` (run only with leave)."""

    refused: str | None = None
    force: bool = False


def is_system_prefix(path: str | os.PathLike[str]) -> bool:
    """Whether ``path`` is ``/opt/mmt`` or below it, as given or once its
    links are resolved."""

    def under(p: PurePosixPath) -> bool:
        return p == _SYSTEM_PREFIX or _SYSTEM_PREFIX in p.parents

    # The path as given first: resolving it looks at the system prefix.
    return under(PurePosixPath(os.path.abspath(path))) or under(
        PurePosixPath(os.path.realpath(path))
    )


def _under_system_prefix(token: str) -> bool:
    for part in [token, *token.split("=")[1:]]:
        if not part.startswith("/"):
            continue
        path = PurePosixPath(os.path.normpath(part))
        if path == _SYSTEM_PREFIX or _SYSTEM_PREFIX in path.parents:
            return True
    return False


def _tokens(command: str) -> list[str]:
    lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    lexer.commenters = ""
    return list(lexer)


def check_command(command: str) -> CommandCheck:
    """Refuse ``sudo``, ``--system`` and a path under ``/opt/mmt``; flag
    ``--force``. A command that does not parse is refused: the agent can
    always write a simpler one."""
    try:
        tokens = _tokens(command)
    except ValueError as exc:
        return CommandCheck(refused=f"the command does not parse ({exc}): write it plainly")
    for token in tokens:
        if PurePosixPath(token).name == "sudo":
            return CommandCheck(refused="sudo is never used (SKILL.md, Rule 3)")
        if token == "--system" or token.startswith("--system="):
            return CommandCheck(refused="--system is never used (SKILL.md, Rule 3)")
        if _under_system_prefix(token):
            return CommandCheck(
                refused=f"{token} is under /opt/mmt, which is never used (SKILL.md, Rule 3)"
            )
    force = any(t == "--force" or t.startswith("--force=") for t in tokens)
    return CommandCheck(force=force)


def _segments(tokens: Iterable[str]) -> list[list[str]]:
    out: list[list[str]] = [[]]
    for token in tokens:
        if token and all(c in "|&;()<>" for c in token):
            out.append([])
        else:
            out[-1].append(token)
    return [s for s in out if s]


def mmt_plugin_command(command: str) -> tuple[str, str | None] | None:
    """The mmt-plugin command a shell command runs (``validate``, ...) and
    its ``-C`` project, or None when it runs no mmt-plugin command.

    The command name is the first argument that is not an option, so a
    parameterized one (``$c`` in a shell loop) is not a loop command, but
    its non-None return still means mmt-plugin was invoked with a
    subcommand."""
    try:
        tokens = _tokens(command)
    except ValueError:
        return None
    for segment in _segments(tokens):
        for i, token in enumerate(segment):
            name = PurePosixPath(token).name
            if name == "mmt-plugin" or (
                token == "mmt_plugin" and i >= 1 and segment[i - 1] == "-m"
            ):
                rest = segment[i + 1 :]
                break
        else:
            continue
        project = None
        j = 0
        while j < len(rest):
            arg = rest[j]
            if arg in _GLOBAL_WITH_VALUE and j + 1 < len(rest):
                project = rest[j + 1]
                j += 2
            elif arg.startswith("-"):
                j += 1
            else:
                return arg, project
        return None
    return None


"""One strict, directly executable invocation, as ``trusted_invocation``
parses it: ``kind`` is ``mmt-plugin`` or ``evaluation``, ``argv`` its
arguments (for ``evaluation``, the script path first), ``subcommand`` the
mmt-plugin subcommand, ``tee`` the tee target, ``timeout`` the ``timeout``
prefix's seconds."""

TrustedInvocation = tuple[str, list[str], str | None, str | None, int | None]

#: Shell punctuation and substitution characters a trusted invocation never
#: holds: they would make the shell, not the backend, decide what runs.
_UNSAFE = frozenset("$`\\*?[];|&<>(){}")


def _shell_tokens(command: str) -> list[str] | None:
    """The command's tokens, shell operators apart, or None when the shell
    itself could not parse it."""
    import shlex

    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        return list(lexer)
    except ValueError:
        return None


def trusted_invocation(command: str) -> TrustedInvocation | None:
    """The strict invocation a shell command is, or None when it is anything
    else.

    The strict form is exactly ``[timeout N] TOOL ARGS...``, optionally
    followed by ``| tee PATH`` — one simple command, no shell operators,
    substitutions, redirections or expansions, where TOOL is ``mmt-plugin``
    or the evaluation's ``pcap_eval.py`` (run directly or through
    ``python``/``python3``). Only this form is parsed exactly as the shell
    would run it, so the backend can execute it itself and trust what it
    captures; everything else the shell runs is untrusted evidence.
    """
    tokens = _shell_tokens(command)
    if not tokens:
        return None
    tee = None
    if len(tokens) >= 3 and tokens[-3:-1] == ["|", "tee"]:
        tee = tokens[-1]
        tokens = tokens[:-3]
    if any(set(token) & _UNSAFE for token in tokens) or (tee and set(tee) & _UNSAFE):
        return None
    timeout = None
    if len(tokens) >= 3 and tokens[0] == "timeout" and tokens[1].isdigit():
        timeout = int(tokens[1])
        tokens = tokens[2:]
    if not tokens:
        return None
    first, rest = tokens[0], tokens[1:]
    if first == "mmt-plugin":
        if not rest:
            return None
        return ("mmt-plugin", list(rest), _subcommand_of(rest), tee, timeout)
    script = None
    args: list[str] = []
    if first in ("python", "python3") and rest:
        script, args = rest[0], rest[1:]
    elif PurePosixPath(first).name == "pcap_eval.py":
        script, args = first, rest
    if script is not None and PurePosixPath(script).name == "pcap_eval.py":
        return ("evaluation", [script, *args], None, tee, timeout)
    return None


def _subcommand_of(args: list[str]) -> str | None:
    """The first argument of a tokenized mmt-plugin invocation that is not
    an option or an option's value."""
    with_value = {"-C", "--project", "--sdk", "--cc", "--sdk-profile", "--out", "-o"}
    i = 0
    while i < len(args):
        arg = args[i]
        if arg in with_value:
            i += 2
        elif arg.startswith("-"):
            i += 1
        else:
            return arg
    return None


def realpath_of(token: str, cwd: Path) -> str:
    """The real path a command token resolves to, against ``cwd`` when it is
    relative, links followed."""
    return os.path.realpath(token if os.path.isabs(token) else str(cwd / token))


def loop_subcommand(
    args: list[str], *, project: Path, sdk: Path | None, cc: str, cwd: Path
) -> str | None:
    """The loop command a strict mmt-plugin argument vector is evidence of,
    or None when it is anything else.

    The only trusted shapes are the skill's own (SKILL.md, Step 4), token
    for token: ``-C <project> --json <command>``, with the run's SDK
    ``--sdk <sdk>`` (validate, generate) plus the run's compiler ``--cc
    <cc>`` in that order (build, test), or without an SDK ``--no-sdk
    --sdk-profile <profile>`` (validate) or ``--sdk-profile <profile>``
    (generate). The project, the SDK and the compiler are the run's own:
    a green loop of another project, against another SDK, with another
    compiler, in another order or with any further argument (a ``--model``,
    a ``--dry-run``, a packet selection, a second ``-C``) is no evidence of
    this run's. The ``-C`` target is resolved against ``cwd`` with its
    links followed, so a symlink planted at the expected project path does
    not resolve to it either.
    """
    if len(args) < 4 or args[0] != "-C" or args[2] != "--json":
        return None
    if realpath_of(args[1], cwd) != str(project):
        return None
    command = args[3]
    if command not in LOOP_COMMANDS:
        return None
    tail = args[4:]
    if sdk is None:
        if command not in LOOP_COMMANDS[:2]:
            return None
        flags = ["--no-sdk", "--sdk-profile"] if command == "validate" else ["--sdk-profile"]
        if len(tail) != len(flags) + 1 or tail[:-1] != flags:
            return None
        if not tail[-1] or tail[-1].startswith("-"):
            return None
        return command
    want = ["--sdk"] if command in LOOP_COMMANDS[:2] else ["--sdk", "--cc"]
    if len(tail) != 2 * len(want) or tail[::2] != want:
        return None
    sdk_token, *values = tail[1::2]
    if realpath_of(sdk_token, cwd) != str(sdk):
        return None
    if values and values[0] != cc:
        return None
    return command


#: pcap_eval.py's options (``scripts/pcap_eval.py``): the ones that take a
#: value at most once, the repeatable ones and the bare flag. Anything
#: else is not the script's interface, so the invocation is not trusted.
_EVAL_ONCE = frozenset(
    {
        "--sdk",
        "--plugin",
        "--label",
        "--parent",
        "--capture",
        "--out",
        "--cc",
        "--expect-filter",
        "--scope-filter",
        "--min-recall",
        "--min-agreement",
        "--max-foreign",
    }
)
_EVAL_REPEAT = frozenset({"--decode-as", "--field", "--accept"})
_EVAL_BARE = frozenset({"--synthetic"})

#: The options the script requires; each bound to the run.
_EVAL_REQUIRED = ("--sdk", "--plugin", "--label", "--parent", "--capture", "--out")


def _same_bytes(a: Path, b: Path) -> bool:
    """Whether two files hold the same bytes: a copy of the configured
    capture inside the work folder is still that capture."""
    try:
        return a.read_bytes() == b.read_bytes()
    except OSError:
        return False


def evaluation_args(
    tokens: list[str],
    *,
    project: Path,
    sdk: Path | None,
    cc: str,
    capture: Path | None,
    work: Path,
    work_capture: bool,
    cwd: Path,
) -> dict[str, list[str]] | None:
    """The evaluation script's arguments when they bind the run, by option,
    or None when the invocation is no evidence of it.

    The skill's capture evaluation (SKILL.md, Step 6) counts only with the
    run's own SDK and compiler, the plugin built in the run's project
    (``<project>/build``, named ``mmtp_*.so`` as ``build`` names its
    output), its output under the work folder, and the capture the run
    was given: the configured one or a byte-for-byte copy of it inside
    the work folder, else a capture inside the work folder when the run
    allows one (``work_capture``: leave for a synthetic one, or a user to
    answer the capture question). Every path is resolved with its links
    followed. ``--help`` exits 0 and evaluates nothing, so it is never
    evidence. The field mapping, the filters and the accepted drifts are
    the evaluation's own configuration, audited in its report: they are
    not bound.
    """
    if not tokens or any(t in ("-h", "--help") for t in tokens):
        return None
    values: dict[str, list[str]] = {}
    i = 0
    while i < len(tokens):
        key, eq, inline = tokens[i].partition("=")
        i += 1
        if key in _EVAL_BARE:
            if eq:
                return None
            values.setdefault(key, []).append("")
            continue
        if key not in _EVAL_ONCE and key not in _EVAL_REPEAT:
            return None
        if eq:
            values.setdefault(key, []).append(inline)
        elif i < len(tokens) and not tokens[i].startswith("-"):
            values.setdefault(key, []).append(tokens[i])
            i += 1
        else:
            return None
    if sdk is None:
        return None
    if any(len(values.get(key, [])) != 1 for key in _EVAL_REQUIRED) or any(
        len(values.get(key, [])) > 1 for key in _EVAL_ONCE
    ):
        return None
    if len(values.get("--cc", [])) != 1 or values["--cc"][0] != cc:
        return None
    if realpath_of(values["--sdk"][0], cwd) != str(sdk):
        return None
    if not is_within(Path(realpath_of(values["--out"][0], cwd)), work):
        return None
    plugin = Path(realpath_of(values["--plugin"][0], cwd))
    if not is_within(plugin, project / "build"):
        return None
    if not (plugin.name.startswith("mmtp_") and plugin.name.endswith(".so")):
        return None
    found = realpath_of(values["--capture"][0], cwd)
    if capture is not None:
        if found != str(capture) and not (
            is_within(Path(found), work) and _same_bytes(Path(found), capture)
        ):
            return None
    elif not work_capture or not is_within(Path(found), work):
        return None
    return values
