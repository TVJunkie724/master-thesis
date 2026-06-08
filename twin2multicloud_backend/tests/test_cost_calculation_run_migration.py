import sqlite3

from migrations.add_cost_calculation_runs import migrate


def test_cost_calculation_run_migration_is_idempotent(tmp_path, monkeypatch):
    db_path = tmp_path / "management.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")

    migrate()
    migrate()

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(cost_calculation_runs)")
    run_columns = {row[1] for row in cursor.fetchall()}
    cursor.execute("PRAGMA table_info(cost_calculation_result_items)")
    item_columns = {row[1] for row in cursor.fetchall()}
    cursor.execute("PRAGMA index_list(cost_calculation_runs)")
    run_indexes = {row[1] for row in cursor.fetchall()}
    cursor.execute("PRAGMA index_list(cost_calculation_result_items)")
    item_indexes = {row[1] for row in cursor.fetchall()}
    conn.close()

    assert {
        "id",
        "twin_id",
        "user_id",
        "optimizer_config_id",
        "status",
        "params_json",
        "result_summary_json",
        "cheapest_path_json",
        "total_monthly_cost",
        "optimization_profile_id",
        "optimization_profile_version",
        "scoring_strategy_id",
        "calculation_model_version",
        "pricing_registry_version",
        "selected_for_deployment_at",
    }.issubset(run_columns)
    assert {
        "id",
        "run_id",
        "layer",
        "component",
        "provider",
        "service_intent_id",
        "cost_amount",
        "evidence_id",
        "service_model_id",
        "review_status",
    }.issubset(item_columns)
    assert "ix_cost_runs_twin_id" in run_indexes
    assert "ix_cost_runs_profile" in run_indexes
    assert "ix_cost_items_run_id" in item_indexes
    assert "ix_cost_items_evidence" in item_indexes

