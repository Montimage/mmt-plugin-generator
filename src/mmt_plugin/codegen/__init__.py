"""Code generation (T1.5): the plugin's C header and source.

``generate(model, profile)`` renders the Jinja2 templates
``templates/plugin.h.j2`` and ``templates/plugin.c.j2`` from an analysed
model (``mmt_plugin.semantics``) and an SDK profile (``mmt_plugin.sdk``), and
returns the files in memory: it reads and writes nothing, so the caller
(``mmt-plugin generate``) can render the whole set before writing any of it.
The output is a function of the model and the profile only: no timestamp,
path, version or hash-order leaks into it, so a re-run gives the same bytes.

``mmt_plugin.codegen.cgen`` computes what the templates print; the module
docstring there says how the generated code reads packets.

Template policy (``ENVIRONMENT``): ``StrictUndefined`` (a name the context
does not have is an error, never an empty string), no autoescape (C is not
HTML), ``trim_blocks`` and ``lstrip_blocks`` (a line with only a ``{% tag %}``
leaves nothing behind), ``keep_trailing_newline`` and ``\\n`` newlines.
"""

from __future__ import annotations

from dataclasses import dataclass

import jinja2

from mmt_plugin.codegen.cgen import (
    C_KEYWORDS,
    Context,
    GenerationError,
    Hook,
    build,
    c_int,
    c_name,
    check_defines,
)
from mmt_plugin.diagnostics import Diagnostic
from mmt_plugin.sdk.profile import Profile
from mmt_plugin.semantics.model import AnalysedModel

__all__ = [
    "C_KEYWORDS",
    "DIAGNOSTIC_CODES",
    "ENVIRONMENT",
    "TEMPLATES",
    "GeneratedFile",
    "Generation",
    "GenerationError",
    "Hook",
    "c_int",
    "c_name",
    "generate",
]

#: The codes generation reports (``mmt_plugin.diagnostics.CODES``).
DIAGNOSTIC_CODES = (
    "model.name-collision",
    "model.hook-value",
    "model.integer-length",
    "model.variable-length",
    "model.missing-length",
    "model.type-size",
    "model.out-of-range",
    "model.default-byte-order",
    "model.classifynext-without-encapsulation",
)

#: The templates, by the kind of file they render.
TEMPLATES = {"header": "plugin.h.j2", "source": "plugin.c.j2"}

#: The Jinja2 environment of every template (see the module docstring).
ENVIRONMENT = jinja2.Environment(
    loader=jinja2.PackageLoader("mmt_plugin.codegen", "templates"),
    undefined=jinja2.StrictUndefined,
    autoescape=False,
    trim_blocks=True,
    lstrip_blocks=True,
    keep_trailing_newline=True,
    newline_sequence="\n",
    auto_reload=False,
)


@dataclass(frozen=True)
class GeneratedFile:
    """One generated file: its name (no directory) and its text."""

    name: str
    text: str

    @property
    def data(self) -> bytes:
        """The bytes written: UTF-8 (the text is ASCII)."""
        return self.text.encode("utf-8")


@dataclass(frozen=True)
class Generation:
    """What ``generate`` returns.

    ``files`` are sorted by name; ``hooks`` are the functions the user
    defines in ``src/<label>_impl.c``; ``diagnostics`` are the generation
    warnings (errors raise ``GenerationError``).
    """

    label: str
    files: tuple[GeneratedFile, ...]
    hooks: tuple[Hook, ...]
    diagnostics: tuple[Diagnostic, ...]

    def file(self, name: str) -> GeneratedFile:
        """A file by name; ``KeyError`` if it is not generated."""
        for f in self.files:
            if f.name == name:
                return f
        raise KeyError(name)


def _render(name: str, ctx: Context) -> str:
    template = ENVIRONMENT.get_template(name)
    text = template.render(ctx=ctx, **{k: getattr(ctx, k) for k in ctx.__dataclass_fields__})
    # Squeeze the blank lines a conditional block may leave in a row.
    lines: list[str] = []
    for line in text.split("\n"):
        stripped = line.rstrip()
        if stripped == "" and lines and lines[-1] == "":
            continue
        lines.append(stripped)
    return "\n".join(lines).rstrip("\n") + "\n"


def generate(model: AnalysedModel, profile: Profile) -> Generation:
    """Render the header and source of ``model`` for ``profile``.

    Raises ``GenerationError`` (``model.*`` diagnostics, exit 3) when the
    model cannot be generated: two generated names that collide, an integer
    read from more than 8 bytes, a value of a fixed-size SDK type whose
    length is only known per packet.
    """
    ctx, warnings = build(model, profile)
    header = _render(TEMPLATES["header"], ctx)
    source = _render(TEMPLATES["source"], ctx)
    check_defines(model, profile, ctx, (header, source))
    files = sorted(
        (GeneratedFile(ctx.header, header), GeneratedFile(ctx.source, source)),
        key=lambda f: f.name,
    )
    return Generation(ctx.label, tuple(files), ctx.hooks, tuple(warnings))
