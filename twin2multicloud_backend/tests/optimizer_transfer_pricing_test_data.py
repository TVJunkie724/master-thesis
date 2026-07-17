"""Deterministic valid Optimizer transfer evidence for Management tests."""

from __future__ import annotations

from collections import defaultdict

from src.schemas.pricing_catalog import PricingCatalogContext
from tests.pricing_catalog_test_data import catalog_context


EDGES = (
    ("L1_to_L2", "L1", "L2", "L1_INGESTION", "L2_PROCESSING"),
    (
        "L2_to_L3_hot",
        "L2",
        "L3_hot",
        "L2_PROCESSING",
        "L3_HOT_STORAGE",
    ),
    (
        "L3_hot_to_L3_cool",
        "L3_hot",
        "L3_cool",
        "L3_HOT_STORAGE",
        "L3_COOL_STORAGE",
    ),
    (
        "L3_cool_to_L3_archive",
        "L3_cool",
        "L3_archive",
        "L3_COOL_STORAGE",
        "L3_ARCHIVE_STORAGE",
    ),
    (
        "L3_hot_to_L4",
        "L3_hot",
        "L4",
        "L3_HOT_STORAGE",
        "L4_TWIN_MANAGEMENT",
    ),
    (
        "L4_to_L5",
        "L4",
        "L5",
        "L4_TWIN_MANAGEMENT",
        "L5_VISUALIZATION",
    ),
)
PROVIDER_DATA = {
    "aws": {
        "networkTier": "provider_default",
        "billingScope": "account_aggregate_public_egress",
        "billingUnit": "gb",
        "bytesPerBillingUnit": 1_000_000_000,
    },
    "azure": {
        "networkTier": "microsoft_premium_global_network",
        "billingScope": "account_aggregate_public_egress",
        "billingUnit": "gb",
        "bytesPerBillingUnit": 1_000_000_000,
    },
    "gcp": {
        "networkTier": "premium",
        "billingScope": "sku_account_aggregate_public_egress",
        "billingUnit": "gib",
        "bytesPerBillingUnit": 1_073_741_824,
    },
}
_LABELS = {"AWS": "aws", "Azure": "azure", "GCP": "gcp"}


def transfer_pricing_result_fields(
    calculation_result: dict,
    *,
    total_cost: float = 14.75,
    currency: str = "USD",
    context: PricingCatalogContext | None = None,
) -> dict:
    """Build one internally consistent zero-priced transfer result."""

    context = context or catalog_context()
    selected = _selected(calculation_result)
    cumulative_quantity = defaultdict(float)
    routes = []
    routes_by_provider = defaultdict(list)

    for index, (
        segment_id,
        source_key,
        destination_key,
        source_layer,
        destination_layer,
    ) in enumerate(EDGES, start=1):
        source_provider = selected[source_key]
        destination_provider = selected[destination_key]
        same_provider = source_provider == destination_provider
        policy = PROVIDER_DATA[source_provider]
        volume_bytes = policy["bytesPerBillingUnit"]
        route = {
            "segmentId": segment_id,
            "source": _endpoint(source_layer, source_provider, context),
            "destination": _endpoint(
                destination_layer,
                destination_provider,
                context,
            ),
            "routeClass": (
                "same_provider_same_region"
                if same_provider
                else "cross_provider_public_internet"
            ),
            "networkTier": (
                "not_applicable"
                if same_provider
                else policy["networkTier"]
            ),
            "volumeBytes": volume_bytes,
            "poolId": None,
            "catalogSnapshotId": None,
            "evidenceId": None,
            "tierContributions": [],
            "egressCost": 0.0,
            "glueCost": 0.0,
            "totalCost": 0.0,
            "assumptions": [f"fixture_edge={segment_id}"],
        }
        if not same_provider:
            pool_id = f"pool:{source_provider}:test"
            evidence_id = f"transfer.{source_provider}.test.v1"
            start = cumulative_quantity[source_provider]
            end = start + 1.0
            cumulative_quantity[source_provider] = end
            route.update(
                {
                    "poolId": pool_id,
                    "catalogSnapshotId": (
                        context.catalogs[source_provider].snapshot_id
                    ),
                    "evidenceId": evidence_id,
                    "tierContributions": [
                        {
                            "tierId": f"free_{index}",
                            "fromQuantity": start,
                            "toQuantity": end,
                            "billableQuantity": 1.0,
                            "unitPrice": 0.0,
                            "cost": 0.0,
                        }
                    ],
                }
            )
            routes_by_provider[source_provider].append(route)
        routes.append(route)

    pools = []
    for provider in ("aws", "azure", "gcp"):
        provider_routes = routes_by_provider.get(provider)
        if not provider_routes:
            continue
        policy = PROVIDER_DATA[provider]
        pools.append(
            {
                "poolId": f"pool:{provider}:test",
                "provider": provider,
                "routeClass": "cross_provider_public_internet",
                "sourceGeography": "europe",
                "destinationGeography": "europe",
                "networkTier": policy["networkTier"],
                "billingScope": policy["billingScope"],
                "billingUnit": policy["billingUnit"],
                "bytesPerBillingUnit": policy["bytesPerBillingUnit"],
                "catalogSnapshotId": context.catalogs[provider].snapshot_id,
                "evidenceId": f"transfer.{provider}.test.v1",
                "aggregateVolumeBytes": sum(
                    route["volumeBytes"] for route in provider_routes
                ),
                "aggregateEgressCost": 0.0,
            }
        )

    candidate_id = "|".join(
        selected[key]
        for key in (
            "L1",
            "L2",
            "L3_hot",
            "L3_cool",
            "L3_archive",
            "L4",
            "L5",
        )
    )
    return {
        "transferCosts": {
            route["segmentId"]: route["totalCost"]
            for route in routes
            if route["routeClass"] == "cross_provider_public_internet"
        },
        "transferPricingContext": {
            "schemaVersion": "complete-path-transfer-pricing.v1",
            "currency": currency,
            "assumptions": ["deterministic_management_contract_fixture"],
            "routes": routes,
            "pools": pools,
        },
        "optimizationDiagnostics": {
            "schemaVersion": "complete-path-optimization.v1",
            "enumeratedPathCount": 972,
            "evaluatedPathCount": 972,
            "rejectedPathCount": 0,
            "rejectedByErrorCode": {},
            "winningCandidateId": candidate_id,
            "winningScore": total_cost,
            "winningLayerCost": total_cost,
            "winningTransferCost": 0.0,
            "tieBreakPolicy": "canonical_provider_order",
            "canonicalProviderOrder": ["aws", "azure", "gcp"],
            "scoreUnit": f"{currency}/month",
        },
    }


def optimizer_transfer_result(
    *,
    calculation_result: dict | None = None,
    total_cost: float = 14.75,
) -> dict:
    calculation_result = calculation_result or {
        "L1": "AWS",
        "L2": "Azure",
        "L3": {"Hot": "GCP", "Cool": "AWS", "Archive": "Azure"},
        "L4": "Azure",
        "L5": "Azure",
    }
    return {
        "calculationResult": calculation_result,
        "totalCost": total_cost,
        "currency": "USD",
        **transfer_pricing_result_fields(
            calculation_result,
            total_cost=total_cost,
        ),
    }


def _selected(calculation_result: dict) -> dict[str, str]:
    l3 = calculation_result["L3"]
    return {
        "L1": _LABELS[calculation_result["L1"]],
        "L2": _LABELS[calculation_result["L2"]],
        "L3_hot": _LABELS[l3["Hot"]],
        "L3_cool": _LABELS[l3["Cool"]],
        "L3_archive": _LABELS[l3["Archive"]],
        "L4": _LABELS[calculation_result["L4"]],
        "L5": _LABELS[calculation_result["L5"]],
    }


def _endpoint(
    layer: str,
    provider: str,
    context: PricingCatalogContext,
) -> dict:
    return {
        "layer": layer,
        "provider": provider,
        "region": context.catalogs[provider].pricing_region,
        "geography": "europe",
    }
