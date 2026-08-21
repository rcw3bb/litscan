# Changelog

## 2.0.0 - 2026-08-22

### Added

- `litscan/parser.py` — new module that loads tree-sitter `Language` objects via `@lru_cache` and creates a fresh `Parser` per call (tree-sitter 0.26+ C-extension isolation requirement).
- `EXTENSION_TO_LANGUAGE`, `LITERAL_NODE_TYPES`, and `FUNCTION_NODE_TYPES` constants in `scanner.py` covering 14 languages: Python, JavaScript, TypeScript, Java, Go, Gosu, C, C++, C#, Rust, Kotlin, Swift, Scala, and Groovy.
- `_WalkContext` dataclass in `scanner.py` for bundling fixed AST-walk parameters.
- `_is_docstring()` helper that excludes Python triple-quoted docstrings from results via AST parent-chain inspection.
- `_walk_literals()` recursive tree-sitter node walker that stops recursing at matched literal nodes.
- Fifteen new tree-sitter runtime dependencies: `tree-sitter` (core), `tree-sitter-python`, `tree-sitter-javascript`, `tree-sitter-typescript`, `tree-sitter-java`, `tree-sitter-go`, `tree-sitter-gosu`, `tree-sitter-c`, `tree-sitter-cpp`, `tree-sitter-c-sharp`, `tree-sitter-rust`, `tree-sitter-kotlin`, `tree-sitter-swift`, `tree-sitter-scala`, `tree-sitter-groovy`.
- Test fixtures for all new languages: `sample.c`, `sample.cpp`, `sample.cs`, `sample.rs`, `sample.kt`, `sample.swift`, `sample.scala`, `sample.groovy`, `func_sample.c`, `func_sample.rs`, plus `sample.go`.

### Changed

- `scanner.py` fully rewritten to use tree-sitter AST walking. `scan_literals()` now accepts `source_bytes: bytes` and an explicit `language: str` instead of a plain source string. Literal detection is language-specific via the node-type tables.
- `scan_file()` now derives the language from the file extension via `EXTENSION_TO_LANGUAGE`; unsupported extensions are skipped with a warning instead of silently returning nothing.
- `__init__.py` `EnvDirBootstrap` resources reduced to `["logging.ini", "lit_ignore"]`; `LIT_BRACE_EXT_PATH` and `LIT_CONTROL_KW_PATH` exports removed.
- `cli.py` `--functions-only` help text updated to list all 14 supported languages.
- Fixture filenames normalised to lowercase (`sample.java`, `func_sample.java`, `sample.cs`) for compatibility with case-sensitive Linux CI filesystems.

### Removed

- `lit_brace_ext` config file and all brace-style extension loading/matching logic (`_load_brace_suffixes`, `_BRACE_STYLE_SUFFIXES`).
- `lit_control_kw` config file and all control-keyword loading logic (`_load_control_keywords`, `_CONTROL_KW`).
- Regex-based literal scanning, comment and docstring masking helpers, and brace-region detection functions (all superseded by tree-sitter AST walking).

## 1.4.0 - 2026-07-05

### Added

- `--version` CLI flag that prints the application name and version then exits.
- `lit_brace_ext` config file bundled inside the package and seeded to `LITSCAN_CONFIG_DIR` on first run; one extension per line, additive to the built-in `_BRACE_STYLE_SUFFIXES` set used by `--functions-only`.
- `lit_control_kw` config file bundled inside the package and seeded to `LITSCAN_CONFIG_DIR` on first run; one keyword per line, additive to the built-in `_CONTROL_KW` set that excludes control-flow blocks from function detection.
- `_load_brace_suffixes()` and `_load_control_keywords()` loader functions in `scanner.py` that read the new config files and union their entries into the respective frozensets at startup.
- `__app_name__` constant exported from `litscan/__init__.py` alongside `__version__`.
- Graceful `KeyboardInterrupt` handling in `main()`: prints an interrupted message, cleans up the SQLite session, and exits with code 1.

### Changed

- `cli.py` no longer defines `_APP_NAME` locally; imports `__app_name__` from `litscan/__init__.py` instead.
- `litscan/__init__.py` `EnvDirBootstrap` resources list extended with `"lit_brace_ext"` and `"lit_control_kw"`; exports `LIT_BRACE_EXT_PATH` and `LIT_CONTROL_KW_PATH`.

## 1.3.1 - 2026-06-11

### Changed

- `_BRACE_STYLE_SUFFIXES` in `scanner.py` extended with `.gs` and `.gsx` so that JSX/TSX files are recognised as brace-style sources for `--functions-only` scanning.
- README `## License` section added linking to the MIT `LICENSE` file.

## 1.3.0 - 2026-06-11

### Added

- `--functions-only` CLI flag that restricts literal scanning to literals found inside function or method implementations.
- `_get_python_function_regions()` — uses `ast` to locate `FunctionDef` / `AsyncFunctionDef` nodes and return their character ranges in Python source.
- `_get_brace_style_function_regions()` — brace-matching parser that identifies function/method bodies in Java, JS, TS, C/C++, C#, Go, Rust, Kotlin, Swift, Scala, and Groovy source files.
- `_mask_for_structure()` — strips comments and string literals (preserving newlines) before structural brace analysis.
- `_BRACE_STYLE_SUFFIXES` and `_CONTROL_KW` constants in `scanner.py` to enumerate supported brace-style file types and exclude control-flow blocks.
- New test fixtures: `tests/fixtures/func_sample.py`, `tests/fixtures/func_sample.js`, `tests/fixtures/FuncSample.java`.

### Changed

- `_scan_and_store()` task tuple extended from 3-tuple to 4-tuple to carry the `functions_only` flag through to `scan_file()`.
- `_run_concurrent_scan()` and `main()` updated to accept and propagate the `functions_only` parameter.
- `scan_file()` passes `functions_only` down to `scan_literals()`.
- README updated with `--functions-only` option and example.

## 1.2.0 - 2026-06-09

### Added

- GitHub Actions CI/CD workflow (`publish.yml`) that runs tests on push to `main` and publishes to PyPI using `PYPI_TOKEN`.
- `_mask_non_literals()` pre-scan step that replaces comments and Python docstrings with spaces before literal matching, preserving line/column offsets.
- `_is_docstring_position()` helper that identifies whether a triple-quoted string occupies a docstring position (module-, class-, or function-level).
- `_PYTHON_SUFFIXES` constant (`{".py", ".pyi"}`) and `_MASK_PATTERN` regex used by the masking step.

### Changed

- `CONF_DIR` now derived via `_bootstrapper.get_dir()` instead of `_bootstrapper.resolve("logging.ini").parent`.
- Multiline literal truncation marker in the HTML report now embeds the full literal text in the tooltip (`title` attribute) so users can inspect it by hovering.
- `scan_literals()` now runs source through `_mask_non_literals()` before applying the literal regex, skipping comments and docstrings.
- Coverage quality gate raised from ≥ 80% to ≥ 90%.
- README updated with PyPI publishing instructions, ignore-pattern documentation, and architecture diagram corrections.

## 1.1.0 - 2026-06-07

### Added

- `lit_ignore` file bundled inside the package and seeded to `LITSCAN_CONFIG_DIR` on first run; contains regex patterns (one per line) for literals to exclude from scan results.
- `ignore_patterns` parameter on `scan_literals()` for overriding the default ignore patterns at call time.
- `logenrich` dependency; delegates logger setup to the library's `setup_logger`.
- `env-dir-bootstrap` dependency; `EnvDirBootstrap` now bootstraps both `logging.ini` and `lit_ignore` into `LITSCAN_CONFIG_DIR`.
- `CONF_DIR` and `LIT_IGNORE_PATH` constants exported from `litscan/__init__.py`.

### Changed

- `scan_literals()` now skips any literal whose value matches a pattern from the active ignore list.
- `litscan/__init__.py` wires up `EnvDirBootstrap` on import so config files are always available before any module uses them.

### Removed

- `util.py` and its `setup_logger` helper; logging setup is now fully handled by the `logenrich` library.

## 1.0.0 - 2026-05-31

### Added

- Regex-based literal scanner supporting triple-quoted strings, double-quoted strings, single-quoted strings, decimal numbers, and integer numbers.
- `SessionStore`: thread-safe SQLite scratch store that persists occurrences keyed by a UUID per scan run; records are deleted after the report is written.
- `reporter.py`: JSON and HTML report generation via `write_outputs()`.
- Parallel file scanning using `ThreadPoolExecutor`.
- `rich`-powered progress bar displayed on stderr during scans.
- `logging.ini` bundled inside the package and seeded to `LITSCAN_CONFIG_DIR` on first run.
- `--workers` option to control the number of parallel scanner threads (default: `min(32, cpu_count + 4)`).
- `--db` option for a custom SQLite database path (default: `<system-temp>/litscan.db`).
- `LITSCAN_CONFIG_DIR` environment variable for overriding the logging configuration directory.