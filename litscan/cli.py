"""Command-line interface for litscan.

Author: Ron Webb
Since: 1.0.0
"""

from __future__ import annotations

import concurrent.futures
import os
import tempfile
import uuid
from pathlib import Path

import click
from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)

from logenrich import setup_logger

from . import __version__
from . import CONF_DIR
from .reporter import write_outputs
from .scanner import scan_file
from .store import SessionStore

_VALID_FORMATS = ("json", "html", "all")
_APP_NAME = "litscan"
_console = Console(stderr=True)
_logger = setup_logger(__name__, conf_dir=CONF_DIR)


def _parse_extensions(raw: str) -> list[str]:
    """Parse a comma-separated extension string into a normalised list.

    Each entry is lowercased and prefixed with a dot when absent.
    Example: ``"py,js, TS"`` → ``['.py', '.js', '.ts']``

    Author: Ron Webb
    Since: 1.0.0
    """
    result: list[str] = []
    for part in raw.split(","):
        ext = part.strip().lower()
        if ext and not ext.startswith("."):
            ext = "." + ext
        if ext:
            result.append(ext)
    return result


def _parse_paths(raw: str) -> list[Path]:
    """Parse a semicolon-separated path string into a list of Path objects.

    Example: ``"/src/a; /src/b"`` → ``[Path('/src/a'), Path('/src/b')]``

    Author: Ron Webb
    Since: 1.0.0
    """
    result: list[Path] = []
    for part in raw.split(";"):
        stripped = part.strip()
        if stripped:
            result.append(Path(stripped))
    return result


def _scan_and_store(task: tuple[Path, SessionStore, str]) -> None:
    """Scan one file and write its occurrences to the session store.

    Accepts a 3-tuple so the function can be passed directly to
    :meth:`concurrent.futures.Executor.map` without a closure.

    Author: Ron Webb
    Since: 1.0.0
    """
    file_path, store, session_id = task
    store.insert_occurrences(session_id, scan_file(file_path))


def discover_files(path: Path, extensions: list[str]) -> list[Path]:
    """Discover files under *path* that match the given extensions.

    When *extensions* is empty every file is included.
    Both files and directories are accepted; for a plain file the extension
    filter still applies.

    Author: Ron Webb
    Since: 1.0.0
    """
    candidates: list[Path]
    if path.is_file():
        candidates = [path]
    elif path.is_dir():
        candidates = sorted(f for f in path.rglob("*") if f.is_file())
    else:
        return []

    if not extensions:
        return candidates
    return [f for f in candidates if f.suffix.lower() in extensions]


def _run_concurrent_scan(
    files: list[Path],
    store: SessionStore,
    session_id: str,
    workers: int,
) -> None:
    """Scan *files* concurrently and store results under *session_id*.

    Displays a live progress bar via the module-level rich console.

    Author: Ron Webb
    Since: 1.0.0
    """
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=_console,
        transient=True,
    ) as progress:
        task = progress.add_task("[cyan]Scanning\u2026", total=len(files))
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(_scan_and_store, (f, store, session_id)): f
                for f in files
            }
            for future in concurrent.futures.as_completed(futures):
                try:
                    future.result()
                except Exception as exc:  # pylint: disable=broad-exception-caught
                    _logger.warning("Failed to scan %s: %s", futures[future], exc)
                progress.advance(task)


@click.command()
@click.argument("path")
@click.option(
    "--ext",
    default="",
    help=(
        "Comma-separated file extensions to include "
        "(e.g. py,java,js,ts). Omit to scan all files."
    ),
)
@click.option(
    "--output",
    default="litscan-output",
    help=(
        "Base name (without extension) for the output file(s) "
        "(default: litscan-output)."
    ),
)
@click.option(
    "--output-dir",
    "output_dir",
    default="reports",
    type=click.Path(path_type=Path),
    help=(
        "Directory where the output file will be written "
        "(default: reports). "
        "The filename from --output is placed inside this directory."
    ),
)
@click.option(
    "--format",
    "fmt",
    default="json",
    type=click.Choice(_VALID_FORMATS),
    help="Output format: json, html, or all (default: json).",
)
@click.option(
    "--workers",
    type=int,
    default=min(32, (os.cpu_count() or 1) + 4),
    help=(
        "Number of parallel worker threads used to scan files "
        "(default: min(32, cpu_count + 4))."
    ),
)
@click.option(
    "--db",
    "db_path",
    default=str(Path(tempfile.gettempdir()) / "litscan.db"),
    type=click.Path(path_type=Path),
    help=(
        "Path to the SQLite scratch database used to store occurrences "
        "during a scan run (default: <system-temp>/litscan.db). "
        "Session records are removed after the report is written."
    ),
)
def main(  # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals
    path: str,
    ext: str,
    output: str,
    output_dir: Path,
    fmt: str,
    workers: int,
    db_path: Path,
) -> None:
    """Scan source files for string and numeric literals.

    Author: Ron Webb
    Since: 1.0.0
    """
    _header = f"{_APP_NAME} v{__version__}"
    _logger.info(_header)
    _console.print(f"[bold]{_header}[/bold]")
    extensions = _parse_extensions(ext) if ext else []
    paths = _parse_paths(path)
    seen: set[Path] = set()
    files: list[Path] = []

    with _console.status("[bold cyan]Discovering files\u2026", spinner="dots"):
        for target_path in paths:
            for found_file in discover_files(target_path, extensions):
                if found_file not in seen:
                    seen.add(found_file)
                    files.append(found_file)

    if not files:
        _logger.info("No files found in %s", path)
        _console.print("[yellow]No files found.[/yellow]")
        return

    _console.print(f"[bold]Scanning[/bold] {len(files)} file(s)\u2026")

    session_id = str(uuid.uuid4())
    store = SessionStore(db_path)
    try:
        _run_concurrent_scan(files, store, session_id, workers)
        groups = store.read_groups(session_id)
        stem = Path(output).stem
        written = write_outputs(groups, output_dir, stem, fmt)
    finally:
        store.delete_session(session_id)
        store.close()

    total = sum(g["count"] for g in groups)
    _logger.info(
        "Found %s literals (%s unique) -> %s",
        total,
        len(groups),
        ", ".join(str(p) for p in written),
    )
    _console.print(
        f"[bold green]\u2713[/bold green] "
        f"[bold]{total}[/bold] literals "
        f"([bold]{len(groups)}[/bold] unique) "
        f"\u2192 {', '.join(str(p) for p in written)}"
    )


if __name__ == "__main__":
    main()  # pylint: disable=no-value-for-parameter
