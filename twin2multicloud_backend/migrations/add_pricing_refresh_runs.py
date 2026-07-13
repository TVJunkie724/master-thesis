"""
Migration: Add pricing refresh run history table.

Run this script to create the Management API run records used by the canonical
pricing refresh contract.

Usage:
    python -m migrations.add_pricing_refresh_runs
"""

import os
import sqlite3


def _resolve_db_path() -> str:
    db_path = os.environ.get("DATABASE_URL", "sqlite:///./management.db")
    if db_path.startswith("sqlite:///"):
        return db_path.replace("sqlite:///", "")
    return db_path


def migrate():
    db_path = _resolve_db_path()
    print(f"Migrating database: {db_path}")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS pricing_refresh_runs (
            id VARCHAR PRIMARY KEY,
            user_id VARCHAR NOT NULL,
            provider VARCHAR NOT NULL,
            status VARCHAR NOT NULL DEFAULT 'running',
            pricing_connection_id VARCHAR,
            force BOOLEAN NOT NULL DEFAULT 0,
            credential_summary_json TEXT NOT NULL,
            result_summary_json TEXT,
            error_code VARCHAR,
            error_message VARCHAR,
            created_at DATETIME,
            started_at DATETIME,
            completed_at DATETIME,
            FOREIGN KEY(user_id) REFERENCES users (id),
            FOREIGN KEY(pricing_connection_id) REFERENCES cloud_connections (id) ON DELETE SET NULL
        )
        """
    )

    indexes = [
        ("ix_pricing_refresh_runs_user_id", "pricing_refresh_runs", "user_id"),
        ("ix_pricing_refresh_runs_provider", "pricing_refresh_runs", "provider"),
        ("ix_pricing_refresh_runs_status", "pricing_refresh_runs", "status"),
        ("ix_pricing_refresh_runs_connection", "pricing_refresh_runs", "pricing_connection_id"),
    ]
    for index_name, table_name, column_name in indexes:
        cursor.execute(
            f"CREATE INDEX IF NOT EXISTS {index_name} ON {table_name} ({column_name})"
        )

    conn.commit()
    conn.close()
    print("\nMigration complete: pricing refresh run history is ready.")


if __name__ == "__main__":
    migrate()
