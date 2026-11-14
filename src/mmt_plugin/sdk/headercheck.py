"""Check an SDK profile against the real mmt-dpi headers.

For each header of the profile, one C translation unit includes that header
alone and asserts, with ``_Static_assert`` and ``__builtin_types_compatible_p``
(GCC and Clang), every entry the profile attributes to it:

- a typedef with a ``definition`` is that type; any other type exists;
- a callback's SDK typedef is a pointer to the profile's function type;
- a registration call or helper has the profile's function type and is
  prototyped (an unprototyped ``R f()`` is compatible with any ``R (...)``
  under gnu11, so the unit also asserts that it is not compatible with a
  function of a parameter type no header declares), and a helper that
  ``implements`` a callback converts to that callback's typedef;
- a ``complete`` struct has exactly the listed fields, in order (a mirror
  struct built from the profile has the same size and offsets), and every
  listed field of any struct has the listed type;
- a constant is an integer constant expression, equal to its ``value`` when
  the profile records one, and a macro is defined; the
  logger macros are also called with a format string, once with the debug
  opt-in defined.

One more unit includes ``parents.header`` and every header of
``parents.ids`` and asserts each protocol id; the same unit, preprocessed
(``-E``), shows that each ``PROTO_<X>_ALIAS`` expands to the recorded name.

The units are compiled with ``-std=<c_std> -Wall -Wextra -Werror
-fsyntax-only``, so a deprecated function also fails. Separately, each entry's
name must appear in its header with comments stripped, so the header recorded
is the one that declares it, not one that includes it, and each header of
``parents.ids`` must define no numeric ``PROTO_*`` macro (``PROTO_CLASS_*``
excepted) and no ``PROTO_*_ALIAS`` that the profile does not list, so the
list is complete.

    python -m mmt_plugin.sdk.headercheck --sdk PREFIX [--profile FILE] [--cc CC]

It prints one ``PASS:``/``FAIL:`` line per check and exits 0 when all pass,
1 when one fails, 4 for an SDK error (the ``mmt-plugin`` exit codes).
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import tempfile
from collections.abc import Iterator, Sequence
from dataclasses import dataclass

from mmt_plugin.diagnostics import CliError
from mmt_plugin.sdk.detect import VERSION_HEADER, Sdk, require_sdk
from mmt_plugin.sdk.profile import Profile, ProfileError, get_bundled, load_profile
from mmt_plugin.sdk.resolve import find_bundled

__all__ = [
    "CheckResult",
    "check_profile",
    "declared_names",
    "main",
    "render_ids_unit",
    "render_unit",
]

_COMMENTS = re.compile(r"/\*.*?\*/|//[^\n]*", re.DOTALL)

#: A numeric ``PROTO_*`` macro, in a header with comments stripped.
_NUMERIC_PROTO = re.compile(
    r"^[ \t]*#[ \t]*define[ \t]+(PROTO_\w+)[ \t]+\(?[ \t]*(?:0[xX][0-9A-Fa-f]+|[0-9]+)[uUlL]*"
    r"[ \t]*\)?[ \t]*$",
    re.MULTILINE,
)
#: A ``PROTO_<X>_ALIAS`` macro, in a header with comments stripped.
_ALIAS_PROTO = re.compile(r"^[ \t]*#[ \t]*define[ \t]+(PROTO_\w+)_ALIAS\b", re.MULTILINE)
#: A line of the preprocessed alias unit: ``mmtp_alias_<n>: <expansion>``.
_ALIAS_LINE = re.compile(r"^mmtp_alias_([0-9]+): (.*?)\s*$", re.MULTILINE)

#: Compiler flags; ``-std`` comes from the profile.
WARNING_FLAGS = ("-Wall", "-Wextra", "-Werror", "-fsyntax-only")


@dataclass(frozen=True)
class CheckResult:
    """One check: what it was, whether it passed, and the details if not."""

    name: str
    ok: bool
    detail: str = ""


def _c_string(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _assert(condition: str, message: str) -> str:
    return f"_Static_assert({condition}, {_c_string(message)});"


def _same(a: str, b: str) -> str:
    return f"__builtin_types_compatible_p({a}, {b})"


#: A struct no header declares. Only an unprototyped function type, ``R ()``,
#: is compatible with ``R (struct mmtp_never_ *)``.
_NEVER_TAG = "struct mmtp_never_"


def _never(returns: str) -> str:
    """A pointer to a function that takes a ``_NEVER_TAG`` pointer."""
    return f"{returns} (*)({_NEVER_TAG} *)"


def _entries(profile: Profile, header: str) -> Iterator[str]:
    """The C checks of the entries declared in ``header``."""
    for t in profile.types:
        if t.header != header:
            continue
        if t.definition is None:
            yield f"typedef {t.name} mmtp_chk_type_{t.name};"
        else:
            yield _assert(_same(t.name, t.definition), f"types.{t.name} is not {t.definition}")
    for s in profile.structs:
        if s.header != header:
            continue
        for f in s.fields:
            yield _assert(
                _same(f"__typeof__((({s.name} *)0)->{f.name})", f.type),
                f"structs.{s.name}.{f.name} is not {f.type}",
            )
        if s.layout == "complete":
            mirror = f"mmtp_chk_mirror_{s.name}"
            members = " ".join(f"__typeof__({f.type}) {f.name};" for f in s.fields)
            yield f"struct {mirror} {{ {members} }};"
            yield _assert(
                f"sizeof(struct {mirror}) == sizeof({s.name})",
                f"structs.{s.name} has fields that the profile does not list",
            )
            for f in s.fields:
                yield _assert(
                    f"offsetof(struct {mirror}, {f.name}) == offsetof({s.name}, {f.name})",
                    f"structs.{s.name}.{f.name} is not at its place in the field order",
                )
    for cb in profile.callbacks:
        if cb.header == header:
            yield _assert(
                _same(cb.typedef, cb.pointer_type),
                f"callbacks.{cb.role}: {cb.typedef} is not {cb.pointer_type}",
            )
            yield _assert(
                "!" + _same(cb.typedef, _never(cb.returns)),
                f"callbacks.{cb.role}: {cb.typedef} is not prototyped",
            )
    for kind, functions in (
        ("registrations", profile.registrations),
        ("helpers", profile.helpers),
    ):
        for fn in functions:
            if fn.header != header:
                continue
            yield _assert(
                _same(f"__typeof__({fn.name})", fn.function_type),
                f"{kind}.{fn.name} is not {fn.function_type}",
            )
            yield _assert(
                "!" + _same(f"__typeof__(&{fn.name})", _never(fn.returns)),
                f"{kind}.{fn.name} is not prototyped",
            )
            if fn.implements is not None:
                typedef = profile.callback(fn.implements).typedef
                yield _assert(
                    _same(f"__typeof__(&{fn.name})", typedef),
                    f"{kind}.{fn.name} does not convert to {typedef}",
                )
    for c in profile.constants:
        if c.header == header:
            yield _assert(
                f"(long long)({c.name}) == (long long)({c.name})",
                f"constants.{c.name} is not an integer constant",
            )
            if c.value is not None:
                yield _assert(
                    f"({c.name}) == {c.value}",
                    f"constants.{c.name} is not {c.value}",
                )
    for m in profile.macros:
        if m.header == header:
            error = _c_string(f"macros.{m.name} is not defined")
            yield f"#ifndef {m.name}\n#error {error}\n#endif"
    lg = profile.logger
    if lg.header == header:
        calls = " ".join(
            f"{name}({_c_string(level + ' %d')}, value);"
            for level, name in (
                ("error", lg.error),
                ("warn", lg.warn),
                ("info", lg.info),
                ("debug", lg.debug),
            )
        )
        yield "void mmtp_chk_logger(int value);"
        yield f"void mmtp_chk_logger(int value) {{ (void)value; {calls} }}"
    pa = profile.parents
    if pa.header == header:
        for name in pa.examples:
            yield _assert(
                f"(long long)({name}) == (long long)({name})",
                f"parents.examples: {name} is not an integer constant",
            )


def _extra_headers(profile: Profile, header: str) -> list[str]:
    """Headers a unit also needs: those of the callbacks its helpers implement."""
    extra = []
    for fn in (*profile.registrations, *profile.helpers):
        if fn.header == header and fn.implements is not None:
            other = profile.callback(fn.implements).header
            if other != header and other not in extra:
                extra.append(other)
    return extra


def render_unit(profile: Profile, header: str) -> str:
    """The C translation unit that checks the entries of one header."""
    lines = [
        f"/* mmt_plugin.sdk.headercheck: profile {profile.version}, header {header}. */",
        "#include <stddef.h>",
        f'#include "{header}"',
        *(f'#include "{h}" /* for a callback typedef */' for h in _extra_headers(profile, header)),
        f"{_NEVER_TAG};",
        "",
        *_entries(profile, header),
        "",
    ]
    return "\n".join(lines)


def render_ids_unit(profile: Profile) -> str:
    """The C translation unit that checks ``parents.ids``: one assertion per
    id, then one ``mmtp_alias_<n>: PROTO_<X>_ALIAS`` line per alias, which
    only the preprocessor reads (``#ifdef MMTP_ALIASES``)."""
    pa = profile.parents
    protocols = pa.protocols()
    aliases = [p for p in protocols if p.alias is not None]
    lines = [
        f"/* mmt_plugin.sdk.headercheck: profile {profile.version}, parents.ids. */",
        "#include <stddef.h>",
        f'#include "{pa.header}"',
        *(f'#include "{h.header}"' for h in pa.ids),
        "",
        *(
            _assert(f"({p.macro}) == {p.id}", f"parents.ids.{p.macro} is not {p.id}")
            for p in protocols
        ),
        "",
        "#ifdef MMTP_ALIASES",
        *(f"mmtp_alias_{i}: {p.macro}_ALIAS" for i, p in enumerate(aliases)),
        "#endif",
        "",
    ]
    return "\n".join(lines)


def declared_names(profile: Profile) -> dict[str, list[str]]:
    """Per header, the names that must appear in it (comments stripped)."""
    names: dict[str, list[str]] = {h.name: [] for h in profile.headers}

    def add(header: str, name: str) -> None:
        names.setdefault(header, []).append(name)

    for t in profile.types:
        add(t.header, t.name)
    for s in profile.structs:
        add(s.header, s.name)
    for cb in profile.callbacks:
        add(cb.header, cb.typedef)
    for fn in (*profile.registrations, *profile.helpers):
        add(fn.header, fn.name)
    for c in profile.constants:
        add(c.header, c.name)
    for m in profile.macros:
        add(m.header, m.name)
    add(profile.logger.header, profile.logger.debug_opt_in)
    for name in profile.parents.examples:
        add(profile.parents.declared_in, name)
    for group in profile.parents.ids:
        for p in group.protocols:
            add(group.header, p.macro)
            if p.alias is not None:
                add(group.header, f"{p.macro}_ALIAS")
        for name in group.not_ids:
            add(group.header, name)
    return names


def _read_header(path: str) -> str:
    with open(path, encoding="utf-8", errors="replace") as f:
        return _COMMENTS.sub(" ", f.read())


def _check_declared(profile: Profile, include_dir: str) -> Iterator[CheckResult]:
    for header, names in declared_names(profile).items():
        if not names:
            continue  # the unit that includes it shows that it exists
        path = os.path.join(include_dir, header)
        try:
            text = _read_header(path)
        except OSError as exc:
            yield CheckResult(f"{header}: exists", False, str(exc.strerror or exc))
            continue
        missing = [n for n in names if not re.search(rf"\b{re.escape(n)}\b", text)]
        yield CheckResult(
            f"{header}: declares its {len(names)} profile entries",
            not missing,
            "not declared there: " + ", ".join(missing) if missing else "",
        )


def _check_complete(profile: Profile, include_dir: str) -> Iterator[CheckResult]:
    """Each header of ``parents.ids`` defines no protocol id or alias that
    the profile does not list."""
    for group in profile.parents.ids:
        try:
            text = _read_header(os.path.join(include_dir, group.header))
        except OSError:
            continue  # _check_declared reports it
        listed = {p.macro for p in group.protocols} | set(group.not_ids)
        aliases = {p.macro for p in group.protocols if p.alias is not None}
        missing = [
            *(n for n in _NUMERIC_PROTO.findall(text) if not n.startswith("PROTO_CLASS_")),
            *(f"{n}_ALIAS" for n in _ALIAS_PROTO.findall(text) if n not in aliases),
        ]
        missing = [n for n in dict.fromkeys(missing) if n not in listed]
        yield CheckResult(
            f"{group.header}: parents.ids lists all its protocols ({len(group.protocols)})",
            not missing,
            "not in the profile: " + ", ".join(missing) if missing else "",
        )


def _check_aliases(cc: str, profile: Profile, include_dir: str, source: str) -> CheckResult:
    """Each recorded alias is what its ``PROTO_<X>_ALIAS`` expands to."""
    aliases = [p for p in profile.parents.protocols() if p.alias is not None]
    name = f"parents.ids: {len(aliases)} PROTO_*_ALIAS expand to their names ({cc} -E)"
    ok, output = _run(
        [cc, f"-std={profile.c_std}", "-E", "-P", "-DMMTP_ALIASES", "-I", include_dir, source]
    )
    if not ok:
        return CheckResult(name, False, output)
    found = {int(i): text for i, text in _ALIAS_LINE.findall(output)}
    wrong = [
        f"parents.ids.{p.macro}: {p.macro}_ALIAS is {found.get(i, 'missing')}, not "
        f"{_c_string(p.alias or '')}"
        for i, p in enumerate(aliases)
        if found.get(i) != _c_string(p.alias or "")
    ]
    return CheckResult(name, not wrong, "\n".join(wrong))


def _run(cmd: Sequence[str]) -> tuple[bool, str]:
    """Run a compiler: whether it succeeded, and its stdout when it did, its
    whole output when it did not."""
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=120)
    except OSError as exc:
        return False, f"cannot run {cmd[0]}: {exc.strerror or exc}"
    if proc.returncode == 0:
        return True, proc.stdout
    return False, (proc.stdout + proc.stderr).strip()


def _compile(
    cc: str, profile: Profile, include_dir: str, source: str, defines: Sequence[str]
) -> tuple[bool, str]:
    cmd = [
        cc,
        f"-std={profile.c_std}",
        *WARNING_FLAGS,
        "-I",
        include_dir,
        *(f"-D{d}" for d in defines),
        source,
    ]
    ok, output = _run(cmd)
    return ok, output.strip()


def check_profile(profile: Profile, sdk: Sdk, cc: str = "gcc") -> list[CheckResult]:
    """Run every check of ``profile`` against the headers of ``sdk``."""
    results = [
        CheckResult(
            f"profile {profile.version} is the SDK version ({sdk.version}, from {VERSION_HEADER})",
            find_bundled(sdk.version or "", [profile.version]) is not None,
        )
    ]
    results += _check_declared(profile, sdk.include_dir)
    results += _check_complete(profile, sdk.include_dir)
    flags = " ".join((f"-std={profile.c_std}", *WARNING_FLAGS))
    with tempfile.TemporaryDirectory(prefix="mmtp-headercheck-") as tmp:
        for i, header in enumerate(h.name for h in profile.headers):
            source = os.path.join(tmp, f"check_{i}.c")
            with open(source, "w", encoding="utf-8") as f:
                f.write(render_unit(profile, header))
            runs: list[Sequence[str]] = [()]
            if header == profile.logger.header:
                runs.append((profile.logger.debug_opt_in,))
            for defines in runs:
                ok, output = _compile(cc, profile, sdk.include_dir, source, defines)
                with_defines = "".join(f" -D{d}" for d in defines)
                results.append(
                    CheckResult(
                        f"{header}: entries compile ({cc} {flags}{with_defines})", ok, output
                    )
                )
        if profile.parents.ids:
            source = os.path.join(tmp, "check_ids.c")
            with open(source, "w", encoding="utf-8") as f:
                f.write(render_ids_unit(profile))
            ok, output = _compile(cc, profile, sdk.include_dir, source, ())
            count = len(profile.parents.protocols())
            results.append(
                CheckResult(
                    f"parents.ids: {count} protocol ids compile ({cc} {flags})", ok, output
                )
            )
            results.append(_check_aliases(cc, profile, sdk.include_dir, source))
    return results


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m mmt_plugin.sdk.headercheck",
        description="Check an SDK profile against the headers of an mmt-dpi SDK prefix.",
    )
    parser.add_argument(
        "--sdk",
        metavar="PREFIX",
        help="the SDK prefix (default: detected as by mmt-plugin: MMT_BASE, mmt-dpi.pc, /opt/mmt)",
    )
    parser.add_argument(
        "--profile",
        metavar="FILE",
        help="the profile file to check (default: the bundled profile of the SDK's version)",
    )
    parser.add_argument(
        "--cc", default=os.environ.get("CC") or "gcc", help="the C compiler (default: $CC or gcc)"
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the checks and print one line per check; return the exit code."""
    args = _parser().parse_args(argv)
    try:
        sdk = require_sdk(args.sdk, os.environ)
        if args.profile is not None:
            profile = load_profile(args.profile)
        else:
            found = find_bundled(sdk.version or "")
            if found is None:
                raise CliError(
                    "sdk.profile-not-found",
                    f"no profile is bundled for the SDK's version ({sdk.version})",
                    "pass the profile to check with --profile FILE",
                )
            bundled = get_bundled(found)
            assert bundled is not None
            profile = bundled
    except CliError as exc:
        print(f"FAIL: {exc.message} (hint: {exc.hint})")
        return int(exc.exit_code)
    except ProfileError as exc:
        print(f"FAIL: {exc}")
        return 1
    print(
        f"SDK {sdk.prefix} ({sdk.source.value}), version {sdk.version}; profile {profile.version}"
    )
    results = check_profile(profile, sdk, args.cc)
    for r in results:
        print(f"{'PASS' if r.ok else 'FAIL'}: {r.name}")
        if not r.ok and r.detail:
            for line in r.detail.splitlines():
                print(f"    {line}")
    failed = sum(not r.ok for r in results)
    print(f"{len(results) - failed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
