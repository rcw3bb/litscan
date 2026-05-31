"""Session-scoped SQLite store for literal occurrences.

Occurrences produced during parallel file scanning are written directly to an
SQLite database instead of accumulated in memory.  Every scan run is assigned
a UUID so multiple concurrent invocations share the same database file without
interference.  After the report is written the caller deletes the session
records, keeping the database lean.

Author: Ron Webb
Since: 1.0.0
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

from .scanner import LiteralGroup, LiteralOccurrence

_CREATE_TABLE = (
    "CREATE TABLE IF NOT EXISTS occurrences ("
    "    session_id TEXT NOT NULL,"
    "    file_path  TEXT NOT NULL,"
    "    line       INTEGER NOT NULL,"
    "    col        INTEGER NOT NULL,"
    "    value      TEXT NOT NULL"
    ")"
)
_CREATE_INDEX = "CREATE INDEX IF NOT EXISTS idx_session ON occurrences (session_id)"
_INSERT = (
    "INSERT INTO occurrences (session_id, file_path, line, col, value)"
    " VALUES (?, ?, ?, ?, ?)"
)
_SELECT_GROUPS = (
    "SELECT value, COUNT(*) AS cnt,"
    " GROUP_CONCAT(file_path || ':' || line || ':' || col, '|||')"
    " FROM occurrences WHERE session_id = ?"
    " GROUP BY value"
    " ORDER BY cnt DESC, value ASC"
)
_DELETE_SESSION = "DELETE FROM occurrences WHERE session_id = ?"

# Separator used inside GROUP_CONCAT; must not appear in file paths or loc strings.
_LOC_SEP = "|||"


class SessionStore:
    """SQLite-backed session store for literal occurrences.

    A single database file is shared across all threads and concurrent runs.
    Every run is identified by a *session_id* (UUID string) so records are
    always isolated.  Grouping and aggregation are performed entirely in SQL so
    Python never holds all raw occurrences in memory at once.

    Author: Ron Webb
    Since: 1.0.0
    """

    def __init__(self, db_path: Path) -> None:
        """Open (or create) the SQLite database at *db_path*.

        WAL journal mode is enabled so reads and writes do not block each
        other; a threading lock serialises Python-side connection calls since
        :mod:`sqlite3` connection objects are not thread-safe.

        Author: Ron Webb
        Since: 1.0.0
        """
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._lock = threading.Lock()
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.execute(_CREATE_TABLE)
            self._conn.execute(_CREATE_INDEX)
            self._conn.commit()

    def insert_occurrences(
        self, session_id: str, occurrences: list[LiteralOccurrence]
    ) -> None:
        """Persist *occurrences* for *session_id* in the database.

        Author: Ron Webb
        Since: 1.0.0
        """
        rows = [
            (session_id, str(o.file_path), o.line, o.column, o.value)
            for o in occurrences
        ]
        with self._lock:
            self._conn.executemany(_INSERT, rows)
            self._conn.commit()

    def read_groups(self, session_id: str) -> list[LiteralGroup]:
        """Return grouped literals for *session_id*, aggregated in SQL.

        Grouping and counting are done entirely inside SQLite; only the final
        :class:`~litscan.scanner.LiteralGroup` objects are constructed in
        Python, so memory usage is proportional to the number of *unique*
        literals, not the total number of occurrences.

        Author: Ron Webb
        Since: 1.0.0
        """
        with self._lock:
            rows = self._conn.execute(_SELECT_GROUPS, (session_id,)).fetchall()
        return [
            LiteralGroup(
                count=row[1],
                literal=row[0],
                files=row[2].split(_LOC_SEP) if row[2] else [],
            )
            for row in rows
        ]

    def delete_session(self, session_id: str) -> None:
        """Remove all occurrences belonging to *session_id* from the database.

        Author: Ron Webb
        Since: 1.0.0
        """
        with self._lock:
            self._conn.execute(_DELETE_SESSION, (session_id,))
            self._conn.commit()

    def close(self) -> None:
        """Close the underlying database connection.

        Author: Ron Webb
        Since: 1.0.0
        """
        with self._lock:
            self._conn.close()
