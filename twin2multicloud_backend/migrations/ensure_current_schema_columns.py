"""
Migration: Ensure additive columns required by the current Management API schema.

This script is intentionally idempotent for SQLite development and thesis
handoff databases. Fresh databases are still created through SQLAlchemy
`Base.metadata.create_all()`, while existing databases need explicit ALTER TABLE
steps because `create_all()` does not add missing columns.

Usage:
    python -m migrations.ensure_current_schema_columns
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path


ADDITIVE_COLUMNS: dict[str, list[tuple[str, str]]] = {
    "twin_configurations": [
        ("aws_sso_region", "VARCHAR"),
        ("aws_session_token", "VARCHAR"),
        ("azure_region", "VARCHAR DEFAULT 'westeurope'"),
        ("azure_region_iothub", "VARCHAR"),
        ("azure_region_digital_twin", "VARCHAR"),
        ("gcp_project_id", "VARCHAR"),
        ("gcp_billing_account", "VARCHAR"),
        ("gcp_region", "VARCHAR DEFAULT 'europe-west1'"),
        ("gcp_service_account_json", "TEXT"),
    ],
    "optimizer_configurations": [
        ("pricing_aws_updated_at", "DATETIME"),
        ("pricing_azure_updated_at", "DATETIME"),
        ("pricing_gcp_updated_at", "DATETIME"),
        ("pricing_aws_snapshot", "TEXT"),
        ("pricing_azure_snapshot", "TEXT"),
        ("pricing_gcp_snapshot", "TEXT"),
        ("calculated_at", "DATETIME"),
    ],
    "deployment_logs": [
        ("operation_type", "VARCHAR DEFAULT 'deploy'"),
    ],
}


def resolve_sqlite_path(database_url: str | None = None) -> Path:
    """Resolve a SQLite database URL or filesystem path to a Path."""
    raw = database_url or os.environ.get("DATABASE_URL", "sqlite:///./management.db")
    if raw.startswith("sqlite:///"):
        raw = raw.removeprefix("sqlite:///")
    if raw.startswith("sqlite://"):
        raise ValueError("Only file-backed sqlite:/// URLs are supported by this migration")
    return Path(raw)


def migrate(database_url: str | None = None) -> list[str]:
    """Apply all missing additive columns and return human-readable actions."""
    db_path = resolve_sqlite_path(database_url)
    conn = sqlite3.connect(db_path)
    try:
        actions: list[str] = []
        for table_name, columns in ADDITIVE_COLUMNS.items():
            if not _table_exists(conn, table_name):
                actions.append(f"skip missing table: {table_name}")
                continue
            existing_columns = _existing_columns(conn, table_name)
            for column_name, column_type in columns:
                if column_name in existing_columns:
                    actions.append(f"exists: {table_name}.{column_name}")
                    continue
                conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")
                actions.append(f"added: {table_name}.{column_name}")
        conn.commit()
        return actions
    finally:
        conn.close()


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    cursor = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    )
    return cursor.fetchone() is not None


def _existing_columns(conn: sqlite3.Connection, table_name: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table_name})")}


if __name__ == "__main__":
    for action in migrate():
        print(action)
