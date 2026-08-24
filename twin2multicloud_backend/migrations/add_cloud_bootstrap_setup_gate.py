"""Add the secret-free setup-only bootstrap lifecycle fields."""

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
        if "execution_kind" not in columns:
            connection.execute(
                "ALTER TABLE cloud_bootstrap_sessions "
                "ADD COLUMN execution_kind VARCHAR(32) NOT NULL "
                "DEFAULT 'persistent_connection' CHECK (execution_kind IN "
                "('persistent_connection', 'setup_only_validation'))"
            )
            actions.append("added: cloud_bootstrap_sessions.execution_kind")
        if "provider_cleanup_receipt_json" not in columns:
            connection.execute(
                "ALTER TABLE cloud_bootstrap_sessions "
                "ADD COLUMN provider_cleanup_receipt_json TEXT"
            )
            actions.append(
                "added: cloud_bootstrap_sessions.provider_cleanup_receipt_json"
            )
    return actions
