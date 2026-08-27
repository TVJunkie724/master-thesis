import sqlite3

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
    connection.close()

    assert "added: cloud_connections.purpose" in actions
    assert row["purpose"] == "deployment"
    assert row["scope"] == "user"
    assert row["last_used_at"] is None
    assert row["encrypted_payload"] == "encrypted-secret-value"


def test_migration_is_idempotent(tmp_path):
    database_path = tmp_path / "legacy.db"
    _legacy_database(database_path)

    migrate(str(database_path))
    actions = migrate(str(database_path))

    assert "exists: cloud_connections.purpose" in actions


def test_migration_skips_missing_table(tmp_path):
    database_path = tmp_path / "empty.db"

    assert migrate(str(database_path)) == ["skip missing table: cloud_connections"]
