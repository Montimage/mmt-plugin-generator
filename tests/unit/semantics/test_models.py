"""Every ``plugins/*_plugin`` and corpus model the parser accepts, analysed.

Each model is clean, gives warnings, or gives errors; the table records which,
with the codes, and says why for every one that is not clean. The corpus
copies of the examples are byte-identical to ``plugins/`` (tests/corpus/
validate.py), so they give the same result.

Most examples collide with mmt-dpi 1.10.2, whose package installs
libmmt_tcpip, libmmt_tdicom, libmmt_tmobile and libmmt_business_app: they
re-implement protocols that libmmt_tcpip already has (dns, tcp, ip, arp,
radius, quic), or were upstreamed into it (the SDK has tpkt as 637, cotp as
638 and s7comm as 639, while the models use 636, 637 and 638, which are
PROTO_LOOPBACK's, PROTO_TPKT's and PROTO_COTP's), and their ids were picked
before the third-party range existed (plan decision 5, inventory bug 23).
Those errors are SDK conflicts (``SDK_CONFLICT_CODES``): like any error they
withhold the model, which ``allow_sdk_conflicts=True`` still returns.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mmt_plugin.pdl import PdlSyntaxError, parse
from mmt_plugin.semantics import SDK_CONFLICT_CODES, analyse

from .conftest import profile

ROOT = Path(__file__).parents[3]

ID = "model.id-taken"
NAME = "model.name-taken"

#: Per model: the diagnostic codes, sorted as reported, and why.
EXPECTED: dict[str, tuple[list[str], str]] = {
    "abb": ([ID], "bug 23: id 658 is PROTO_INT"),
    "arp": (
        [NAME, ID, "model.duplicate-name"],
        "arp is PROTO_ARP (id 30, its own id); ar_pro is declared twice, in arphdr and in the "
        "else branch (bug 12, corpus: invalid)",
    ),
    "cam": ([ID], "bug 23: id 700 is PROTO_HTTP2"),
    "cotp": ([NAME, ID], "bug 23: COTP is PROTO_COTP (638) and 637 is PROTO_TPKT"),
    "cpm": ([ID], "bug 23: id 701 is PROTO_DICOM (libmmt_tdicom, dicom/dicom.h)"),
    "dns": ([NAME, ID], "bug 23: DNS is PROTO_DNS (85) and 11 is PROTO_ADDTHIS"),
    "ip": ([NAME, ID], "bug 23: IP is PROTO_IP (178) and 12 is PROTO_ADF"),
    "ndn": ([], "clean: NDN_EXAMPLE, id 980"),
    "quic": ([NAME, ID], "bug 23: QUIC is PROTO_QUIC (627) and 630 is PROTO_VMWARE"),
    "radius": ([NAME, ID], "bug 23: RADIUS is PROTO_RADIUS (288) and 11 is PROTO_ADDTHIS"),
    "s7com": ([NAME, ID], "bug 23: S7COMM is PROTO_S7COMM (639) and 638 is PROTO_COTP"),
    "tcp": ([NAME, ID], "bug 23: TCP is PROTO_TCP (354) and 19 is PROTO_ALIPAY"),
    "topo_ind_sch": ([ID], "bug 23: id 500 is PROTO_NETBLT"),
    "tpkt": ([NAME, ID], "bug 23: TPKT is PROTO_TPKT (637) and 636 is PROTO_LOOPBACK"),
    "pdl_alignment": (
        ["model.branch-offset-mismatch"] * 2,
        "warnings, decision 8: cs0 adds the R of the first if/else (branches end at 7 and 8) "
        "and a2 the R of the second if, which has no else (10, and 8 without the if); the "
        "model exercises exactly that rule",
    ),
    "pdl_bitfields": ([], "clean"),
    "pdl_classifynext": ([], "clean"),
    "pdl_conditionals": ([], "clean"),
    "pdl_defines": ([], "clean"),
    "pdl_encoding_ascii": ([], "clean"),
    "pdl_encoding_host": ([], "clean"),
    "pdl_encoding_unicode": ([], "clean"),
    "pdl_expressions": ([], "clean"),
    "pdl_keyword_names": ([], "clean"),
    "pdl_properties_all": ([], "clean"),
    "pdl_properties_minimal": ([], "clean"),
    "pdl_scopes": (["model.default-scope"], "warning: s_default omits its scope on purpose"),
    "pdl_struct_types": (["model.pointer-field"], "warning: f_ptr is a T* field on purpose"),
    "pdl_types": ([], "clean"),
}

#: The models the parser rejects; nothing to analyse.
UNPARSED = {"ethernet", "mongodb"}


def _models() -> list[tuple[str, Path]]:
    found = [
        (p.name.removesuffix("_plugin"), p) for p in sorted((ROOT / "plugins").glob("*_plugin"))
    ]
    found += [
        (p.parent.name, p)
        for p in sorted((ROOT / "tests" / "corpus" / "models").glob("*/model.pdl"))
    ]
    return found


def test_the_table_covers_every_model() -> None:
    names = {name for name, _ in _models()}
    assert names == set(EXPECTED) | UNPARSED
    assert len(_models()) == 16 + 31


@pytest.mark.parametrize(
    ("name", "path"), _models(), ids=lambda v: v if isinstance(v, str) else str(v.parent.name)
)
def test_model(name: str, path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    filename = str(path.relative_to(ROOT))
    if name in UNPARSED:
        with pytest.raises(PdlSyntaxError):
            parse(text, filename=filename)
        return
    model = parse(text, filename=filename)
    analysed, diagnostics = analyse(model, profile=profile())
    expected, why = EXPECTED[name]
    assert [d.code for d in diagnostics] == expected, why
    errors = {d.code for d in diagnostics if d.severity.value == "error"}
    assert (analysed is None) == bool(errors)
    allowed, again = analyse(model, profile=profile(), allow_sdk_conflicts=True)
    assert again == diagnostics
    if errors - SDK_CONFLICT_CODES:
        assert allowed is None
    else:
        assert allowed is not None
        assert allowed.source.span.file == filename


def test_the_if_else_warning_in_pdl_alignment() -> None:
    path = ROOT / "tests" / "corpus" / "models" / "pdl_alignment" / "model.pdl"
    text = path.read_text(encoding="utf-8")
    _, diagnostics = analyse(parse(text, filename="m"), profile=profile())
    lines = text.splitlines()
    found = []
    for d in diagnostics:
        assert d.location is not None and d.location.line is not None
        name = lines[d.location.line - 1].strip()
        (related,) = d.related
        assert related.location is not None and related.location.line is not None
        found.append((name, related.message, lines[related.location.line - 1].strip()))
    assert found == [
        (
            "struct pdl_align_c {",
            "its then branch ends at 7, its else branch at 8",
            "if (val(a0) == 1) {",
        ),
        (
            'alias="a2" data_type="MMT_U8_DATA" data_len="1" offset="2" scope="SCOPE_PACKET"',
            "its then branch ends at 10; without the if, R is 8",
            "if (val(a0) == 2) {",
        ),
    ]
