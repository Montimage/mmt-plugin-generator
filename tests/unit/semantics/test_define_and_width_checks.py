"""The checks of #53: a define named like an SDK macro
(``model.define-sdk-name``) and a data_len that is not a fixed-width type's
width (``model.data-len-width``)."""

from __future__ import annotations

import pytest

from mmt_plugin.diagnostics import Severity

from .conftest import attr, build, codes, covered, ok, run, u8

# --- model.define-sdk-name ----------------------------------------------------

#: Ethernet's defines, as the Java tool's example model has them
#: (tests/corpus/models/ethernet/model.pdl, which does not parse as a whole).
ETHERNET_DEFINES = (
    "\tdefine ETH_P_IP = 0x0800\n"
    "\tdefine PROTO_ARP = 11\n"
    "\tdefine PROTO_IP = 15\n"
    "\tdefine PROTO_IP6 = 16\n"
)


def test_ethernets_proto_ip_is_an_error_that_names_the_sdk_header() -> None:
    text = build(u8("a", "0"), defines=ETHERNET_DEFINES)
    analysed, diagnostics = run(text)
    assert analysed is None
    found = [d for d in diagnostics if d.code == "model.define-sdk-name"]
    # PROTO_IP6 is no SDK macro (mmt-dpi's is PROTO_IPV6), ETH_P_IP neither.
    assert [covered(text, d.location) for d in found] == ["PROTO_ARP", "PROTO_IP"]
    assert all(d.severity is Severity.ERROR for d in found)
    proto_ip = found[1]
    assert "PROTO_IP (= 178)" in proto_ip.message
    assert "redefine" in proto_ip.message
    assert proto_ip.hint is not None and "name PROTO_IP directly" in proto_ip.hint
    (related,) = proto_ip.related
    assert related.message == (
        "PROTO_IP is declared in tcpip/mmt_tcpip_protocols.h (SDK profile 1.10.2)"
    )


@pytest.mark.parametrize(
    ("name", "kind", "header"),
    [
        ("mmt_log_error", "macro", "mmt_log.h"),
        ("MMT_LOG_ENABLE_DEBUG", "macro", "mmt_log.h"),
        ("MMT_U8_DATA", "constant", "types_defs.h"),
        ("Max_Alias_Len", "constant", "data_defs.h"),
        ("PROTO_UNKNOWN", "protocol macro", "proto_meta.h"),
        ("mac_addr_t", "type", "types_defs.h"),
    ],
)
def test_every_kind_of_recorded_sdk_name_is_checked(name: str, kind: str, header: str) -> None:
    text = build(u8("a", "0"), defines=f"\tdefine {name} = 1\n")
    _, diagnostics = run(text)
    assert codes(diagnostics) == ["model.define-sdk-name"]
    (d,) = diagnostics
    assert f"the SDK {kind} {name}" in d.message
    assert d.related[0].message.startswith(f"{name} is declared in {header} ")
    if kind != "protocol macro":
        assert d.hint == "rename the define"


def test_the_check_is_case_sensitive_like_c() -> None:
    ok(build(u8("a", "0"), defines="\tdefine proto_ip = 15\n\tdefine Mmt_U8_Data = 1\n"))


def test_a_define_differing_only_in_case_does_not_change_the_sdk_macro() -> None:
    # PDL names are case-insensitive, but PROTO_IP named exactly is the
    # SDK's, not the define proto_ip's.
    text = build(
        u8("k", "0"),
        properties='label = "p"\n\t\tid = "960"\n\t\tencapsulation = "true"',
        defines="\tdefine proto_ip = 15\n\tdefine NEXT_IP = PROTO_IP\n\tdefine OWN = PROTO_ip\n",
    )
    analysed = ok(text)
    values = {d.name: (d.value, d.alias_of) for d in analysed.defines}
    assert values["NEXT_IP"] == (178, "PROTO_IP")
    assert values["OWN"] == (15, "proto_ip")


def test_naming_the_sdk_macro_without_a_define_is_still_fine() -> None:
    text = build(
        u8("k", "0"),
        properties='label = "p"\n\t\tid = "960"\n\t\tencapsulation = "true"',
        defines="\tdefine NEXT_IP = PROTO_IP\n",
    ).replace(
        "\t}\n}\n",
        "\t}\n\tclassifynext {\n\t\tswitch(val(k)) {\n\t\t\tcase 4: nextencaps = NEXT_IP"
        " nextoffset = 1 break\n\t\t\tcase 6: nextencaps = PROTO_IP nextoffset = 1 break"
        "\n\t\t\tdefault: break\n\t\t}\n\t}\n}\n",
    )
    analysed = ok(text)
    assert (analysed.defines[0].value, analysed.defines[0].alias_of) == (178, "PROTO_IP")


# --- model.data-len-width -----------------------------------------------------


def _attribute(data_type: str, data_len: str, offset: str | None = "0") -> str:
    where = "" if offset is None else f' offset="{offset}"'
    return attr(f'alias="a" data_type="{data_type}" data_len="{data_len}"{where} scope="packet"')


@pytest.mark.parametrize(
    ("data_type", "width", "data_len", "effect"),
    [
        ("MMT_U8_DATA", 1, 2, "its value is stored in 1 byte, so the high bytes would be lost"),
        ("MMT_U16_DATA", 2, 4, "its value is stored in 2 bytes, so the high bytes would be lost"),
        ("MMT_U16_DATA", 2, 1, "the value is read from 1 byte into a 2-byte integer"),
        ("MMT_U32_DATA", 4, 3, "the value is read from 3 bytes into a 4-byte integer"),
        ("MMT_U32_DATA", 4, 8, "its value is stored in 4 bytes, so the high bytes would be lost"),
        ("MMT_U64_DATA", 8, 6, "the value is read from 6 bytes into a 8-byte integer"),
        (
            "MMT_DATA_MAC_ADDR",
            6,
            4,
            "only 4 of its 6 bytes come from the packet, the rest are zeros",
        ),
        ("MMT_DATA_IP_ADDR", 4, 8, "only the first 4 bytes of the 8 read are kept"),
    ],
)
def test_a_data_len_other_than_the_width_is_a_warning_naming_both(
    data_type: str, width: int, data_len: int, effect: str
) -> None:
    text = build(_attribute(data_type, str(data_len)))
    analysed, diagnostics = run(text)
    assert analysed is not None
    assert codes(diagnostics) == ["model.data-len-width"]
    (d,) = diagnostics
    assert d.severity is Severity.WARNING
    width_text = "1 byte" if width == 1 else f"{width} bytes"
    assert d.message == (
        f"`a` has data_len {data_len}, but {data_type} is {width_text} wide: {effect}"
    )
    assert covered(text, d.location) == str(data_len)
    assert d.hint is not None and f"give data_len {width}" in d.hint


@pytest.mark.parametrize(
    ("data_type", "data_len"),
    [
        ("MMT_U8_DATA", "1"),
        ("MMT_U16_DATA", "2"),
        ("MMT_U32_DATA", "sizeof(uint32_t)"),
        ("MMT_U64_DATA", "8"),
        ("MMT_DATA_MAC_ADDR", "6"),
        ("MMT_BINARY_DATA", "3"),
        ("MMT_DATA_POINTER", "8"),
    ],
)
def test_the_types_width_or_a_type_without_one_is_fine(data_type: str, data_len: str) -> None:
    ok(build(_attribute(data_type, data_len)))


def test_a_folded_data_len_is_compared_too() -> None:
    _, diagnostics = run(build(_attribute("MMT_U32_DATA", "sizeof(uint16_t) + 1")))
    assert codes(diagnostics) == ["model.data-len-width"]


def test_a_data_len_known_only_per_packet_is_not_checked() -> None:
    text = build(u8("n", "0") + _attribute("MMT_U32_DATA", "val(n)", offset="1"))
    analysed, diagnostics = run(text)
    assert analysed is not None
    assert codes(diagnostics) == []


def test_a_user_hooks_data_len_is_not_checked() -> None:
    # Without an offset the attribute is a user hook, which stores its value
    # itself; its data_len only places what follows.
    analysed, diagnostics = run(build(_attribute("MMT_U32_DATA", "3", offset=None)))
    assert analysed is not None
    assert codes(diagnostics) == []
