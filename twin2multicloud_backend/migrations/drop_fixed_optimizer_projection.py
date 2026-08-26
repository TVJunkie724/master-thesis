"""Remove the obsolete Five-layer provider projection from Management.

Selected, digest-verified Six-layer architecture documents are the sole
deployment provider source after this migration. The calculation-run JSON and
resolved architecture records remain intact.
"""

from __future__ import annotations

import sqlite3

from migrations.ensure_current_schema_columns import resolve_sqlite_path


OBSOLETE_COLUMNS = (
    "cheapest_l1",
    "cheapest_l2",
    "cheapest_l3_hot",
    "cheapest_l3_cool",
    "cheapest_l3_archive",
    "cheapest_l4",
    "cheapest_l5",
)


def migrate(database_url: str | None = None) -> list[str]:
    """Drop fixed-path columns when upgrading an existing SQLite database."""

    database_path = resolve_sqlite_path(database_url)
    with sqlite3.connect(database_path) as connection:
        if not _table_exists(connection, "optimizer_configurations"):
            return ["skip missing table: optimizer_configurations"]
        existing = _columns(connection, "optimizer_configurations")
        actions: list[str] = []
        for column in OBSOLETE_COLUMNS:
            if column not in existing:
                actions.append(f"absent: optimizer_configurations.{column}")
                continue
            connection.execute(
                f'ALTER TABLE optimizer_configurations DROP COLUMN "{column}"'
            )
            actions.append(f"dropped: optimizer_configurations.{column}")
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
