"""Tests for ``mmt_plugin.sdk.resolve``: one per step of the profile precedence
(``--sdk-profile`` > ``MMT_PLUGIN_SDK_PROFILE`` > ``plugin.yaml`` > the
detected SDK > newest), the fallback and "nearest"."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from mmt_plugin import envelope
from mmt_plugin.diagnostics import CODES, CliError, Severity
from mmt_plugin.exitcodes import ExitCode
from mmt_plugin.sdk.detect import Sdk, SdkSource
from mmt_plugin.sdk.resolve import (
    ENV_PROFILE,
    ProfileChoice,
    ProfileSource,
    find_bundled,
    nearest_version,
    resolve_profile,
    sdk_context,
)

SDK = Sdk("/tmp/sdk", SdkSource.ENV, "1.10.2")


def _sdk(version: str | None) -> Sdk:
    return Sdk("/tmp/sdk", SdkSource.CLI, version)


def _assert_choice(choice: ProfileChoice, version: str, source: ProfileSource) -> None:
    assert (choice.profile.version, choice.source) == (version, source)


# --- precedence --------------------------------------------------------------


def test_sdk_profile_option_comes_first() -> None:
    choice = resolve_profile("1.10.2", {ENV_PROFILE: "9.9"}, "9.9", _sdk("9.9"))
    _assert_choice(choice, "1.10.2", ProfileSource.CLI)
    assert choice.diagnostics == ()


def test_env_comes_second() -> None:
    choice = resolve_profile(None, {ENV_PROFILE: "1.10.2"}, "9.9", _sdk("9.9"))
    _assert_choice(choice, "1.10.2", ProfileSource.ENV)


def test_plugin_yaml_comes_third() -> None:
    choice = resolve_profile(None, {ENV_PROFILE: ""}, "1.10.2", _sdk("9.9"))
    _assert_choice(choice, "1.10.2", ProfileSource.PROJECT)


def test_the_detected_sdk_comes_fourth() -> None:
    choice = resolve_profile(None, {}, None, SDK)
    _assert_choice(choice, "1.10.2", ProfileSource.SDK)
    assert choice.diagnostics == ()


def test_no_sdk_and_no_pin_takes_the_newest_with_a_warning() -> None:
    choice = resolve_profile(None, {}, None, None)
    _assert_choice(choice, "1.10.2", ProfileSource.DEFAULT)
    (warning,) = choice.diagnostics
    assert (warning.severity, warning.code) == (Severity.WARNING, "sdk.profile-default")
    assert "newest bundled profile, 1.10.2" in warning.message
    assert warning.hint and "--sdk-profile" in warning.hint and "--sdk" in warning.hint


# --- explicit profiles never fall back -------------------------------------------


@pytest.mark.parametrize(
    ("cli", "env", "pin", "source"),
    [
        ("1.9.0", {}, None, "--sdk-profile"),
        (None, {ENV_PROFILE: "2.0"}, None, ENV_PROFILE),
        (None, {}, "latest", "plugin.yaml"),
        ("", {}, None, "--sdk-profile"),
    ],
)
def test_an_unbundled_explicit_profile_is_an_error(
    cli: str | None, env: dict[str, str], pin: str | None, source: str
) -> None:
    with pytest.raises(CliError) as info:
        resolve_profile(cli, env, pin, SDK)
    assert info.value.code == "sdk.profile-not-found"
    assert info.value.exit_code is ExitCode.SDK
    assert info.value.message.startswith(f"{source} asks for SDK profile")
    assert info.value.hint and "bundled profiles: 1.10.2" in info.value.hint


def test_an_equal_version_spelling_is_the_same_profile() -> None:
    _assert_choice(resolve_profile("1.10.2.0", {}, None, None), "1.10.2", ProfileSource.CLI)
    assert find_bundled("1.10.2.0") == "1.10.2"
    assert find_bundled("1.10.2-rc1") is None


# --- fallback to the nearest ------------------------------------------------------


@pytest.mark.parametrize(
    ("detected", "why"),
    [
        ("1.11.0", "no profile is bundled for mmt-dpi 1.11.0"),
        ("1.9.4", "no profile is bundled for mmt-dpi 1.9.4"),
        ("1.10.2-rc1", "no profile is bundled for mmt-dpi 1.10.2-rc1"),
        ("devel", "no profile is bundled for mmt-dpi devel"),
        (None, "the version of the SDK at /tmp/sdk is unknown"),
    ],
)
def test_an_unknown_sdk_version_falls_back_with_a_warning(detected: str | None, why: str) -> None:
    choice = resolve_profile(None, {}, None, _sdk(detected))
    _assert_choice(choice, "1.10.2", ProfileSource.SDK)
    (warning,) = choice.diagnostics
    assert (warning.severity, warning.code) == (Severity.WARNING, "sdk.profile-fallback")
    assert warning.message.startswith(why)
    assert warning.message.endswith("using the nearest bundled profile, 1.10.2")
    assert warning.hint and ENV_PROFILE in warning.hint


BUNDLE = ["1.10.2", "2.0", "1.11.0"]


@pytest.mark.parametrize(
    ("detected", "nearest"),
    [
        ("1.10.2", "1.10.2"),
        ("1.10.5", "1.10.2"),  # newest not above it
        ("1.11", "1.11.0"),
        ("1.11.0-rc1", "1.11.0"),  # numeric part
        ("1.12.0", "1.11.0"),
        ("3.1", "2.0"),
        ("1.9.9", "1.10.2"),  # all newer: the oldest
        ("0", "1.10.2"),
        ("devel", "2.0"),  # no number: the newest
        (None, "2.0"),
    ],
)
def test_nearest(detected: str | None, nearest: str) -> None:
    assert nearest_version(detected, BUNDLE) == nearest


def test_nearest_needs_a_profile() -> None:
    with pytest.raises(ValueError):
        nearest_version("1.0", [])


# --- context.sdk ------------------------------------------------------------------


def test_sdk_context(validate_envelope: Callable[[Any], None]) -> None:
    choice = resolve_profile(None, {}, None, SDK)
    ctx = sdk_context(SDK, choice)
    assert ctx == {
        "prefix": "/tmp/sdk",
        "version": "1.10.2",
        "profile": "1.10.2",
        "source": "MMT_BASE",
        "profile_source": "sdk",
    }
    validate_envelope(envelope.build(command="x", context={"sdk": ctx}))
    assert sdk_context(None, resolve_profile(None, {}, None, None)) == {
        "prefix": None,
        "version": None,
        "profile": "1.10.2",
        "source": None,
        "profile_source": "default",
    }
    assert set(sdk_context(None, None).values()) == {None}


def test_the_sdk_codes_are_registered() -> None:
    for code in (
        "sdk.not-found",
        "sdk.invalid-prefix",
        "sdk.invalid-pkg-config",
        "sdk.profile-not-found",
        "sdk.profile-fallback",
        "sdk.profile-default",
    ):
        assert code in CODES
        assert CliError(code, "m").exit_code is ExitCode.SDK
