# Evaluating the plugin on the capture

Packet tests check the bytes the drafter chose, one packet at a time,
through the test harness. The capture evaluation runs the built plugin the
way mmt-dpi loads it, on every frame of `<work>/capture/capture.pcap`, and
checks three things: that mmt-dpi classifies the protocol's frames as the
plugin (and nothing else), that the plugin extracts its attributes there,
and, when tshark has a dissector for the protocol, that each value is
tshark's.

`mmt-plugin run` (the CLI's own command) gives the first look: the
protocol paths with their packet counts and, per attribute, the packets
that have it, through mmt-dpi's stack, in constant memory, without libpcap
or tshark. The evaluation below adds what `run` does not measure: the
frames that should be the protocol (recall), the foreign ones, the
displaced paths and the field values against tshark.

## Run it

After a green loop run (`SKILL.md`, "Done" criteria for the loop), with
the same SDK and compiler:

```sh
python3 <skill>/scripts/pcap_eval.py --sdk <prefix> --cc <cc> \
    --plugin <project>/build/mmtp_<label>.so --label <label> --parent <selector> \
    --capture <work>/capture/capture.pcap --out <work>/eval \
    [--field <attribute>=<tshark field> ...] [--decode-as <rule>] [--synthetic]
```

- `<skill>` is this skill's directory.
- `--field` once per attribute that a tshark field also gives, e.g.
  `--field length=tpkt.length`. tshark's dissector has to be on the frames:
  for a port tshark does not know, add `--decode-as 'udp.port==5684,coap'`.
  The agreement must be 100 % by default (`--min-agreement`).
- `--synthetic` when `capture.md` says synthetic.
- `--expect-filter` and `--scope-filter` replace the filters made from
  `--parent` when they do not fit, e.g. a protocol that only some payloads
  on its port carry: `--expect-filter 'udp.port == 5684 && data.data[0] == 0x12'`.
  Write why in `notes.md`.
- Without tshark, the expected frames come from the `mmt_plugin` package
  (run the script with the Python that has it, `uv run python` in a
  checkout), and the scope (foreign frames) is not measured. `--field` needs
  tshark.

It compiles `scripts/pcap_eval.c` against the SDK (it needs the libpcap
headers, `libpcap-dev`), links the SDK's plugins into
`<work>/eval/baseline-plugins/` and, with a copy of the plugin, into
`<work>/eval/plugins/`, runs the capture once with the SDK's plugins alone
and once with the plugin, and writes `report.md` and `report.json`. It
never writes under `--sdk`: an SDK plugin with the plugin's file name (a
copy installed there) is left out of both runs, with a warning. It
prints one line and exits:

| Exit | Meaning | What to do |
|---|---|---|
| 0 | PASS | Read every warning in `report.md`; explain each in `REPORT.md`. |
| 1 | FAIL | Fix each problem (below), then run the loop and the evaluation again. |
| 2 | usage | A wrong argument, a missing file, a filter tshark rejects: fix the command. |
| 3 | environment | No compiler, no libpcap headers, not an SDK prefix, a capture libpcap cannot read: fix it or say it in `REPORT.md`; never change the model for it. |

## What the report measures

- `expected`: frames that carry the protocol (`--expect-filter`).
- `claimed`: frames in which mmt-dpi puts the plugin's protocol in the
  path. Over TCP, mmt-dpi classifies a session: the handshake and the
  empty ACKs of a claimed session are claimed too, which is why the scope
  filter has no payload condition.
- `recall`: expected frames that are claimed, at least `--min-recall`
  (0.95).
- `foreign_frames`: claimed frames outside the scope; none by default
  (`--max-foreign`).
- `hollow_frames` (a warning): claimed frames with no protocol bytes in
  which the plugin still reports attribute values.
- `fields`: frame by frame, the plugin's value against tshark's first
  occurrence of the field (integers by value, bytes as hex).
- `attributes`: for each of the model's attributes, the packets that have
  it and its most frequent values. An attribute never extracted is a
  warning.
- `paths.displaced` (a warning): protocol paths that lost packets when the
  plugin was loaded, other than `*.unknown`: the plugin takes packets that
  mmt-dpi classified as something else.

## Fixing a FAIL

Fix one problem per run, as in the loop, and keep every packet test (Rule
9). After a fix, run the loop until green, then the evaluation again. Write
each evaluation run in `runs/run-<n>/notes.md` with the loop run it
follows.

| Problem | Where to look | Usual fix |
|---|---|---|
| mmt-dpi crashed with the plugin | the frame: run the plugin's packet bytes as a packet test with `test --sanitize` | a length or a condition of a variable-length attribute, or the user code |
| the plugin did not register a protocol | `mmt-plugin --json doctor --sdk <prefix>`; the load order | the label must sort after `libmmt_tcpip.so`; `register_parents` returns 1 |
| the capture has no expected frame | `tshark -r <pcap> -Y '<scope filter>'` | the capture or the selector is wrong (Step 1): never the model |
| recall below the minimum | a missed frame: `tshark -n -r <pcap> -Y 'frame.number == <n>' -x` | the parent's `classify` (port, direction, offset) or `<label>_hook_register_parents`; a TCP session captured without its start |
| claimed frames outside the scope | a foreign frame, as above | `classify` matches too much: add a match, or check a magic value in the classification hook |
| a field below the agreement | the mismatches in `report.json` (`fields.<attr>.mismatches`) against the spec | the attribute's offset, type, length or bit order in `plugin.yaml` |

For a field mismatch, first decide from the spec which side is right:
tshark's dissector can be wrong, or describe the field otherwise (a
different unit, a masked value). When the plugin is wrong, take the
frame's protocol bytes (`tshark -x`), write them as a new packet test,
`tests/<label>-capture-<frame>.yaml`, with the values the spec gives (never
the plugin's), and fix the model: the loop shows the fix, and the test
keeps it. When tshark is wrong or differs by design, drop that `--field`
and write why in `REPORT.md`.

Stop after 3 evaluation runs that fail with the same problem, and report
the last `report.md`.

## Warnings

A PASS with warnings is reported with each warning explained:

- `synthetic capture`: say what the evaluation does not show (`capture.md`).
- `attributes never extracted`: an attribute in a branch the capture never
  takes, a session attribute, or one the plugin fails to extract. Say
  which; for the last, it is a FAIL in all but name: fix it.
- `hollow frames`: the plugin reports values in frames that carry none of
  its bytes (often the empty ACKs of a TCP session it claimed). Look at the
  values in `frames.jsonl`: values read from beyond the payload are a bug;
  guard the attribute (an `if` in the model, or a length check in its
  hook).
- `the plugin takes packets mmt-dpi classified before`: say which, and
  whether that is meant (a protocol that mmt-dpi labelled generically,
  such as `http` for WebSocket) or a `classify` that is too broad.
