"""Create the bounded current-source persistence for Twin user functions."""

from __future__ import annotations

import sqlite3

from migrations.ensure_current_schema_columns import resolve_sqlite_path

LEGACY_TABLES = (
    "twin_extension_bindings",
    "user_function_artifact_dependencies",
    "user_function_artifact_files",
    "user_function_audit_events",
    "user_function_artifacts",
)


def migrate(database_url: str | None = None) -> list[str]:
    database_path = resolve_sqlite_path(database_url)
    actions: list[str] = []
    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        for table in LEGACY_TABLES:
            if _table_exists(connection, table):
                connection.execute(f'DROP TABLE "{table}"')
                actions.append(f"dropped: {table}")
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS twin_user_functions (
                id VARCHAR PRIMARY KEY,
                twin_id VARCHAR NOT NULL REFERENCES digital_twins(id) ON DELETE CASCADE,
                artifact_digest VARCHAR(71) NOT NULL,
                slot_id VARCHAR(128) NOT NULL,
                slot_version VARCHAR(10) NOT NULL,
                runtime_id VARCHAR(32) NOT NULL,
                manifest_json TEXT NOT NULL,
                configuration_json TEXT NOT NULL DEFAULT '{}',
                declared_capabilities_json TEXT NOT NULL DEFAULT '[]',
                validator_version VARCHAR(64) NOT NULL,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                CONSTRAINT uq_twin_user_function_slot
                    UNIQUE(twin_id, slot_id, slot_version)
            );
            CREATE INDEX IF NOT EXISTS ix_twin_user_functions_twin
                ON twin_user_functions(twin_id);

            CREATE TABLE IF NOT EXISTS twin_user_function_files (
                id VARCHAR PRIMARY KEY,
                user_function_id VARCHAR NOT NULL
                    REFERENCES twin_user_functions(id) ON DELETE CASCADE,
                relative_path VARCHAR(240) NOT NULL,
                content_text TEXT NOT NULL,
                content_digest VARCHAR(71) NOT NULL,
                size_bytes INTEGER NOT NULL,
                CONSTRAINT uq_twin_user_function_file_path
                    UNIQUE(user_function_id, relative_path)
            );

            CREATE TABLE IF NOT EXISTS twin_user_function_dependencies (
                id VARCHAR PRIMARY KEY,
                user_function_id VARCHAR NOT NULL
                    REFERENCES twin_user_functions(id) ON DELETE CASCADE,
                name VARCHAR(128) NOT NULL,
                version VARCHAR(64) NOT NULL,
                hashes_json TEXT NOT NULL,
                policy_result VARCHAR(32) NOT NULL,
                CONSTRAINT uq_twin_user_function_dependency_name
                    UNIQUE(user_function_id, name)
            );
            """
        )
        connection.commit()
    actions.append("ensured: bounded Twin user-function tables")
    return actions


def _table_exists(connection: sqlite3.Connection, table: str) -> bool:
    return (
        connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        ).fetchone()
        is not None
    )
