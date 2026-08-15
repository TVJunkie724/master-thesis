"""Create immutable user-function v1 persistence and import legacy source safely."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import uuid


TABLES = (
    "user_function_artifacts",
    "user_function_artifact_files",
    "user_function_artifact_dependencies",
    "twin_extension_bindings",
    "user_function_audit_events",
)


def migrate(database_url: str | None = None) -> list[str]:
    path = _database_path(database_url)
    actions: list[str] = []
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        _create_tables(connection)
        _create_indexes(connection)
        _create_immutability_triggers(connection)
        imported = _import_legacy_artifacts(connection)
        actions.extend(f"ensured: {table}" for table in TABLES)
        actions.append(f"imported legacy artifacts: {imported}")
    return actions


def _database_path(database_url: str | None) -> str:
    value = database_url or os.environ.get("DATABASE_URL", "sqlite:///./management.db")
    if not value.startswith("sqlite:///"):
        raise ValueError("User-function extension migration requires SQLite.")
    return value.removeprefix("sqlite:///")


def _create_tables(connection: sqlite3.Connection) -> None:
    statements = (
        """
        CREATE TABLE IF NOT EXISTS user_function_artifacts (
            id VARCHAR PRIMARY KEY,
            user_id VARCHAR NOT NULL REFERENCES users(id),
            schema_version VARCHAR NOT NULL,
            artifact_state VARCHAR NOT NULL,
            artifact_digest VARCHAR(71) NOT NULL,
            slot_id VARCHAR(128) NOT NULL,
            slot_version VARCHAR(10) NOT NULL,
            runtime_id VARCHAR(32) NOT NULL,
            manifest_json TEXT,
            configuration_json TEXT NOT NULL DEFAULT '{}',
            declared_capabilities_json TEXT NOT NULL DEFAULT '[]',
            validator_version VARCHAR(64),
            created_by VARCHAR NOT NULL REFERENCES users(id),
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT uq_user_function_artifact_owner_digest
                UNIQUE(user_id, artifact_digest)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS user_function_artifact_files (
            id VARCHAR PRIMARY KEY,
            artifact_id VARCHAR NOT NULL
                REFERENCES user_function_artifacts(id) ON DELETE CASCADE,
            relative_path VARCHAR(240) NOT NULL,
            content_text TEXT NOT NULL,
            content_digest VARCHAR(71) NOT NULL,
            size_bytes INTEGER NOT NULL,
            CONSTRAINT uq_user_function_artifact_file_path
                UNIQUE(artifact_id, relative_path)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS user_function_artifact_dependencies (
            id VARCHAR PRIMARY KEY,
            artifact_id VARCHAR NOT NULL
                REFERENCES user_function_artifacts(id) ON DELETE CASCADE,
            name VARCHAR(128) NOT NULL,
            version VARCHAR(64) NOT NULL,
            hashes_json TEXT NOT NULL,
            policy_result VARCHAR(32) NOT NULL,
            CONSTRAINT uq_user_function_artifact_dependency_name
                UNIQUE(artifact_id, name)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS twin_extension_bindings (
            id VARCHAR PRIMARY KEY,
            user_id VARCHAR NOT NULL REFERENCES users(id),
            twin_id VARCHAR NOT NULL
                REFERENCES digital_twins(id) ON DELETE CASCADE,
            slot_id VARCHAR(128) NOT NULL,
            slot_version VARCHAR(10) NOT NULL,
            artifact_id VARCHAR NOT NULL REFERENCES user_function_artifacts(id),
            binding_digest VARCHAR(71) NOT NULL,
            active BOOLEAN NOT NULL DEFAULT 1,
            revision INTEGER NOT NULL DEFAULT 1,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            unbound_at DATETIME
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS user_function_audit_events (
            id VARCHAR PRIMARY KEY,
            user_id VARCHAR NOT NULL REFERENCES users(id),
            action VARCHAR(64) NOT NULL,
            outcome VARCHAR(32) NOT NULL,
            artifact_id VARCHAR,
            twin_id VARCHAR,
            slot_id VARCHAR(128),
            correlation_id VARCHAR(128) NOT NULL,
            error_code VARCHAR(64),
            occurred_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """,
    )
    for statement in statements:
        connection.execute(statement)


def _create_indexes(connection: sqlite3.Connection) -> None:
    statements = (
        "CREATE INDEX IF NOT EXISTS ix_user_function_artifacts_owner_time "
        "ON user_function_artifacts(user_id, created_at)",
        "CREATE INDEX IF NOT EXISTS ix_user_function_artifacts_slot "
        "ON user_function_artifacts(user_id, slot_id, slot_version)",
        "CREATE INDEX IF NOT EXISTS ix_user_function_artifact_files_artifact "
        "ON user_function_artifact_files(artifact_id)",
        "CREATE INDEX IF NOT EXISTS ix_user_function_artifact_dependencies_artifact "
        "ON user_function_artifact_dependencies(artifact_id)",
        "CREATE INDEX IF NOT EXISTS ix_twin_extension_bindings_owner_twin "
        "ON twin_extension_bindings(user_id, twin_id, created_at)",
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_twin_extension_bindings_one_active "
        "ON twin_extension_bindings(twin_id, slot_id, slot_version) WHERE active = 1",
        "CREATE INDEX IF NOT EXISTS ix_user_function_audit_owner_time "
        "ON user_function_audit_events(user_id, occurred_at)",
        "CREATE INDEX IF NOT EXISTS ix_user_function_audit_correlation "
        "ON user_function_audit_events(correlation_id)",
    )
    for statement in statements:
        connection.execute(statement)


def _create_immutability_triggers(connection: sqlite3.Connection) -> None:
    for table in (
        "user_function_artifacts",
        "user_function_artifact_files",
        "user_function_artifact_dependencies",
        "user_function_audit_events",
    ):
        connection.execute(
            f"""
            CREATE TRIGGER IF NOT EXISTS trg_{table}_immutable_update
            BEFORE UPDATE ON {table}
            BEGIN
                SELECT RAISE(ABORT, '{table} is immutable');
            END
            """
        )
        connection.execute(
            f"""
            CREATE TRIGGER IF NOT EXISTS trg_{table}_immutable_delete
            BEFORE DELETE ON {table}
            BEGIN
                SELECT RAISE(ABORT, '{table} is immutable');
            END
            """
        )


def _import_legacy_artifacts(connection: sqlite3.Connection) -> int:
    if not _table_exists(connection, "deployer_configurations"):
        return 0
    rows = connection.execute(
        """
        SELECT dc.id, dc.twin_id, dt.user_id,
               dc.processor_contents, dc.processor_requirements,
               dc.event_feedback_content, dc.event_feedback_requirements,
               dc.event_action_contents, dc.event_action_requirements,
               dc.created_at
        FROM deployer_configurations AS dc
        JOIN digital_twins AS dt ON dt.id = dc.twin_id
        """
    ).fetchall()
    imported = 0
    for row in rows:
        (
            _config_id,
            twin_id,
            user_id,
            processor_contents,
            processor_requirements,
            feedback_content,
            feedback_requirements,
            action_contents,
            action_requirements,
            created_at,
        ) = row
        processors = _json_map(processor_contents)
        processor_locks = _json_map(processor_requirements)
        for name, source in sorted(processors.items()):
            imported += _insert_legacy(
                connection,
                user_id=user_id,
                twin_id=twin_id,
                slot_id=f"legacy.processor.{_stable_fragment(name)}",
                source=source,
                requirements=processor_locks.get(name),
                created_at=created_at,
            )
        actions = _json_map(action_contents)
        action_locks = _json_map(action_requirements)
        for name, source in sorted(actions.items()):
            imported += _insert_legacy(
                connection,
                user_id=user_id,
                twin_id=twin_id,
                slot_id=f"legacy.event-action.{_stable_fragment(name)}",
                source=source,
                requirements=action_locks.get(name),
                created_at=created_at,
            )
        if isinstance(feedback_content, str) and feedback_content:
            imported += _insert_legacy(
                connection,
                user_id=user_id,
                twin_id=twin_id,
                slot_id="legacy.event-feedback",
                source=feedback_content,
                requirements=feedback_requirements,
                created_at=created_at,
            )
    return imported


def _insert_legacy(
    connection: sqlite3.Connection,
    *,
    user_id: str,
    twin_id: str,
    slot_id: str,
    source: object,
    requirements: object,
    created_at: object,
) -> int:
    if not isinstance(source, str) or not source:
        return 0
    source = _normalize(source)
    files = [("process.py", source)]
    if isinstance(requirements, str) and requirements:
        files.append(("requirements.txt", _normalize(requirements)))
    digest = _digest_json(
        {
            "schema_version": "legacy-user-function-artifact.v0",
            "twin_id": twin_id,
            "slot_id": slot_id,
            "files": [
                {"path": path, "digest": _digest_text(content)}
                for path, content in files
            ],
        }
    )
    artifact_id = str(
        uuid.uuid5(
            uuid.UUID("a407c746-63ce-4e13-91fe-bc6f92802419"),
            f"{user_id}:{digest}",
        )
    )
    inserted = connection.execute(
        """
        INSERT OR IGNORE INTO user_function_artifacts (
            id, user_id, schema_version, artifact_state, artifact_digest,
            slot_id, slot_version, runtime_id, manifest_json,
            configuration_json, declared_capabilities_json, validator_version,
            created_by, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, '{}', '[]', NULL, ?, ?)
        """,
        (
            artifact_id,
            user_id,
            "legacy-user-function-artifact.v0",
            "legacy_unvalidated",
            digest,
            slot_id,
            "0",
            "python311",
            user_id,
            created_at or "1970-01-01T00:00:00Z",
        ),
    ).rowcount
    if not inserted:
        return 0
    for path, content in files:
        connection.execute(
            """
            INSERT INTO user_function_artifact_files (
                id, artifact_id, relative_path, content_text,
                content_digest, size_bytes
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid.uuid4()),
                artifact_id,
                path,
                content,
                _digest_text(content),
                len(content.encode("utf-8")),
            ),
        )
    return 1


def _table_exists(connection: sqlite3.Connection, name: str) -> bool:
    return (
        connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (name,),
        ).fetchone()
        is not None
    )


def _json_map(value: object) -> dict[str, object]:
    if not isinstance(value, str) or not value:
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _stable_fragment(value: object) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", str(value).lower()).strip("-")
    return normalized[:64] or "unnamed"


def _normalize(value: str) -> str:
    return value.replace("\r\n", "\n").replace("\r", "\n")


def _digest_text(value: str) -> str:
    return f"sha256:{hashlib.sha256(value.encode('utf-8')).hexdigest()}"


def _digest_json(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


if __name__ == "__main__":
    migrate()
