"""One-way migration tests for removed file-version storage."""

from __future__ import annotations

import sqlite3

from migrations.drop_file_versions import migrate


def test_migration_drops_unused_file_version_table(tmp_path):
    database = tmp_path / "management.db"
    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE TABLE file_versions "
            "(id VARCHAR PRIMARY KEY, twin_id VARCHAR, file_path VARCHAR, version INTEGER)"
        )
        connection.execute(
            "INSERT INTO file_versions VALUES ('one', 'twin', 'config.json', 1)"
        )

    assert migrate(f"sqlite:///{database}") == ["dropped: file_versions"]
    assert migrate(f"sqlite:///{database}") == ["absent: file_versions"]
