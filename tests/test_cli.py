"""Tests for cli module.

Author: Ron Webb
Since: 1.0.0
"""

from __future__ import annotations

from pathlib import Path
import json
import logging

from click.testing import CliRunner

from litscan import cli


def test_parse_paths_single_path() -> None:
    """It should parse a single path string into a one-element list."""
    result = cli._parse_paths("/src/project")
    assert result == [Path("/src/project")]


def test_parse_paths_multiple_paths() -> None:
    """It should parse a semicolon-separated string into multiple Path objects."""
    result = cli._parse_paths("src; lib ; tests")
    assert result == [Path("src"), Path("lib"), Path("tests")]


def test_parse_paths_ignores_empty_segments() -> None:
    """It should skip empty segments produced by trailing or double semicolons."""
    result = cli._parse_paths("src;;lib;")
    assert result == [Path("src"), Path("lib")]


def test_discover_files_for_file_and_dir(tmp_path: Path) -> None:
    """It should discover files from both file and directory inputs."""
    sample_file = tmp_path / "sample.js"
    sample_file.write_text("var x = 1;\n", encoding="utf-8")
    nested = tmp_path / "pkg"
    nested.mkdir()
    nested_file = nested / "mod.ts"
    nested_file.write_text("const y = 2;\n", encoding="utf-8")

    file_result = cli.discover_files(sample_file, [])
    dir_result = cli.discover_files(tmp_path, [])

    assert file_result == [sample_file]
    assert nested_file in dir_result


def test_discover_files_extension_filter(tmp_path: Path) -> None:
    """It should return only files matching the given extensions."""
    js_file = tmp_path / "app.js"
    js_file.write_text("var a = 1;", encoding="utf-8")
    txt_file = tmp_path / "notes.txt"
    txt_file.write_text("hello", encoding="utf-8")

    result = cli.discover_files(tmp_path, [".js"])

    assert js_file in result
    assert txt_file not in result


def test_discover_files_no_match_returns_empty(tmp_path: Path) -> None:
    """It should return an empty list when no files match the extensions."""
    (tmp_path / "app.js").write_text("x = 1;", encoding="utf-8")
    result = cli.discover_files(tmp_path, [".py"])
    assert result == []


def test_discover_files_nonexistent_path_returns_empty(tmp_path: Path) -> None:
    """It should return an empty list for a path that does not exist."""
    result = cli.discover_files(tmp_path / "missing", [])
    assert result == []


def test_main_returns_zero_when_no_files(monkeypatch) -> None:
    """It should return zero when there are no files to scan."""
    monkeypatch.setattr(cli, "setup_logger", lambda _name: logging.getLogger("tests"))
    monkeypatch.setattr(cli, "discover_files", lambda _path, _ext: [])
    runner = CliRunner()

    result = runner.invoke(cli.main, ["some_dir"])

    assert result.exit_code == 0


def test_main_writes_json_for_discovered_file(tmp_path: Path, monkeypatch) -> None:
    """It should write a JSON file with discovered literal occurrences."""
    sample_file = tmp_path / "example.js"
    sample_file.write_text("name = 'Ron';\n", encoding="utf-8")
    out_dir = tmp_path / "out"

    monkeypatch.setattr(cli, "setup_logger", lambda _name: logging.getLogger("tests"))
    runner = CliRunner()

    result = runner.invoke(cli.main, [str(tmp_path), "--output-dir", str(out_dir)])
    data = json.loads((out_dir / "litscan-output.json").read_text(encoding="utf-8"))

    assert result.exit_code == 0
    assert any(g["literal"] == "'Ron'" for g in data["findings"])
    assert any("example.js" in f for g in data["findings"] for f in g["files"])


def test_main_ext_flag_filters_files(tmp_path: Path, monkeypatch) -> None:
    """It should only scan files matching --ext when the flag is provided."""
    js_file = tmp_path / "app.js"
    js_file.write_text("x = 'hello';", encoding="utf-8")
    txt_file = tmp_path / "notes.txt"
    txt_file.write_text("y = 'world';", encoding="utf-8")
    out_dir = tmp_path / "out"

    monkeypatch.setattr(cli, "setup_logger", lambda _name: logging.getLogger("tests"))
    runner = CliRunner()

    result = runner.invoke(
        cli.main, [str(tmp_path), "--ext", "js", "--output-dir", str(out_dir)]
    )
    data = json.loads((out_dir / "litscan-output.json").read_text(encoding="utf-8"))
    all_files = [f for g in data["findings"] for f in g["files"]]

    assert result.exit_code == 0
    assert any("app.js" in f for f in all_files)
    assert not any("notes.txt" in f for f in all_files)


def test_main_json_contains_count_and_files(tmp_path: Path, monkeypatch) -> None:
    """It should write a JSON file with count and file locations per literal."""
    sample_file = tmp_path / "code.js"
    # 'hello' appears twice, 42 appears once
    sample_file.write_text("x = 'hello'; y = 'hello'; z = 42;", encoding="utf-8")
    out_dir = tmp_path / "out"

    monkeypatch.setattr(cli, "setup_logger", lambda _name: logging.getLogger("tests"))
    runner = CliRunner()

    result = runner.invoke(cli.main, [str(tmp_path), "--output-dir", str(out_dir)])
    data = json.loads((out_dir / "litscan-output.json").read_text(encoding="utf-8"))
    hello_group = next(g for g in data["findings"] if g["literal"] == "'hello'")

    assert result.exit_code == 0
    assert hello_group["count"] == 2
    assert len(hello_group["files"]) == 2


def test_main_default_output_dir_is_reports(tmp_path: Path, monkeypatch) -> None:
    """It should write the output into the 'reports' directory by default."""
    sample_file = tmp_path / "code.js"
    sample_file.write_text("x = 'default';", encoding="utf-8")
    reports_dir = tmp_path / "reports"

    monkeypatch.setattr(cli, "setup_logger", lambda _name: logging.getLogger("tests"))
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()

    result = runner.invoke(cli.main, [str(tmp_path)])

    assert result.exit_code == 0
    assert (reports_dir / "litscan-output.json").exists()


def test_main_output_dir_places_file_in_directory(tmp_path: Path, monkeypatch) -> None:
    """It should write the output file inside the given --output-dir."""
    sample_file = tmp_path / "code.js"
    sample_file.write_text("x = 'hi';", encoding="utf-8")
    out_dir = tmp_path / "results"

    monkeypatch.setattr(cli, "setup_logger", lambda _name: logging.getLogger("tests"))
    runner = CliRunner()

    result = runner.invoke(cli.main, [str(tmp_path), "--output-dir", str(out_dir)])
    expected_file = out_dir / "litscan-output.json"

    assert result.exit_code == 0
    assert expected_file.exists()
    data = json.loads(expected_file.read_text(encoding="utf-8"))
    assert any(g["literal"] == "'hi'" for g in data["findings"])


def test_main_output_dir_creates_missing_directory(tmp_path: Path, monkeypatch) -> None:
    """It should create the output directory when it does not yet exist."""
    sample_file = tmp_path / "code.js"
    sample_file.write_text("x = 42;", encoding="utf-8")
    out_dir = tmp_path / "nested" / "deep"

    monkeypatch.setattr(cli, "setup_logger", lambda _name: logging.getLogger("tests"))
    runner = CliRunner()

    result = runner.invoke(cli.main, [str(tmp_path), "--output-dir", str(out_dir)])

    assert result.exit_code == 0
    assert (out_dir / "litscan-output.json").exists()


def test_main_output_dir_with_custom_filename(tmp_path: Path, monkeypatch) -> None:
    """It should use the stem of --output as the base filename inside --output-dir."""
    sample_file = tmp_path / "code.js"
    sample_file.write_text("x = 'test';", encoding="utf-8")
    out_dir = tmp_path / "out"

    monkeypatch.setattr(cli, "setup_logger", lambda _name: logging.getLogger("tests"))
    runner = CliRunner()

    result = runner.invoke(
        cli.main, [str(tmp_path), "--output", "custom", "--output-dir", str(out_dir)]
    )

    assert result.exit_code == 0
    assert (out_dir / "custom.json").exists()


def test_main_format_html_writes_html_file(tmp_path: Path, monkeypatch) -> None:
    """It should write an HTML file when --format html is supplied."""
    sample_file = tmp_path / "code.js"
    sample_file.write_text("x = 'hi';", encoding="utf-8")
    out_dir = tmp_path / "out"

    monkeypatch.setattr(cli, "setup_logger", lambda _name: logging.getLogger("tests"))
    runner = CliRunner()

    result = runner.invoke(
        cli.main, [str(tmp_path), "--format", "html", "--output-dir", str(out_dir)]
    )
    html_file = out_dir / "litscan-output.html"

    assert result.exit_code == 0
    assert html_file.exists()
    assert not (out_dir / "litscan-output.json").exists()
    content = html_file.read_text(encoding="utf-8")
    assert "LitScan" in content and "Report" in content
    assert "'hi'" in content


def test_main_format_html_escapes_special_characters(
    tmp_path: Path, monkeypatch
) -> None:
    """It should HTML-escape literal values in the HTML report."""
    sample_file = tmp_path / "code.js"
    sample_file.write_text('x = "<b>bold</b>";\n', encoding="utf-8")
    out_dir = tmp_path / "out"

    monkeypatch.setattr(cli, "setup_logger", lambda _name: logging.getLogger("tests"))
    runner = CliRunner()

    result = runner.invoke(
        cli.main, [str(tmp_path), "--format", "html", "--output-dir", str(out_dir)]
    )
    content = (out_dir / "litscan-output.html").read_text(encoding="utf-8")

    assert result.exit_code == 0
    assert "&lt;b&gt;bold&lt;/b&gt;" in content


def test_main_format_all_writes_both_files(tmp_path: Path, monkeypatch) -> None:
    """It should write both JSON and HTML files when --format all is supplied."""
    sample_file = tmp_path / "code.js"
    sample_file.write_text("x = 'both';", encoding="utf-8")
    out_dir = tmp_path / "out"

    monkeypatch.setattr(cli, "setup_logger", lambda _name: logging.getLogger("tests"))
    runner = CliRunner()

    result = runner.invoke(
        cli.main, [str(tmp_path), "--format", "all", "--output-dir", str(out_dir)]
    )

    assert result.exit_code == 0
    assert (out_dir / "litscan-output.json").exists()
    assert (out_dir / "litscan-output.html").exists()
    json_data = json.loads(
        (out_dir / "litscan-output.json").read_text(encoding="utf-8")
    )
    assert any(g["literal"] == "'both'" for g in json_data["findings"])
    html_content = (out_dir / "litscan-output.html").read_text(encoding="utf-8")
    assert "'both'" in html_content


def test_main_logs_app_header_on_startup(tmp_path: Path, monkeypatch, caplog) -> None:
    """It should log the application name and version as a header on startup."""
    (tmp_path / "code.js").write_text("x = 1;", encoding="utf-8")
    out_dir = tmp_path / "out"
    test_logger = logging.getLogger("test.cli.header")

    monkeypatch.setattr(cli, "setup_logger", lambda _name: test_logger)
    runner = CliRunner()

    with caplog.at_level(logging.INFO, logger="test.cli.header"):
        runner.invoke(cli.main, [str(tmp_path), "--output-dir", str(out_dir)])

    assert any("litscan v" in r.message for r in caplog.records)


def test_main_format_json_explicit_writes_only_json(
    tmp_path: Path, monkeypatch
) -> None:
    """It should write only a JSON file when --format json is supplied explicitly."""
    sample_file = tmp_path / "code.js"
    sample_file.write_text("x = 99;", encoding="utf-8")
    out_dir = tmp_path / "out"

    monkeypatch.setattr(cli, "setup_logger", lambda _name: logging.getLogger("tests"))
    runner = CliRunner()

    result = runner.invoke(
        cli.main, [str(tmp_path), "--format", "json", "--output-dir", str(out_dir)]
    )

    assert result.exit_code == 0
    assert (out_dir / "litscan-output.json").exists()
    assert not (out_dir / "litscan-output.html").exists()


def test_main_multiple_comma_separated_paths(tmp_path: Path, monkeypatch) -> None:
    """It should scan and merge findings from all comma-separated target paths."""
    dir_a = tmp_path / "a"
    dir_a.mkdir()
    (dir_a / "file_a.js").write_text("x = 'alpha';", encoding="utf-8")
    dir_b = tmp_path / "b"
    dir_b.mkdir()
    (dir_b / "file_b.js").write_text("x = 'beta';", encoding="utf-8")
    out_dir = tmp_path / "out"

    monkeypatch.setattr(cli, "setup_logger", lambda _name: logging.getLogger("tests"))
    runner = CliRunner()

    result = runner.invoke(cli.main, [f"{dir_a};{dir_b}", "--output-dir", str(out_dir)])
    data = json.loads((out_dir / "litscan-output.json").read_text(encoding="utf-8"))
    all_literals = [g["literal"] for g in data["findings"]]

    assert result.exit_code == 0
    assert "'alpha'" in all_literals
    assert "'beta'" in all_literals


def test_main_multiple_paths_deduplicates_overlapping_files(
    tmp_path: Path, monkeypatch
) -> None:
    """It should not double-count literals when the same file appears in two paths."""
    sub = tmp_path / "src"
    sub.mkdir()
    (sub / "code.js").write_text("x = 'once';", encoding="utf-8")
    out_dir = tmp_path / "out"

    # Pass the sub-directory and its parent – code.js would appear twice without dedup
    monkeypatch.setattr(cli, "setup_logger", lambda _name: logging.getLogger("tests"))
    runner = CliRunner()

    result = runner.invoke(
        cli.main, [f"{sub};{tmp_path}", "--output-dir", str(out_dir)]
    )
    data = json.loads((out_dir / "litscan-output.json").read_text(encoding="utf-8"))
    once_group = next(g for g in data["findings"] if g["literal"] == "'once'")

    assert result.exit_code == 0
    assert once_group["count"] == 1


def test_main_workers_flag_is_accepted(tmp_path: Path, monkeypatch) -> None:
    """It should accept --workers and still produce correct output."""
    sample_file = tmp_path / "code.js"
    sample_file.write_text("x = 'parallel';", encoding="utf-8")
    out_dir = tmp_path / "out"

    monkeypatch.setattr(cli, "setup_logger", lambda _name: logging.getLogger("tests"))
    runner = CliRunner()

    result = runner.invoke(
        cli.main, [str(tmp_path), "--workers", "2", "--output-dir", str(out_dir)]
    )
    data = json.loads((out_dir / "litscan-output.json").read_text(encoding="utf-8"))

    assert result.exit_code == 0
    assert any(g["literal"] == "'parallel'" for g in data["findings"])


def test_main_functions_only_flag_excludes_module_level(
    tmp_path: Path, monkeypatch
) -> None:
    """With --functions-only, module-level literals must not appear in the report."""
    sample_file = tmp_path / "code.py"
    sample_file.write_text(
        'MODULE = "top"\ndef foo():\n    x = "inside"\n', encoding="utf-8"
    )
    out_dir = tmp_path / "out"

    monkeypatch.setattr(cli, "setup_logger", lambda _name: logging.getLogger("tests"))
    runner = CliRunner()

    result = runner.invoke(
        cli.main,
        [str(tmp_path), "--functions-only", "--output-dir", str(out_dir)],
    )
    data = json.loads((out_dir / "litscan-output.json").read_text(encoding="utf-8"))
    all_literals = [g["literal"] for g in data["findings"]]

    assert result.exit_code == 0
    assert '"inside"' in all_literals
    assert '"top"' not in all_literals


def test_main_version_flag_prints_version(monkeypatch) -> None:
    """--version should print the program name and version then exit with code 0."""
    monkeypatch.setattr(cli, "setup_logger", lambda _name: logging.getLogger("tests"))
    runner = CliRunner()

    result = runner.invoke(cli.main, ["--version"])

    assert result.exit_code == 0
    assert "litscan" in result.output
    assert cli.__version__ in result.output


def test_main_keyboard_interrupt_exits_with_code_1(tmp_path: Path, monkeypatch) -> None:
    """A KeyboardInterrupt during scanning must print an interrupted message and exit 1."""
    sample_file = tmp_path / "code.js"
    sample_file.write_text("x = 1;", encoding="utf-8")
    out_dir = tmp_path / "out"

    def _raise_interrupt(*_args: object, **_kwargs: object) -> None:
        raise KeyboardInterrupt()

    monkeypatch.setattr(cli, "setup_logger", lambda _name: logging.getLogger("tests"))
    monkeypatch.setattr(cli, "_run_concurrent_scan", _raise_interrupt)
    runner = CliRunner()

    result = runner.invoke(cli.main, [str(tmp_path), "--output-dir", str(out_dir)])

    assert result.exit_code == 1
    assert "interrupted" in result.output.lower()
