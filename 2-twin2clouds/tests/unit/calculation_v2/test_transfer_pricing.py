from decimal import Decimal
from typing import Any

import pytest

from backend.calculation_v2.components.types import LayerType, Provider
from backend.calculation_v2.transfer_pricing import (
    TransferBillingScope,
    TransferBillingUnit,
    TransferEndpoint,
    TransferGeography,
    TransferNetworkTier,
    TransferPricingContractError,
    TransferPricingPool,
    TransferRouteClass,
    TransferRouteIntent,
    TransferTier,
    TransferTierTable,
    allocate_transfer_pool,
)


def _endpoint(
    layer: LayerType,
    provider: Provider,
    region: str,
) -> TransferEndpoint:
    return TransferEndpoint(
        layer=layer,
        provider=provider,
        region=region,
        geography=TransferGeography.EUROPE,
    )


def _route(
    segment_id: str,
    volume_bytes: Any,
    *,
    source_provider: Provider = Provider.AWS,
    destination_provider: Provider = Provider.AZURE,
) -> TransferRouteIntent:
    source_regions = {
        Provider.AWS: "eu-central-1",
        Provider.AZURE: "westeurope",
        Provider.GCP: "europe-west1",
    }
    return TransferRouteIntent(
        segment_id=segment_id,
        source=_endpoint(
            LayerType.L1_INGESTION,
            source_provider,
            source_regions[source_provider],
        ),
        destination=_endpoint(
            LayerType.L2_PROCESSING,
            destination_provider,
            source_regions[destination_provider],
        ),
        route_class=TransferRouteClass.CROSS_PROVIDER_PUBLIC_INTERNET,
        network_tier=TransferNetworkTier.PROVIDER_DEFAULT,
        volume_bytes=volume_bytes,
        assumptions=("legacy KB inputs use 1024 bytes",),
    )


def _table(
    *,
    billing_unit: TransferBillingUnit = TransferBillingUnit.GB,
    bytes_per_billing_unit: int = 1_000_000_000,
) -> TransferTierTable:
    return TransferTierTable(
        tiers=(
            TransferTier("free", Decimal("0"), Decimal("1"), Decimal("0")),
            TransferTier("paid", Decimal("1"), Decimal("3"), Decimal("0.10")),
            TransferTier("terminal", Decimal("3"), None, Decimal("0.05")),
        ),
        billing_unit=billing_unit,
        bytes_per_billing_unit=bytes_per_billing_unit,
        currency="USD",
        evidence_id="aws.transfer.egress.europe.v1",
    )


def _pool(table: TransferTierTable | None = None) -> TransferPricingPool:
    return TransferPricingPool(
        pool_id="aws.public-egress.europe",
        provider=Provider.AWS,
        route_class=TransferRouteClass.CROSS_PROVIDER_PUBLIC_INTERNET,
        source_geography=TransferGeography.EUROPE,
        destination_geography=TransferGeography.EUROPE,
        network_tier=TransferNetworkTier.PROVIDER_DEFAULT,
        billing_scope=TransferBillingScope.ACCOUNT_AGGREGATE_PUBLIC_EGRESS,
        catalog_snapshot_id=f"pcs_{'a' * 64}",
        evidence_id="aws.transfer.egress.europe.v1",
        tier_table=table or _table(),
    )


def test_tier_table_preserves_exact_boundaries_and_terminal_tier():
    table = _table()

    assert table.cost_between("0", "1") == Decimal("0")
    assert table.cost_between("0", "3") == Decimal("0.20")
    assert table.cost_between("0", "4") == Decimal("0.25")
    assert table.cost_between("1", "3") == Decimal("0.20")

    contributions = table.contributions_between("0.5", "3.5")
    assert [item.tier_id for item in contributions] == [
        "free",
        "paid",
        "terminal",
    ]
    assert sum(
        (item.cost for item in contributions),
        Decimal("0"),
    ) == Decimal("0.225")


def test_billing_units_convert_from_canonical_bytes_without_ambiguous_gb():
    gb_table = _table()
    gib_table = _table(
        billing_unit=TransferBillingUnit.GIB,
        bytes_per_billing_unit=1_073_741_824,
    )

    assert gb_table.quantity_for_bytes(1_000_000_000) == Decimal("1")
    assert gib_table.quantity_for_bytes(1_073_741_824) == Decimal("1")
    assert gib_table.quantity_for_bytes(1_000_000_000) != Decimal("1")


@pytest.mark.parametrize(
    "tiers, expected_message",
    [
        (
            (
                TransferTier("first", 1, 2, 0),
                TransferTier("terminal", 2, None, 1),
            ),
            "first tier must start at zero",
        ),
        (
            (
                TransferTier("first", 0, 1, 0),
                TransferTier("terminal", 2, None, 1),
            ),
            "ordered, contiguous, and non-overlapping",
        ),
        (
            (
                TransferTier("first", 0, None, 0),
                TransferTier("terminal", 1, None, 1),
            ),
            "only the last tier may be open-ended",
        ),
        (
            (
                TransferTier("first", 0, 1, 0),
                TransferTier("last", 1, 2, 1),
            ),
            "terminal open-ended tier",
        ),
    ],
)
def test_tier_table_rejects_malformed_ranges(tiers, expected_message):
    with pytest.raises(TransferPricingContractError, match=expected_message):
        TransferTierTable(
            tiers=tiers,
            billing_unit=TransferBillingUnit.GB,
            bytes_per_billing_unit=1_000_000_000,
            currency="USD",
            evidence_id="evidence.v1",
        )


@pytest.mark.parametrize("value", [-1, float("inf"), float("nan"), True, "bad"])
def test_transfer_quantities_must_be_finite_non_negative(value):
    with pytest.raises(
        TransferPricingContractError,
        match="finite non-negative",
    ):
        _route("L1_to_L2", value)


def test_route_contract_rejects_endpoint_class_mismatch():
    source = _endpoint(
        LayerType.L1_INGESTION,
        Provider.AWS,
        "eu-central-1",
    )
    destination = _endpoint(
        LayerType.L2_PROCESSING,
        Provider.AWS,
        "eu-central-1",
    )

    with pytest.raises(
        TransferPricingContractError,
        match="route_class must be 'same_provider_same_region'",
    ):
        TransferRouteIntent(
            segment_id="L1_to_L2",
            source=source,
            destination=destination,
            route_class=TransferRouteClass.CROSS_PROVIDER_PUBLIC_INTERNET,
            network_tier=TransferNetworkTier.PROVIDER_DEFAULT,
            volume_bytes=1,
        )


def test_domain_contracts_reject_untyped_enums_and_assumption_strings():
    source = _endpoint(
        LayerType.L1_INGESTION,
        Provider.AWS,
        "eu-central-1",
    )
    destination = _endpoint(
        LayerType.L2_PROCESSING,
        Provider.AZURE,
        "westeurope",
    )

    with pytest.raises(
        TransferPricingContractError,
        match="route_class must be a TransferRouteClass",
    ):
        TransferRouteIntent(
            segment_id="L1_to_L2",
            source=source,
            destination=destination,
            route_class="cross_provider_public_internet",
            network_tier=TransferNetworkTier.PROVIDER_DEFAULT,
            volume_bytes=1,
        )

    with pytest.raises(
        TransferPricingContractError,
        match="assumptions must be a sequence",
    ):
        TransferRouteIntent(
            segment_id="L1_to_L2",
            source=source,
            destination=destination,
            route_class=TransferRouteClass.CROSS_PROVIDER_PUBLIC_INTERNET,
            network_tier=TransferNetworkTier.PROVIDER_DEFAULT,
            volume_bytes=1,
            assumptions="not-a-sequence",
        )


def test_pool_allocation_applies_free_allowance_once_and_reconciles():
    pool = _pool()
    routes = (
        _route("L1_to_L2", 750_000_000),
        _route("L2_to_L3_hot", 750_000_000),
        _route("L3_hot_to_L4", 2_000_000_000),
    )

    charges = allocate_transfer_pool(
        pool,
        routes,
        glue_costs={"L3_hot_to_L4": "0.03"},
    )

    assert [charge.egress_cost for charge in charges] == [
        Decimal("0"),
        Decimal("0.0500"),
        Decimal("0.1750"),
    ]
    assert sum(
        (charge.egress_cost for charge in charges),
        Decimal("0"),
    ) == pool.tier_table.cost_for_bytes(3_500_000_000)
    assert charges[-1].total_cost == Decimal("0.2050")
    assert allocate_transfer_pool(pool, routes) == allocate_transfer_pool(
        pool,
        routes,
    )


def test_pool_allocation_rejects_duplicate_segments_and_pool_mismatch():
    route = _route("L1_to_L2", 1)
    with pytest.raises(
        TransferPricingContractError,
        match="segment IDs must be unique",
    ):
        allocate_transfer_pool(_pool(), (route, route))

    azure_route = _route(
        "L1_to_L2",
        1,
        source_provider=Provider.AZURE,
        destination_provider=Provider.AWS,
    )
    with pytest.raises(
        TransferPricingContractError,
        match="source provider does not match pool",
    ):
        allocate_transfer_pool(_pool(), (azure_route,))
