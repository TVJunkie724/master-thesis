"""Exact-once component/route cost ownership for Five-layer v2."""

from __future__ import annotations

from dataclasses import replace
import json

import pytest

from backend.architecture_profiles.diagnostics import ArchitectureResolutionError
from backend.architecture_profiles.five_layer_v2_costing import (
    CONTRACT_ROOT as RDS_ROOT,
    FORMULA_REF,
    FiveLayerV2CostedCandidate,
    evaluate_five_layer_v2_costs,
    expected_route_owners,
    select_lowest_cost_five_layer_v2_candidate,
    selection_digest,
)
from backend.architecture_profiles.five_layer_v2_workload import (
    CONTRACT_ROOT as WORKLOAD_ROOT,
    resolve_five_layer_v2_workload,
)
from backend.architecture_profiles.registry import ArchitectureProfileRegistry
from backend.deployment_specification.five_layer_v2_builder import (
    LOGICAL_COMPONENTS,
    build_five_layer_v2_deployment_specification,
)


def _read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _build(assignment, size="small"):
    workload = resolve_five_layer_v2_workload(
        _read(WORKLOAD_ROOT / "fixtures" / "valid" / f"core-{size}.json")
    )
    registry = ArchitectureProfileRegistry(profile_version="2")
    selected_providers = set(assignment.values())
    evidence = {
        provider: "sha256:"
        + ({"aws": "a", "azure": "b", "gcp": "c"}[provider] * 64)
        for provider in selected_providers
    }
    specification = build_five_layer_v2_deployment_specification(
        calculation_run_id="018f0f5e-7b5e-7b2d-9f0b-7f66c2a88a01",
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
        pricing_evidence_digests=evidence,
    )
    return specification, workload


def _ledger(specification, assignment, workload):
    registry = _read(RDS_ROOT / "component-capacity-registry.json")
    component_index = {
        item["component_id"]: item for item in registry["components"]
    }
    evidence = {
        item["provider"]: item["digest"]
        for item in specification["optimization_context"]["pricing_evidence_refs"]
    }
    component_costs = []
    for selection in specification["component_selections"]:
        component = component_index[selection["implementation_component_id"]]
        component_costs.append(
            {
                "component_id": selection["implementation_component_id"],
                "cost_owner_id": component["pricing_owner_id"],
                "selection_digest": selection_digest(selection),
                "formula_reference": FORMULA_REF,
                "pricing_evidence_digest": evidence[selection["provider"]],
                "monthly_amount": "1",
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
                "pricing_evidence_digest": evidence[route.source_provider],
                "monthly_amount": str(len(route.allocation_item_ids)),
                "allocations": [
                    {"item_id": item_id, "monthly_amount": "1"}
                    for item_id in route.allocation_item_ids
                ],
            }
        )
    return {
        "schema_version": "five-layer-v2-cost-ledger.v1",
        "currency": specification["currency"],
        "component_costs": component_costs,
        "route_costs": route_costs,
    }


@pytest.mark.parametrize(
    "assignment",
    (
        {logical: "aws" for logical in LOGICAL_COMPONENTS},
        {
            logical: "gcp" if logical == "component.twin-state" else "azure"
            for logical in LOGICAL_COMPONENTS
        },
        {
            "component.ingestion": "aws",
            "component.processing": "azure",
            "component.hot-storage": "gcp",
            "component.cool-storage": "aws",
            "component.archive-storage": "azure",
            "component.twin-state": "aws",
            "component.visualization": "gcp",
        },
    ),
)
def test_all_component_and_route_owners_reconcile_exactly_once(assignment):
    specification, workload = _build(assignment)
    ledger = _ledger(specification, assignment, workload)

    evaluation = evaluate_five_layer_v2_costs(
        specification=specification,
        assignment=assignment,
        resolved_workload=workload,
        cost_ledger=ledger,
    )

    expected_total = len(ledger["component_costs"]) + sum(
        len(item["allocations"]) for item in ledger["route_costs"]
    )
    assert evaluation.monthly_total == expected_total
    assert len(evaluation.component_owner_totals) == len(ledger["component_costs"])
    assert len(evaluation.route_owner_totals) == len(ledger["route_costs"])
    assert sum(evaluation.component_totals.values()) + sum(
        evaluation.edge_totals.values()
    ) == evaluation.monthly_total


def test_single_cloud_has_no_cross_cloud_route_owner():
    assignment = {logical: "aws" for logical in LOGICAL_COMPONENTS}
    specification, workload = _build(assignment)

    assert expected_route_owners(assignment, workload) == ()
    assert _ledger(specification, assignment, workload)["route_costs"] == []


@pytest.mark.parametrize(
    "tamper",
    (
        lambda ledger: ledger["component_costs"].pop(),
        lambda ledger: ledger["component_costs"][0].update(
            {"pricing_evidence_digest": "sha256:" + ("f" * 64)}
        ),
        lambda ledger: ledger["route_costs"][0].update(
            {"monthly_amount": "999"}
        ),
    ),
)
def test_incomplete_or_unreconciled_cost_ledgers_fail_closed(tamper):
    assignment = {
        logical: "gcp" if logical == "component.twin-state" else "azure"
        for logical in LOGICAL_COMPONENTS
    }
    specification, workload = _build(assignment)
    ledger = _ledger(specification, assignment, workload)
    tamper(ledger)

    with pytest.raises(ArchitectureResolutionError) as raised:
        evaluate_five_layer_v2_costs(
            specification=specification,
            assignment=assignment,
            resolved_workload=workload,
            cost_ledger=ledger,
        )

    assert raised.value.code == "ARCH_PRICING_EVIDENCE_MISSING"


def test_ranking_uses_exact_cost_then_canonical_assignment():
    aws_assignment = {logical: "aws" for logical in LOGICAL_COMPONENTS}
    azure_assignment = {logical: "azure" for logical in LOGICAL_COMPONENTS}
    aws_specification, workload = _build(aws_assignment)
    azure_specification, _ = _build(azure_assignment)
    aws_evaluation = evaluate_five_layer_v2_costs(
        specification=aws_specification,
        assignment=aws_assignment,
        resolved_workload=workload,
        cost_ledger=_ledger(aws_specification, aws_assignment, workload),
    )
    azure_evaluation = evaluate_five_layer_v2_costs(
        specification=azure_specification,
        assignment=azure_assignment,
        resolved_workload=workload,
        cost_ledger=_ledger(azure_specification, azure_assignment, workload),
    )
    tied_azure = replace(azure_evaluation, monthly_total=aws_evaluation.monthly_total)

    winner = select_lowest_cost_five_layer_v2_candidate(
        (
            FiveLayerV2CostedCandidate(
                candidate_id="azure",
                canonical_assignment_key=tuple(sorted(azure_assignment.items())),
                evaluation=tied_azure,
            ),
            FiveLayerV2CostedCandidate(
                candidate_id="aws",
                canonical_assignment_key=tuple(sorted(aws_assignment.items())),
                evaluation=aws_evaluation,
            ),
        )
    )

    assert winner.candidate_id == "aws"
