"""Ordered, journaled migration runner for the SQLite thesis database."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from importlib import import_module
import logging
import os
import sqlite3
from typing import Iterator

from migrations.ensure_current_schema_columns import resolve_sqlite_path


logger = logging.getLogger(__name__)

@dataclass(frozen=True)
class Migration:
    migration_id: str
    module: str


MIGRATIONS: tuple[Migration, ...] = (
    Migration("001_deployment_lifecycle", "migrations.add_deployment_lifecycle_columns"),
    Migration("002_error_tracking", "migrations.add_error_tracking_columns"),
    Migration("003_deployment_sessions", "migrations.add_deployment_session_columns"),
    Migration("004_l4_l5_configuration", "migrations.add_l4_l5_columns"),
    Migration("005_function_requirements", "migrations.add_requirements_columns"),
    Migration("006_current_schema_columns", "migrations.ensure_current_schema_columns"),
    Migration("007_cloud_connections", "migrations.add_cloud_connections_table"),
    Migration("008_cloud_connection_bindings", "migrations.add_twin_cloud_connection_bindings"),
    Migration(
        "009_cloud_connection_permission_set",
        "migrations.add_cloud_connection_permission_set_version",
    ),
    Migration("010_cloud_connection_purpose", "migrations.add_cloud_connection_purpose"),
    Migration("011_deployment_preflight", "migrations.add_deployment_preflight_cache"),
    Migration(
        "012_deployment_operation_state",
        "migrations.add_deployment_operation_state_columns",
    ),
    Migration("013_pricing_refresh_runs", "migrations.add_pricing_refresh_runs"),
    Migration("014_pricing_review", "migrations.add_pricing_review_tables"),
    Migration("015_cost_calculation_runs", "migrations.add_cost_calculation_runs"),
    Migration("016_disable_legacy_credentials", "migrations.disable_legacy_twin_credentials"),
)


def run_migrations(database_url: str) -> list[str]:
    """Apply every pending SQLite migration and return the applied IDs."""
    if not database_url.startswith("sqlite:///"):
        logger.info("Skipping SQLite migrations for non-SQLite database")
        return []

    database_path = resolve_sqlite_path(database_url)
    database_path.parent.mkdir(parents=True, exist_ok=True)
    _ensure_journal(database_path)
    applied = _applied_migrations(database_path)
    completed: list[str] = []

    with _database_url(database_url):
        for migration in MIGRATIONS:
            if migration.migration_id in applied:
                continue
            logger.info("Applying database migration %s", migration.migration_id)
            migrate = getattr(import_module(migration.module), "migrate")
            migrate()
            _record_migration(database_path, migration.migration_id)
            completed.append(migration.migration_id)

    return completed


def _ensure_journal(database_path) -> None:
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                migration_id VARCHAR PRIMARY KEY,
                applied_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )


def _applied_migrations(database_path) -> set[str]:
    with sqlite3.connect(database_path) as connection:
        return {
            row[0]
            for row in connection.execute(
                "SELECT migration_id FROM schema_migrations"
            )
        }


def _record_migration(database_path, migration_id: str) -> None:
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "INSERT INTO schema_migrations (migration_id) VALUES (?)",
            (migration_id,),
        )


@contextmanager
def _database_url(database_url: str) -> Iterator[None]:
    previous = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = database_url
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous
