"""Migration 026 Layer Access regression test."""

from __future__ import annotations

import sqlite3

from migrations.add_deployment_access import migrate


def test_deployment_access_migration_is_idempotent_and_secret_free(
    tmp_path,
    monkeypatch,
):
    database_path = tmp_path / "management.db"
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            CREATE TABLE deployments (
                id VARCHAR PRIMARY KEY,
                twin_id VARCHAR NOT NULL,
                session_id VARCHAR NOT NULL
            )
            """
        )
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path}")

    migrate()
    migrate()

    with sqlite3.connect(database_path) as connection:
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(deployments)")
        }
    assert {
        "deployment_access_evidence",
        "layer_access_credential_rotated_at",
        "layer_access_credential_fingerprint",
    } <= columns
    assert not {"password", "admin_password", "viewer_password"}.intersection(columns)
