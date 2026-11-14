"""The user code scaffold, ``src/<label>_impl.c`` (plan T2.2, decision 3).

``mmt_plugin.codegen.scaffold(generation, profile)`` renders
``templates/impl.c.j2`` from ``scaffold_context`` in memory:
a definition of every hook the generated header declares, which compiles
with ``-Wall -Wextra -Werror`` and lets the plugin load, and a commented
example in ``<label>_hook_register_parents`` that attaches the protocol to
Ethernet. It writes nothing: the scaffold is written once, when a project is
created (``mmt-plugin init``, #23), and is the user's from then on.
``generate`` never writes under ``src/``, so a model change that adds a hook
leaves the file as it is and the build fails (``mmt_plugin.codegen.hooks``).

Each stub returns a value that means "nothing here": 0 (an attribute is
absent), ``NULL``, ``false``, the profile's "skip" verdict for a classifier,
and 1 for ``<label>_hook_register_parents``, whose 0 would fail the load.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from mmt_plugin.codegen.cgen import REGISTER_PARENTS, Hook
from mmt_plugin.sdk.profile import Profile

if TYPE_CHECKING:
    from mmt_plugin.codegen import Generation

__all__ = [
    "SCAFFOLD_TEMPLATE",
    "ScaffoldFile",
    "classification_names",
    "impl_name",
    "scaffold_context",
]

#: The scaffold's template (``mmt_plugin.codegen.ENVIRONMENT``).
SCAFFOLD_TEMPLATE = "impl.c.j2"

#: The parent the example attaches the protocol to.
_EXAMPLE_PARENT = "PROTO_ETHERNET"


@dataclass(frozen=True)
class ScaffoldFile:
    """The scaffold: its path in the project (``src/<label>_impl.c``) and
    its text."""

    path: str
    text: str

    @property
    def data(self) -> bytes:
        """The bytes written: UTF-8 (the text is ASCII)."""
        return self.text.encode("utf-8")


@dataclass(frozen=True)
class _Stub:
    """What the template prints for one hook."""

    declaration: str
    doc: str
    params: tuple[str, ...]
    value: str | None  # None: the hook returns void
    parents: bool


def impl_name(label: str) -> str:
    """The user code file of ``label``, relative to the project:
    ``src/<label>_impl.c``."""
    return f"src/{label.lower()}_impl.c"


def _value(hook: Hook, profile: Profile) -> str | None:
    """What the stub of ``hook`` returns."""
    if hook.role == REGISTER_PARENTS:
        return "1"
    if hook.returns == "void":
        return None
    if hook.returns.endswith("*"):
        return "NULL"
    if hook.returns == "bool":
        return "false"
    if hook.returns == profile.callback("classification").returns:
        return profile.constant("MMT_CLASSIFY_SKIP").name
    if hook.returns in ("int", "unsigned"):
        return "0"
    raise ValueError(f"{hook.name}: no stub value for the return type {hook.returns}")


def classification_names(profile: Profile) -> tuple[dict[str, str], tuple[str, ...]]:
    """The SDK names of the register_parents example, from the profile, and
    the headers that declare them (in the profile's order)."""
    if profile.parents.id_of(_EXAMPLE_PARENT) is None:
        raise KeyError(f"SDK profile {profile.version} has no parent {_EXAMPLE_PARENT}")
    used = {profile.parents.header}

    def field(struct: str, name: str) -> str:
        used.add(profile.struct(struct).header)
        for f in profile.struct(struct).fields:
            if f.name == name:
                return f.name
        raise KeyError(f"SDK profile {profile.version}: {struct} has no field {name}")

    def function(name: str) -> str:
        fn = profile.function(name)
        used.add(fn.header)
        return fn.name

    def constant(name: str) -> str:
        c = profile.constant(name)
        used.add(c.header)
        return c.name

    classification = profile.callback("classification")
    used.add(classification.header)
    ipacket_t = classification.params[0].type.removesuffix("*").strip()
    names = {
        "ethernet": _EXAMPLE_PARENT,
        "verdict_t": classification.returns,
        "ipacket_t": ipacket_t,
        "offset_at": function("get_packet_offset_at_index"),
        "classified_proto_t": profile.struct("classified_proto_t").name,
        "ipacket_header": field(ipacket_t, "p_hdr"),
        "ipacket_data": field(ipacket_t, "data"),
        "caplen": field("pkthdr_t", "caplen"),
        "next_proto": field("classified_proto_t", "proto_id"),
        "next_offset": field("classified_proto_t", "offset"),
        "next_status": field("classified_proto_t", "status"),
        "classified": constant("Classified"),
        "skip": constant("MMT_CLASSIFY_SKIP"),
        "matched": constant("MMT_CLASSIFY_MATCHED"),
        "set_classified_proto": function("set_classified_proto"),
        "with_parent": function("register_classification_function_with_parent_protocol"),
    }
    return names, tuple(h.name for h in profile.headers if h.name in used)


def scaffold_context(generation: Generation, profile: Profile) -> dict[str, object]:
    """What ``templates/impl.c.j2`` prints for ``generation``."""
    label = generation.label
    names, includes = classification_names(profile)
    stubs = tuple(
        _Stub(
            declaration=h.declaration,
            doc=h.doc,
            params=tuple(p.name for p in h.params),
            value=_value(h, profile),
            parents=h.role == REGISTER_PARENTS,
        )
        for h in generation.hooks
    )
    return {
        "path": impl_name(label),
        "lc": label.lower(),
        "label": label,
        "header": generation.header,
        "proto_macro": f"PROTO_{label.upper()}",
        "hooks": stubs,
        "sdk": names,
        "example_includes": includes,
        "sdk_version": profile.version,
    }
