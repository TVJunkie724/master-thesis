"""AWS pricing evidence report builder.

This module converts AWS Price List products into inspectable evidence records.
It preserves AWS product, OnDemand term, and price-dimension identity without
changing calculation formulas.
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


AWS_EVIDENCE_REPORT_SCHEMA_VERSION = "aws-pricing-evidence-report.v1"
AWS_PRICE_LIST_API = "aws-price-list"

AWS_MATCH_FIELD_ALIASES = {
    "service_code": "provider_service",
    "product_family": "product_name",
    "storage_class": "sku_name",
    "user_type": "meter_name",
}


def build_aws_pricing_evidence_report(
    raw_products: Iterable[str | dict[str, Any]],
    *,
    region: str,
    pricing_registry_service: PricingRegistryService | None = None,
    fetched_at: str | None = None,
    request_scope: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a deterministic AWS evidence report from Price List products."""
    registry_service = pricing_registry_service or PricingRegistryService()
    scope = {
        "provider": "aws",
        "region": region,
        **(request_scope or {}),
    }
    snapshot = build_pricing_catalog_snapshot(
        "aws",
        raw_products,
        source_api=AWS_PRICE_LIST_API,
        request_scope=scope,
        fetched_at=fetched_at,
    )
    mappings = registry_service.list_provider_mappings("aws")
    normalization_rules = registry_service.list_normalization_rules()
    registry_version = registry_service.get_registry_version()

    candidate_lookup = {
        candidate.get("candidate_id"): candidate
        for candidate in snapshot["candidates"]
    }
    records = []
    match_results = {}
    for intent_id in sorted(mappings):
        mapping = mappings[intent_id]
        match_mapping = _intent_match_mapping(mapping)
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
        "schema_version": AWS_EVIDENCE_REPORT_SCHEMA_VERSION,
        "provider": "aws",
        "region": region,
        "source_api": AWS_PRICE_LIST_API,
        "request_scope": scope,
        "registry_version": registry_version,
        "snapshot": snapshot,
        "match_results": match_results,
        "records": records,
        "record_count": len(records),
        "review_required": review_required,
    }


def write_aws_pricing_evidence_report(report: dict[str, Any], path: str | Path) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2, sort_keys=True))


def _intent_match_mapping(mapping: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": MAPPING_SCHEMA_VERSION,
        "mapping_version": mapping.get("mapping_version"),
        "intent_id": mapping.get("intent_id"),
        "provider": "aws",
        "review_status": mapping.get("review_status"),
        "match": _translate_match_fields(mapping.get("match") or {}),
        "drift_markers": _translate_match_fields(mapping.get("drift_markers") or {}),
        "normalization": {
            "rule_id": mapping.get("normalization_rule"),
        },
    }


def _translate_match_fields(match: dict[str, Any]) -> dict[str, Any]:
    translated: dict[str, Any] = {}
    for key, value in match.items():
        translated[AWS_MATCH_FIELD_ALIASES.get(key, key)] = value
    return translated


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
    normalization_rule_id = mapping.get("normalization_rule")
    normalization_rule = normalization_rules.get(normalization_rule_id, {})
    normalized_value = _normalized_value(selected_evidence, normalization_rule)
    review_required = status != MATCHED or mapping.get("review_status") != "reviewed"

    return {
        "schema_version": "pricing-evidence.v1",
        "provider": "aws",
        "intent_id": mapping.get("intent_id"),
        "field_path": mapping.get("intent_id"),
        "source_type": FETCHED if selected else NOT_APPLICABLE,
        "source_api": AWS_PRICE_LIST_API,
        "request_scope": request_scope,
        "price_list_filters": mapping.get("match") or {},
        "normalization_rule": normalization_rule_id,
        "normalization": normalization_rule,
        "normalized_value": normalized_value,
        "currency": selected_evidence.get("currency") if selected_evidence else None,
        "mapping_version": mapping.get("mapping_version"),
        "registry_version": registry_version,
        "fetched_at": fetched_at,
        "review_required": review_required,
        "match_status": status,
        "selected_row": _selected_row(selected_evidence),
        "candidate_rows": result.get("candidates") or [],
        "rejected_rows": _rejected_rows(result.get("rejections") or [], candidate_lookup),
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


def _selected_row(candidate: dict[str, Any] | None) -> dict[str, Any] | None:
    if not candidate:
        return None
    identifiers = candidate.get("provider_identifiers") or {}
    raw_payload_ref = candidate.get("raw_payload_ref") or {}
    product = raw_payload_ref.get("product") or {}
    price_dimension = raw_payload_ref.get("price_dimension") or {}
    attributes = product.get("attributes") or {}
    offer_term_key = identifiers.get("offer_term_code")
    return {
        "candidate_id": candidate.get("candidate_id"),
        "serviceCode": identifiers.get("service_code") or candidate.get("provider_service"),
        "serviceName": candidate.get("service_name"),
        "productFamily": candidate.get("product_name"),
        "sku": identifiers.get("sku"),
        "skuName": candidate.get("sku_name"),
        "usageType": identifiers.get("usage_type"),
        "operation": identifiers.get("operation"),
        "offerTermKey": offer_term_key,
        "offerTermCode": _offer_term_code(offer_term_key, identifiers.get("sku")),
        "rateCode": identifiers.get("rate_code"),
        "description": candidate.get("meter_name"),
        "unit": candidate.get("unit"),
        "pricePerUnit": candidate.get("raw_price"),
        "currency": candidate.get("currency"),
        "beginRange": (candidate.get("tier") or {}).get("begin_range"),
        "endRange": (candidate.get("tier") or {}).get("end_range"),
        "attributes": attributes,
        "price_dimension": price_dimension,
        "raw_payload_ref": raw_payload_ref,
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
        return [f"Multiple AWS candidates matched {intent_id}"]
    if status == MISSING:
        return [f"No AWS candidate matched {intent_id}"]
    if status == CHANGED:
        return [f"Stable AWS candidate identity changed for {intent_id}"]
    return [f"AWS evidence match failed for {intent_id}: {status}"]


def _offer_term_code(offer_term_key: str | None, sku: str | None) -> str | None:
    if not offer_term_key:
        return None
    prefix = f"{sku}." if sku else ""
    if prefix and offer_term_key.startswith(prefix):
        return offer_term_key[len(prefix):]
    return offer_term_key
