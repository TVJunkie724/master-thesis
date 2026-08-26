"""Canonical Six-layer fixture helpers for Management architecture tests."""

from __future__ import annotations

import copy
import json
from pathlib import Path

from src.services.architecture_contract_service import (
    calculate_digest,
    calculate_resolution_id,
)
from src.services.resolved_deployment_specification_service import (
    calculate_digest as calculate_deployment_digest,
)
from tests.pricing_catalog_test_data import catalog_context


RUN_ID = "018f0f5e-7b5e-7b2d-9f0b-7f66c2a88a01"
GENERATED_ROOT = Path(__file__).resolve().parents[1] / "src" / "contracts" / "generated"
PROFILE_ROOT = GENERATED_ROOT / "architecture-profiles"
RDS_FIXTURE = (
    GENERATED_ROOT
    / "resolved-deployment-specification"
    / "v2"
    / "fixtures"
    / "valid"
    / "six-layer-aws-azure-eventing-small.json"
)
RTA_FIXTURE = (
    PROFILE_ROOT
    / "v2"
    / "fixtures"
    / "valid"
    / "six-layer-aws-azure-eventing-small-resolved.json"
)


def _read(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"Expected a JSON object in {path}")
    return value


def linked_architecture_fixture_documents() -> tuple[dict, ...]:
    definitions = PROFILE_ROOT / "definitions"
    return (
        _read(definitions / "profiles" / "six-layer-eventing" / "1" / "profile.json"),
        *(
            _read(
                definitions
                / "provider-implementations"
                / "six-layer-eventing"
                / "1"
                / provider
                / "1.json"
            )
            for provider in ("aws", "azure", "gcp")
        ),
        _read(
            definitions
            / "component-catalogs"
            / "six-layer-eventing"
            / "1"
            / "catalog.json"
        ),
    )


def calculation_result_and_contracts(
    provider: str | None = None,
) -> tuple[dict, dict, dict]:
    """Return one internally consistent Six-layer result/RDS/RTA bundle.

    ``provider`` used to select synthetic Five-layer fixtures. It remains only
    as a transitional test-call argument; the fixture is always the canonical
    cross-cloud Six-layer architecture.
    """

    if provider not in {None, "aws", "azure"}:
        raise ValueError("provider must be aws, azure, or None")

    specification = copy.deepcopy(_read(RDS_FIXTURE))
    architecture = copy.deepcopy(_read(RTA_FIXTURE))
    context = catalog_context()
    selected_providers = sorted(
        {item["provider"] for item in specification["component_selections"]}
    )

    specification["calculation_run_id"] = RUN_ID
    specification["optimization_context"]["pricing_evidence_refs"] = [
        {
            "provider": selected_provider,
            "digest": context.catalogs[selected_provider].content_digest,
        }
        for selected_provider in selected_providers
    ]
    specification["digest"] = calculate_deployment_digest(specification)

    architecture["calculation_run_id"] = RUN_ID
    architecture["deployment_specification_ref"] = {
        "schema_version": specification["schema_version"],
        "calculation_run_id": RUN_ID,
        "digest": specification["digest"],
    }
    architecture["pricing_evidence_refs"] = [
        {
            "id": context.catalogs[selected_provider].snapshot_id,
            "version": "1",
            "digest": context.catalogs[selected_provider].content_digest,
            "provider": selected_provider,
            "currency": specification["currency"],
        }
        for selected_provider in selected_providers
    ]
    architecture["resolution_id"] = calculate_resolution_id(architecture)
    architecture["content_digest"] = calculate_digest(architecture)

    assignments = {
        item["logical_component_id"]: item["provider"].upper()
        for item in architecture["component_assignments"]
    }
    calculation_result = {
        "L1": assignments["component.ingestion"],
        "L2": assignments["component.processing"],
        "L3": {
            "Hot": assignments["component.hot-storage"],
            "Cool": assignments["component.cool-storage"],
            "Archive": assignments["component.archive-storage"],
        },
        "L4": assignments["component.twin-state"],
        "L5": assignments["component.visualization"],
        "Eventing": assignments["component.eventing"],
    }
    total = architecture["cost_summary"]["monthly_total"]
    result = {
        "calculationResult": calculation_result,
        "cheapestPath": [],
        "totalCost": float(total),
        "totalCostExact": total,
        "currency": architecture["cost_summary"]["currency"],
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
        "pricingCatalogs": context.to_http_dict(),
        "resolvedTwinArchitecture": architecture,
        "resolvedDeploymentSpecification": specification,
    }
    return result, specification, architecture
