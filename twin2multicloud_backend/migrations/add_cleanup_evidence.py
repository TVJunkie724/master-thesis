"""Add first-class post-destroy cleanup evidence to operations."""

from __future__ import annotations

import sqlite3

from migrations.ensure_current_schema_columns import resolve_sqlite_path


def migrate(database_url: str | None = None) -> list[str]:
    """Add the nullable JSON evidence column idempotently."""
    database_path = resolve_sqlite_path(database_url)
    actions: list[str] = []
    with sqlite3.connect(database_path) as connection:
        columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(deployments)").fetchall()
        }
        if "cleanup_evidence" not in columns:
            connection.execute(
                "ALTER TABLE deployments ADD COLUMN cleanup_evidence JSON"
            )
            actions.append("added: deployments.cleanup_evidence")
        else:
            actions.append("present: deployments.cleanup_evidence")
        connection.commit()
    return actions
