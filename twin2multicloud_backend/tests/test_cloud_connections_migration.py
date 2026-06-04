import sqlite3

from migrations.add_cloud_connection_permission_set_version import migrate as migrate_permission_set_version
from migrations.add_cloud_connections_table import migrate


def test_cloud_connections_migration_is_idempotent(tmp_path, monkeypatch):
    db_path = tmp_path / "management.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")

    migrate()
    migrate()

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(cloud_connections)")
    columns = {row[1] for row in cursor.fetchall()}
    cursor.execute("PRAGMA index_list(cloud_connections)")
    indexes = {row[1] for row in cursor.fetchall()}
    conn.close()

    assert {
        "id",
        "user_id",
        "provider",
        "display_name",
        "permission_set_version",
        "encrypted_payload",
        "validation_status",
    }.issubset(columns)
    assert "ix_cloud_connections_user_id" in indexes
    assert "ix_cloud_connections_permission_set_version" in indexes


def test_cloud_connections_migration_upgrades_existing_table_without_permission_set_version(
    tmp_path,
    monkeypatch,
):
    db_path = tmp_path / "management.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE cloud_connections (
            id VARCHAR PRIMARY KEY,
            user_id VARCHAR NOT NULL,
            provider VARCHAR NOT NULL,
            display_name VARCHAR NOT NULL,
            cloud_scope TEXT NOT NULL DEFAULT '{}',
            auth_type VARCHAR NOT NULL,
            encrypted_payload TEXT NOT NULL,
            payload_fingerprint VARCHAR NOT NULL,
            validation_status VARCHAR NOT NULL DEFAULT 'untested'
        )
        """
    )
    conn.commit()
    conn.close()

    migrate()

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(cloud_connections)")
    columns = {row[1] for row in cursor.fetchall()}
    cursor.execute("PRAGMA index_list(cloud_connections)")
    indexes = {row[1] for row in cursor.fetchall()}
    conn.close()

    assert "permission_set_version" in columns
    assert "ix_cloud_connections_permission_set_version" in indexes


def test_cloud_connection_permission_set_version_migration_is_idempotent(tmp_path, monkeypatch):
    db_path = tmp_path / "management.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")

    migrate()
    migrate_permission_set_version()
    migrate_permission_set_version()

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(cloud_connections)")
    columns = {row[1] for row in cursor.fetchall()}
    cursor.execute("PRAGMA index_list(cloud_connections)")
    indexes = {row[1] for row in cursor.fetchall()}
    conn.close()

    assert "permission_set_version" in columns
    assert "ix_cloud_connections_permission_set_version" in indexes
