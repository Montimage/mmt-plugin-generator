"""The documentation's links resolve (plan task T5.2, #29).

Every relative link of every tracked Markdown file names a file or a
directory of the repository, and every ``#anchor`` (in the same file or in
another Markdown file) names one of its headings, with GitHub's anchors.
Offline: ``http(s)://`` and ``mailto:`` links are not followed.
"""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote

import pytest

from mmt_plugin.pluginyaml.reference import slug

from .mdtext import ROOT, fenced_spans, tracked_markdown

#: ``[text](target)`` and ``![alt](target)``, the target without a title.
_INLINE = re.compile(r"!?\[(?:[^\[\]]|\[[^\[\]]*\])*\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")
#: ``[label]: target`` reference definitions.
_REFERENCE = re.compile(r"^ {0,3}\[[^\]]+\]:\s*<?(\S+?)>?(?:\s+.*)?$", re.MULTILINE)
_HEADING = re.compile(r"^ {0,3}(#{1,6})\s+(.*?)\s*#*\s*$", re.MULTILINE)
_EXPLICIT_ANCHOR = re.compile(r"<a\s+(?:name|id)=\"([^\"]+)\"", re.IGNORECASE)
_EXTERNAL = re.compile(r"^(?:[a-z][a-z0-9+.-]*:|//)", re.IGNORECASE)


def _prose(text: str) -> str:
    """``text`` with its fenced code blocks and code spans blanked out."""
    chars = list(text)
    for start, end in fenced_spans(text):
        for i in range(start, end):
            if chars[i] != "\n":
                chars[i] = " "
    blanked = "".join(chars)
    return re.sub(r"(`+)(?:(?!\1).)+?\1", lambda m: " " * len(m.group(0)), blanked)


def anchors(text: str) -> set[str]:
    """The anchors GitHub gives the headings of ``text`` (duplicates get ``-1``,
    ``-2``, ...), plus explicit ``<a id>`` anchors."""
    found: set[str] = set()
    counts: dict[str, int] = {}
    for match in _HEADING.finditer(_prose_keep_code(text)):
        base = slug(re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", match.group(2)))
        n = counts.get(base, 0)
        counts[base] = n + 1
        found.add(base if n == 0 else f"{base}-{n}")
    found.update(_EXPLICIT_ANCHOR.findall(text))
    return found


def _prose_keep_code(text: str) -> str:
    """``text`` without its fenced blocks (a ``#`` line in a block is no heading)."""
    chars = list(text)
    for start, end in fenced_spans(text):
        for i in range(start, end):
            if chars[i] != "\n":
                chars[i] = " "
    return "".join(chars)


def links(text: str) -> list[tuple[int, str]]:
    """Each link target of ``text`` outside code, with its line number."""
    prose = _prose(text)
    found = [(m.start(1), m.group(1)) for m in _INLINE.finditer(prose)]
    found += [(m.start(1), m.group(1)) for m in _REFERENCE.finditer(prose)]
    return [(prose.count("\n", 0, pos) + 1, target) for pos, target in sorted(found)]


def broken_links(path: Path, root: Path = ROOT) -> list[str]:
    """What is wrong with the links of the Markdown file ``path``, a file of
    the repository ``root``."""
    text = path.read_text(encoding="utf-8")
    problems: list[str] = []
    for line, target in links(text):
        if _EXTERNAL.match(target):
            continue
        file_part, _, anchor = target.partition("#")
        dest = (path.parent / unquote(file_part)).resolve() if file_part else path
        where = f"{path.relative_to(root)}:{line}: {target}"
        if not dest.exists():
            problems.append(f"{where}: no such file")
            continue
        try:
            dest.relative_to(root.resolve())
        except ValueError:
            problems.append(f"{where}: outside the repository")
            continue
        if anchor:
            if dest.suffix != ".md" or not dest.is_file():
                problems.append(f"{where}: an anchor into a file that is not Markdown")
            elif unquote(anchor) not in anchors(dest.read_text(encoding="utf-8")):
                problems.append(f"{where}: no heading with this anchor")
    return problems


@pytest.mark.parametrize("path", tracked_markdown(), ids=lambda p: str(p.relative_to(ROOT)))
def test_every_link_resolves(path: Path) -> None:
    assert broken_links(path) == []


def test_the_user_docs_are_checked() -> None:
    names = {str(p.relative_to(ROOT)) for p in tracked_markdown()}
    assert {
        "README.md",
        "docs/user-guide.md",
        "docs/model-reference.md",
        "docs/migration.md",
    } <= names


def test_a_broken_link_or_anchor_is_found(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "user-guide.md").write_text("# Guide\n\n## Install\n", encoding="utf-8")
    (docs / "plugin-yaml.md").write_text("# plugin.yaml\n", encoding="utf-8")
    (tmp_path / "outside.md").write_text("# Out\n", encoding="utf-8")
    page = docs / "probe.md"
    page.write_text(
        "# Title\n\n## A `code` heading\n\n## A `code` heading\n\n"
        "[ok](#title) [ok](#a-code-heading-1) [ok](user-guide.md#install) [ok](../outside.md)\n"
        "[gone](no-such-file.md) [bad](#nowhere) [bad](plugin-yaml.md#nowhere)\n"
        "[web](https://example.org/#x) `[code](not-a-link.md)`\n\n"
        "```\n[fenced](not-a-link.md)\n# not a heading\n```\n"
        "[up](../../escape.md)\n",
        encoding="utf-8",
    )
    assert broken_links(page, tmp_path) == [
        "docs/probe.md:8: no-such-file.md: no such file",
        "docs/probe.md:8: #nowhere: no heading with this anchor",
        "docs/probe.md:8: plugin-yaml.md#nowhere: no heading with this anchor",
        "docs/probe.md:15: ../../escape.md: no such file",
    ]
    assert "not-a-heading" not in anchors(page.read_text(encoding="utf-8"))


def test_github_anchors() -> None:
    assert slug("`classify_next.cases[]`") == "classify_nextcases"
    heading = "9. Config strategy (precedence: CLI > env)"
    assert slug(heading) == "9-config-strategy-precedence-cli--env"
    assert anchors("# A\n## A\n## A\n") == {"a", "a-1", "a-2"}
