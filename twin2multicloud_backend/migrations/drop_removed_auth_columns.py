"""Remove obsolete production-auth columns from the local PoC user table."""

from __future__ import annotations

import sqlite3

from migrations.ensure_current_schema_columns import resolve_sqlite_path


OBSOLETE_COLUMNS = ("picture_url", "auth_provider", "last_login_at")


def migrate(database_url: str | None = None) -> list[str]:
    """Drop removed auth columns while preserving every active user field."""
    database_path = resolve_sqlite_path(database_url)
    with sqlite3.connect(database_path) as connection:
        if not _table_exists(connection, "users"):
            return ["skip missing table: users"]

        existing = _columns(connection, "users")
        actions: list[str] = []
        for column in OBSOLETE_COLUMNS:
            if column not in existing:
                actions.append(f"absent: users.{column}")
                continue
            connection.execute(f'ALTER TABLE users DROP COLUMN "{column}"')
            actions.append(f"dropped: users.{column}")
        connection.commit()
        return actions


def _table_exists(connection: sqlite3.Connection, table: str) -> bool:
    return (
        connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table,),
        ).fetchone()
        is not None
    )


def _columns(connection: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in connection.execute(f'PRAGMA table_info("{table}")')}


if __name__ == "__main__":
    for action in migrate():
        print(action)
