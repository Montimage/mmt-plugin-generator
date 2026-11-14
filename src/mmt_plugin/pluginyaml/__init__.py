"""``plugin.yaml``: the canonical model format (plan task T3.1, #24).

``load(text, filename=...)`` reads a ``plugin.yaml`` into the typed model of
``mmt_plugin.pdl.model``, which the semantic passes and code generation read
for both formats, or raises ``PluginYamlError`` (a ``PdlSyntaxError``) with
``model.yaml``, ``model.schema`` or ``model.syntax.*`` diagnostics,
each at the line and column of its node. ``dumps(analysed)`` writes an
analysed model (of either format) as ``plugin.yaml``. The format is defined
by its JSON Schema, ``mmt_plugin/schemas/model/v1/plugin.json``
(``SCHEMA_PATH``), and described in ``docs/plugin-yaml.md``.
"""

from mmt_plugin.pluginyaml.dump import dumps, to_document
from mmt_plugin.pluginyaml.load import (
    DIAGNOSTIC_CODES,
    PluginYaml,
    PluginYamlError,
    load,
    profile_pin,
)
from mmt_plugin.pluginyaml.schema import SCHEMA_PATH, load_schema

__all__ = [
    "DIAGNOSTIC_CODES",
    "SCHEMA_PATH",
    "PluginYaml",
    "PluginYamlError",
    "dumps",
    "load",
    "load_schema",
    "profile_pin",
    "to_document",
]
