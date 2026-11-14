"""The mmt-dpi SDK: bundled profiles, prefix detection and profile choice.

- ``mmt_plugin.sdk.profile``: the profile data files, loaded into frozen
  dataclasses (``Profile``), and the bundled versions;
- ``mmt_plugin.sdk.detect``: the SDK prefix (``find_sdk``, ``require_sdk``)
  and its version;
- ``mmt_plugin.sdk.resolve``: the profile to use (``resolve_profile``) and
  the envelope's ``context.sdk`` (``sdk_context``);
- ``mmt_plugin.sdk.headercheck``: checks a profile against real headers;
- ``mmt_plugin.sdk.registry``: the protocols an installed SDK registers at
  run time with its plugins (``read_registry``).

No command is registered here: ``generate``, ``validate``, ``build`` and
``doctor`` call these functions.
"""

from mmt_plugin.sdk.detect import Sdk, SdkSource, find_sdk, require_sdk
from mmt_plugin.sdk.profile import Profile, ProfileError, bundled_versions, get_bundled
from mmt_plugin.sdk.resolve import ProfileChoice, ProfileSource, resolve_profile, sdk_context

__all__ = [
    "Profile",
    "ProfileChoice",
    "ProfileError",
    "ProfileSource",
    "Sdk",
    "SdkSource",
    "bundled_versions",
    "find_sdk",
    "get_bundled",
    "require_sdk",
    "resolve_profile",
    "sdk_context",
]
