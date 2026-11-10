#!/usr/bin/env python3
"""Validate the test corpus under tests/corpus/ (Python 3.8+, stdlib only).

Checks that:
  - index.yaml declares exactly the PDL constructs of the Java generator
    inventory (REQUIRED_CONSTRUCTS below), and every construct is exercised
    by at least one packet of at least one valid model;
  - every example model in plugins/*_plugin has a corpus entry whose model
    file is a byte-identical copy, with at least one packet;
  - each packet file is well-formed (required keys, types, value ranges);
  - each expected value agrees with the packet bytes at the stated offset
    under the corpus byte-order and bitfield rules (README.md, "Semantics");
  - the label, id, encoding and encapsulation the fixtures assume match the
    model file.

The corpus files use a strict YAML subset (README.md, "File format") so that
this script needs no third-party parser. Every file in that subset is also
plain YAML 1.1/1.2 and loads to the same data with a full YAML parser.

Usage: python3 tests/corpus/validate.py [corpus dir]
Exit status: 0 when the corpus is valid, 1 otherwise.
"""

import ipaddress
import json
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# The constructs of the inventory (issue #3, first comment, section 1).
# ---------------------------------------------------------------------------

MMT_TYPES = (
    "MMT_U8_DATA", "MMT_U16_DATA", "MMT_U32_DATA", "MMT_U64_DATA",
    "MMT_DATA_POINTER", "MMT_STRING_DATA", "MMT_DATA_IP_NET",
    "MMT_DATA_MAC_ADDR", "MMT_DATA_IP_ADDR", "MMT_DATA_PATH",
    "MMT_DATA_TIMEVAL", "MMT_BINARY_DATA", "MMT_DATA_BUFFER", "MMT_DATA_CHAR",
    "MMT_DATA_IP6_ADDR", "MMT_DATA_PORT", "MMT_DATA_POINT",
    "MMT_DATA_PORT_RANGE", "MMT_DATA_DATE", "MMT_DATA_TIMEARG",
    "MMT_DATA_STRING_INDEX", "MMT_DATA_FLOAT", "MMT_DATA_LAYERID",
    "MMT_DATA_FILTER_STATE", "MMT_DATA_PARENT", "MMT_BINARY_VAR_DATA",
)

REQUIRED_CONSTRUCTS = (
    # Top level
    "lexical.keyword_names",
    # define
    "define.decimal", "define.hex", "define.alias",
    # Properties
    "properties.label", "properties.id", "properties.context",
    "properties.session_context", "properties.session",
    "properties.encapsulation", "properties.optional_omitted",
    "properties.encoding.network", "properties.encoding.host",
    "properties.encoding.ascii", "properties.encoding.unicode",
    "properties.encoding.default",
    # Attributes: struct
    "struct.plain", "struct.multi_name", "struct.bitfield",
    "struct.bitfield.mixed_line", "struct.bitfield.followed",
    "struct.type.int", "struct.type.long", "struct.type.uint32_t",
    "struct.type.short", "struct.type.uint16_t", "struct.type.char",
    "struct.type.u_char", "struct.type.uint8_t", "struct.type.unsigned",
    "struct.type.pointer", "struct.type.mmt", "struct.type.nested",
    # Attributes: attribute
    "attribute.full", "attribute.no_offset_len", "attribute.no_scope",
    "attribute.no_data_len", "attribute.no_offset",
    # Scopes
    "scope.SCOPE_PACKET", "scope.packet", "scope.SCOPE_SESSION",
    "scope.session",
    # Attributes: conditional
    "conditional.if", "conditional.if_else", "conditional.nested_if",
    "conditional.nested_else", "conditional.struct", "conditional.no_match",
    # Expressions
    "expr.literal.decimal", "expr.literal.hex", "expr.add", "expr.sub",
    "expr.mul", "expr.div", "expr.parens", "expr.cmp.eq", "expr.cmp.ne",
    "expr.cmp.gt", "expr.cmp.lt", "expr.cmp.ge", "expr.cmp.le",
    "expr.and", "expr.or", "expr.val", "expr.sizeof.type",
    "expr.sizeof.struct", "expr.sizeof.mmt", "expr.offset_fn", "expr.len_fn",
    "expr.ntohs", "expr.ntohl",
    # Offset and alignment
    "layout.align.plain", "layout.align.struct", "layout.align.stop",
    "layout.align.conditional_else", "layout.align.conditional_no_else",
    # classifynext
    "classifynext.switch", "classifynext.case.decimal",
    "classifynext.case.hex", "classifynext.case.define",
    "classifynext.default", "classifynext.nextencaps.number",
    "classifynext.nextencaps.define", "classifynext.nextoffset",
    "classifynext.fallthrough", "classifynext.no_match",
) + tuple("type." + t for t in MMT_TYPES)

# Value kinds of the MMT_* types (README.md, "Value kinds").
INT_WIDTH = {
    "MMT_U8_DATA": 1, "MMT_U16_DATA": 2, "MMT_U32_DATA": 4,
    "MMT_U64_DATA": 8, "MMT_DATA_CHAR": 1, "MMT_DATA_PORT": 2,
}
ADDR_WIDTH = {
    "MMT_DATA_MAC_ADDR": 6, "MMT_DATA_IP_ADDR": 4, "MMT_DATA_IP_NET": 4,
    "MMT_DATA_IP6_ADDR": 16,
}
POINTER_TYPES = {"MMT_DATA_POINTER"}
BYTES_TYPES = set(MMT_TYPES) - set(INT_WIDTH) - set(ADDR_WIDTH) - POINTER_TYPES

ENCODING_ORDER = {
    "network": "big", "host": "little",
    "ascii": "none", "unicode": "none", "default": "none",
}

CONSTRUCT_ID = re.compile(r"^[a-z][a-z0-9_]*(\.[A-Za-z0-9_]+)+$")
NAME = re.compile(r"^[a-z][a-z0-9_]*$")
HEX_BYTES = re.compile(r"^([0-9a-f]{2})( [0-9a-f]{2})*$")


# ---------------------------------------------------------------------------
# Strict YAML subset loader.
# ---------------------------------------------------------------------------

class LoadError(Exception):
    pass


KEY = re.compile(r"^([A-Za-z_][A-Za-z0-9_.-]*):(?: (.*))?$")
INT = re.compile(r"^-?(0|[1-9][0-9]*)$")
PLAIN = re.compile(r"^[A-Za-z_/][A-Za-z0-9_./+-]*$")
# Plain words that YAML 1.1 reads as booleans or null: always quote them.
YAML11_SPECIAL = {"y", "n", "yes", "no", "on", "off", "true", "false",
                  "null", "~"}


def _scalar(text, where):
    text = text.strip()
    if not text:
        raise LoadError(f"{where}: empty value")
    if text[0] == '"':
        end = _string_end(text, where)
        rest = text[end + 1:].strip()
        if rest and not rest.startswith("#"):
            raise LoadError(f"{where}: text after a quoted string")
        try:
            return json.loads(text[:end + 1])
        except ValueError as exc:
            raise LoadError(f"{where}: bad quoted string: {exc}") from None
    if text[0] == "[":
        return _flow_seq(text, where)
    text = re.sub(r"\s+#.*$", "", text)
    if INT.match(text):
        return int(text)
    if text == "true":
        return True
    if text == "false":
        return False
    if text == "null":
        return None
    if PLAIN.match(text) and text.lower() not in YAML11_SPECIAL:
        return text
    raise LoadError(f"{where}: unsupported scalar {text!r} (quote it)")


def _string_end(text, where):
    i = 1
    while i < len(text):
        if text[i] == "\\":
            i += 2
            continue
        if text[i] == '"':
            return i
        i += 1
    raise LoadError(f"{where}: unterminated string")


def _flow_seq(text, where):
    end = text.rfind("]")
    if end < 0:
        raise LoadError(f"{where}: unterminated flow sequence")
    rest = text[end + 1:].strip()
    if rest and not rest.startswith("#"):
        raise LoadError(f"{where}: text after a flow sequence")
    body = text[1:end].strip()
    if not body:
        return []
    items, cur, i = [], "", 0
    while i < len(body):
        c = body[i]
        if c == '"':
            j = _string_end(body[i:], where) + i
            cur += body[i:j + 1]
            i = j + 1
            continue
        if c in "[]{}":
            raise LoadError(f"{where}: nested flow collections are not allowed")
        if c == ",":
            items.append(cur)
            cur = ""
        else:
            cur += c
        i += 1
    items.append(cur)
    return [_scalar(item, where) for item in items]


def load_yaml(path):
    lines = []
    raw = path.read_bytes()
    if b"\r" in raw:
        raise LoadError(f"{path}: CRLF line endings (use LF)")
    for no, line in enumerate(raw.decode("utf-8").split("\n"), 1):
        if "\t" in line:
            raise LoadError(f"{path}:{no}: tab character")
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped in ("---", "...") or stripped[0] in "&*!|>%@`{":
            raise LoadError(f"{path}:{no}: unsupported YAML syntax")
        lines.append((no, len(line) - len(line.lstrip(" ")), stripped))
    if not lines:
        raise LoadError(f"{path}: empty file")
    value, pos = _block(lines, 0, lines[0][1], str(path))
    if pos != len(lines):
        raise LoadError(f"{path}:{lines[pos][0]}: unexpected indentation")
    return value


def _block(lines, pos, indent, name):
    if lines[pos][2].startswith("- ") or lines[pos][2] == "-":
        return _seq(lines, pos, indent, name)
    return _map(lines, pos, indent, name)


def _map(lines, pos, indent, name, first=None):
    out = {}
    while pos < len(lines):
        no, ind, text = lines[pos] if first is None else (lines[pos][0], indent, first)
        first = None
        if ind < indent:
            break
        if ind > indent:
            raise LoadError(f"{name}:{no}: unexpected indentation")
        m = KEY.match(text)
        if not m:
            raise LoadError(f"{name}:{no}: expected 'key: value'")
        key, rest = m.group(1), m.group(2)
        if key in out:
            raise LoadError(f"{name}:{no}: duplicate key {key!r}")
        pos += 1
        if rest is None or not rest.strip() or rest.strip().startswith("#"):
            if pos < len(lines) and (lines[pos][1] > indent or (
                    lines[pos][1] == indent and lines[pos][2].startswith("- "))):
                out[key], pos = _block(lines, pos, lines[pos][1], name)
            else:
                raise LoadError(f"{name}:{no}: key {key!r} has no value")
        else:
            out[key] = _scalar(rest, f"{name}:{no}")
    return out, pos


def _seq(lines, pos, indent, name):
    out = []
    while pos < len(lines):
        no, ind, text = lines[pos]
        if ind < indent:
            break
        if ind > indent or not (text.startswith("- ") or text == "-"):
            if ind == indent:
                break
            raise LoadError(f"{name}:{no}: unexpected indentation")
        item = text[1:].strip()
        if not item:
            pos += 1
            if pos >= len(lines) or lines[pos][1] <= indent:
                raise LoadError(f"{name}:{no}: empty sequence item")
            value, pos = _block(lines, pos, lines[pos][1], name)
        elif KEY.match(item) and not item.startswith('"'):
            value, pos = _map(lines, pos, indent + 2, name, first=item)
        else:
            value = _scalar(item, f"{name}:{no}")
            pos += 1
        out.append(value)
    return out, pos


# ---------------------------------------------------------------------------
# Checks.
# ---------------------------------------------------------------------------

class Report:
    def __init__(self):
        self.errors = []

    def err(self, where, msg):
        self.errors.append(f"{where}: {msg}")


def _need(rep, where, obj, key, kind, allow_empty=False):
    if not isinstance(obj, dict) or key not in obj:
        rep.err(where, f"missing key {key!r}")
        return None
    val = obj[key]
    if kind is int and isinstance(val, bool):
        rep.err(where, f"{key!r} must be an integer")
        return None
    if not isinstance(val, kind):
        rep.err(where, f"{key!r} must be {kind.__name__}")
        return None
    if not allow_empty and kind in (str, list) and not val:
        rep.err(where, f"{key!r} must not be empty")
        return None
    return val


def _only(rep, where, obj, allowed):
    for key in obj:
        if key not in allowed:
            rep.err(where, f"unknown key {key!r}")


def _hex(rep, where, text):
    if not isinstance(text, str) or not HEX_BYTES.match(text):
        rep.err(where, "bytes must be lower-case hex pairs separated by one space")
        return None
    return bytes.fromhex(text)


def _decode(rep, where, typ, data, order, value, offset):
    """Compare an expected value with the bytes it claims to come from."""
    if typ in INT_WIDTH:
        if len(data) > 1 and order == "none":
            rep.err(where, f"{typ} wider than one byte needs a byte order")
            return
        got = int.from_bytes(data, "little" if order == "little" else "big")
        if not isinstance(value, int) or isinstance(value, bool):
            rep.err(where, "value must be an integer")
        elif value != got:
            rep.err(where, f"value {value} != {got} read from the bytes")
    elif typ in ADDR_WIDTH:
        if typ == "MMT_DATA_MAC_ADDR":
            got = ":".join(f"{b:02x}" for b in data)
        elif typ == "MMT_DATA_IP6_ADDR":
            got = str(ipaddress.IPv6Address(data))
        else:
            got = str(ipaddress.IPv4Address(data))
        if value != got:
            rep.err(where, f"value {value!r} != {got!r} read from the bytes")
    elif typ in POINTER_TYPES:
        if value != offset:
            rep.err(where, "a pointer value is the offset it points at")
    else:
        if not isinstance(value, str) or not HEX_BYTES.match(value):
            rep.err(where, "value must be lower-case hex pairs separated by one space")
        elif bytes.fromhex(value) != data:
            rep.err(where, f"value != the {len(data)} bytes at the offset")


def _check_value(rep, where, attr, typ, payload, order):
    offset = _need(rep, where, attr, "offset", int)
    length = _need(rep, where, attr, "length", int)
    if offset is None or length is None:
        return
    if offset < 0 or length <= 0 or offset + length > len(payload):
        rep.err(where, f"bytes {offset}..{offset + length - 1} are outside the packet")
        return
    data = payload[offset:offset + length]
    value = attr.get("value")
    if "value" not in attr:
        rep.err(where, "missing key 'value'")
        return
    if "bit_offset" in attr or "bit_width" in attr:
        bo = _need(rep, where, attr, "bit_offset", int)
        bw = _need(rep, where, attr, "bit_width", int)
        if bo is None or bw is None:
            return
        if typ not in INT_WIDTH or bw <= 0 or bo < 0 or bo + bw > 8 * length:
            rep.err(where, "bad bitfield position")
            return
        if length != INT_WIDTH[typ]:
            rep.err(where, f"a {typ} bitfield's storage unit is {INT_WIDTH[typ]} bytes, not {length}")
            return
        unit = int.from_bytes(data, "little" if order == "little" else "big")
        got = (unit >> (8 * length - bo - bw)) & ((1 << bw) - 1)
        if value != got:
            rep.err(where, f"bitfield value {value} != {got} read from the bytes")
        return
    if typ in INT_WIDTH and length != INT_WIDTH[typ]:
        rep.err(where, f"{typ} has length {INT_WIDTH[typ]}, not {length}")
        return
    if typ in ADDR_WIDTH and length != ADDR_WIDTH[typ]:
        rep.err(where, f"{typ} has length {ADDR_WIDTH[typ]}, not {length}")
        return
    if typ in BYTES_TYPES and "text" in attr:
        if not isinstance(attr["text"], str) or attr["text"].encode("utf-8") != data:
            rep.err(where, "'text' does not match the bytes")
    _decode(rep, where, typ, data, order, value, offset)


ATTR_KEYS = {"name", "type", "status", "offset", "length", "value",
             "bit_offset", "bit_width", "text", "scope", "source", "note",
             "reason", "spec"}


def check_attribute(rep, where, attr, payload, order):
    if not isinstance(attr, dict):
        rep.err(where, "attribute must be a mapping")
        return
    _only(rep, where, attr, ATTR_KEYS)
    name = _need(rep, where, attr, "name", str)
    if name:
        where = f"{where} ({name})"
    typ = _need(rep, where, attr, "type", str)
    _need(rep, where, attr, "source", str)
    if typ and typ not in MMT_TYPES:
        rep.err(where, f"unknown type {typ!r}")
        return
    if "scope" in attr and attr["scope"] not in ("packet", "session"):
        rep.err(where, "scope must be packet or session")
    status = attr.get("status", "value")
    if status == "value":
        if "reason" in attr or "spec" in attr:
            rep.err(where, "'reason'/'spec' only go with status undefined")
        if typ:
            _check_value(rep, where, attr, typ, payload, order)
    elif status == "absent":
        for key in ("offset", "length", "value", "spec"):
            if key in attr:
                rep.err(where, f"an absent attribute has no {key!r}")
    elif status == "undefined":
        _need(rep, where, attr, "reason", str)
        for key in ("offset", "length", "value"):
            if key in attr:
                rep.err(where, f"an undefined attribute has no {key!r} (use 'spec')")
        spec = attr.get("spec")
        if spec is not None:
            sw = f"{where} spec"
            if not isinstance(spec, dict):
                rep.err(sw, "must be a mapping")
                return
            _only(rep, sw, spec, {"offset", "length", "value", "byte_order",
                                  "text", "source"})
            _need(rep, sw, spec, "source", str)
            sorder = spec.get("byte_order", "none")
            if sorder not in ("big", "little", "none"):
                rep.err(sw, "byte_order must be big, little or none")
            elif typ:
                _check_value(rep, sw, spec, typ, payload, sorder)
    else:
        rep.err(where, "status must be value, absent or undefined")


PACKET_KEYS = {"schema", "id", "model", "summary", "constructs", "parent",
               "bytes", "bytes_source", "expect", "note"}


def check_packet(rep, path, model, facts, known_constructs):
    where = str(path)
    try:
        doc = load_yaml(path)
    except LoadError as exc:
        rep.err(where, str(exc))
        return []
    if not isinstance(doc, dict):
        rep.err(where, "top level must be a mapping")
        return []
    _only(rep, where, doc, PACKET_KEYS)
    if doc.get("schema") != 1:
        rep.err(where, "schema must be 1")
    expected_id = f"{model['name']}/{path.stem}"
    if doc.get("id") != expected_id:
        rep.err(where, f"id must be {expected_id!r}")
    if doc.get("model") != model["name"]:
        rep.err(where, f"model must be {model['name']!r}")
    _need(rep, where, doc, "summary", str)
    _need(rep, where, doc, "bytes_source", str)
    constructs = _need(rep, where, doc, "constructs", list) or []
    for c in constructs:
        if c not in known_constructs:
            rep.err(where, f"unknown construct {c!r}")
    if len(set(constructs)) != len(constructs):
        rep.err(where, "duplicate construct")

    parent = _need(rep, where, doc, "parent", dict)
    if parent is not None:
        pw = f"{where} parent"
        _only(rep, pw, parent, {"kind", "path", "selector", "source"})
        kind = parent.get("kind")
        path_ = _need(rep, pw, parent, "path", list, allow_empty=True)
        _need(rep, pw, parent, "selector", str)
        _need(rep, pw, parent, "source", str)
        if kind not in ("stack", "link", "none"):
            rep.err(pw, "kind must be stack, link or none")
        elif path_ is not None and (kind == "stack") != bool(path_):
            rep.err(pw, "only a stack parent has a non-empty path")
        for p in path_ or []:
            if not isinstance(p, str) or not NAME.match(p):
                rep.err(pw, f"bad protocol name {p!r}")

    chunks = _need(rep, where, doc, "bytes", list) or []
    payload = b""
    for i, chunk in enumerate(chunks):
        data = _hex(rep, f"{where} bytes[{i}]", chunk)
        if data is None:
            return constructs
        payload += data

    expect = _need(rep, where, doc, "expect", dict)
    if expect is None:
        return constructs
    ew = f"{where} expect"
    _only(rep, ew, expect, {"protocol", "proto_id", "next", "attributes"})
    if expect.get("protocol") != facts["protocol"]:
        rep.err(ew, f"protocol must be {facts['protocol']!r} (the upper-cased label)")
    if expect.get("proto_id") != facts["proto_id"]:
        rep.err(ew, f"proto_id must be {facts['proto_id']} (the model id)")
    nxt = _need(rep, ew, expect, "next", dict)
    if nxt is not None:
        nw = f"{ew} next"
        kind = nxt.get("kind")
        if kind == "proto":
            _only(rep, nw, nxt, {"kind", "proto_id", "offset", "source"})
            _need(rep, nw, nxt, "proto_id", int)
            off = _need(rep, nw, nxt, "offset", int)
            _need(rep, nw, nxt, "source", str)
            if off is not None and not 0 <= off <= len(payload):
                rep.err(nw, "offset is outside the packet")
        elif kind in ("none", "hook"):
            _only(rep, nw, nxt, {"kind", "source"})
        else:
            rep.err(nw, "kind must be none, hook or proto")
        if not facts["encapsulation"] and kind != "none":
            rep.err(nw, "encapsulation is false: next must be none")
        if facts["encapsulation"] and not facts["classifynext"] and kind != "hook":
            rep.err(nw, "encapsulation without classifynext: next must be hook")
        if facts["classifynext"] and facts["encapsulation"] and kind == "hook":
            rep.err(nw, "the model has a classifynext switch: next is none or proto")
    attrs = _need(rep, ew, expect, "attributes", list, allow_empty=True) or []
    seen = set()
    for i, attr in enumerate(attrs):
        check_attribute(rep, f"{ew} attributes[{i}]", attr, payload,
                        ENCODING_ORDER[facts["encoding"]])
        if isinstance(attr, dict) and attr.get("name") in seen:
            rep.err(ew, f"attribute {attr.get('name')!r} listed twice")
        if isinstance(attr, dict):
            seen.add(attr.get("name"))
    return constructs


def model_facts(rep, where, text):
    def prop(key):
        m = re.search(r"\b" + key + r'\s*=\s*"([^"]*)"', text)
        return m.group(1) if m else None

    label, ident = prop("label"), prop("id")
    if label is None or ident is None or not INT.match(ident):
        rep.err(where, "cannot read label and id from the model")
        return None
    encoding = prop("encoding")
    return {
        "protocol": label.upper(),
        "proto_id": int(ident),
        "encoding": "default" if encoding is None else encoding.lower(),
        "encapsulation": prop("encapsulation") == "true",
        "classifynext": re.search(r"\bclassifynext\s*\{", text) is not None,
    }


MODEL_KEYS = {"name", "kind", "origin", "model", "encoding", "valid",
              "invalid_reason", "java", "spec", "notes", "packets"}
JAVA_STATUS = {"compiles", "compile-fail", "parses", "syntax-errors",
               "no-output"}


def validate(corpus):
    rep = Report()
    repo = corpus.parent.parent
    index_path = corpus / "index.yaml"
    try:
        index = load_yaml(index_path)
    except LoadError as exc:
        rep.err(str(index_path), str(exc))
        return rep
    iw = str(index_path)
    if not isinstance(index, dict) or index.get("schema") != 1:
        rep.err(iw, "top level must be a mapping with schema: 1")
        return rep
    _only(rep, iw, index, {"schema", "inventory", "constructs", "models"})
    _need(rep, iw, index, "inventory", str)

    constructs = _need(rep, iw, index, "constructs", list) or []
    declared = {}
    for i, c in enumerate(constructs):
        cw = f"{iw} constructs[{i}]"
        if not isinstance(c, dict):
            rep.err(cw, "must be a mapping")
            continue
        _only(rep, cw, c, {"id", "inventory", "summary", "covered_by"})
        cid = _need(rep, cw, c, "id", str)
        _need(rep, cw, c, "inventory", str)
        _need(rep, cw, c, "summary", str)
        cov = _need(rep, cw, c, "covered_by", list, allow_empty=True)
        if cid is None:
            continue
        if not CONSTRUCT_ID.match(cid):
            rep.err(cw, f"bad construct id {cid!r}")
        if cid in declared:
            rep.err(cw, f"construct {cid!r} declared twice")
        declared[cid] = cov or []
    for cid in REQUIRED_CONSTRUCTS:
        if cid not in declared:
            rep.err(iw, f"inventory construct {cid!r} is not in the index")
    for cid in declared:
        if cid not in REQUIRED_CONSTRUCTS:
            rep.err(iw, f"construct {cid!r} is not an inventory construct")

    models = _need(rep, iw, index, "models", list) or []
    coverage = {cid: set() for cid in declared}
    runnable = set()  # constructs exercised by a packet of a valid model
    names, origins = set(), set()
    for i, model in enumerate(models):
        mw = f"{iw} models[{i}]"
        if not isinstance(model, dict):
            rep.err(mw, "must be a mapping")
            continue
        _only(rep, mw, model, MODEL_KEYS)
        name = _need(rep, mw, model, "name", str)
        if name is None:
            continue
        mw = f"{iw} model {name}"
        if not NAME.match(name) or name in names:
            rep.err(mw, "name must be unique lower_snake_case")
        names.add(name)
        kind = model.get("kind")
        if kind not in ("example", "targeted"):
            rep.err(mw, "kind must be example or targeted")
        if model.get("model") != f"models/{name}/model.pdl":
            rep.err(mw, f"model must be models/{name}/model.pdl")
        valid = model.get("valid")
        if not isinstance(valid, bool):
            rep.err(mw, "valid must be true or false")
        elif not valid:
            _need(rep, mw, model, "invalid_reason", str)
        elif "invalid_reason" in model:
            rep.err(mw, "invalid_reason only goes with valid: false")
        if model.get("java") not in JAVA_STATUS:
            rep.err(mw, f"java must be one of {sorted(JAVA_STATUS)}")
        _need(rep, mw, model, "spec", str)
        enc = model.get("encoding")
        if enc not in ENCODING_ORDER:
            rep.err(mw, f"encoding must be one of {sorted(ENCODING_ORDER)}")

        model_path = corpus / "models" / name / "model.pdl"
        if not model_path.is_file():
            rep.err(mw, f"{model_path} is missing")
            continue
        text = model_path.read_bytes()
        if kind == "example":
            origin = _need(rep, mw, model, "origin", str)
            if origin:
                origins.add(origin)
                src = repo / origin
                if not src.is_file():
                    rep.err(mw, f"origin {origin} is missing")
                elif src.read_bytes() != text:
                    rep.err(mw, f"model.pdl differs from {origin}")
        elif "origin" in model:
            rep.err(mw, "a targeted model has no origin")
        facts = model_facts(rep, mw, text.decode("utf-8", "replace"))
        if facts is None:
            continue
        if enc in ENCODING_ORDER and enc != facts["encoding"]:
            rep.err(mw, f"encoding {enc!r} but the model says {facts['encoding']!r}")

        packets = _need(rep, mw, model, "packets", list) or []
        pdir = corpus / "models" / name / "packets"
        on_disk = sorted(p.stem for p in pdir.glob("*.yaml")) if pdir.is_dir() else []
        if sorted(packets) != on_disk:
            rep.err(mw, f"packets {sorted(packets)} != files on disk {on_disk}")
        for stem in packets:
            ppath = pdir / f"{stem}.yaml"
            if not ppath.is_file():
                continue
            for cid in check_packet(rep, ppath, model, facts, declared):
                coverage.setdefault(cid, set()).add(f"{name}/{stem}")
                if valid is True:
                    runnable.add(cid)

    mdir = corpus / "models"
    for d in sorted(mdir.iterdir()) if mdir.is_dir() else []:
        if d.name not in names:
            rep.err(iw, f"models/{d.name} has no entry in the index")
    plugin_models = {f"plugins/{p.name}" for p in (repo / "plugins").glob("*_plugin")
                     if p.is_file()}
    for origin in sorted(plugin_models - origins):
        rep.err(iw, f"example model {origin} has no corpus entry")
    for origin in sorted(origins - plugin_models):
        rep.err(iw, f"origin {origin} is not a plugins/*_plugin model")

    for cid, cov in declared.items():
        got = coverage.get(cid, set())
        if not got:
            rep.err(iw, f"construct {cid!r} is not exercised by any packet")
        elif cid not in runnable:
            rep.err(iw, f"construct {cid!r} is only exercised by invalid models")
        if sorted(cov) != sorted(got):
            rep.err(iw, f"construct {cid!r}: covered_by {sorted(cov)} != "
                        f"packets that list it {sorted(got)}")
    return rep, len(names), sum(len(v) for v in coverage.values()), len(declared)


def main(argv):
    corpus = Path(argv[1]) if len(argv) > 1 else Path(__file__).resolve().parent
    result = validate(corpus)
    if isinstance(result, Report):
        rep, counts = result, None
    else:
        rep, *counts = result
    if rep.errors:
        for line in rep.errors:
            print(f"FAIL: {line}")
        print(f"corpus invalid: {len(rep.errors)} error(s)")
        return 1
    models, links, constructs = counts
    print(f"PASS: {models} models, {constructs} constructs, "
          f"{links} construct-packet links")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
