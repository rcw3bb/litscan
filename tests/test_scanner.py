"""Tests for scanner module.

Author: Ron Webb
Since: 1.0.0
"""

import re
from pathlib import Path

from litscan.scanner import (
    LiteralOccurrence,
    _build_line_offsets,
    _get_brace_function_regions,
    _get_python_function_regions,
    _is_docstring_position,
    _load_brace_suffixes,
    _load_control_keywords,
    _load_ignore_patterns,
    _mask_for_structure,
    _mask_non_literals,
    _mask_outside_regions,
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
    """It should find multiline triple-double-quoted blocks in assignment context."""
    source = 'x = """line one\nline two\nline three"""'
    matches = scan_literals(source, Path("sample.py"))
    values = [m.value for m in matches]
    assert '"""line one\nline two\nline three"""' in values


def test_scan_literals_finds_triple_single_quoted_block() -> None:
    """It should find multiline triple-single-quoted blocks in assignment context."""
    source = "x = '''first\nsecond'''"
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
    number_values = [v for v in values if v[0].isdigit()]
    assert '"Alice"' in values
    assert '"Hello"' in values
    assert "42" in number_values
    assert "3.14" in number_values
    assert any(v.startswith('"""') for v in values)
    # Date string literals are captured whole; their constituent digits are not
    # separately reported as numeric literals.
    assert '"2023-01-15"' in values
    assert '"2024/06/07"' in values
    assert "2023" not in number_values
    assert "2024" not in number_values
    # Module docstring content must be excluded.
    assert "'excluded_module'" not in values
    # Inline comment content must be excluded.
    assert "'excluded_comment'" not in values
    assert "999" not in number_values
    # Function docstring content must be excluded.
    assert "'excluded_func'" not in values


def test_scan_literals_javascript_fixture() -> None:
    """It should find string and numeric literals in a JavaScript fixture file."""
    fixture = Path(__file__).parent / "fixtures" / "sample.js"
    source = fixture.read_text(encoding="utf-8")
    matches = scan_literals(source, fixture)
    values = [m.value for m in matches]
    number_values = [v for v in values if v[0].isdigit()]
    assert '"Bob"' in values
    assert "'Hi there'" in values
    assert "100" in number_values
    assert "0.75" in number_values
    # Date string literals are captured whole; their constituent digits are not
    # separately reported as numeric literals.
    assert '"2023/06/01"' in values
    assert '"10:30:00"' in values
    assert "2023" not in number_values
    assert "10" not in number_values
    # Single-line comment content must be excluded.
    assert '"excluded_line"' not in values
    assert "400" not in number_values
    # Block comment content must be excluded.
    assert '"excluded_block"' not in values
    assert "500" not in number_values


def test_scan_literals_java_fixture() -> None:
    """It should find string and numeric literals in a Java fixture file."""
    fixture = Path(__file__).parent / "fixtures" / "sample.java"
    source = fixture.read_text(encoding="utf-8")
    matches = scan_literals(source, fixture)
    values = [m.value for m in matches]
    number_values = [v for v in values if v[0].isdigit()]
    assert '"Charlie"' in values
    assert "99" in number_values
    assert "3.14159" in number_values
    assert any(v.startswith('"""') for v in values)
    # Date string literals are captured whole; their constituent digits are not
    # separately reported as numeric literals.
    assert '"2023-06-01"' in values
    assert '"10:30:00"' in values
    assert "2023" not in number_values
    assert "10" not in number_values
    # Javadoc content must be excluded.
    assert '"excluded_doc"' not in values
    assert "200" not in number_values
    # Single-line comment content must be excluded.
    assert '"excluded_line"' not in values
    assert "300" not in number_values


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


# ---------------------------------------------------------------------------
# Numbers inside string literals – not separately reported
# ---------------------------------------------------------------------------


def test_scan_literals_number_inside_double_quoted_string_not_separately_reported() -> (
    None
):
    """A number embedded in a double-quoted string must not be reported as a number."""
    source = 'label = "count is 42";'
    matches = scan_literals(source, Path("sample.js"), ignore_patterns=[])
    values = [m.value for m in matches]
    number_values = [v for v in values if v[0].isdigit()]
    assert '"count is 42"' in values
    assert "42" not in number_values


def test_scan_literals_number_inside_single_quoted_string_not_separately_reported() -> (
    None
):
    """A number embedded in a single-quoted string must not be reported as a number."""
    source = "msg = 'value 99';"
    matches = scan_literals(source, Path("sample.js"), ignore_patterns=[])
    values = [m.value for m in matches]
    number_values = [v for v in values if v[0].isdigit()]
    assert "'value 99'" in values
    assert "99" not in number_values


def test_scan_literals_date_inside_string_not_separately_reported() -> None:
    """Date segments inside a quoted string must not be reported as standalone numbers."""
    source = 'release = "2023-01-15";'
    matches = scan_literals(source, Path("sample.js"), ignore_patterns=[])
    values = [m.value for m in matches]
    number_values = [v for v in values if v[0].isdigit()]
    assert '"2023-01-15"' in values
    assert "2023" not in number_values
    assert "01" not in number_values
    assert "15" not in number_values


def test_scan_literals_time_inside_string_not_separately_reported() -> None:
    """Time segments inside a quoted string must not be reported as standalone numbers."""
    source = 'start = "10:30:00";'
    matches = scan_literals(source, Path("sample.js"), ignore_patterns=[])
    values = [m.value for m in matches]
    number_values = [v for v in values if v[0].isdigit()]
    assert '"10:30:00"' in values
    assert "10" not in number_values
    assert "30" not in number_values


def test_scan_literals_bare_number_outside_string_is_reported() -> None:
    """A bare number that appears outside any string literal must be reported."""
    source = "count = 42;"
    matches = scan_literals(source, Path("sample.js"), ignore_patterns=[])
    number_values = [m.value for m in matches if m.value[0].isdigit()]
    assert "42" in number_values


def test_scan_literals_date_like_bare_number_outside_string_is_reported() -> None:
    """Numbers outside any string literal or comment must be reported."""
    source = "year = 2023; month = 01; day = 15"
    matches = scan_literals(source, Path("sample.py"), ignore_patterns=[])
    number_values = [m.value for m in matches if m.value[0].isdigit()]
    assert "2023" in number_values
    assert "01" in number_values
    assert "15" in number_values


# ---------------------------------------------------------------------------
# lit_ignore – default patterns (0 and "")
# ---------------------------------------------------------------------------


def test_scan_literals_ignores_zero_by_default() -> None:
    """The literal '0' should be excluded by default via lit_ignore."""
    source = "x = 0;"
    matches = scan_literals(source, Path("sample.js"))
    values = [m.value for m in matches]
    assert "0" not in values


def test_scan_literals_ignores_empty_string_by_default() -> None:
    """The empty string literal '""' should be excluded by default via lit_ignore."""
    source = 'name = "";'
    matches = scan_literals(source, Path("sample.js"))
    values = [m.value for m in matches]
    assert '""' not in values


def test_scan_literals_zero_reported_when_ignore_overridden() -> None:
    """'0' should appear when ignore_patterns is overridden with an empty list."""
    source = "x = 0;"
    matches = scan_literals(source, Path("sample.js"), ignore_patterns=[])
    values = [m.value for m in matches]
    assert "0" in values


def test_scan_literals_custom_ignore_pattern_excludes_match() -> None:
    """A custom ignore pattern should exclude matching literals."""
    patterns = [re.compile(r"^42$")]
    source = "x = 42;"
    matches = scan_literals(source, Path("sample.js"), ignore_patterns=patterns)
    values = [m.value for m in matches]
    assert "42" not in values


def test_load_ignore_patterns_skips_comments_and_empty_lines(
    tmp_path: Path,
) -> None:
    """_load_ignore_patterns should skip comment lines and blank lines."""
    ignore_file = tmp_path / "lit_ignore"
    ignore_file.write_text("# comment\n\n^test$\n", encoding="utf-8")
    patterns = _load_ignore_patterns(ignore_file)
    assert len(patterns) == 1
    assert patterns[0].pattern == "^test$"


def test_load_ignore_patterns_compiles_each_line_as_regex(
    tmp_path: Path,
) -> None:
    """_load_ignore_patterns should compile each non-blank, non-comment line."""
    ignore_file = tmp_path / "lit_ignore"
    ignore_file.write_text('^0$\n^""$\n', encoding="utf-8")
    patterns = _load_ignore_patterns(ignore_file)
    assert len(patterns) == 2
    assert patterns[0].search("0") is not None
    assert patterns[1].search('""') is not None


# ---------------------------------------------------------------------------
# Comment stripping
# ---------------------------------------------------------------------------


def test_scan_literals_skips_python_hash_comment() -> None:
    """Literals inside a Python # comment must not be reported."""
    source = "# comment with 'secret' and 42\nx = 'real'"
    matches = scan_literals(source, Path("sample.py"))
    values = [m.value for m in matches]
    assert "'secret'" not in values
    assert "42" not in [v for v in values if v[0].isdigit()]
    assert "'real'" in values


def test_scan_literals_skips_c_style_line_comment() -> None:
    """Literals inside a // comment must not be reported."""
    source = '// comment with "secret" and 42\nlet x = "real";'
    matches = scan_literals(source, Path("sample.js"))
    values = [m.value for m in matches]
    assert '"secret"' not in values
    assert "42" not in [v for v in values if v[0].isdigit()]
    assert '"real"' in values


def test_scan_literals_skips_block_comment() -> None:
    """Literals inside a /* */ block comment must not be reported."""
    source = '/* "ignore" 99 */\nlet x = "keep";'
    matches = scan_literals(source, Path("sample.js"))
    values = [m.value for m in matches]
    assert '"ignore"' not in values
    assert "99" not in [v for v in values if v[0].isdigit()]
    assert '"keep"' in values


def test_scan_literals_skips_javadoc() -> None:
    """Literals inside a Javadoc /** */ comment must not be reported."""
    source = '/** "documented" 42 */\nString x = "keep";'
    matches = scan_literals(source, Path("sample.java"))
    values = [m.value for m in matches]
    assert '"documented"' not in values
    assert "42" not in [v for v in values if v[0].isdigit()]
    assert '"keep"' in values


def test_scan_literals_url_in_string_not_misidentified_as_comment() -> None:
    """A URL inside a string literal must not cause the rest to be masked as a comment."""
    source = 'url = "http://example.com/path"; x = 7;'
    matches = scan_literals(source, Path("sample.py"))
    values = [m.value for m in matches]
    assert '"http://example.com/path"' in values
    assert "7" in values


# ---------------------------------------------------------------------------
# Python docstring detection
# ---------------------------------------------------------------------------


def test_scan_literals_skips_python_module_docstring() -> None:
    """Literals inside a Python module docstring must not be reported."""
    source = '"""Module docs with \'secret\' and 42."""\nx = 1'
    matches = scan_literals(source, Path("sample.py"))
    values = [m.value for m in matches]
    assert "42" not in [v for v in values if v[0].isdigit()]
    assert "'secret'" not in values
    assert "1" in values


def test_scan_literals_skips_python_function_docstring() -> None:
    """Literals inside a Python function docstring must not be reported."""
    source = 'def foo():\n    """Docs with \'secret\' and 42."""\n    return "real"'
    matches = scan_literals(source, Path("sample.py"))
    values = [m.value for m in matches]
    assert "42" not in [v for v in values if v[0].isdigit()]
    assert "'secret'" not in values
    assert '"real"' in values


def test_scan_literals_skips_python_class_docstring() -> None:
    """Literals inside a Python class docstring must not be reported."""
    source = 'class Foo:\n    """Class docs with 99."""\n    x = "keep"'
    matches = scan_literals(source, Path("sample.py"))
    values = [m.value for m in matches]
    assert "99" not in [v for v in values if v[0].isdigit()]
    assert '"keep"' in values


def test_scan_literals_triple_quoted_assignment_not_skipped() -> None:
    """A triple-quoted string in an assignment must not be treated as a docstring."""
    source = 'x = """real value"""'
    matches = scan_literals(source, Path("sample.py"))
    values = [m.value for m in matches]
    assert '"""real value"""' in values


def test_scan_literals_java_triple_quoted_not_skipped() -> None:
    """Java text blocks (triple-quoted) must never be treated as docstrings."""
    source = 'String s = """\n    content\n    """;'
    matches = scan_literals(source, Path("sample.java"))
    values = [m.value for m in matches]
    assert any(v.startswith('"""') for v in values)


# ---------------------------------------------------------------------------
# _is_docstring_position unit tests
# ---------------------------------------------------------------------------


def test_is_docstring_position_module_level_true() -> None:
    """A triple-quoted string at the very start of source is a module docstring."""
    source = '"""docstring"""'
    assert _is_docstring_position(source, 0) is True


def test_is_docstring_position_after_def_true() -> None:
    """A triple-quoted string right after def ....: is a function docstring."""
    source = 'def foo():\n    """docstring"""'
    start = source.index('"""')
    assert _is_docstring_position(source, start) is True


def test_is_docstring_position_after_class_true() -> None:
    """A triple-quoted string right after class ...: is a class docstring."""
    source = 'class Bar:\n    """docstring"""'
    start = source.index('"""')
    assert _is_docstring_position(source, start) is True


def test_is_docstring_position_assignment_false() -> None:
    """A triple-quoted string on the right of an assignment is not a docstring."""
    source = 'x = """value"""'
    start = source.index('"""')
    assert _is_docstring_position(source, start) is False


def test_is_docstring_position_dict_value_false() -> None:
    """A triple-quoted value in a dict literal is not a docstring."""
    source = 'd = {"key": """value"""}'
    start = source.index('"""')
    assert _is_docstring_position(source, start) is False


# ---------------------------------------------------------------------------
# _mask_non_literals unit tests
# ---------------------------------------------------------------------------


def test_mask_non_literals_masks_hash_comment() -> None:
    """_mask_non_literals should replace # comment content with spaces."""
    source = "# secret\nx = 1"
    masked = _mask_non_literals(source, ".py")
    assert "secret" not in masked
    assert masked.count("\n") == source.count("\n")
    assert len(masked) == len(source)


def test_mask_non_literals_masks_block_comment() -> None:
    """_mask_non_literals should replace /* */ block comment content with spaces."""
    source = "/* secret 99 */\nx = 1;"
    masked = _mask_non_literals(source, ".java")
    assert "secret" not in masked
    assert "99" not in masked
    assert masked.count("\n") == source.count("\n")


def test_mask_non_literals_preserves_length_and_newlines() -> None:
    """_mask_non_literals must preserve source length and newline positions."""
    source = "# comment\ncode = 42\n"
    masked = _mask_non_literals(source, ".py")
    assert len(masked) == len(source)
    assert masked.count("\n") == source.count("\n")


def test_mask_non_literals_non_python_triple_quote_not_masked() -> None:
    """Triple-quoted strings in non-Python files must never be masked as docstrings."""
    source = '"""\ndocstring-like\n"""'
    masked = _mask_non_literals(source, ".java")
    assert '"""' in masked


# ---------------------------------------------------------------------------
# _mask_for_structure unit tests
# ---------------------------------------------------------------------------


def test_mask_for_structure_replaces_string_content() -> None:
    """_mask_for_structure should replace string literal content with spaces."""
    source = 'x = "hello"; y = 1;'
    masked = _mask_for_structure(source)
    assert "hello" not in masked
    assert len(masked) == len(source)


def test_mask_for_structure_replaces_comment_content() -> None:
    """_mask_for_structure should replace comment content with spaces."""
    source = "// secret\nx = 1;"
    masked = _mask_for_structure(source)
    assert "secret" not in masked
    assert masked.count("\n") == source.count("\n")


def test_mask_for_structure_preserves_length_and_newlines() -> None:
    """_mask_for_structure must not change source length or newline positions."""
    source = '/* block */\nlet x = "value";\n'
    masked = _mask_for_structure(source)
    assert len(masked) == len(source)
    assert masked.count("\n") == source.count("\n")


# ---------------------------------------------------------------------------
# _get_python_function_regions unit tests
# ---------------------------------------------------------------------------


def test_get_python_function_regions_detects_top_level_function() -> None:
    """It should return a region spanning the full function definition."""
    source = 'def foo():\n    x = "hello"\n'
    from litscan.scanner import _build_line_offsets

    offsets = _build_line_offsets(source)
    regions = _get_python_function_regions(source, offsets)
    assert len(regions) == 1
    start, end = regions[0]
    assert source[start:end].startswith("def foo")
    assert '"hello"' in source[start:end]


def test_get_python_function_regions_detects_class_method() -> None:
    """It should detect a method inside a class."""
    source = "class C:\n    def method(self):\n        x = 1\n"
    from litscan.scanner import _build_line_offsets

    offsets = _build_line_offsets(source)
    regions = _get_python_function_regions(source, offsets)
    assert any("def method" in source[s:e] for s, e in regions)


def test_get_python_function_regions_excludes_module_level() -> None:
    """Module-level code must not fall inside any returned region."""
    source = 'MODULE = "top"\ndef foo():\n    x = "inside"\n'
    from litscan.scanner import _build_line_offsets

    offsets = _build_line_offsets(source)
    regions = _get_python_function_regions(source, offsets)
    all_covered = set()
    for s, e in regions:
        all_covered.update(range(s, e))
    module_offset = source.index('"top"')
    assert module_offset not in all_covered


def test_get_python_function_regions_syntax_error_returns_empty() -> None:
    """It should return an empty list when the source cannot be parsed."""
    from litscan.scanner import _build_line_offsets

    offsets = _build_line_offsets("def broken(:\n")
    assert _get_python_function_regions("def broken(:\n", offsets) == []


# ---------------------------------------------------------------------------
# _get_brace_function_regions unit tests
# ---------------------------------------------------------------------------


def test_get_brace_function_regions_detects_js_function() -> None:
    """It should detect a regular JS function body."""
    source = 'function foo() {\n    const x = "hello";\n}\n'
    regions = _get_brace_function_regions(source)
    assert len(regions) >= 1
    combined = "".join(source[s:e] for s, e in regions)
    assert '"hello"' in combined


def test_get_brace_function_regions_detects_arrow_function() -> None:
    """It should detect an arrow function body."""
    source = 'const fn = () => {\n    const x = "arrow";\n};\n'
    regions = _get_brace_function_regions(source)
    combined = "".join(source[s:e] for s, e in regions)
    assert '"arrow"' in combined


def test_get_brace_function_regions_excludes_if_block() -> None:
    """An if-block must not be returned as a function region on its own."""
    source = 'if (cond) {\n    x = "inside";\n}\n'
    regions = _get_brace_function_regions(source)
    assert regions == []


def test_get_brace_function_regions_excludes_module_level_java() -> None:
    """Class-level field assignments must not fall inside any detected region."""
    source = (
        "public class C {\n"
        '    String field = "class_level";\n'
        "    public void m() {\n"
        '        String x = "method_level";\n'
        "    }\n"
        "}\n"
    )
    regions = _get_brace_function_regions(source)
    combined = "".join(source[s:e] for s, e in regions)
    assert '"method_level"' in combined
    assert '"class_level"' not in combined


# ---------------------------------------------------------------------------
# _mask_outside_regions unit tests
# ---------------------------------------------------------------------------


def test_mask_outside_regions_keeps_region_content() -> None:
    """Characters inside the given region must be preserved."""
    source = "AAABBBCCC"
    masked = _mask_outside_regions(source, [(3, 6)])
    assert masked[3:6] == "BBB"


def test_mask_outside_regions_replaces_outside_with_spaces() -> None:
    """Characters outside the region must be replaced by spaces."""
    source = "AAABBBCCC"
    masked = _mask_outside_regions(source, [(3, 6)])
    assert masked[:3] == "   "
    assert masked[6:] == "   "


def test_mask_outside_regions_preserves_newlines() -> None:
    """Newlines outside regions must be preserved."""
    source = "A\nB\nC\n"
    masked = _mask_outside_regions(source, [(2, 3)])
    assert masked.count("\n") == source.count("\n")


def test_mask_outside_regions_empty_regions_masks_all() -> None:
    """When regions is empty the entire non-newline content must be masked."""
    source = "hello\nworld"
    masked = _mask_outside_regions(source, [])
    assert all(c in (" ", "\n") for c in masked)
    assert masked.count("\n") == source.count("\n")


def test_mask_outside_regions_merges_overlapping() -> None:
    """Overlapping regions must be merged and their union preserved."""
    source = "ABCDE"
    masked = _mask_outside_regions(source, [(1, 3), (2, 5)])
    # merged → (1, 5) → 'BCDE' kept, 'A' masked
    assert masked[0] == " "
    assert masked[1:5] == "BCDE"


# ---------------------------------------------------------------------------
# scan_literals functions_only – Python
# ---------------------------------------------------------------------------


def test_scan_literals_functions_only_excludes_module_level_python() -> None:
    """With functions_only, module-level literals must not be reported."""
    source = 'MODULE = "top"\ndef foo():\n    x = "inside"\n'
    matches = scan_literals(source, Path("f.py"), functions_only=True)
    values = [m.value for m in matches]
    assert '"top"' not in values
    assert '"inside"' in values


def test_scan_literals_functions_only_includes_method_python() -> None:
    """With functions_only, literals inside a class method must be reported."""
    source = "class C:\n    cvar = 1\n    def method(self):\n        x = 2\n"
    matches = scan_literals(
        source, Path("f.py"), ignore_patterns=[], functions_only=True
    )
    values = [m.value for m in matches]
    assert "2" in values
    assert "1" not in values


def test_scan_literals_functions_only_python_fixture() -> None:
    """With functions_only, only literals inside functions in the fixture are reported."""
    fixture = Path(__file__).parent / "fixtures" / "func_sample.py"
    source = fixture.read_text(encoding="utf-8")
    matches = scan_literals(source, fixture, functions_only=True)
    values = [m.value for m in matches]
    # Function-body literals must be present.
    assert '"func_string"' in values
    assert '"method_string"' in values
    assert '"async_string"' in values
    # Module-level literals must be absent.
    assert '"module_string"' not in values
    assert '"class_var"' not in values


# ---------------------------------------------------------------------------
# scan_literals functions_only – JavaScript
# ---------------------------------------------------------------------------


def test_scan_literals_functions_only_excludes_module_level_js() -> None:
    """With functions_only, top-level JS literals must not be reported."""
    source = 'const A = "top";\nfunction foo() {\n    const x = "inside";\n}\n'
    matches = scan_literals(source, Path("f.js"), functions_only=True)
    values = [m.value for m in matches]
    assert '"top"' not in values
    assert '"inside"' in values


def test_scan_literals_functions_only_js_fixture() -> None:
    """With functions_only, only literals inside functions in the JS fixture are reported."""
    fixture = Path(__file__).parent / "fixtures" / "func_sample.js"
    source = fixture.read_text(encoding="utf-8")
    matches = scan_literals(source, fixture, functions_only=True)
    values = [m.value for m in matches]
    assert '"func_string"' in values
    assert '"arrow_string"' in values
    assert '"control_inside"' in values
    assert '"module_string"' not in values


# ---------------------------------------------------------------------------
# scan_literals functions_only – Java
# ---------------------------------------------------------------------------


def test_scan_literals_functions_only_java_fixture() -> None:
    """With functions_only, only literals inside methods in the Java fixture are reported."""
    fixture = Path(__file__).parent / "fixtures" / "FuncSample.java"
    source = fixture.read_text(encoding="utf-8")
    matches = scan_literals(source, fixture, functions_only=True)
    values = [m.value for m in matches]
    assert '"method_string"' in values
    assert '"another_method"' in values
    assert '"class_field"' not in values


# ---------------------------------------------------------------------------
# scan_file functions_only
# ---------------------------------------------------------------------------


def test_scan_file_functions_only(tmp_path: Path) -> None:
    """scan_file with functions_only=True must only return in-function literals."""
    sample = tmp_path / "code.py"
    sample.write_text(
        'MODULE = "top"\ndef foo():\n    x = "inside"\n', encoding="utf-8"
    )
    occurrences = scan_file(sample, functions_only=True)
    values = [o.value for o in occurrences]
    assert '"inside"' in values
    assert '"top"' not in values


# ---------------------------------------------------------------------------
# _load_brace_suffixes unit tests
# ---------------------------------------------------------------------------


def test_load_brace_suffixes_returns_normalised_extensions(
    tmp_path: Path,
) -> None:
    """_load_brace_suffixes should normalise entries to lowercase with a leading dot."""
    cfg = tmp_path / "lit_brace_ext"
    cfg.write_text(".Dart\nsol\n", encoding="utf-8")
    result = _load_brace_suffixes(cfg)
    assert ".dart" in result
    assert ".sol" in result


def test_load_brace_suffixes_skips_comments_and_blank_lines(
    tmp_path: Path,
) -> None:
    """_load_brace_suffixes should skip lines starting with # and blank lines."""
    cfg = tmp_path / "lit_brace_ext"
    cfg.write_text("# a comment\n\n.dart\n", encoding="utf-8")
    result = _load_brace_suffixes(cfg)
    assert len(result) == 1
    assert ".dart" in result


def test_load_brace_suffixes_returns_frozenset(
    tmp_path: Path,
) -> None:
    """_load_brace_suffixes should return a frozenset."""
    cfg = tmp_path / "lit_brace_ext"
    cfg.write_text(".dart\n", encoding="utf-8")
    result = _load_brace_suffixes(cfg)
    assert isinstance(result, frozenset)


def test_load_brace_suffixes_empty_file_returns_empty_frozenset(
    tmp_path: Path,
) -> None:
    """_load_brace_suffixes should return an empty frozenset for a comment-only file."""
    cfg = tmp_path / "lit_brace_ext"
    cfg.write_text("# just a comment\n", encoding="utf-8")
    result = _load_brace_suffixes(cfg)
    assert result == frozenset()


# ---------------------------------------------------------------------------
# _load_control_keywords unit tests
# ---------------------------------------------------------------------------


def test_load_control_keywords_returns_stripped_keywords(
    tmp_path: Path,
) -> None:
    """_load_control_keywords should return stripped, non-comment entries."""
    cfg = tmp_path / "lit_control_kw"
    cfg.write_text("using\nlock\n", encoding="utf-8")
    result = _load_control_keywords(cfg)
    assert "using" in result
    assert "lock" in result


def test_load_control_keywords_skips_comments_and_blank_lines(
    tmp_path: Path,
) -> None:
    """_load_control_keywords should skip lines starting with # and blank lines."""
    cfg = tmp_path / "lit_control_kw"
    cfg.write_text("# a comment\n\nusing\n", encoding="utf-8")
    result = _load_control_keywords(cfg)
    assert len(result) == 1
    assert "using" in result


def test_load_control_keywords_returns_frozenset(
    tmp_path: Path,
) -> None:
    """_load_control_keywords should return a frozenset."""
    cfg = tmp_path / "lit_control_kw"
    cfg.write_text("lock\n", encoding="utf-8")
    result = _load_control_keywords(cfg)
    assert isinstance(result, frozenset)


def test_load_control_keywords_empty_file_returns_empty_frozenset(
    tmp_path: Path,
) -> None:
    """_load_control_keywords should return an empty frozenset for a comment-only file."""
    cfg = tmp_path / "lit_control_kw"
    cfg.write_text("# just a comment\n", encoding="utf-8")
    result = _load_control_keywords(cfg)
    assert result == frozenset()
