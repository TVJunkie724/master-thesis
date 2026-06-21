"""Tests for explicit Management API SQLite migration helpers."""

from __future__ import annotations

import sqlite3

from migrations.ensure_current_schema_columns import migrate


def test_ensure_current_schema_columns_adds_missing_columns(tmp_path):
    db_path = tmp_path / "legacy.db"
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("CREATE TABLE twin_configurations (id VARCHAR PRIMARY KEY)")
        conn.execute("CREATE TABLE optimizer_configurations (id VARCHAR PRIMARY KEY)")
        conn.execute("CREATE TABLE deployment_logs (id VARCHAR PRIMARY KEY)")
        conn.commit()
    finally:
        conn.close()

    actions = migrate(f"sqlite:///{db_path}")
    second_run_actions = migrate(f"sqlite:///{db_path}")

    conn = sqlite3.connect(db_path)
    try:
        twin_columns = _columns(conn, "twin_configurations")
        optimizer_columns = _columns(conn, "optimizer_configurations")
        log_columns = _columns(conn, "deployment_logs")
    finally:
        conn.close()

    assert "added: twin_configurations.aws_sso_region" in actions
    assert "added: optimizer_configurations.pricing_aws_snapshot" in actions
    assert "added: deployment_logs.operation_type" in actions
    assert "exists: twin_configurations.aws_sso_region" in second_run_actions
    assert "aws_session_token" in twin_columns
    assert "gcp_service_account_json" in twin_columns
    assert "pricing_gcp_updated_at" in optimizer_columns
    assert "operation_type" in log_columns


def test_ensure_current_schema_columns_skips_missing_tables(tmp_path):
    db_path = tmp_path / "empty.db"

    actions = migrate(f"sqlite:///{db_path}")

    assert "skip missing table: twin_configurations" in actions
    assert "skip missing table: optimizer_configurations" in actions
    assert "skip missing table: deployment_logs" in actions


def _columns(conn: sqlite3.Connection, table_name: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table_name})")}
