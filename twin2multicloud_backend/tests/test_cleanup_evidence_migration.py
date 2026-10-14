"""Migration coverage for persisted cleanup evidence."""

import sqlite3

from migrations.add_cleanup_evidence import migrate


def test_cleanup_evidence_migration_is_idempotent(tmp_path):
    database_path = tmp_path / "management.db"
    with sqlite3.connect(database_path) as connection:
        connection.execute("CREATE TABLE deployments (id VARCHAR PRIMARY KEY)")

    database_url = f"sqlite:///{database_path}"
    first = migrate(database_url)
    second = migrate(database_url)

    with sqlite3.connect(database_path) as connection:
        columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(deployments)").fetchall()
        }

    assert first == ["added: deployments.cleanup_evidence"]
    assert second == ["present: deployments.cleanup_evidence"]
    assert "cleanup_evidence" in columns
