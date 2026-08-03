"""Migration 023: persist bounded immutable deployment graph evidence."""

from __future__ import annotations

import os
import sqlite3


def migrate() -> None:
    database_url = os.environ.get("DATABASE_URL", "sqlite:///./management.db")
    database_path = database_url.removeprefix("sqlite:///")
    connection = sqlite3.connect(database_path)
    try:
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(deployments)")
        }
        additions = (
            ("architecture_digest", "VARCHAR(71)"),
            ("graph_digest", "VARCHAR(71)"),
            ("profile_id", "VARCHAR(128)"),
            ("profile_version", "VARCHAR(32)"),
            ("catalog_id", "VARCHAR(128)"),
            ("catalog_version", "VARCHAR(32)"),
            ("completed_stage", "VARCHAR(32)"),
            ("graph_validation", "JSON"),
        )
        for name, sql_type in additions:
            if name not in columns:
                connection.execute(
                    f"ALTER TABLE deployments ADD COLUMN {name} {sql_type}"
                )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS ix_deployments_graph_digest "
            "ON deployments (graph_digest)"
        )
        connection.commit()
    finally:
        connection.close()


if __name__ == "__main__":
    migrate()
