# Legacy Java generator (frozen)

The original MMT plugin generator (2015, NetBeans Ant project), frozen by plan
task T0.5 as the parity baseline for the Python rewrite
(`docs/design/workflow-redesign.md`). Its behaviour is described in
`docs/legacy/java-generator-inventory.md`.

- `src/`, `pdl_grammar/`: Java sources and the ANTLR 3 grammar.
- `lib/`, `nbproject/`, `build.xml`, `manifest.mf`: the NetBeans Ant build.
  Every path in it is relative to this directory.
- `dist/MMTPluginGenerator.jar`: the prebuilt jar (no version string; its
  entries are dated 2015-04-20). It needs a Java 8 runtime.
- `reference-output/`: the jar's output for every `plugins/*_plugin` model.
- `check-reference-output.sh`: regenerates that output and diffs it.

## Reference output

From the repository root, for each model:

```
java -jar legacy/dist/MMTPluginGenerator.jar plugins/<model> <out>/<model>
```

`reference-output/<model>/` holds the generated files, and
`<model>.exit`, `<model>.stdout` and `<model>.stderr` next to it record the
run. `reference-output/MANIFEST` records the jar's sha256, the Java version,
the platform, the date, and one line per model: its status and the sha256 of
each of its files. Status is `ok`, `parse-errors` (files written, stderr not
empty), `no-output` (no file written) or `exit-<n>`. The tool exits 0 even on
errors, so the status comes from stderr and the files.

Check it (exits non-zero on any difference), or regenerate it:

```
bash legacy/check-reference-output.sh            # JAVA=<java 8> to pick one
bash legacy/check-reference-output.sh --write
```

CI runs the check with a pinned Temurin 8u502 JRE.

## Determinism and normalisation

Two runs give byte-identical output, and so do two Java 8 builds (Ubuntu's
OpenJDK 8u502 on aarch64, which wrote the reference, and Temurin 8u502 on
aarch64 and x86_64). The output holds no timestamp or path. Struct blocks are
emitted in `java.util.HashMap` order: that order is fixed for a given model
under Java 8's HashMap, but another HashMap implementation could change it,
so run the check with Java 8. The script sets `LC_ALL=C`, because the tool
lower-cases names with the default locale.

The generated files are compared as they are. The only normalisation is in
the comparison: a model that writes nothing (`ip_plugin`) leaves an empty
output dir, which git cannot store, so the script drops empty dirs before
`diff -r`. `MANIFEST` still lists that model, as `no-output`.
