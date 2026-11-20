# Capture evaluation: ocip — PASS

- Capture: `ocip-plugin/capture/capture.pcap` (sha256 `0688efc704f01b33…`), **synthetic**
- Plugin: `ocip-plugin/project/build/mmtp_ocip.so` (sha256 `1f9aceb04d782b34…`)
- Parent: `tcp:port=2208`; expected frames from tshark: `tcp.port==2208 && tcp.len>0`
- Frames 101, expected 23, claimed 50, expected and claimed 23, recall 1.0

## Warnings

- synthetic capture: its bytes come from the spec as read by the drafter, not from a real implementation

## Drift against tshark

None: the plugin agrees with tshark on every compared frame.

## Attributes

| Attribute | Packets | Most frequent values |
|---|---:|---|
| dtd | 8 | `<!DOCTYPE BroadsoftDocument SYSTEM "http://203.0.113.50/oci.dtd` x2, `<!DOCTYPE BroadsoftDocument [<!ENTITY xxe SYSTEM "file:///usr/l` x1, `<!DOCTYPE BroadsoftDocument [<!ENTITY % ext SYSTEM "http://203.` x1, `<!DOCTYPE BroadsoftDocument SYSTEM "http://203.0.113.50:8000/oc` x1 |
| has_dtd | 23 | `0` x15, `1` x8 |
| command_type | 22 | `AuthenticationRequest` x9, `c:ErrorResponse` x7, `AuthenticationResponse` x2, `LoginRequest22V5` x1 |
| session_id | 22 | `a1b2c3d4e5f6` x20, `&xxe;` x1, `s1` x1 |
| is_request | 23 | `1` x12, `0` x11 |

## Protocol paths

| Path | Without plugin | With plugin |
|---|---:|---:|
| `meta.ethernet.ip.tcp.OCIP` | 0 | 50 |
| `meta.ethernet.ip.tcp.http` | 15 | 15 |
| `meta.ethernet.ip.tcp.unknown` | 86 | 36 |
