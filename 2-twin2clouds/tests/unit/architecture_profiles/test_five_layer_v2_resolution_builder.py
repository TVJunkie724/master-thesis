"""ResolvedTwinArchitecture v2 construction from one complete winner."""

from __future__ import annotations

from dataclasses import replace
import json

import pytest

from backend.architecture_profiles.diagnostics import ArchitectureResolutionError
from backend.architecture_profiles.five_layer_v2_costing import (
    CONTRACT_ROOT as RDS_ROOT,
    FORMULA_REF,
    evaluate_five_layer_v2_costs,
    selection_digest,
)
from backend.architecture_profiles.five_layer_v2_resolution_builder import (
    FiveLayerV2ResolutionBuilder,
)
from backend.architecture_profiles.five_layer_v2_strategy import (
    FiveLayerV2CandidateStrategy,
)
from backend.architecture_profiles.five_layer_v2_workload import (
    CONTRACT_ROOT as WORKLOAD_ROOT,
    resolve_five_layer_v2_workload,
)
from backend.architecture_profiles.registry import ArchitectureProfileRegistry
from backend.architecture_profiles.strategy import build_resolution_context
from backend.deployment_specification.five_layer_v2_builder import (
    LOGICAL_COMPONENTS,
    build_five_layer_v2_deployment_specification,
)


RUN_ID = "018f0f5e-7b5e-7b2d-9f0b-7f66c2a88a01"


def _read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _winner_inputs():
    registry = ArchitectureProfileRegistry(profile_version="2")
    context = build_resolution_context(
        registry=registry,
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
                "artifactId": "artifact.user.processor.example",
                "artifactDigest": "sha256:" + ("1" * 64),
                "configurationDigest": "sha256:" + ("2" * 64),
            }
        ],
        resolution_status="offline_contract_fixture",
    ).with_execution_inputs(
        layer_options={
            layer: (("AWS", 1),)
            for layer in (
                "L1",
                "L2",
                "L3_hot",
                "L3_cool",
                "L3_archive",
                "L4",
                "L5",
            )
        },
        provider_regions={
            "aws": "eu-central-1",
            "azure": "westeurope",
            "gcp": "europe-west1",
        },
    )
    strategy = FiveLayerV2CandidateStrategy(registry.profile)
    candidate = strategy.validate_functional_completeness(
        strategy.enumerate_candidates(context)[0], context
    )
    assignment = {logical: "aws" for logical in LOGICAL_COMPONENTS}
    workload = resolve_five_layer_v2_workload(
        _read(WORKLOAD_ROOT / "fixtures" / "valid" / "core-small.json")
    )
    evidence_digest = "sha256:" + ("a" * 64)
    specification = build_five_layer_v2_deployment_specification(
        calculation_run_id=RUN_ID,
        assignment=assignment,
        resolved_workload=workload,
        architecture_profile_ref={
            "id": registry.profile["profile_id"],
            "version": registry.profile["profile_version"],
            "digest": registry.profile["content_digest"],
        },
        component_catalog_ref={
            "id": registry.catalog["catalog_id"],
            "version": registry.catalog["catalog_version"],
            "digest": registry.catalog["content_digest"],
        },
        workload_contract_digest=registry.profile["workload_contract_ref"]["digest"],
        pricing_evidence_digests={"aws": evidence_digest},
    )
    component_registry = _read(RDS_ROOT / "component-capacity-registry.json")
    component_index = {
        item["component_id"]: item for item in component_registry["components"]
    }
    ledger = {
        "schema_version": "five-layer-v2-cost-ledger.v1",
        "currency": "USD",
        "component_costs": [
            {
                "component_id": selection["implementation_component_id"],
                "cost_owner_id": component_index[
                    selection["implementation_component_id"]
                ]["pricing_owner_id"],
                "selection_digest": selection_digest(selection),
                "formula_reference": FORMULA_REF,
                "pricing_evidence_digest": evidence_digest,
                "monthly_amount": "1",
            }
            for selection in specification["component_selections"]
        ],
        "route_costs": [],
    }
    costs = evaluate_five_layer_v2_costs(
        specification=specification,
        assignment=assignment,
        resolved_workload=workload,
        cost_ledger=ledger,
    )
    pricing_refs = {
        "aws": {
            "id": "pricing-evidence.aws.test-v2",
            "version": "1",
            "digest": evidence_digest,
            "provider": "aws",
            "currency": "USD",
        }
    }
    return context, candidate, specification, costs, pricing_refs


def test_resolution_builds_valid_costed_v2_architecture():
    context, candidate, specification, costs, pricing_refs = _winner_inputs()

    resolved = FiveLayerV2ResolutionBuilder().build(
        candidate=candidate,
        context=context,
        deployment_specification=specification,
        cost_evaluation=costs,
        pricing_evidence_refs=pricing_refs,
    )

    assert resolved["schema_version"] == "resolved-twin-architecture.v2"
    assert resolved["resolution_status"] == "offline_contract_fixture"
    assert resolved["cost_summary"]["monthly_total"] == "19"
    assert resolved["deployment_specification_ref"]["digest"] == specification[
        "digest"
    ]
    edge_ids = {edge["edge_id"] for edge in resolved["resolved_edges"]}
    assert "edge.hot-storage-to-visualization" in edge_ids
    assert "edge.twin-state-to-visualization" not in edge_ids


def test_resolution_rejects_cost_total_tampering():
    context, candidate, specification, costs, pricing_refs = _winner_inputs()
    costs = replace(costs, monthly_total=costs.monthly_total + 1)

    with pytest.raises(ArchitectureResolutionError) as raised:
        FiveLayerV2ResolutionBuilder().build(
            candidate=candidate,
            context=context,
            deployment_specification=specification,
            cost_evaluation=costs,
            pricing_evidence_refs=pricing_refs,
        )

    assert raised.value.code == "ARCH_RESOLUTION_BUILD_FAILED"
