"""
Migration: Add cost calculation run history tables.

Run this script to create the typed optimizer run-history tables in the
Management API database.

Usage:
    python -m migrations.add_cost_calculation_runs
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
        CREATE TABLE IF NOT EXISTS cost_calculation_runs (
            id VARCHAR PRIMARY KEY,
            twin_id VARCHAR NOT NULL,
            user_id VARCHAR NOT NULL,
            optimizer_config_id VARCHAR,
            status VARCHAR NOT NULL DEFAULT 'succeeded',
            params_json TEXT NOT NULL,
            result_summary_json TEXT,
            cheapest_path_json TEXT,
            total_monthly_cost FLOAT,
            currency VARCHAR NOT NULL DEFAULT 'USD',
            optimization_profile_id VARCHAR NOT NULL,
            optimization_profile_version VARCHAR,
            scoring_strategy_id VARCHAR NOT NULL,
            calculation_model_version VARCHAR,
            pricing_registry_version VARCHAR,
            pricing_evidence_version VARCHAR,
            pricing_run_reference VARCHAR,
            created_at DATETIME,
            completed_at DATETIME,
            selected_for_deployment_at DATETIME,
            error_code VARCHAR,
            error_message VARCHAR,
            FOREIGN KEY(twin_id) REFERENCES digital_twins (id) ON DELETE CASCADE,
            FOREIGN KEY(user_id) REFERENCES users (id),
            FOREIGN KEY(optimizer_config_id) REFERENCES optimizer_configurations (id) ON DELETE SET NULL
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS cost_calculation_result_items (
            id VARCHAR PRIMARY KEY,
            run_id VARCHAR NOT NULL,
            layer VARCHAR NOT NULL,
            component VARCHAR,
            provider VARCHAR,
            service_intent_id VARCHAR,
            cost_amount FLOAT,
            currency VARCHAR NOT NULL DEFAULT 'USD',
            unit VARCHAR,
            quantity FLOAT,
            unit_price FLOAT,
            evidence_id VARCHAR,
            service_model_id VARCHAR,
            calculation_notes_json TEXT,
            review_status VARCHAR,
            created_at DATETIME,
            FOREIGN KEY(run_id) REFERENCES cost_calculation_runs (id) ON DELETE CASCADE
        )
        """
    )

    indexes = [
        ("ix_cost_runs_twin_id", "cost_calculation_runs", "twin_id"),
        ("ix_cost_runs_user_id", "cost_calculation_runs", "user_id"),
        ("ix_cost_runs_optimizer_config_id", "cost_calculation_runs", "optimizer_config_id"),
        ("ix_cost_runs_status", "cost_calculation_runs", "status"),
        ("ix_cost_runs_profile", "cost_calculation_runs", "optimization_profile_id"),
        ("ix_cost_items_run_id", "cost_calculation_result_items", "run_id"),
        ("ix_cost_items_layer", "cost_calculation_result_items", "layer"),
        ("ix_cost_items_provider", "cost_calculation_result_items", "provider"),
        ("ix_cost_items_intent", "cost_calculation_result_items", "service_intent_id"),
        ("ix_cost_items_evidence", "cost_calculation_result_items", "evidence_id"),
    ]
    for index_name, table_name, column_name in indexes:
        cursor.execute(
            f"CREATE INDEX IF NOT EXISTS {index_name} ON {table_name} ({column_name})"
        )

    conn.commit()
    conn.close()
    print("\nMigration complete: cost calculation run history is ready.")


if __name__ == "__main__":
    migrate()

