"""PDL v1: the legacy protocol description language, parsed into a typed model.

``parse(text, filename=...)`` returns a ``Model`` (``mmt_plugin.pdl.model``)
or raises ``PdlSyntaxError``, whose ``diagnostics`` carry ``model.syntax.*``
codes (exit code 3). Parsing only checks syntax; the semantic passes (T1.3)
check names, layouts and values.
"""

from mmt_plugin.pdl.model import Model, Span
from mmt_plugin.pdl.parser import STDIN, PdlSyntaxError, parse

__all__ = ["STDIN", "Model", "PdlSyntaxError", "Span", "parse"]
