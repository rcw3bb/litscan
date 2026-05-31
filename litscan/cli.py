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
import argparse

from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)

from . import __version__
from .reporter import write_outputs
from .scanner import scan_file
from .store import SessionStore
from .util import setup_logger

_VALID_FORMATS = ("json", "html", "all")
_APP_NAME = "litscan"
_console = Console(stderr=True)


def _parse_extensions(raw: str) -> list[str]:
    """Parse a comma-separated extension string into a normalised list.

    Each entry is lowercased and prefixed with a dot when absent.
    Example: ``"py,js, TS"`` → ``['.py', '.js', '.ts']``
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
    """Parse a comma-separated path string into a list of Path objects.

    Example: ``"/src/a; /src/b"`` → ``[Path('/src/a'), Path('/src/b')]``
    """
    result: list[Path] = []
    for part in raw.split(";"):
        stripped = part.strip()
        if stripped:
            result.append(Path(stripped))
    return result


def build_parser() -> argparse.ArgumentParser:
    """Build and return the argument parser."""
    parser = argparse.ArgumentParser(
        description="Scan files for string and numeric literals"
    )
    parser.add_argument(
        "path",
        help=(
            "Target directory (or directories) to scan. "
            "Separate multiple paths with a semicolon "
            "(e.g. src;lib;tests)."
        ),
    )
    parser.add_argument(
        "--ext",
        default="",
        help=(
            "Comma-separated file extensions to include "
            "(e.g. py,js,ts). Omit to scan all files."
        ),
    )
    parser.add_argument(
        "--output",
        default="litscan-output",
        help=(
            "Base name (without extension) for the output file(s) "
            "(default: litscan-output)."
        ),
    )
    parser.add_argument(
        "--output-dir",
        default=Path("reports"),
        type=Path,
        help=(
            "Directory where the output file will be written "
            "(default: reports). "
            "The filename from --output is placed inside this directory."
        ),
    )
    parser.add_argument(
        "--format",
        default="json",
        choices=_VALID_FORMATS,
        help="Output format: json, html, or all (default: json).",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=min(32, (os.cpu_count() or 1) + 4),
        help=(
            "Number of parallel worker threads used to scan files "
            "(default: min(32, cpu_count + 4))."
        ),
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=Path(tempfile.gettempdir()) / "litscan.db",
        help=(
            "Path to the SQLite scratch database used to store occurrences "
            "during a scan run (default: <system-temp>/litscan.db). "
            "Session records are removed after the report is written."
        ),
    )
    return parser


def _output_stem(name: str) -> str:
    """Return the stem of the output name, stripping any file extension."""
    return Path(name).stem


def _scan_and_store(task: tuple[Path, SessionStore, str]) -> None:
    """Scan one file and write its occurrences to the session store.

    Accepts a 3-tuple so the function can be passed directly to
    :meth:`concurrent.futures.Executor.map` without a closure.
    """
    file_path, store, session_id = task
    store.insert_occurrences(session_id, scan_file(file_path))


def discover_files(path: Path, extensions: list[str]) -> list[Path]:
    """Discover files under *path* that match the given extensions.

    When *extensions* is empty every file is included.
    Both files and directories are accepted; for a plain file the extension
    filter still applies.
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
                future.result()
                progress.advance(task)


def main() -> int:
    """Run the CLI entry point."""
    logger = setup_logger(__name__)
    _header = f"{_APP_NAME} v{__version__}"
    logger.info(_header)
    _console.print(f"[bold]{_header}[/bold]")
    args = build_parser().parse_args()
    extensions = _parse_extensions(args.ext) if args.ext else []
    paths = _parse_paths(args.path)
    seen: set[Path] = set()
    files: list[Path] = []

    with _console.status("[bold cyan]Discovering files\u2026", spinner="dots"):
        for target_path in paths:
            for found_file in discover_files(target_path, extensions):
                if found_file not in seen:
                    seen.add(found_file)
                    files.append(found_file)

    if not files:
        logger.info("No files found in %s", args.path)
        _console.print("[yellow]No files found.[/yellow]")
        return 0

    _console.print(f"[bold]Scanning[/bold] {len(files)} file(s)\u2026")

    session_id = str(uuid.uuid4())
    store = SessionStore(args.db)
    try:
        _run_concurrent_scan(files, store, session_id, args.workers)
        groups = store.read_groups(session_id)
        stem = _output_stem(args.output)
        written = write_outputs(groups, args.output_dir, stem, args.format)
        store.delete_session(session_id)
    finally:
        store.close()

    total = sum(g["count"] for g in groups)
    logger.info(
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
