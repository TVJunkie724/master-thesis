import sqlite3

from migrations.add_deployment_operation_state_columns import migrate


def test_deployment_operation_state_migration_is_idempotent(tmp_path, monkeypatch):
    db_path = tmp_path / "management.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")

    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE deployments (id VARCHAR PRIMARY KEY)")
    conn.commit()
    conn.close()

    migrate()
    migrate()

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(deployments)")
    columns = {row[1] for row in cursor.fetchall()}
    cursor.execute("PRAGMA index_list(deployments)")
    indexes = {row[1] for row in cursor.fetchall()}
    conn.close()

    assert {"operation_id", "error_code"}.issubset(columns)
    assert "ix_deployments_operation_id" in indexes
