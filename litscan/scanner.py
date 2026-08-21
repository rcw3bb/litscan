"""Literal scanner utilities.

Author: Ron Webb
Since: 1.0.0
"""

from __future__ import annotations

import logging
import re
from collections.abc import Generator
from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict

from tree_sitter import Node, Tree  # type: ignore[import-untyped]

from . import LIT_IGNORE_PATH
from .parser import parse

_logger = logging.getLogger(__name__)

# Maps file extension → tree-sitter language name.
EXTENSION_TO_LANGUAGE: dict[str, str] = {
    ".py": "Python",
    ".pyi": "Python",
    ".js": "JavaScript",
    ".mjs": "JavaScript",
    ".cjs": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".java": "Java",
    ".go": "Go",
    ".gs": "Gosu",
    ".gsx": "Gosu",
    ".c": "C",
    ".h": "C",
    ".cpp": "C++",
    ".cc": "C++",
    ".cxx": "C++",
    ".hpp": "C++",
    ".hxx": "C++",
    ".cs": "CSharp",
    ".rs": "Rust",
    ".kt": "Kotlin",
    ".kts": "Kotlin",
    ".swift": "Swift",
    ".scala": "Scala",
    ".groovy": "Groovy",
    ".gradle": "Groovy",
}

# Per-language literal node types recognised by tree-sitter.
LITERAL_NODE_TYPES: dict[str, frozenset[str]] = {
    "Python": frozenset({"string", "integer", "float"}),
    "JavaScript": frozenset({"string", "number", "template_string"}),
    "TypeScript": frozenset({"string", "number", "template_string"}),
    "Java": frozenset(
        {
            "string_literal",
            "text_block",
            "decimal_integer_literal",
            "decimal_floating_point_literal",
        }
    ),
    "Go": frozenset(
        {
            "interpreted_string_literal",
            "raw_string_literal",
            "int_literal",
            "float_literal",
        }
    ),
    "Gosu": frozenset({"string_literal", "number_literal"}),
    "C": frozenset({"string_literal", "number_literal", "char_literal"}),
    "C++": frozenset({"string_literal", "number_literal", "char_literal"}),
    "CSharp": frozenset({"string_literal", "integer_literal", "real_literal"}),
    "Rust": frozenset({"string_literal", "integer_literal", "float_literal"}),
    "Kotlin": frozenset({"string_literal", "number_literal", "float_literal"}),
    "Swift": frozenset(
        {
            "line_string_literal",
            "multi_line_string_literal",
            "integer_literal",
            "real_literal",
        }
    ),
    "Scala": frozenset({"string", "integer_literal", "floating_point_literal"}),
    "Groovy": frozenset(
        {
            "string_literal",
            "decimal_integer_literal",
            "decimal_floating_point_literal",
        }
    ),
}

# Per-language function/method node types (used by ``--functions-only``).
FUNCTION_NODE_TYPES: dict[str, frozenset[str]] = {
    "Python": frozenset({"function_definition"}),
    "JavaScript": frozenset(
        {"function_declaration", "function_expression", "arrow_function"}
    ),
    "TypeScript": frozenset(
        {"function_declaration", "function_expression", "arrow_function"}
    ),
    "Java": frozenset({"method_declaration", "constructor_declaration"}),
    "Go": frozenset({"function_declaration", "method_declaration"}),
    "Gosu": frozenset({"function_declaration", "constructor_declaration"}),
    "C": frozenset({"function_definition"}),
    "C++": frozenset({"function_definition"}),
    "CSharp": frozenset({"method_declaration", "constructor_declaration"}),
    "Rust": frozenset({"function_item"}),
    "Kotlin": frozenset({"function_declaration"}),
    "Swift": frozenset({"function_declaration"}),
    "Scala": frozenset({"function_definition"}),
    "Groovy": frozenset({"function_definition"}),
}


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


@dataclass(frozen=True)
class _WalkContext:
    """Immutable context shared across recursive literal-walk calls.

    Author: Ron Webb
    Since: 2.0.0
    """

    source_bytes: bytes
    literal_types: frozenset[str]
    function_types: frozenset[str]
    language: str
    functions_only: bool


def _is_docstring(node: Node, source_bytes: bytes) -> bool:
    """Return ``True`` when *node* is a Python triple-quoted docstring.

    A string node is treated as a docstring when its text starts with triple
    quotes, its parent is an ``expression_statement``, and its grandparent is
    either ``module`` or ``block`` (the body of a function or class).

    Author: Ron Webb
    Since: 2.0.0
    """
    text = source_bytes[node.start_byte : node.end_byte]
    if not (text.startswith(b'"""') or text.startswith(b"'''")):
        return False
    parent = node.parent
    if parent is None or parent.type != "expression_statement":
        return False
    grandparent = parent.parent
    return grandparent is not None and grandparent.type in {"module", "block"}


def _walk_literals(
    node: Node,
    ctx: _WalkContext,
    inside_function: bool = False,
) -> Generator[Node, None, None]:
    """Recursively walk *node*, yielding each literal :class:`Node`.

    When *ctx.functions_only* is ``True`` only literals that are descendants of
    a function or method node are yielded.  Python triple-quoted docstrings are
    always excluded.

    Recursion stops when a literal node is matched so that composite literal
    nodes (e.g. ``string_start`` / ``string_content`` children of ``string``)
    are never yielded separately.

    Author: Ron Webb
    Since: 2.0.0
    """
    if node.type in ctx.literal_types:
        if not ctx.functions_only or inside_function:
            if not (ctx.language == "Python" and _is_docstring(node, ctx.source_bytes)):
                yield node
        return

    if ctx.functions_only and not inside_function and node.type in ctx.function_types:
        for child in node.children:
            yield from _walk_literals(child, ctx, True)
        return

    for child in node.children:
        yield from _walk_literals(child, ctx, inside_function)


def scan_literals(
    source_bytes: bytes,
    file_path: Path,
    language: str,
    ignore_patterns: list[re.Pattern[str]] | None = None,
    functions_only: bool = False,
) -> list[LiteralOccurrence]:
    """Parse *source_bytes* with tree-sitter and collect literal occurrences.

    Supported languages are determined by :data:`LITERAL_NODE_TYPES`.  When
    *ignore_patterns* is ``None`` the module-level :data:`_IGNORE_PATTERNS`
    (loaded from ``lit_ignore``) are used; pass an explicit list to override.

    When *functions_only* is ``True`` only literals inside function or method
    bodies are reported.

    Author: Ron Webb
    Since: 1.0.0
    """
    active = _IGNORE_PATTERNS if ignore_patterns is None else ignore_patterns
    tree: Tree | None = parse(source_bytes, language)
    if tree is None:
        return []

    ctx = _WalkContext(
        source_bytes=source_bytes,
        literal_types=LITERAL_NODE_TYPES.get(language, frozenset()),
        function_types=FUNCTION_NODE_TYPES.get(language, frozenset()),
        language=language,
        functions_only=functions_only,
    )
    occurrences: list[LiteralOccurrence] = []

    for node in _walk_literals(tree.root_node, ctx):
        value = source_bytes[node.start_byte : node.end_byte].decode(
            "utf-8", errors="replace"
        )
        if any(p.search(value) for p in active):
            continue
        row, col = node.start_point
        occurrences.append(
            LiteralOccurrence(
                file_path=file_path,
                line=row + 1,
                column=col,
                value=value,
            )
        )

    return occurrences


def scan_file(
    file_path: Path,
    functions_only: bool = False,
) -> list[LiteralOccurrence]:
    """Read *file_path* from disk and return all literal occurrences found in it.

    The tree-sitter language is determined from the file extension via
    :data:`EXTENSION_TO_LANGUAGE`.  Files with unsupported extensions are
    skipped with a warning and an empty list is returned.

    Author: Ron Webb
    Since: 1.0.0
    """
    language = EXTENSION_TO_LANGUAGE.get(file_path.suffix.lower())
    if language is None:
        _logger.warning(
            "Unsupported extension '%s' — skipping %s", file_path.suffix, file_path
        )
        return []
    source_bytes = file_path.read_bytes()
    return scan_literals(
        source_bytes, file_path, language, functions_only=functions_only
    )


class LiteralGroup(TypedDict):
    """JSON-serialisable representation of a grouped literal.

    Author: Ron Webb
    Since: 1.0.0
    """

    count: int
    literal: str
    files: list[str]


# ScanReport uses the functional TypedDict syntax because "run-date" is not a
# valid Python identifier.
ScanReport = TypedDict(
    "ScanReport",
    {
        "application": str,
        "version": str,
        "run-date": str,
        "findings": list[LiteralGroup],
    },
)
