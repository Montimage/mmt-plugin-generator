"""``mmt-plugin-agent doctor``: what a run needs, each check ``pass``, ``warn``
or ``fail`` with a hint. A ``fail`` is a dependency the agent cannot run
without; a ``warn`` one the skill works around (no tshark: no drift check;
no Docker: synthetic captures only, with leave)."""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from mmt_plugin_agent.models import ENV_MODEL, model_spec
from mmt_plugin_agent.policy import hide_environ, is_system_prefix, readable_ancestors
from mmt_plugin_agent.skills import ENV_SKILLS, SKILL_NAME, find_skills_dir

__all__ = ["MIN_PYTHON", "DoctorCheck", "DoctorReport", "run_doctor"]

#: deepagents 0.7.32 needs Python 3.11.
MIN_PYTHON = (3, 11)

CheckStatus = Literal["pass", "warn", "fail"]

#: Seconds for each probe (mmt-plugin doctor, the compiler, docker info).
PROBE_TIMEOUT = 60

#: The API key variable of each provider the extra installs.
_PROVIDER_KEYS = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY"}


@dataclass(frozen=True)
class DoctorCheck:
    id: str
    status: CheckStatus
    detail: str
    hint: str | None = None

    def to_json(self) -> dict[str, Any]:
        return {"id": self.id, "status": self.status, "detail": self.detail, "hint": self.hint}


@dataclass
class DoctorReport:
    checks: list[DoctorCheck] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(c.status != "fail" for c in self.checks)

    def to_json(self) -> dict[str, Any]:
        return {"ok": self.ok, "checks": [c.to_json() for c in self.checks]}


def _probe(argv: list[str], stdin: str | None = None) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(
            argv,
            input=stdin,
            capture_output=True,
            text=True,
            timeout=PROBE_TIMEOUT,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None


def _python() -> DoctorCheck:
    version = ".".join(str(n) for n in sys.version_info[:3])
    if sys.version_info[:2] >= MIN_PYTHON:
        return DoctorCheck("python", "pass", f"Python {version}")
    return DoctorCheck(
        "python", "fail", f"Python {version}", "mmt-plugin-agent needs Python 3.11 or newer"
    )


def _extra() -> DoctorCheck:
    names = ("deepagents", "langgraph", "langchain", "langchain_anthropic")
    missing = [n for n in names if importlib.util.find_spec(n) is None]
    if not missing:
        return DoctorCheck("agent-extra", "pass", "deepagents, langgraph and langchain import")
    return DoctorCheck(
        "agent-extra",
        "fail",
        f"not installed: {', '.join(missing)}",
        "install the extra with Python 3.11+: pip install 'mmt-plugin[agent]'",
    )


def _mmt_plugin_checks(sdk: Path | None, cc: str) -> list[DoctorCheck]:
    exe = shutil.which("mmt-plugin")
    if exe is None:
        return [
            DoctorCheck(
                "mmt-plugin",
                "fail",
                "mmt-plugin is not on PATH",
                "install mmt-plugin in the same environment (pip install mmt-plugin), "
                "or run inside the checkout with uv run",
            )
        ]
    checks = [DoctorCheck("mmt-plugin", "pass", exe)]
    if sdk is None:
        checks.append(
            DoctorCheck(
                "sdk",
                "warn",
                "no SDK prefix: the run stops after generate",
                "pass --sdk PREFIX (or set MMT_BASE) to a private mmt-dpi prefix",
            )
        )
        return checks
    if is_system_prefix(sdk):
        checks.append(
            DoctorCheck(
                "sdk",
                "fail",
                f"{sdk} is under /opt/mmt, which the skill never uses (SKILL.md, Rule 3)",
                "extract the mmt-dpi package into a private prefix and pass it with --sdk "
                "(or MMT_BASE); AGENTS.md, 'A private prefix can also come from the "
                "published package'",
            )
        )
        return checks
    probe = _probe([exe, "--json", "doctor", "--sdk", str(sdk), "--cc", cc])
    found: dict[str, Any] = {}
    if probe is not None:
        try:
            result = json.loads(probe.stdout).get("result") or {}
            found = {c["id"]: c for c in result.get("checks") or []}
        except (ValueError, AttributeError, TypeError, KeyError):
            found = {}
    for ident, hint in (
        ("sdk", f"pass --sdk a prefix that holds dpi/include/mmt_log.h (given: {sdk})"),
        ("compiler", f"install {cc} (or pass --cc clang)"),
    ):
        check = found.get(ident)
        if check is None:
            checks.append(
                DoctorCheck(ident, "fail", "mmt-plugin --json doctor did not report it", hint)
            )
            continue
        status: CheckStatus = "fail" if check.get("status") == "fail" else "pass"
        checks.append(
            DoctorCheck(
                ident, status, str(check.get("detail")), hint if status == "fail" else None
            )
        )
    return checks


def _tool(name: str, why: str) -> DoctorCheck:
    path = shutil.which(name)
    if path is not None:
        return DoctorCheck(name, "pass", path)
    return DoctorCheck(
        name, "warn", f"{name} is not on PATH: {why}", "install Wireshark's command line tools"
    )


def _libpcap(cc: str) -> DoctorCheck:
    probe = _probe([cc, "-fsyntax-only", "-x", "c", "-"], stdin="#include <pcap.h>\n")
    if probe is not None and probe.returncode == 0:
        return DoctorCheck("libpcap", "pass", f"{cc} finds pcap.h")
    return DoctorCheck(
        "libpcap",
        "warn",
        f"{cc} does not find pcap.h: no capture evaluation",
        "install the libpcap headers (libpcap-dev)",
    )


def _cyberlab() -> DoctorCheck:
    local = os.environ.get("CYBERLAB_DIR")
    if local and (Path(local) / "scripts" / "cyberlab").is_file():
        return DoctorCheck("cyberlab", "pass", f"local: {local}")
    asm = shutil.which("asm")
    if asm is not None:
        return DoctorCheck("cyberlab", "pass", f"through asm ({asm})")
    return DoctorCheck(
        "cyberlab",
        "warn",
        "no local cyberlab and no asm: captures are not recorded, only synthetic ones",
        "set CYBERLAB_DIR to a cyberlab skill directory, or install asm "
        "(npm install -g agent-skill-manager)",
    )


def _docker() -> DoctorCheck:
    exe = shutil.which("docker")
    if exe is None:
        return DoctorCheck(
            "docker",
            "warn",
            "no docker: cyberlab cannot record a capture",
            "install docker, or mount a Docker socket into the agent's container",
        )
    probe = _probe([exe, "info", "--format", "{{.ServerVersion}}"])
    if probe is not None and probe.returncode == 0:
        return DoctorCheck("docker", "pass", f"docker server {probe.stdout.strip()}")
    return DoctorCheck(
        "docker",
        "warn",
        "docker cannot reach a server: cyberlab cannot record a capture",
        "start Docker, or set DOCKER_HOST",
    )


def _skills(skills_dir: str | os.PathLike[str] | None) -> DoctorCheck:
    found = find_skills_dir(skills_dir)
    if found is not None:
        return DoctorCheck("skills", "pass", str(found / SKILL_NAME))
    return DoctorCheck(
        "skills",
        "fail",
        f"no {SKILL_NAME}/SKILL.md found",
        f"pass --skills DIR (or set {ENV_SKILLS}) to a directory holding {SKILL_NAME}/",
    )


def _home() -> DoctorCheck:
    home = os.environ.get("HOME")
    if home and Path(home).is_dir():
        return DoctorCheck("home", "pass", home)
    return DoctorCheck("home", "fail", "HOME is not a directory", "set HOME to your home")


def _environ(proc: Path = Path("/proc"), start: int | None = None) -> DoctorCheck:
    reason = hide_environ()
    if reason is None:
        leaks = readable_ancestors(proc, start)
        if not leaks:
            return DoctorCheck(
                "environ",
                "pass",
                "not dumpable: the shell cannot read the agent's own environment, and no "
                "parent process it can read holds a key",
            )
        held = "; ".join(f"{pid} ({comm}): {', '.join(names)}" for pid, comm, names in leaks)
        return DoctorCheck(
            "environ",
            "warn",
            "only the agent's own environment is hidden: the shell can read a parent "
            f"process's, which holds {held}",
            "start the mmt-plugin-agent console script directly (not through uv run or a "
            "wrapper started with the key), or run the agent in the agent image (make "
            "agent-run), where it is PID 1",
        )
    return DoctorCheck(
        "environ",
        "warn",
        reason,
        "run the agent in the agent image (make agent-run), where its shell cannot read "
        "the provider keys",
    )


def _model(model: str | None, model_object: bool) -> DoctorCheck:
    if model_object:
        return DoctorCheck("model", "pass", "a chat model object")
    spec = model_spec(model)
    if spec is None:
        return DoctorCheck(
            "model",
            "fail",
            "no model configured",
            f"pass --model PROVIDER:MODEL or set {ENV_MODEL}",
        )
    provider = spec.split(":", 1)[0]
    key = _PROVIDER_KEYS.get(provider)
    if (
        key is not None
        and not os.environ.get(key)
        and not (provider == "openai" and os.environ.get("OPENAI_BASE_URL"))
    ):
        return DoctorCheck("model", "warn", f"{spec}, but {key} is not set", f"export {key}")
    return DoctorCheck("model", "pass", spec)


def run_doctor(
    *,
    sdk: Path | None,
    cc: str,
    skills_dir: str | os.PathLike[str] | None = None,
    model: str | None = None,
    model_object: bool = False,
) -> DoctorReport:
    """Every check, in the order they are printed."""
    checks = [_python(), _extra(), *_mmt_plugin_checks(sdk, cc)]
    if not any(c.id == "compiler" for c in checks):
        path = shutil.which(cc)
        # Without an SDK nothing is compiled: build, test and the evaluation stop.
        missing: CheckStatus = "fail" if sdk is not None else "warn"
        checks.append(
            DoctorCheck("compiler", "pass", path)
            if path
            else DoctorCheck("compiler", missing, f"{cc} is not on PATH", f"install {cc}")
        )
    checks += [
        _tool("tshark", "no field and drift check against tshark"),
        _tool("capinfos", "captures are not checked"),
        _tool("editcap", "large captures are not cut"),
        _tool("mergecap", "other traffic is not merged into a synthetic capture"),
        _libpcap(cc),
        _cyberlab(),
        _docker(),
        _skills(skills_dir),
        _home(),
        _environ(),
        _model(model, model_object),
    ]
    return DoctorReport(checks)
