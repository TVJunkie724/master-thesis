from __future__ import annotations

import copy
import json

import pytest

from src.services.errors import OptimizerContractError
from src.services.five_layer_v2_cost_ledger_service import (
    FORMULA_REF,
    SIX_LAYER_EVENT_COMPONENT_IDS,
    _expected_routes,
    _resolved_workload,
    _selection_digest,
    _six_layer_topology_cost_registry_digest,
    validate_five_layer_v2_cost_ledger,
)
from src.services.resolved_deployment_specification_service import (
    V2_CONTRACT_ROOT,
)
from tests.pricing_catalog_test_data import catalog_context


def _fixture(size: str = "medium", *, currency: str = "USD"):
    stem = {
        "small": "single-cloud-aws-small",
        "medium": "two-cloud-azure-l3l5-gcp-l4-medium",
        "large": "three-cloud-mixed-large",
    }[size]
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
            / "five-layer-workload"
            / "v2"
            / "fixtures"
            / "valid"
            / f"core-{size}.json"
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
    specification["optimization_context"]["pricing_evidence_refs"] = [
        {"provider": provider, "digest": evidence[provider]}
        for provider in sorted(
            {
                selection["provider"]
                for selection in specification["component_selections"]
            }
        )
    ]
    component_costs = [
        {
            "component_id": selection["implementation_component_id"],
            "cost_owner_id": (f"cost::{selection['implementation_component_id']}"),
            "selection_digest": _selection_digest(selection),
            "formula_reference": FORMULA_REF,
            "pricing_evidence_digest": evidence[selection["provider"]],
            "monthly_amount": "0",
        }
        for selection in specification["component_selections"]
    ]
    assignment = {
        item["logical_component_id"]: item["provider"]
        for item in architecture["component_assignments"]
    }
    resolved_size, workload, eventing_ref = _resolved_workload(params)
    route_costs = []
    for route in _expected_routes(
        assignment,
        size=resolved_size,
        workload=workload,
        eventing_ref=eventing_ref,
    ):
        route_costs.append(
            {
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
        )
    ledger = {
        "schema_version": "five-layer-v2-cost-ledger.v1",
        "currency": currency,
        "component_costs": component_costs,
        "route_costs": route_costs,
    }
    return specification, architecture, params, context, ledger


def _six_layer_fixture():
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
            / "five-layer-workload"
            / "v2"
            / "fixtures"
            / "valid"
            / "core-small.json"
        ).read_text(encoding="utf-8")
    )
    params["optimizationProfileId"] = "cost-minimization-v2"
    context = catalog_context()
    evidence = {
        provider: reference.content_digest
        for provider, reference in context.catalogs.items()
    }
    specification["optimization_context"]["pricing_evidence_refs"] = [
        {"provider": provider, "digest": evidence[provider]}
        for provider in sorted(
            {
                selection["provider"]
                for selection in specification["component_selections"]
            }
        )
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
    for item in architecture["cost_summary"]["component_totals"]:
        item["monthly_amount"] = "0"
    for item in architecture["cost_summary"]["edge_totals"]:
        item["monthly_amount"] = "0"
    architecture["cost_summary"]["monthly_total"] = "0"
    ledger = {
        "schema_version": "five-layer-v2-cost-ledger.v1",
        "currency": "USD",
        "component_costs": component_costs,
        "route_costs": route_costs,
    }
    return specification, architecture, params, context, ledger, routes


@pytest.mark.parametrize("size", ("small", "medium", "large"))
def test_five_layer_v2_ledger_validates_all_scenarios(size):
    specification, architecture, params, context, ledger = _fixture(size)

    validated = validate_five_layer_v2_cost_ledger(
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


def test_five_layer_v2_ledger_preserves_currency_in_route_identity():
    specification, architecture, params, context, ledger = _fixture(currency="EUR")
    *_, usd_ledger = _fixture(currency="USD")

    validated = validate_five_layer_v2_cost_ledger(
        ledger,
        specification=specification,
        architecture=architecture,
        persisted_params=params,
        catalog_context=context,
        expected_total_exact="0",
    )

    assert validated.ledger["currency"] == "EUR"
    assert validated.result_items[0]["currency"] == "EUR"
    assert {route["workload_digest"] for route in ledger["route_costs"]} != {
        route["workload_digest"] for route in usd_ledger["route_costs"]
    }


def test_six_layer_ledger_matches_current_topology_registry_and_hot_route():
    specification, architecture, params, context, ledger, routes = _six_layer_fixture()

    domain_routes = {
        route.pair: route
        for route in routes
        if route.route_class == "domain_event_cross_cloud"
    }
    assert domain_routes["aws->azure"].allocation_item_ids == (
        "edge.ingestion-to-eventing",
        "edge.processing-to-eventing",
    )
    assert domain_routes["azure->aws"].allocation_item_ids == (
        "edge.eventing-to-hot-storage",
        "edge.eventing-to-ingestion",
        "edge.eventing-to-processing",
    )

    validated = validate_five_layer_v2_cost_ledger(
        ledger,
        specification=specification,
        architecture=architecture,
        persisted_params=params,
        catalog_context=context,
        expected_total_exact="0",
    )

    assert validated.monthly_total == 0
    assert {
        quote["topology_cost_registry_digest"]
        for quote in ledger["route_costs"]
        if quote["route_class"] == "domain_event_cross_cloud"
    } == {_six_layer_topology_cost_registry_digest()}


def test_six_layer_ledger_rejects_stale_topology_registry_digest():
    specification, architecture, params, context, ledger, _routes = _six_layer_fixture()
    topology_quote = next(
        quote
        for quote in ledger["component_costs"]
        if "topology_cost_registry_digest" in quote
    )
    topology_quote["topology_cost_registry_digest"] = "sha256:" + ("0" * 64)

    with pytest.raises(OptimizerContractError, match="cost ledger is invalid"):
        validate_five_layer_v2_cost_ledger(
            ledger,
            specification=specification,
            architecture=architecture,
            persisted_params=params,
            catalog_context=context,
            expected_total_exact="0",
        )


def test_five_layer_v2_ledger_rejects_destination_catalog_drift():
    specification, architecture, params, context, ledger = _fixture()
    ledger["route_costs"][0]["pricing_evidence_digests"]["destination"] = "sha256:" + (
        "f" * 64
    )

    with pytest.raises(OptimizerContractError) as raised:
        validate_five_layer_v2_cost_ledger(
            ledger,
            specification=specification,
            architecture=architecture,
            persisted_params=params,
            catalog_context=context,
            expected_total_exact="0",
        )

    assert raised.value.errors[0]["field"].startswith("costLedger.route_costs")


def test_five_layer_v2_ledger_rejects_missing_owner_and_total_drift():
    specification, architecture, params, context, ledger = _fixture()
    missing = copy.deepcopy(ledger)
    missing["component_costs"].pop()

    with pytest.raises(OptimizerContractError):
        validate_five_layer_v2_cost_ledger(
            missing,
            specification=specification,
            architecture=architecture,
            persisted_params=params,
            catalog_context=context,
            expected_total_exact="0",
        )

    with pytest.raises(OptimizerContractError):
        validate_five_layer_v2_cost_ledger(
            ledger,
            specification=specification,
            architecture=architecture,
            persisted_params=params,
            catalog_context=context,
            expected_total_exact="1",
        )
