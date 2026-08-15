"""Transactional and conservative migration 022 coverage."""

from __future__ import annotations

import json
from pathlib import Path
import sqlite3

import pytest

from migrations import add_resolved_twin_architecture as migration
from migrations import allow_resolved_architecture_v2 as v2_migration
from tests.architecture_test_data import (
    RUN_ID,
    calculation_result_and_contracts,
    linked_architecture_fixture_documents,
)
from tests.pricing_catalog_test_data import catalog_context


def _create_populated_database(
    path: Path,
    provider: str | None = None,
) -> None:
    result, specification, architecture = calculation_result_and_contracts(
        provider
    )
    context = catalog_context()
    calculation_path = result["calculationResult"]
    result["resolvedDeploymentSpecification"] = specification
    result["resolvedTwinArchitecture"] = architecture
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            PRAGMA foreign_keys=ON;
            CREATE TABLE users (
                id VARCHAR PRIMARY KEY
            );
            CREATE TABLE digital_twins (
                id VARCHAR PRIMARY KEY,
                user_id VARCHAR NOT NULL REFERENCES users(id)
            );
            CREATE TABLE optimizer_configurations (
                id VARCHAR PRIMARY KEY,
                twin_id VARCHAR NOT NULL REFERENCES digital_twins(id),
                cheapest_l1 VARCHAR,
                cheapest_l2 VARCHAR,
                cheapest_l3_hot VARCHAR,
                cheapest_l3_cool VARCHAR,
                cheapest_l3_archive VARCHAR,
                cheapest_l4 VARCHAR,
                cheapest_l5 VARCHAR
            );
            CREATE TABLE cost_calculation_runs (
                id VARCHAR PRIMARY KEY,
                twin_id VARCHAR NOT NULL REFERENCES digital_twins(id),
                user_id VARCHAR NOT NULL REFERENCES users(id),
                optimizer_config_id VARCHAR
                    REFERENCES optimizer_configurations(id),
                result_summary_json TEXT,
                cheapest_path_json TEXT,
                total_monthly_cost FLOAT,
                currency VARCHAR,
                pricing_catalog_context_json TEXT,
                deployment_specification_json TEXT,
                deployment_specification_digest VARCHAR(71),
                deployment_specification_version VARCHAR(64),
                selected_for_deployment_at DATETIME
            );
            CREATE TABLE user_function_artifacts (
                id VARCHAR PRIMARY KEY,
                artifact_digest VARCHAR(71) NOT NULL,
                configuration_json TEXT NOT NULL,
                validator_version VARCHAR(64),
                artifact_state VARCHAR NOT NULL
            );
            CREATE TABLE twin_extension_bindings (
                id VARCHAR PRIMARY KEY,
                user_id VARCHAR NOT NULL,
                twin_id VARCHAR NOT NULL,
                slot_id VARCHAR NOT NULL,
                slot_version VARCHAR NOT NULL,
                artifact_id VARCHAR NOT NULL,
                active BOOLEAN NOT NULL
            );
            INSERT INTO users(id) VALUES ('owner');
            INSERT INTO digital_twins(id, user_id)
            VALUES ('twin', 'owner');
            """
        )
        connection.execute(
            """
            INSERT INTO optimizer_configurations (
                id, twin_id, cheapest_l1, cheapest_l2,
                cheapest_l3_hot, cheapest_l3_cool,
                cheapest_l3_archive, cheapest_l4, cheapest_l5
            ) VALUES ('optimizer', 'twin', ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                calculation_path["L1"],
                calculation_path["L2"],
                calculation_path["L3"]["Hot"],
                calculation_path["L3"]["Cool"],
                calculation_path["L3"]["Archive"],
                calculation_path["L4"],
                calculation_path["L5"],
            ),
        )
        extension = architecture["extension_bindings"][0]
        connection.execute(
            """
            INSERT INTO user_function_artifacts (
                id, artifact_digest, configuration_json,
                validator_version, artifact_state
            ) VALUES (?, ?, '{}', ?, 'valid')
            """,
            (
                extension["artifact_id"],
                extension["artifact_digest"],
                extension["validation_contract_version"],
            ),
        )
        connection.execute(
            """
            INSERT INTO twin_extension_bindings (
                id, user_id, twin_id, slot_id, slot_version,
                artifact_id, active
            ) VALUES ('binding', 'owner', 'twin', ?, ?, ?, 1)
            """,
            (
                extension["slot_id"],
                extension["slot_version"],
                extension["artifact_id"],
            ),
        )
        connection.execute(
            """
            INSERT INTO cost_calculation_runs (
                id, twin_id, user_id, optimizer_config_id, result_summary_json,
                cheapest_path_json, total_monthly_cost, currency,
                pricing_catalog_context_json,
                deployment_specification_json,
                deployment_specification_digest,
                deployment_specification_version,
                selected_for_deployment_at
            ) VALUES (
                ?, 'twin', 'owner', 'optimizer', ?, ?, 7.6, 'USD',
                ?, ?, ?, ?, ?
            )
            """,
            (
                RUN_ID,
                json.dumps(result),
                json.dumps(
                    {
                        "l1": calculation_path["L1"],
                        "l2": calculation_path["L2"],
                        "l3_hot": calculation_path["L3"]["Hot"],
                        "l3_cool": calculation_path["L3"]["Cool"],
                        "l3_archive": calculation_path["L3"]["Archive"],
                        "l4": calculation_path["L4"],
                        "l5": calculation_path["L5"],
                    }
                ),
                json.dumps(
                    context.model_dump(mode="json", by_alias=True)
                ),
                json.dumps(specification),
                specification["digest"],
                specification["schema_version"],
                "2026-07-19T12:00:00+00:00",
            ),
        )
        connection.execute(
            """
            INSERT INTO cost_calculation_runs (
                id, twin_id, user_id, currency, selected_for_deployment_at
            ) VALUES (
                '018f0f5e-7b5e-7b2d-9f0b-7f66c2a88aff',
                'twin',
                'owner',
                'USD',
                '2026-07-19T13:00:00+00:00'
            )
            """
        )


def test_empty_migration_is_idempotent(tmp_path):
    path = tmp_path / "empty.db"

    first = migration.migrate(f"sqlite:///{path}")
    second = migration.migrate(f"sqlite:///{path}")

    assert "ensured: architecture tables" in first
    assert "backfilled: architecture selections=0" in second
    with sqlite3.connect(path) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM twin_architecture_selections"
        ).fetchone() == (0,)


def test_populated_migration_reconstructs_only_sufficient_evidence(
    tmp_path,
    monkeypatch,
):
    path = tmp_path / "populated.db"
    _create_populated_database(path)
    linked = linked_architecture_fixture_documents()
    monkeypatch.setattr(migration, "_provider_documents", lambda *_: linked[1:3])
    monkeypatch.setattr(migration, "_catalog_documents", lambda: (linked[3],))

    first = migration.migrate(f"sqlite:///{path}")
    second = migration.migrate(f"sqlite:///{path}")

    assert "classified: reconstructed=1, legacy_not_resolvable=1" in first
    assert "classified: reconstructed=0, legacy_not_resolvable=0" in second
    with sqlite3.connect(path) as connection:
        selection = connection.execute(
            """
            SELECT profile_id, profile_version, revision
            FROM twin_architecture_selections
            """
        ).fetchone()
        assert selection == ("five-layer-baseline", "1", 1)
        statuses = dict(
            connection.execute(
                """
                SELECT id, architecture_compatibility_status
                FROM cost_calculation_runs
                """
            )
        )
        assert statuses[RUN_ID] == "ready"
        assert (
            statuses["018f0f5e-7b5e-7b2d-9f0b-7f66c2a88aff"]
            == "legacy_not_resolvable"
        )
        assert connection.execute(
            """
            SELECT selected_for_deployment_at
            FROM cost_calculation_runs
            WHERE id = '018f0f5e-7b5e-7b2d-9f0b-7f66c2a88aff'
            """
        ).fetchone() == (None,)
        assert connection.execute(
            "SELECT COUNT(*) FROM resolved_twin_architectures"
        ).fetchone() == (1,)
        assert connection.execute(
            "SELECT COUNT(*) FROM resolved_architecture_component_assignments"
        ).fetchone() == (7,)
        assert connection.execute(
            "SELECT COUNT(*) FROM resolved_architecture_edges"
        ).fetchone() == (6,)
        assert connection.execute(
            "SELECT COUNT(*) FROM architecture_audit_events"
        ).fetchone() == (3,)
        assert connection.execute(
            """
            SELECT outcome
            FROM architecture_audit_events
            WHERE action = 'profile.select'
            """
        ).fetchone() == ("migrated",)
    assert migration.ARCHITECTURE_MIGRATION_METRICS[
        ("reconstructed", "1")
    ] >= 1
    assert migration.ARCHITECTURE_MIGRATION_METRICS[
        ("legacy_not_resolvable", "1")
    ] >= 1


@pytest.mark.parametrize("provider", ("aws", "azure"))
def test_populated_migration_reconstructs_single_provider_runs(
    tmp_path,
    monkeypatch,
    provider,
):
    path = tmp_path / f"populated-{provider}.db"
    _create_populated_database(path, provider)
    linked = linked_architecture_fixture_documents()
    monkeypatch.setattr(migration, "_provider_documents", lambda *_: linked[1:3])
    monkeypatch.setattr(migration, "_catalog_documents", lambda: (linked[3],))

    actions = migration.migrate(f"sqlite:///{path}")

    assert "classified: reconstructed=1, legacy_not_resolvable=1" in actions
    with sqlite3.connect(path) as connection:
        assert set(
            row[0]
            for row in connection.execute(
                """
                SELECT provider
                FROM resolved_architecture_component_assignments
                """
            )
        ) == {provider}
        assert connection.execute(
            "SELECT COUNT(*) FROM resolved_architecture_edges"
        ).fetchone() == (6,)


def test_migration_immutability_triggers_reject_updates_and_audit_delete(
    tmp_path,
    monkeypatch,
):
    path = tmp_path / "immutable.db"
    _create_populated_database(path)
    linked = linked_architecture_fixture_documents()
    monkeypatch.setattr(migration, "_provider_documents", lambda *_: linked[1:3])
    monkeypatch.setattr(migration, "_catalog_documents", lambda: (linked[3],))
    migration.migrate(f"sqlite:///{path}")

    with sqlite3.connect(path) as connection:
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            connection.execute(
                """
                UPDATE cost_calculation_runs
                SET architecture_compatibility_status = 'ready'
                WHERE id = ?
                """,
                ("018f0f5e-7b5e-7b2d-9f0b-7f66c2a88aff",),
            )
        connection.rollback()
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            connection.execute(
                """
                UPDATE resolved_twin_architectures
                SET currency = 'EUR'
                WHERE calculation_run_id = ?
                """,
                (RUN_ID,),
            )
        connection.rollback()
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute(
                "DELETE FROM architecture_audit_events"
            )


@pytest.mark.parametrize(
    "corruption",
    (
        "incomplete_path",
        "invalid_specification",
        "specification_digest_mismatch",
        "architecture_digest_mismatch",
        "optimization_bundle_mismatch",
        "fixed_projection_mismatch",
        "unsupported_gcp_l4",
    ),
)
def test_migration_never_fabricates_resolution_from_inconsistent_evidence(
    tmp_path,
    monkeypatch,
    corruption,
):
    path = tmp_path / f"{corruption}.db"
    _create_populated_database(path)
    linked = linked_architecture_fixture_documents()
    monkeypatch.setattr(migration, "_provider_documents", lambda *_: linked[1:3])
    monkeypatch.setattr(migration, "_catalog_documents", lambda: (linked[3],))
    with sqlite3.connect(path) as connection:
        run = connection.execute(
            """
            SELECT result_summary_json, cheapest_path_json
            FROM cost_calculation_runs
            WHERE id = ?
            """,
            (RUN_ID,),
        ).fetchone()
        result = json.loads(run[0])
        cheapest_path = json.loads(run[1])
        if corruption == "incomplete_path":
            cheapest_path.pop("l5")
            connection.execute(
                """
                UPDATE cost_calculation_runs
                SET cheapest_path_json = ?
                WHERE id = ?
                """,
                (json.dumps(cheapest_path), RUN_ID),
            )
        elif corruption == "invalid_specification":
            connection.execute(
                """
                UPDATE cost_calculation_runs
                SET deployment_specification_json = '{}'
                WHERE id = ?
                """,
                (RUN_ID,),
            )
        elif corruption == "specification_digest_mismatch":
            connection.execute(
                """
                UPDATE cost_calculation_runs
                SET deployment_specification_digest = ?
                WHERE id = ?
                """,
                ("sha256:" + ("0" * 64), RUN_ID),
            )
        elif corruption == "architecture_digest_mismatch":
            result["resolvedTwinArchitecture"]["content_digest"] = (
                "sha256:" + ("0" * 64)
            )
            connection.execute(
                """
                UPDATE cost_calculation_runs
                SET result_summary_json = ?
                WHERE id = ?
                """,
                (json.dumps(result), RUN_ID),
            )
        elif corruption == "optimization_bundle_mismatch":
            result["resolvedTwinArchitecture"]["optimization_bundle_ref"][
                "formula_set_version"
            ] = "2"
            connection.execute(
                """
                UPDATE cost_calculation_runs
                SET result_summary_json = ?
                WHERE id = ?
                """,
                (json.dumps(result), RUN_ID),
            )
        elif corruption == "fixed_projection_mismatch":
            connection.execute(
                """
                UPDATE optimizer_configurations
                SET cheapest_l2 = 'GCP'
                WHERE id = 'optimizer'
                """
            )
        else:
            invalid_fixture = json.loads(
                (
                    Path(__file__).resolve().parents[1]
                    / "src"
                    / "contracts"
                    / "generated"
                    / "resolved-deployment-specification"
                    / "v1"
                    / "fixtures"
                    / "invalid"
                    / "unsupported-gcp-l4.json"
                ).read_text(encoding="utf-8")
            )["specification"]
            connection.execute(
                """
                UPDATE cost_calculation_runs
                SET deployment_specification_json = ?,
                    deployment_specification_digest = ?,
                    deployment_specification_version = ?
                WHERE id = ?
                """,
                (
                    json.dumps(invalid_fixture),
                    invalid_fixture["digest"],
                    invalid_fixture["schema_version"],
                    RUN_ID,
                ),
            )

    migration.migrate(f"sqlite:///{path}")

    with sqlite3.connect(path) as connection:
        status = connection.execute(
            """
            SELECT architecture_compatibility_status,
                   selected_for_deployment_at
            FROM cost_calculation_runs
            WHERE id = ?
            """,
            (RUN_ID,),
        ).fetchone()
        assert status == ("legacy_not_resolvable", None)
        assert connection.execute(
            "SELECT COUNT(*) FROM resolved_twin_architectures"
        ).fetchone() == (0,)


def test_migration_failure_rolls_back_all_partial_architecture_state(
    tmp_path,
    monkeypatch,
):
    path = tmp_path / "rollback.db"
    _create_populated_database(path)
    linked = linked_architecture_fixture_documents()
    monkeypatch.setattr(migration, "_provider_documents", lambda *_: linked[1:3])
    monkeypatch.setattr(migration, "_catalog_documents", lambda: (linked[3],))
    original_insert = migration._insert_resolution

    def fail_after_resolution_insert(connection, row, architecture):
        original_insert(connection, row, architecture)
        raise RuntimeError("bounded migration failure")

    monkeypatch.setattr(migration, "_insert_resolution", fail_after_resolution_insert)
    with pytest.raises(RuntimeError, match="bounded migration failure"):
        migration.migrate(f"sqlite:///{path}")

    with sqlite3.connect(path) as connection:
        assert connection.execute(
            """
            SELECT COUNT(*)
            FROM sqlite_master
            WHERE type = 'table'
              AND name = 'resolved_twin_architectures'
            """
        ).fetchone() == (0,)
        assert connection.execute(
            "SELECT COUNT(*) FROM cost_calculation_runs"
        ).fetchone() == (2,)


def test_v2_origin_migration_preserves_v1_and_immutability(tmp_path, monkeypatch):
    path = tmp_path / "architecture-v2-origin.db"
    _create_populated_database(path)
    linked = linked_architecture_fixture_documents()
    monkeypatch.setattr(migration, "_provider_documents", lambda *_: linked[1:3])
    monkeypatch.setattr(migration, "_catalog_documents", lambda: (linked[3],))
    migration.migrate(f"sqlite:///{path}")

    expected = ["ensured: resolved architecture v2 origin"]
    assert v2_migration.migrate(f"sqlite:///{path}") == expected
    assert v2_migration.migrate(f"sqlite:///{path}") == expected

    with sqlite3.connect(path) as connection:
        existing = connection.execute(
            "SELECT * FROM resolved_twin_architectures LIMIT 1"
        ).fetchone()
        assert existing is not None
        columns = [
            item[1]
            for item in connection.execute(
                "PRAGMA table_info(resolved_twin_architectures)"
            )
        ]
        row = dict(zip(columns, existing, strict=True))
        connection.execute(
            """
            INSERT INTO cost_calculation_runs (
                id, twin_id, user_id, optimizer_config_id
            ) VALUES ('v2-run', 'twin', 'owner', 'optimizer')
            """
        )
        row.update(
            {
                "id": "v2-resolution",
                "calculation_run_id": "v2-run",
                "schema_version": "resolved-twin-architecture.v2",
                "content_digest": "sha256:" + ("f" * 64),
                "origin": "native_v2",
            }
        )
        placeholders = ", ".join("?" for _ in columns)
        connection.execute(
            f"INSERT INTO resolved_twin_architectures "
            f"({', '.join(columns)}) VALUES ({placeholders})",
            tuple(row[column] for column in columns),
        )
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            connection.execute(
                """
                UPDATE resolved_twin_architectures
                SET origin = 'native_v1'
                WHERE id = 'v2-resolution'
                """
            )
