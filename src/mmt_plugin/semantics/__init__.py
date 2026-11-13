"""The semantic passes (T1.3): from a parsed PDL model to an analysed model.

``analyse(model, profile=...)`` resolves names and types, lays out structs
and bitfields, folds constant expressions and validates the model, and
returns ``(AnalysedModel | None, diagnostics)``. The analysed model
(``mmt_plugin.semantics.model``) is what code generation (T1.5) reads. It
reads no file and detects no SDK: the SDK facts come from the profile.

The package is named for what it adds to the parser's syntax tree, the
model's meaning; it is not part of ``mmt_plugin.pdl`` because that meaning,
and the analysed model, do not depend on the PDL v1 syntax (plugin.yaml,
T3.1, describes the same protocols).
"""

from mmt_plugin.semantics.analyse import HINTS, SDK_CONFLICT_CODES, THIRD_PARTY_IDS, analyse
from mmt_plugin.semantics.model import AnalysedModel

__all__ = ["HINTS", "SDK_CONFLICT_CODES", "THIRD_PARTY_IDS", "AnalysedModel", "analyse"]
