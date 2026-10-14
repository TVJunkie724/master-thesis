"""Create bounded telemetry verification evidence storage."""

from __future__ import annotations

import sqlite3

from migrations.ensure_current_schema_columns import resolve_sqlite_path


def migrate(database_url: str | None = None) -> list[str]:
    """Create the telemetry verification table and its read indexes."""

    database_path = resolve_sqlite_path(database_url)
    actions: list[str] = []
    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS telemetry_verifications (
                id VARCHAR PRIMARY KEY,
                twin_id VARCHAR NOT NULL,
                deployment_id VARCHAR,
                session_id VARCHAR NOT NULL UNIQUE,
                device_id VARCHAR(128) NOT NULL,
                status VARCHAR(16) NOT NULL DEFAULT 'running',
                trace_id VARCHAR(15),
                result JSON,
                error_code VARCHAR(64),
                error_message TEXT,
                requested_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                completed_at DATETIME,
                FOREIGN KEY(twin_id) REFERENCES digital_twins(id) ON DELETE CASCADE,
                FOREIGN KEY(deployment_id) REFERENCES deployments(id) ON DELETE SET NULL
            )
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS ix_telemetry_verifications_twin_requested
            ON telemetry_verifications (twin_id, requested_at)
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS ix_telemetry_verifications_twin_status
            ON telemetry_verifications (twin_id, status)
            """
        )
        connection.commit()
    actions.extend(
        [
            "present: telemetry_verifications",
            "present: ix_telemetry_verifications_twin_requested",
            "present: ix_telemetry_verifications_twin_status",
        ]
    )
    return actions
