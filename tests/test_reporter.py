"""Tests for reporter module.

Author: Ron Webb
Since: 1.0.0
"""

from __future__ import annotations

import json
from pathlib import Path

from litscan.reporter import _build_html, _write_html, _write_json, write_outputs
from litscan.scanner import LiteralGroup


def _make_group(literal: str, count: int, files: list[str]) -> LiteralGroup:
    """Return a minimal LiteralGroup fixture."""
    return LiteralGroup(count=count, literal=literal, files=files)


def test_write_json_creates_file(tmp_path: Path) -> None:
    """It should create a JSON file at the given path."""
    groups = [_make_group("'hello'", 2, ["src/a.js:1:0", "src/a.js:2:0"])]
    out = tmp_path / "report.json"
    _write_json(groups, out, "2026-01-01 00:00:00")
    assert out.exists()


def test_write_json_structure(tmp_path: Path) -> None:
    """The JSON file should contain application, version, run-date, and findings."""
    groups = [_make_group("42", 1, ["main.py:10:4"])]
    out = tmp_path / "report.json"
    _write_json(groups, out, "2026-05-31 12:00:00")
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["application"] == "litscan"
    assert "version" in data
    assert data["run-date"] == "2026-05-31 12:00:00"
    assert len(data["findings"]) == 1
    assert data["findings"][0]["literal"] == "42"


def test_write_json_findings_content(tmp_path: Path) -> None:
    """Each finding should preserve count and files from the group."""
    groups = [_make_group('"Ron"', 3, ["a.py:1:0", "b.py:2:4", "c.py:5:8"])]
    out = tmp_path / "report.json"
    _write_json(groups, out, "2026-01-01 00:00:00")
    data = json.loads(out.read_text(encoding="utf-8"))
    finding = data["findings"][0]
    assert finding["count"] == 3
    assert finding["literal"] == '"Ron"'
    assert finding["files"] == ["a.py:1:0", "b.py:2:4", "c.py:5:8"]


def test_build_html_returns_string(tmp_path: Path) -> None:
    """_build_html should return a non-empty HTML string."""
    groups = [_make_group("'test'", 1, ["f.py:1:0"])]
    result = _build_html(groups, "2026-01-01 00:00:00")
    assert isinstance(result, str)
    assert result.startswith("<!DOCTYPE html>")


def test_build_html_contains_literal(tmp_path: Path) -> None:
    """The HTML output should contain the literal value."""
    groups = [_make_group("'unique_literal'", 1, ["x.py:5:2"])]
    result = _build_html(groups, "2026-01-01 00:00:00")
    assert "'unique_literal'" in result


def test_build_html_contains_counts(tmp_path: Path) -> None:
    """The HTML output should include the total and unique literal counts."""
    groups = [
        _make_group("'a'", 3, ["f.py:1:0", "f.py:2:0", "f.py:3:0"]),
        _make_group("'b'", 1, ["f.py:4:0"]),
    ]
    result = _build_html(groups, "2026-01-01 00:00:00")
    # total = 4, unique = 2
    assert "4 literals" in result
    assert "2 unique" in result


def test_build_html_escapes_special_chars() -> None:
    """The HTML output should escape angle brackets in literal data cells."""
    groups = [_make_group("<script>", 1, ["evil.js:1:0"])]
    result = _build_html(groups, "2026-01-01 00:00:00")
    assert "&lt;script&gt;" in result
    # The unescaped value must not appear inside a <code> element
    assert "<code><script>" not in result


def test_write_html_creates_file(tmp_path: Path) -> None:
    """It should create an HTML file at the given path."""
    groups = [_make_group("'hi'", 1, ["f.py:1:0"])]
    out = tmp_path / "report.html"
    _write_html(groups, out, "2026-01-01 00:00:00")
    assert out.exists()
    content = out.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in content


def test_write_outputs_json_format(tmp_path: Path) -> None:
    """write_outputs with fmt='json' should write only a .json file."""
    groups = [_make_group("1", 1, ["f.py:1:0"])]
    written = write_outputs(groups, tmp_path, "out", "json")
    assert len(written) == 1
    assert written[0].suffix == ".json"
    assert (tmp_path / "out.json").exists()
    assert not (tmp_path / "out.html").exists()


def test_write_outputs_html_format(tmp_path: Path) -> None:
    """write_outputs with fmt='html' should write only an .html file."""
    groups = [_make_group("1", 1, ["f.py:1:0"])]
    written = write_outputs(groups, tmp_path, "out", "html")
    assert len(written) == 1
    assert written[0].suffix == ".html"
    assert (tmp_path / "out.html").exists()
    assert not (tmp_path / "out.json").exists()


def test_write_outputs_all_format(tmp_path: Path) -> None:
    """write_outputs with fmt='all' should write both .json and .html files."""
    groups = [_make_group("1", 1, ["f.py:1:0"])]
    written = write_outputs(groups, tmp_path, "out", "all")
    assert len(written) == 2
    assert (tmp_path / "out.json").exists()
    assert (tmp_path / "out.html").exists()


def test_write_outputs_creates_missing_directory(tmp_path: Path) -> None:
    """write_outputs should create the output directory when it does not exist."""
    groups = [_make_group("'x'", 1, ["f.py:1:0"])]
    out_dir = tmp_path / "nested" / "deep"
    write_outputs(groups, out_dir, "report", "json")
    assert (out_dir / "report.json").exists()


def test_write_outputs_returns_paths(tmp_path: Path) -> None:
    """write_outputs should return Path objects for every file written."""
    groups = [_make_group("'x'", 1, ["f.py:1:0"])]
    written = write_outputs(groups, tmp_path, "result", "all")
    assert all(isinstance(p, Path) for p in written)
