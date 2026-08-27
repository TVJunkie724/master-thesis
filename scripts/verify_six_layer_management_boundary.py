#!/usr/bin/env python3
"""Verify one real Cross-Cloud Six-layer result through Management persistence.

Run from the repository root in the Management development image so both
service source trees and their locked Python dependencies are available. The
gate is deterministic, credential-free, and never calls a cloud API.
"""

from __future__ import annotations

import copy
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "twin2multicloud_backend"))
sys.path.insert(0, str(ROOT / "2-twin2clouds"))

from backend.architecture_profiles.six_layer_pricing import (  # noqa: E402
    SixLayerCatalogCostLedgerResolver,
)
from backend.architecture_profiles.registry import (  # noqa: E402
    ArchitectureProfileRegistry,
)
from backend.architecture_profiles.six_layer_optimizer import (  # noqa: E402
    optimize_six_layer_eventing_v1,
)
import src.models  # noqa: E402,F401
from src.models.architecture_profile import TwinArchitectureSelection  # noqa: E402
from src.models.cost_calculation import CostCalculationRun  # noqa: E402
from src.models.database import Base  # noqa: E402
from src.models.optimizer_config import OptimizerConfiguration  # noqa: E402
from src.models.twin import DigitalTwin  # noqa: E402
from src.models.user import User  # noqa: E402
from src.models.user_function_extension import (  # noqa: E402
    TwinExtensionBinding,
    UserFunctionArtifact,
)
from src.schemas.architecture_profile import (  # noqa: E402
    ResolvedTwinArchitectureContractV2,
)
from src.schemas.pricing_catalog import (  # noqa: E402
    PricingCatalogContext,
    PricingCatalogReference,
)
from src.services.cost_calculation_run_service import (  # noqa: E402
    CostCalculationRunService,
)
from src.services.user_function_extension_service import (  # noqa: E402
    runtime as extension_contract,
)


RUN_ID = "018f0f5e-7b5e-7b2d-9f0b-7f66c2a88a02"
USER_ID = "phase-8-six-layer-owner"
TWIN_ID = "phase-8-six-layer-twin"
ARTIFACT_ID = "artifact.user.processor.example"
EXPECTED_EVENT_EDGE_IDS = frozenset(
    {
        "edge.ingestion-to-eventing",
        "edge.eventing-to-processing",
        "edge.processing-to-eventing",
        "edge.eventing-to-ingestion",
        "edge.eventing-to-hot-storage",
    }
)


def _read(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"Expected an object: {path}")
    return value


def _pricing_inputs() -> tuple[dict, PricingCatalogContext]:
    root = ROOT / "2-twin2clouds" / "json" / "pricing_catalog_baselines"
    manifest = _read(root / "baseline.json")
    catalogs = {
        provider: PricingCatalogReference.model_validate(reference)
        for provider, reference in manifest["catalogs"].items()
    }
    pricing = {}
    for provider, reference in manifest["catalogs"].items():
        snapshot = _read(
            root
            / provider
            / reference["pricing_region"]
            / "snapshots"
            / f"{reference['snapshot_id']}.json"
        )
        pricing[provider] = snapshot["pricing"]
    return pricing, PricingCatalogContext(
        schema_version="provider-pricing-catalog-context.v1",
        catalogs=catalogs,
    )


def _optimize_cross_eventing(
    pricing: dict,
    context: PricingCatalogContext,
):
    registry = ArchitectureProfileRegistry(
        profile_id="six-layer-eventing",
        profile_version="1",
    )
    workload = _read(
        ROOT
        / "2-twin2clouds"
        / "backend"
        / "contracts"
        / "generated"
        / "six-layer-workload"
        / "v1"
        / "fixtures"
        / "valid"
        / "core-small.json"
    )
    providers = ("aws", "azure")
    evidence = {
        provider: {
            "id": context.catalogs[provider].snapshot_id,
            "version": "1",
            "digest": context.catalogs[provider].content_digest,
            "provider": provider,
            "currency": "USD",
        }
        for provider in providers
    }
    base_resolver = SixLayerCatalogCostLedgerResolver(
        {provider: pricing[provider] for provider in providers}
    )

    def force_cross_eventing(specification, assignment, resolved_workload):
        ledger = copy.deepcopy(
            base_resolver.resolve(
                specification,
                assignment,
                resolved_workload,
            )
        )
        target = (
            assignment["component.ingestion"] == "aws"
            and assignment["component.eventing"] == "azure"
            and assignment["component.processing"] == "aws"
        )
        if not target:
            quote = ledger["component_costs"][0]
            quote["monthly_amount"] = str(
                Decimal(quote["monthly_amount"]) + Decimal("1000000000")
            )
        return ledger

    configuration_digest = "sha256:" + hashlib.sha256(b"{}").hexdigest()
    optimized = optimize_six_layer_eventing_v1(
        calculation_run_id=RUN_ID,
        architecture_profile={
            "profileId": registry.profile["profile_id"],
            "profileVersion": registry.profile["profile_version"],
            "contentDigest": registry.profile["content_digest"],
        },
        extension_bindings=[
            {
                "slotId": "processor.telemetry",
                "slotVersion": "1",
                "artifactId": ARTIFACT_ID,
                "artifactDigest": "sha256:" + ("1" * 64),
                "configurationDigest": configuration_digest,
            }
        ],
        workload=workload,
        pricing_evidence_refs=evidence,
        cost_ledger_resolver=force_cross_eventing,
        providers=providers,
        registry=registry,
    )
    return optimized, workload, registry


def _persist(optimized, workload: dict, registry, context: PricingCatalogContext):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        user = User(id=USER_ID, email="phase-8-six-layer@example.test")
        twin = DigitalTwin(id=TWIN_ID, name="Phase 8 Six-layer", user_id=USER_ID)
        config = OptimizerConfiguration(id="phase-8-six-layer-config", twin_id=TWIN_ID)
        session.add_all([user, twin, config])
        session.flush()
        session.add(
            TwinArchitectureSelection(
                twin_id=TWIN_ID,
                user_id=USER_ID,
                profile_id="six-layer-eventing",
                profile_version="1",
                profile_digest=registry.profile["content_digest"],
                revision=1,
                selected_by_user_id=USER_ID,
            )
        )
        artifact = UserFunctionArtifact(
            id=ARTIFACT_ID,
            user_id=USER_ID,
            schema_version="user-function-artifact.v1",
            artifact_state="valid",
            artifact_digest="sha256:" + ("1" * 64),
            slot_id="processor.telemetry",
            slot_version="1",
            runtime_id="python311",
            configuration_json="{}",
            declared_capabilities_json="[]",
            validator_version="user-function-validator.v1",
            created_by=USER_ID,
        )
        session.add(artifact)
        session.flush()
        session.add(
            TwinExtensionBinding(
                id="phase-8-six-layer-binding",
                user_id=USER_ID,
                twin_id=TWIN_ID,
                slot_id="processor.telemetry",
                slot_version="1",
                artifact_id=ARTIFACT_ID,
                binding_digest=extension_contract.binding_digest(
                    twin_id=TWIN_ID,
                    slot_id="processor.telemetry",
                    slot_version="1",
                    artifact_id=ARTIFACT_ID,
                    artifact_digest=artifact.artifact_digest,
                ),
                active=True,
                revision=1,
            )
        )
        session.flush()

        architecture = dict(optimized.resolved_architecture)
        specification = dict(optimized.deployment_specification)
        assignment = {
            item["logical_component_id"]: item["provider"]
            for item in architecture["component_assignments"]
        }
        provider_labels = {"aws": "AWS", "azure": "Azure", "gcp": "GCP"}
        calculation_result = {
            "L1": provider_labels[assignment["component.ingestion"]],
            "L2": provider_labels[assignment["component.processing"]],
            "L3": {
                "Hot": provider_labels[assignment["component.hot-storage"]],
                "Cool": provider_labels[assignment["component.cool-storage"]],
                "Archive": provider_labels[assignment["component.archive-storage"]],
            },
            "L4": provider_labels[assignment["component.twin-state"]],
            "L5": provider_labels[assignment["component.visualization"]],
            "Eventing": provider_labels[assignment["component.eventing"]],
        }
        total = str(optimized.cost_evaluation.monthly_total)
        result = {
            "calculationResult": calculation_result,
            "cheapestPath": [],
            "totalCost": float(total),
            "totalCostExact": total,
            "currency": "USD",
            "optimization_profile_id": "cost-minimization-v2",
            "result_schema_version": "cost-result.v2",
            "optimizationProfile": {
                "enabled": True,
                "profile_version": "2",
                "scoring_strategy_id": "profile-local-min-total-cost-v2",
                "calculation_model_ids": ["profile-resolution-v2@2"],
                "pricing_registry_version": "phase-08-complete-service-pricing@1",
            },
            "evidenceReferences": {
                "pricing_registry": "phase-08-complete-service-pricing@1"
            },
            "costLedger": dict(optimized.cost_ledger),
            "resolvedTwinArchitecture": architecture,
            "resolvedDeploymentSpecification": specification,
        }
        run = CostCalculationRun(
            id=RUN_ID,
            twin_id=TWIN_ID,
            user_id=USER_ID,
            optimizer_config_id=config.id,
            optimizer_config=config,
            status="failed",
            params_json=json.dumps(
                workload,
                sort_keys=True,
                separators=(",", ":"),
            ),
            total_monthly_cost=float(total),
            currency="USD",
            optimization_profile_id="cost-minimization-v2",
            optimization_profile_version="2",
            scoring_strategy_id="profile-local-min-total-cost-v2",
            calculation_model_version="profile-resolution-v2@2",
            pricing_catalog_context_json=context.canonical_json(),
        )
        persisted = CostCalculationRunService(session).persist_successful_run(
            result,
            specification,
            architecture,
            run=run,
            catalog_context=context,
        )
        ResolvedTwinArchitectureContractV2.model_validate(architecture)
        event_edges = [
            edge
            for edge in persisted.resolved_architecture.edges
            if edge.logical_edge_id in EXPECTED_EVENT_EDGE_IDS
        ]
        if (
            len(persisted.resolved_architecture.components) != 8
            or len(persisted.resolved_architecture.edges) != 9
            or {edge.logical_edge_id for edge in event_edges} != EXPECTED_EVENT_EDGE_IDS
            or {edge.mechanism for edge in event_edges} != {"cross_provider_adapter"}
        ):
            raise RuntimeError("Persisted Six-layer graph is incomplete")
        return {
            "profile": "six-layer-eventing@1",
            "components": len(persisted.resolved_architecture.components),
            "edges": len(persisted.resolved_architecture.edges),
            "event_bridges": len(event_edges),
            "result_items": len(persisted.result_items),
            "resolution_digest": persisted.resolved_architecture_digest,
        }
    finally:
        session.close()
        engine.dispose()


def main() -> int:
    pricing, context = _pricing_inputs()
    optimized, workload, registry = _optimize_cross_eventing(pricing, context)
    print(json.dumps(_persist(optimized, workload, registry, context), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
