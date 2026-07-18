import sqlite3

import pytest

from migrations.add_production_authentication import migrate


def test_authentication_migration_is_idempotent_and_copies_legacy_identities(tmp_path):
    database = tmp_path / "auth.db"
    with sqlite3.connect(database) as connection:
        connection.execute(
            """
            CREATE TABLE users (
                id VARCHAR PRIMARY KEY,
                email VARCHAR NOT NULL,
                google_id VARCHAR,
                uibk_id VARCHAR
            )
            """
        )
        connection.execute(
            "INSERT INTO users VALUES ('u1', 'person@example.test', 'google-sub', 'uibk-sub')"
        )

    first = migrate(f"sqlite:///{database}")
    second = migrate(f"sqlite:///{database}")

    with sqlite3.connect(database) as connection:
        identities = connection.execute(
            "SELECT provider, subject, user_id FROM external_identities ORDER BY provider"
        ).fetchall()
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }

    assert "authentication tables ready" in first
    assert "authentication tables ready" in second
    assert identities == [
        ("google", "google-sub", "u1"),
        ("uibk", "uibk-sub", "u1"),
    ]
    assert {
        "external_identities",
        "auth_login_transactions",
        "auth_sessions",
        "authentication_events",
    } <= tables


def test_authentication_migration_rejects_conflicting_legacy_identity(tmp_path):
    database = tmp_path / "auth-conflict.db"
    with sqlite3.connect(database) as connection:
        connection.execute(
            """
            CREATE TABLE users (
                id VARCHAR PRIMARY KEY,
                email VARCHAR NOT NULL,
                google_id VARCHAR,
                uibk_id VARCHAR
            )
            """
        )
        connection.executemany(
            "INSERT INTO users VALUES (?, ?, ?, NULL)",
            [
                ("u1", "first@example.test", "shared-subject"),
                ("u2", "second@example.test", None),
            ],
        )
    migrate(f"sqlite:///{database}")
    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE external_identities SET user_id = 'u2' WHERE provider = 'google'"
        )

    with pytest.raises(RuntimeError, match="different user"):
        migrate(f"sqlite:///{database}")


def test_authentication_migration_skips_unavailable_legacy_provider_column(tmp_path):
    database = tmp_path / "auth-google-only.db"
    with sqlite3.connect(database) as connection:
        connection.execute(
            """
            CREATE TABLE users (
                id VARCHAR PRIMARY KEY,
                email VARCHAR NOT NULL,
                google_id VARCHAR
            )
            """
        )
        connection.execute(
            "INSERT INTO users VALUES ('u1', 'person@example.test', 'google-sub')"
        )

    actions = migrate(f"sqlite:///{database}")

    with sqlite3.connect(database) as connection:
        identities = connection.execute(
            "SELECT provider, subject, user_id FROM external_identities"
        ).fetchall()

    assert "migrated google identities: 1" in actions
    assert not any("uibk" in action for action in actions)
    assert identities == [("google", "google-sub", "u1")]
