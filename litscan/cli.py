"""Command-line interface for litscan.

Author: Ron Webb
Since: 1.0.0
"""

from __future__ import annotations

import concurrent.futures
import os
import sys
import tempfile
import uuid
from collections.abc import Generator
from pathlib import Path

import click
from braincraft.ignorefile import IgnoreFile
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
from . import __app_name__ as _APP_NAME
from . import CONF_DIR
from . import PATH_IGNORE_PATH
from .reporter import write_outputs
from .scanner import decode_literal, scan_file
from .store import SessionStore

_VALID_FORMATS = ("json", "html", "all")
_VALID_MODES = ("string", "number", "both")


def _configure_stream_encoding(stream: object) -> None:
    """Force *stream* to UTF-8 with a replacing error handler when possible.

    Prevents UnicodeEncodeError on legacy Windows code pages or restrictive
    locales. Streams without ``reconfigure`` (e.g. click's test runner) are
    left untouched instead of raising.

    Author: Ron Webb
    Since: 2.1.0
    """
    reconfigure = getattr(stream, "reconfigure", None)
    if callable(reconfigure):
        reconfigure(encoding="utf-8", errors="replace")


_configure_stream_encoding(sys.stdout)
_configure_stream_encoding(sys.stderr)
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


def _parse_literals(raw: str) -> set[str]:
    """Parse a semicolon-separated literal-value string into a set of targets.

    Example: ``"foo;bar"`` → ``{'foo', 'bar'}``

    Author: Ron Webb
    Since: 2.1.0
    """
    return {part.strip() for part in raw.split(";") if part.strip()}


def _scan_and_store(task: tuple[Path, SessionStore, str, bool, str]) -> None:
    """Scan one file and write its occurrences to the session store.

    Accepts a 5-tuple so the function can be passed directly to
    :meth:`concurrent.futures.Executor.map` without a closure.

    Author: Ron Webb
    Since: 1.0.0
    """
    file_path, store, session_id, functions_only, mode = task
    store.insert_occurrences(
        session_id, scan_file(file_path, functions_only=functions_only, mode=mode)
    )


def _build_ignore(base_dir: Path) -> IgnoreFile | None:
    """Build a path-ignore matcher anchored at *base_dir*.

    Returns ``None`` when the bundled ignore file is missing or unreadable
    (including a decoding failure from non-UTF-8 content) so callers can
    proceed without path filtering instead of failing the whole scan.

    Author: Ron Webb
    Since: 2.1.0
    """
    try:
        return IgnoreFile(PATH_IGNORE_PATH, base_dir=base_dir)
    except FileNotFoundError:
        _logger.warning("Ignore file not found at %s", PATH_IGNORE_PATH)
        return None
    except UnicodeDecodeError as exc:
        _logger.warning(
            "Ignore file at %s is not valid UTF-8: %s", PATH_IGNORE_PATH, exc
        )
        return None


def _walk_unignored(
    root: Path, ignore: IgnoreFile | None
) -> Generator[Path, None, None]:
    """Recursively yield files under *root*, pruning directories matched by *ignore*.

    Author: Ron Webb
    Since: 2.1.0
    """
    for entry in root.iterdir():
        if ignore is not None and ignore.is_ignored(entry):
            continue
        if entry.is_dir():
            yield from _walk_unignored(entry, ignore)
        elif entry.is_file():
            yield entry


def discover_files(
    path: Path, extensions: list[str], ignore: IgnoreFile | None = None
) -> list[Path]:
    """Discover files under *path* that match the given extensions.

    When *extensions* is empty every file is included.
    Both files and directories are accepted; for a plain file the extension
    filter still applies. When *ignore* is given, matching files are skipped
    and matching directories are pruned from the walk entirely.

    Author: Ron Webb
    Since: 1.0.0
    """
    candidates: list[Path]
    if path.is_file():
        candidates = [] if ignore is not None and ignore.is_ignored(path) else [path]
    elif path.is_dir():
        candidates = sorted(_walk_unignored(path, ignore))
    else:
        return []

    if not extensions:
        return candidates
    return [f for f in candidates if f.suffix.lower() in extensions]


def _run_concurrent_scan(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    files: list[Path],
    store: SessionStore,
    session_id: str,
    workers: int,
    functions_only: bool = False,
    mode: str = "both",
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
                executor.submit(
                    _scan_and_store, (f, store, session_id, functions_only, mode)
                ): f
                for f in files
            }
            for future in concurrent.futures.as_completed(futures):
                try:
                    future.result()
                except Exception as exc:  # pylint: disable=broad-exception-caught
                    _logger.warning("Failed to scan %s: %s", futures[future], exc)
                progress.advance(task)


@click.command()
@click.version_option(
    version=__version__, prog_name=_APP_NAME, message="%(prog)s v%(version)s"
)
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
@click.option(
    "--functions-only",
    "functions_only",
    is_flag=True,
    default=False,
    help=(
        "Scan only literals that appear inside function or method implementations. "
        "Supported languages: Python, JavaScript, TypeScript, Java, Go, Gosu, "
        "C, C++, C#, Rust, Kotlin, Swift, Scala, Groovy."
    ),
)
@click.option(
    "--min",
    "min_count",
    type=int,
    default=0,
    help=(
        "Minimum occurrence count a literal must have to be included in the "
        "report (default: 0, no filtering)."
    ),
)
@click.option(
    "--mode",
    default="both",
    type=click.Choice(_VALID_MODES),
    help="Literal category to scan: string, number, or both (default: both).",
)
@click.option(
    "--literals",
    default="",
    help=(
        "Semicolon-separated target literal values to restrict the report to "
        "(matched against the decoded, single-line literal value; e.g. "
        "'foo;bar'). Omit to include all literals."
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
    functions_only: bool,
    min_count: int,
    mode: str,
    literals: str,
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
    literals_targets = _parse_literals(literals) if literals else set()
    seen: set[Path] = set()
    files: list[Path] = []

    with _console.status("[bold cyan]Discovering files\u2026", spinner="dots"):
        for target_path in paths:
            ignore = _build_ignore(target_path)
            for found_file in discover_files(target_path, extensions, ignore):
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
    interrupted = False
    groups: list[dict[str, object]] = []
    written: list[Path] = []
    try:
        _run_concurrent_scan(files, store, session_id, workers, functions_only, mode)
        groups = store.read_groups(session_id)
        groups = [g for g in groups if g["count"] >= min_count]
        if literals_targets:
            groups = [
                g
                for g in groups
                if "\n" not in g["literal"]
                and decode_literal(g["literal"]) in literals_targets
            ]
        stem = Path(output).stem
        written = write_outputs(
            groups,
            output_dir,
            stem,
            fmt,
            paths_scanned=[str(p) for p in paths],
            min_count=min_count,
            mode=mode,
            literals=sorted(literals_targets),
        )
    except KeyboardInterrupt:
        interrupted = True
        _console.print("[yellow]Scan interrupted by user.[/yellow]")
    finally:
        store.delete_session(session_id)
        store.close()

    if interrupted:
        raise SystemExit(1)

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
