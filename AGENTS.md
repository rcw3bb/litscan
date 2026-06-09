# AGENTS.md

## Purpose

litscan is a Python CLI tool (Python ^3.14, Poetry 2.2, PEP 621) that scans a codebase for string
and numeric literals, helping developers spot hard-coded values in source files. Entry point:
`litscan.cli:main` (run as `poetry run litscan`). No runtime dependencies; dev deps are black,
pylint, pytest, and pytest-cov. Test: `poetry run pytest --cov=litscan tests --cov-report html`.
Format and lint: `poetry run black litscan; poetry run pylint litscan`. Quality gates: ≥90% coverage,
pylint 10/10. Author: Ron Webb (ron@ronella.xyz), version 1.0.0.

## Tree

- litscan/ — main package (CLI, scanner, utilities)
- litscan/__init__.py — package init; sets `__version__`
- litscan/cli.py — CLI entry point (`main` function)
- litscan/logging.ini — logging config bundled inside the package; seeded into `LITSCAN_CONFIG_DIR` on first run
- litscan/scanner.py — literal scanning logic
- litscan/store.py — SQLite session store (`SessionStore`); occurrences persisted per UUID, deleted after report
- litscan/reporter.py — report generation (JSON + HTML output); exposes `write_outputs`
- tests/ — pytest suite mirroring litscan/ structure
- tests/fixtures/ — sample source files used in tests (java, js, py)
- tests/test_store.py — tests for store module
- tests/test_reporter.py — tests for reporter module
- pyproject.toml — PEP 621 project metadata and Poetry build config
- .pylintrc — pylint config (must match canonical gist)
- reports/ — scanner output artifacts (HTML, JSON)
- CHANGELOG.md — version history

## Rules

- Before adding a module, place it inside litscan/; mirror its path under tests/ as test_*.py.
- Before changing logging setup, verify logging.ini matches its canonical gist; `setup_logger` is provided by the `logenrich` external library — do not re-implement it in the package.
- Never modify pyproject.toml version, .pylintrc, or poetry.lock without explicit approval.
- When the version is updated, keep it in sync across all three locations: `pyproject.toml` (`version` field), `README.md` (version badge or reference), and `litscan/__init__.py` (`__version__`).
- Use relative imports within litscan/; add type hints to all function arguments and return values.
- Use `collections.abc` instead of deprecated `typing` generics (e.g. `Callable`, `Sequence`).
- Naming: snake_case for variables/methods, PascalCase for classes, UPPER_CASE for constants; prefix private members with `_`.
- Every module, class, and method must have a docstring with `Author: Ron Webb` and `Since: 1.0.0`; for versions > 1.0.0 add Author/Since only to newly introduced classes or methods.
- Apply SOLID, DRY, and composition over inheritance; use dependency injection where applicable; decompose large methods into smaller private methods.
- When .env is used, load it with python-dotenv.
- When you create or discover new files, update the Tree above.

## Note-taking

- After each task, log any correction, preference, or pattern learned.
- Write to the matching docs file's "Session learnings" section; if none fits, add to Rules above. One dated line, plain language. e.g. "Pylint plugin X needed for dataclasses (learned 5/31)"
- 3+ related notes → create a new docs/ file. Move notes there. Update the Tree. Keep this file under 100 lines.