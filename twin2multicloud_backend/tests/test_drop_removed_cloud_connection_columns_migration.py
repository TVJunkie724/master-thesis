"""Upgrade the actual retired credential schema, not only fresh databases."""

from __future__ import annotations

import sqlite3

import pytest
from sqlalchemy import text

from migrations.drop_removed_cloud_connection_columns import migrate
from src.models.cloud_connection import CloudConnection
from src.services.cloud_connection_service import CloudConnectionService


def _legacy_database(path):
    with sqlite3.connect(path) as connection:
        connection.executescript("""
            CREATE TABLE cloud_connections (
                id TEXT PRIMARY KEY, user_id TEXT NOT NULL,
                provider TEXT NOT NULL, purpose TEXT NOT NULL,
                encrypted_payload TEXT NOT NULL, payload_fingerprint TEXT NOT NULL,
                is_default_for_pricing BOOLEAN NOT NULL,
                permission_set_version TEXT
            );
            CREATE UNIQUE INDEX uq_cloud_connections_pricing_default
                ON cloud_connections(user_id, provider)
                WHERE purpose = 'pricing' AND is_default_for_pricing = 1;
            CREATE INDEX ix_cloud_connections_permission_set_version
                ON cloud_connections(permission_set_version);
            CREATE INDEX ix_cloud_connections_payload_fingerprint
                ON cloud_connections(payload_fingerprint);
            CREATE TABLE bindings (
                twin_id TEXT PRIMARY KEY,
                connection_id TEXT REFERENCES cloud_connections(id)
            );
            INSERT INTO cloud_connections VALUES (
                'connection-1', 'user-1', 'azure', 'deployment',
                'synthetic-opaque-ciphertext', 'synthetic-fingerprint', 0, 'retired'
            );
            INSERT INTO bindings VALUES ('twin-1', 'connection-1');
        """)


def test_upgrade_preserves_payload_bindings_and_active_index(tmp_path):
    database = tmp_path / "legacy.db"
    _legacy_database(database)
    url = f"sqlite:///{database}"
    assert len(migrate(url)) == 2
    assert all(action.startswith("absent:") for action in migrate(url))
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT * FROM cloud_connections").fetchone() == (
            "connection-1",
            "user-1",
            "azure",
            "deployment",
            "synthetic-opaque-ciphertext",
            "synthetic-fingerprint",
        )
        assert connection.execute("SELECT * FROM bindings").fetchone() == (
            "twin-1",
            "connection-1",
        )
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        indexes = {
            row[1] for row in connection.execute("PRAGMA index_list(cloud_connections)")
        }
        assert "ix_cloud_connections_payload_fingerprint" in indexes
        assert "uq_cloud_connections_pricing_default" not in indexes
        connection.execute("""
            INSERT INTO cloud_connections VALUES
                ('connection-2', 'user-1', 'azure', 'deployment', 'opaque-2', 'fp-2')
        """)


def test_upgrade_rolls_back_all_ddl_on_unexpected_dependency(tmp_path):
    database = tmp_path / "legacy.db"
    _legacy_database(database)
    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE INDEX unexpected ON cloud_connections(permission_set_version)"
        )
    with pytest.raises(sqlite3.OperationalError):
        migrate(f"sqlite:///{database}")
    with sqlite3.connect(database) as connection:
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(cloud_connections)")
        }
        assert {"is_default_for_pricing", "permission_set_version"} <= columns
        indexes = {
            row[1] for row in connection.execute("PRAGMA index_list(cloud_connections)")
        }
        assert "uq_cloud_connections_pricing_default" in indexes


def test_missing_table_is_safe(tmp_path):
    assert migrate(f"sqlite:///{tmp_path / 'empty.db'}") == [
        "skip missing table: cloud_connections"
    ]


def test_azure_import_fails_on_legacy_schema_then_passes_after_upgrade(
    authenticated_client,
    db_session,
):
    client, headers = authenticated_client
    db_session.execute(
        text(
            "ALTER TABLE cloud_connections ADD COLUMN is_default_for_pricing BOOLEAN NOT NULL"
        )
    )
    db_session.execute(
        text("ALTER TABLE cloud_connections ADD COLUMN permission_set_version TEXT")
    )
    db_session.commit()
    form = {
        "metadata": '{"provider":"azure","display_name":"Synthetic upgrade test",'
        '"region":"westeurope","target_scope_id":"synthetic-subscription"}',
    }
    files = {
        "file": (
            "azure.json",
            b'{"appId":"synthetic-client",'
            b'"password":"synthetic-secret","tenant":"synthetic-tenant"}',
            "application/json",
        )
    }
    assert (
        client.post(
            "/cloud-connections/import", data=form, files=files, headers=headers
        ).status_code
        == 409
    )
    migrate(str(db_session.get_bind().url))
    response = client.post(
        "/cloud-connections/import", data=form, files=files, headers=headers
    )
    assert response.status_code == 200
    assert response.json()["validation_status"] == "untested"
    assert "synthetic-secret" not in response.text
    stored = db_session.get(CloudConnection, response.json()["id"])
    assert "synthetic-secret" not in stored.encrypted_payload
    payload = CloudConnectionService(db_session).decrypt_payload(stored, stored.user_id)
    assert payload["azure_client_secret"] == "synthetic-secret"
