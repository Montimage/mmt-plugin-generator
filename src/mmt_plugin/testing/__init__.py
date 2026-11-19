"""``mmt-plugin test`` (plan T2.4): packet tests, the host harness, and the
random packets of ``--sanitize``.

- ``mmt_plugin.testing.yamlsubset``: the strict YAML subset the packet tests
  are written in (``tests/corpus/README.md``, "File format");
- ``mmt_plugin.testing.packets``: a packet test (corpus schema 1) and the
  check of what the harness saw against it;
- ``mmt_plugin.testing.fuzz``: the seeded truncated and random packets;
- ``mmt_plugin.testing.harness``: the generated C harness, the empty
  baseline plugin of ``--bench``, and running the harness.

The command itself is ``mmt_plugin.commands.test``.
"""
