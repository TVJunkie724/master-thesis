import sqlite3

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
        "encrypted_payload",
        "validation_status",
    }.issubset(columns)
    assert "ix_cloud_connections_user_id" in indexes
