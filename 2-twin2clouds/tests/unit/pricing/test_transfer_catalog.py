from copy import deepcopy
from decimal import Decimal

import pytest

from backend.calculation_v2.engine import _calculate_egress_cost
from backend.calculation_v2.transfer_pricing import (
    TransferPricingContractError,
)
from backend.transfer_catalog import (
    TRANSFER_CATALOG_SCHEMA_VERSION,
    build_transfer_catalog,
    build_transfer_evidence,
    validate_transfer_catalog,
)
from tests.unit.pricing.transfer_fixtures import canonical_transfer_catalog


def _thresholds():
    return [
        {"tier_id": "free", "start_quantity": 0, "unit_price": 0},
        {"tier_id": "paid-1", "start_quantity": 100, "unit_price": 0.087},
        {"tier_id": "paid-2", "start_quantity": 10_335, "unit_price": 0.083},
        {"tier_id": "terminal", "start_quantity": 51_295, "unit_price": 0.07},
    ]


def test_azure_catalog_builds_explicit_decimal_gb_ranges():
    catalog = build_transfer_catalog(
        provider="azure",
        pricing_region="westeurope",
        tier_thresholds=_thresholds(),
        evidence_id="azure.transfer.evidence",
    )

    assert catalog["schema_version"] == TRANSFER_CATALOG_SCHEMA_VERSION
    assert catalog["billing_unit"] == "gb"
    assert catalog["bytes_per_billing_unit"] == 1_000_000_000
    assert catalog["network_tier"] == "microsoft_premium_global_network"
    assert catalog["pricing_tiers"][0] == {
        "tier_id": "free",
        "start_quantity": 0,
        "end_quantity": 100,
        "unit": "gb",
        "unit_price": 0,
    }
    assert catalog["pricing_tiers"][-1]["end_quantity"] is None
    table = validate_transfer_catalog("azure", "westeurope", catalog)
    assert table.cost_between(0, 100) == Decimal("0")
    assert table.cost_between(100, 101) == Decimal("0.087")


def test_gcp_catalog_uses_gib_and_adds_reviewed_one_gib_allowance_once():
    catalog = build_transfer_catalog(
        provider="gcp",
        pricing_region="europe-west1",
        tier_thresholds=[
            {"start_quantity": 0, "unit_price": 0.12},
            {"start_quantity": 1024, "unit_price": 0.11},
            {"start_quantity": 10240, "unit_price": 0.085},
        ],
        free_allowance_quantity=1,
        evidence_id="gcp.transfer.evidence",
    )

    assert catalog["billing_unit"] == "gib"
    assert catalog["bytes_per_billing_unit"] == 1_073_741_824
    assert [
        (tier["start_quantity"], tier["end_quantity"], tier["unit_price"])
        for tier in catalog["pricing_tiers"]
    ] == [
        (0, 1, 0),
        (1, 1024, 0.12),
        (1024, 10240, 0.11),
        (10240, None, 0.085),
    ]


def test_aws_catalog_adds_reviewed_allowance_without_repeating_paid_tier():
    catalog = build_transfer_catalog(
        provider="aws",
        pricing_region="eu-central-1",
        tier_thresholds=[
            {"start_quantity": 0, "unit_price": 0.09},
            {"start_quantity": 10240, "unit_price": 0.085},
            {"start_quantity": 51200, "unit_price": 0.07},
            {"start_quantity": 153600, "unit_price": 0.05},
        ],
        free_allowance_quantity=100,
        evidence_id="aws.transfer.evidence",
    )

    assert [
        (tier["start_quantity"], tier["end_quantity"], tier["unit_price"])
        for tier in catalog["pricing_tiers"][:3]
    ] == [
        (0, 100, 0),
        (100, 10240, 0.09),
        (10240, 51200, 0.085),
    ]


@pytest.mark.parametrize(
    "mutation, expected",
    [
        (lambda value: value.update({"egressPrice": 0.09}), "unknown fields"),
        (
            lambda value: value.update({"bytes_per_billing_unit": 1024}),
            "bytes_per_billing_unit must be 1000000000",
        ),
        (
            lambda value: value["pricing_tiers"][1].update(
                {"start_quantity": 101}
            ),
            "contiguous",
        ),
        (
            lambda value: value.update({"network_tier": "standard"}),
            "network_tier must be",
        ),
    ],
)
def test_catalog_validation_fails_closed_for_contract_drift(
    mutation,
    expected,
):
    catalog = build_transfer_catalog(
        provider="azure",
        pricing_region="westeurope",
        tier_thresholds=_thresholds(),
        evidence_id="azure.transfer.evidence",
    )
    altered = deepcopy(catalog)
    mutation(altered)

    with pytest.raises(TransferPricingContractError, match=expected):
        validate_transfer_catalog("azure", "westeurope", altered)


def test_evidence_identity_is_deterministic_and_bounded():
    rows = [
        {"meterId": f"meter-{index}", "tierMinimumUnits": index * 100}
        for index in range(30)
    ]
    first = build_transfer_evidence(
        provider="azure",
        pricing_region="westeurope",
        source_type="provider_api",
        source_api="azure-retail-prices",
        source_url="https://prices.azure.com/",
        mapping_version="2026.07.18",
        selected_rows=rows,
        fetched_at="2026-07-18T00:00:00Z",
    )
    second = build_transfer_evidence(
        provider="azure",
        pricing_region="westeurope",
        source_type="provider_api",
        source_api="azure-retail-prices",
        source_url="https://prices.azure.com/",
        mapping_version="2026.07.18",
        selected_rows=rows,
        fetched_at="2026-07-18T00:00:00Z",
    )

    assert first["evidence_id"] == second["evidence_id"]
    assert first["selected_row_count"] == 30
    assert len(first["selected_rows"]) == 25


@pytest.mark.parametrize("provider", ["AWS", "Azure", "GCP"])
def test_runtime_calculation_requires_canonical_catalog_for_every_provider(provider):
    provider_key = provider.lower()

    with pytest.raises(ValueError, match=rf"{provider_key}\.transfer\.catalog"):
        _calculate_egress_cost(
            data_gb=1,
            pricing={provider_key: {}},
            source_provider=provider,
        )


def test_runtime_calculation_rejects_tampered_provider_unit_contract():
    catalog = canonical_transfer_catalog("gcp")
    catalog["bytes_per_billing_unit"] = 1_000_000_000

    with pytest.raises(ValueError, match="gcp.transfer.catalog"):
        _calculate_egress_cost(
            data_gb=1,
            pricing={"gcp": {"transfer": catalog}},
            source_provider="GCP",
        )


@pytest.mark.parametrize("data_gb", [-1, float("inf"), float("nan"), True])
def test_runtime_calculation_rejects_invalid_transfer_volume(data_gb):
    with pytest.raises(ValueError, match="data_gb"):
        _calculate_egress_cost(
            data_gb=data_gb,
            pricing={"aws": {"transfer": canonical_transfer_catalog("aws")}},
            source_provider="AWS",
        )


@pytest.mark.parametrize("provider", [None, 1, "unknown"])
def test_runtime_calculation_rejects_unknown_provider(provider):
    with pytest.raises(ValueError, match="provider"):
        _calculate_egress_cost(
            data_gb=1,
            pricing={},
            source_provider=provider,
        )
