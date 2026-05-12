"""
Migration: Add Deployer operation state columns to deployments table.

Adds operation_id and error_code for correlating Management API deployment
history with Deployer logs and typed failure contracts.

Usage:
    python -m migrations.add_deployment_operation_state_columns
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
        ("operation_id", "VARCHAR"),
        ("error_code", "VARCHAR"),
    ]

    for column_name, column_type in columns_to_add:
        try:
            cursor.execute(f"ALTER TABLE deployments ADD COLUMN {column_name} {column_type}")
            print(f"✓ Added column: {column_name}")
        except sqlite3.OperationalError as exc:
            if "duplicate column name" in str(exc).lower():
                print(f"✓ Column already exists: {column_name}")
            else:
                raise

    try:
        cursor.execute(
            "CREATE INDEX ix_deployments_operation_id ON deployments (operation_id)"
        )
        print("✓ Added index: ix_deployments_operation_id")
    except sqlite3.OperationalError as exc:
        if "already exists" in str(exc).lower():
            print("✓ Index already exists: ix_deployments_operation_id")
        else:
            raise

    conn.commit()
    conn.close()
    print("\n✓ Migration complete!")


if __name__ == "__main__":
    migrate()
