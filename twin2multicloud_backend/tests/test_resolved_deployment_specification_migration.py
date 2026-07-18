import sqlite3

import pytest

from migrations.add_resolved_deployment_specification import (
    IMMUTABILITY_TRIGGER,
    SELECTION_INDEX,
    STATUS_INSERT_TRIGGER,
    migrate,
)


def _create_legacy_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE cost_calculation_runs (
            id VARCHAR PRIMARY KEY,
            twin_id VARCHAR NOT NULL,
            user_id VARCHAR NOT NULL,
            params_json TEXT NOT NULL,
            selected_for_deployment_at DATETIME
        )
        """
    )


def test_migration_is_idempotent_and_marks_existing_runs_as_legacy(tmp_path):
    db_path = tmp_path / "management.db"
    with sqlite3.connect(db_path) as connection:
        _create_legacy_table(connection)
        connection.execute(
            """
            INSERT INTO cost_calculation_runs (
                id,
                twin_id,
                user_id,
                params_json
            ) VALUES (?, ?, ?, ?)
            """,
            ("legacy-run", "twin-1", "user-1", "{}"),
        )

    first = migrate(f"sqlite:///{db_path}")
    second = migrate(f"sqlite:///{db_path}")

    with sqlite3.connect(db_path) as connection:
        columns = {
            row[1]
            for row in connection.execute(
                "PRAGMA table_info(cost_calculation_runs)"
            )
        }
        indexes = {
            row[1]
            for row in connection.execute(
                "PRAGMA index_list(cost_calculation_runs)"
            )
        }
        triggers = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'trigger'"
            )
        }
        status = connection.execute(
            """
            SELECT deployment_compatibility_status
            FROM cost_calculation_runs
            WHERE id = 'legacy-run'
            """
        ).fetchone()[0]

    assert {
        "deployment_specification_json",
        "deployment_specification_digest",
        "deployment_specification_version",
        "deployment_compatibility_status",
    }.issubset(columns)
    assert {
        "ix_cost_runs_deployment_specification_digest",
        SELECTION_INDEX,
    }.issubset(indexes)
    assert {IMMUTABILITY_TRIGGER, STATUS_INSERT_TRIGGER}.issubset(triggers)
    assert status == "legacy_not_deployable"
    assert any(action.startswith("added:") for action in first)
    assert all(
        action.startswith(("exists:", "ensured:"))
        for action in second
    )


def test_migration_trigger_prevents_specification_mutation(tmp_path):
    db_path = tmp_path / "management.db"
    with sqlite3.connect(db_path) as connection:
        _create_legacy_table(connection)
    migrate(f"sqlite:///{db_path}")

    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            INSERT INTO cost_calculation_runs (
                id,
                twin_id,
                user_id,
                params_json,
                deployment_specification_json,
                deployment_specification_digest,
                deployment_specification_version,
                deployment_compatibility_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "ready-run",
                "twin-1",
                "user-1",
                "{}",
                '{"schema_version":"resolved-deployment-specification.v1"}',
                "sha256:" + ("a" * 64),
                "resolved-deployment-specification.v1",
                "ready",
            ),
        )
        with pytest.raises(
            sqlite3.IntegrityError,
            match="resolved deployment specification is immutable",
        ):
            connection.execute(
                """
                UPDATE cost_calculation_runs
                SET deployment_specification_digest = ?
                WHERE id = 'ready-run'
                """,
                ("sha256:" + ("b" * 64),),
            )


def test_migration_normalizes_and_prevents_duplicate_selections(tmp_path):
    db_path = tmp_path / "management.db"
    with sqlite3.connect(db_path) as connection:
        _create_legacy_table(connection)
        connection.executemany(
            """
            INSERT INTO cost_calculation_runs (
                id,
                twin_id,
                user_id,
                params_json,
                selected_for_deployment_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                ("older", "twin-1", "user-1", "{}", "2026-07-17 10:00:00"),
                ("newer", "twin-1", "user-1", "{}", "2026-07-17 11:00:00"),
            ),
        )

    actions = migrate(f"sqlite:///{db_path}")

    with sqlite3.connect(db_path) as connection:
        selected = connection.execute(
            """
            SELECT id
            FROM cost_calculation_runs
            WHERE selected_for_deployment_at IS NOT NULL
            """
        ).fetchall()
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                UPDATE cost_calculation_runs
                SET selected_for_deployment_at = '2026-07-17 12:00:00'
                WHERE id = 'older'
                """
            )

    assert selected == [("newer",)]
    assert "normalized: duplicate selections=1" in actions


def test_migration_rejects_unknown_compatibility_status_on_insert(tmp_path):
    db_path = tmp_path / "management.db"
    with sqlite3.connect(db_path) as connection:
        _create_legacy_table(connection)
    migrate(f"sqlite:///{db_path}")

    with sqlite3.connect(db_path) as connection:
        with pytest.raises(
            sqlite3.IntegrityError,
            match="invalid deployment compatibility status",
        ):
            connection.execute(
                """
                INSERT INTO cost_calculation_runs (
                    id,
                    twin_id,
                    user_id,
                    params_json,
                    deployment_compatibility_status
                ) VALUES (?, ?, ?, ?, ?)
                """,
                ("invalid", "twin-1", "user-1", "{}", "unknown"),
            )


def test_migration_skips_missing_run_table(tmp_path):
    db_path = tmp_path / "management.db"

    assert migrate(f"sqlite:///{db_path}") == [
        "skip missing table: cost_calculation_runs"
    ]
