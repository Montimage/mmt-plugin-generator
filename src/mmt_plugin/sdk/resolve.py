"""Choosing the SDK profile (``docs/design/cli.md``, section 9).

The profile is the first of:

1. ``--sdk-profile VERSION`` (``cli``);
2. ``MMT_PLUGIN_SDK_PROFILE`` (ignored when empty);
3. ``plugin.yaml`` ``sdk.profile`` (``project_pin``, parsed by the caller);
4. the detected SDK's version: its own profile when one is bundled, else the
   nearest one with the warning ``sdk.profile-fallback``;
5. with no SDK, the newest bundled profile, with the warning
   ``sdk.profile-default``.

A profile asked for in steps 1-3 that is not bundled is ``sdk.profile-not-found``
(exit 4): an explicit choice never falls back.

"Nearest" (``nearest_version``): the newest bundled profile whose version is
not above the SDK's, so generated code only uses what that SDK already had;
when every bundled profile is newer, the oldest. Versions compare as dotted
numbers (``1.10.2`` > ``1.9.9``); a version with a suffix, a pre-release
(``1.10.2-rc1``), compares just below its release (``1.10.2``), so it gets
the newest profile below that release, and one with no numeric part, or an
SDK whose version is unknown, gets the newest profile.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from mmt_plugin.diagnostics import CliError, Diagnostic, Severity
from mmt_plugin.sdk.detect import VERSION_HEADER, Sdk
from mmt_plugin.sdk.profile import Profile, bundled_versions, get_bundled, version_key

__all__ = [
    "ENV_PROFILE",
    "ProfileChoice",
    "ProfileSource",
    "find_bundled",
    "nearest_version",
    "resolve_profile",
    "sdk_context",
]

#: The environment variable that pins a profile.
ENV_PROFILE = "MMT_PLUGIN_SDK_PROFILE"

_NUMERIC_PREFIX = re.compile(r"^[0-9]+(\.[0-9]+)*")


class ProfileSource(str, Enum):
    """Where the profile came from, as reported in ``context.sdk.profile_source``."""

    CLI = "--sdk-profile"
    ENV = ENV_PROFILE
    PROJECT = "plugin.yaml"
    SDK = "sdk"
    DEFAULT = "default"


@dataclass(frozen=True)
class ProfileChoice:
    """The chosen profile, where it came from, and the warnings to report."""

    profile: Profile
    source: ProfileSource
    diagnostics: tuple[Diagnostic, ...] = field(default=())


def _numeric_key(version: str) -> tuple[tuple[int, ...], bool] | None:
    """The numeric part's key, and whether the version is that release (no
    suffix); ``None`` with no numeric part."""
    match = _NUMERIC_PREFIX.match(version)
    if match is None:
        return None
    return version_key(match.group(0)), match.end() == len(version)


def find_bundled(version: str, bundled: Sequence[str] | None = None) -> str | None:
    """The bundled version equal to ``version`` (``1.10.2.0`` is ``1.10.2``),
    or ``None``. Only a plain dotted number can be equal."""
    versions = bundled_versions() if bundled is None else bundled
    try:
        key = version_key(version)
    except ValueError:
        return None
    return next((v for v in versions if version_key(v) == key), None)


def nearest_version(detected: str | None, bundled: Sequence[str]) -> str:
    """The bundled version to use for an SDK of version ``detected`` that has
    no profile of its own (see the module docstring). ``bundled`` must not be
    empty."""
    if not bundled:
        raise ValueError("no bundled profiles")
    ordered = sorted(bundled, key=version_key)
    numeric = None if detected is None else _numeric_key(detected)
    if numeric is None:
        return ordered[-1]
    key, is_release = numeric
    # A pre-release is just below its release: only a release reaches it.
    not_above = [
        v for v in ordered if version_key(v) < key or (is_release and version_key(v) == key)
    ]
    return not_above[-1] if not_above else ordered[0]


def _profile(version: str) -> Profile:
    profile = get_bundled(version)
    if profile is None:  # pragma: no cover - versions come from the bundle
        raise AssertionError(f"profile {version} is not bundled")
    return profile


def _pins(
    cli: str | None, env: Mapping[str, str], project_pin: str | None
) -> tuple[str, ProfileSource] | None:
    if cli is not None:
        return cli, ProfileSource.CLI
    env_pin = env.get(ENV_PROFILE, "")
    if env_pin:
        return env_pin, ProfileSource.ENV
    if project_pin is not None:
        return project_pin, ProfileSource.PROJECT
    return None


def resolve_profile(
    cli: str | None,
    env: Mapping[str, str],
    project_pin: str | None,
    sdk: Sdk | None,
) -> ProfileChoice:
    """Choose the profile in precedence order (see the module docstring).

    ``cli`` is ``--sdk-profile``, ``env`` the environment, ``project_pin``
    ``plugin.yaml``'s ``sdk.profile`` and ``sdk`` the detected SDK, if any.
    Raises ``CliError`` ``sdk.profile-not-found`` for an explicit profile that
    is not bundled.
    """
    versions = bundled_versions()
    names = ", ".join(versions)
    pin = _pins(cli, env, project_pin)
    if pin is not None:
        wanted, source = pin
        found = find_bundled(wanted, versions)
        if found is None:
            raise CliError(
                "sdk.profile-not-found",
                f"{source.value} asks for SDK profile {wanted!r}, which is not bundled",
                f"bundled profiles: {names}; pick one of them, or use an mmt-plugin that bundles"
                f" {wanted}",
            )
        return ProfileChoice(_profile(found), source)
    pin_hint = (
        f"pin a profile with --sdk-profile, {ENV_PROFILE} or plugin.yaml sdk.profile"
        f" (bundled: {names})"
    )
    if sdk is None:
        newest = versions[-1]
        warning = Diagnostic(
            Severity.WARNING,
            "sdk.profile-default",
            f"no SDK found and no profile pinned: using the newest bundled profile, {newest}",
            hint=f"pass the SDK with --sdk or MMT_BASE, or {pin_hint}",
        )
        return ProfileChoice(_profile(newest), ProfileSource.DEFAULT, (warning,))
    if sdk.version is not None:
        exact = find_bundled(sdk.version, versions)
        if exact is not None:
            return ProfileChoice(_profile(exact), ProfileSource.SDK)
    nearest = nearest_version(sdk.version, versions)
    if sdk.version is None:
        why = f"the version of the SDK at {sdk.prefix} is unknown (no VERSION in {VERSION_HEADER})"
    else:
        why = f"no profile is bundled for mmt-dpi {sdk.version} (the SDK at {sdk.prefix})"
    warning = Diagnostic(
        Severity.WARNING,
        "sdk.profile-fallback",
        f"{why}: using the nearest bundled profile, {nearest}",
        hint=pin_hint,
    )
    return ProfileChoice(_profile(nearest), ProfileSource.SDK, (warning,))


def sdk_context(sdk: Sdk | None, choice: ProfileChoice | None) -> dict[str, Any]:
    """The envelope's ``context.sdk``: ``prefix``, ``version``, ``profile``,
    ``source`` (of the prefix) and ``profile_source``; ``None`` for an SDK or
    profile that is not known."""
    return {
        "prefix": None if sdk is None else sdk.prefix,
        "version": None if sdk is None else sdk.version,
        "profile": None if choice is None else choice.profile.version,
        "source": None if sdk is None else sdk.source.value,
        "profile_source": None if choice is None else choice.source.value,
    }
