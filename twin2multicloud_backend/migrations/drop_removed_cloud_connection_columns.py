"""Remove retired pricing/permission metadata without rebuilding credentials."""

from __future__ import annotations

import sqlite3

from migrations.ensure_current_schema_columns import resolve_sqlite_path


OBSOLETE_COLUMNS = ("is_default_for_pricing", "permission_set_version")
OBSOLETE_INDEXES = (
    "uq_cloud_connections_pricing_default",
    "ix_cloud_connections_permission_set_version",
)


def migrate(database_url: str | None = None) -> list[str]:
    """Drop only retired metadata atomically; retain payloads, IDs and bindings."""
    database_path = resolve_sqlite_path(database_url)
    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        # SQLite DDL needs an explicit transaction for all-or-nothing rollback.
        connection.execute("BEGIN IMMEDIATE")
        exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            ("cloud_connections",),
        ).fetchone()
        if exists is None:
            return ["skip missing table: cloud_connections"]
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(cloud_connections)")
        }
        for index in OBSOLETE_INDEXES:
            connection.execute(f'DROP INDEX IF EXISTS "{index}"')
        actions: list[str] = []
        for column in OBSOLETE_COLUMNS:
            if column in columns:
                connection.execute(
                    f'ALTER TABLE cloud_connections DROP COLUMN "{column}"'
                )
                actions.append(f"dropped: cloud_connections.{column}")
            else:
                actions.append(f"absent: cloud_connections.{column}")
        return actions
