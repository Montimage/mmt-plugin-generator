# DEMO: what is known besides the capture

An eval input of the mmt-plugin-generator skill. `capture.pcap` (written by
tcpdump) holds DEMO messages sent to UDP port 4433, and two other frames.
The protocol's author says:

- byte 0 is the version, 1;
- byte 1 is the message kind;
- bytes 2-3 are the length of the whole message, big-endian;
- bytes 4-7 are a sequence number, big-endian;
- the body follows, from byte 8: text, not decoded.
