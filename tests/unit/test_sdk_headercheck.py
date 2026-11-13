"""Tests for ``mmt_plugin.sdk.headercheck``. The check of the bundled profile
against the real mmt-dpi 1.10.2 headers runs in CI (job ``sdk-profile``);
here the checker itself is tested on a small stub SDK, compiled when a C
compiler is installed."""

from __future__ import annotations

import copy
import json
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from mmt_plugin.sdk import headercheck
from mmt_plugin.sdk.detect import Sdk, SdkSource
from mmt_plugin.sdk.headercheck import check_profile, declared_names, render_unit
from mmt_plugin.sdk.profile import Profile, get_bundled, parse_profile

CC = shutil.which("gcc") or shutil.which("cc")
needs_cc = pytest.mark.skipif(CC is None, reason="no C compiler")

STUB_HEADER = """\
/* stub.h: a tiny SDK for the checker's own tests. */
#ifndef STUB_H
#define STUB_H
#include <stdbool.h>
typedef unsigned idx_t;
typedef struct opaque_struct opaque_t;
typedef struct row_struct { int id; char alias[4 + 1]; } row_t;
typedef struct view_struct { int hidden; const unsigned char *data; } view_t;
typedef int (*cb_t)(const opaque_t *o, idx_t i);
bool reg(cb_t f, int weight);
int helper(const opaque_t *o, idx_t i);
int old_helper(const opaque_t *o, idx_t i) __attribute__((deprecated("gone")));
#define K_ONE 1
enum { K_TWO = 2 };
typedef struct cp_struct { int (*klass)(idx_t); } cp_t;
bool cp_register(const cp_t *p);
#define CP_UNKNOWN 0
#define log_e(...) ((void)0)
#define log_w(...) ((void)0)
#define log_i(...) ((void)0)
#ifdef STUB_DEBUG_ON
void stub_log(const char *fmt, ...) __attribute__((format(printf, 1, 2)));
#define log_d(...) stub_log(__VA_ARGS__)
#else
#define log_d(...) ((void)0)
#endif
#define PROTO_TCP 354
#endif
"""


def _fn(name: str, returns: str, params: list[tuple[str, str]], **extra: str) -> dict[str, Any]:
    return {
        "name": name,
        "header": "stub.h",
        "returns": returns,
        "params": [{"name": n, "type": t} for n, t in params],
        "doc": name,
        **extra,
    }


def _stub_data() -> dict[str, Any]:
    def entry(name: str, **extra: Any) -> dict[str, Any]:
        return {"name": name, "header": "stub.h", "doc": name, **extra}

    return {
        "schema_version": 1,
        "profile": "1.10.2",
        "sdk": "mmt-dpi",
        "c_std": "gnu11",
        "headers": [{"name": "stub.h", "doc": "the stub"}],
        "types": [entry("idx_t", definition="unsigned"), entry("opaque_t")],
        "structs": [
            entry(
                "row_t",
                layout="complete",
                fields=[{"name": "id", "type": "int"}, {"name": "alias", "type": "char [5]"}],
            ),
            entry(
                "view_t",
                layout="partial",
                fields=[{"name": "data", "type": "const unsigned char *"}],
            ),
            entry("cp_t", layout="complete", fields=[{"name": "klass", "type": "int (*)(idx_t)"}]),
        ],
        "callbacks": [
            {
                "role": "cb",
                "typedef": "cb_t",
                "header": "stub.h",
                "returns": "int",
                "params": [
                    {"name": "o", "type": "const opaque_t *"},
                    {"name": "i", "type": "idx_t"},
                ],
                "doc": "cb",
            }
        ],
        "registrations": [
            _fn("reg", "bool", [("f", "cb_t"), ("weight", "int")]),
            _fn("cp_register", "bool", [("p", "const cp_t *")]),
        ],
        "helpers": [
            _fn("helper", "int", [("o", "const opaque_t *"), ("i", "idx_t")], implements="cb")
        ],
        "constants": [
            entry("K_ONE", group="k"),
            entry("K_TWO", group="k"),
            entry("CP_UNKNOWN", group="cp"),
        ],
        "macros": [entry(m) for m in ("log_e", "log_w", "log_i", "log_d")],
        "logger": {
            "header": "stub.h",
            "error": "log_e",
            "warn": "log_w",
            "info": "log_i",
            "debug": "log_d",
            "debug_opt_in": "STUB_DEBUG_ON",
            "doc": "logger",
        },
        "class_provider": {
            "header": "stub.h",
            "struct": "cp_t",
            "register": "cp_register",
            "unknown": "CP_UNKNOWN",
            "doc": "cp",
        },
        "parents": {
            "header": "stub.h",
            "declared_in": "stub.h",
            "id_macro": "PROTO_{LABEL}",
            "examples": ["PROTO_TCP"],
            "doc": "parents",
        },
    }


@pytest.fixture
def stub_sdk(tmp_path: Path) -> Sdk:
    include = tmp_path / "dpi" / "include"
    include.mkdir(parents=True)
    (include / "stub.h").write_text(STUB_HEADER)
    (include / "mmt_log.h").write_text("/* the marker of an SDK prefix */\n")
    (include / "mmt_core.h").write_text('#define VERSION "1.10.2"\n')
    return Sdk(str(tmp_path), SdkSource.CLI, "1.10.2")


def _failures(profile: Profile, sdk: Sdk) -> list[str]:
    assert CC is not None
    return [f"{r.name}\n{r.detail}" for r in check_profile(profile, sdk, CC) if not r.ok]


@needs_cc
def test_a_matching_profile_passes(stub_sdk: Sdk) -> None:
    results = check_profile(parse_profile(_stub_data()), stub_sdk, CC or "cc")
    assert [r.name for r in results if not r.ok] == []
    # version, declared names, the unit, the unit again with the debug opt-in
    assert len(results) == 4
    assert results[-1].name.endswith("-DSTUB_DEBUG_ON)")


Mutation = Callable[[dict[str, Any]], object]

MUTATIONS: dict[str, tuple[Mutation, str]] = {
    "callback param": (
        lambda d: d["callbacks"][0]["params"][1].update(type="int"),
        "callbacks.cb: cb_t is not int (*)(const opaque_t *, int)",
    ),
    "callback return": (
        lambda d: d["callbacks"][0].update(returns="long"),
        "callbacks.cb: cb_t is not long",
    ),
    "registration param": (
        lambda d: d["registrations"][0]["params"][1].update(type="unsigned"),
        "registrations.reg is not bool (cb_t, unsigned)",
    ),
    "helper does not implement": (
        lambda d: d["helpers"][0]["params"][1].update(type="int"),
        "helpers.helper is not int (const opaque_t *, int)",
    ),
    "deprecated helper": (
        lambda d: d["helpers"][0].update(name="old_helper"),
        "deprecated",
    ),
    "typedef definition": (
        lambda d: d["types"][0].update(definition="int"),
        "types.idx_t is not int",
    ),
    "missing struct field": (
        lambda d: d["structs"][0]["fields"].pop(),
        "structs.row_t has fields that the profile does not list",
    ),
    "swapped struct fields": (
        lambda d: d["structs"][0]["fields"].reverse(),
        "structs.row_t.alias is not at its place",
    ),
    "partial field type": (
        lambda d: d["structs"][1]["fields"][0].update(type="char *"),
        "structs.view_t.data is not char *",
    ),
    "unknown constant": (
        lambda d: d["constants"].append({**d["constants"][0], "name": "K_NONE"}),
        "not declared there: K_NONE",
    ),
    "unknown macro": (
        lambda d: d["macros"].append({**d["macros"][0], "name": "log_f"}),
        "macros.log_f is not defined",
    ),
    "unknown parent": (
        lambda d: d["parents"].update(examples=["PROTO_SCTP"]),
        "not declared there: PROTO_SCTP",
    ),
    "unknown version": (lambda d: d.update(profile="1.11.0"), "profile 1.11.0 is the SDK version"),
}


@needs_cc
@pytest.mark.parametrize("name", sorted(MUTATIONS))
def test_a_wrong_profile_fails(stub_sdk: Sdk, name: str) -> None:
    mutate, message = MUTATIONS[name]
    data = copy.deepcopy(_stub_data())
    mutate(data)
    failures = _failures(parse_profile(data), stub_sdk)
    assert failures, f"{name}: no check failed"
    assert any(message in f for f in failures), failures


def test_render_unit_of_the_bundled_profile() -> None:
    profile = get_bundled("1.10.2")
    assert profile is not None
    unit = render_unit(profile, "plugin_defs.h")
    assert '#include "plugin_defs.h"' in unit
    assert (
        "_Static_assert(__builtin_types_compatible_p(generic_attribute_extraction_function,"
        " int (*)(const ipacket_t *, mmt_proto_index_t, attribute_t *))"
    ) in unit
    assert "__typeof__(register_protocol), bool (protocol_t *, mmt_proto_id_t))" in unit
    assert "struct mmtp_chk_mirror_attribute_metadata_t {" in unit
    lib = render_unit(profile, "extraction_lib.h")
    assert '#include "plugin_defs.h" /* for a callback typedef */' in lib
    assert "__typeof__(&general_char_extraction), generic_attribute_extraction_function" in lib
    assert "void mmtp_chk_logger(int value)" in render_unit(profile, "mmt_log.h")
    assert "PROTO_TCP" in render_unit(profile, "tcpip/mmt_tcpip.h")


def test_declared_names_cover_every_entry() -> None:
    profile = get_bundled("1.10.2")
    assert profile is not None
    names = declared_names(profile)
    flat = {n for ns in names.values() for n in ns}
    assert "get_packet_offset_at_index" in names["data_defs.h"]
    assert "MMT_LOG_ENABLE_DEBUG" in names["mmt_log.h"]
    assert names["tcpip/mmt_tcpip_protocols.h"] == [
        "PROTO_ETHERNET",
        "PROTO_IP",
        "PROTO_TCP",
        "PROTO_UDP",
    ]
    expected = {
        *(t.name for t in profile.types),
        *(s.name for s in profile.structs),
        *(c.typedef for c in profile.callbacks),
        *(f.name for f in (*profile.registrations, *profile.helpers)),
        *(c.name for c in profile.constants),
        *(m.name for m in profile.macros),
    }
    assert expected <= flat


def test_missing_headers_and_compiler(tmp_path: Path) -> None:
    sdk = Sdk(str(tmp_path), SdkSource.CLI, "1.10.2")
    results = check_profile(parse_profile(_stub_data()), sdk, str(tmp_path / "no-cc"))
    failed = {r.name: r.detail for r in results if not r.ok}
    assert "stub.h: exists" in failed
    assert any("cannot run" in d for d in failed.values())


def test_main_exit_codes(
    tmp_path: Path,
    make_prefix: Callable[..., Path],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("MMT_BASE", str(tmp_path / "missing"))
    assert headercheck.main([]) == 4
    assert "FAIL: MMT_BASE" in capsys.readouterr().out
    prefix = make_prefix(tmp_path / "p", version="9.9")
    assert headercheck.main(["--sdk", str(prefix)]) == 4
    assert "no profile is bundled for the SDK's version (9.9)" in capsys.readouterr().out
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"schema_version": 1}))
    assert headercheck.main(["--sdk", str(prefix), "--profile", str(bad)]) == 1
    assert "missing key" in capsys.readouterr().out


@needs_cc
def test_main_prints_one_line_per_check(
    stub_sdk: Sdk, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    good = tmp_path / "stub.json"
    good.write_text(json.dumps(_stub_data()))
    args = ["--sdk", stub_sdk.prefix, "--profile", str(good), "--cc", CC or "cc"]
    assert headercheck.main(args) == 0
    out = capsys.readouterr().out.splitlines()
    assert out[0].startswith(f"SDK {stub_sdk.prefix} (--sdk), version 1.10.2; profile 1.10.2")
    assert all(line.startswith("PASS: ") for line in out[1:-1])
    assert out[-1] == "4 passed, 0 failed"
    data = _stub_data()
    data["callbacks"][0]["returns"] = "long"
    good.write_text(json.dumps(data))
    assert headercheck.main(args) == 1
    text = capsys.readouterr().out
    assert "FAIL: stub.h: entries compile" in text and "callbacks.cb: cb_t is not long" in text
