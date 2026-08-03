"""Migration 023 deployment graph evidence regression test."""

from __future__ import annotations

import sqlite3

from migrations.add_deployment_graph_evidence import migrate


def test_deployment_graph_evidence_migration_is_idempotent(
    tmp_path,
    monkeypatch,
):
    database_path = tmp_path / "management.db"
    connection = sqlite3.connect(database_path)
    connection.execute(
        """
        CREATE TABLE deployments (
            id VARCHAR PRIMARY KEY,
            twin_id VARCHAR NOT NULL,
            session_id VARCHAR NOT NULL
        )
        """
    )
    connection.commit()
    connection.close()
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path}")

    migrate()
    migrate()

    connection = sqlite3.connect(database_path)
    columns = {row[1] for row in connection.execute("PRAGMA table_info(deployments)")}
    indexes = {row[1] for row in connection.execute("PRAGMA index_list(deployments)")}
    connection.close()

    assert {
        "architecture_digest",
        "graph_digest",
        "profile_id",
        "profile_version",
        "catalog_id",
        "catalog_version",
        "completed_stage",
        "graph_validation",
    } <= columns
    assert "ix_deployments_graph_digest" in indexes
