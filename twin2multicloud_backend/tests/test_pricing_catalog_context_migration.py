"""Migration tests for compact immutable pricing-catalog evidence."""

from __future__ import annotations

import json
import sqlite3

from migrations.add_pricing_catalog_context import migrate
from tests.pricing_catalog_test_data import catalog_context


def test_migration_adds_columns_and_backfills_only_valid_contexts(tmp_path):
    database_path = tmp_path / "legacy.db"
    valid_result = json.dumps(
        {"pricingCatalogs": catalog_context().to_http_dict()}
    )
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "CREATE TABLE cost_calculation_runs "
            "(id VARCHAR PRIMARY KEY, result_summary_json TEXT)"
        )
        connection.execute(
            "CREATE TABLE optimizer_configurations "
            "(id VARCHAR PRIMARY KEY, result_json TEXT)"
        )
        connection.executemany(
            "INSERT INTO cost_calculation_runs VALUES (?, ?)",
            [
                ("valid-run", valid_result),
                ("invalid-run", '{"pricingCatalogs":{"schemaVersion":"bad"}}'),
            ],
        )
        connection.executemany(
            "INSERT INTO optimizer_configurations VALUES (?, ?)",
            [
                ("valid-config", valid_result),
                ("invalid-config", "not-json"),
            ],
        )

    first = migrate(f"sqlite:///{database_path}")
    second = migrate(f"sqlite:///{database_path}")

    assert "added: cost_calculation_runs.pricing_catalog_context_json" in first
    assert "added: optimizer_configurations.pricing_catalog_context_json" in first
    assert "backfilled: cost_calculation_runs=1" in first
    assert "backfilled: optimizer_configurations=1" in first
    assert "exists: cost_calculation_runs.pricing_catalog_context_json" in second
    assert "backfilled: cost_calculation_runs=0" in second

    with sqlite3.connect(database_path) as connection:
        run_rows = dict(
            connection.execute(
                "SELECT id, pricing_catalog_context_json "
                "FROM cost_calculation_runs"
            )
        )
        config_rows = dict(
            connection.execute(
                "SELECT id, pricing_catalog_context_json "
                "FROM optimizer_configurations"
            )
        )

    expected = catalog_context().to_http_dict()
    assert json.loads(run_rows["valid-run"]) == expected
    assert run_rows["invalid-run"] is None
    assert json.loads(config_rows["valid-config"]) == expected
    assert config_rows["invalid-config"] is None


def test_migration_skips_absent_tables(tmp_path):
    database_path = tmp_path / "empty.db"

    actions = migrate(f"sqlite:///{database_path}")

    assert actions == [
        "skip missing table: cost_calculation_runs",
        "skip missing table: optimizer_configurations",
    ]
