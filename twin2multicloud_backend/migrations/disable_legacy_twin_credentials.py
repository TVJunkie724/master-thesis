"""
Migration: Disable legacy per-twin credential storage.

CloudConnections are the runtime credential source of truth. This migration
clears duplicated legacy secret columns on twin_configurations while preserving
CloudConnection bindings and non-secret provider metadata used by the UI.

Usage:
    python -m migrations.disable_legacy_twin_credentials
"""

import os
import sqlite3


LEGACY_COLUMNS = (
    "aws_access_key_id",
    "aws_secret_access_key",
    "aws_session_token",
    "aws_sso_region",
    "azure_subscription_id",
    "azure_client_id",
    "azure_client_secret",
    "azure_tenant_id",
    "gcp_billing_account",
    "gcp_service_account_json",
)


def migrate():
    db_path = os.environ.get("DATABASE_URL", "sqlite:///./management.db")
    if db_path.startswith("sqlite:///"):
        db_path = db_path.replace("sqlite:///", "")

    print(f"Migrating database: {db_path}")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    existing_columns = {
        row[1]
        for row in cursor.execute("PRAGMA table_info(twin_configurations)").fetchall()
    }

    missing = [column for column in LEGACY_COLUMNS if column not in existing_columns]
    if missing:
        print(f"Skipping missing legacy columns: {', '.join(missing)}")

    columns_to_clear = [column for column in LEGACY_COLUMNS if column in existing_columns]
    if columns_to_clear:
        set_clauses = [f"{column} = NULL" for column in columns_to_clear]
        for validation_column, binding_column in (
            ("aws_validated", "aws_cloud_connection_id"),
            ("azure_validated", "azure_cloud_connection_id"),
            ("gcp_validated", "gcp_cloud_connection_id"),
        ):
            if validation_column in existing_columns and binding_column in existing_columns:
                set_clauses.append(
                    f"{validation_column} = CASE "
                    f"WHEN {binding_column} IS NULL THEN 0 ELSE {validation_column} END"
                )

        # set_clauses are built from hardcoded allowlists above; no
        # user-controlled identifiers or values enter this statement.
        cursor.execute(f"UPDATE twin_configurations SET {', '.join(set_clauses)}")  # nosec B608
        print(f"Cleared legacy credential columns on {cursor.rowcount} twin configurations.")
    else:
        print("No legacy credential columns found.")

    conn.commit()
    conn.close()
    print("\nMigration complete: per-twin credential secrets are disabled.")


if __name__ == "__main__":
    migrate()
