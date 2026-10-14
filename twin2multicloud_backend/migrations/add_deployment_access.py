"""Migration 026: persist secret-free Layer Access evidence and rotation metadata."""

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
            ("deployment_access_evidence", "JSON"),
            ("layer_access_credential_rotated_at", "DATETIME"),
            ("layer_access_credential_fingerprint", "VARCHAR(64)"),
        )
        for name, sql_type in additions:
            if name not in columns:
                connection.execute(
                    f"ALTER TABLE deployments ADD COLUMN {name} {sql_type}"
                )
        connection.commit()
    finally:
        connection.close()


if __name__ == "__main__":
    migrate()
