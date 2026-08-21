"""Tests for scanner module.

Author: Ron Webb
Since: 1.0.0
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from litscan.scanner import (
    EXTENSION_TO_LANGUAGE,
    FUNCTION_NODE_TYPES,
    LITERAL_NODE_TYPES,
    LiteralOccurrence,
    _is_docstring,
    _load_ignore_patterns,
    scan_file,
    scan_literals,
)
from litscan.parser import parse

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _values(occurrences: list[LiteralOccurrence]) -> list[str]:
    return [o.value for o in occurrences]


def _numbers(occurrences: list[LiteralOccurrence]) -> list[str]:
    return [o.value for o in occurrences if o.value[0].isdigit()]


# ---------------------------------------------------------------------------
# EXTENSION_TO_LANGUAGE mapping
# ---------------------------------------------------------------------------


def test_extension_to_language_python() -> None:
    """Python extensions must map to the Python language."""
    assert EXTENSION_TO_LANGUAGE[".py"] == "Python"
    assert EXTENSION_TO_LANGUAGE[".pyi"] == "Python"


def test_extension_to_language_javascript() -> None:
    """JS/MJS/CJS extensions must map to JavaScript."""
    assert EXTENSION_TO_LANGUAGE[".js"] == "JavaScript"
    assert EXTENSION_TO_LANGUAGE[".mjs"] == "JavaScript"
    assert EXTENSION_TO_LANGUAGE[".cjs"] == "JavaScript"


def test_extension_to_language_typescript() -> None:
    """TS and TSX extensions must map to TypeScript."""
    assert EXTENSION_TO_LANGUAGE[".ts"] == "TypeScript"
    assert EXTENSION_TO_LANGUAGE[".tsx"] == "TypeScript"


def test_extension_to_language_java() -> None:
    """Java extension must map to Java."""
    assert EXTENSION_TO_LANGUAGE[".java"] == "Java"


def test_extension_to_language_go() -> None:
    """Go extension must map to Go."""
    assert EXTENSION_TO_LANGUAGE[".go"] == "Go"


def test_extension_to_language_gosu() -> None:
    """Gosu extensions must map to Gosu."""
    assert EXTENSION_TO_LANGUAGE[".gs"] == "Gosu"
    assert EXTENSION_TO_LANGUAGE[".gsx"] == "Gosu"


# ---------------------------------------------------------------------------
# scan_literals – Python literals
# ---------------------------------------------------------------------------


def test_scan_literals_python_double_quoted_string() -> None:
    """It should find a double-quoted string in Python source."""
    occurrences = scan_literals(b'name = "Alice"', Path("f.py"), "Python")
    assert '"Alice"' in _values(occurrences)


def test_scan_literals_python_single_quoted_string() -> None:
    """It should find a single-quoted string in Python source."""
    occurrences = scan_literals(b"greeting = 'hello'", Path("f.py"), "Python")
    assert "'hello'" in _values(occurrences)


def test_scan_literals_python_integer() -> None:
    """It should find an integer literal in Python source."""
    occurrences = scan_literals(b"count = 42", Path("f.py"), "Python")
    assert "42" in _numbers(occurrences)


def test_scan_literals_python_float() -> None:
    """It should find a float literal in Python source."""
    occurrences = scan_literals(b"pi = 3.14", Path("f.py"), "Python")
    assert "3.14" in _numbers(occurrences)


def test_scan_literals_python_triple_double_quoted() -> None:
    """It should find a triple-double-quoted string in an assignment context."""
    src = b'msg = """line one\nline two"""'
    occurrences = scan_literals(src, Path("f.py"), "Python")
    assert '"""line one\nline two"""' in _values(occurrences)


def test_scan_literals_python_triple_single_quoted() -> None:
    """It should find a triple-single-quoted string in an assignment context."""
    src = b"msg = '''first\nsecond'''"
    occurrences = scan_literals(src, Path("f.py"), "Python")
    assert "'''first\nsecond'''" in _values(occurrences)


def test_scan_literals_python_returns_literal_occurrence_instances() -> None:
    """scan_literals must return LiteralOccurrence instances."""
    occurrences = scan_literals(b"a = 7", Path("f.py"), "Python")
    assert all(isinstance(o, LiteralOccurrence) for o in occurrences)


def test_scan_literals_python_empty_source() -> None:
    """An empty source produces no occurrences."""
    assert scan_literals(b"", Path("f.py"), "Python") == []


def test_scan_literals_python_correct_line_and_column() -> None:
    """It should report the correct 1-based line and 0-based column."""
    src = b"x = 1\ny = 'hello'\n"
    occurrences = scan_literals(src, Path("f.py"), "Python")
    by_value = {o.value: o for o in occurrences}
    assert by_value["1"].line == 1
    assert by_value["'hello'"].line == 2
    assert by_value["'hello'"].column == 4


# ---------------------------------------------------------------------------
# scan_literals – JavaScript literals
# ---------------------------------------------------------------------------


def test_scan_literals_js_double_quoted_string() -> None:
    """It should find a double-quoted string in JavaScript source."""
    occurrences = scan_literals(b'const x = "Bob";', Path("f.js"), "JavaScript")
    assert '"Bob"' in _values(occurrences)


def test_scan_literals_js_single_quoted_string() -> None:
    """It should find a single-quoted string in JavaScript source."""
    occurrences = scan_literals(b"const x = 'Hi';", Path("f.js"), "JavaScript")
    assert "'Hi'" in _values(occurrences)


def test_scan_literals_js_number() -> None:
    """It should find a number literal in JavaScript source."""
    occurrences = scan_literals(b"const n = 100;", Path("f.js"), "JavaScript")
    assert "100" in _numbers(occurrences)


def test_scan_literals_js_float() -> None:
    """It should find a float literal in JavaScript source."""
    occurrences = scan_literals(b"const r = 0.75;", Path("f.js"), "JavaScript")
    assert "0.75" in _numbers(occurrences)


# ---------------------------------------------------------------------------
# scan_literals – Java literals
# ---------------------------------------------------------------------------


def test_scan_literals_java_string_literal() -> None:
    """It should find a string literal in Java source."""
    src = b'String s = "Charlie";'
    occurrences = scan_literals(src, Path("f.java"), "Java")
    assert '"Charlie"' in _values(occurrences)


def test_scan_literals_java_integer() -> None:
    """It should find a decimal integer literal in Java source."""
    src = b"int n = 99;"
    occurrences = scan_literals(src, Path("f.java"), "Java")
    assert "99" in _numbers(occurrences)


def test_scan_literals_java_float() -> None:
    """It should find a decimal floating-point literal in Java source."""
    src = b"double pi = 3.14159;"
    occurrences = scan_literals(src, Path("f.java"), "Java")
    assert "3.14159" in _numbers(occurrences)


# ---------------------------------------------------------------------------
# scan_literals – Go literals
# ---------------------------------------------------------------------------


def test_scan_literals_go_string() -> None:
    """It should find an interpreted string literal in Go source."""
    src = b'var s = "hello"'
    occurrences = scan_literals(src, Path("f.go"), "Go")
    assert '"hello"' in _values(occurrences)


def test_scan_literals_go_integer() -> None:
    """It should find an integer literal in Go source."""
    src = b"var n = 42"
    occurrences = scan_literals(src, Path("f.go"), "Go")
    assert "42" in _numbers(occurrences)


def test_scan_literals_go_float() -> None:
    """It should find a float literal in Go source."""
    src = b"var pi = 3.14"
    occurrences = scan_literals(src, Path("f.go"), "Go")
    assert "3.14" in _numbers(occurrences)


# ---------------------------------------------------------------------------
# Comments – automatically excluded (tree-sitter separates comment nodes)
# ---------------------------------------------------------------------------


def test_scan_literals_python_hash_comment_excluded() -> None:
    """Literals inside a Python # comment must not be reported."""
    src = b"# comment with 'secret' and 42\nx = 'real'"
    occurrences = scan_literals(src, Path("f.py"), "Python")
    values = _values(occurrences)
    assert "'secret'" not in values
    assert "42" not in _numbers(occurrences)
    assert "'real'" in values


def test_scan_literals_js_line_comment_excluded() -> None:
    """Literals inside a // comment must not be reported."""
    src = b'// "secret" 42\nconst x = "real";'
    occurrences = scan_literals(src, Path("f.js"), "JavaScript")
    values = _values(occurrences)
    assert '"secret"' not in values
    assert "42" not in _numbers(occurrences)
    assert '"real"' in values


def test_scan_literals_java_block_comment_excluded() -> None:
    """Literals inside a /* */ block comment must not be reported."""
    src = b'/* "secret" 99 */\nString x = "keep";'
    occurrences = scan_literals(src, Path("f.java"), "Java")
    values = _values(occurrences)
    assert '"secret"' not in values
    assert "99" not in _numbers(occurrences)
    assert '"keep"' in values


def test_scan_literals_java_javadoc_excluded() -> None:
    """Literals inside a Javadoc /** */ comment must not be reported."""
    src = b'/** "documented" 42 */\nString x = "keep";'
    occurrences = scan_literals(src, Path("f.java"), "Java")
    values = _values(occurrences)
    assert '"documented"' not in values
    assert "42" not in _numbers(occurrences)
    assert '"keep"' in values


def test_scan_literals_go_comment_excluded() -> None:
    """Literals inside a Go // comment must not be reported."""
    src = b'// "excluded" 400\nvar s = "real"'
    occurrences = scan_literals(src, Path("f.go"), "Go")
    values = _values(occurrences)
    assert '"excluded"' not in values
    assert "400" not in _numbers(occurrences)
    assert '"real"' in values


# ---------------------------------------------------------------------------
# Python docstring detection
# ---------------------------------------------------------------------------


def test_scan_literals_python_module_docstring_excluded() -> None:
    """The module-level docstring must be excluded from results."""
    src = b'"""Module docs with \'secret\' and 42."""\nx = 1'
    occurrences = scan_literals(src, Path("f.py"), "Python")
    values = _values(occurrences)
    assert "42" not in _numbers(occurrences)
    assert "'secret'" not in values
    assert "1" in _numbers(occurrences)


def test_scan_literals_python_function_docstring_excluded() -> None:
    """A function-level docstring must be excluded from results."""
    src = b'def foo():\n    """Docs with \'secret\' and 42."""\n    return "real"'
    occurrences = scan_literals(src, Path("f.py"), "Python")
    values = _values(occurrences)
    assert "42" not in _numbers(occurrences)
    assert "'secret'" not in values
    assert '"real"' in values


def test_scan_literals_python_class_docstring_excluded() -> None:
    """A class-level docstring must be excluded from results."""
    src = b'class Foo:\n    """Class docs with 99."""\n    x = "keep"'
    occurrences = scan_literals(src, Path("f.py"), "Python")
    values = _values(occurrences)
    assert "99" not in _numbers(occurrences)
    assert '"keep"' in values


def test_scan_literals_python_triple_quoted_assignment_included() -> None:
    """A triple-quoted string used as an assignment value must not be excluded."""
    src = b'x = """real value"""'
    occurrences = scan_literals(src, Path("f.py"), "Python")
    assert '"""real value"""' in _values(occurrences)


def test_scan_literals_java_triple_quoted_text_block_included() -> None:
    """Java text blocks must never be treated as docstrings."""
    src = b'String s = """\n    content\n    """;'
    occurrences = scan_literals(src, Path("f.java"), "Java")
    assert any(v.startswith('"""') for v in _values(occurrences))


# ---------------------------------------------------------------------------
# _is_docstring unit tests
# ---------------------------------------------------------------------------


def test_is_docstring_module_level_triple_double() -> None:
    """A triple-double-quoted string at module level is a docstring."""
    src = b'"""docstring"""'
    tree = parse(src, "Python")
    assert tree is not None
    # Walk to the first string node
    string_node = tree.root_node.children[0].children[0]
    assert string_node.type == "string"
    assert _is_docstring(string_node, src) is True


def test_is_docstring_assignment_is_false() -> None:
    """A triple-quoted string on the right of an assignment is not a docstring."""
    src = b'x = """value"""'
    tree = parse(src, "Python")
    assert tree is not None
    # Find the string node via a simple walk
    found = None
    stack = [tree.root_node]
    while stack:
        node = stack.pop()
        if node.type == "string":
            found = node
            break
        stack.extend(reversed(node.children))
    assert found is not None
    assert _is_docstring(found, src) is False


# ---------------------------------------------------------------------------
# lit_ignore – default patterns (0 and "")
# ---------------------------------------------------------------------------


def test_scan_literals_ignores_zero_by_default() -> None:
    """The literal '0' should be excluded by default via lit_ignore."""
    occurrences = scan_literals(b"x = 0;", Path("f.js"), "JavaScript")
    assert "0" not in _numbers(occurrences)


def test_scan_literals_ignores_empty_string_by_default_js() -> None:
    """The empty string literal should be excluded by default via lit_ignore."""
    occurrences = scan_literals(b'name = "";', Path("f.js"), "JavaScript")
    assert '""' not in _values(occurrences)


def test_scan_literals_zero_reported_when_ignore_overridden() -> None:
    """'0' should appear when ignore_patterns is overridden with an empty list."""
    occurrences = scan_literals(
        b"x = 0;", Path("f.js"), "JavaScript", ignore_patterns=[]
    )
    assert "0" in _numbers(occurrences)


def test_scan_literals_custom_ignore_pattern_excludes_match() -> None:
    """A custom ignore pattern should exclude matching literals."""
    patterns = [re.compile(r"^42$")]
    occurrences = scan_literals(
        b"x = 42;", Path("f.js"), "JavaScript", ignore_patterns=patterns
    )
    assert "42" not in _numbers(occurrences)


# ---------------------------------------------------------------------------
# _load_ignore_patterns
# ---------------------------------------------------------------------------


def test_load_ignore_patterns_skips_comments_and_empty_lines(tmp_path: Path) -> None:
    """_load_ignore_patterns should skip comment lines and blank lines."""
    ignore_file = tmp_path / "lit_ignore"
    ignore_file.write_text("# comment\n\n^test$\n", encoding="utf-8")
    patterns = _load_ignore_patterns(ignore_file)
    assert len(patterns) == 1
    assert patterns[0].pattern == "^test$"


def test_load_ignore_patterns_compiles_each_line_as_regex(tmp_path: Path) -> None:
    """_load_ignore_patterns should compile each non-blank, non-comment line."""
    ignore_file = tmp_path / "lit_ignore"
    ignore_file.write_text('^0$\n^""$\n', encoding="utf-8")
    patterns = _load_ignore_patterns(ignore_file)
    assert len(patterns) == 2
    assert patterns[0].search("0") is not None
    assert patterns[1].search('""') is not None


# ---------------------------------------------------------------------------
# scan_file – language detection from extension
# ---------------------------------------------------------------------------


def test_scan_file_unsupported_extension_returns_empty(tmp_path: Path) -> None:
    """scan_file must return an empty list for unsupported file extensions."""
    unsupported = tmp_path / "notes.txt"
    unsupported.write_text("hello = 42\n", encoding="utf-8")
    assert scan_file(unsupported) == []


def test_scan_file_ruby_extension_returns_empty(tmp_path: Path) -> None:
    """scan_file must return an empty list for a .rb file (not supported)."""
    rb_file = tmp_path / "script.rb"
    rb_file.write_text("x = 'hello'\n", encoding="utf-8")
    assert scan_file(rb_file) == []


def test_scan_file_returns_occurrences(tmp_path: Path) -> None:
    """scan_file should read a Python file from disk and return its occurrences."""
    sample = tmp_path / "code.py"
    sample.write_text("x = 'hello'; y = 42\n", encoding="utf-8")
    occurrences = scan_file(sample)
    values = _values(occurrences)
    assert "'hello'" in values
    assert "42" in _numbers(occurrences)


def test_scan_file_returns_correct_file_path(tmp_path: Path) -> None:
    """Each occurrence returned by scan_file must reference the scanned file."""
    sample = tmp_path / "script.js"
    sample.write_text("var n = 7;", encoding="utf-8")
    occurrences = scan_file(sample)
    assert all(o.file_path == sample for o in occurrences)


# ---------------------------------------------------------------------------
# Fixture-based integration tests
# ---------------------------------------------------------------------------

_FIXTURES = Path(__file__).parent / "fixtures"


def test_scan_file_python_fixture() -> None:
    """scan_file should find expected literals in the Python fixture."""
    occurrences = scan_file(_FIXTURES / "sample.py")
    values = _values(occurrences)
    nums = _numbers(occurrences)
    assert '"Alice"' in values
    assert '"Hello"' in values
    assert "42" in nums
    assert "3.14" in nums
    assert any(v.startswith('"""') for v in values)
    assert '"2023-01-15"' in values
    assert '"2024/06/07"' in values
    # Digits inside date strings must not be separately reported.
    assert "2023" not in nums
    assert "2024" not in nums
    # Module and inline comment content must be excluded.
    assert "'excluded_module'" not in values
    assert "'excluded_comment'" not in values
    assert "999" not in nums
    # Function docstring content must be excluded.
    assert "'excluded_func'" not in values


def test_scan_file_javascript_fixture() -> None:
    """scan_file should find expected literals in the JavaScript fixture."""
    occurrences = scan_file(_FIXTURES / "sample.js")
    values = _values(occurrences)
    nums = _numbers(occurrences)
    assert '"Bob"' in values
    assert "'Hi there'" in values
    assert "100" in nums
    assert "0.75" in nums
    assert '"2023/06/01"' in values
    assert '"10:30:00"' in values
    # Digits inside string literals must not be separately reported.
    assert "2023" not in nums
    assert "10" not in nums
    # Comment content must be excluded.
    assert '"excluded_line"' not in values
    assert "400" not in nums
    assert '"excluded_block"' not in values
    assert "500" not in nums


def test_scan_file_java_fixture() -> None:
    """scan_file should find expected literals in the Java fixture."""
    occurrences = scan_file(_FIXTURES / "Sample.java")
    values = _values(occurrences)
    nums = _numbers(occurrences)
    assert '"Charlie"' in values
    assert "99" in nums
    assert "3.14159" in nums
    # Java text block should be included.
    assert any(v.startswith('"""') for v in values)
    assert '"2023-06-01"' in values
    assert '"10:30:00"' in values
    assert "2023" not in nums
    assert "10" not in nums
    # Javadoc content must be excluded.
    assert '"excluded_doc"' not in values
    assert "200" not in nums
    # Single-line comment content must be excluded.
    assert '"excluded_line"' not in values
    assert "300" not in nums


def test_scan_file_go_fixture() -> None:
    """scan_file should find expected literals in the Go fixture."""
    occurrences = scan_file(_FIXTURES / "sample.go")
    values = _values(occurrences)
    nums = _numbers(occurrences)
    assert '"Alice"' in values
    assert "42" in nums
    assert "3.14" in nums
    # Comment content must be excluded.
    assert '"excluded_comment"' not in values
    assert "400" not in nums


# ---------------------------------------------------------------------------
# --functions-only
# ---------------------------------------------------------------------------


def test_scan_file_functions_only_python_includes_func_body() -> None:
    """--functions-only must include literals inside Python function bodies."""
    occurrences = scan_file(_FIXTURES / "func_sample.py", functions_only=True)
    values = _values(occurrences)
    assert "func_string" in " ".join(values)
    assert "method_string" in " ".join(values)
    assert "async_string" in " ".join(values)


def test_scan_file_functions_only_python_excludes_module_level() -> None:
    """--functions-only must exclude module-level literals in Python."""
    occurrences = scan_file(_FIXTURES / "func_sample.py", functions_only=True)
    values = _values(occurrences)
    assert '"module_string"' not in values


def test_scan_file_functions_only_python_excludes_class_var() -> None:
    """--functions-only must exclude class-level variables in Python."""
    occurrences = scan_file(_FIXTURES / "func_sample.py", functions_only=True)
    values = _values(occurrences)
    assert '"class_var"' not in values


def test_scan_file_functions_only_java_includes_method_body() -> None:
    """--functions-only must include literals inside Java method bodies."""
    occurrences = scan_file(_FIXTURES / "FuncSample.java", functions_only=True)
    values = _values(occurrences)
    assert '"method_string"' in values
    assert '"another_method"' in values


def test_scan_file_functions_only_java_excludes_class_field() -> None:
    """--functions-only must exclude class-level fields in Java."""
    occurrences = scan_file(_FIXTURES / "FuncSample.java", functions_only=True)
    values = _values(occurrences)
    assert '"class_field"' not in values


def test_scan_file_functions_only_js_includes_function_body() -> None:
    """--functions-only must include literals inside JS function bodies."""
    occurrences = scan_file(_FIXTURES / "func_sample.js", functions_only=True)
    values = _values(occurrences)
    assert '"func_string"' in values
    assert '"arrow_string"' in values
    assert '"control_inside"' in values


def test_scan_file_functions_only_js_excludes_module_level() -> None:
    """--functions-only must exclude module-level literals in JavaScript."""
    occurrences = scan_file(_FIXTURES / "func_sample.js", functions_only=True)
    values = _values(occurrences)
    assert '"module_string"' not in values


# ---------------------------------------------------------------------------
# New language mappings
# ---------------------------------------------------------------------------


def test_extension_to_language_c() -> None:
    """C and header extensions must map to C."""
    assert EXTENSION_TO_LANGUAGE[".c"] == "C"
    assert EXTENSION_TO_LANGUAGE[".h"] == "C"


def test_extension_to_language_cpp() -> None:
    """C++ extensions must map to C++."""
    assert EXTENSION_TO_LANGUAGE[".cpp"] == "C++"
    assert EXTENSION_TO_LANGUAGE[".cc"] == "C++"
    assert EXTENSION_TO_LANGUAGE[".hpp"] == "C++"


def test_extension_to_language_csharp() -> None:
    """C# extension must map to CSharp."""
    assert EXTENSION_TO_LANGUAGE[".cs"] == "CSharp"


def test_extension_to_language_rust() -> None:
    """Rust extension must map to Rust."""
    assert EXTENSION_TO_LANGUAGE[".rs"] == "Rust"


def test_extension_to_language_kotlin() -> None:
    """Kotlin extensions must map to Kotlin."""
    assert EXTENSION_TO_LANGUAGE[".kt"] == "Kotlin"
    assert EXTENSION_TO_LANGUAGE[".kts"] == "Kotlin"


def test_extension_to_language_swift() -> None:
    """Swift extension must map to Swift."""
    assert EXTENSION_TO_LANGUAGE[".swift"] == "Swift"


def test_extension_to_language_scala() -> None:
    """Scala extension must map to Scala."""
    assert EXTENSION_TO_LANGUAGE[".scala"] == "Scala"


def test_extension_to_language_groovy() -> None:
    """Groovy extensions must map to Groovy."""
    assert EXTENSION_TO_LANGUAGE[".groovy"] == "Groovy"
    assert EXTENSION_TO_LANGUAGE[".gradle"] == "Groovy"


# ---------------------------------------------------------------------------
# scan_literals – new languages (inline snippets)
# ---------------------------------------------------------------------------


def test_scan_literals_c_string() -> None:
    """It should find a string literal in C source."""
    occurrences = scan_literals(b'char *s = "Alice";', Path("f.c"), "C")
    assert '"Alice"' in _values(occurrences)


def test_scan_literals_c_number() -> None:
    """It should find a number literal (integer) in C source."""
    occurrences = scan_literals(b"int n = 99;", Path("f.c"), "C")
    assert "99" in _numbers(occurrences)


def test_scan_literals_c_float() -> None:
    """It should find a number literal (float) in C source."""
    occurrences = scan_literals(b"float x = 3.14;", Path("f.c"), "C")
    assert "3.14" in _numbers(occurrences)


def test_scan_literals_cpp_string() -> None:
    """It should find a string literal in C++ source."""
    occurrences = scan_literals(b'std::string s = "Alice";', Path("f.cpp"), "C++")
    assert '"Alice"' in _values(occurrences)


def test_scan_literals_cpp_number() -> None:
    """It should find a number literal in C++ source."""
    occurrences = scan_literals(b"int n = 99;", Path("f.cpp"), "C++")
    assert "99" in _numbers(occurrences)


def test_scan_literals_csharp_string() -> None:
    """It should find a string literal in C# source."""
    occurrences = scan_literals(b'string s = "Alice";', Path("f.cs"), "CSharp")
    assert '"Alice"' in _values(occurrences)


def test_scan_literals_csharp_integer() -> None:
    """It should find an integer literal in C# source."""
    occurrences = scan_literals(b"int n = 99;", Path("f.cs"), "CSharp")
    assert "99" in _numbers(occurrences)


def test_scan_literals_csharp_real() -> None:
    """It should find a real (float) literal in C# source."""
    occurrences = scan_literals(b"float x = 3.14f;", Path("f.cs"), "CSharp")
    assert "3.14f" in _values(occurrences)


def test_scan_literals_rust_string() -> None:
    """It should find a string literal in Rust source."""
    occurrences = scan_literals(b'let s = "Alice";', Path("f.rs"), "Rust")
    assert '"Alice"' in _values(occurrences)


def test_scan_literals_rust_integer() -> None:
    """It should find an integer literal in Rust source."""
    occurrences = scan_literals(b"let n: i32 = 99;", Path("f.rs"), "Rust")
    assert "99" in _numbers(occurrences)


def test_scan_literals_rust_float() -> None:
    """It should find a float literal in Rust source."""
    occurrences = scan_literals(b"let x: f64 = 3.14;", Path("f.rs"), "Rust")
    assert "3.14" in _numbers(occurrences)


def test_scan_literals_kotlin_string() -> None:
    """It should find a string literal in Kotlin source."""
    occurrences = scan_literals(b'val s = "Alice"', Path("f.kt"), "Kotlin")
    assert '"Alice"' in _values(occurrences)


def test_scan_literals_kotlin_number() -> None:
    """It should find an integer literal in Kotlin source."""
    occurrences = scan_literals(b"val n = 99", Path("f.kt"), "Kotlin")
    assert "99" in _numbers(occurrences)


def test_scan_literals_swift_string() -> None:
    """It should find a string literal in Swift source."""
    occurrences = scan_literals(b'let s = "Alice"', Path("f.swift"), "Swift")
    assert '"Alice"' in _values(occurrences)


def test_scan_literals_swift_integer() -> None:
    """It should find an integer literal in Swift source."""
    occurrences = scan_literals(b"let n = 99", Path("f.swift"), "Swift")
    assert "99" in _numbers(occurrences)


def test_scan_literals_scala_string() -> None:
    """It should find a string literal in Scala source."""
    occurrences = scan_literals(b'val s = "Alice"', Path("f.scala"), "Scala")
    assert '"Alice"' in _values(occurrences)


def test_scan_literals_scala_integer() -> None:
    """It should find an integer literal in Scala source."""
    occurrences = scan_literals(b"val n = 99", Path("f.scala"), "Scala")
    assert "99" in _numbers(occurrences)


def test_scan_literals_groovy_string() -> None:
    """It should find a string literal in Groovy source."""
    occurrences = scan_literals(b'def s = "Alice"', Path("f.groovy"), "Groovy")
    assert '"Alice"' in _values(occurrences)


def test_scan_literals_groovy_integer() -> None:
    """It should find an integer literal in Groovy source."""
    occurrences = scan_literals(b"def n = 99", Path("f.groovy"), "Groovy")
    assert "99" in _numbers(occurrences)


# ---------------------------------------------------------------------------
# Fixture-based integration tests for new languages
# ---------------------------------------------------------------------------


def test_scan_file_c_fixture() -> None:
    """scan_file should find expected literals in the C fixture."""
    occurrences = scan_file(_FIXTURES / "sample.c")
    values = _values(occurrences)
    nums = _numbers(occurrences)
    assert '"Alice"' in values
    assert "99" in nums
    assert "3.14" in nums
    assert '"excluded_comment"' not in values
    assert "400" not in nums


def test_scan_file_cpp_fixture() -> None:
    """scan_file should find expected literals in the C++ fixture."""
    occurrences = scan_file(_FIXTURES / "sample.cpp")
    values = _values(occurrences)
    nums = _numbers(occurrences)
    assert '"Alice"' in values
    assert "99" in nums
    assert "3.14" in nums
    assert '"excluded_comment"' not in values
    assert "400" not in nums


def test_scan_file_csharp_fixture() -> None:
    """scan_file should find expected literals in the C# fixture."""
    occurrences = scan_file(_FIXTURES / "Sample.cs")
    values = _values(occurrences)
    nums = _numbers(occurrences)
    assert '"Alice"' in values
    assert "99" in nums
    assert '"excluded_comment"' not in values
    assert "400" not in nums


def test_scan_file_rust_fixture() -> None:
    """scan_file should find expected literals in the Rust fixture."""
    occurrences = scan_file(_FIXTURES / "sample.rs")
    values = _values(occurrences)
    nums = _numbers(occurrences)
    assert '"Alice"' in values
    assert "99" in nums
    assert "3.14" in nums
    assert '"excluded_comment"' not in values
    assert "400" not in nums


def test_scan_file_kotlin_fixture() -> None:
    """scan_file should find expected literals in the Kotlin fixture."""
    occurrences = scan_file(_FIXTURES / "sample.kt")
    values = _values(occurrences)
    nums = _numbers(occurrences)
    assert '"Alice"' in values
    assert "99" in nums
    assert "3.14" in nums
    assert '"excluded_comment"' not in values
    assert "400" not in nums


def test_scan_file_swift_fixture() -> None:
    """scan_file should find expected literals in the Swift fixture."""
    occurrences = scan_file(_FIXTURES / "sample.swift")
    values = _values(occurrences)
    nums = _numbers(occurrences)
    assert '"Alice"' in values
    assert "99" in nums
    assert "3.14" in nums
    assert '"excluded_comment"' not in values
    assert "400" not in nums


def test_scan_file_scala_fixture() -> None:
    """scan_file should find expected literals in the Scala fixture."""
    occurrences = scan_file(_FIXTURES / "sample.scala")
    values = _values(occurrences)
    nums = _numbers(occurrences)
    assert '"Alice"' in values
    assert "99" in nums
    assert "3.14" in nums
    assert '"excluded_comment"' not in values
    assert "400" not in nums


def test_scan_file_groovy_fixture() -> None:
    """scan_file should find expected literals in the Groovy fixture."""
    occurrences = scan_file(_FIXTURES / "sample.groovy")
    values = _values(occurrences)
    nums = _numbers(occurrences)
    assert '"Alice"' in values
    assert "99" in nums
    assert "3.14" in nums
    assert '"excluded_comment"' not in values
    assert "400" not in nums


# ---------------------------------------------------------------------------
# --functions-only for new languages
# ---------------------------------------------------------------------------


def test_scan_file_functions_only_c_includes_func_body() -> None:
    """--functions-only must include literals inside C function bodies."""
    occurrences = scan_file(_FIXTURES / "func_sample.c", functions_only=True)
    values = _values(occurrences)
    assert '"func_string"' in values
    assert '"another_func"' in values


def test_scan_file_functions_only_c_excludes_global() -> None:
    """--functions-only must exclude global-scope literals in C."""
    occurrences = scan_file(_FIXTURES / "func_sample.c", functions_only=True)
    assert '"module_string"' not in _values(occurrences)


def test_scan_file_functions_only_rust_includes_func_body() -> None:
    """--functions-only must include literals inside Rust function bodies."""
    occurrences = scan_file(_FIXTURES / "func_sample.rs", functions_only=True)
    values = _values(occurrences)
    assert '"func_string"' in values
    assert '"another_func"' in values


def test_scan_file_functions_only_rust_excludes_global() -> None:
    """--functions-only must exclude global-scope literals in Rust."""
    occurrences = scan_file(_FIXTURES / "func_sample.rs", functions_only=True)
    assert '"module_string"' not in _values(occurrences)
