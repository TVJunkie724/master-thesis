"""Migration coverage for persisted telemetry verification evidence."""

import sqlite3

from migrations.add_telemetry_verifications import migrate


def test_telemetry_verification_migration_is_idempotent(tmp_path):
    database_path = tmp_path / "management.db"
    with sqlite3.connect(database_path) as connection:
        connection.executescript(
            """
            CREATE TABLE digital_twins (id VARCHAR PRIMARY KEY);
            CREATE TABLE deployments (id VARCHAR PRIMARY KEY);
            """
        )

    database_url = f"sqlite:///{database_path}"
    migrate(database_url)
    migrate(database_url)

    with sqlite3.connect(database_path) as connection:
        columns = {
            row[1]
            for row in connection.execute(
                "PRAGMA table_info(telemetry_verifications)"
            ).fetchall()
        }
        indexes = {
            row[1]
            for row in connection.execute(
                "PRAGMA index_list(telemetry_verifications)"
            ).fetchall()
        }

    assert {
        "id",
        "twin_id",
        "deployment_id",
        "session_id",
        "device_id",
        "status",
        "trace_id",
        "result",
        "error_code",
        "error_message",
        "requested_at",
        "completed_at",
    } <= columns
    assert "ix_telemetry_verifications_twin_requested" in indexes
    assert "ix_telemetry_verifications_twin_status" in indexes
