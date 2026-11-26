## Q1: cyberlab is unavailable (no CYBERLAB_DIR, no asm): may I use a synthetic capture generated with scripts/make_pcap.py?
Recommended: Yes: generate a synthetic capture with make_pcap.py, labelled synthetic everywhere.
Taken: allow a synthetic capture (the request grants it)

## Q2: The spec's `readings` is a per-session 32-bit counter that is not in the packet, and gives no rules for when it is updated or reported. Should the hook compute it (needs session-state machinery) or just report it absent?
Recommended: Declare the attribute (MMT_U32_DATA, hook-extracted) and have the hook return 0 (absent) until the spec says how the session counter is kept.
Taken: Declare the attribute (MMT_U32_DATA, hook-extracted) and have the hook return 0 (absent) until the spec says how the session counter is kept.

