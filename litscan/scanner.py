"""Literal scanner utilities.

Author: Ron Webb
Since: 1.0.0
"""

from __future__ import annotations

import bisect
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict

from . import LIT_IGNORE_PATH

# Ordered alternation: triple-quoted blocks first (multiline), then single-line
# strings, then decimal numbers, then integers.  String patterns appear first so
# that any digits inside a quoted literal are consumed as part of the string
# match and are never re-matched as standalone numeric literals.
_PATTERN = re.compile(
    r'"""[\s\S]*?"""'
    r"|'''[\s\S]*?'''"
    r'|"(?:[^"\\\n]|\\.)*"'
    r"|'(?:[^'\\\n]|\\.)*'"
    r"|\b\d+\.\d+\b"
    r"|\b\d+\b",
)

# File suffixes treated as Python source (enables docstring detection).
_PYTHON_SUFFIXES: frozenset[str] = frozenset({".py", ".pyi"})

# Pattern used during the pre-scan masking step.  Comments are listed before
# string alternatives so that quote characters appearing inside comment text
# are consumed by the comment pattern first and are never matched as string
# delimiters.
_MASK_PATTERN = re.compile(
    r"#[^\n]*"
    r"|//[^\n]*"
    r"|/\*[\s\S]*?\*/"
    r'|"""[\s\S]*?"""'
    r"|'''[\s\S]*?'''"
    r'|"(?:[^"\\\n]|\\.)*"'
    r"|'(?:[^'\\\n]|\\.)*'",
)


@dataclass(frozen=True)
class LiteralOccurrence:
    """Represents a discovered literal value in source code.

    Author: Ron Webb
    Since: 1.0.0
    """

    file_path: Path
    line: int
    column: int
    value: str


def _build_line_offsets(source: str) -> list[int]:
    """Return a list of character offsets where each line starts (0-indexed).

    The result always begins with ``0`` (start of line 1). Each subsequent
    entry is the offset of the first character on the following line.
    Precomputing this once gives O(log n) line/column lookup per match via
    :func:`_line_and_column`, instead of the naive O(n) slice-and-scan.

    Author: Ron Webb
    Since: 1.0.0
    """
    offsets: list[int] = [0]
    start = 0
    while True:
        pos = source.find("\n", start)
        if pos == -1:
            break
        offsets.append(pos + 1)
        start = pos + 1
    return offsets


def _line_and_column(line_offsets: list[int], offset: int) -> tuple[int, int]:
    """Return 1-based line and 0-based column for a character offset in source.

    *line_offsets* must be the list returned by :func:`_build_line_offsets`.
    Uses :func:`bisect.bisect_right` for O(log n) lookup.

    Author: Ron Webb
    Since: 1.0.0
    """
    line = bisect.bisect_right(line_offsets, offset)
    col = offset - line_offsets[line - 1]
    return line, col


def _load_ignore_patterns(path: Path) -> list[re.Pattern[str]]:
    """Load regex ignore patterns from *path*.

    Lines starting with ``#`` and blank lines are skipped. Each remaining
    line is compiled as a :func:`re.compile` pattern.

    Author: Ron Webb
    Since: 1.1.0
    """
    patterns: list[re.Pattern[str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            patterns.append(re.compile(stripped))
    return patterns


_IGNORE_PATTERNS: list[re.Pattern[str]] = _load_ignore_patterns(LIT_IGNORE_PATH)


def _is_docstring_position(source: str, match_start: int) -> bool:
    """Return ``True`` when a triple-quoted string is in a docstring position.

    A string is considered a docstring when it starts at the beginning of its
    line (only whitespace before it on that line) **and** either:

    * nothing except blank lines or ``#`` comments precedes it in the file
      (module-level docstring), or
    * the previous non-blank, non-comment line ends with ``:`` (function,
      class, ``if``, ``for`` … block opener).

    Author: Ron Webb
    Since: 1.1.0
    """
    # The triple-quote must be the first non-whitespace token on its line.
    line_start = source.rfind("\n", 0, match_start) + 1
    if source[line_start:match_start].strip():
        return False

    # Examine lines above the current line.
    before = source[:line_start]
    if not before.strip():
        return True  # nothing meaningful above → module docstring

    for line in reversed(before.splitlines()):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue  # skip blank lines and # comments
        return stripped.endswith(":")

    # Only blank lines / comments above → module docstring.
    return True


def _mask_non_literals(source: str, suffix: str) -> str:
    """Return *source* with comment and docstring regions replaced by spaces.

    Replaces every non-newline character in each masked region with a space so
    that character offsets (and therefore line/column numbers) remain identical
    to the original source.  Masked regions are:

    * Single-line comments (``#…`` and ``//…``).
    * Block comments including Javadoc (``/* … */``).
    * For ``.py`` / ``.pyi`` files: triple-quoted strings that occupy a
      docstring position (see :func:`_is_docstring_position`).

    Author: Ron Webb
    Since: 1.1.0
    """
    is_python = suffix in _PYTHON_SUFFIXES

    def _replace(match: re.Match[str]) -> str:
        text = match.group()
        if text.startswith(("#", "//", "/*")):
            return "".join(" " if c != "\n" else c for c in text)
        if is_python and text.startswith(('"""', "'''")):
            if _is_docstring_position(source, match.start()):
                return "".join(" " if c != "\n" else c for c in text)
        return text

    return _MASK_PATTERN.sub(_replace, source)


def scan_literals(
    source: str,
    file_path: Path,
    ignore_patterns: list[re.Pattern[str]] | None = None,
) -> list[LiteralOccurrence]:
    """Scan source text and collect string and numeric literals.

    Works with any language or plain text file. Detects:
    - Block strings/text enclosed with triple double or triple single quotes
      (may span multiple lines).
    - Strings/text enclosed with double or single quotes (single line).
    - Decimal and integer numbers.

    When *ignore_patterns* is ``None`` the module-level :data:`_IGNORE_PATTERNS`
    (loaded from ``lit_ignore``) are used. Pass an explicit list to override.

    Author: Ron Webb
    Since: 1.0.0
    """
    active = _IGNORE_PATTERNS if ignore_patterns is None else ignore_patterns
    suffix = file_path.suffix.lower()
    effective_source = _mask_non_literals(source, suffix)
    line_offsets = _build_line_offsets(source)
    occurrences: list[LiteralOccurrence] = []
    for match in _PATTERN.finditer(effective_source):
        value = match.group()
        if any(p.search(value) for p in active):
            continue
        line, column = _line_and_column(line_offsets, match.start())
        occurrences.append(
            LiteralOccurrence(
                file_path=file_path,
                line=line,
                column=column,
                value=value,
            )
        )
    return occurrences


def scan_file(file_path: Path) -> list[LiteralOccurrence]:
    """Read *file_path* from disk and return all literal occurrences found in it.

    Convenience wrapper around :func:`scan_literals` intended for parallel
    execution: a single callable that handles both I/O and scanning so it can
    be submitted directly to a :class:`concurrent.futures.Executor`.

    Author: Ron Webb
    Since: 1.0.0
    """
    contents = file_path.read_text(encoding="utf-8", errors="replace")
    return scan_literals(contents, file_path)


class LiteralGroup(TypedDict):
    """JSON-serialisable representation of a grouped literal.

    Author: Ron Webb
    Since: 1.0.0
    """

    count: int
    literal: str
    files: list[str]


# ScanReport uses the functional TypedDict syntax because "run-date" is not a
# valid Python identifier.  Docstrings are not supported in this form; see the
# individual field names for documentation of the report structure.
ScanReport = TypedDict(
    "ScanReport",
    {
        "application": str,
        "version": str,
        "run-date": str,
        "findings": list[LiteralGroup],
    },
)
