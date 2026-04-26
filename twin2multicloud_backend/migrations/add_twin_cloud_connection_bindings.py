"""
Migration: Add CloudConnection binding columns to twin_configurations.

These nullable columns let a twin reference user-scoped CloudConnections while
legacy encrypted credential fields remain readable during the transition.

Usage:
    python -m migrations.add_twin_cloud_connection_bindings
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

    columns_to_add = [
        ("aws_cloud_connection_id", "VARCHAR"),
        ("azure_cloud_connection_id", "VARCHAR"),
        ("gcp_cloud_connection_id", "VARCHAR"),
    ]

    for column_name, column_type in columns_to_add:
        try:
            cursor.execute(f"ALTER TABLE twin_configurations ADD COLUMN {column_name} {column_type}")
            print(f"Added column: {column_name}")
        except sqlite3.OperationalError as exc:
            if "duplicate column name" in str(exc).lower():
                print(f"Column already exists: {column_name}")
            else:
                raise

    indexes = [
        ("ix_twin_configurations_aws_cloud_connection_id", "aws_cloud_connection_id"),
        ("ix_twin_configurations_azure_cloud_connection_id", "azure_cloud_connection_id"),
        ("ix_twin_configurations_gcp_cloud_connection_id", "gcp_cloud_connection_id"),
    ]
    for index_name, column_name in indexes:
        cursor.execute(
            f"CREATE INDEX IF NOT EXISTS {index_name} ON twin_configurations ({column_name})"
        )

    conn.commit()
    conn.close()
    print("\nMigration complete: twin CloudConnection bindings are ready.")


if __name__ == "__main__":
    migrate()
