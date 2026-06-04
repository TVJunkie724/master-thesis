"""
Migration: Add cloud_connections table.

Run this script to create the user-scoped Cloud Connections credential store.
This is needed because SQLAlchemy's create_all() is implicit and does not give
existing installations an auditable upgrade step.

Usage:
    python -m migrations.add_cloud_connections_table
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

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS cloud_connections (
            id VARCHAR PRIMARY KEY,
            user_id VARCHAR NOT NULL,
            provider VARCHAR NOT NULL,
            display_name VARCHAR NOT NULL,
            cloud_scope TEXT NOT NULL DEFAULT '{}',
            auth_type VARCHAR NOT NULL,
            permission_set_version VARCHAR,
            encrypted_payload TEXT NOT NULL,
            payload_fingerprint VARCHAR NOT NULL,
            validation_status VARCHAR NOT NULL DEFAULT 'untested',
            validation_message VARCHAR,
            last_validated_at DATETIME,
            created_at DATETIME,
            updated_at DATETIME,
            FOREIGN KEY(user_id) REFERENCES users (id)
        )
        """
    )

    cursor.execute("PRAGMA table_info(cloud_connections)")
    columns = {row[1] for row in cursor.fetchall()}
    if "permission_set_version" not in columns:
        cursor.execute(
            "ALTER TABLE cloud_connections ADD COLUMN permission_set_version VARCHAR"
        )

    indexes = [
        ("ix_cloud_connections_user_id", "user_id"),
        ("ix_cloud_connections_provider", "provider"),
        ("ix_cloud_connections_permission_set_version", "permission_set_version"),
        ("ix_cloud_connections_payload_fingerprint", "payload_fingerprint"),
    ]
    for index_name, column_name in indexes:
        cursor.execute(
            f"CREATE INDEX IF NOT EXISTS {index_name} ON cloud_connections ({column_name})"
        )

    conn.commit()
    conn.close()
    print("\nMigration complete: cloud_connections table is ready.")


if __name__ == "__main__":
    migrate()
