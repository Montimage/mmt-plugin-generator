# Migrating from the Java generator

The Java tool (`MMTPluginGenerator.jar`, 2015) turned a PDL v1 model into a
C header and source that you then edited, compiled and copied by hand.
`mmt-plugin` replaces it with a project that it generates, builds, tests and
installs; the C it generates means the same to mmt-dpi as the Java tool's,
apart from the changes listed in
[`behaviour-changes.md`](behaviour-changes.md). This page shows how to move
a model and its hand-written code over. Install `mmt-plugin` first
([user guide](user-guide.md#install-mmt-plugin)); the commands run from the
root of a checkout of this repository.

## What maps to what

| With the Java tool | With mmt-plugin |
|---|---|
| A PDL v1 model file (`tpkt_plugin`) | `plugin.yaml` in a project ([format](plugin-yaml.md), [reference](model-reference.md)); `mmt-plugin import` converts a PDL v1 model, and every command still reads PDL v1 |
| `java -jar MMTPluginGenerator.jar MODEL OUT` | `mmt-plugin generate` (into `generated/`, with `plugin.lock`) |
| Editing the generated C (classification, extraction, `init_<l>_proto_struct`) | The hooks in `src/<label>_impl.c`, which `generate` never writes; `parents:` in the model for a parent with a fixed header |
| `gcc -fPIC -shared -o x.so -I .../dpi/include x.c` | `mmt-plugin build`, with fixed flags and `-Wall -Wextra -Werror` |
| Checking the plugin with `proto_attributes_iterator` | `mmt-plugin test` on packet tests, `--sanitize` for ASan and UBSan |
| `cp x.so /opt/mmt/plugins/` | `mmt-plugin install` into a prefix you can write, with a manifest; `mmt-plugin doctor` to see what mmt-dpi loads |
| Choosing an id and a name by hand | `validate` checks them against the SDK and the installed plugins; `init` picks a free id from 950 to 999 |

## Move a model

Create a project for it, with the label and id it will have, then convert
the model into it. The Java tool's tpkt model, kept in the test corpus as
`tests/corpus/models/tpkt/model.pdl`, is the example:

<!-- doc:run no-sdk -->
```sh
mmt-plugin init tpkt_port --id 970 --sdk-profile 1.10.2
mmt-plugin -C tpkt_port import tests/corpus/models/tpkt/model.pdl -o tpkt_port/plugin.imported.yaml
```

`init` wrote a sample model, `tpkt_port/plugin.yaml`; `import` writes the
converted one next to it, `tpkt_port/plugin.imported.yaml` (it never
replaces a file with other content unless you pass `--force`). It warns, with a code that starts
with `model.legacy-`, about every construct whose meaning depended on a bug
of the Java tool, and says what the Java tool did; `--strict` makes them
errors. Here it is `model.legacy-sdk-conflict`, twice: the label TPKT is
mmt-dpi 1.10.2's own TPKT (`PROTO_TPKT`, id 637), and the id 636 is
`PROTO_LOOPBACK`'s. The table in
[`plugin-yaml.md`](plugin-yaml.md#from-pdl-v1) lists every warning, the Java
bug behind it and what to do. Any other model error stops `import` (exit 3)
and writes nothing.

Then make the converted model the project's, in place of `init`'s sample
model, fix what the warnings say and finish it. Give it the project's label
and id, pin the profile (as `init`'s did), and drop `init`'s test (it
describes `init`'s own 4-byte header):

<!-- doc:run no-sdk -->
```sh
mv tpkt_port/plugin.imported.yaml tpkt_port/plugin.yaml
sed -e 's/^  label: .*/  label: tpkt_port/' -e 's/^  id: .*/  id: 970/' tpkt_port/plugin.yaml > tpkt_port/plugin.yaml.new
mv tpkt_port/plugin.yaml.new tpkt_port/plugin.yaml
printf 'sdk:\n  profile: "1.10.2"\n' >> tpkt_port/plugin.yaml
rm tpkt_port/tests/tpkt_port-basic.yaml
mmt-plugin -C tpkt_port validate --no-sdk
mmt-plugin -C tpkt_port generate
```

What else usually changes:

- **The label and the id.** Most of the Java tool's models reuse a name or an id
  that mmt-dpi 1.10.x has, which `generate` refuses (`model.id-taken`,
  `model.name-taken`). Third-party plugins use ids 950 to 999.
- **The parents.** PDL v1 had no way to say what a protocol runs on, so the
  Java output attached nothing, or you attached it by hand. Declare them in
  `parents:`: with `classify` the generated code attaches the protocol
  (under `tcp`, by port: `classify: {port: 102}`), without it
  `<label>_hook_register_parents` does.
- **Hand edits to the generated C** move to the hooks of
  `src/<label>_impl.c`. Write the classification of a parent with a
  variable-length header that a port does not say (IPv4, TCP by content
  alone), the extraction of an attribute
  without `offset`, and the session or context code there. `build` names
  each hook that is missing (`build.missing-hook`).
- **Packet tests.** Write one or more `tests/*.yaml` with the values the
  specification gives (the [user guide](user-guide.md#packet-tests) has the
  format). `scaffold --from-pcap` drafts them from a capture.

The Java tool's 16 example models are all ported this way in
[`examples/`](../examples/README.md), which lists what each port changed;
`examples/tpkt/` is the finished version of the project above, with its
parent hook and packet tests:

<!-- doc:run sdk -->
```sh
mmt-plugin -C examples/tpkt test
```

## Generate without a project

To use `mmt-plugin` as the jar was used, from a model file to two C files,
give `generate` the model and an output directory. It writes the header,
the source and `plugin.lock` there, and needs no installed SDK when the
profile is given:

<!-- doc:run no-sdk -->
```sh
mmt-plugin generate tests/corpus/models/ndn/model.pdl -o ndn-out --sdk-profile 1.10.2
```

The output is not meant to be edited: a model whose code needs hooks is
better served by a project, where the hooks live in `src/`.

## What behaves differently

[`behaviour-changes.md`](behaviour-changes.md) lists every difference, each
with the Java bug it fixes (numbered in the
[inventory](legacy/java-generator-inventory.md#5-bugs-and-limitations)) and
the test that pins it. The ones you are most likely to notice:

- The generated C compiles against mmt-dpi 1.10.2 for every model (the Java
  output did for 4 of its 16 example models), and each attribute is read
  only from bytes inside the captured packet.
- An id or a name that the SDK already has is an error, not a plugin that
  fails to load.
- `register_protocol_stack` is never generated (the Java tool registered
  every plugin as a protocol stack that claimed every packet).
- The registration function returns 1 only when the protocol and every
  attribute register.
- Bitfields are numbered from the most significant bit of their unit, in
  the model's byte order, not in the C compiler's order.
- Constant folding is right: `val(x) - 4` is not -4, comparisons are not
  `!=`, `ntohs` swaps bytes, and `sizeof` is the type's size.
- A model error is exit 3 with a located diagnostic, and nothing is
  written; the jar always exited 0. A missing output directory is created
  (the jar printed `Error in writing to file` and exited 0), and a
  generated file edited by hand is not overwritten without `--force`.
- The file names (`<label>_mmt_plugin.h` and `.c`), the macro names and the
  `init_<l>_proto_struct()` and `init_proto()` entry points are the Java
  tool's.

## The Java tool

The jar and its sources were removed in #31 (plan task T5.4), once
`mmt-plugin` was shown to match it; they are in `legacy/` at commit
4076899 if you need them. What the tests still compare with is frozen in
`tests/java-output/`: the record of the jar's last run on every example
model, and its C output for the 4 models whose output compiled, which the
parity test (`tests/unit/generate/test_parity.py`) compares with
`mmt-plugin`'s.

The example models and their hand-written C, in `plugins/`, were removed
in #78: the ported projects in `examples/` replace them, and the test
corpus keeps the 16 models, byte for byte, as
`tests/corpus/models/<name>/model.pdl`. They are in `plugins/` at commit
f081d43;
[`examples/README.md`](../examples/README.md#the-java-tools-c-sources)
says which C each port replaces and why the rest has no port.
