"""One-way migration tests for the removed production-auth user fields."""

from __future__ import annotations

import sqlite3

from migrations.drop_removed_auth_columns import OBSOLETE_COLUMNS, migrate


def test_migration_preserves_active_user_fields_and_rows(tmp_path):
    database = tmp_path / "management.db"
    with sqlite3.connect(database) as connection:
        connection.execute(
            """
            CREATE TABLE users (
                id VARCHAR PRIMARY KEY,
                email VARCHAR NOT NULL,
                name VARCHAR,
                picture_url VARCHAR,
                auth_provider VARCHAR NOT NULL,
                created_at DATETIME,
                last_login_at DATETIME,
                theme_preference VARCHAR
            )
            """
        )
        connection.execute(
            """
            INSERT INTO users (
                id, email, name, auth_provider, created_at, theme_preference
            ) VALUES ('user-1', 'local@example.invalid', 'Local', 'development',
                      '2026-08-31 00:00:00', 'dark')
            """
        )

    actions = migrate(f"sqlite:///{database}")

    with sqlite3.connect(database) as connection:
        columns = {row[1] for row in connection.execute('PRAGMA table_info("users")')}
        row = connection.execute(
            "SELECT id, email, name, created_at, theme_preference FROM users"
        ).fetchone()

    assert not columns.intersection(OBSOLETE_COLUMNS)
    assert {"id", "email", "name", "created_at", "theme_preference"}.issubset(columns)
    assert row == (
        "user-1",
        "local@example.invalid",
        "Local",
        "2026-08-31 00:00:00",
        "dark",
    )
    assert len([action for action in actions if action.startswith("dropped:")]) == 3


def test_migration_is_idempotent_and_handles_missing_table(tmp_path):
    missing_database = tmp_path / "missing.db"
    assert migrate(f"sqlite:///{missing_database}") == ["skip missing table: users"]

    current_database = tmp_path / "current.db"
    with sqlite3.connect(current_database) as connection:
        connection.execute(
            "CREATE TABLE users (id VARCHAR PRIMARY KEY, email VARCHAR NOT NULL)"
        )

    assert all(
        action.startswith("absent:")
        for action in migrate(f"sqlite:///{current_database}")
    )
