# capture.pcap

**Synthetic.** No public OCI-P capture or exploit exists (Cisco and Malbear Labs withhold the payloads), and no
BroadWorks server was available to record one. The capture is the 11 pcaps of `inputs/gen_pcaps.py` (Scapy, RFC 5737
addresses, wire format of lukebeer/broadworks-ocip), concatenated by `make-capture.sh`, each file's client port moved
to 50000+10k (gen_pcaps.py gives attack_v2 and attack_v4 the same client port 41019).

- 101 frames, Ethernet, sha256 `0688efc704f01b331a28650280deb4fa000e495e57ccddf37428bd266a47f045`
- OCI-P flows to TCP 2208: attack V1-V4b, V6, V7 (split DOCTYPE), benign OCI-P session, benign server DOCTYPE flow;
  HTTP port 80: V5 (OCI over SOAP), benign SOAP, benign HTML page (not the plugin's).
