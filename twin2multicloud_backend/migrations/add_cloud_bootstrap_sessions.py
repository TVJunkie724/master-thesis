"""Create the durable, secret-free guided bootstrap session table."""

from __future__ import annotations

import os
import sqlite3

from migrations.ensure_current_schema_columns import resolve_sqlite_path


def migrate(database_url: str | None = None) -> list[str]:
    path = resolve_sqlite_path(database_url or os.environ.get("DATABASE_URL"))
    actions: list[str] = []
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS cloud_bootstrap_sessions (
                id VARCHAR PRIMARY KEY,
                user_id VARCHAR NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                provider VARCHAR(16) NOT NULL
                    CHECK (provider IN ('aws', 'azure', 'gcp')),
                target_scope_digest VARCHAR(71) NOT NULL,
                target_json TEXT NOT NULL,
                entry_point VARCHAR(32) NOT NULL
                    CHECK (entry_point IN ('settings', 'twin_prepare')),
                twin_id VARCHAR REFERENCES digital_twins(id) ON DELETE SET NULL,
                display_name VARCHAR(120) NOT NULL,
                revision INTEGER NOT NULL CHECK (revision > 0),
                state VARCHAR(48) NOT NULL CHECK (
                    state IN (
                        'draft', 'bootstrap_running',
                        'generated_connection_ready', 'disposal_running',
                        'manual_revocation_required',
                        'credential_reentry_required', 'ready', 'failed',
                        'cancelled', 'expired'
                    )
                ),
                guide_digest VARCHAR(71) NOT NULL,
                bootstrap_authority_pack_id VARCHAR(128) NOT NULL,
                bootstrap_authority_pack_version VARCHAR(32) NOT NULL,
                bootstrap_authority_pack_digest VARCHAR(71) NOT NULL,
                generated_deployment_pack_id VARCHAR(128) NOT NULL,
                generated_deployment_pack_version VARCHAR(32) NOT NULL,
                generated_deployment_pack_digest VARCHAR(71) NOT NULL,
                create_idempotency_key VARCHAR(128) NOT NULL,
                create_request_digest VARCHAR(71) NOT NULL,
                execute_idempotency_key VARCHAR(128),
                credential_origin VARCHAR(32),
                disposal_status VARCHAR(48),
                credential_expires_at DATETIME,
                safe_credential_identifier VARCHAR(160),
                finding_json TEXT,
                connection_id VARCHAR
                    REFERENCES cloud_connections(id) ON DELETE SET NULL,
                lease_started_at DATETIME,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                CONSTRAINT uq_cloud_bootstrap_create_idempotency
                    UNIQUE (user_id, create_idempotency_key)
            )
            """
        )
        actions.append("ensured: cloud_bootstrap_sessions")
        connection.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS
                uq_cloud_bootstrap_active_scope
            ON cloud_bootstrap_sessions (
                user_id, provider, target_scope_digest
            )
            WHERE state IN (
                'draft', 'bootstrap_running', 'generated_connection_ready',
                'disposal_running', 'manual_revocation_required',
                'credential_reentry_required'
            )
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS ix_cloud_bootstrap_owner_provider
            ON cloud_bootstrap_sessions (user_id, provider)
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS ix_cloud_bootstrap_connection
            ON cloud_bootstrap_sessions (connection_id)
            """
        )
        actions.append("ensured: cloud bootstrap indexes")
    return actions
