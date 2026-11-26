#!/bin/sh
python3 /tmp/.cache/mmt-plugin-agent/skills-5c743542e33849c7a3e36f1835808c54-d65d3a297c6851a7/mmt-plugin-generator/scripts/make_pcap.py --parent udp:dport=5684 --payloads-file /work/plugin-work-5c743542/capture/payloads.txt --out /work/plugin-work-5c743542/capture/capture.pcap
