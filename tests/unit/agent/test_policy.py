"""What the agent's shell refuses, the commands it recognises and the
environment it passes on (``mmt_plugin_agent.policy``)."""

from __future__ import annotations

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
