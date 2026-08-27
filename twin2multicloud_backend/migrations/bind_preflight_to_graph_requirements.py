"""Bind cached deployment preflight evidence to one resolved graph inspection."""

from __future__ import annotations

import os
import sqlite3

from migrations.ensure_current_schema_columns import resolve_sqlite_path


def migrate(database_url: str | None = None) -> list[str]:
    path = resolve_sqlite_path(database_url or os.environ.get("DATABASE_URL"))
    connection = sqlite3.connect(path)
    try:
        existing = {
            row[1]
            for row in connection.execute(
                "PRAGMA table_info(deployment_preflight_cache)"
            )
        }
        actions: list[str] = []
        columns = {
            "architecture_digest": "VARCHAR(71)",
            "graph_digest": "VARCHAR(71)",
            "requirements_digest": "VARCHAR(71)",
            "requirements_json": "TEXT NOT NULL DEFAULT '[]'",
            "preparation_plan_json": "TEXT NOT NULL DEFAULT '{}'",
            "completed_preparation_actions_json": "TEXT NOT NULL DEFAULT '[]'",
            "manual_acknowledgements_json": "TEXT NOT NULL DEFAULT '[]'",
        }
        for name, declaration in columns.items():
            if name in existing:
                continue
            connection.execute(
                f"ALTER TABLE deployment_preflight_cache ADD COLUMN {name} {declaration}"
            )
            actions.append(f"added: deployment_preflight_cache.{name}")
        connection.commit()
        return actions
    finally:
        connection.close()


if __name__ == "__main__":
    for action in migrate():
        print(action)
