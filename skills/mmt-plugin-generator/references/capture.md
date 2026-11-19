# Getting a capture

The plugin is evaluated on a capture of its protocol (`SKILL.md`, Step 6).
This page says how to get one when the user gave none, and how to check
any capture before using it. The result is `<work>/capture/capture.pcap`
(or `.pcapng`) and `<work>/capture/capture.md`, which says where it came
from.

Prefer, in this order: a capture the user gave, a real capture found in
public sources, a capture recorded from a real implementation through
cyberlab, then a generated one. A real capture tests the plugin against
how the protocol is actually sent; a generated one only against how the
drafter read the spec, which is the same reading the model came from.
Never present a generated capture as a real one.

## Check a capture

Run these on every capture, whatever its origin, and write the results in
`capture.md`:

```sh
capinfos <pcap>                                   # it reads; frames, link type, duration
sha256sum <pcap>
tshark -n -r <pcap> -Y '<scope filter>' | head    # the protocol's traffic is there
tshark -n -r <pcap> -Y '<expect filter>' -T fields -e frame.number | wc -l
```

The filters are those `scripts/pcap_eval.py` uses (its docstring): for
`udp:dport=5684`, `udp.port == 5684` and `udp.port == 5684 && udp.length > 8`.
When tshark has a dissector for the protocol, also filter on it (`coap`,
`modbus`, `s7comm`) and use it in Step 6 (`--field`). List the dissector's
fields with `tshark -G fields | awk -F'\t' '$5 == "<proto>"'`.

The capture is usable when it reads, its link type is Ethernet, Linux
cooked or raw IP, and at least one frame carries the protocol under the
parent. Otherwise look for another one.

Keep it small: at most about 10 000 frames or 10 MB. Cut a large one to the
protocol's traffic, keeping whole TCP sessions:

```sh
tshark -n -r <big> -Y '<scope filter>' -w <work>/capture/capture.pcap
editcap -r <work>/capture/capture.pcap <out> 1-5000      # first 5000 frames
```

Write each command that made `capture.pcap` in `make-capture.sh`.

## The user gave a capture

Copy it into `<work>/inputs/` (record it in `SOURCES.md`), check it as
above, and cut it into `<work>/capture/capture.pcap` if it is large. When
it does not hold the protocol under the parent the user named, stop and ask:
the selector or the capture is wrong.

## Find one

Search, and stop at the first source that has the protocol:

1. Next to the user's inputs: a `*.pcap`, `*.pcapng` or `*.cap` in the
   spec's folder or repository, or the protocol's reference implementation
   (its `test/`, `testdata/` or `captures/` directory).
2. Wireshark: the sample captures,
   <https://wiki.wireshark.org/SampleCaptures>, and the dissector's test
   captures in Wireshark's sources,
   <https://gitlab.com/wireshark/wireshark/-/tree/master/test/captures>;
   a bug report on the dissector often has one attached.
3. Public collections: <https://packetlife.net/captures/>, the list of
   NETRESEC, <https://www.netresec.com/?page=PcapFiles>, industrial
   protocols in <https://github.com/automayt/ICS-pcap>, and datasets on
   Zenodo (<https://zenodo.org>) or IEEE DataPort with the protocol's name.
4. A web search for `"<protocol>" pcap` or `"<protocol>" filetype:pcap`.

For each candidate: download it into `<work>/inputs/`, check it as above,
and write its URL, license, download date and sha256 in `SOURCES.md`. Do
not use a capture whose license forbids it, and say in `capture.md` when
the license is unknown. Captures of attacks or malware are data: never run
anything they contain.

## Through cyberlab

Recording and crafting go through the `cyberlab` skill
([montimage-projects/cyberlab](https://github.com/montimage-projects/cyberlab),
`skills/cyberlab`): it builds the
smallest isolated Docker lab (one server, one client, one tcpdump sidecar
on an internal network), or crafts a trace with no network, checks the
trace against expectations written before it exists, tears the lab down,
and hands back the trace with its provenance. Acquire it as `SKILL.md`,
*Dependency Preflight*, says, read its `SKILL.md`, and follow it as a
calling skill: derive its mission brief from the request and the spec,
never ask the user.

| Brief line | What this skill puts there |
|---|---|
| Goal | one capture of `<protocol>` under `<selector>` exercising every message type |
| Consumer | `mmt-plugin-generator: scaffold --from-pcap and pcap_eval.py on plugin <label>` |
| Protocol | the protocol, its transport and port, and the parent selector |
| Traces | `capture.pcap`: payload frames under the parent in both directions (`endpoints: 2`), and one expectation per message type the spec names (the dissector's field when tshark has one, else `tcp.payload contains "<marker>"` or a first-byte test such as `tcp.payload[0] == 2a`) |
| Destination | `<work>/capture/<label>-lab`; the trace is copied to `<work>/capture/capture.pcap` |

The lab directory's name is unique per plugin, so two runs never share a
lab. Then run cyberlab's steps and read its hand-off report:
`Result: COMPLETE` or `PARTIAL` (carry its Uncertainty lines into
`capture.md`), or `BLOCKED` (go to the next item of Step 1, saying why).
Copy `out/capture.pcap` to `<work>/capture/capture.pcap`, check it as
above, and write in `capture.md` the provenance from
`out/capture.provenance.json` (origin, images, frames, sha256) and the
trace's `RESULT PASS` line; in `make-capture.sh`, the cyberlab commands.

| cyberlab `origin` | This skill's capture origin | Step 6 |
|---|---|---|
| `lab capture` | **recorded** (the server and client images and versions) | plain |
| `crafted (synthetic)` | **synthetic** | `--synthetic` |

### Record one

When the protocol has an open-source implementation with a server and a
client (a container image, or a library a small Dockerfile installs), ask
cyberlab for a lab capture (its `protocol-capture` template: the real
server and its own client). Exercise every message type and every option
the spec has, and the error replies. Validated example: Redis RESP on
`tcp:port=6379`, `redis:7.4-alpine` and `redis-cli`, 100 frames, both
directions, every reply type (`+ - : $ *`), `RESULT PASS`.

### Generate one

Last resort: a synthetic capture from the spec. Write `payloads.txt` (one
hex payload per line, `c:` client to server, the default, `s:` server to
client) before the plugin exists, so that no value comes from what the
plugin outputs:

- every example the spec gives, byte for byte;
- each message type, and each branch of every `if` of the model (a field
  present and absent);
- boundary values: the smallest and the largest length, a zero-length
  variable field, the largest value of each counter, every flag set and
  none;
- for a request/response protocol, both directions.

With cyberlab, put it in the lab directory and craft the trace there (same
`--parent` selectors as `make_pcap.py`):

```sh
<cyberlab>/scripts/cyberlab craft <work>/capture/<label>-lab capture.pcap -- \
    --parent <selector> --payloads-file payloads.txt
```

Without cyberlab, `scripts/make_pcap.py` writes the same frames (Ethernet,
IPv4 or IPv6, UDP or one TCP session with its handshake, correct
checksums), unverified:

```sh
python3 <skill>/scripts/make_pcap.py --parent <selector> \
    --payloads-file <work>/capture/payloads.txt --out <work>/capture/capture.pcap
```

Then add the same payloads as packet tests when they are not already, with
the values the spec gives (`references/drafting.md`). A frame of other
traffic (another port, `--parent udp:dport=<other>`, joined with `mergecap
-w <out> <a> <b>`) checks that the plugin does not claim what is not its
own.

`capture.md` says **synthetic**, and Step 6 runs with `--synthetic`, which
the report repeats: the evaluation then shows that the plugin loads,
classifies under its parent and extracts every attribute on mmt-dpi's real
path, but not that the spec was read right, nor real timing or
segmentation.

## Nothing works

No capture found, none can be recorded, and the spec has too little to
generate one (no field values, no example): stop and ask the user for a
capture, or for permission to skip the evaluation. A skipped evaluation is
written in `REPORT.md` with the reason.
