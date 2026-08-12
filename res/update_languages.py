"""Refresh the LANGUAGES table of src/lucio/languages.py from highlight.js.

Run it through ``make update-languages``. Only the ``LANGUAGES = frozenset(...)`` literal
is rewritten: the docstrings and the comment above it are hand-written and left alone.

:copyright: Copyright (C) 2026 Alberto Pettarin
:license: GNU General Public License v3.0 (see the LICENSE file for details)
"""

import ast
import re
import sys
from pathlib import Path

import requests

END_MARKER = "<!-- LANGLIST_END -->"
INDENT = " " * 8
START_MARKER = "<!-- LANGLIST -->"
TARGET = Path(__file__).resolve().parent.parent / "src" / "lucio" / "languages.py"
TIMEOUT = 30
URL = (
    "https://raw.githubusercontent.com/highlightjs/highlight.js/"
    "refs/heads/main/SUPPORTED_LANGUAGES.md"
)
WIDTH = 96
"""The column the aliases are wrapped at, narrower than the 100 the linter allows."""

_LITERAL_RE = re.compile(r"^LANGUAGES = frozenset\(\n.*?^\)$", re.DOTALL | re.MULTILINE)


class UpdateError(Exception):
    """Something the script cannot do anything about, reported instead of a traceback."""


def current_aliases(text: str) -> set[str]:
    """Return the aliases the target file holds today, read out of its literal."""
    match = _LITERAL_RE.search(text)
    if match is None:
        raise UpdateError(f"no 'LANGUAGES = frozenset(...)' literal in {TARGET}")
    braces = match.group().partition("(")[2].rpartition(")")[0]
    return set(ast.literal_eval(braces.strip()))


def fetch_table(url: str) -> str:
    """Return the Markdown document listing the languages, as upstream serves it."""
    try:
        response = requests.get(url, timeout=TIMEOUT)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise UpdateError(f"cannot fetch {url}: {exc}") from exc
    return response.text


def format_literal(aliases: set[str]) -> str:
    """Return the frozenset literal, its aliases sorted and wrapped at WIDTH columns."""
    tokens = [f'"{alias}",' for alias in sorted(aliases)]
    tokens[-1] = tokens[-1].removesuffix(",")
    lines: list[str] = []
    current = ""
    for token in tokens:
        candidate = f"{INDENT}{token}" if not current else f"{current} {token}"
        if len(candidate) > WIDTH:
            lines.append(current)
            current = f"{INDENT}{token}"
        else:
            current = candidate
    lines.append(current)
    body = "\n".join(lines)
    return f"LANGUAGES = frozenset(\n    {{\n{body}\n    }}\n)"


def main() -> int:
    """Rewrite the literal of the target file, reporting what changed."""
    try:
        aliases = parse_aliases(fetch_table(URL))
        text = TARGET.read_text(encoding="utf-8")
        current = current_aliases(text)
    except (OSError, UpdateError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if aliases == current:
        print(f"{TARGET.name}: already up to date, {len(current)} aliases")
        return 0
    for alias in sorted(aliases - current):
        print(f"+ {alias}")
    for alias in sorted(current - aliases):
        print(f"- {alias}")

    try:
        TARGET.write_text(
            _LITERAL_RE.sub(lambda _: format_literal(aliases), text, count=1),
            encoding="utf-8",
            newline="\n",
        )
    except OSError as exc:
        print(f"error: cannot write {TARGET}: {exc}", file=sys.stderr)
        return 1
    print(f"{TARGET.name}: {len(current)} aliases -> {len(aliases)}")
    return 0


def parse_aliases(text: str) -> set[str]:
    """Return every alias of the language table, lowercased.

    Only the rows between the two markers are read, which is what leaves the Alias
    Overlap table at the bottom of the document out of the result.
    """
    _, marked, rest = text.partition(START_MARKER)
    table, ended, _ = rest.partition(END_MARKER)
    if not marked or not ended:
        raise UpdateError(f"no {START_MARKER} ... {END_MARKER} table in the document")

    aliases: set[str] = set()
    for line in table.splitlines():
        if not line.startswith("|") or line.startswith(("| :", "| Language")):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) >= 2:
            aliases.update(alias.strip().lower() for alias in cells[1].split(",") if alias.strip())
    if not aliases:
        raise UpdateError("the language table holds no alias")
    return aliases


if __name__ == "__main__":
    sys.exit(main())
