"""
Migration: Add pricing candidate review tables.

Run this script to create Management API review artifacts for pricing refresh
candidate reports and explicit reviewed decisions.

Usage:
    python -m migrations.add_pricing_review_tables
"""

import os
import sqlite3


def _resolve_db_path() -> str:
    db_path = os.environ.get("DATABASE_URL", "sqlite:///./management.db")
    if db_path.startswith("sqlite:///"):
        return db_path.replace("sqlite:///", "")
    return db_path


def migrate():
    db_path = _resolve_db_path()
    print(f"Migrating database: {db_path}")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS pricing_candidate_reports (
            id VARCHAR PRIMARY KEY,
            user_id VARCHAR NOT NULL,
            provider VARCHAR NOT NULL,
            refresh_run_id VARCHAR NOT NULL,
            intent_id VARCHAR NOT NULL,
            review_state VARCHAR NOT NULL,
            report_json TEXT NOT NULL,
            trace_json TEXT NOT NULL,
            created_at DATETIME,
            updated_at DATETIME,
            FOREIGN KEY(user_id) REFERENCES users (id),
            FOREIGN KEY(refresh_run_id) REFERENCES pricing_refresh_runs (id) ON DELETE CASCADE
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS pricing_review_decisions (
            id VARCHAR PRIMARY KEY,
            user_id VARCHAR NOT NULL,
            report_id VARCHAR NOT NULL,
            provider VARCHAR NOT NULL,
            intent_id VARCHAR NOT NULL,
            decision VARCHAR NOT NULL,
            selected_candidate_id VARCHAR,
            rationale TEXT,
            created_at DATETIME,
            FOREIGN KEY(user_id) REFERENCES users (id),
            FOREIGN KEY(report_id) REFERENCES pricing_candidate_reports (id) ON DELETE CASCADE
        )
        """
    )

    indexes = [
        ("ix_pricing_candidate_reports_user_id", "pricing_candidate_reports", "user_id"),
        ("ix_pricing_candidate_reports_provider", "pricing_candidate_reports", "provider"),
        ("ix_pricing_candidate_reports_run", "pricing_candidate_reports", "refresh_run_id"),
        ("ix_pricing_candidate_reports_intent", "pricing_candidate_reports", "intent_id"),
        ("ix_pricing_candidate_reports_state", "pricing_candidate_reports", "review_state"),
        ("ix_pricing_review_decisions_user_id", "pricing_review_decisions", "user_id"),
        ("ix_pricing_review_decisions_report", "pricing_review_decisions", "report_id"),
        ("ix_pricing_review_decisions_provider", "pricing_review_decisions", "provider"),
        ("ix_pricing_review_decisions_intent", "pricing_review_decisions", "intent_id"),
        ("ix_pricing_review_decisions_decision", "pricing_review_decisions", "decision"),
    ]
    for index_name, table_name, column_name in indexes:
        cursor.execute(
            f"CREATE INDEX IF NOT EXISTS {index_name} ON {table_name} ({column_name})"
        )

    conn.commit()
    conn.close()
    print("\nMigration complete: pricing review tables are ready.")


if __name__ == "__main__":
    migrate()
