"""Schema migration coverage for the deployment preflight cache."""

import sqlite3

import pytest

from migrations.add_deployment_preflight_cache import migrate


def test_deployment_preflight_cache_migration_is_idempotent_and_unique(tmp_path):
    db_path = tmp_path / "management.db"
    database_url = f"sqlite:///{db_path}"

    migrate(database_url)
    migrate(database_url)

    connection = sqlite3.connect(db_path)
    try:
        columns = {
            row[1]
            for row in connection.execute(
                "PRAGMA table_info(deployment_preflight_cache)"
            ).fetchall()
        }
        indexes = {
            row[1]
            for row in connection.execute(
                "PRAGMA index_list(deployment_preflight_cache)"
            ).fetchall()
        }
        assert {
            "id",
            "twin_id",
            "provider",
            "cloud_connection_id",
            "connection_payload_fingerprint",
            "expected_permission_set_version",
            "ready",
            "checks_json",
            "checked_at",
        }.issubset(columns)
        assert {
            "ix_deployment_preflight_cache_twin_id",
            "ix_deployment_preflight_cache_provider",
            "ix_deployment_preflight_cache_connection_id",
        }.issubset(indexes)

        values = (
            "cache-1",
            "twin-1",
            "aws",
            "connection-1",
            "fingerprint",
            "thesis-demo-v1",
            "thesis-demo-v1",
            1,
            "Ready",
            "[]",
            "2026-07-14 09:00:00",
            "2026-07-14 09:00:00",
            "2026-07-14 09:00:00",
        )
        connection.execute(
            """
            INSERT INTO deployment_preflight_cache (
                id, twin_id, provider, cloud_connection_id,
                connection_payload_fingerprint,
                supplied_permission_set_version,
                expected_permission_set_version, ready, summary, checks_json,
                checked_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            values,
        )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO deployment_preflight_cache (
                    id, twin_id, provider, cloud_connection_id,
                    connection_payload_fingerprint,
                    supplied_permission_set_version,
                    expected_permission_set_version, ready, summary, checks_json,
                    checked_at, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("cache-2", *values[1:]),
            )
    finally:
        connection.close()
