"""Tests for scanner module.

Author: Ron Webb
Since: 1.0.0
"""

from pathlib import Path

from litscan.scanner import (
    LiteralOccurrence,
    _build_line_offsets,
    scan_file,
    scan_literals,
)


def test_scan_literals_finds_double_quoted_string() -> None:
    """It should find double-quoted strings."""
    source = 'name = "Alice";'
    matches = scan_literals(source, Path("sample.js"))
    values = [m.value for m in matches]
    assert '"Alice"' in values


def test_scan_literals_finds_single_quoted_string() -> None:
    """It should find single-quoted strings."""
    source = "name = 'Bob';"
    matches = scan_literals(source, Path("sample.js"))
    values = [m.value for m in matches]
    assert "'Bob'" in values


def test_scan_literals_finds_integer() -> None:
    """It should find integer numbers."""
    source = "count = 42;"
    matches = scan_literals(source, Path("sample.js"))
    values = [m.value for m in matches]
    assert "42" in values


def test_scan_literals_finds_decimal() -> None:
    """It should find decimal numbers."""
    source = "pi = 3.14;"
    matches = scan_literals(source, Path("sample.js"))
    values = [m.value for m in matches]
    assert "3.14" in values


def test_scan_literals_finds_triple_double_quoted_block() -> None:
    """It should find multiline triple-double-quoted blocks."""
    source = '"""line one\nline two\nline three"""'
    matches = scan_literals(source, Path("sample.py"))
    values = [m.value for m in matches]
    assert '"""line one\nline two\nline three"""' in values


def test_scan_literals_finds_triple_single_quoted_block() -> None:
    """It should find multiline triple-single-quoted blocks."""
    source = "'''first\nsecond'''"
    matches = scan_literals(source, Path("sample.py"))
    values = [m.value for m in matches]
    assert "'''first\nsecond'''" in values


def test_scan_literals_block_not_split_into_single_quotes() -> None:
    """Triple-quoted blocks must not be broken into smaller single-quote matches."""
    source = "x = '''hello''';"
    matches = scan_literals(source, Path("sample.py"))
    # Exactly one match for the whole block (plus the integer from nothing)
    string_matches = [m for m in matches if m.value.startswith("'''")]
    assert len(string_matches) == 1
    assert string_matches[0].value == "'''hello'''"


def test_scan_literals_reports_correct_line_and_column() -> None:
    """It should report the correct line and column of each literal."""
    source = "x = 1\ny = 'hello'\n"
    matches = scan_literals(source, Path("sample.txt"))
    by_value = {m.value: m for m in matches}
    assert by_value["1"].line == 1
    assert by_value["'hello'"].line == 2
    assert by_value["'hello'"].column == 4


def test_scan_literals_returns_literal_occurrence_instances() -> None:
    """It should return LiteralOccurrence dataclass instances."""
    source = "a = 7"
    matches = scan_literals(source, Path("f.txt"))
    assert all(isinstance(m, LiteralOccurrence) for m in matches)


def test_scan_literals_empty_source_returns_no_matches() -> None:
    """It should return an empty list for empty source."""
    matches = scan_literals("", Path("empty.txt"))
    assert matches == []


def test_scan_literals_python_fixture() -> None:
    """It should find string and numeric literals in a Python fixture file."""
    fixture = Path(__file__).parent / "fixtures" / "sample.py"
    source = fixture.read_text(encoding="utf-8")
    matches = scan_literals(source, fixture)
    values = [m.value for m in matches]
    assert '"Alice"' in values
    assert '"Hello"' in values
    assert "42" in values
    assert "3.14" in values
    assert any(v.startswith('"""') for v in values)


def test_scan_literals_javascript_fixture() -> None:
    """It should find string and numeric literals in a JavaScript fixture file."""
    fixture = Path(__file__).parent / "fixtures" / "sample.js"
    source = fixture.read_text(encoding="utf-8")
    matches = scan_literals(source, fixture)
    values = [m.value for m in matches]
    assert '"Bob"' in values
    assert "'Hi there'" in values
    assert "100" in values
    assert "0.75" in values


def test_scan_literals_java_fixture() -> None:
    """It should find string and numeric literals in a Java fixture file."""
    fixture = Path(__file__).parent / "fixtures" / "sample.java"
    source = fixture.read_text(encoding="utf-8")
    matches = scan_literals(source, fixture)
    values = [m.value for m in matches]
    assert '"Charlie"' in values
    assert "99" in values
    assert "3.14159" in values
    assert any(v.startswith('"""') for v in values)


def test_build_line_offsets_single_line() -> None:
    """It should return [0] for a source with no newlines."""
    assert _build_line_offsets("hello world") == [0]


def test_build_line_offsets_two_lines() -> None:
    """It should return two offsets for a two-line source."""
    offsets = _build_line_offsets("line1\nline2")
    assert offsets == [0, 6]


def test_build_line_offsets_trailing_newline() -> None:
    """It should include a trailing entry when source ends with a newline."""
    offsets = _build_line_offsets("a\nb\n")
    assert offsets == [0, 2, 4]


def test_build_line_offsets_empty_source() -> None:
    """It should return [0] for an empty source string."""
    assert _build_line_offsets("") == [0]


def test_scan_file_returns_occurrences(tmp_path: Path) -> None:
    """scan_file should read a file from disk and return its literal occurrences."""
    sample = tmp_path / "code.py"
    sample.write_text("x = 'hello'; y = 42\n", encoding="utf-8")
    occurrences = scan_file(sample)
    values = [o.value for o in occurrences]
    assert "'hello'" in values
    assert "42" in values


def test_scan_file_returns_correct_file_path(tmp_path: Path) -> None:
    """Each occurrence returned by scan_file should reference the scanned file."""
    sample = tmp_path / "script.js"
    sample.write_text("var n = 7;", encoding="utf-8")
    occurrences = scan_file(sample)
    assert all(o.file_path == sample for o in occurrences)
