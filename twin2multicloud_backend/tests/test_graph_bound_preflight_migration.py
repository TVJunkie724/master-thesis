"""Migration 030 graph-bound preflight regression tests."""

from __future__ import annotations

import sqlite3

from migrations.bind_preflight_to_graph_requirements import migrate


def test_graph_bound_preflight_migration_is_idempotent(tmp_path, monkeypatch):
    database_path = tmp_path / "management.db"
    connection = sqlite3.connect(database_path)
    connection.execute(
        """
        CREATE TABLE deployment_preflight_cache (
            id VARCHAR PRIMARY KEY,
            twin_id VARCHAR NOT NULL,
            provider VARCHAR NOT NULL
        )
        """
    )
    connection.commit()
    connection.close()
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path}")

    migrate()
    assert migrate() == []

    connection = sqlite3.connect(database_path)
    columns = {
        row[1]: row
        for row in connection.execute(
            "PRAGMA table_info(deployment_preflight_cache)"
        )
    }
    connection.close()

    assert {
        "architecture_digest",
        "graph_digest",
        "requirements_digest",
        "requirements_json",
    } <= set(columns)
    assert columns["requirements_json"][4] == "'[]'"
