"""Migration 017: append-only credential security event storage."""

import os
import sqlite3


def _resolve_db_path() -> str:
    database_url = os.environ.get("DATABASE_URL", "sqlite:///./data/app.db")
    return database_url.removeprefix("sqlite:///")


def migrate() -> None:
    with sqlite3.connect(_resolve_db_path()) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS credential_security_events (
                id VARCHAR PRIMARY KEY,
                user_id VARCHAR NOT NULL,
                action VARCHAR NOT NULL,
                outcome VARCHAR NOT NULL,
                resource_type VARCHAR NOT NULL,
                resource_id VARCHAR,
                provider VARCHAR,
                purpose VARCHAR,
                http_status INTEGER NOT NULL,
                request_id VARCHAR NOT NULL,
                occurred_at DATETIME NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users (id)
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS ix_credential_security_events_user_time "
            "ON credential_security_events (user_id, occurred_at)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS ix_credential_security_events_request_id "
            "ON credential_security_events (request_id)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS ix_credential_security_events_action "
            "ON credential_security_events (action)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS ix_credential_security_events_resource "
            "ON credential_security_events (resource_type, resource_id)"
        )
