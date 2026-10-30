"""Remove retired permission-version constraints from existing preflight caches."""

from __future__ import annotations

import sqlite3

from migrations.ensure_current_schema_columns import resolve_sqlite_path


OBSOLETE_COLUMNS = (
    "supplied_permission_set_version",
    "expected_permission_set_version",
)


def migrate(database_url: str | None = None) -> list[str]:
    """Preserve graph-bound evidence and keys; roll back unexpected dependencies."""
    with sqlite3.connect(resolve_sqlite_path(database_url)) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("BEGIN IMMEDIATE")
        exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            ("deployment_preflight_cache",),
        ).fetchone()
        if exists is None:
            return ["skip missing table: deployment_preflight_cache"]
        columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(deployment_preflight_cache)")
        }
        actions: list[str] = []
        for column in OBSOLETE_COLUMNS:
            if column in columns:
                connection.execute(
                    f'ALTER TABLE deployment_preflight_cache DROP COLUMN "{column}"'
                )
                actions.append(f"dropped: deployment_preflight_cache.{column}")
            else:
                actions.append(f"absent: deployment_preflight_cache.{column}")
        return actions
