# Capture

- Origin: **synthetic** (crafted by scripts/make_pcap.py from payloads.txt; NOT a real capture; not verified by cyberlab).
- Why: no capture was given, none found next to the inputs, cyberlab unavailable (no `asm`, no `$CYBERLAB_DIR`). The request allows a synthetic capture.
- Contents: 9 Ethernet/IPv4/UDP frames, client 10.0.0.1:40000 <-> server 10.0.0.2:5684; 5 readings (c:, to port 5684) and 4 acknowledgements (s:, from port 5684). Covers both spec examples byte for byte, flags 0/1/2/0xf, empty and non-empty payloads, sequence 0/1/42/255/65535/0xffffffff.
- Written before the plugin existed; payloads come from the spec only.
- sha256: 249a4dedad50c50e379f78d3c90846bd9682ca98f8104254f981f8d8d66922c9
- Checks: capinfos reads it (Ethernet, 9 packets); tshark `udp.port == 5684 && udp.length > 8` matches 9 frames, which tshark dissects as DTLS (port 5684 is CoAP over DTLS); tshark has no TELEM dissector, so no `--field` comparison is possible.
- Limits: shows that the plugin loads, classifies under its parent and extracts every attribute on mmt-dpi's path; not that the spec was read right, nor real traffic.
