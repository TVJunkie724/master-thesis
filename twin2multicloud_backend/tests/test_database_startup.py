"""Integration tests for deterministic Management API schema upgrades."""

from __future__ import annotations

import sqlite3

from sqlalchemy import create_engine

from migrations.runner import MIGRATIONS
from src.database_startup import initialize_database_schema
from src.models.database import Base


def test_database_startup_upgrades_legacy_tables_and_journals_once(tmp_path):
    database_path = tmp_path / "legacy.db"
    database_url = f"sqlite:///{database_path}"
    engine = create_engine(database_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    _remove_representative_additive_columns(database_path)

    first_run = initialize_database_schema(engine, database_url)
    second_run = initialize_database_schema(engine, database_url)

    assert first_run == [migration.migration_id for migration in MIGRATIONS]
    assert second_run == []
    with sqlite3.connect(database_path) as connection:
        applied = connection.execute(
            "SELECT migration_id FROM schema_migrations ORDER BY migration_id"
        ).fetchall()
        assert [row[0] for row in applied] == sorted(first_run)
        _assert_model_columns_exist(connection)


def test_database_startup_skips_sqlite_runner_for_other_databases(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(Base.metadata, "create_all", lambda *, bind: calls.append("create"))

    result = initialize_database_schema(object(), "postgresql://db/example")

    assert result == []
    assert calls == ["create"]


def _remove_representative_additive_columns(database_path) -> None:
    with sqlite3.connect(database_path) as connection:
        connection.executescript(
            """
            ALTER TABLE digital_twins DROP COLUMN last_error;
            ALTER TABLE deployer_configurations DROP COLUMN hierarchy_content;
            ALTER TABLE optimizer_configurations DROP COLUMN pricing_aws_snapshot;
            ALTER TABLE deployment_logs DROP COLUMN operation_type;
            """
        )


def _assert_model_columns_exist(connection) -> None:
    for table in Base.metadata.sorted_tables:
        actual = {
            row[1]
            for row in connection.execute(f"PRAGMA table_info({table.name})")
        }
        expected = {column.name for column in table.columns}
        assert expected <= actual, f"{table.name} is missing {sorted(expected - actual)}"
