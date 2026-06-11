# litscan 1.3.1

> A small CLI tool that scans a codebase for string and numeric literals, helping you quickly spot hard-coded values in source files.

## Prerequisites

- Python 3.14+

## Installation

```powershell
pip install litscan
```

## Usage

After installation, litscan is available as a console script:

```powershell
litscan <path> [options]
```

### What is detected

The scanner recognises the following literal types in any source file:

| Type | Examples |
|------|---------|
| Triple-quoted strings (multiline) | `"""hello"""`, `'''world'''` |
| Double-quoted strings | `"hello"` |
| Single-quoted strings | `'world'` |
| Decimal numbers | `3.14`, `0.5` |
| Integer numbers | `42`, `0` |

Results are grouped by unique literal value and sorted by occurrence count (highest first).

### Arguments

| Argument | Description |
|----------|-------------|
| `path`   | Target directory or file to scan. Multiple paths can be specified, separated by a semicolon (e.g. `src;lib;tests`). |

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--ext <exts>` | _(all files)_ | Comma-separated extensions to include (e.g. `py,js,ts`) |
| `--output <name>` | `litscan-output` | Base name (without extension) for output file(s) |
| `--output-dir <dir>` | `reports` | Directory where output file(s) will be written |
| `--format <fmt>` | `json` | Output format: `json`, `html`, or `all` |
| `--workers <n>` | `min(32, cpu_count + 4)` | Number of parallel worker threads used during scanning |
| `--db <path>` | `<system-temp>/litscan.db` | Path to the SQLite scratch database that stores occurrences during a scan run. Session records are removed after the report is written. |
| `--functions-only` | _(off)_ | Scan only literals that appear inside function or method implementations. Supported for Python and brace-style languages (Java, JS, JSX, TS, TSX, C/C++, C#, Go, Rust, Kotlin, Swift, Scala, Groovy, GS, GSX). |

### Examples

Scan all files in the current directory and produce a JSON report:

```powershell
litscan .
```

Scan only Python and JavaScript files in `src/`:

```powershell
litscan src --ext py,js
```

Generate both JSON and HTML reports in a custom directory:

```powershell
litscan . --format all --output-dir my-reports
```

Scan a Java source tree with a custom output name:

```powershell
litscan src/main/java --ext java --format all --output-dir reports
```

Scan only literals inside functions and methods:

```powershell
litscan src --functions-only
```

## Configuration

| Environment variable | Description |
|----------------------|-------------|
| `LITSCAN_CONFIG_DIR` | Directory where `logging.ini` and `lit_ignore` are seeded and read from. When unset, the bundled copies inside the package are used directly. |

### Ignore patterns

The `lit_ignore` file (seeded into `LITSCAN_CONFIG_DIR` on first run) contains one regex pattern per line. Any literal whose value matches a pattern is excluded from scan results. Edit the file to suppress noise such as common stop-words or numeric constants you do not care about.

## Development

### Prerequisites

- Poetry 2.2+

### Installation

```powershell
poetry install
```

### Architecture

```mermaid
flowchart TD
    CLI["cli.py\n(entry point)"] --> logenrich["setup_logger()\nlogenrich"]
    CLI --> discover["discover_files()"]
    discover --> concurrent["ThreadPoolExecutor\n(parallel scan)"]
    concurrent --> scan["scan_file()\nscanner.py"]
    scan --> litignore["lit_ignore\n(exclude patterns)"]
    scan --> store["SessionStore\nstore.py (SQLite)"]
    store --> report["write_outputs()\nreporter.py"]
    report --> JSON["JSON report"]
    report --> HTML["HTML report"]
```

| Module | Responsibility |
|--------|---------------|
| `cli.py` | Argument parsing, file discovery, orchestration |
| `scanner.py` | Regex-based literal extraction; `LiteralOccurrence` / `LiteralGroup` types |
| `store.py` | `SessionStore` — thread-safe SQLite scratch store; one UUID per scan run |
| `reporter.py` | `write_outputs()` — renders JSON and/or HTML reports |
| `logenrich` | External library that provides `setup_logger()` — logging config seeded from `logging.ini` |

### Test with coverage

```powershell
poetry run pytest --cov=litscan tests --cov-report html
```

### Format and lint

```powershell
poetry run black litscan; poetry run pylint litscan
```

### Quality gates

- Coverage ≥ 90%
- Pylint score 10/10

### Example

Scan the test fixtures and produce both JSON and HTML reports:

```powershell
poetry run litscan tests\fixtures --format all
```

## Publishing to PyPI

### Prerequisites

- A [PyPI](https://pypi.org/) account with an API token.

### Configure the token

```bash
poetry config pypi-token.pypi <your-token>
```

### Build and publish

```bash
poetry publish --build
```

This builds the source distribution and wheel, then uploads them to PyPI in one step.

> **Note:** PyPI releases are immutable. Once a version is published, it cannot be overwritten.  
> To fix a mistake, yank the release via the PyPI web UI and publish a new version.

## [Changelog](CHANGELOG.md)

## License

[MIT](LICENSE)

## Author

Ron Webb &lt;ron@ronella.xyz&gt;
