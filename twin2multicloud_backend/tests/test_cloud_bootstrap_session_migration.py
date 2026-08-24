from __future__ import annotations

import sqlite3

from migrations.add_cloud_bootstrap_sessions import migrate
from migrations.add_cloud_bootstrap_setup_gate import migrate as migrate_setup_gate


def _baseline(path) -> None:
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            PRAGMA foreign_keys=ON;
            CREATE TABLE users (id VARCHAR PRIMARY KEY);
            CREATE TABLE digital_twins (
                id VARCHAR PRIMARY KEY,
                user_id VARCHAR NOT NULL REFERENCES users(id)
            );
            CREATE TABLE cloud_connections (
                id VARCHAR PRIMARY KEY,
                user_id VARCHAR NOT NULL REFERENCES users(id)
            );
            INSERT INTO users(id) VALUES ('owner');
            """
        )


def test_cloud_bootstrap_session_migration_is_idempotent_and_secret_free(tmp_path):
    path = tmp_path / "bootstrap.db"
    _baseline(path)
    url = f"sqlite:///{path}"

    assert migrate(url) == [
        "ensured: cloud_bootstrap_sessions",
        "ensured: cloud bootstrap indexes",
    ]
    assert migrate(url) == [
        "ensured: cloud_bootstrap_sessions",
        "ensured: cloud bootstrap indexes",
    ]

    with sqlite3.connect(path) as connection:
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(cloud_bootstrap_sessions)")
        }
        indexes = {
            row[1] for row in connection.execute("PRAGMA index_list(cloud_bootstrap_sessions)")
        }

    assert {
        "target_json",
        "guide_digest",
        "credential_origin",
        "disposal_status",
        "safe_credential_identifier",
        "connection_id",
    }.issubset(columns)
    assert not {
        "secret_access_key",
        "session_token",
        "client_secret",
        "service_account_json",
        "private_key",
        "credential_payload",
    }.intersection(columns)
    assert "uq_cloud_bootstrap_active_scope" in indexes
    assert "ix_cloud_bootstrap_owner_provider" in indexes


def test_setup_gate_migration_adds_only_secret_free_lifecycle_fields(tmp_path):
    path = tmp_path / "bootstrap-setup-gate.db"
    _baseline(path)
    url = f"sqlite:///{path}"
    migrate(url)

    assert migrate_setup_gate(url) == [
        "added: cloud_bootstrap_sessions.execution_kind",
        "added: cloud_bootstrap_sessions.provider_cleanup_receipt_json",
    ]
    assert migrate_setup_gate(url) == []

    with sqlite3.connect(path) as connection:
        columns = {
            row[1]: row
            for row in connection.execute(
                "PRAGMA table_info(cloud_bootstrap_sessions)"
            )
        }

    assert columns["execution_kind"][4] == "'persistent_connection'"
    assert columns["provider_cleanup_receipt_json"][2] == "TEXT"
