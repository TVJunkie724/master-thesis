"""
Provider catalog snapshot and pricing candidate extraction.

This module does not decide which price is correct for an optimizer intent.
It preserves provider catalog evidence in a canonical, JSON-serializable shape
so later registry and drift-detection code can make deterministic decisions.
"""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


SNAPSHOT_SCHEMA_VERSION = "pricing-catalog-snapshot.v1"
CANDIDATE_SCHEMA_VERSION = "pricing-candidate.v1"

SECRET_KEY_FRAGMENTS = (
    "secret",
    "token",
    "credential",
    "private_key",
    "access_key",
)


def build_pricing_catalog_snapshot(
    provider: str,
    raw_items: Iterable[Any],
    *,
    source_api: str,
    request_scope: dict[str, Any] | None = None,
    fetched_at: str | None = None,
) -> dict[str, Any]:
    """Build a secrets-free provider catalog snapshot with canonical candidates."""
    normalized_provider = _normalize_provider(provider)
    raw_list = list(raw_items)
    timestamp = fetched_at or _utc_now()
    sanitized_items = [_sanitize_raw_payload(item) for item in raw_list]
    snapshot_id = _snapshot_id(
        normalized_provider,
        source_api,
        request_scope or {},
        sanitized_items,
        timestamp,
    )
    candidates = extract_pricing_candidates(
        normalized_provider,
        sanitized_items,
        source_snapshot_id=snapshot_id,
        fetched_at=timestamp,
    )

    return {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "provider": normalized_provider,
        "snapshot_id": snapshot_id,
        "source_api": source_api,
        "request_scope": request_scope or {},
        "fetched_at": timestamp,
        "raw_item_count": len(sanitized_items),
        "candidate_count": len(candidates),
        "candidates": candidates,
    }


def extract_pricing_candidates(
    provider: str,
    raw_items: Iterable[Any],
    *,
    source_snapshot_id: str,
    fetched_at: str,
) -> list[dict[str, Any]]:
    """Convert provider catalog rows into canonical pricing candidates."""
    normalized_provider = _normalize_provider(provider)
    if normalized_provider == "aws":
        return _extract_aws_candidates(raw_items, source_snapshot_id, fetched_at)
    if normalized_provider == "azure":
        return _extract_azure_candidates(raw_items, source_snapshot_id, fetched_at)
    if normalized_provider == "gcp":
        return _extract_gcp_candidates(raw_items, source_snapshot_id, fetched_at)
    raise ValueError(f"Unsupported provider: {provider}")


def write_pricing_catalog_snapshot(snapshot: dict[str, Any], path: str | Path) -> None:
    """Persist a snapshot without touching calculation pricing files."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(snapshot, indent=2, sort_keys=True))


def _extract_aws_candidates(
    raw_items: Iterable[Any],
    source_snapshot_id: str,
    fetched_at: str,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for item in raw_items:
        product_item = json.loads(item) if isinstance(item, str) else item
        product = product_item.get("product", {})
        attributes = product.get("attributes", {})
        terms = product_item.get("terms", {}).get("OnDemand", {})
        sku = product.get("sku") or attributes.get("sku")

        for offer_term_code, term in terms.items():
            dimensions = term.get("priceDimensions", {})
            for rate_code, dimension in dimensions.items():
                price = _first_price(dimension.get("pricePerUnit", {}))
                candidates.append(
                    _candidate(
                        provider="aws",
                        candidate_id=f"aws:{sku}:{rate_code}",
                        source_snapshot_id=source_snapshot_id,
                        fetched_at=fetched_at,
                        provider_identifiers={
                            "sku": sku,
                            "rate_code": rate_code,
                            "offer_term_code": offer_term_code,
                            "service_code": attributes.get("servicecode"),
                            "usage_type": attributes.get("usagetype"),
                            "operation": attributes.get("operation"),
                        },
                        provider_service=attributes.get("servicecode"),
                        service_name=attributes.get("servicename"),
                        product_name=product.get("productFamily"),
                        sku_name=attributes.get("instanceType") or attributes.get("volumeType"),
                        meter_name=dimension.get("description"),
                        region=attributes.get("location"),
                        unit=dimension.get("unit"),
                        price_type="OnDemand",
                        currency=price["currency"],
                        raw_price=price["amount"],
                        tier={
                            "begin_range": dimension.get("beginRange"),
                            "end_range": dimension.get("endRange"),
                        },
                        evidence={
                            "term_type": "OnDemand",
                            "location_type": attributes.get("locationType"),
                        },
                        raw_payload_ref={
                            "product": product,
                            "price_dimension": dimension,
                        },
                    )
                )
    return candidates


def _extract_azure_candidates(
    raw_items: Iterable[Any],
    source_snapshot_id: str,
    fetched_at: str,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for item in raw_items:
        meter_id = item.get("meterId")
        sku_id = item.get("skuId")
        product_id = item.get("productId")
        tier_minimum_units = item.get("tierMinimumUnits")
        tier_id = "base" if tier_minimum_units is None else str(tier_minimum_units)
        price_type = item.get("priceType") or item.get("type")
        candidates.append(
            _candidate(
                provider="azure",
                candidate_id=(
                    f"azure:{meter_id or item.get('meterName')}:{product_id or '-'}:"
                    f"{sku_id or '-'}:{price_type or '-'}:{tier_id}"
                ),
                source_snapshot_id=source_snapshot_id,
                fetched_at=fetched_at,
                provider_identifiers={
                    "meter_id": meter_id,
                    "sku_id": sku_id,
                    "product_id": product_id,
                    "arm_sku_name": item.get("armSkuName"),
                    "service_id": item.get("serviceId"),
                },
                provider_service=item.get("serviceName"),
                service_name=item.get("serviceName"),
                product_name=item.get("productName"),
                sku_name=item.get("skuName"),
                meter_name=item.get("meterName"),
                region=item.get("armRegionName") or item.get("location"),
                unit=item.get("unitOfMeasure"),
                price_type=price_type,
                currency=item.get("currencyCode"),
                raw_price=_to_float(
                    item.get("retailPrice")
                    if item.get("retailPrice") is not None
                    else item.get("unitPrice")
                ),
                tier={"tier_minimum_units": tier_minimum_units},
                evidence={
                    "is_primary_meter_region": item.get("isPrimaryMeterRegion"),
                    "reservation_term": item.get("reservationTerm"),
                    "effective_start_date": item.get("effectiveStartDate"),
                },
                raw_payload_ref=item,
            )
        )
    return candidates


def _extract_gcp_candidates(
    raw_items: Iterable[Any],
    source_snapshot_id: str,
    fetched_at: str,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for item in raw_items:
        service_id = item.get("serviceId") or item.get("service_id")
        sku_id = item.get("skuId") or item.get("sku_id")
        pricing_info = item.get("pricingInfo") or item.get("pricing_info") or []
        category = item.get("category", {})
        service_regions = item.get("serviceRegions") or item.get("service_regions") or []

        for pricing_index, info in enumerate(pricing_info):
            expression = info.get("pricingExpression") or info.get("pricing_expression") or {}
            tiered_rates = expression.get("tieredRates") or expression.get("tiered_rates") or []
            for tier_index, tier_rate in enumerate(tiered_rates):
                unit_price = tier_rate.get("unitPrice") or tier_rate.get("unit_price") or {}
                candidates.append(
                    _candidate(
                        provider="gcp",
                        candidate_id=f"gcp:{service_id}:{sku_id}:{pricing_index}:{tier_index}",
                        source_snapshot_id=source_snapshot_id,
                        fetched_at=fetched_at,
                        provider_identifiers={
                            "service_id": service_id,
                            "sku_id": sku_id,
                            "pricing_info_index": pricing_index,
                            "tier_index": tier_index,
                        },
                        provider_service=service_id,
                        service_name=item.get("serviceDisplayName") or item.get("service_display_name"),
                        product_name=category.get("resourceFamily"),
                        sku_name=item.get("description"),
                        meter_name=category.get("usageType"),
                        region=",".join(service_regions) if service_regions else None,
                        unit=expression.get("usageUnitDescription")
                        or expression.get("usage_unit_description"),
                        price_type=category.get("usageType"),
                        currency=unit_price.get("currencyCode") or unit_price.get("currency_code"),
                        raw_price=_money_value(unit_price),
                        tier={
                            "start_usage_amount": _first_present(
                                tier_rate,
                                "startUsageAmount",
                                "start_usage_amount",
                            ),
                            "base_unit": expression.get("baseUnit") or expression.get("base_unit"),
                            "base_unit_description": expression.get("baseUnitDescription")
                            or expression.get("base_unit_description"),
                        },
                        evidence={
                            "resource_group": category.get("resourceGroup"),
                            "resource_family": category.get("resourceFamily"),
                            "aggregation_info": item.get("aggregationInfo")
                            or item.get("aggregation_info"),
                        },
                        raw_payload_ref={
                            "sku": item,
                            "pricing_expression": expression,
                            "tiered_rate": tier_rate,
                        },
                    )
                )
    return candidates


def _candidate(
    *,
    provider: str,
    candidate_id: str,
    source_snapshot_id: str,
    fetched_at: str,
    provider_identifiers: dict[str, Any],
    provider_service: Any,
    service_name: Any,
    product_name: Any,
    sku_name: Any,
    meter_name: Any,
    region: Any,
    unit: Any,
    price_type: Any,
    currency: Any,
    raw_price: Any,
    tier: dict[str, Any],
    evidence: dict[str, Any],
    raw_payload_ref: Any,
) -> dict[str, Any]:
    return {
        "schema_version": CANDIDATE_SCHEMA_VERSION,
        "candidate_id": candidate_id,
        "source_snapshot_id": source_snapshot_id,
        "provider": provider,
        "provider_identifiers": _drop_none(provider_identifiers),
        "provider_service": provider_service,
        "service_name": service_name,
        "product_name": product_name,
        "sku_name": sku_name,
        "meter_name": meter_name,
        "region": region,
        "unit": unit,
        "price_type": price_type,
        "currency": currency,
        "raw_price": raw_price,
        "tier": _drop_none(tier),
        "evidence": _drop_none(evidence),
        "fetched_at": fetched_at,
        "raw_payload_ref": _sanitize_raw_payload(raw_payload_ref),
    }


def _first_price(price_per_unit: dict[str, Any]) -> dict[str, Any]:
    for currency, amount in price_per_unit.items():
        return {"currency": currency, "amount": _to_float(amount)}
    return {"currency": None, "amount": None}


def _money_value(unit_price: dict[str, Any]) -> float | None:
    units = unit_price.get("units", 0) or 0
    nanos = unit_price.get("nanos", 0) or 0
    try:
        return float(units) + (float(nanos) / 1_000_000_000)
    except (TypeError, ValueError):
        return None


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _sanitize_raw_payload(value: Any) -> Any:
    if isinstance(value, dict):
        sanitized = {}
        for key, raw in value.items():
            if any(fragment in str(key).lower() for fragment in SECRET_KEY_FRAGMENTS):
                sanitized[key] = "<redacted>"
            else:
                sanitized[key] = _sanitize_raw_payload(raw)
        return sanitized
    if isinstance(value, list):
        return [_sanitize_raw_payload(item) for item in value]
    return value


def _drop_none(values: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in values.items() if value is not None}


def _first_present(values: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in values:
            return values[key]
    return None


def _normalize_provider(provider: str) -> str:
    normalized = provider.lower()
    if normalized not in {"aws", "azure", "gcp"}:
        raise ValueError(f"Unsupported provider: {provider}")
    return normalized


def _snapshot_id(
    provider: str,
    source_api: str,
    request_scope: dict[str, Any],
    raw_items: list[Any],
    fetched_at: str,
) -> str:
    payload = {
        "provider": provider,
        "source_api": source_api,
        "request_scope": request_scope,
        "raw_items": raw_items,
        "fetched_at": fetched_at,
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
    return f"{provider}-{digest[:16]}"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
