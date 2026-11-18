#!/bin/bash
# Rebuilds capture.pcap: the 11 crafted pcaps of gen_pcaps.py (synthetic), one after the other, each file's client
# port moved to 50000+k (gen_pcaps.py gives attack_v2 and attack_v4 the same port 41019: merged as they are, the second
# would read as a retransmission of the first). Run in the rulegen container (Scapy), worktree at /pg:
#   docker exec rulegen bash /pg/ocip-plugin/capture/make-capture.sh
set -euo pipefail
d=$(mktemp -d)
python3 /pg/ocip-plugin/inputs/gen_pcaps.py "$d" >/dev/null
python3 - "$d" /pg/ocip-plugin/capture/capture.pcap <<'PY'
import glob, os, sys
from scapy.all import rdpcap, wrpcap, TCP, IP
d, out = sys.argv[1], sys.argv[2]
files = sorted(glob.glob(os.path.join(d, "attack_v*.pcap"))) + sorted(glob.glob(os.path.join(d, "benign_*.pcap")))
pk, t = [], 1763390000.0
for k, f in enumerate(files):
    ports = {}
    for p in rdpcap(f):
        if TCP in p:
            for side in ("sport", "dport"):
                v = getattr(p[TCP], side)
                if v not in (2208, 80):
                    setattr(p[TCP], side, ports.setdefault(v, 50000 + 10 * k + len(ports)))
            del p[TCP].chksum, p[IP].chksum
        p.time = t; t += 0.01
        pk.append(p)
wrpcap(out, pk)
print(len(files), "files:", " ".join(os.path.basename(f) for f in files))
PY
rm -rf "$d"
capinfos -c -M /pg/ocip-plugin/capture/capture.pcap
