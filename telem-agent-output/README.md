# telem plugin work folder

TELEM (label `telem`, id 963, parent `udp:dport=5684`): green, capture evaluation PASS on a synthetic capture.

## Re-run

Each command is one simple command:

    mmt-plugin -C /work/plugin-work-5c743542/project --json validate --sdk /opt/sdk
    mmt-plugin -C /work/plugin-work-5c743542/project --json generate --sdk /opt/sdk
    mmt-plugin -C /work/plugin-work-5c743542/project --json build --sdk /opt/sdk --cc gcc
    mmt-plugin -C /work/plugin-work-5c743542/project --json test --sdk /opt/sdk --cc gcc

Evaluation (no `--accept`: no drift to accept):

    python3 /tmp/.cache/mmt-plugin-agent/skills-5c743542e33849c7a3e36f1835808c54-d65d3a297c6851a7/mmt-plugin-generator/scripts/pcap_eval.py --sdk /opt/sdk --cc gcc --plugin /work/plugin-work-5c743542/project/build/mmtp_telem.so --label telem --parent udp:dport=5684 --capture /work/plugin-work-5c743542/capture/capture.pcap --out /work/plugin-work-5c743542/eval --synthetic

## Resume

- The `readings` session counter is not implemented (hook returns absent); questions.md Q2 awaits the spec's rules.
- The capture is synthetic; a real capture would test more.
