# Capture evaluation: telem — PASS

- Capture: `/work/plugin-work-5c743542/capture/capture.pcap` (sha256 `249a4dedad50c50e…`), **synthetic**
- Plugin: `/work/plugin-work-5c743542/project/build/mmtp_telem.so` (sha256 `287beb3bafb77bee…`)
- Parent: `udp:dport=5684`; expected frames from tshark: `udp.port == 5684 && udp.length > 8`
- Frames 9, expected 9, claimed 9, expected and claimed 9, recall 1.0

## Warnings

- attributes never extracted on this capture: readings
- synthetic capture: its bytes come from the spec as read by the drafter, not from a real implementation

## Drift against tshark

None: the plugin agrees with tshark on every compared frame.

## Attributes

| Attribute | Packets | Most frequent values |
|---|---:|---|
| flags | 9 | `0` x5, `15` x2, `2` x1, `1` x1 |
| version | 9 | `1` x9 |
| msg_type | 9 | `1` x5, `2` x4 |
| readings | 0 |  |
| length | 9 | `8` x5, `12` x1, `13` x1, `20` x1 |
| sequence | 9 | `42` x2, `4294967295` x2, `43` x1, `255` x1 |
| payload | 5 | `deadbeef` x1, `` x1, `0102030405` x1, `000102030405060708090a0b` x1 |

## Protocol paths

| Path | Without plugin | With plugin |
|---|---:|---:|
| `meta.ethernet.ip.udp.TELEM` | 0 | 9 |
| `meta.ethernet.ip.udp.unknown` | 9 | 0 |
