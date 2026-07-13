"""Add purpose-aware CloudConnection metadata to existing SQLite databases."""

from __future__ import annotations

import sqlite3

from migrations.ensure_current_schema_columns import resolve_sqlite_path


TABLE_NAME = "cloud_connections"
COLUMNS: tuple[tuple[str, str], ...] = (
    ("purpose", "VARCHAR NOT NULL DEFAULT 'deployment'"),
    ("scope", "VARCHAR NOT NULL DEFAULT 'user'"),
    ("is_default_for_pricing", "BOOLEAN NOT NULL DEFAULT 0"),
    ("last_used_at", "DATETIME"),
)


def migrate(database_url: str | None = None) -> list[str]:
    """Apply the additive migration without reading or rewriting secret payloads."""
    connection = sqlite3.connect(resolve_sqlite_path(database_url))
    try:
        if not _table_exists(connection):
            return [f"skip missing table: {TABLE_NAME}"]

        actions: list[str] = []
        existing = _existing_columns(connection)
        for name, sql_type in COLUMNS:
            if name in existing:
                actions.append(f"exists: {TABLE_NAME}.{name}")
                continue
            connection.execute(f"ALTER TABLE {TABLE_NAME} ADD COLUMN {name} {sql_type}")
            actions.append(f"added: {TABLE_NAME}.{name}")

        connection.execute(
            "CREATE INDEX IF NOT EXISTS ix_cloud_connections_purpose "
            "ON cloud_connections (purpose)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS ix_cloud_connections_scope "
            "ON cloud_connections (scope)"
        )
        connection.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_cloud_connections_pricing_default "
            "ON cloud_connections (user_id, provider) "
            "WHERE purpose = 'pricing' AND is_default_for_pricing = 1"
        )
        connection.commit()
        actions.append("ensured: cloud connection purpose indexes")
        return actions
    finally:
        connection.close()


def _table_exists(connection: sqlite3.Connection) -> bool:
    return connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (TABLE_NAME,),
    ).fetchone() is not None


def _existing_columns(connection: sqlite3.Connection) -> set[str]:
    return {row[1] for row in connection.execute(f"PRAGMA table_info({TABLE_NAME})")}


if __name__ == "__main__":
    for action in migrate():
        print(action)
