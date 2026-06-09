# Changelog

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