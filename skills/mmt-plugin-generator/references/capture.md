# Getting a capture

The plugin is evaluated on a capture of its protocol (`SKILL.md`, Step 6).
This page says how to get one when the user gave none, and how to check
any capture before using it. The result is `<work>/capture/capture.pcap`
(or `.pcapng`) and `<work>/capture/capture.md`, which says where it came
from.

Prefer, in this order: a capture the user gave, a real capture found in
public sources, a capture recorded from a real implementation, then a
generated one. A real capture tests the plugin against how the protocol is
actually sent; a generated one only against how the drafter read the spec,
which is the same reading the model came from. Never present a generated
capture as a real one.

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

## Record one

When the protocol has an open-source implementation that runs locally (a
library, a client and a server, a container), run a client against a
server on the loopback interface and capture it:

```sh
dumpcap -i lo -f '<bpf, e.g. udp port 5684>' -a duration:30 -w <work>/capture/capture.pcapng
```

Only when the user can capture without `sudo` (`dumpcap` with capabilities,
or the `wireshark` group): never use `sudo`. Exercise every message type
and every option the spec has. Write the commands and the implementation's
name and version in `make-capture.sh` and `capture.md`.

## Generate one

Last resort: `scripts/make_pcap.py` writes each payload behind the headers
the parent selector names (Ethernet, IPv4 or IPv6, UDP or one TCP session
with its handshake), with correct checksums:

```sh
python3 <skill>/scripts/make_pcap.py --parent <selector> \
    --payloads-file <work>/capture/payloads.txt --out <work>/capture/capture.pcap
```

Write `payloads.txt` from the spec, one hex payload per line, `c:` for
client to server (the default), `s:` for server to client, before the
plugin exists, so that no value comes from what the plugin outputs:

- every example the spec gives, byte for byte;
- each message type, and each branch of every `if` of the model (a field
  present and absent);
- boundary values: the smallest and the largest length, a zero-length
  variable field, the largest value of each counter, every flag set and
  none;
- for a request/response protocol, both directions.

Then add the same payloads as packet tests when they are not already, with
the values the spec gives (`references/drafting.md`). A frame of other
traffic (another port, `--parent udp:dport=<other>`, joined with `mergecap
-w <out> <a> <b>`) checks that the plugin does not claim what is not its
own.

`capture.md` says **synthetic**, and Step 6 runs with `--synthetic`, which
the report repeats: the evaluation then shows that the plugin loads,
classifies under its parent and extracts every attribute on mmt-dpi's real
path, but not that the spec was read right.

## Nothing works

No capture found, none can be recorded, and the spec has too little to
generate one (no field values, no example): stop and ask the user for a
capture, or for permission to skip the evaluation. A skipped evaluation is
written in `REPORT.md` with the reason.
