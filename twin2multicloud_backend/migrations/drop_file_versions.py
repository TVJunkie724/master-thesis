"""Drop the unused per-file revision table from the thesis PoC."""

from __future__ import annotations

import sqlite3

from migrations.ensure_current_schema_columns import resolve_sqlite_path


def migrate(database_url: str | None = None) -> list[str]:
    """Remove the unused table; portable archives replace file-version storage."""
    database_path = resolve_sqlite_path(database_url)
    with sqlite3.connect(database_path) as connection:
        exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            ("file_versions",),
        ).fetchone()
        if exists is None:
            return ["absent: file_versions"]
        connection.execute("DROP TABLE file_versions")
        connection.commit()
        return ["dropped: file_versions"]
