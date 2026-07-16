import sqlite3

from migrations.add_credential_security_events import migrate


def test_credential_security_event_migration_is_idempotent(tmp_path, monkeypatch):
    database = tmp_path / "audit.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database}")
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE users (id VARCHAR PRIMARY KEY)")

    migrate()
    migrate()

    with sqlite3.connect(database) as connection:
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(credential_security_events)")
        }
        indexes = {
            row[1] for row in connection.execute("PRAGMA index_list(credential_security_events)")
        }

    assert columns == {
        "id",
        "user_id",
        "action",
        "outcome",
        "resource_type",
        "resource_id",
        "provider",
        "purpose",
        "http_status",
        "request_id",
        "occurred_at",
    }
    assert "ix_credential_security_events_user_time" in indexes
    assert "ix_credential_security_events_request_id" in indexes
