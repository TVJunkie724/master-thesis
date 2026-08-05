"""Closed-world Five-layer v2 optimization orchestration coverage."""

from __future__ import annotations

import json

import pytest

from backend.architecture_profiles.diagnostics import ArchitectureResolutionError
from backend.architecture_profiles.five_layer_v2_costing import (
    CONTRACT_ROOT as RDS_ROOT,
    FORMULA_REF,
    expected_route_owners,
    selection_digest,
)
from backend.architecture_profiles.five_layer_v2_optimizer import (
    optimize_five_layer_v2,
)
from backend.architecture_profiles.five_layer_v2_workload import (
    CONTRACT_ROOT as WORKLOAD_ROOT,
)
from backend.architecture_profiles.registry import ArchitectureProfileRegistry


RUN_ID = "018f0f5e-7b5e-7b2d-9f0b-7f66c2a88a01"
EVIDENCE = {
    "aws": {
        "id": "pricing-evidence.aws.test-v2",
        "version": "1",
        "digest": "sha256:" + ("a" * 64),
        "provider": "aws",
        "currency": "USD",
    },
    "azure": {
        "id": "pricing-evidence.azure.test-v2",
        "version": "1",
        "digest": "sha256:" + ("b" * 64),
        "provider": "azure",
        "currency": "USD",
    },
}


def _read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _request():
    registry = ArchitectureProfileRegistry(profile_version="2")
    return registry, {
        "calculation_run_id": RUN_ID,
        "architecture_profile": {
            "profileId": registry.profile["profile_id"],
            "profileVersion": registry.profile["profile_version"],
            "contentDigest": registry.profile["content_digest"],
        },
        "extension_bindings": [
            {
                "slotId": "processor.telemetry",
                "slotVersion": "1",
                "artifactId": "artifact.user.processor.example",
                "artifactDigest": "sha256:" + ("1" * 64),
                "configurationDigest": "sha256:" + ("2" * 64),
            }
        ],
        "workload": _read(
            WORKLOAD_ROOT / "fixtures" / "valid" / "core-small.json"
        ),
        "pricing_evidence_refs": EVIDENCE,
        "providers": ("aws", "azure"),
        "registry": registry,
    }


def _ledger(specification, assignment, workload, *, omit_azure=False):
    registry = _read(RDS_ROOT / "component-capacity-registry.json")
    components = {
        item["component_id"]: item for item in registry["components"]
    }
    evidence = {
        item["provider"]: item["digest"]
        for item in specification["optimization_context"]["pricing_evidence_refs"]
    }
    component_costs = []
    for selection in specification["component_selections"]:
        if omit_azure and selection["provider"] == "azure":
            continue
        component = components[selection["implementation_component_id"]]
        component_costs.append(
            {
                "component_id": selection["implementation_component_id"],
                "cost_owner_id": component["pricing_owner_id"],
                "selection_digest": selection_digest(selection),
                "formula_reference": FORMULA_REF,
                "pricing_evidence_digest": evidence[selection["provider"]],
                "monthly_amount": "1" if selection["provider"] == "aws" else "2",
            }
        )
    route_costs = []
    for route in expected_route_owners(assignment, workload):
        route_costs.append(
            {
                "cost_owner_id": route.cost_owner_id,
                "route_class": route.route_class,
                "pair": route.pair,
                "domain_flow_ids": list(route.domain_flow_ids),
                "workload_digest": route.workload_digest,
                "formula_reference": FORMULA_REF,
                "pricing_evidence_digests": {
                    "source": evidence[route.source_provider],
                    "destination": evidence[route.destination_provider],
                },
                "monthly_amount": str(10 * len(route.allocation_item_ids)),
                "allocations": [
                    {"item_id": item_id, "monthly_amount": "10"}
                    for item_id in route.allocation_item_ids
                ],
            }
        )
    return {
        "schema_version": "five-layer-v2-cost-ledger.v1",
        "currency": "USD",
        "component_costs": component_costs,
        "route_costs": route_costs,
    }


def test_optimizer_costs_all_64_two_provider_candidates_and_selects_aws():
    _, request = _request()

    result = optimize_five_layer_v2(
        **request,
        cost_ledger_resolver=_ledger,
    )

    assert result.enumerated_candidate_count == 64
    assert result.costed_candidate_count == 64
    assert result.rejected_by_error_code == ()
    assert {
        assignment["provider"]
        for assignment in result.resolved_architecture["component_assignments"]
    } == {"aws"}
    assert result.resolved_architecture["cost_summary"]["monthly_total"] == "19"
    assert result.cost_ledger["schema_version"] == (
        "five-layer-v2-cost-ledger.v1"
    )
    assert len(result.cost_ledger["component_costs"]) == len(
        result.deployment_specification["component_selections"]
    )
    assert result.cost_ledger["route_costs"] == []


def test_optimizer_rejects_incomplete_provider_price_coverage_per_candidate():
    _, request = _request()

    result = optimize_five_layer_v2(
        **request,
        cost_ledger_resolver=lambda specification, assignment, workload: _ledger(
            specification,
            assignment,
            workload,
            omit_azure=True,
        ),
    )

    assert result.enumerated_candidate_count == 64
    assert result.costed_candidate_count == 1
    assert dict(result.rejected_by_error_code) == {
        "ARCH_PRICING_EVIDENCE_MISSING": 63
    }


def test_optimizer_requires_exactly_one_production_or_test_pricing_source():
    _, request = _request()

    with pytest.raises(ArchitectureResolutionError) as missing:
        optimize_five_layer_v2(**request)
    with pytest.raises(ArchitectureResolutionError) as ambiguous:
        optimize_five_layer_v2(
            **request,
            cost_ledger_resolver=_ledger,
            pricing_by_provider={},
        )

    assert missing.value.code == "ARCH_PRICING_EVIDENCE_MISSING"
    assert ambiguous.value.code == "ARCH_PRICING_EVIDENCE_MISSING"
