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

# Ordered alternation: triple-quoted blocks first (multiline), then single-line
# strings, then decimal numbers, then integers.
_PATTERN = re.compile(
    r'"""[\s\S]*?"""'
    r"|'''[\s\S]*?'''"
    r'|"(?:[^"\\\n]|\\.)*"'
    r"|'(?:[^'\\\n]|\\.)*'"
    r"|\b\d+\.\d+\b"
    r"|\b\d+\b",
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


def scan_literals(source: str, file_path: Path) -> list[LiteralOccurrence]:
    """Scan source text and collect string and numeric literals.

    Works with any language or plain text file. Detects:
    - Block strings/text enclosed with triple double or triple single quotes
      (may span multiple lines).
    - Strings/text enclosed with double or single quotes (single line).
    - Decimal and integer numbers.

    Author: Ron Webb
    Since: 1.0.0
    """
    line_offsets = _build_line_offsets(source)
    occurrences: list[LiteralOccurrence] = []
    for match in _PATTERN.finditer(source):
        line, column = _line_and_column(line_offsets, match.start())
        occurrences.append(
            LiteralOccurrence(
                file_path=file_path,
                line=line,
                column=column,
                value=match.group(),
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
