"""Canonical transfer-pricing catalog construction and validation."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation
import hashlib
import json
from typing import Any

from backend.calculation_v2.components.types import Provider
from backend.calculation_v2.transfer_pricing import (
    TransferBillingUnit,
    TransferGeography,
    TransferPricingContractError,
    TransferTier,
    TransferTierTable,
)
from backend.pricing_registry import PricingRegistry, load_pricing_registry


TRANSFER_CATALOG_SCHEMA_VERSION = "transfer-pricing-catalog.v1"
TRANSFER_EVIDENCE_SCHEMA_VERSION = "transfer-pricing-evidence.v1"

_EXPECTED_BILLING_UNITS = {
    Provider.AWS: (TransferBillingUnit.GB, 1_000_000_000),
    Provider.AZURE: (TransferBillingUnit.GB, 1_000_000_000),
    Provider.GCP: (TransferBillingUnit.GIB, 1_073_741_824),
}
TRANSFER_CATALOG_FIELDS = (
    "schema_version",
    "route_class",
    "source_region",
    "source_geography",
    "destination_geographies",
    "network_tier",
    "billing_scope",
    "billing_unit",
    "bytes_per_billing_unit",
    "currency",
    "evidence_id",
    "aggregation_semantics",
    "pricing_tiers",
)
_CATALOG_KEYS = {
    *TRANSFER_CATALOG_FIELDS,
}
_TIER_KEYS = {
    "tier_id",
    "start_quantity",
    "end_quantity",
    "unit",
    "unit_price",
}


def build_transfer_catalog(
    *,
    provider: str | Provider,
    pricing_region: str,
    tier_thresholds: Sequence[Mapping[str, Any]],
    evidence_id: str,
    currency: str = "USD",
    free_allowance_quantity: Decimal | int | str | None = None,
    pricing_registry: PricingRegistry | None = None,
) -> dict[str, Any]:
    """Build one strict canonical catalog from cumulative tier thresholds."""

    provider_enum = _provider(provider)
    registry = pricing_registry or load_pricing_registry()
    transfer_registry = registry.transfer_routes
    endpoint_regions = transfer_registry.region_geographies[provider_enum]
    try:
        source_geography = endpoint_regions[pricing_region]
    except KeyError as exc:
        raise TransferPricingContractError(
            "TRANSFER_REGION_UNMAPPED",
            f"no transfer geography for {provider_enum.value}.{pricing_region}",
        ) from exc
    policy = transfer_registry.provider_policies[provider_enum]
    billing_unit, bytes_per_billing_unit = _EXPECTED_BILLING_UNITS[
        provider_enum
    ]
    tiers = _canonical_tiers(
        tier_thresholds,
        billing_unit=billing_unit,
        free_allowance_quantity=free_allowance_quantity,
    )
    table = TransferTierTable(
        tiers=tuple(
            TransferTier(
                tier_id=tier["tier_id"],
                start_quantity=tier["start_quantity"],
                end_quantity=tier["end_quantity"],
                unit_price=tier["unit_price"],
            )
            for tier in tiers
        ),
        billing_unit=billing_unit,
        bytes_per_billing_unit=bytes_per_billing_unit,
        currency=currency,
        evidence_id=evidence_id,
    )
    result = {
        "schema_version": TRANSFER_CATALOG_SCHEMA_VERSION,
        "route_class": "cross_provider_public_internet",
        "source_region": pricing_region,
        "source_geography": source_geography.value,
        "destination_geographies": [
            geography.value for geography in TransferGeography
        ],
        "network_tier": policy.public_route_tier.value,
        "billing_scope": policy.billing_scope.value,
        "billing_unit": table.billing_unit.value,
        "bytes_per_billing_unit": table.bytes_per_billing_unit,
        "currency": table.currency,
        "evidence_id": table.evidence_id,
        "aggregation_semantics": policy.billing_scope.value,
        "pricing_tiers": [
            {
                "tier_id": tier.tier_id,
                "start_quantity": _json_decimal(tier.start_quantity),
                "end_quantity": (
                    None
                    if tier.end_quantity is None
                    else _json_decimal(tier.end_quantity)
                ),
                "unit": table.billing_unit.value,
                "unit_price": _json_decimal(tier.unit_price),
            }
            for tier in table.tiers
        ],
    }
    validate_transfer_catalog(
        provider_enum,
        pricing_region,
        result,
        pricing_registry=registry,
    )
    return result


def validate_transfer_catalog(
    provider: str | Provider,
    pricing_region: str,
    catalog: Any,
    *,
    pricing_registry: PricingRegistry | None = None,
) -> TransferTierTable:
    """Validate one catalog and return its exact domain tier table."""

    provider_enum = _provider(provider)
    if not isinstance(catalog, Mapping):
        _fail("transfer catalog must be an object")
    _exact_keys(catalog, _CATALOG_KEYS, "transfer")
    if catalog["schema_version"] != TRANSFER_CATALOG_SCHEMA_VERSION:
        _fail("transfer schema_version is unsupported")
    if catalog["source_region"] != pricing_region:
        _fail("transfer source_region does not match pricing_region")

    registry = pricing_registry or load_pricing_registry()
    transfer_registry = registry.transfer_routes
    try:
        geography = transfer_registry.region_geographies[provider_enum][
            pricing_region
        ]
    except KeyError as exc:
        raise TransferPricingContractError(
            "TRANSFER_REGION_UNMAPPED",
            f"no transfer geography for {provider_enum.value}.{pricing_region}",
        ) from exc
    policy = transfer_registry.provider_policies[provider_enum]
    expected_unit, expected_bytes = _EXPECTED_BILLING_UNITS[provider_enum]
    expected_values = {
        "route_class": "cross_provider_public_internet",
        "source_geography": geography.value,
        "network_tier": policy.public_route_tier.value,
        "billing_scope": policy.billing_scope.value,
        "billing_unit": expected_unit.value,
        "bytes_per_billing_unit": expected_bytes,
        "currency": "USD",
        "aggregation_semantics": policy.billing_scope.value,
    }
    for key, expected in expected_values.items():
        if catalog[key] != expected:
            _fail(f"transfer {key} must be {expected!r}")

    destinations = catalog["destination_geographies"]
    if not isinstance(destinations, list) or destinations != [
        geography.value for geography in TransferGeography
    ]:
        _fail("transfer destination_geographies are unsupported")
    evidence_id = catalog["evidence_id"]
    if not isinstance(evidence_id, str) or not evidence_id:
        _fail("transfer evidence_id must be a non-empty string")

    raw_tiers = catalog["pricing_tiers"]
    if not isinstance(raw_tiers, list) or not raw_tiers:
        _fail("transfer pricing_tiers must be a non-empty list")
    tiers: list[TransferTier] = []
    for index, raw_tier in enumerate(raw_tiers):
        if not isinstance(raw_tier, Mapping):
            _fail(f"transfer pricing_tiers[{index}] must be an object")
        _exact_keys(raw_tier, _TIER_KEYS, f"transfer.pricing_tiers[{index}]")
        if raw_tier["unit"] != expected_unit.value:
            _fail(
                f"transfer pricing_tiers[{index}].unit must be "
                f"{expected_unit.value!r}"
            )
        tiers.append(
            TransferTier(
                tier_id=raw_tier["tier_id"],
                start_quantity=raw_tier["start_quantity"],
                end_quantity=raw_tier["end_quantity"],
                unit_price=raw_tier["unit_price"],
            )
        )
    return TransferTierTable(
        tiers=tuple(tiers),
        billing_unit=expected_unit,
        bytes_per_billing_unit=expected_bytes,
        currency=catalog["currency"],
        evidence_id=evidence_id,
    )


def build_transfer_evidence(
    *,
    provider: str | Provider,
    pricing_region: str,
    source_type: str,
    source_api: str,
    source_url: str,
    mapping_version: str,
    selected_rows: Sequence[Mapping[str, Any]],
    fetched_at: str,
    evidence_id: str | None = None,
) -> dict[str, Any]:
    """Build bounded, secrets-free evidence for a selected transfer tier series."""

    provider_enum = _provider(provider)
    rows = [dict(row) for row in selected_rows]
    if not rows:
        _fail("transfer evidence requires selected_rows")
    resolved_evidence_id = evidence_id or transfer_evidence_id(
        provider_enum,
        pricing_region,
        mapping_version,
        rows,
    )
    return {
        "schema_version": TRANSFER_EVIDENCE_SCHEMA_VERSION,
        "evidence_id": resolved_evidence_id,
        "provider": provider_enum.value,
        "pricing_region": pricing_region,
        "intent_id": "transfer.egress_gb",
        "source_type": source_type,
        "source_api": source_api,
        "source_url": source_url,
        "mapping_version": mapping_version,
        "selected_rows": rows[:25],
        "selected_row_count": len(rows),
        "fetched_at": fetched_at,
        "review_required": False,
    }


def transfer_evidence_id(
    provider: str | Provider,
    pricing_region: str,
    mapping_version: str,
    selected_rows: Sequence[Mapping[str, Any]],
) -> str:
    provider_enum = _provider(provider)
    identity = {
        "provider": provider_enum.value,
        "pricing_region": pricing_region,
        "mapping_version": mapping_version,
        "selected_rows": list(selected_rows),
    }
    encoded = json.dumps(
        identity,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")
    return f"{provider_enum.value}.transfer.{hashlib.sha256(encoded).hexdigest()}"


def _canonical_tiers(
    tier_thresholds: Sequence[Mapping[str, Any]],
    *,
    billing_unit: TransferBillingUnit,
    free_allowance_quantity: Decimal | int | str | None,
) -> tuple[dict[str, Any], ...]:
    if isinstance(tier_thresholds, (str, bytes)) or not isinstance(
        tier_thresholds,
        Sequence,
    ):
        _fail("transfer tier thresholds must be a sequence")
    parsed: list[tuple[Decimal, Decimal, str]] = []
    for index, raw in enumerate(tier_thresholds):
        if not isinstance(raw, Mapping):
            _fail(f"transfer tier threshold {index} must be an object")
        unknown = set(raw) - {"start_quantity", "unit_price", "tier_id"}
        missing = {"start_quantity", "unit_price"} - set(raw)
        if missing or unknown:
            _fail(
                f"transfer tier threshold {index} has invalid fields"
            )
        start = _decimal(raw["start_quantity"], "start_quantity")
        price = _decimal(raw["unit_price"], "unit_price")
        tier_id = raw.get("tier_id") or f"provider-tier-{index + 1}"
        if not isinstance(tier_id, str) or not tier_id:
            _fail(f"transfer tier threshold {index} tier_id is invalid")
        parsed.append((start, price, tier_id))
    if not parsed:
        _fail("transfer tier thresholds must not be empty")
    if parsed != sorted(parsed, key=lambda item: item[0]):
        _fail("transfer tier thresholds must be sorted")
    if len({start for start, _, _ in parsed}) != len(parsed):
        _fail("transfer tier thresholds must have unique starts")
    if parsed[0][0] != Decimal("0"):
        _fail("transfer tier thresholds must start at zero")

    allowance = (
        None
        if free_allowance_quantity is None
        else _decimal(free_allowance_quantity, "free_allowance_quantity")
    )
    if allowance == Decimal("0"):
        allowance = None
    if allowance is not None:
        first_start, first_price, first_id = parsed[0]
        if first_price == Decimal("0"):
            if len(parsed) < 2 or parsed[1][0] != allowance:
                _fail(
                    "provider free tier does not match the reviewed allowance"
                )
        else:
            if len(parsed) > 1 and parsed[1][0] <= allowance:
                _fail(
                    "reviewed free allowance overlaps the next provider tier"
                )
            parsed = [
                (Decimal("0"), Decimal("0"), "free-allowance"),
                (allowance, first_price, first_id),
                *parsed[1:],
            ]

    tiers: list[dict[str, Any]] = []
    for index, (start, price, tier_id) in enumerate(parsed):
        end = parsed[index + 1][0] if index + 1 < len(parsed) else None
        tiers.append(
            {
                "tier_id": tier_id,
                "start_quantity": start,
                "end_quantity": end,
                "unit": billing_unit.value,
                "unit_price": price,
            }
        )
    return tuple(tiers)


def _provider(value: str | Provider) -> Provider:
    if isinstance(value, Provider):
        return value
    try:
        return Provider(value)
    except (TypeError, ValueError) as exc:
        raise TransferPricingContractError(
            "TRANSFER_PROVIDER_INVALID",
            f"unsupported transfer provider {value!r}",
        ) from exc


def _decimal(value: Any, label: str) -> Decimal:
    if isinstance(value, bool):
        _fail(f"{label} must be a finite non-negative number")
    try:
        normalized = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise TransferPricingContractError(
            "TRANSFER_CATALOG_INVALID",
            f"{label} must be a finite non-negative number",
        ) from exc
    if not normalized.is_finite() or normalized < 0:
        _fail(f"{label} must be a finite non-negative number")
    return normalized


def _json_decimal(value: Decimal) -> int | float:
    if value == value.to_integral_value():
        return int(value)
    return float(value)


def _exact_keys(
    value: Mapping[str, Any],
    expected: set[str],
    label: str,
) -> None:
    missing = expected - set(value)
    unknown = set(value) - expected
    if missing:
        _fail(f"{label} is missing fields: {', '.join(sorted(missing))}")
    if unknown:
        _fail(
            f"{label} has unknown fields: "
            + ", ".join(sorted(str(item) for item in unknown))
        )


def _fail(message: str) -> None:
    raise TransferPricingContractError(
        "TRANSFER_CATALOG_INVALID",
        message,
    )
