"""Literal scanner utilities.

Author: Ron Webb
Since: 1.0.0
"""

from __future__ import annotations

import ast
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

# File suffixes whose block structure is delimited by braces.
_BRACE_STYLE_SUFFIXES: frozenset[str] = frozenset(
    {
        ".java",
        ".js",
        ".ts",
        ".jsx",
        ".tsx",
        ".c",
        ".cpp",
        ".h",
        ".hpp",
        ".cs",
        ".go",
        ".rs",
        ".kt",
        ".swift",
        ".scala",
        ".groovy",
        ".gs",
        ".gsx",
    }
)

# Keywords that open brace-blocks but are NOT function/method definitions.
_CONTROL_KW: frozenset[str] = frozenset(
    {
        "if",
        "else",
        "for",
        "while",
        "do",
        "switch",
        "try",
        "catch",
        "finally",
        "with",
        "synchronized",
    }
)

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


def _mask_for_structure(source: str) -> str:
    """Return *source* with all comments and string literals replaced by spaces.

    Preserves newlines so that character offsets remain identical to those of
    the original source.  Used for structural analysis (e.g. brace matching)
    where the content of strings and comments must not be interpreted as code.

    Author: Ron Webb
    Since: 1.2.0
    """

    def _replace(match: re.Match[str]) -> str:
        return "".join(" " if c != "\n" else c for c in match.group())

    return _MASK_PATTERN.sub(_replace, source)


def _get_python_function_regions(
    source: str,
    line_offsets: list[int],
) -> list[tuple[int, int]]:
    """Return character ranges covering each function/method definition in Python source.

    Uses :mod:`ast` to locate :class:`ast.FunctionDef` and
    :class:`ast.AsyncFunctionDef` nodes.  Each range starts at the ``def``
    keyword and ends at the last character of the function body.  Returns an
    empty list when the source cannot be parsed.

    Author: Ron Webb
    Since: 1.2.0
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    regions: list[tuple[int, int]] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.end_lineno is None or node.end_col_offset is None:
            continue
        start = line_offsets[node.lineno - 1] + node.col_offset
        end_line_idx = node.end_lineno - 1
        if end_line_idx < len(line_offsets):
            end = line_offsets[end_line_idx] + node.end_col_offset
        else:
            end = len(source)
        regions.append((start, end))

    return regions


def _find_matching_brace(structural: str, open_pos: int) -> int:
    """Return the position of the ``}`` matching the ``{`` at *open_pos*.

    Scans *structural* (a source string with strings and comments already
    replaced by spaces) starting from *open_pos*, tracking brace depth.
    Returns the last position in *structural* when no matching ``}`` is found.

    Author: Ron Webb
    Since: 1.2.0
    """
    depth = 0
    for i in range(open_pos, len(structural)):
        char = structural[i]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return i
    return len(structural) - 1


def _is_func_open_brace(structural: str, brace_pos: int) -> bool:
    """Return ``True`` when the ``{`` at *brace_pos* opens a function/method body.

    Examines up to 1 000 characters before *brace_pos* in the structural
    source (strings and comments already replaced by spaces).  A ``{`` is
    considered a function opener when the text before it ends with a closing
    parenthesis ``)`` (possibly followed by ``throws``/``extends``/
    ``implements`` clauses or a return-type annotation), or with a lambda arrow
    (``->`` / ``=>``) – provided the identifier immediately before ``(`` is
    not a control-flow keyword.

    Author: Ron Webb
    Since: 1.2.0
    """
    look_start = max(0, brace_pos - 1000)
    before = structural[look_start:brace_pos].rstrip()

    # Arrow / lambda: ) => { or ) -> {
    if re.search(r"\)\s*(?::\s*[\w<>\[\], ]+)?\s*(?:->|=>)\s*$", before):
        return True

    # Standard function/method: word( ... ) [throws/extends/implements ...] {
    paren_end = re.search(
        r"\)\s*(?:(?:throws|extends|implements)\s+[\w,\s<>]+)?\s*$", before
    )
    if not paren_end:
        return False

    # Find the ( that matches the ) found above.
    relevant = before[: paren_end.start() + 1]  # up to and including the )
    depth = 0
    open_pos: int | None = None
    for i in range(len(relevant) - 1, -1, -1):
        char = relevant[i]
        if char == ")":
            depth += 1
        elif char == "(":
            depth -= 1
            if depth == 0:
                open_pos = i
                break

    if open_pos is None:
        return False

    # The word immediately before ( must not be a control-flow keyword.
    word_match = re.search(r"\b(\w+)\s*$", relevant[:open_pos])
    if not word_match:
        return False

    return word_match.group(1) not in _CONTROL_KW


def _get_brace_function_regions(source: str) -> list[tuple[int, int]]:
    """Return character ranges covering each function/method body in a brace-style source.

    Operates on the structurally-masked view of *source* (via
    :func:`_mask_for_structure`) so that braces inside string literals and
    comments are ignored.  Each region spans from the opening ``{`` to the
    matching closing ``}`` (inclusive).

    Author: Ron Webb
    Since: 1.2.0
    """
    structural = _mask_for_structure(source)
    regions: list[tuple[int, int]] = []
    i = 0
    while i < len(structural):
        if structural[i] == "{" and _is_func_open_brace(structural, i):
            end = _find_matching_brace(structural, i)
            regions.append((i, end + 1))
        i += 1
    return regions


def _mask_outside_regions(source: str, regions: list[tuple[int, int]]) -> str:
    """Return *source* with all characters outside *regions* replaced by spaces.

    Preserves newlines everywhere so that character offsets – and therefore
    the line/column numbers reported in :class:`LiteralOccurrence` – remain
    identical to those of the original source.  Overlapping or adjacent
    regions are merged before masking.  When *regions* is empty the entire
    source is masked.

    Author: Ron Webb
    Since: 1.2.0
    """
    if not regions:
        return "".join(" " if c != "\n" else c for c in source)

    # Sort and merge overlapping / adjacent regions.
    sorted_regions = sorted(regions)
    merged: list[list[int]] = []
    for r_start, r_end in sorted_regions:
        if merged and r_start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], r_end)
        else:
            merged.append([r_start, r_end])

    parts: list[str] = []
    pos = 0
    for r_start, r_end in merged:
        for char in source[pos:r_start]:
            parts.append("\n" if char == "\n" else " ")
        parts.append(source[r_start:r_end])
        pos = r_end
    for char in source[pos:]:
        parts.append("\n" if char == "\n" else " ")

    return "".join(parts)


def _get_function_regions(
    source: str,
    suffix: str,
    line_offsets: list[int],
) -> list[tuple[int, int]]:
    """Return character ranges covering each function/method for the given file type.

    Dispatches to :func:`_get_python_function_regions` for Python files and to
    :func:`_get_brace_function_regions` for brace-style languages.  Returns an
    empty list for unsupported file types; when ``functions_only`` is ``True``
    no literals are reported for those files.

    Author: Ron Webb
    Since: 1.2.0
    """
    if suffix in _PYTHON_SUFFIXES:
        return _get_python_function_regions(source, line_offsets)
    if suffix in _BRACE_STYLE_SUFFIXES:
        return _get_brace_function_regions(source)
    return []


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
    functions_only: bool = False,
) -> list[LiteralOccurrence]:
    """Scan source text and collect string and numeric literals.

    Works with any language or plain text file. Detects:
    - Block strings/text enclosed with triple double or triple single quotes
      (may span multiple lines).
    - Strings/text enclosed with double or single quotes (single line).
    - Decimal and integer numbers.

    When *ignore_patterns* is ``None`` the module-level :data:`_IGNORE_PATTERNS`
    (loaded from ``lit_ignore``) are used. Pass an explicit list to override.

    When *functions_only* is ``True`` only literals that appear inside a
    function or method body are reported.  Supported file types are Python
    (``.py`` / ``.pyi``) and brace-style languages (see
    :data:`_BRACE_STYLE_SUFFIXES`).  Literals in unsupported file types are
    suppressed entirely when this flag is set.

    Author: Ron Webb
    Since: 1.0.0
    """
    active = _IGNORE_PATTERNS if ignore_patterns is None else ignore_patterns
    suffix = file_path.suffix.lower()
    effective_source = _mask_non_literals(source, suffix)
    line_offsets = _build_line_offsets(source)
    if functions_only:
        regions = _get_function_regions(source, suffix, line_offsets)
        effective_source = _mask_outside_regions(effective_source, regions)
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


def scan_file(
    file_path: Path,
    functions_only: bool = False,
) -> list[LiteralOccurrence]:
    """Read *file_path* from disk and return all literal occurrences found in it.

    Convenience wrapper around :func:`scan_literals` intended for parallel
    execution: a single callable that handles both I/O and scanning so it can
    be submitted directly to a :class:`concurrent.futures.Executor`.

    When *functions_only* is ``True`` only literals inside function/method
    bodies are reported (see :func:`scan_literals`).

    Author: Ron Webb
    Since: 1.0.0
    """
    contents = file_path.read_text(encoding="utf-8", errors="replace")
    return scan_literals(contents, file_path, functions_only=functions_only)


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
