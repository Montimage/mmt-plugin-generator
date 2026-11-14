"""Tests for ``mmt_plugin.sdk.profile``: the bundled profile, its schema and
the loader's checks."""

from __future__ import annotations

import copy
import json
from collections.abc import Callable
from importlib import resources
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from mmt_plugin.sdk.profile import (
    SCHEMA_VERSION,
    Param,
    Profile,
    ProfileError,
    bundled_versions,
    get_bundled,
    load_profile,
    load_schema,
    parse_profile,
    version_key,
)

BUNDLED = resources.files("mmt_plugin").joinpath("sdk/profiles/1.10.2.json")


def _raw() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(BUNDLED.read_text(encoding="utf-8"))
    return data


@pytest.fixture
def profile() -> Profile:
    p = get_bundled("1.10.2")
    assert p is not None
    return p


def test_the_bundled_profiles() -> None:
    assert bundled_versions() == ["1.10.2"]
    assert get_bundled("1.10.3") is None


def test_the_bundled_profile_follows_its_schema() -> None:
    schema = load_schema()
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(_raw())
    assert _raw()["schema_version"] == SCHEMA_VERSION


def test_what_the_generator_needs(profile: Profile) -> None:
    extraction = profile.callback("attribute_extraction")
    assert extraction.typedef == "generic_attribute_extraction_function"
    assert extraction.function_type == (
        "int (const ipacket_t *, mmt_proto_index_t, attribute_t *)"
    )
    assert (
        extraction.pointer_type == "int (*)(const ipacket_t *, mmt_proto_index_t, attribute_t *)"
    )
    assert [p.declaration for p in extraction.params] == [
        "const ipacket_t *packet",
        "mmt_proto_index_t proto_index",
        "attribute_t *extracted_data",
    ]
    assert profile.callback("init_proto").function_type == "int (void)"
    assert profile.callback("classification").returns == "mmt_classify_verdict_t"
    assert profile.function("register_protocol").header == "plugin_defs.h"
    assert profile.function("general_char_extraction").implements == "attribute_extraction"
    fields = [f.name for f in profile.struct("attribute_metadata_t").fields]
    assert fields == [
        "id",
        "alias",
        "data_type",
        "data_len",
        "position_in_packet",
        "scope",
        "extraction_function",
    ]
    assert profile.constant("SCOPE_PACKET").header == "mmt_core.h"
    assert profile.constant("Max_Alias_Len").value == 64
    assert profile.constant("SCOPE_PACKET").value is None
    assert len([c for c in profile.constants if c.group == "data_type"]) == 26
    assert profile.logger.header == "mmt_log.h"
    assert profile.logger.debug_opt_in == "MMT_LOG_ENABLE_DEBUG"
    assert profile.class_provider.register == "mmt_register_class_provider"
    assert profile.parents.id_for("tcp") == "PROTO_TCP"
    # The ids that model checks compare a plugin's id and name with (#12).
    assert profile.constant("PROTO_MAX_IDENTIFIER").value == 1000
    assert profile.constant("PROTO_META").value == 1
    assert profile.parents.id_of("PROTO_TCP") == 354
    assert profile.parents.id_of("PROTO_TPKT") == 637
    assert profile.parents.id_of("PROTO_NOTHING") is None
    # Every plugin the 1.10.2 package installs (#51 review, F1), by header.
    assert [(h.header, len(h.protocols)) for h in profile.parents.ids] == [
        ("tcpip/mmt_tcpip_protocols.h", 670),
        ("dicom/dicom.h", 1),
        ("mobile/mmt_mobile.h", 5),
        ("business_app/mmt_business_app.h", 1),
    ]
    assert profile.parents.ids[1].not_ids == ("PROTO_DICOM_HDRLEN",)
    assert profile.parents.id_of("PROTO_DICOM") == 701
    assert [(p.macro, p.id) for p in profile.parents.ids[2].protocols] == [
        ("PROTO_S1AP", 900),
        ("PROTO_DIAMETER", 901),
        ("PROTO_GTPV2", 902),
        ("PROTO_NGAP", 903),
        ("PROTO_NAS5G", 904),
    ]
    protocols = profile.parents.protocols()
    assert len(protocols) == 677
    assert [p.id for p in protocols] == sorted(p.id for p in protocols)
    # The registered names (F2), where they are not the macro's suffix.
    renamed = {
        p.macro: p.alias
        for p in protocols
        if p.alias is not None and p.alias != p.macro.removeprefix("PROTO_").lower()
    }
    assert renamed == {
        "PROTO_GROOVESHARK": "groovesharks",
        "PROTO_HTTP_APPLICATION_ACTIVESYNC": "http_activesync",
        "PROTO_APPLE_ICLOUD": "icloud",
        "PROTO_UNENCRYPED_JABBER": "jabber",
        "PROTO_NAS5G": "nas_5g",
        "PROTO_IPS_DATA": "lps_data",
    }
    # tcpip/mmt_tcpip_protocols.h defines no PROTO_INT*_ALIAS.
    assert [p.macro for p in protocols if p.alias is None] == ["PROTO_INT", "PROTO_INT_REPORT"]
    assert all(profile.parents.id_of(name) is not None for name in profile.parents.examples)
    for lookup in (profile.callback, profile.function, profile.struct, profile.constant):
        with pytest.raises(KeyError):
            lookup("nothing")


def test_the_sdk_names_of_the_java_output_and_the_corpus(profile: Profile) -> None:
    # Used by legacy/reference-output/, the example sources and the corpus
    # models (review of PR #49, F1).
    assert [t.header for t in profile.types if t.name == "mac_addr_t"] == ["types_defs.h"]
    layout = {c.name: c.header for c in profile.constants if c.group == "data_len_or_offset"}
    assert layout == {
        "POSITION_NOT_KNOWN": "mmt_core.h",
        "IPv6_ALEN": "types_defs.h",
        "BINARY_64DATA_TYPE_LEN": "types_defs.h",
    }
    fields = {f.name: f.type for f in profile.struct("ipacket_t").fields}
    assert fields["packet_id"] == "uint64_t"
    assert profile.function("hex2int").header == "mmt_utils.h"
    assert profile.function("str_hex2int_n").function_type == "int (char *, size_t, int, int)"


def test_deprecated_and_missing_sdk_functions_are_not_listed(profile: Profile) -> None:
    names = {f.name for f in (*profile.registrations, *profile.helpers)}
    # Deprecated in 1.10.2, and the Java generator's call that does not exist.
    assert "general_short_extraction" not in names
    assert "str_hex2int" not in names
    assert "register_proto_context_cleanup_function" not in names
    assert "register_proto_context_init_cleanup_function" in names


def test_params_are_declarable() -> None:
    assert Param("x", "int").declaration == "int x"
    assert Param("p", "char *").declaration == "char *p"


def test_version_key() -> None:
    assert version_key("1.10.2") == (1, 10, 2)
    assert version_key("1.10.0") == version_key("1.10") == (1, 10)
    assert version_key("0") == (0,)
    assert version_key("1.10.2") > version_key("1.9.9")
    for bad in ("", "1.", "v1.10", "1.10.2-rc1"):
        with pytest.raises(ValueError):
            version_key(bad)


def test_load_profile_from_a_file(tmp_path: Path) -> None:
    path = tmp_path / "p.json"
    path.write_text(json.dumps(_raw()))
    assert load_profile(path) == get_bundled("1.10.2")
    path.write_text("{")
    with pytest.raises(ProfileError, match="not JSON"):
        load_profile(path)
    with pytest.raises(ProfileError, match="No such file"):
        load_profile(tmp_path / "missing.json")


Mutation = Callable[[dict[str, Any]], object]


def _cb(d: dict[str, Any], role: str) -> dict[str, Any]:
    found: dict[str, Any] = next(c for c in d["callbacks"] if c["role"] == role)
    return found


def _const(d: dict[str, Any], name: str) -> dict[str, Any]:
    found: dict[str, Any] = next(c for c in d["constants"] if c["name"] == name)
    return found


def _ids(d: dict[str, Any], index: int = 0) -> dict[str, Any]:
    """One header of ``parents.ids`` (0: tcpip/mmt_tcpip_protocols.h)."""
    found: dict[str, Any] = d["parents"]["ids"][index]
    return found


def _tcp(d: dict[str, Any]) -> dict[str, Any]:
    found: dict[str, Any] = _ids(d)["protocols"]["PROTO_TCP"]
    return found


#: Invalid profiles that both the schema and the loader reject.
SCHEMA_ERRORS: dict[str, tuple[Mutation, str]] = {
    "schema version": (lambda d: d.update(schema_version=2), "schema_version"),
    "unknown key": (lambda d: d.update(extra=1), "unknown key 'extra'"),
    "missing key": (lambda d: d.pop("logger"), "missing key 'logger'"),
    "bad version": (lambda d: d.update(profile="1.10.x"), "profile"),
    "bad header": (lambda d: d["headers"][0].update(name="../x.h"), "name"),
    "array param": (
        lambda d: _cb(d, "init_proto")["params"].append({"name": "a", "type": "int [2]"}),
        "array declarator",
    ),
    "bad layout": (lambda d: d["structs"][0].update(layout="some"), "layout"),
    "no fields": (lambda d: d["structs"][0].update(fields=[]), "at least one field"),
    "empty doc": (lambda d: d["types"][0].update(doc=" "), "non-empty"),
    "bad id macro": (lambda d: d["parents"].update(id_macro="PROTO_"), "LABEL"),
    "id macro starts with label": (
        lambda d: d["parents"].update(id_macro="{LABEL}_ID"),
        "LABEL",
    ),
    "id macro with two labels": (
        lambda d: d["parents"].update(id_macro="P_{LABEL}{LABEL}"),
        "LABEL",
    ),
    "boolean schema version": (lambda d: d.update(schema_version=True), "schema_version"),
    "other sdk": (lambda d: d.update(sdk="other"), "'other' is not 'mmt-dpi'"),
    "not an object": (lambda d: d["types"].__setitem__(0, "x"), "expected an object"),
    "not an array": (lambda d: d.update(helpers={}), "expected an array"),
    "string value": (
        lambda d: _const(d, "Max_Alias_Len").update(value="64"),
        "expected an integer",
    ),
    "fractional value": (lambda d: _const(d, "Max_Alias_Len").update(value=64.5), "an integer"),
    "boolean value": (lambda d: _const(d, "Max_Alias_Len").update(value=True), "an integer"),
    "ids not an array": (lambda d: d["parents"].update(ids={}), "expected an array"),
    "ids item not an object": (lambda d: d["parents"].update(ids=[1]), "expected an object"),
    "ids without doc": (lambda d: _ids(d).pop("doc"), "missing key 'doc'"),
    "ids unknown key": (lambda d: _ids(d).update(library="x"), "unknown key 'library'"),
    "protocols not an object": (lambda d: _ids(d).update(protocols=[]), "expected an object"),
    "id not a name": (
        lambda d: _ids(d)["protocols"].update({"1x": {"id": 3}}),
        "not a C identifier",
    ),
    "bare id": (lambda d: _tcp(d).clear(), "missing key 'id'"),
    "id not an object": (
        lambda d: _ids(d)["protocols"].update(PROTO_TCP=354),
        "expected an object",
    ),
    "negative id": (lambda d: _tcp(d).update(id=-1), "expected a non-negative integer"),
    "string id": (lambda d: _tcp(d).update(id="354"), "expected a non-negative integer"),
    "empty alias": (lambda d: _tcp(d).update(alias=""), "non-empty"),
    "quoted alias": (lambda d: _tcp(d).update(alias='t"cp'), "quote"),
    "not_ids not a name": (lambda d: _ids(d, 1).update(not_ids=["1x"]), "C identifier"),
}

#: Invalid profiles only the loader can see (cross-references).
LOADER_ERRORS: dict[str, tuple[Mutation, str]] = {
    "unlisted header": (lambda d: d["types"][0].update(header="other.h"), "not in headers"),
    "duplicate symbol": (lambda d: d["helpers"].append(d["helpers"][0]), "listed twice"),
    "duplicate header": (lambda d: d["headers"].append(d["headers"][0]), "listed twice"),
    "duplicate role": (
        lambda d: d["callbacks"].append({**d["callbacks"][0], "typedef": "other_t"}),
        "listed twice",
    ),
    "duplicate field": (
        lambda d: d["structs"][0]["fields"].append(d["structs"][0]["fields"][0]),
        "listed twice",
    ),
    "unknown role": (lambda d: d["helpers"][3].update(implements="nope"), "not a callback role"),
    "logger macro": (lambda d: d["logger"].update(warn="mmt_log_fatal"), "logger.warn"),
    "class provider": (
        lambda d: d["class_provider"].update(unknown="Classified"),
        "class_provider.unknown",
    ),
    "duplicate id": (
        lambda d: _ids(d)["protocols"].update(PROTO_NEW={"id": 354}),
        "PROTO_NEW and PROTO_TCP are both 354",
    ),
    "duplicate id across headers": (
        lambda d: _ids(d, 1)["protocols"].update(PROTO_NEW={"id": 354}),
        "PROTO_NEW and PROTO_TCP are both 354",
    ),
    "duplicate macro across headers": (
        lambda d: _ids(d, 1)["protocols"].update(PROTO_TCP={"id": 7000}),
        "macro 'PROTO_TCP' is listed twice",
    ),
    "duplicate alias": (
        lambda d: _ids(d, 1)["protocols"].update(PROTO_NEW={"id": 7000, "alias": "TCP"}),
        "alias 'tcp' is listed twice",
    ),
    "duplicate ids header": (
        lambda d: d["parents"]["ids"].append(copy.deepcopy(_ids(d, 3))),
        "header 'business_app/mmt_business_app.h' is listed twice",
    ),
}


@pytest.mark.parametrize("name", sorted(SCHEMA_ERRORS))
def test_schema_and_loader_reject_the_same_profiles(name: str) -> None:
    mutate, message = SCHEMA_ERRORS[name]
    data = copy.deepcopy(_raw())
    mutate(data)
    assert not Draft202012Validator(load_schema()).is_valid(data)
    with pytest.raises(ProfileError, match=message):
        parse_profile(data)


@pytest.mark.parametrize("name", sorted(LOADER_ERRORS))
def test_the_loader_checks_cross_references(name: str) -> None:
    mutate, message = LOADER_ERRORS[name]
    data = copy.deepcopy(_raw())
    mutate(data)
    with pytest.raises(ProfileError, match=message):
        parse_profile(data)


def test_parent_ids_are_optional() -> None:
    data = copy.deepcopy(_raw())
    del data["parents"]["ids"]
    assert Draft202012Validator(load_schema()).is_valid(data)
    assert parse_profile(data).parents.ids == ()


def test_a_constant_value_is_optional() -> None:
    schema = Draft202012Validator(load_schema())
    data = copy.deepcopy(_raw())
    _const(data, "Max_Alias_Len").pop("value")
    assert schema.is_valid(data)
    assert parse_profile(data).constant("Max_Alias_Len").value is None
    # JSON Schema's integer includes 64.0, so the loader takes it as 64.
    _const(data, "Max_Alias_Len")["value"] = 64.0
    assert schema.is_valid(data)
    assert parse_profile(data).constant("Max_Alias_Len").value == 64
    _const(data, "Max_Alias_Len")["value"] = -1
    assert schema.is_valid(data)
    assert parse_profile(data).constant("Max_Alias_Len").value == -1


def test_the_profile_is_frozen(profile: Profile) -> None:
    with pytest.raises(AttributeError):
        profile.version = "2"  # type: ignore[misc]
