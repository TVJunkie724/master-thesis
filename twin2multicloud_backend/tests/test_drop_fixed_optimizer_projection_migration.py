"""One-way migration tests for the removed fixed provider projection."""

from __future__ import annotations

import sqlite3

from migrations.drop_fixed_optimizer_projection import OBSOLETE_COLUMNS, migrate


def test_migration_drops_only_fixed_projection_columns(tmp_path):
    database = tmp_path / "management.db"
    with sqlite3.connect(database) as connection:
        projection = ", ".join(f"{column} VARCHAR" for column in OBSOLETE_COLUMNS)
        connection.execute(
            "CREATE TABLE optimizer_configurations "
            f"(id VARCHAR PRIMARY KEY, params TEXT, result_json TEXT, {projection})"
        )
        connection.execute(
            "INSERT INTO optimizer_configurations (id, params) VALUES ('one', '{}')"
        )

    actions = migrate(f"sqlite:///{database}")

    with sqlite3.connect(database) as connection:
        columns = {
            row[1]
            for row in connection.execute(
                "PRAGMA table_info(optimizer_configurations)"
            )
        }
        row = connection.execute(
            "SELECT id, params FROM optimizer_configurations"
        ).fetchone()
    assert not columns.intersection(OBSOLETE_COLUMNS)
    assert {"id", "params", "result_json"}.issubset(columns)
    assert row == ("one", "{}")
    assert len([action for action in actions if action.startswith("dropped:")]) == 7


def test_migration_is_idempotent(tmp_path):
    database = tmp_path / "management.db"
    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE TABLE optimizer_configurations (id VARCHAR PRIMARY KEY)"
        )

    assert all(
        action.startswith("absent:")
        for action in migrate(f"sqlite:///{database}")
    )
