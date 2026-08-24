"""Add secret-free setup-only cleanup progress markers."""

from __future__ import annotations

import os
import sqlite3

from migrations.ensure_current_schema_columns import resolve_sqlite_path


def migrate(database_url: str | None = None) -> list[str]:
    path = resolve_sqlite_path(database_url or os.environ.get("DATABASE_URL"))
    actions: list[str] = []
    with sqlite3.connect(path) as connection:
        columns = {
            row[1]
            for row in connection.execute(
                "PRAGMA table_info(cloud_bootstrap_sessions)"
            )
        }
        for column in (
            "setup_generated_access_clean",
            "setup_local_connection_clean",
        ):
            if column in columns:
                continue
            connection.execute(
                f"ALTER TABLE cloud_bootstrap_sessions ADD COLUMN {column} "
                "INTEGER NOT NULL DEFAULT 0 CHECK ("
                f"{column} IN (0, 1))"
            )
            actions.append(f"added: cloud_bootstrap_sessions.{column}")
    return actions
