"""Live-catalog rate-card adapter coverage for Five-layer v2."""

from __future__ import annotations

import json
from decimal import Decimal

import pytest

from backend.architecture_profiles.diagnostics import ArchitectureResolutionError
from backend.architecture_profiles.five_layer_v2_costing import (
    FORMULA_REF,
    evaluate_five_layer_v2_costs,
    expected_route_owners,
)
from backend.architecture_profiles.five_layer_v2_pricing import (
    RATE_CARD_KEY,
    RATE_CARD_SCHEMA_VERSION,
    FiveLayerV2CatalogCostLedgerResolver,
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


RUN_ID = "018f0f5e-7b5e-7b2d-9f0b-7f66c2a88a01"


def _read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _build(assignment):
    workload = resolve_five_layer_v2_workload(
        _read(WORKLOAD_ROOT / "fixtures" / "valid" / "core-small.json")
    )
    registry = ArchitectureProfileRegistry(profile_version="2")
    evidence = {
        provider: "sha256:" + marker * 64
        for provider, marker in {"aws": "a", "azure": "b", "gcp": "c"}.items()
        if provider in set(assignment.values())
    }
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
        pricing_evidence_digests=evidence,
    )
    return specification, workload


def _meter(dimension, unit, price):
    return {
        "dimension": dimension,
        "unit": unit,
        "billingIncrement": "1",
        "freeQuantity": "0",
        "minimumCharge": "0",
        "tiers": [{"upTo": None, "pricePerUnit": str(price)}],
    }


def _rate_cards(specification, *, missing_component=None):
    cards = {}
    for provider in {
        item["provider"] for item in specification["component_selections"]
    }:
        component_rates = {}
        for selection in specification["component_selections"]:
            if selection["provider"] != provider:
                continue
            component_id = selection["implementation_component_id"]
            if component_id == missing_component:
                continue
            dimensions = {
                item["dimension_id"].rsplit(".", 1)[-1]: item
                for item in selection["dimensions"]
            }
            priced = "resource_count"
            component_rates[component_id] = {
                "variants": [
                    {
                        "selectors": {},
                        "meters": [
                            _meter(
                                priced,
                                dimensions[priced]["unit"],
                                {"aws": "1", "azure": "2", "gcp": "3"}[provider],
                            )
                        ],
                        "nonBillableDimensions": {
                            key: "not_billable_in_bounded_poc_formula"
                            for key in dimensions
                            if key != priced
                        },
                    }
                ]
            }
        route_rates = {}
        for route_class in {
            route.route_class
            for route in expected_route_owners(
                {
                    item["logical_component_id"]: item["provider"]
                    for item in specification["component_selections"]
                    if item["logical_component_id"] in LOGICAL_COMPONENTS
                },
                resolve_five_layer_v2_workload(
                    _read(WORKLOAD_ROOT / "fixtures" / "valid" / "core-small.json")
                ),
            )
        }:
            route_rates[route_class] = {
                "sourceVariants": [
                    {
                        "selectors": {},
                        "meters": [
                            _meter(
                                "cross_cloud_egress_bytes",
                                "bytes/month",
                                "0.000000001",
                            )
                        ],
                        "nonBillableDimensions": {
                            "source_runtime": "priced_in_source_adapter_component"
                        },
                    }
                ],
                "destinationVariants": [
                    {
                        "selectors": {},
                        "meters": [
                            _meter(
                                "destination_operations",
                                "operations/month",
                                "0.000001",
                            )
                        ],
                        "nonBillableDimensions": {},
                    }
                ],
            }
        cards[provider] = {
            RATE_CARD_KEY: {
                "schemaVersion": RATE_CARD_SCHEMA_VERSION,
                "baseCurrency": "USD",
                "currencyConversions": {"USD": "1", "EUR": "0.8"},
                "formulaReference": FORMULA_REF,
                "componentRates": component_rates,
                "routeRates": route_rates,
            }
        }
    return cards


def test_catalog_adapter_builds_reconciling_ledger_from_both_route_catalogs():
    assignment = {
        "component.ingestion": "aws",
        "component.processing": "azure",
        "component.hot-storage": "aws",
        "component.cool-storage": "azure",
        "component.archive-storage": "aws",
        "component.twin-state": "azure",
        "component.visualization": "aws",
    }
    specification, workload = _build(assignment)

    ledger = FiveLayerV2CatalogCostLedgerResolver(_rate_cards(specification)).resolve(
        specification, assignment, workload
    )
    evaluation = evaluate_five_layer_v2_costs(
        specification=specification,
        assignment=assignment,
        resolved_workload=workload,
        cost_ledger=ledger,
    )

    assert evaluation.monthly_total > 0
    assert ledger["route_costs"]
    assert all(
        set(item["pricing_evidence_digests"]) == {"source", "destination"}
        for item in ledger["route_costs"]
    )


def test_catalog_adapter_fails_closed_when_selected_component_rate_is_missing():
    assignment = {logical: "aws" for logical in LOGICAL_COMPONENTS}
    specification, workload = _build(assignment)
    missing = specification["component_selections"][0]["implementation_component_id"]

    with pytest.raises(ArchitectureResolutionError) as raised:
        FiveLayerV2CatalogCostLedgerResolver(
            _rate_cards(specification, missing_component=missing)
        ).resolve(specification, assignment, workload)

    assert raised.value.code == "ARCH_PRICING_EVIDENCE_MISSING"


def test_catalog_adapter_rejects_unowned_component_dimension():
    assignment = {logical: "aws" for logical in LOGICAL_COMPONENTS}
    specification, workload = _build(assignment)
    cards = _rate_cards(specification)
    first = specification["component_selections"][0]
    variant = cards["aws"][RATE_CARD_KEY]["componentRates"][
        first["implementation_component_id"]
    ]["variants"][0]
    variant["nonBillableDimensions"].pop(next(iter(variant["nonBillableDimensions"])))

    with pytest.raises(ArchitectureResolutionError) as raised:
        FiveLayerV2CatalogCostLedgerResolver(cards).resolve(
            specification,
            assignment,
            workload,
        )

    assert raised.value.code == "ARCH_PRICING_EVIDENCE_MISSING"


def test_catalog_adapter_applies_free_quantity_billing_increment_and_tiers():
    assignment = {logical: "aws" for logical in LOGICAL_COMPONENTS}
    specification, workload = _build(assignment)
    cards = _rate_cards(specification)
    first = specification["component_selections"][0]
    variant = cards["aws"][RATE_CARD_KEY]["componentRates"][
        first["implementation_component_id"]
    ]["variants"][0]
    variant["meters"][0].update(
        {
            "billingIncrement": "2",
            "freeQuantity": "0",
            "minimumCharge": "3",
            "tiers": [
                {"upTo": "1", "pricePerUnit": "1"},
                {"upTo": None, "pricePerUnit": "2"},
            ],
        }
    )

    ledger = FiveLayerV2CatalogCostLedgerResolver(cards).resolve(
        specification,
        assignment,
        workload,
    )

    quote = next(
        item
        for item in ledger["component_costs"]
        if item["component_id"] == first["implementation_component_id"]
    )
    assert quote["monthly_amount"] == "3"


def test_catalog_adapter_uses_the_same_pinned_eur_rate_for_every_provider():
    assignment = {
        "component.ingestion": "aws",
        "component.processing": "azure",
        "component.hot-storage": "gcp",
        "component.cool-storage": "aws",
        "component.archive-storage": "azure",
        "component.twin-state": "gcp",
        "component.visualization": "gcp",
    }
    specification, workload = _build(assignment)
    specification["currency"] = "EUR"
    cards = _rate_cards(specification)

    ledger = FiveLayerV2CatalogCostLedgerResolver(cards).resolve(
        specification,
        assignment,
        workload,
    )

    assert ledger["currency"] == "EUR"
    assert all(
        Decimal(item["monthly_amount"]) % Decimal("0.8") == 0
        for item in ledger["component_costs"]
    )
