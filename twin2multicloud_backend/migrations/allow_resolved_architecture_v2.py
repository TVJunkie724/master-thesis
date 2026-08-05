"""Allow immutable native v2 resolved-architecture records."""

from __future__ import annotations

import os
import sqlite3

from migrations.ensure_current_schema_columns import resolve_sqlite_path


TABLE = "resolved_twin_architectures"


def migrate(database_url: str | None = None) -> list[str]:
    path = resolve_sqlite_path(database_url or os.environ.get("DATABASE_URL"))
    connection = sqlite3.connect(path)
    try:
        existing = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?",
            (TABLE,),
        ).fetchone()
        if existing is None:
            return ["skipped: resolved architecture table unavailable"]
        if "native_v2" in str(existing[0]):
            return ["ensured: resolved architecture v2 origin"]

        connection.execute("PRAGMA foreign_keys=OFF")
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            "DROP TRIGGER IF EXISTS trg_resolved_twin_architectures_immutable"
        )
        connection.execute(
            """
            CREATE TABLE resolved_twin_architectures_v2 (
                id VARCHAR PRIMARY KEY,
                calculation_run_id VARCHAR NOT NULL UNIQUE
                    REFERENCES cost_calculation_runs(id) ON DELETE CASCADE,
                twin_id VARCHAR NOT NULL
                    REFERENCES digital_twins(id) ON DELETE CASCADE,
                user_id VARCHAR NOT NULL REFERENCES users(id),
                schema_version VARCHAR(64) NOT NULL,
                profile_id VARCHAR(128) NOT NULL,
                profile_version VARCHAR(32) NOT NULL,
                profile_digest VARCHAR(71) NOT NULL,
                optimization_bundle_digest VARCHAR(71) NOT NULL,
                workload_contract_id VARCHAR(128) NOT NULL,
                workload_contract_version VARCHAR(32) NOT NULL,
                workload_digest VARCHAR(71) NOT NULL,
                deployment_specification_version VARCHAR(64) NOT NULL,
                deployment_specification_digest VARCHAR(71) NOT NULL,
                total_monthly_cost VARCHAR(128) NOT NULL,
                currency VARCHAR(3) NOT NULL,
                functional_completeness_status VARCHAR(32) NOT NULL
                    CHECK (functional_completeness_status = 'complete'),
                canonical_json TEXT NOT NULL,
                content_digest VARCHAR(71) NOT NULL UNIQUE,
                origin VARCHAR(32) NOT NULL CHECK (
                    origin IN (
                        'native_v1', 'reconstructed_v1', 'native_v2'
                    )
                ),
                created_at DATETIME NOT NULL
            )
            """
        )
        connection.execute(
            """
            INSERT INTO resolved_twin_architectures_v2 (
                id, calculation_run_id, twin_id, user_id, schema_version,
                profile_id, profile_version, profile_digest,
                optimization_bundle_digest, workload_contract_id,
                workload_contract_version, workload_digest,
                deployment_specification_version,
                deployment_specification_digest, total_monthly_cost,
                currency, functional_completeness_status, canonical_json,
                content_digest, origin, created_at
            )
            SELECT
                id, calculation_run_id, twin_id, user_id, schema_version,
                profile_id, profile_version, profile_digest,
                optimization_bundle_digest, workload_contract_id,
                workload_contract_version, workload_digest,
                deployment_specification_version,
                deployment_specification_digest, total_monthly_cost,
                currency, functional_completeness_status, canonical_json,
                content_digest, origin, created_at
            FROM resolved_twin_architectures
            """
        )
        connection.execute("DROP TABLE resolved_twin_architectures")
        connection.execute(
            "ALTER TABLE resolved_twin_architectures_v2 "
            "RENAME TO resolved_twin_architectures"
        )
        connection.execute(
            """
            CREATE INDEX ix_resolved_architecture_owner_twin
            ON resolved_twin_architectures (user_id, twin_id)
            """
        )
        connection.execute(
            """
            CREATE INDEX ix_resolved_architecture_content_digest
            ON resolved_twin_architectures (content_digest)
            """
        )
        connection.execute(
            """
            CREATE TRIGGER trg_resolved_twin_architectures_immutable
            BEFORE UPDATE ON resolved_twin_architectures
            FOR EACH ROW
            BEGIN
                SELECT RAISE(ABORT, 'resolved architecture is immutable');
            END
            """
        )
        violations = connection.execute("PRAGMA foreign_key_check").fetchall()
        if violations:
            raise RuntimeError(
                "Resolved architecture v2 migration created foreign-key drift"
            )
        connection.commit()
        connection.execute("PRAGMA foreign_keys=ON")
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
    return ["ensured: resolved architecture v2 origin"]


if __name__ == "__main__":
    for action in migrate():
        print(action)
