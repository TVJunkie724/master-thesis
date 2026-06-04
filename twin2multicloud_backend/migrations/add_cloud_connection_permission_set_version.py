"""
Migration: Add permission_set_version to cloud_connections.

CloudConnections keep the versioned deployment permission baseline as
non-secret metadata. Existing rows are intentionally left NULL so preflight can
surface them as outdated/unknown until the connection is rotated or re-imported.

Usage:
    python -m migrations.add_cloud_connection_permission_set_version
"""

import os
import sqlite3


def migrate():
    db_path = os.environ.get("DATABASE_URL", "sqlite:///./management.db")
    if db_path.startswith("sqlite:///"):
        db_path = db_path.replace("sqlite:///", "")

    print(f"Migrating database: {db_path}")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        cursor.execute(
            "ALTER TABLE cloud_connections ADD COLUMN permission_set_version VARCHAR"
        )
        print("Added column: permission_set_version")
    except sqlite3.OperationalError as exc:
        if "duplicate column name" in str(exc).lower():
            print("Column already exists: permission_set_version")
        else:
            raise

    cursor.execute(
        "CREATE INDEX IF NOT EXISTS ix_cloud_connections_permission_set_version "
        "ON cloud_connections (permission_set_version)"
    )

    conn.commit()
    conn.close()
    print("\nMigration complete: cloud connection permission-set metadata is ready.")


if __name__ == "__main__":
    migrate()
