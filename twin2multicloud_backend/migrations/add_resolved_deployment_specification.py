"""Add immutable resolved deployment specifications to optimizer runs."""

from __future__ import annotations

import os
import sqlite3


TABLE = "cost_calculation_runs"
IMMUTABILITY_TRIGGER = "trg_cost_runs_deployment_specification_immutable"
STATUS_INSERT_TRIGGER = "trg_cost_runs_deployment_compatibility_status_insert"
SELECTION_INDEX = "ix_cost_runs_one_selected_per_twin"
COLUMNS = (
    (
        "deployment_specification_json",
        "ALTER TABLE cost_calculation_runs "
        "ADD COLUMN deployment_specification_json TEXT",
    ),
    (
        "deployment_specification_digest",
        "ALTER TABLE cost_calculation_runs "
        "ADD COLUMN deployment_specification_digest VARCHAR(71)",
    ),
    (
        "deployment_specification_version",
        "ALTER TABLE cost_calculation_runs "
        "ADD COLUMN deployment_specification_version VARCHAR(64)",
    ),
    (
        "deployment_compatibility_status",
        "ALTER TABLE cost_calculation_runs "
        "ADD COLUMN deployment_compatibility_status VARCHAR(32) "
        "NOT NULL DEFAULT 'legacy_not_deployable'",
    ),
)


def migrate(database_url: str | None = None) -> list[str]:
    """Add columns, legacy state, digest index, and immutability trigger."""

    db_path = _resolve_db_path(database_url)
    actions: list[str] = []
    with sqlite3.connect(db_path) as connection:
        if not _table_exists(connection, TABLE):
            return [f"skip missing table: {TABLE}"]

        existing = _columns(connection, TABLE)
        for column_name, statement in COLUMNS:
            if column_name in existing:
                actions.append(f"exists: {TABLE}.{column_name}")
                continue
            connection.execute(statement)
            actions.append(f"added: {TABLE}.{column_name}")

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
                ix_cost_runs_deployment_specification_digest
            ON cost_calculation_runs (deployment_specification_digest)
            """
        )
        normalized_selections = _normalize_duplicate_selections(connection)
        connection.execute(
            f"""
            CREATE UNIQUE INDEX IF NOT EXISTS {SELECTION_INDEX}
            ON cost_calculation_runs (twin_id, user_id)
            WHERE selected_for_deployment_at IS NOT NULL
            """
        )
        connection.execute(
            f"""
            CREATE TRIGGER IF NOT EXISTS {IMMUTABILITY_TRIGGER}
            BEFORE UPDATE OF
                deployment_specification_json,
                deployment_specification_digest,
                deployment_specification_version,
                deployment_compatibility_status
            ON cost_calculation_runs
            FOR EACH ROW
            WHEN
                OLD.deployment_specification_json
                    IS NOT NEW.deployment_specification_json
                OR OLD.deployment_specification_digest
                    IS NOT NEW.deployment_specification_digest
                OR OLD.deployment_specification_version
                    IS NOT NEW.deployment_specification_version
                OR OLD.deployment_compatibility_status
                    IS NOT NEW.deployment_compatibility_status
            BEGIN
                SELECT RAISE(
                    ABORT,
                    'resolved deployment specification is immutable'
                );
            END
            """
        )
        connection.execute(
            f"""
            CREATE TRIGGER IF NOT EXISTS {STATUS_INSERT_TRIGGER}
            BEFORE INSERT ON cost_calculation_runs
            FOR EACH ROW
            WHEN NEW.deployment_compatibility_status NOT IN (
                'ready',
                'legacy_not_deployable'
            )
            BEGIN
                SELECT RAISE(
                    ABORT,
                    'invalid deployment compatibility status'
                );
            END
            """
        )
        actions.append(
            "ensured: deployment specification indexes and triggers"
        )
        if normalized_selections:
            actions.append(
                f"normalized: duplicate selections={normalized_selections}"
            )
    return actions


def _resolve_db_path(database_url: str | None) -> str:
    resolved = database_url or os.environ.get(
        "DATABASE_URL",
        "sqlite:///./management.db",
    )
    if not resolved.startswith("sqlite:///"):
        raise ValueError("Resolved deployment migration requires SQLite.")
    return resolved.removeprefix("sqlite:///")


def _table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    return (
        connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table_name,),
        ).fetchone()
        is not None
    )


def _columns(connection: sqlite3.Connection, table_name: str) -> set[str]:
    return {
        str(row[1])
        for row in connection.execute(f"PRAGMA table_info({table_name})")
    }


def _normalize_duplicate_selections(connection: sqlite3.Connection) -> int:
    duplicate_groups = connection.execute(
        """
        SELECT twin_id, user_id
        FROM cost_calculation_runs
        WHERE selected_for_deployment_at IS NOT NULL
        GROUP BY twin_id, user_id
        HAVING COUNT(*) > 1
        """
    ).fetchall()
    normalized = 0
    for twin_id, user_id in duplicate_groups:
        selected = connection.execute(
            """
            SELECT id
            FROM cost_calculation_runs
            WHERE twin_id = ?
              AND user_id = ?
              AND selected_for_deployment_at IS NOT NULL
            ORDER BY selected_for_deployment_at DESC, id DESC
            """,
            (twin_id, user_id),
        ).fetchall()
        stale_ids = [row[0] for row in selected[1:]]
        for stale_id in stale_ids:
            connection.execute(
                """
                UPDATE cost_calculation_runs
                SET selected_for_deployment_at = NULL
                WHERE id = ?
                """,
                (stale_id,),
            )
        normalized += len(stale_ids)
    return normalized


if __name__ == "__main__":
    migrate()
