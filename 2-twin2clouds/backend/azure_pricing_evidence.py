"""Azure pricing evidence report builder.

This module converts Azure Retail Prices rows into inspectable evidence records.
It does not decide calculation formulas and does not write calculation pricing.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from backend.pricing_catalog_candidates import build_pricing_catalog_snapshot
from backend.pricing_evidence import FETCHED, NOT_APPLICABLE
from backend.pricing_intent_registry import (
    AMBIGUOUS,
    CHANGED,
    MATCHED,
    MAPPING_SCHEMA_VERSION,
    MISSING,
    match_pricing_intent,
)
from backend.pricing_registry_service import PricingRegistryService


AZURE_EVIDENCE_REPORT_SCHEMA_VERSION = "azure-pricing-evidence-report.v1"
AZURE_RETAIL_API = "azure-retail-prices"
MAX_REJECTED_ROWS = 25


def build_azure_intent_evidence(
    raw_rows: Iterable[dict[str, Any]],
    *,
    intent_id: str,
    region: str,
    pricing_registry_service: PricingRegistryService | None = None,
    fetched_at: str | None = None,
) -> dict[str, Any]:
    """Select and normalize one Azure intent through the canonical registry."""
    registry_service = pricing_registry_service or PricingRegistryService()
    scope = {"provider": "azure", "region": region}
    snapshot = build_pricing_catalog_snapshot(
        "azure",
        raw_rows,
        source_api=AZURE_RETAIL_API,
        request_scope=scope,
        fetched_at=fetched_at,
    )
    mapping = registry_service.get_provider_mapping("azure", intent_id)
    result = match_pricing_intent(
        snapshot["candidates"],
        _intent_match_mapping(mapping, region=region),
    )
    candidate_lookup = {
        candidate.get("candidate_id"): candidate
        for candidate in snapshot["candidates"]
    }
    return _evidence_record(
        result,
        mapping=mapping,
        normalization_rules=registry_service.list_normalization_rules(),
        registry_version=registry_service.get_registry_version(),
        request_scope=scope,
        fetched_at=snapshot["fetched_at"],
        candidate_lookup=candidate_lookup,
    )


def build_azure_pricing_evidence_report(
    raw_rows: Iterable[dict[str, Any]],
    *,
    region: str,
    pricing_registry_service: PricingRegistryService | None = None,
    fetched_at: str | None = None,
    request_scope: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a deterministic Azure evidence report from Retail Prices rows."""
    registry_service = pricing_registry_service or PricingRegistryService()
    scope = {
        "provider": "azure",
        "region": region,
        **(request_scope or {}),
    }
    snapshot = build_pricing_catalog_snapshot(
        "azure",
        raw_rows,
        source_api=AZURE_RETAIL_API,
        request_scope=scope,
        fetched_at=fetched_at,
    )
    mappings = registry_service.list_provider_mappings("azure")
    normalization_rules = registry_service.list_normalization_rules()
    registry_version = registry_service.get_registry_version()

    records = []
    match_results = {}
    candidate_lookup = {
        candidate.get("candidate_id"): candidate
        for candidate in snapshot["candidates"]
    }
    for intent_id in sorted(mappings):
        mapping = mappings[intent_id]
        match_mapping = _intent_match_mapping(mapping, region=region)
        result = match_pricing_intent(snapshot["candidates"], match_mapping)
        match_results[intent_id] = result
        records.append(
            _evidence_record(
                result,
                mapping=mapping,
                normalization_rules=normalization_rules,
                registry_version=registry_version,
                request_scope=scope,
                fetched_at=snapshot["fetched_at"],
                candidate_lookup=candidate_lookup,
            )
        )

    review_required = any(record["review_required"] for record in records)
    return {
        "schema_version": AZURE_EVIDENCE_REPORT_SCHEMA_VERSION,
        "provider": "azure",
        "region": region,
        "source_api": AZURE_RETAIL_API,
        "request_scope": scope,
        "registry_version": registry_version,
        "snapshot": snapshot,
        "match_results": match_results,
        "records": records,
        "record_count": len(records),
        "review_required": review_required,
    }


def write_azure_pricing_evidence_report(report: dict[str, Any], path: str | Path) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2, sort_keys=True))


def _intent_match_mapping(
    mapping: dict[str, Any],
    *,
    region: str,
) -> dict[str, Any]:
    match = dict(mapping.get("match") or {})
    match["region"] = region
    return {
        "schema_version": MAPPING_SCHEMA_VERSION,
        "mapping_version": mapping.get("mapping_version"),
        "intent_id": mapping.get("intent_id"),
        "provider": "azure",
        "review_status": mapping.get("review_status"),
        "match": match,
        "drift_markers": mapping.get("drift_markers") or {},
        "selection_mode": mapping.get("selection_mode", "single"),
        "normalization": {
            "rule_id": mapping.get("normalization_rule"),
        },
    }


def _evidence_record(
    result: dict[str, Any],
    *,
    mapping: dict[str, Any],
    normalization_rules: dict[str, dict[str, Any]],
    registry_version: str,
    request_scope: dict[str, Any],
    fetched_at: str,
    candidate_lookup: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    status = result["status"]
    selected = result.get("selected_candidate")
    selected_full = candidate_lookup.get(selected.get("candidate_id")) if selected else None
    selected_evidence = selected_full or selected
    selected_series = [
        candidate_lookup.get(candidate.get("candidate_id"), candidate)
        for candidate in (result.get("selected_candidates") or [])
    ]
    normalization_rule_id = mapping.get("normalization_rule")
    normalization_rule = normalization_rules.get(normalization_rule_id, {})
    normalized_value = _normalized_value(selected_evidence, normalization_rule)
    normalized_tiers = _normalized_tiers(selected_series)
    review_required = status != MATCHED or mapping.get("review_status") != "reviewed"

    return {
        "schema_version": "pricing-evidence.v1",
        "provider": "azure",
        "intent_id": mapping.get("intent_id"),
        "field_path": mapping.get("intent_id"),
        "source_type": FETCHED if selected or selected_series else NOT_APPLICABLE,
        "source_api": AZURE_RETAIL_API,
        "request_scope": request_scope,
        "retail_api_filter": mapping.get("match") or {},
        "normalization_rule": normalization_rule_id,
        "normalization": normalization_rule,
        "normalized_value": normalized_value,
        "normalized_tiers": normalized_tiers,
        "currency": (
            selected_evidence.get("currency")
            if selected_evidence
            else _uniform_value(selected_series, "currency")
        ),
        "mapping_version": mapping.get("mapping_version"),
        "registry_version": registry_version,
        "fetched_at": fetched_at,
        "review_required": review_required,
        "match_status": status,
        "selected_row": _selected_row(selected_evidence),
        "selected_rows": [_selected_row(candidate) for candidate in selected_series],
        "tier": selected_evidence.get("tier") if selected_evidence else None,
        "candidate_rows": result.get("candidates") or [],
        "rejected_rows": _rejected_rows(
            result.get("rejections") or [], candidate_lookup
        )[:MAX_REJECTED_ROWS],
        "errors": _status_errors(status, mapping.get("intent_id")),
        "review_status": mapping.get("review_status"),
    }


def _normalized_value(
    selected: dict[str, Any] | None,
    normalization_rule: dict[str, Any],
) -> float | None:
    if not selected:
        return None
    raw_price = selected.get("raw_price")
    multiplier = normalization_rule.get("multiplier", 1)
    if not isinstance(raw_price, (int, float)) or not isinstance(multiplier, (int, float)):
        return None
    return float(raw_price) * float(multiplier)


def _normalized_tiers(selected: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not selected:
        return []
    ordered = sorted(
        selected,
        key=lambda candidate: float(
            (candidate.get("tier") or {}).get("tier_minimum_units")
        ),
    )
    tiers = []
    for index, candidate in enumerate(ordered):
        next_threshold = (
            (ordered[index + 1].get("tier") or {}).get("tier_minimum_units")
            if index + 1 < len(ordered)
            else "Infinity"
        )
        tiers.append(
            {
                "lower_bound": (candidate.get("tier") or {}).get(
                    "tier_minimum_units"
                ),
                "limit": next_threshold,
                "price": float(candidate["raw_price"]),
                "unit": candidate.get("unit"),
            }
        )
    return tiers


def _uniform_value(candidates: list[dict[str, Any]], key: str) -> Any:
    values = {candidate.get(key) for candidate in candidates}
    return next(iter(values)) if len(values) == 1 else None


def _selected_row(candidate: dict[str, Any] | None) -> dict[str, Any] | None:
    if not candidate:
        return None
    return {
        "candidate_id": candidate.get("candidate_id"),
        "serviceName": candidate.get("service_name"),
        "productName": candidate.get("product_name"),
        "skuName": candidate.get("sku_name"),
        "meterName": candidate.get("meter_name"),
        "unitOfMeasure": candidate.get("unit"),
        "retailPrice": candidate.get("raw_price"),
        "currencyCode": candidate.get("currency"),
        "armRegionName": candidate.get("region"),
        "tierMinimumUnits": (candidate.get("tier") or {}).get("tier_minimum_units"),
        "effectiveStartDate": (candidate.get("evidence") or {}).get(
            "effective_start_date"
        ),
        "meterId": (candidate.get("provider_identifiers") or {}).get("meter_id"),
        "skuId": (candidate.get("provider_identifiers") or {}).get("sku_id"),
        "productId": (candidate.get("provider_identifiers") or {}).get("product_id"),
    }


def _rejected_rows(
    rejections: list[dict[str, Any]],
    candidate_lookup: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    enriched = []
    for rejection in rejections:
        candidate = candidate_lookup.get(rejection.get("candidate_id"))
        row = _selected_row(candidate) if candidate else {"candidate_id": rejection.get("candidate_id")}
        row["reasons"] = rejection.get("reasons") or []
        enriched.append(row)
    return enriched


def _status_errors(status: str, intent_id: str | None) -> list[str]:
    if status == MATCHED:
        return []
    if status == AMBIGUOUS:
        return [f"Multiple Azure candidates matched {intent_id}"]
    if status == MISSING:
        return [f"No Azure candidate matched {intent_id}"]
    if status == CHANGED:
        return [f"Stable Azure candidate identity changed for {intent_id}"]
    return [f"Azure evidence match failed for {intent_id}: {status}"]
