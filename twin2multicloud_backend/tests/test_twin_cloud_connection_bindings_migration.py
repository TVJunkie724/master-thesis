import sqlite3

from migrations.add_twin_cloud_connection_bindings import migrate


def test_twin_cloud_connection_bindings_migration_is_idempotent(tmp_path, monkeypatch):
    db_path = tmp_path / "management.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")

    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE twin_configurations (id VARCHAR PRIMARY KEY)")
    conn.commit()
    conn.close()

    migrate()
    migrate()

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(twin_configurations)")
    columns = {row[1] for row in cursor.fetchall()}
    cursor.execute("PRAGMA index_list(twin_configurations)")
    indexes = {row[1] for row in cursor.fetchall()}
    conn.close()

    assert {
        "aws_cloud_connection_id",
        "azure_cloud_connection_id",
        "gcp_cloud_connection_id",
    }.issubset(columns)
    assert "ix_twin_configurations_aws_cloud_connection_id" in indexes
