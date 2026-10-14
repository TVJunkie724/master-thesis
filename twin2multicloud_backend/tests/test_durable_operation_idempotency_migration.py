"""Migration coverage for durable deployment command keys."""

import sqlite3

from migrations.add_durable_operation_idempotency import migrate


def test_durable_operation_idempotency_migration_is_idempotent(tmp_path):
    database_path = tmp_path / "management.db"
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            CREATE TABLE deployments (
                id VARCHAR PRIMARY KEY,
                twin_id VARCHAR NOT NULL,
                operation_type VARCHAR NOT NULL
            )
            """
        )

    database_url = f"sqlite:///{database_path}"
    migrate(database_url)
    migrate(database_url)

    with sqlite3.connect(database_path) as connection:
        columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(deployments)").fetchall()
        }
        indexes = {
            row[1]
            for row in connection.execute("PRAGMA index_list(deployments)").fetchall()
        }

    assert "idempotency_key" in columns
    assert "ux_deployments_twin_operation_idempotency" in indexes
