"""Add immutable pricing-catalog references to optimizer persistence."""

from __future__ import annotations

import json
import os
import sqlite3
from typing import Any

from pydantic import ValidationError

from src.schemas.pricing_catalog import PricingCatalogContext


MIGRATION_TARGETS = (
    {
        "table": "cost_calculation_runs",
        "result_column": "result_summary_json",
        "alter": (
            "ALTER TABLE cost_calculation_runs "
            "ADD COLUMN pricing_catalog_context_json TEXT"
        ),
        "select": (
            "SELECT id, result_summary_json FROM cost_calculation_runs "
            "WHERE pricing_catalog_context_json IS NULL"
        ),
        "update": (
            "UPDATE cost_calculation_runs "
            "SET pricing_catalog_context_json = ? "
            "WHERE id = ? AND pricing_catalog_context_json IS NULL"
        ),
    },
    {
        "table": "optimizer_configurations",
        "result_column": "result_json",
        "alter": (
            "ALTER TABLE optimizer_configurations "
            "ADD COLUMN pricing_catalog_context_json TEXT"
        ),
        "select": (
            "SELECT id, result_json FROM optimizer_configurations "
            "WHERE pricing_catalog_context_json IS NULL"
        ),
        "update": (
            "UPDATE optimizer_configurations "
            "SET pricing_catalog_context_json = ? "
            "WHERE id = ? AND pricing_catalog_context_json IS NULL"
        ),
    },
)


def migrate(database_url: str | None = None) -> list[str]:
    """Add context columns and backfill only structurally trustworthy results."""

    db_path = _resolve_db_path(database_url)
    actions: list[str] = []
    with sqlite3.connect(db_path) as connection:
        for target in MIGRATION_TARGETS:
            table_name = target["table"]
            if not _table_exists(connection, table_name):
                actions.append(f"skip missing table: {table_name}")
                continue
            if "pricing_catalog_context_json" not in _columns(
                connection,
                table_name,
            ):
                connection.execute(target["alter"])
                actions.append(
                    f"added: {table_name}.pricing_catalog_context_json"
                )
            else:
                actions.append(
                    f"exists: {table_name}.pricing_catalog_context_json"
                )
            actions.extend(
                _backfill_contexts(
                    connection,
                    table_name,
                    target["result_column"],
                    target["select"],
                    target["update"],
                )
            )
    return actions


def _backfill_contexts(
    connection: sqlite3.Connection,
    table_name: str,
    result_column: str,
    select_statement: str,
    update_statement: str,
) -> list[str]:
    if result_column not in _columns(connection, table_name):
        return [f"skip missing column: {table_name}.{result_column}"]

    updated = 0
    rows = connection.execute(select_statement).fetchall()
    for row_id, raw_result in rows:
        context = _trusted_context(raw_result)
        if context is None:
            continue
        connection.execute(
            update_statement,
            (context.canonical_json(), row_id),
        )
        updated += 1
    return [f"backfilled: {table_name}={updated}"]


def _trusted_context(raw_result: Any) -> PricingCatalogContext | None:
    if not isinstance(raw_result, str) or not raw_result:
        return None
    try:
        result = json.loads(raw_result)
    except json.JSONDecodeError:
        return None
    if not isinstance(result, dict):
        return None
    try:
        return PricingCatalogContext.model_validate(result.get("pricingCatalogs"))
    except ValidationError:
        return None


def _resolve_db_path(database_url: str | None) -> str:
    resolved = database_url or os.environ.get(
        "DATABASE_URL",
        "sqlite:///./management.db",
    )
    if not resolved.startswith("sqlite:///"):
        raise ValueError("Pricing catalog context migration requires SQLite.")
    return resolved.removeprefix("sqlite:///")


def _table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def _columns(connection: sqlite3.Connection, table_name: str) -> set[str]:
    return {
        str(row[1])
        for row in connection.execute(f"PRAGMA table_info({table_name})")
    }


if __name__ == "__main__":
    migrate()
