import sqlite3

import pytest

from migrations.add_cloud_connection_purpose import migrate


def _legacy_database(path):
    connection = sqlite3.connect(path)
    connection.execute(
        """
        CREATE TABLE cloud_connections (
            id VARCHAR PRIMARY KEY,
            user_id VARCHAR NOT NULL,
            provider VARCHAR NOT NULL,
            encrypted_payload TEXT NOT NULL
        )
        """
    )
    connection.execute(
        "INSERT INTO cloud_connections VALUES (?, ?, ?, ?)",
        ("connection-1", "user-1", "aws", "encrypted-secret-value"),
    )
    connection.commit()
    connection.close()


def test_migration_backfills_legacy_rows_without_touching_payload(tmp_path):
    database_path = tmp_path / "legacy.db"
    _legacy_database(database_path)

    actions = migrate(str(database_path))

    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    row = connection.execute("SELECT * FROM cloud_connections").fetchone()
    indexes = {item[1] for item in connection.execute("PRAGMA index_list(cloud_connections)")}
    connection.close()

    assert "added: cloud_connections.purpose" in actions
    assert row["purpose"] == "deployment"
    assert row["scope"] == "user"
    assert row["is_default_for_pricing"] == 0
    assert row["last_used_at"] is None
    assert row["encrypted_payload"] == "encrypted-secret-value"
    assert "uq_cloud_connections_pricing_default" in indexes


def test_migration_is_idempotent(tmp_path):
    database_path = tmp_path / "legacy.db"
    _legacy_database(database_path)

    migrate(str(database_path))
    actions = migrate(str(database_path))

    assert "exists: cloud_connections.purpose" in actions


def test_migration_skips_missing_table(tmp_path):
    database_path = tmp_path / "empty.db"

    assert migrate(str(database_path)) == ["skip missing table: cloud_connections"]


def test_partial_unique_index_allows_one_default_per_user_and_provider(tmp_path):
    database_path = tmp_path / "legacy.db"
    _legacy_database(database_path)
    migrate(str(database_path))
    connection = sqlite3.connect(database_path)
    connection.execute(
        "UPDATE cloud_connections SET purpose = 'pricing', is_default_for_pricing = 1"
    )

    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "INSERT INTO cloud_connections "
            "(id, user_id, provider, encrypted_payload, purpose, scope, is_default_for_pricing) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("connection-2", "user-1", "aws", "opaque", "pricing", "user", 1),
        )

    connection.execute(
        "INSERT INTO cloud_connections "
        "(id, user_id, provider, encrypted_payload, purpose, scope, is_default_for_pricing) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("connection-3", "user-2", "aws", "opaque", "pricing", "user", 1),
    )
    connection.execute(
        "INSERT INTO cloud_connections "
        "(id, user_id, provider, encrypted_payload, purpose, scope, is_default_for_pricing) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("connection-4", "user-1", "gcp", "opaque", "pricing", "user", 1),
    )
    connection.commit()
    connection.close()
