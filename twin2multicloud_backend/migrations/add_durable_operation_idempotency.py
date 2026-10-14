"""Add durable command idempotency to deployment operations."""

from __future__ import annotations

import sqlite3

from migrations.ensure_current_schema_columns import resolve_sqlite_path


def migrate(database_url: str | None = None) -> list[str]:
    """Add the nullable key and its Twin/operation-scoped unique index."""

    database_path = resolve_sqlite_path(database_url)
    actions: list[str] = []
    with sqlite3.connect(database_path) as connection:
        columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(deployments)").fetchall()
        }
        if "idempotency_key" not in columns:
            connection.execute(
                "ALTER TABLE deployments ADD COLUMN idempotency_key VARCHAR(128)"
            )
            actions.append("added: deployments.idempotency_key")
        else:
            actions.append("present: deployments.idempotency_key")
        connection.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS
                ux_deployments_twin_operation_idempotency
            ON deployments (twin_id, operation_type, idempotency_key)
            """
        )
        connection.commit()
    actions.append("present: ux_deployments_twin_operation_idempotency")
    return actions
