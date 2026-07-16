"""Create provider-neutral authentication state and migrate legacy identities."""

from __future__ import annotations

import os
import sqlite3
import uuid


def _resolve_db_path() -> str:
    database_url = os.environ.get("DATABASE_URL", "sqlite:///./data/app.db")
    if database_url.startswith("sqlite:///"):
        return database_url.removeprefix("sqlite:///")
    return database_url


def migrate(database_url: str | None = None) -> list[str]:
    path = (
        database_url.removeprefix("sqlite:///")
        if database_url and database_url.startswith("sqlite:///")
        else _resolve_db_path()
    )
    actions: list[str] = []
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        _create_tables(connection)
        actions.append("authentication tables ready")
        if _table_exists(connection, "users"):
            columns = _columns(connection, "users")
            for provider, column in (("google", "google_id"), ("uibk", "uibk_id")):
                if column not in columns:
                    continue
                rows = connection.execute(
                    f"SELECT id, email, {column} FROM users WHERE {column} IS NOT NULL"
                ).fetchall()
                for user_id, email, subject in rows:
                    _assert_identity_slot_available(
                        connection,
                        provider=provider,
                        subject=subject,
                        user_id=user_id,
                    )
                    connection.execute(
                        """
                        INSERT INTO external_identities (
                            id, user_id, provider, subject, email_at_login,
                            created_at, last_login_at
                        ) VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                        ON CONFLICT(provider, subject) DO NOTHING
                        """,
                        (str(uuid.uuid4()), user_id, provider, subject, email),
                    )
                actions.append(f"migrated {provider} identities: {len(rows)}")
    return actions


def _assert_identity_slot_available(
    connection: sqlite3.Connection,
    *,
    provider: str,
    subject: str,
    user_id: str,
) -> None:
    by_subject = connection.execute(
        "SELECT user_id FROM external_identities WHERE provider = ? AND subject = ?",
        (provider, subject),
    ).fetchone()
    by_user = connection.execute(
        "SELECT subject FROM external_identities WHERE user_id = ? AND provider = ?",
        (user_id, provider),
    ).fetchone()
    if by_subject is not None and by_subject[0] != user_id:
        raise RuntimeError(
            f"Legacy {provider} subject is already bound to a different user"
        )
    if by_user is not None and by_user[0] != subject:
        raise RuntimeError(
            f"User already has a different {provider} external identity"
        )


def _create_tables(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS external_identities (
            id VARCHAR PRIMARY KEY,
            user_id VARCHAR NOT NULL,
            provider VARCHAR NOT NULL,
            subject VARCHAR NOT NULL,
            email_at_login VARCHAR NOT NULL,
            created_at DATETIME NOT NULL,
            last_login_at DATETIME NOT NULL,
            CONSTRAINT uq_external_identity_provider_subject UNIQUE (provider, subject),
            FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
        );
        CREATE UNIQUE INDEX IF NOT EXISTS ix_external_identities_user_provider
            ON external_identities (user_id, provider);
        CREATE INDEX IF NOT EXISTS ix_external_identities_user_id
            ON external_identities (user_id);

        CREATE TABLE IF NOT EXISTS auth_login_transactions (
            id VARCHAR PRIMARY KEY,
            provider VARCHAR NOT NULL,
            purpose VARCHAR NOT NULL DEFAULT 'login',
            state_digest VARCHAR(64) NOT NULL UNIQUE,
            poll_verifier_digest VARCHAR(64) NOT NULL,
            pkce_verifier_encrypted TEXT,
            provider_request_id VARCHAR,
            status VARCHAR NOT NULL DEFAULT 'pending',
            user_id VARCHAR,
            error_code VARCHAR,
            created_at DATETIME NOT NULL,
            expires_at DATETIME NOT NULL,
            callback_consumed_at DATETIME,
            completed_at DATETIME,
            exchange_consumed_at DATETIME,
            cancelled_at DATETIME,
            FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE SET NULL
        );
        CREATE INDEX IF NOT EXISTS ix_auth_login_transactions_status_expiry
            ON auth_login_transactions (status, expires_at);
        CREATE INDEX IF NOT EXISTS ix_auth_login_transactions_poll_digest
            ON auth_login_transactions (poll_verifier_digest);

        CREATE TABLE IF NOT EXISTS auth_sessions (
            id VARCHAR PRIMARY KEY,
            user_id VARCHAR NOT NULL,
            issued_at DATETIME NOT NULL,
            expires_at DATETIME NOT NULL,
            revoked_at DATETIME,
            revocation_reason VARCHAR,
            FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS ix_auth_sessions_user_id ON auth_sessions (user_id);
        CREATE INDEX IF NOT EXISTS ix_auth_sessions_user_expiry
            ON auth_sessions (user_id, expires_at);
        CREATE INDEX IF NOT EXISTS ix_auth_sessions_active
            ON auth_sessions (expires_at, revoked_at);

        CREATE TABLE IF NOT EXISTS authentication_events (
            id VARCHAR PRIMARY KEY,
            action VARCHAR NOT NULL,
            outcome VARCHAR NOT NULL,
            provider VARCHAR,
            transaction_id VARCHAR,
            user_id VARCHAR,
            http_status INTEGER NOT NULL,
            request_id VARCHAR NOT NULL,
            occurred_at DATETIME NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE SET NULL
        );
        CREATE INDEX IF NOT EXISTS ix_authentication_events_request_id
            ON authentication_events (request_id);
        CREATE INDEX IF NOT EXISTS ix_authentication_events_transaction
            ON authentication_events (transaction_id);
        CREATE INDEX IF NOT EXISTS ix_authentication_events_user_time
            ON authentication_events (user_id, occurred_at);
        """
    )


def _table_exists(connection: sqlite3.Connection, table: str) -> bool:
    return connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone() is not None


def _columns(connection: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}


if __name__ == "__main__":
    migrate()
