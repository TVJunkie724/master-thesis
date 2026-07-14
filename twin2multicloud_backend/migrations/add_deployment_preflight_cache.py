"""Create the secret-free twin deployment preflight cache table.

Usage:
    python -m migrations.add_deployment_preflight_cache
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path


def resolve_sqlite_path(database_url: str | None = None) -> Path:
    raw = database_url or os.environ.get("DATABASE_URL", "sqlite:///./management.db")
    if raw.startswith("sqlite:///"):
        raw = raw.removeprefix("sqlite:///")
    if raw.startswith("sqlite://"):
        raise ValueError("Only file-backed sqlite:/// URLs are supported by this migration")
    return Path(raw)


def migrate(database_url: str | None = None) -> list[str]:
    db_path = resolve_sqlite_path(database_url)
    connection = sqlite3.connect(db_path)
    try:
        actions: list[str] = []
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS deployment_preflight_cache (
                id VARCHAR NOT NULL PRIMARY KEY,
                twin_id VARCHAR NOT NULL,
                provider VARCHAR NOT NULL,
                cloud_connection_id VARCHAR NOT NULL,
                connection_payload_fingerprint VARCHAR NOT NULL,
                supplied_permission_set_version VARCHAR,
                expected_permission_set_version VARCHAR NOT NULL,
                ready BOOLEAN NOT NULL DEFAULT 0,
                summary VARCHAR NOT NULL,
                checks_json TEXT NOT NULL DEFAULT '[]',
                checked_at DATETIME NOT NULL,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                CONSTRAINT uq_deployment_preflight_cache_twin_provider
                    UNIQUE (twin_id, provider),
                FOREIGN KEY(twin_id) REFERENCES digital_twins (id) ON DELETE CASCADE
            )
            """
        )
        actions.append("ensured: deployment_preflight_cache")
        for name, column in (
            ("ix_deployment_preflight_cache_twin_id", "twin_id"),
            ("ix_deployment_preflight_cache_provider", "provider"),
            ("ix_deployment_preflight_cache_connection_id", "cloud_connection_id"),
        ):
            connection.execute(
                f"CREATE INDEX IF NOT EXISTS {name} "
                f"ON deployment_preflight_cache ({column})"
            )
            actions.append(f"ensured index: {name}")
        connection.commit()
        return actions
    finally:
        connection.close()


if __name__ == "__main__":
    for action in migrate():
        print(action)
