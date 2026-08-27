"""Add profile selections and immutable resolved Twin architecture persistence."""

from __future__ import annotations

from collections import Counter
from decimal import Decimal, InvalidOperation
from datetime import datetime, timezone
import hashlib
import json
import os
import sqlite3
import uuid
from typing import Any

from src.services.architecture_contract_service import (
    ArchitectureContractService,
    ContractError,
    canonical_json,
)
from src.services.architecture_profile_service import (
    ArchitectureProfileService,
    _catalog_documents,
    _provider_documents,
)
from src.services.errors import OptimizerContractError
from src.services.pricing_catalog_context_service import (
    parse_pricing_catalog_context,
)
from src.services.resolved_deployment_specification_service import (
    validate_resolved_deployment_specification,
)


BASELINE_ID = "six-layer-eventing"
BASELINE_VERSION = "1"
ARCHITECTURE_MIGRATION_METRICS: Counter[tuple[str, str]] = Counter()
ARCHITECTURE_COLUMNS = (
    (
        "architecture_compatibility_status",
        "ALTER TABLE cost_calculation_runs ADD COLUMN "
        "architecture_compatibility_status VARCHAR(32) NOT NULL "
        "DEFAULT 'legacy_not_resolvable'",
    ),
    (
        "resolved_architecture_version",
        "ALTER TABLE cost_calculation_runs ADD COLUMN "
        "resolved_architecture_version VARCHAR(64)",
    ),
    (
        "resolved_architecture_digest",
        "ALTER TABLE cost_calculation_runs ADD COLUMN "
        "resolved_architecture_digest VARCHAR(71)",
    ),
)


def migrate(database_url: str | None = None) -> list[str]:
    """Create, backfill, conservatively classify, and protect architecture state."""

    profile = ArchitectureProfileService.get_definition(
        BASELINE_ID,
        BASELINE_VERSION,
    )
    profile_digest = profile["content_digest"]
    db_path = _resolve_db_path(database_url)
    actions: list[str] = []
    with sqlite3.connect(db_path) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("BEGIN IMMEDIATE")
        _create_tables(connection)
        actions.append("ensured: architecture tables")

        if _table_exists(connection, "cost_calculation_runs"):
            existing = _columns(connection, "cost_calculation_runs")
            for column_name, statement in ARCHITECTURE_COLUMNS:
                if column_name in existing:
                    actions.append(f"exists: cost_calculation_runs.{column_name}")
                else:
                    connection.execute(statement)
                    actions.append(f"added: cost_calculation_runs.{column_name}")
            connection.execute(
                "CREATE INDEX IF NOT EXISTS "
                "ix_cost_runs_resolved_architecture_digest "
                "ON cost_calculation_runs (resolved_architecture_digest)"
            )

        selection_count = _backfill_selections(connection, profile_digest)
        actions.append(f"backfilled: architecture selections={selection_count}")
        reconstructed, legacy = _classify_runs(connection, profile)
        ARCHITECTURE_MIGRATION_METRICS[("reconstructed", BASELINE_VERSION)] += (
            reconstructed
        )
        ARCHITECTURE_MIGRATION_METRICS[("legacy_not_resolvable", BASELINE_VERSION)] += (
            legacy
        )
        actions.append(
            f"classified: reconstructed={reconstructed}, legacy_not_resolvable={legacy}"
        )
        _create_triggers(connection)
        actions.append("ensured: architecture immutability triggers")
    return actions


def _create_tables(connection: sqlite3.Connection) -> None:
    statements = (
        """
        CREATE TABLE IF NOT EXISTS twin_architecture_selections (
            id VARCHAR PRIMARY KEY,
            twin_id VARCHAR NOT NULL UNIQUE
                REFERENCES digital_twins(id) ON DELETE CASCADE,
            user_id VARCHAR NOT NULL REFERENCES users(id),
            profile_id VARCHAR(128) NOT NULL,
            profile_version VARCHAR(32) NOT NULL,
            profile_digest VARCHAR(71) NOT NULL,
            revision INTEGER NOT NULL CHECK (revision > 0),
            selected_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            selected_by_user_id VARCHAR NOT NULL REFERENCES users(id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS resolved_twin_architectures (
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
            origin VARCHAR(32) NOT NULL
                CHECK (origin IN ('native_v1', 'reconstructed_v1')),
            created_at DATETIME NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS
        resolved_architecture_component_assignments (
            id VARCHAR PRIMARY KEY,
            resolved_architecture_id VARCHAR NOT NULL
                REFERENCES resolved_twin_architectures(id) ON DELETE CASCADE,
            assignment_id VARCHAR(128) NOT NULL,
            responsibility_id VARCHAR(128) NOT NULL,
            logical_component_id VARCHAR(128) NOT NULL,
            provider VARCHAR(16) NOT NULL,
            deployment_component_id VARCHAR(160) NOT NULL,
            deployment_component_version VARCHAR(32) NOT NULL,
            service_id VARCHAR(160) NOT NULL,
            provider_profile_id VARCHAR(160) NOT NULL,
            provider_profile_version VARCHAR(32) NOT NULL,
            provider_profile_digest VARCHAR(71) NOT NULL,
            region VARCHAR(64) NOT NULL,
            deployment_specification_component_ids_json TEXT NOT NULL,
            cost_contribution VARCHAR(128) NOT NULL,
            capability_refs_json TEXT NOT NULL,
            pricing_refs_json TEXT NOT NULL,
            formula_refs_json TEXT NOT NULL,
            evidence_refs_json TEXT NOT NULL,
            ordinal INTEGER NOT NULL,
            UNIQUE (resolved_architecture_id, assignment_id),
            UNIQUE (resolved_architecture_id, ordinal)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS resolved_architecture_edges (
            id VARCHAR PRIMARY KEY,
            resolved_architecture_id VARCHAR NOT NULL
                REFERENCES resolved_twin_architectures(id) ON DELETE CASCADE,
            resolved_edge_id VARCHAR(160) NOT NULL,
            logical_edge_id VARCHAR(160) NOT NULL,
            source_assignment_id VARCHAR(160) NOT NULL,
            source_port_id VARCHAR(160) NOT NULL,
            destination_assignment_id VARCHAR(160) NOT NULL,
            destination_port_id VARCHAR(160) NOT NULL,
            edge_implementation_id VARCHAR(200) NOT NULL,
            mechanism VARCHAR(64) NOT NULL,
            transfer_route_id VARCHAR(64) NOT NULL,
            cost_contribution VARCHAR(128) NOT NULL,
            delivery_semantics_json TEXT NOT NULL,
            binding_refs_json TEXT NOT NULL,
            trust_ref_json TEXT NOT NULL,
            observability_ref_json TEXT NOT NULL,
            formula_refs_json TEXT NOT NULL,
            evidence_refs_json TEXT NOT NULL,
            ordinal INTEGER NOT NULL,
            UNIQUE (resolved_architecture_id, resolved_edge_id),
            UNIQUE (resolved_architecture_id, ordinal)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS architecture_audit_events (
            id VARCHAR PRIMARY KEY,
            user_id VARCHAR NOT NULL REFERENCES users(id),
            action VARCHAR(64) NOT NULL,
            outcome VARCHAR(32) NOT NULL,
            profile_id VARCHAR(128),
            profile_version VARCHAR(32),
            profile_digest VARCHAR(71),
            twin_id VARCHAR,
            calculation_run_id VARCHAR,
            resolution_digest VARCHAR(71),
            result_code VARCHAR(64),
            correlation_id VARCHAR(128) NOT NULL,
            occurred_at DATETIME NOT NULL
        )
        """,
    )
    for statement in statements:
        connection.execute(statement)
    indexes = (
        "CREATE INDEX IF NOT EXISTS ix_architecture_selection_owner_twin "
        "ON twin_architecture_selections (user_id, twin_id)",
        "CREATE INDEX IF NOT EXISTS ix_resolved_architecture_owner_twin "
        "ON resolved_twin_architectures (user_id, twin_id)",
        "CREATE INDEX IF NOT EXISTS ix_resolved_architecture_content_digest "
        "ON resolved_twin_architectures (content_digest)",
        "CREATE INDEX IF NOT EXISTS ix_resolved_component_responsibility "
        "ON resolved_architecture_component_assignments "
        "(resolved_architecture_id, responsibility_id)",
        "CREATE INDEX IF NOT EXISTS ix_resolved_component_provider "
        "ON resolved_architecture_component_assignments "
        "(resolved_architecture_id, provider)",
        "CREATE INDEX IF NOT EXISTS ix_resolved_component_deployment_component "
        "ON resolved_architecture_component_assignments "
        "(deployment_component_id)",
        "CREATE INDEX IF NOT EXISTS ix_resolved_component_service "
        "ON resolved_architecture_component_assignments (service_id)",
        "CREATE INDEX IF NOT EXISTS ix_resolved_edge_logical "
        "ON resolved_architecture_edges "
        "(resolved_architecture_id, logical_edge_id)",
        "CREATE INDEX IF NOT EXISTS ix_resolved_edge_source "
        "ON resolved_architecture_edges "
        "(resolved_architecture_id, source_assignment_id)",
        "CREATE INDEX IF NOT EXISTS ix_resolved_edge_destination "
        "ON resolved_architecture_edges "
        "(resolved_architecture_id, destination_assignment_id)",
        "CREATE INDEX IF NOT EXISTS ix_architecture_audit_owner_time "
        "ON architecture_audit_events (user_id, occurred_at)",
        "CREATE INDEX IF NOT EXISTS ix_architecture_audit_correlation "
        "ON architecture_audit_events (correlation_id)",
        "CREATE INDEX IF NOT EXISTS ix_architecture_audit_twin_run "
        "ON architecture_audit_events (twin_id, calculation_run_id)",
    )
    for statement in indexes:
        connection.execute(statement)


def _backfill_selections(
    connection: sqlite3.Connection,
    profile_digest: str,
) -> int:
    if not _table_exists(connection, "digital_twins"):
        return 0
    inserted = 0
    rows = connection.execute(
        """
        SELECT id, user_id
        FROM digital_twins
        WHERE NOT EXISTS (
            SELECT 1
            FROM twin_architecture_selections selections
            WHERE selections.twin_id = digital_twins.id
        )
        ORDER BY id
        """
    ).fetchall()
    timestamp = datetime.now(timezone.utc).isoformat()
    for twin_id, user_id in rows:
        connection.execute(
            """
            INSERT INTO twin_architecture_selections (
                id, twin_id, user_id, profile_id, profile_version,
                profile_digest, revision, selected_at, updated_at,
                selected_by_user_id
            ) VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
            """,
            (
                str(uuid.uuid4()),
                twin_id,
                user_id,
                BASELINE_ID,
                BASELINE_VERSION,
                profile_digest,
                timestamp,
                timestamp,
                user_id,
            ),
        )
        connection.execute(
            """
            INSERT INTO architecture_audit_events (
                id, user_id, action, outcome, profile_id, profile_version,
                profile_digest, twin_id, correlation_id, occurred_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid.uuid4()),
                user_id,
                "profile.select",
                "migrated",
                BASELINE_ID,
                BASELINE_VERSION,
                profile_digest,
                twin_id,
                f"migration-022:selection:{twin_id}",
                timestamp,
            ),
        )
        inserted += 1
    return inserted


def _classify_runs(
    connection: sqlite3.Connection,
    profile: dict[str, Any],
) -> tuple[int, int]:
    if not _table_exists(connection, "cost_calculation_runs"):
        return 0, 0
    rows = connection.execute(
        "SELECT * FROM cost_calculation_runs ORDER BY id"
    ).fetchall()
    column_names = [
        item[1]
        for item in connection.execute("PRAGMA table_info(cost_calculation_runs)")
    ]
    reconstructed = 0
    legacy = 0
    for raw in rows:
        row = dict(zip(column_names, raw, strict=True))
        if _resolution_exists(connection, row["id"]):
            continue
        if _migration_audit_exists(connection, row["id"]):
            continue
        architecture = _reconstructable_architecture(connection, row, profile)
        if architecture is None:
            connection.execute(
                """
                UPDATE cost_calculation_runs
                SET architecture_compatibility_status = 'legacy_not_resolvable',
                    resolved_architecture_version = NULL,
                    resolved_architecture_digest = NULL,
                    selected_for_deployment_at = NULL
                WHERE id = ?
                """,
                (row["id"],),
            )
            _audit(
                connection,
                row,
                action="resolution.legacy-rejection",
                outcome="classified",
                result_code="ARCH_LEGACY_NOT_RESOLVABLE",
                profile=profile,
            )
            legacy += 1
            continue
        _insert_resolution(connection, row, architecture)
        connection.execute(
            """
            UPDATE cost_calculation_runs
            SET architecture_compatibility_status = 'ready',
                resolved_architecture_version = ?,
                resolved_architecture_digest = ?
            WHERE id = ?
            """,
            (
                architecture["schema_version"],
                architecture["content_digest"],
                row["id"],
            ),
        )
        _audit(
            connection,
            row,
            action="resolution.reconstruction",
            outcome="succeeded",
            profile=profile,
            resolution_digest=architecture["content_digest"],
        )
        reconstructed += 1
    return reconstructed, legacy


def _reconstructable_architecture(
    connection: sqlite3.Connection,
    row: dict[str, Any],
    profile: dict[str, Any],
) -> dict[str, Any] | None:
    if "status" in row and row.get("status") != "succeeded":
        return None
    required = (
        "result_summary_json",
        "cheapest_path_json",
        "pricing_catalog_context_json",
        "deployment_specification_json",
        "deployment_specification_digest",
        "deployment_specification_version",
    )
    if any(not row.get(field) for field in required):
        return None
    try:
        result = json.loads(row["result_summary_json"])
        cheapest_path = json.loads(row["cheapest_path_json"])
        specification = json.loads(row["deployment_specification_json"])
        catalog_context = parse_pricing_catalog_context(
            json.loads(row["pricing_catalog_context_json"])
        )
        validated_specification = validate_resolved_deployment_specification(
            specification,
            expected_run_id=row["id"],
            expected_cheapest_path=cheapest_path,
            expected_catalog_context=catalog_context,
            expected_result=result,
        )
    except (
        json.JSONDecodeError,
        KeyError,
        OptimizerContractError,
        TypeError,
        ValueError,
    ):
        return None
    if (
        validated_specification.digest != row["deployment_specification_digest"]
        or validated_specification.schema_version
        != row["deployment_specification_version"]
    ):
        return None
    raw_architecture = result.get("resolvedTwinArchitecture")
    if not isinstance(raw_architecture, dict):
        return None
    try:
        bundle = ArchitectureContractService.read_bundle(
            (
                profile,
                *_provider_documents(BASELINE_ID, BASELINE_VERSION),
                *_catalog_documents(),
                raw_architecture,
            )
        )
    except (ContractError, TypeError, ValueError):
        return None
    architecture = bundle[-1].as_dict()
    selection = connection.execute(
        """
        SELECT profile_id, profile_version, profile_digest
        FROM twin_architecture_selections
        WHERE twin_id = ? AND user_id = ?
        """,
        (row["twin_id"], row["user_id"]),
    ).fetchone()
    if selection is None:
        return None
    profile_ref = architecture["architecture_profile_ref"]
    deployment_ref = architecture["deployment_specification_ref"]
    bundle_ref = architecture["optimization_bundle_ref"]
    expected_bundle_ref = {
        field: profile["optimization_bundle"][field]
        for field in (
            "optimization_strategy_id",
            "optimization_strategy_version",
            "calculation_strategy_id",
            "calculation_strategy_version",
            "formula_set_id",
            "formula_set_version",
            "scoring_strategy_id",
            "scoring_strategy_version",
            "compatibility_digest",
        )
    }
    result_profile = result.get("optimizationProfile")
    result_strategy = result.get("calculationStrategy")
    if (
        architecture["calculation_run_id"] != row["id"]
        or (
            profile_ref["id"],
            profile_ref["version"],
            profile_ref["digest"],
        )
        != tuple(selection)
        or deployment_ref["calculation_run_id"] != row["id"]
        or deployment_ref["digest"] != row["deployment_specification_digest"]
        or deployment_ref["schema_version"] != row["deployment_specification_version"]
        or architecture["workload_contract_ref"] != profile["workload_contract_ref"]
        or bundle_ref != expected_bundle_ref
        or not isinstance(result_profile, dict)
        or not isinstance(result_strategy, dict)
        or bundle_ref["optimization_strategy_id"]
        != result.get("optimization_profile_id")
        or bundle_ref["calculation_strategy_id"]
        != result.get("calculation_strategy_id")
        or bundle_ref["formula_set_id"] != result_strategy.get("formula_set_id")
        or bundle_ref["scoring_strategy_id"]
        != result_profile.get("scoring_strategy_id")
        or architecture["functional_completeness"]["status"] != "complete"
        or str(architecture["cost_summary"]["currency"]) != str(row["currency"])
        or not _deployment_components_match(
            validated_specification.specification,
            architecture,
        )
        or not _extensions_match(connection, row, architecture)
        or not _fixed_projection_matches(connection, row, architecture)
    ):
        return None
    try:
        if Decimal(architecture["cost_summary"]["monthly_total"]) != Decimal(
            str(row["total_monthly_cost"])
        ):
            return None
    except (InvalidOperation, TypeError, ValueError):
        return None
    return architecture


def _deployment_components_match(
    specification: dict[str, Any],
    architecture: dict[str, Any],
) -> bool:
    components = {
        item.get("component_id"): item
        for item in specification.get("components", [])
        if isinstance(item, dict) and isinstance(item.get("component_id"), str)
    }
    assigned: set[str] = set()
    for assignment in architecture["component_assignments"]:
        for component_id in assignment["deployment_specification_component_ids"]:
            component = components.get(component_id)
            if component is None or component.get("provider") != assignment["provider"]:
                return False
            assigned.add(component_id)
    non_auxiliary = {
        component_id
        for component_id, component in components.items()
        if component.get("slot_id") not in {"transition_runtime", "cross_cloud_glue"}
    }
    return assigned == non_auxiliary


def _extensions_match(
    connection: sqlite3.Connection,
    row: dict[str, Any],
    architecture: dict[str, Any],
) -> bool:
    if not _table_exists(connection, "twin_user_functions"):
        return not architecture["extension_bindings"]
    active = connection.execute(
        """
        SELECT slot_id, slot_version, id, artifact_digest,
               configuration_json, validator_version
        FROM twin_user_functions
        WHERE twin_id = ?
        ORDER BY slot_id, slot_version, id
        """,
        (row["twin_id"],),
    ).fetchall()
    expected = {
        (item["slot_id"], item["slot_version"], item["artifact_id"]): item
        for item in architecture["extension_bindings"]
    }
    if set(expected) != {(item[0], item[1], item[2]) for item in active}:
        return False
    for (
        slot_id,
        slot_version,
        artifact_id,
        artifact_digest,
        configuration_json,
        validator_version,
    ) in active:
        item = expected[(slot_id, slot_version, artifact_id)]
        try:
            configuration = json.loads(configuration_json)
        except (TypeError, json.JSONDecodeError):
            return False
        configuration_digest = (
            "sha256:"
            + hashlib.sha256(canonical_json(configuration).encode("utf-8")).hexdigest()
        )
        if (
            artifact_digest != item["artifact_digest"]
            or validator_version != item["validation_contract_version"]
            or configuration_digest != item["configuration_digest"]
        ):
            return False
    return True


def _fixed_projection_matches(
    connection: sqlite3.Connection,
    row: dict[str, Any],
    architecture: dict[str, Any],
) -> bool:
    fields = {
        "component.ingestion": "cheapest_l1",
        "component.processing": "cheapest_l2",
        "component.hot-storage": "cheapest_l3_hot",
        "component.cool-storage": "cheapest_l3_cool",
        "component.archive-storage": "cheapest_l3_archive",
        "component.twin-state": "cheapest_l4",
        "component.visualization": "cheapest_l5",
    }
    config_id = row.get("optimizer_config_id")
    if (
        not config_id
        or not _table_exists(connection, "optimizer_configurations")
        or not set(fields.values()).issubset(
            _columns(connection, "optimizer_configurations")
        )
    ):
        return False
    projection = connection.execute(
        """
        SELECT cheapest_l1, cheapest_l2, cheapest_l3_hot,
               cheapest_l3_cool, cheapest_l3_archive,
               cheapest_l4, cheapest_l5
        FROM optimizer_configurations
        WHERE id = ?
        """,
        (config_id,),
    ).fetchone()
    if projection is None:
        return False
    expected = {
        fields[item["logical_component_id"]]: item["provider"]
        for item in architecture["component_assignments"]
    }
    actual = {
        field: _canonical_provider(value)
        for field, value in zip(fields.values(), projection, strict=True)
    }
    return actual == expected


def _canonical_provider(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    provider = value.strip().lower()
    if provider == "google":
        return "gcp"
    if provider in {"aws", "azure", "gcp"}:
        return provider
    return None


def _insert_resolution(
    connection: sqlite3.Connection,
    row: dict[str, Any],
    architecture: dict[str, Any],
) -> None:
    profile = architecture["architecture_profile_ref"]
    workload = architecture["workload_contract_ref"]
    deployment = architecture["deployment_specification_ref"]
    connection.execute(
        """
        INSERT INTO resolved_twin_architectures (
            id, calculation_run_id, twin_id, user_id, schema_version,
            profile_id, profile_version, profile_digest,
            optimization_bundle_digest, workload_contract_id,
            workload_contract_version, workload_digest,
            deployment_specification_version,
            deployment_specification_digest, total_monthly_cost, currency,
            functional_completeness_status, canonical_json, content_digest,
            origin, created_at
        ) VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
        """,
        (
            architecture["resolution_id"],
            row["id"],
            row["twin_id"],
            row["user_id"],
            architecture["schema_version"],
            profile["id"],
            profile["version"],
            profile["digest"],
            architecture["optimization_bundle_ref"]["compatibility_digest"],
            workload["id"],
            workload["version"],
            workload["digest"],
            deployment["schema_version"],
            deployment["digest"],
            architecture["cost_summary"]["monthly_total"],
            architecture["cost_summary"]["currency"],
            architecture["functional_completeness"]["status"],
            canonical_json(architecture),
            architecture["content_digest"],
            "reconstructed_v1",
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    for ordinal, item in enumerate(architecture["component_assignments"]):
        provider = item["provider_implementation_profile_ref"]
        connection.execute(
            """
            INSERT INTO resolved_architecture_component_assignments (
                id, resolved_architecture_id, assignment_id,
                responsibility_id, logical_component_id, provider,
                deployment_component_id, deployment_component_version,
                service_id, provider_profile_id, provider_profile_version,
                provider_profile_digest, region,
                deployment_specification_component_ids_json,
                cost_contribution, capability_refs_json, pricing_refs_json,
                formula_refs_json, evidence_refs_json, ordinal
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            (
                str(uuid.uuid4()),
                architecture["resolution_id"],
                item["assignment_id"],
                item["responsibility_id"],
                item["logical_component_id"],
                item["provider"],
                item["deployment_component_id"],
                item["deployment_component_version"],
                item["service_id"],
                provider["id"],
                provider["version"],
                provider["digest"],
                item["region"],
                canonical_json(item["deployment_specification_component_ids"]),
                item["cost_contribution"]["monthly_amount"],
                canonical_json(item["capability_evidence"]),
                canonical_json(item["pricing_model_refs"]),
                canonical_json(item["formula_refs"]),
                canonical_json(item["capability_evidence"]),
                ordinal,
            ),
        )
    for ordinal, item in enumerate(architecture["resolved_edges"]):
        connection.execute(
            """
            INSERT INTO resolved_architecture_edges (
                id, resolved_architecture_id, resolved_edge_id,
                logical_edge_id, source_assignment_id, source_port_id,
                destination_assignment_id, destination_port_id,
                edge_implementation_id, mechanism, transfer_route_id,
                cost_contribution, delivery_semantics_json, binding_refs_json,
                trust_ref_json, observability_ref_json, formula_refs_json,
                evidence_refs_json, ordinal
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            (
                str(uuid.uuid4()),
                architecture["resolution_id"],
                item["resolved_edge_id"],
                item["edge_id"],
                item["source_assignment_id"],
                item["source_port_id"],
                item["destination_assignment_id"],
                item["destination_port_id"],
                item["edge_implementation_id"],
                item["mechanism"],
                item["transfer_route_class"],
                item["cost_contribution"]["monthly_amount"],
                canonical_json(item["delivery_semantics"]),
                canonical_json(
                    {
                        "input": item["deployment_input_binding_ids"],
                        "output": item["deployment_output_binding_ids"],
                    }
                ),
                canonical_json(item["trust_contract_ref"]),
                canonical_json(item["observability_contract_ref"]),
                canonical_json(item["formula_refs"]),
                canonical_json(item["transfer_evidence_refs"]),
                ordinal,
            ),
        )


def _audit(
    connection: sqlite3.Connection,
    row: dict[str, Any],
    *,
    action: str,
    outcome: str,
    profile: dict[str, Any],
    result_code: str | None = None,
    resolution_digest: str | None = None,
) -> None:
    connection.execute(
        """
        INSERT INTO architecture_audit_events (
            id, user_id, action, outcome, profile_id, profile_version,
            profile_digest, twin_id, calculation_run_id, resolution_digest,
            result_code, correlation_id, occurred_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(uuid.uuid4()),
            row["user_id"],
            action,
            outcome,
            profile["profile_id"],
            profile["profile_version"],
            profile["content_digest"],
            row["twin_id"],
            row["id"],
            resolution_digest,
            result_code,
            f"migration-022:{row['id']}",
            datetime.now(timezone.utc).isoformat(),
        ),
    )


def _create_triggers(connection: sqlite3.Connection) -> None:
    for table in (
        "resolved_twin_architectures",
        "resolved_architecture_component_assignments",
        "resolved_architecture_edges",
    ):
        connection.execute(
            f"""
            CREATE TRIGGER IF NOT EXISTS trg_{table}_immutable
            BEFORE UPDATE ON {table}
            FOR EACH ROW
            BEGIN
                SELECT RAISE(ABORT, 'resolved architecture is immutable');
            END
            """
        )
    if _table_exists(connection, "cost_calculation_runs"):
        connection.execute(
            """
            CREATE TRIGGER IF NOT EXISTS trg_cost_runs_architecture_immutable
        BEFORE UPDATE OF architecture_compatibility_status,
                         resolved_architecture_version,
                         resolved_architecture_digest
        ON cost_calculation_runs
        FOR EACH ROW
        WHEN
            OLD.architecture_compatibility_status
                IS NOT NEW.architecture_compatibility_status
            OR OLD.resolved_architecture_version
                IS NOT NEW.resolved_architecture_version
            OR OLD.resolved_architecture_digest
                IS NOT NEW.resolved_architecture_digest
        BEGIN
            SELECT RAISE(ABORT, 'resolved architecture metadata is immutable');
        END
            """
        )
        connection.execute(
            """
            CREATE TRIGGER IF NOT EXISTS
            trg_cost_runs_architecture_status_insert
        BEFORE INSERT ON cost_calculation_runs
        FOR EACH ROW
        WHEN NEW.architecture_compatibility_status NOT IN (
            'ready', 'legacy_not_resolvable'
        )
        BEGIN
            SELECT RAISE(
                ABORT,
                'invalid architecture compatibility status'
            );
        END
            """
        )
    connection.execute(
        """
        CREATE TRIGGER IF NOT EXISTS trg_architecture_audit_immutable
        BEFORE UPDATE ON architecture_audit_events
        FOR EACH ROW
        BEGIN
            SELECT RAISE(ABORT, 'architecture audit event is append-only');
        END
        """
    )
    connection.execute(
        """
        CREATE TRIGGER IF NOT EXISTS trg_architecture_audit_no_delete
        BEFORE DELETE ON architecture_audit_events
        FOR EACH ROW
        BEGIN
            SELECT RAISE(ABORT, 'architecture audit event is append-only');
        END
        """
    )


def _resolution_exists(
    connection: sqlite3.Connection,
    run_id: str,
) -> bool:
    return (
        connection.execute(
            """
            SELECT 1
            FROM resolved_twin_architectures
            WHERE calculation_run_id = ?
            """,
            (run_id,),
        ).fetchone()
        is not None
    )


def _migration_audit_exists(
    connection: sqlite3.Connection,
    run_id: str,
) -> bool:
    return (
        connection.execute(
            """
            SELECT 1
            FROM architecture_audit_events
            WHERE calculation_run_id = ?
              AND correlation_id = ?
            """,
            (run_id, f"migration-022:{run_id}"),
        ).fetchone()
        is not None
    )


def _resolve_db_path(database_url: str | None) -> str:
    resolved = database_url or os.environ.get(
        "DATABASE_URL",
        "sqlite:///./management.db",
    )
    if not resolved.startswith("sqlite:///"):
        raise ValueError("Resolved architecture migration requires SQLite.")
    return resolved.removeprefix("sqlite:///")


def _table_exists(
    connection: sqlite3.Connection,
    table_name: str,
) -> bool:
    return (
        connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table_name,),
        ).fetchone()
        is not None
    )


def _columns(
    connection: sqlite3.Connection,
    table_name: str,
) -> set[str]:
    return {
        str(row[1]) for row in connection.execute(f"PRAGMA table_info({table_name})")
    }


if __name__ == "__main__":
    migrate()
