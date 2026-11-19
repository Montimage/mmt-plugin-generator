"""The fields tshark dissects in a capture's payloads, for ``mmt-plugin
scaffold --tshark`` (#125).

``dissect(tshark, capture, frames, payloads)`` runs ``tshark -n -r CAPTURE
-c FRAMES -T pdml`` (TCP reassembly off, so each segment is dissected where
it is, and each ``--decode-as`` rule as ``-d``) and reads its PDML as it
streams: for each sliced payload, the protocols that start where its bytes
start, and every field of each one, at its first occurrence, with its
offset from the protocol's start. ``choose`` picks the protocol to draft:
the one asked for, or the only one tshark dissects at the payloads' start
(``data``, tshark's name for bytes it has no dissector for, never counts).

``fields_of(tshark, protocol)`` reads ``tshark -G fields``: each field's
type and bitmask. ``draft`` maps the chosen protocol's fields to the
attributes of a ``Skeleton`` (``mmt_plugin.pcap.skeleton``). A field is
proposed when tshark has it in every dissected payload at the same offset
and length, its bytes are the payload's, and its value is what the
attribute would read:

- an unsigned integer (``FT_UINT8`` to ``FT_UINT64``, ``FT_BOOLEAN``,
  ``FT_CHAR``) whose length is its type's width, in network byte order:
  ``MMT_U8_DATA`` to ``MMT_U64_DATA``;
- one with a bitmask over 1, 2 or 4 bytes, its bits contiguous: a bit field
  of that unit, in a struct ``bits_<offset>`` (``bits_<offset>_<bits>`` for
  a unit wider than a byte); bits the unit's fields leave out before one of
  them are a field ``<struct>_b<bit>`` that the packet tests do not check;
- an IPv4 address, an IPv6 address, a MAC address: ``MMT_DATA_IP_ADDR``,
  ``MMT_DATA_IP6_ADDR``, ``MMT_DATA_MAC_ADDR``;
- anything else with bytes (a string, a byte array, ...) up to 64 bytes:
  ``MMT_BINARY_DATA`` of that length.

Every other field is not proposed, with the reason (``Draft.skipped``):
present in some payloads only, at another offset, a length tshark computes
(``dns.qry.name.len``), a signed or a 3-byte integer, a little-endian
value, no bytes. The attribute's name is the field's without the
protocol's prefix, ``.`` and any other character a C name cannot hold
replaced by ``_`` (``dns.flags.response`` is ``flags_response``).
"""

from __future__ import annotations

import ipaddress
import os
import re
import subprocess
import tempfile
import threading
import xml.etree.ElementTree as ET
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO

from mmt_plugin.diagnostics import CliError
from mmt_plugin.pcap.layers import Payload
from mmt_plugin.pcap.skeleton import Field, Skeleton

__all__ = [
    "BINARY_MAX",
    "NO_DISSECTOR",
    "Dissected",
    "Dissection",
    "Draft",
    "FieldInfo",
    "Occurrence",
    "choose",
    "dissect",
    "draft",
    "field_name",
    "fields_of",
    "parse_fields",
    "parse_pdml",
]

#: The longest byte field proposed (``MMT_BINARY_DATA`` holds 64 bytes).
BINARY_MAX = 64
#: tshark's name for the bytes it has no dissector for.
NO_DISSECTOR = "data"
#: How long one tshark run may take, in seconds.
TIMEOUT = 600

_UNSIGNED = {
    "FT_UINT8": 1,
    "FT_UINT16": 2,
    "FT_UINT24": 3,
    "FT_UINT32": 4,
    "FT_UINT40": 5,
    "FT_UINT48": 6,
    "FT_UINT56": 7,
    "FT_UINT64": 8,
}
_INT_TYPES = {1: "MMT_U8_DATA", 2: "MMT_U16_DATA", 4: "MMT_U32_DATA", 8: "MMT_U64_DATA"}
_ADDRESSES = {"FT_IPv4": 4, "FT_IPv6": 16, "FT_ETHER": 6}
_ADDRESS_TYPES = {
    "FT_IPv4": "MMT_DATA_IP_ADDR",
    "FT_IPv6": "MMT_DATA_IP6_ADDR",
    "FT_ETHER": "MMT_DATA_MAC_ADDR",
}
_NO_VALUE = ("FT_NONE", "FT_PROTOCOL")
#: PDML's pseudo-protocols of every packet.
_SKIPPED_PROTOS = ("geninfo", "frame")
_HEX = re.compile(r"0x[0-9a-fA-F]+")
_NOT_C = re.compile(r"[^0-9A-Za-z_]+")


@dataclass(frozen=True)
class FieldInfo:
    """A field of ``tshark -G fields``: its ``abbrev`` (``dns.flags``), its
    ``type`` (``FT_UINT16``) and its ``bitmask`` (0 for none)."""

    abbrev: str
    type: str
    bitmask: int


@dataclass(frozen=True)
class Occurrence:
    """A field in one packet: its offset from the protocol's start, its
    length, tshark's ``show`` and ``value`` (hex: the bytes, or a bit
    field's value) and, for a bit field, ``unmasked`` (the unit's bytes)."""

    offset: int
    size: int
    show: str
    value: str
    unmasked: str | None


@dataclass
class Dissected:
    """A payload where tshark dissects ``protocol`` from its first byte:
    the first occurrence of each of its fields, by name."""

    payload: Payload
    fields: dict[str, Occurrence]


@dataclass
class Dissection:
    """What ``parse_pdml`` found, per payload (by index): the protocols
    tshark dissects from the payload's first byte, in order, and each one's
    fields."""

    protocols: list[list[str]] = field(default_factory=list)
    fields: list[dict[str, dict[str, Occurrence]]] = field(default_factory=list)


@dataclass(frozen=True)
class Draft:
    """The attributes ``draft`` proposes (a ``Skeleton``), the fields it
    does not (``(abbrev, reason)``), and the payloads it used."""

    skeleton: Skeleton
    skipped: tuple[tuple[str, str], ...]
    payloads: tuple[Payload, ...]


def _clean_env(home: str) -> dict[str, str]:
    """The environment tshark runs in: ``HOME`` and ``XDG_CONFIG_HOME`` an
    empty directory, so that the user's Wireshark profile (preferences,
    decode-as entries, disabled protocols, Lua plugins) does not change the
    draft; ``--decode-as`` says what it must."""
    env = dict(os.environ)
    env["HOME"] = home
    env["XDG_CONFIG_HOME"] = home
    env.pop("WIRESHARK_CONFIG_DIR", None)
    return env


def _run(cmd: Sequence[str], what: str) -> subprocess.CompletedProcess[bytes]:
    try:
        with tempfile.TemporaryDirectory() as home:
            done = subprocess.run(
                list(cmd),
                capture_output=True,
                stdin=subprocess.DEVNULL,
                timeout=TIMEOUT,
                check=False,
                env=_clean_env(home),
            )
    except OSError as exc:
        raise CliError(
            "sdk.tshark-failed",
            f"cannot run {cmd[0]}: {exc.strerror or exc}",
            "check that tshark runs: tshark -v",
        ) from None
    except subprocess.TimeoutExpired:
        raise CliError(
            "sdk.tshark-failed",
            f"tshark did not finish {what} in {TIMEOUT} seconds",
            "lower --max-packets, or cut the capture (editcap -r)",
        ) from None
    if done.returncode != 0:
        _failed(done.returncode, done.stderr, what)
    return done


def _failed(code: int, stderr: bytes, what: str) -> None:
    # The first lines say why (a bad -d rule is followed by every protocol
    # it could name); tshark's warning about running as root does not.
    lines = [
        line.strip()
        for line in stderr.decode("utf-8", "replace").splitlines()
        if line.strip() and not line.startswith("Running as user")
    ][:2]
    raise CliError(
        "sdk.tshark-failed",
        f"tshark failed {what} (exit {code})" + (": " + " / ".join(lines) if lines else ""),
        "run the same tshark command to see why; check each --decode-as rule",
    )


def parse_fields(text: str, protocol: str) -> dict[str, FieldInfo]:
    """The fields of ``protocol`` in ``tshark -G fields`` output: lines
    ``F<TAB>name<TAB>abbrev<TAB>type<TAB>protocol<TAB>...``, the bitmask the
    first ``0x`` column after the protocol (its place changed between
    tshark versions)."""
    out: dict[str, FieldInfo] = {}
    for line in text.splitlines():
        cols = line.split("\t")
        if len(cols) < 5 or cols[0] != "F" or cols[4] != protocol:
            continue
        mask = next((int(c, 16) for c in cols[5:] if _HEX.fullmatch(c)), 0)
        out.setdefault(cols[2], FieldInfo(cols[2], cols[3], mask))
    return out


def fields_of(tshark: str, protocol: str) -> dict[str, FieldInfo]:
    """``parse_fields`` of ``tshark -G fields``."""
    done = _run([tshark, "-G", "fields"], "listing its fields")
    return parse_fields(done.stdout.decode("utf-8", "replace"), protocol)


def _int(text: str | None) -> int | None:
    try:
        return None if text is None else int(text, 10)
    except ValueError:
        return None


def _occurrences(proto: ET.Element, pos: int) -> dict[str, Occurrence]:
    found: dict[str, Occurrence] = {}
    for el in proto.iter("field"):
        name = el.get("name", "")
        at, size = _int(el.get("pos")), _int(el.get("size"))
        if not name or name in found or at is None or size is None:
            continue
        found[name] = Occurrence(
            at - pos, size, el.get("show", ""), el.get("value", ""), el.get("unmaskedvalue")
        )
    return found


def _packet(
    packet: ET.Element, wanted: dict[int, list[int]], payloads: Sequence[Payload], out: Dissection
) -> None:
    number = None
    for el in packet.iter("field"):
        if el.get("name") == "num":
            number = _int(el.get("show"))
            break
    if number is None or number not in wanted:
        return
    protos = [
        (p.get("name", ""), _int(p.get("pos")), p)
        for p in packet.findall("proto")
        if p.get("name", "") not in _SKIPPED_PROTOS and not p.get("name", "").startswith("_ws")
    ]
    for index in wanted[number]:
        payload = payloads[index]
        at = payload.start + payload.cut
        for name, pos, proto in protos:
            if pos == at and name not in out.fields[index]:
                out.protocols[index].append(name)
                out.fields[index][name] = _occurrences(proto, at)


def parse_pdml(stream: IO[bytes], payloads: Sequence[Payload]) -> Dissection:
    """The protocols and fields of ``payloads`` in tshark's PDML, read as it
    streams (each packet is dropped once read)."""
    wanted: dict[int, list[int]] = {}
    for i, p in enumerate(payloads):
        wanted.setdefault(p.frame, []).append(i)
    out = Dissection([[] for _ in payloads], [{} for _ in payloads])
    try:
        for _, el in ET.iterparse(stream, events=("end",)):
            if el.tag == "packet":
                _packet(el, wanted, payloads, out)
                el.clear()
    except ET.ParseError as exc:
        raise CliError(
            "sdk.tshark-failed",
            f"tshark's PDML output does not parse: {exc}",
            "run tshark -T pdml on the capture to see why",
        ) from None
    return out


def dissect(
    tshark: str,
    capture: Path,
    frames: int,
    payloads: Sequence[Payload],
    decode_as: Sequence[str] = (),
) -> Dissection:
    """``parse_pdml`` of ``tshark -T pdml`` on the first ``frames`` frames of
    ``capture`` (those ``slice_payloads`` read)."""
    cmd = [tshark, "-n", "-r", str(capture), "-c", str(frames), "-T", "pdml"]
    cmd += ["-o", "tcp.desegment_tcp_streams:FALSE"]
    for rule in decode_as:
        cmd += ["-d", rule]
    what = f"dissecting {capture.name}"
    timeout = CliError(
        "sdk.tshark-failed",
        f"tshark did not finish {what} in {TIMEOUT} seconds",
        "lower --max-packets, or cut the capture (editcap -r)",
    )
    with tempfile.TemporaryFile() as err, tempfile.TemporaryDirectory() as home:
        try:
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=err,
                env=_clean_env(home),
            )
        except OSError as exc:
            raise CliError(
                "sdk.tshark-failed",
                f"cannot run {tshark}: {exc.strerror or exc}",
                "check that tshark runs: tshark -v",
            ) from None
        assert proc.stdout is not None
        # A tshark that hangs while it streams is killed: the PDML then ends,
        # often in the middle of a packet. ``timed_out`` records that the
        # timer killed it, whatever that truncated output then does.
        timed_out = threading.Event()

        def kill() -> None:
            timed_out.set()
            proc.kill()

        timer = threading.Timer(TIMEOUT, kill)
        timer.start()
        problem: CliError | None = None
        try:
            dissection = parse_pdml(proc.stdout, payloads)
        except CliError as exc:
            problem, dissection = exc, Dissection()
        finally:
            proc.stdout.close()
            try:
                proc.wait(timeout=TIMEOUT)
            except subprocess.TimeoutExpired:
                timed_out.set()
                proc.kill()
                proc.wait()
            timer.cancel()
        if timed_out.is_set() and proc.returncode is not None and proc.returncode < 0:
            # Killed by the timer: its output, parsed or not, is not why.
            raise timeout
        if proc.returncode is not None and proc.returncode > 0:
            err.seek(0)
            _failed(proc.returncode, err.read(), what)
        if proc.returncode is not None and proc.returncode < 0 and problem is None:
            # Killed by another signal before its output ended.
            raise timeout
    if problem is not None:
        # Output that does not parse (tshark then dies of SIGPIPE when its
        # stdout is closed, which is not the timer): the parse error says why.
        raise problem
    return dissection


def _counted(names: Iterator[str]) -> list[tuple[str, int]]:
    counts: dict[str, int] = {}
    for name in names:
        counts[name] = counts.get(name, 0) + 1
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))


def _listed(counts: Sequence[tuple[str, int]]) -> str:
    return ", ".join(f"{name} ({n})" for name, n in counts) or "none"


def choose(
    dissection: Dissection, payloads: Sequence[Payload], protocol: str | None, parent: str
) -> tuple[str, list[Dissected]]:
    """The protocol to draft (``protocol``, or the only one tshark dissects
    at the start of the payloads) and the payloads where tshark dissects it
    from their first byte. ``model.no-dissector`` when tshark has none for
    them, or not ``protocol``; ``usage.missing-argument`` when there are
    several and no ``protocol``."""
    first = _counted(p[0] for p in dissection.protocols if p)
    named = [kv for kv in first if kv[0] != NO_DISSECTOR]
    if protocol is None:
        if not named:
            raise CliError(
                "model.no-dissector",
                f"tshark has no dissector for the payloads under {parent} (it dissects:"
                f" {_listed(first)}): nothing drafted",
                "tell tshark the protocol with --decode-as (e.g. 'udp.port==4433,dns'),"
                " or drop --tshark",
            )
        if len(named) > 1:
            raise CliError(
                "usage.missing-argument",
                f"tshark dissects several protocols at the start of the payloads under {parent}:"
                f" {_listed(named)}",
                "choose one with --protocol NAME",
            )
        protocol = named[0][0]
    chosen = [
        Dissected(payloads[i], dissection.fields[i][protocol])
        for i, names in enumerate(dissection.protocols)
        if protocol in names
    ]
    if not chosen or protocol == NO_DISSECTOR:
        raise CliError(
            "model.no-dissector",
            f"tshark does not dissect {protocol} at the start of any payload under {parent}"
            f" (it dissects: {_listed(first)}): nothing drafted",
            "pass a protocol tshark dissects there to --protocol, or tell tshark with"
            f" --decode-as (e.g. 'udp.port==4433,{protocol}')",
        )
    return protocol, chosen


def field_name(abbrev: str, protocol: str) -> str:
    """The attribute name of a tshark field: without the protocol's prefix,
    every run of characters a C name cannot hold one ``_``."""
    text = abbrev[len(protocol) + 1 :] if abbrev.startswith(protocol + ".") else abbrev
    name = _NOT_C.sub("_", text).strip("_")
    if not name:
        name = _NOT_C.sub("_", protocol).strip("_") or "field"
    if name[0].isdigit():
        name = "f_" + name
    return name


def _hex(data: bytes) -> str:
    return data.hex()


def _decoded_int(occ: Occurrence) -> int | None:
    """tshark's integer value: its ``show`` (decimal or ``0x`` hex)."""
    show = occ.show.strip()
    try:
        return int(show, 16) if show.lower().startswith("0x") else int(show, 10)
    except ValueError:
        return None


@dataclass(frozen=True)
class _Mapped:
    abbrev: str
    offset: int
    length: int
    mmt_type: str | None  # None: a bit field or an integer of _INT_TYPES
    bit_offset: int | None = None
    bit_width: int | None = None


def _map(info: FieldInfo, occs: Sequence[Occurrence], datas: Sequence[bytes]) -> _Mapped | str:
    """The attribute of a field present in every payload, or why not."""
    first = occs[0]
    offset, size = first.offset, first.size
    if any((o.offset, o.size) != (offset, size) for o in occs):
        return "its offset or length varies"
    if size <= 0:
        return "no bytes: tshark computes it"
    if offset < 0 or any(offset + size > len(d) for d in datas):
        return "outside the payload"
    raws = [d[offset : offset + size] for d in datas]
    if info.type in _NO_VALUE:
        return "no value"
    pairs = list(zip(occs, raws, strict=True))
    if info.bitmask:
        if any(o.unmasked is not None and o.unmasked != _hex(r) for o, r in pairs):
            return "its bytes are not the payload's"
        if size not in (1, 2, 4):
            return f"a bit field of a {size}-byte unit"
        if info.type not in (*_UNSIGNED, "FT_BOOLEAN", "FT_CHAR"):
            return f"a bit field of {info.type}"
        mask = info.bitmask
        low = (mask & -mask).bit_length() - 1
        width = bin(mask).count("1")
        if mask.bit_length() > size * 8 or mask >> low != (1 << width) - 1:
            return f"its bitmask {mask:#x} is not one run of bits"
        mapped = _Mapped(info.abbrev, offset, size, None, size * 8 - mask.bit_length(), width)
        for o, r in pairs:
            try:
                tshark_value = int(o.value, 16)
            except ValueError:
                return "tshark gives no value"
            if tshark_value != (int.from_bytes(r, "big") & mask) >> low:
                return "tshark's value is not its bits"
        return mapped
    if any(o.value and o.value != _hex(r) for o, r in pairs):
        return "its bytes are not the payload's"
    if info.type in _UNSIGNED or info.type in ("FT_BOOLEAN", "FT_CHAR"):
        width = _UNSIGNED.get(info.type, size)
        if size != width:
            return f"{info.type} in {size} bytes: tshark computes it"
        if size not in _INT_TYPES:
            return f"a {size}-byte integer: no MMT integer type of that width"
        if info.type in _UNSIGNED:
            for o, r in pairs:
                if _decoded_int(o) != int.from_bytes(r, "big"):
                    return "tshark's value is not the bytes in network byte order"
        return _Mapped(info.abbrev, offset, size, _INT_TYPES[size])
    if info.type.startswith("FT_INT"):
        return "a signed integer: no MMT signed type"
    if info.type in _ADDRESSES:
        if size != _ADDRESSES[info.type]:
            return f"{info.type} in {size} bytes"
        for o, r in pairs:
            if info.type == "FT_ETHER":
                same = o.show.lower() == ":".join(f"{b:02x}" for b in r)
            else:
                try:
                    same = ipaddress.ip_address(o.show) == ipaddress.ip_address(r)
                except ValueError:
                    same = False
            if not same:
                return "tshark's value is not the bytes"
        return _Mapped(info.abbrev, offset, size, _ADDRESS_TYPES[info.type])
    if size > BINARY_MAX:
        return f"{size} bytes: more than {BINARY_MAX}"
    return _Mapped(info.abbrev, offset, size, "MMT_BINARY_DATA")


def _bits(start: int, width: int) -> str:
    return f"bit {start}" if width == 1 else f"bits {start}-{start + width - 1}"


def _struct(offset: int, length: int) -> str:
    return f"bits_{offset}" if length == 1 else f"bits_{offset}_{length * 8}"


def draft(
    protocol: str,
    infos: dict[str, FieldInfo],
    dissected: Sequence[Dissected],
    *,
    max_name: int | None = None,
) -> Draft:
    """The attributes of ``protocol``'s fields (module docstring) in the
    ``dissected`` payloads (at least one)."""
    datas = [d.payload.data for d in dissected]
    n = len(dissected)
    names: list[str] = []
    for d in dissected:
        names += [k for k in d.fields if k not in names]
    skipped: list[tuple[str, str]] = []
    mapped: list[_Mapped] = []
    for abbrev in names:
        if not abbrev.startswith(protocol + "."):
            continue
        info = infos.get(abbrev)
        if info is None:
            skipped.append((abbrev, "not a field of tshark -G fields"))
            continue
        occs = [d.fields.get(abbrev) for d in dissected]
        present = [o for o in occs if o is not None]
        if len(present) < n:
            skipped.append((abbrev, f"in {len(present)} of {n} payloads"))
            continue
        result = _map(info, present, datas)
        if isinstance(result, str):
            skipped.append((abbrev, result))
        else:
            mapped.append(result)

    # Bit fields by unit: the first of two that share bits is kept.
    units: dict[tuple[int, int], list[_Mapped]] = {}
    plain: list[_Mapped] = []
    for m in mapped:
        if m.bit_offset is None:
            plain.append(m)
            continue
        unit = units.setdefault((m.offset, m.length), [])
        clash = next(
            (
                u
                for u in unit
                if u.bit_offset is not None
                and u.bit_width is not None
                and m.bit_width is not None
                and u.bit_offset < m.bit_offset + m.bit_width
                and m.bit_offset < u.bit_offset + u.bit_width
            ),
            None,
        )
        if clash is not None:
            skipped.append((m.abbrev, f"its bits are {clash.abbrev}'s"))
        else:
            unit.append(m)

    # A struct's name is taken too: no attribute may have it.
    taken: set[str] = {_struct(offset, length).lower() for offset, length in units}

    def unique(name: str) -> str:
        if max_name is not None:
            name = name[:max_name]
        candidate, k = name, 2
        while candidate.lower() in taken:
            suffix = f"_{k}"
            base = name if max_name is None else name[: max_name - len(suffix)]
            candidate, k = base + suffix, k + 1
        taken.add(candidate.lower())
        return candidate

    def note(m: _Mapped) -> str:
        info = infos[m.abbrev]
        mask = f", mask {info.bitmask:#x}" if info.bitmask else ""
        return f"tshark {m.abbrev} ({info.type}{mask})"

    fields: list[Field] = []
    for m in plain:
        values = {d[m.offset : m.offset + m.length] for d in datas}
        fields.append(
            Field(
                unique(field_name(m.abbrev, protocol)),
                m.offset,
                m.length,
                len(values) == 1,
                note(m),
                mmt_type=m.mmt_type,
                source=m.abbrev,
            )
        )
    for (offset, length), unit in units.items():
        struct = _struct(offset, length)
        bit = 0
        for m in sorted(unit, key=lambda u: u.bit_offset or 0):
            assert m.bit_offset is not None and m.bit_width is not None
            if m.bit_offset > bit:
                fields.append(
                    Field(
                        unique(f"{struct}_b{bit}"),
                        offset,
                        length,
                        False,
                        _bits(bit, m.bit_offset - bit) + ": no tshark field in every payload",
                        bit,
                        m.bit_offset - bit,
                        expect=False,
                    )
                )
            probe = Field("", offset, length, True, "", m.bit_offset, m.bit_width)
            fields.append(
                Field(
                    unique(field_name(m.abbrev, protocol)),
                    offset,
                    length,
                    len({probe.value(d) for d in datas}) == 1,
                    note(m),
                    m.bit_offset,
                    m.bit_width,
                    source=m.abbrev,
                )
            )
            bit = m.bit_offset + m.bit_width
    fields.sort(key=lambda f: (f.offset, f.bit_offset is not None, f.length, f.bit_offset or 0))
    lengths = [len(d) for d in datas]
    header = max((f.offset + f.length for f in fields), default=0)
    skeleton = Skeleton(header, tuple(fields), None, None, min(lengths), max(lengths))
    return Draft(skeleton, tuple(skipped), tuple(d.payload for d in dissected))
