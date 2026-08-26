"""Validation coverage for the canonical Six-layer cost ledger."""

from __future__ import annotations

import copy
import json

import pytest

from src.services.errors import OptimizerContractError
from src.services.resolved_deployment_specification_service import V2_CONTRACT_ROOT
from src.services.six_layer_cost_ledger_service import (
    FORMULA_REF,
    SIX_LAYER_EVENT_COMPONENT_IDS,
    _expected_routes,
    _resolved_workload,
    _selection_digest,
    _six_layer_topology_cost_registry_digest,
    validate_six_layer_cost_ledger,
)
from tests.pricing_catalog_test_data import catalog_context


def _fixture(size: str = "small", *, currency: str = "USD"):
    if size != "small":
        raise ValueError("Only the canonical Small evidence fixture is stored")
    stem = "six-layer-aws-azure-eventing-small"
    specification = json.loads(
        (V2_CONTRACT_ROOT / "fixtures" / "valid" / f"{stem}.json").read_text(
            encoding="utf-8"
        )
    )
    architecture = json.loads(
        (
            V2_CONTRACT_ROOT.parents[1]
            / "architecture-profiles"
            / "v2"
            / "fixtures"
            / "valid"
            / f"{stem}-resolved.json"
        ).read_text(encoding="utf-8")
    )
    params = json.loads(
        (
            V2_CONTRACT_ROOT.parents[1]
            / "six-layer-workload"
            / "v1"
            / "fixtures"
            / "valid"
            / "core-small.json"
        ).read_text(encoding="utf-8")
    )
    params["optimizationProfileId"] = "cost-minimization-v2"
    params["currency"] = currency
    specification["currency"] = currency
    architecture["cost_summary"]["currency"] = currency

    context = catalog_context()
    evidence = {
        provider: reference.content_digest
        for provider, reference in context.catalogs.items()
    }
    selected_providers = sorted(
        {item["provider"] for item in specification["component_selections"]}
    )
    specification["optimization_context"]["pricing_evidence_refs"] = [
        {"provider": provider, "digest": evidence[provider]}
        for provider in selected_providers
    ]

    topology_digest = _six_layer_topology_cost_registry_digest()
    component_costs = []
    for selection in specification["component_selections"]:
        component_id = selection["implementation_component_id"]
        quote = {
            "component_id": component_id,
            "cost_owner_id": f"cost::{component_id}",
            "selection_digest": _selection_digest(selection),
            "formula_reference": FORMULA_REF,
            "pricing_evidence_digest": evidence[selection["provider"]],
            "monthly_amount": "0",
        }
        if component_id in SIX_LAYER_EVENT_COMPONENT_IDS:
            quote["topology_cost_registry_digest"] = topology_digest
        component_costs.append(quote)

    assignment = {
        item["logical_component_id"]: item["provider"]
        for item in architecture["component_assignments"]
    }
    resolved_size, workload, eventing_ref = _resolved_workload(params)
    routes = _expected_routes(
        assignment,
        size=resolved_size,
        workload=workload,
        eventing_ref=eventing_ref,
    )
    route_costs = []
    for route in routes:
        quote = {
            "cost_owner_id": route.cost_owner_id,
            "route_class": route.route_class,
            "pair": route.pair,
            "domain_flow_ids": list(route.domain_flow_ids),
            "workload_digest": route.workload_digest,
            "formula_reference": FORMULA_REF,
            "normalized_quantities": route.normalized_quantities,
            "pricing_evidence_digests": {
                "source": evidence[route.source_provider],
                "destination": evidence[route.destination_provider],
            },
            "monthly_amount": "0",
            "allocations": [
                {"item_id": item_id, "monthly_amount": "0"}
                for item_id in route.allocation_item_ids
            ],
        }
        if route.route_class == "domain_event_cross_cloud":
            quote["topology_cost_registry_digest"] = topology_digest
        route_costs.append(quote)

    for group in (
        "responsibility_totals",
        "component_totals",
        "edge_totals",
    ):
        for item in architecture["cost_summary"][group]:
            item["monthly_amount"] = "0"
    for assignment_item in architecture["component_assignments"]:
        assignment_item["cost_contribution"]["monthly_amount"] = "0"
    for edge in architecture["resolved_edges"]:
        edge["cost_contribution"]["monthly_amount"] = "0"
    architecture["cost_summary"]["monthly_total"] = "0"
    ledger = {
        "schema_version": "six-layer-cost-ledger.v1",
        "currency": currency,
        "component_costs": component_costs,
        "route_costs": route_costs,
    }
    return specification, architecture, params, context, ledger


def test_canonical_six_layer_ledger_validates():
    specification, architecture, params, context, ledger = _fixture()

    validated = validate_six_layer_cost_ledger(
        ledger,
        specification=specification,
        architecture=architecture,
        persisted_params=params,
        catalog_context=context,
        expected_total_exact="0",
    )

    assert validated.monthly_total == 0
    assert len(validated.result_items) == len(ledger["component_costs"]) + len(
        ledger["route_costs"]
    )
    assert all(item["review_status"] == "ready" for item in validated.result_items)


def test_ledger_preserves_currency_in_route_identity():
    specification, architecture, params, context, ledger = _fixture(currency="EUR")
    *_, usd_ledger = _fixture(currency="USD")

    validated = validate_six_layer_cost_ledger(
        ledger,
        specification=specification,
        architecture=architecture,
        persisted_params=params,
        catalog_context=context,
        expected_total_exact="0",
    )

    assert validated.ledger["currency"] == "EUR"
    assert {route["workload_digest"] for route in ledger["route_costs"]} != {
        route["workload_digest"] for route in usd_ledger["route_costs"]
    }


def test_ledger_rejects_topology_catalog_and_total_drift():
    specification, architecture, params, context, ledger = _fixture()
    stale_topology = copy.deepcopy(ledger)
    topology_quote = next(
        quote
        for quote in stale_topology["component_costs"]
        if "topology_cost_registry_digest" in quote
    )
    topology_quote["topology_cost_registry_digest"] = "sha256:" + ("0" * 64)
    with pytest.raises(OptimizerContractError):
        validate_six_layer_cost_ledger(
            stale_topology,
            specification=specification,
            architecture=architecture,
            persisted_params=params,
            catalog_context=context,
            expected_total_exact="0",
        )

    stale_catalog = copy.deepcopy(ledger)
    stale_catalog["route_costs"][0]["pricing_evidence_digests"]["destination"] = (
        "sha256:" + ("f" * 64)
    )
    with pytest.raises(OptimizerContractError):
        validate_six_layer_cost_ledger(
            stale_catalog,
            specification=specification,
            architecture=architecture,
            persisted_params=params,
            catalog_context=context,
            expected_total_exact="0",
        )

    with pytest.raises(OptimizerContractError):
        validate_six_layer_cost_ledger(
            ledger,
            specification=specification,
            architecture=architecture,
            persisted_params=params,
            catalog_context=context,
            expected_total_exact="1",
        )
