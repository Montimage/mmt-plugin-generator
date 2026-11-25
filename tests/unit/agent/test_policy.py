"""What the agent's shell refuses, the commands it recognises and the
environment it passes on (``mmt_plugin_agent.policy``)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path, PurePosixPath

import pytest

from mmt_plugin_agent import policy
from mmt_plugin_agent.errors import redact
from mmt_plugin_agent.policy import check_command, is_system_prefix, mmt_plugin_command, shell_env


@pytest.mark.parametrize(
    "command",
    [
        "sudo make install",
        "cd x && /usr/bin/sudo -n true",
        "mmt-plugin install --system",
        "mmt-plugin install --system=yes",
        "mmt-plugin -C p --json validate --sdk /opt/mmt",
        "ls /opt/mmt/plugins",
        "mmt-plugin build --sdk=/opt/mmt/",
        "cat /opt/./mmt/dpi/include/mmt_log.h",
        "echo 'unbalanced",
    ],
)
def test_the_shell_refuses_what_the_skill_never_does(command: str) -> None:
    assert check_command(command).refused is not None


@pytest.mark.parametrize(
    "command",
    [
        "mmt-plugin -C p --json validate --sdk /home/u/sdk/opt/mmt",
        "/opt/mmt-plugin/bin/mmt-plugin --version",
        "python3 /opt/mmt-plugin-skills/mmt-plugin-generator/scripts/pcap_eval.py --help",
        "ls /opt/mmtx",
        "echo 'sudo is never used' --system-wide",
        "grep -r 'é \"quoted\" <b>' .",
    ],
)
def test_the_shell_runs_paths_next_to_the_system_prefix(command: str) -> None:
    assert check_command(command) == check_command(command).__class__()


def test_force_is_flagged_not_refused() -> None:
    assert check_command("mmt-plugin -C p --json generate --force").force
    assert check_command("mmt-plugin import x --force=1").force
    assert not check_command("echo 'no --force here'").force
    assert check_command("mmt-plugin generate --force").refused is None


@pytest.mark.parametrize(
    ("command", "found"),
    [
        ("mmt-plugin -C proj --json validate --sdk s", ("validate", "proj")),
        ("mmt-plugin --json -C p test --sdk s | tee runs/run-1/test.json", ("test", "p")),
        ("set -o pipefail; uv run mmt-plugin --json init demo", ("init", None)),
        ("python -m mmt_plugin --json --version", None),
        ("/opt/mmt-plugin/bin/mmt-plugin -C 'a b' build", ("build", "a b")),
        ("echo mmt-plugin", None),
        ("ls -la", None),
    ],
)
def test_the_mmt_plugin_command_of_a_shell_command(
    command: str, found: tuple[str, str | None] | None
) -> None:
    assert mmt_plugin_command(command) == found


def test_the_shell_gets_the_allowed_variables_without_secrets() -> None:
    env = shell_env(
        {
            "PATH": "/bin",
            "HOME": "/h",
            "LC_ALL": "C",
            "MMT_BASE": "/sdk",
            "UV_CACHE_DIR": "/c",
            "ANTHROPIC_API_KEY": "k",
            "OPENAI_API_KEY": "k",
            "MMT_TOKEN": "t",
            "MMT_DB_PASSWORD": "p",
            "GITHUB_TOKEN": "t",
            "AWS_SECRET_ACCESS_KEY": "s",
            "PYTHONPATH": "/x",
        }
    )
    assert env == {
        "PATH": "/bin",
        "HOME": "/h",
        "LC_ALL": "C",
        "MMT_BASE": "/sdk",
        "UV_CACHE_DIR": "/c",
        "PYTHONDONTWRITEBYTECODE": "1",
    }


def test_uv_passes_only_its_own_settings_not_its_index_urls() -> None:
    env = shell_env(
        {
            "UV_CACHE_DIR": "/c",
            "UV_LOCKED": "1",
            "UV_INDEX_URL": "https://u:t@pypi.example/simple",
            "UV_EXTRA_INDEX_URL": "https://u:t@pypi.example/simple",
            "UV_DEFAULT_INDEX": "https://u:t@pypi.example/simple",
            "UV_INDEX": "corp=https://u:t@pypi.example/simple",
        }
    )
    assert env == {"UV_CACHE_DIR": "/c", "UV_LOCKED": "1", "PYTHONDONTWRITEBYTECODE": "1"}


@pytest.mark.parametrize(
    ("name", "value", "passed"),
    [
        ("HTTPS_PROXY", "http://u:p@h:3128", "http://h:3128"),
        ("http_proxy", "http://token@proxy.example:8080/", "http://proxy.example:8080/"),
        ("HTTP_PROXY", "u:p@h:3128", "h:3128"),
        ("https_proxy", "http://u:p@[::1]:3128", "http://[::1]:3128"),
        ("HTTPS_PROXY", "http://h:3128", "http://h:3128"),
        ("NO_PROXY", "localhost,.example,10.0.0.0/8", "localhost,.example,10.0.0.0/8"),
        ("DOCKER_HOST", "ssh://user@build.example", "ssh://user@build.example"),
        ("DOCKER_HOST", "tcp://u:p@docker.example:2376", "tcp://docker.example:2376"),
        (
            "MMT_MIRRORS",
            "https://u:p@a.example/x, https://b.example/y",
            "https://a.example/x, https://b.example/y",
        ),
        ("MMT_BASE", "/home/u@corp/sdk", "/home/u@corp/sdk"),
    ],
)
def test_the_shell_gets_urls_without_their_credentials(name: str, value: str, passed: str) -> None:
    assert shell_env({name: value})[name] == passed


def test_an_sdk_prefix_under_the_system_prefix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert is_system_prefix("/opt/mmt") and is_system_prefix("/opt/mmt/dpi/..")
    assert not is_system_prefix("/opt/mmt-sdk") and not is_system_prefix(tmp_path)
    # A link to it, with a stand-in system prefix: tests never look at /opt/mmt.
    system = tmp_path / "system"
    (system / "dpi").mkdir(parents=True)
    monkeypatch.setattr(policy, "_SYSTEM_PREFIX", PurePosixPath(system))
    (tmp_path / "sdk").symlink_to(system / "dpi")
    assert is_system_prefix(tmp_path / "sdk")


def test_secrets_are_redacted_from_messages() -> None:
    env = {"ANTHROPIC_API_KEY": "abcdefgh12345678", "HOME": "/home/agent"}
    text = redact("bad key abcdefgh12345678, or sk-proj-0123456789abc, in /home/agent", env)
    assert text == "bad key <ANTHROPIC_API_KEY>, or <key>, in /home/agent"


def test_a_urls_credentials_are_redacted_from_messages() -> None:
    text = redact("no index at https://u:t@pypi.example/simple or http://tok@h:3128/", {})
    assert (
        text == "no index at https://<userinfo>@pypi.example/simple or http://<userinfo>@h:3128/"
    )


#: In a child Python: hide_environ(), then a shell child reads its parent's
#: environment (and PID 1's); prints the hide_environ() result first.
_HIDE = """
import subprocess, sys
from mmt_plugin_agent.policy import hide_environ
print(repr(hide_environ()))
sys.stdout.flush()
shell = "cat /proc/$PPID/environ /proc/1/environ"
subprocess.run(["sh", "-c", shell], env={"PATH": "/bin:/usr/bin"})
"""


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="prctl is Linux's")
def test_the_shell_cannot_read_the_agents_environment() -> None:
    key = "dummy-not-a-real-key-123456"
    env = {**os.environ, "ANTHROPIC_API_KEY": key}
    # A separate process: a non-dumpable pytest would stay so for the session.
    done = subprocess.run(
        [sys.executable, "-c", _HIDE], env=env, capture_output=True, text=True, check=True
    )
    assert done.stdout.splitlines()[0] == "None", done.stdout
    assert key not in done.stdout


@pytest.mark.skipif(sys.platform.startswith("linux"), reason="off Linux only")
def test_off_linux_the_environment_is_not_hidden_and_says_why() -> None:
    reason = policy.hide_environ()
    assert reason is not None and "not Linux" in reason
    assert policy.environ_failure() is None
