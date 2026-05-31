# Changelog

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