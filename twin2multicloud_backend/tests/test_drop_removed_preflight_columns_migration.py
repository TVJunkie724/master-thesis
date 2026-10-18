"""Preserve cached graph evidence when upgrading the retired permission schema."""

import sqlite3

import pytest

from migrations.drop_removed_preflight_columns import migrate


def _legacy_database(path):
    with sqlite3.connect(path) as connection:
        connection.executescript("""
            CREATE TABLE twins (id TEXT PRIMARY KEY);
            INSERT INTO twins VALUES ('twin-1');
            CREATE TABLE deployment_preflight_cache (
                id TEXT PRIMARY KEY,
                twin_id TEXT REFERENCES twins(id), provider TEXT NOT NULL,
                checks_json TEXT NOT NULL, graph_digest TEXT NOT NULL,
                supplied_permission_set_version TEXT,
                expected_permission_set_version TEXT NOT NULL,
                UNIQUE(twin_id, provider)
            );
            CREATE INDEX ix_preflight_provider ON deployment_preflight_cache(provider);
            INSERT INTO deployment_preflight_cache VALUES (
                'cache-1', 'twin-1', 'aws', '[{"passed":true}]', 'graph-1',
                'old-supplied', 'old-expected'
            );
        """)


def test_upgrade_preserves_evidence_keys_and_indexes_and_is_idempotent(tmp_path):
    path = tmp_path / "legacy.db"
    _legacy_database(path)
    assert all(action.startswith("dropped:") for action in migrate(f"sqlite:///{path}"))
    assert all(action.startswith("absent:") for action in migrate(f"sqlite:///{path}"))
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT * FROM deployment_preflight_cache").fetchall() == [
            ("cache-1", "twin-1", "aws", '[{"passed":true}]', "graph-1")
        ]
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        assert "ix_preflight_provider" in {
            row[1] for row in connection.execute("PRAGMA index_list(deployment_preflight_cache)")
        }
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO deployment_preflight_cache VALUES (?, ?, ?, ?, ?)",
                ("cache-2", "twin-1", "aws", "[]", "graph-2"),
            )
        connection.execute(
            "INSERT INTO deployment_preflight_cache VALUES (?, ?, ?, ?, ?)",
            ("cache-2", "twin-1", "azure", "[]", "graph-2"),
        )


def test_unexpected_dependency_rolls_back_all_column_removals(tmp_path):
    path = tmp_path / "legacy.db"
    _legacy_database(path)
    with sqlite3.connect(path) as connection:
        connection.execute(
            "CREATE INDEX unexpected ON deployment_preflight_cache(expected_permission_set_version)"
        )
    with pytest.raises(sqlite3.OperationalError):
        migrate(f"sqlite:///{path}")
    with sqlite3.connect(path) as connection:
        assert {
            "supplied_permission_set_version", "expected_permission_set_version"
        } <= {
            row[1] for row in connection.execute("PRAGMA table_info(deployment_preflight_cache)")
        }
        assert connection.execute("SELECT count(*) FROM deployment_preflight_cache").fetchone() == (1,)


def test_missing_table_is_safe(tmp_path):
    assert migrate(f"sqlite:///{tmp_path / 'empty.db'}") == [
        "skip missing table: deployment_preflight_cache"
    ]
