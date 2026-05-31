"""Tests for store module.

Author: Ron Webb
Since: 1.0.0
"""

from pathlib import Path

import pytest

from litscan.scanner import LiteralOccurrence
from litscan.store import SessionStore


def _make_occurrence(value: str, line: int = 1, col: int = 0) -> LiteralOccurrence:
    """Return a minimal LiteralOccurrence for testing."""
    return LiteralOccurrence(
        file_path=Path("code.py"), line=line, column=col, value=value
    )


def test_session_store_insert_and_read_groups(tmp_path: Path) -> None:
    """Inserted occurrences should appear in read_groups for the same session."""
    store = SessionStore(tmp_path / "test.db")
    try:
        occurrences = [_make_occurrence("'hello'"), _make_occurrence("42")]
        store.insert_occurrences("session-1", occurrences)
        groups = store.read_groups("session-1")
        literals = [g["literal"] for g in groups]
        assert "'hello'" in literals
        assert "42" in literals
    finally:
        store.close()


def test_session_store_count_reflects_duplicates(tmp_path: Path) -> None:
    """Count for a literal should reflect the total number of occurrences."""
    store = SessionStore(tmp_path / "test.db")
    try:
        occurrences = [
            _make_occurrence("'x'", line=1),
            _make_occurrence("'x'", line=2),
            _make_occurrence("'x'", line=3),
        ]
        store.insert_occurrences("session-1", occurrences)
        groups = store.read_groups("session-1")
        group = next(g for g in groups if g["literal"] == "'x'")
        assert group["count"] == 3
        assert len(group["files"]) == 3
    finally:
        store.close()


def test_session_store_groups_sorted_by_count_desc(tmp_path: Path) -> None:
    """read_groups should return entries sorted by count descending."""
    store = SessionStore(tmp_path / "test.db")
    try:
        store.insert_occurrences(
            "s",
            [
                _make_occurrence("'a'", 1),
                _make_occurrence("'b'", 2),
                _make_occurrence("'b'", 3),
            ],
        )
        groups = store.read_groups("s")
        assert groups[0]["literal"] == "'b'"
        assert groups[0]["count"] == 2
    finally:
        store.close()


def test_session_store_isolates_sessions(tmp_path: Path) -> None:
    """Occurrences from different sessions must not mix."""
    store = SessionStore(tmp_path / "test.db")
    try:
        store.insert_occurrences("alpha", [_make_occurrence("'alpha-value'")])
        store.insert_occurrences("beta", [_make_occurrence("'beta-value'")])

        alpha_literals = [g["literal"] for g in store.read_groups("alpha")]
        beta_literals = [g["literal"] for g in store.read_groups("beta")]

        assert "'alpha-value'" in alpha_literals
        assert "'beta-value'" not in alpha_literals
        assert "'beta-value'" in beta_literals
        assert "'alpha-value'" not in beta_literals
    finally:
        store.close()


def test_session_store_delete_session_removes_only_that_session(
    tmp_path: Path,
) -> None:
    """delete_session should remove only the specified session's records."""
    store = SessionStore(tmp_path / "test.db")
    try:
        store.insert_occurrences("to-delete", [_make_occurrence("'gone'")])
        store.insert_occurrences("to-keep", [_make_occurrence("'stays'")])

        store.delete_session("to-delete")

        assert store.read_groups("to-delete") == []
        kept = [g["literal"] for g in store.read_groups("to-keep")]
        assert "'stays'" in kept
    finally:
        store.close()


def test_session_store_read_groups_empty_when_no_occurrences(
    tmp_path: Path,
) -> None:
    """read_groups should return an empty list for an unknown session."""
    store = SessionStore(tmp_path / "test.db")
    try:
        assert store.read_groups("nonexistent-session") == []
    finally:
        store.close()


def test_session_store_insert_empty_list_is_noop(tmp_path: Path) -> None:
    """Inserting an empty occurrence list should not raise and produce no groups."""
    store = SessionStore(tmp_path / "test.db")
    try:
        store.insert_occurrences("empty-session", [])
        assert store.read_groups("empty-session") == []
    finally:
        store.close()


def test_session_store_files_contain_location_strings(tmp_path: Path) -> None:
    """Each entry in files should be in file_path:line:col format."""
    store = SessionStore(tmp_path / "test.db")
    try:
        store.insert_occurrences(
            "s",
            [
                LiteralOccurrence(
                    file_path=Path("src/a.py"), line=5, column=3, value="99"
                )
            ],
        )
        groups = store.read_groups("s")
        group = next(g for g in groups if g["literal"] == "99")
        assert any("src" in f and ":5:3" in f for f in group["files"])
    finally:
        store.close()


def test_session_store_concurrent_inserts(tmp_path: Path) -> None:
    """Concurrent inserts from multiple threads should all be persisted."""
    import concurrent.futures

    store = SessionStore(tmp_path / "test.db")
    try:
        session_id = "concurrent-session"

        def insert_batch(offset: int) -> None:
            occurrences = [
                _make_occurrence(f"'{offset}-{i}'", line=i) for i in range(10)
            ]
            store.insert_occurrences(session_id, occurrences)

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            list(executor.map(insert_batch, range(8)))

        groups = store.read_groups(session_id)
        assert len(groups) == 80  # 8 batches × 10 unique values each
    finally:
        store.close()
