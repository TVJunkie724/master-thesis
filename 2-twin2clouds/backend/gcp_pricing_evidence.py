"""GCP pricing preflight and evidence report builder.

GCP Cloud Billing Catalog access must be proven before generated GCP pricing can
be treated as live evidence. This module keeps auth failures structured and
secret-redacted, and converts Catalog SKUs into inspectable evidence records.
"""
from __future__ import annotations

import json
import re
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


GCP_EVIDENCE_REPORT_SCHEMA_VERSION = "gcp-pricing-evidence-report.v1"
GCP_BILLING_CATALOG_API = "gcp-cloud-billing-catalog"

GCP_BILLING_CATALOG_OPERATIONS = (
    {
        "operation": "cloudbilling.services.list",
        "permission": "cloudbilling.services.list",
        "description": "List Cloud Billing Catalog services.",
    },
    {
        "operation": "cloudbilling.skus.list",
        "permission": "cloudbilling.skus.list",
        "description": "List SKUs for a Cloud Billing Catalog service.",
    },
)

SECRET_PATTERNS = (
    re.compile(r"-----BEGIN PRIVATE KEY-----.*?-----END PRIVATE KEY-----", re.DOTALL),
    re.compile(r'("private_key"\s*:\s*")[^"]+(")', re.IGNORECASE),
    re.compile(r'("private_key_id"\s*:\s*")[^"]+(")', re.IGNORECASE),
    re.compile(r'("client_email"\s*:\s*")[^"]+(")', re.IGNORECASE),
    re.compile(r'("token"\s*:\s*")[^"]+(")', re.IGNORECASE),
)


def validate_gcp_billing_catalog_access(client: Any) -> dict[str, Any]:
    """Validate the two Catalog operations needed by pricing refresh."""
    operations = []
    try:
        service_iterator = client.list_services(request={})
        first_service = next(iter(service_iterator), None)
        if first_service is None:
            raise RuntimeError("Cloud Billing Catalog returned no services")
        operations.append(_operation_result(GCP_BILLING_CATALOG_OPERATIONS[0]))
    except Exception as exc:
        return _preflight_failure(GCP_BILLING_CATALOG_OPERATIONS[0], exc, operations)

    service_parent = _service_parent(first_service)
    try:
        sku_iterator = client.list_skus(request={"parent": service_parent})
        next(iter(sku_iterator), None)
        operations.append(
            {
                **_operation_result(GCP_BILLING_CATALOG_OPERATIONS[1]),
                "service_parent": service_parent,
            }
        )
    except Exception as exc:
        return _preflight_failure(GCP_BILLING_CATALOG_OPERATIONS[1], exc, operations)

    return {
        "status": "valid",
        "provider": "gcp",
        "source_api": GCP_BILLING_CATALOG_API,
        "operations": operations,
        "required_permissions": [
            operation["permission"] for operation in GCP_BILLING_CATALOG_OPERATIONS
        ],
    }


def build_gcp_pricing_evidence_report(
    raw_skus: Iterable[dict[str, Any]],
    *,
    region: str,
    pricing_registry_service: PricingRegistryService | None = None,
    fetched_at: str | None = None,
    request_scope: dict[str, Any] | None = None,
    preflight: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a deterministic GCP evidence report from Billing Catalog SKUs."""
    registry_service = pricing_registry_service or PricingRegistryService()
    scope = {
        "provider": "gcp",
        "region": region,
        **(request_scope or {}),
    }
    snapshot = build_pricing_catalog_snapshot(
        "gcp",
        raw_skus,
        source_api=GCP_BILLING_CATALOG_API,
        request_scope=scope,
        fetched_at=fetched_at,
    )
    candidates = _enrich_gcp_candidates(snapshot["candidates"])
    snapshot = {**snapshot, "candidates": candidates}
    mappings = registry_service.list_provider_mappings("gcp")
    normalization_rules = registry_service.list_normalization_rules()
    registry_version = registry_service.get_registry_version()

    candidate_lookup = {
        candidate.get("candidate_id"): candidate
        for candidate in candidates
    }
    records = []
    match_results = {}
    for intent_id in sorted(mappings):
        mapping = mappings[intent_id]
        match_mapping = _intent_match_mapping(mapping)
        result = match_pricing_intent(candidates, match_mapping)
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
    auth_status = (preflight or {}).get("status", "not_checked")
    if auth_status != "valid":
        review_required = True
    return {
        "schema_version": GCP_EVIDENCE_REPORT_SCHEMA_VERSION,
        "provider": "gcp",
        "region": region,
        "source_api": GCP_BILLING_CATALOG_API,
        "request_scope": scope,
        "registry_version": registry_version,
        "preflight": preflight or {"status": "not_checked"},
        "snapshot": snapshot,
        "match_results": match_results,
        "records": records,
        "record_count": len(records),
        "review_required": review_required,
    }


def build_gcp_intent_evidence(
    raw_skus: Iterable[dict[str, Any]],
    *,
    intent_id: str,
    region: str,
    pricing_registry_service: PricingRegistryService | None = None,
    fetched_at: str | None = None,
) -> dict[str, Any]:
    """Select and normalize one GCP intent through the canonical registry."""

    registry_service = pricing_registry_service or PricingRegistryService()
    scope = {"provider": "gcp", "region": region}
    snapshot = build_pricing_catalog_snapshot(
        "gcp",
        raw_skus,
        source_api=GCP_BILLING_CATALOG_API,
        request_scope=scope,
        fetched_at=fetched_at,
    )
    candidates = _enrich_gcp_candidates(snapshot["candidates"])
    mapping = registry_service.get_provider_mapping("gcp", intent_id)
    result = match_pricing_intent(
        candidates,
        _intent_match_mapping(mapping),
    )
    candidate_lookup = {
        candidate.get("candidate_id"): candidate for candidate in candidates
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


def write_gcp_pricing_evidence_report(report: dict[str, Any], path: str | Path) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2, sort_keys=True))


def redact_gcp_error(value: Any) -> str:
    text = str(value)
    for pattern in SECRET_PATTERNS:
        text = pattern.sub(_redaction_replacement, text)
    return text


def _redaction_replacement(match: re.Match[str]) -> str:
    if match.lastindex == 2:
        return f"{match.group(1)}<redacted>{match.group(2)}"
    return "<redacted>"


def _operation_result(operation: dict[str, str]) -> dict[str, str]:
    return {
        "operation": operation["operation"],
        "permission": operation["permission"],
        "status": "ok",
    }


def _preflight_failure(
    operation: dict[str, str],
    exc: Exception,
    completed_operations: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "status": "failed",
        "provider": "gcp",
        "source_api": GCP_BILLING_CATALOG_API,
        "failed_operation": operation["operation"],
        "required_permission": operation["permission"],
        "operations": completed_operations
        + [
            {
                "operation": operation["operation"],
                "permission": operation["permission"],
                "status": "failed",
            }
        ],
        "error": {
            "type": exc.__class__.__name__,
            "message": redact_gcp_error(exc),
        },
    }


def _service_parent(service: Any) -> str:
    name = getattr(service, "name", None) or ""
    if name.startswith("services/"):
        return name
    service_id = getattr(service, "service_id", None) or getattr(service, "serviceId", None)
    if service_id:
        return f"services/{service_id}"
    return name


def _intent_match_mapping(mapping: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": MAPPING_SCHEMA_VERSION,
        "mapping_version": mapping.get("mapping_version"),
        "intent_id": mapping.get("intent_id"),
        "provider": "gcp",
        "review_status": mapping.get("review_status"),
        "match": mapping.get("match") or {},
        "drift_markers": mapping.get("drift_markers") or {},
        "selection_mode": mapping.get("selection_mode", "single"),
        "normalization": {
            "rule_id": mapping.get("normalization_rule"),
        },
    }


def _enrich_gcp_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    enriched = []
    for candidate in candidates:
        evidence = candidate.get("evidence") or {}
        enriched.append(
            {
                **candidate,
                "resource_group": evidence.get("resource_group"),
                "resource_family": evidence.get("resource_family"),
            }
        )
    return enriched


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
        "provider": "gcp",
        "intent_id": mapping.get("intent_id"),
        "field_path": mapping.get("intent_id"),
        "source_type": FETCHED if selected or selected_series else NOT_APPLICABLE,
        "source_api": GCP_BILLING_CATALOG_API,
        "request_scope": request_scope,
        "catalog_match": mapping.get("match") or {},
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
        "selected_rows": [
            _selected_row(candidate) for candidate in selected_series
        ],
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


def _normalized_tiers(
    selected: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    ordered = sorted(
        selected,
        key=lambda candidate: float(
            (candidate.get("tier") or {}).get("start_usage_amount")
        ),
    )
    return [
        {
            "lower_bound": float(
                (candidate.get("tier") or {})["start_usage_amount"]
            ),
            "price": float(candidate["raw_price"]),
            "unit": candidate.get("unit"),
        }
        for candidate in ordered
    ]


def _uniform_value(candidates: list[dict[str, Any]], key: str) -> Any:
    values = {candidate.get(key) for candidate in candidates}
    return next(iter(values)) if len(values) == 1 else None


def _selected_row(candidate: dict[str, Any] | None) -> dict[str, Any] | None:
    if not candidate:
        return None
    identifiers = candidate.get("provider_identifiers") or {}
    raw_payload_ref = candidate.get("raw_payload_ref") or {}
    pricing_expression = raw_payload_ref.get("pricing_expression") or {}
    tiered_rate = raw_payload_ref.get("tiered_rate") or {}
    return {
        "candidate_id": candidate.get("candidate_id"),
        "serviceId": identifiers.get("service_id"),
        "skuId": identifiers.get("sku_id"),
        "serviceDisplayName": candidate.get("service_name"),
        "description": candidate.get("sku_name"),
        "resourceFamily": candidate.get("resource_family"),
        "resourceGroup": candidate.get("resource_group"),
        "usageType": candidate.get("meter_name"),
        "serviceRegions": candidate.get("region"),
        "unit": candidate.get("unit"),
        "baseUnit": (candidate.get("tier") or {}).get("base_unit"),
        "baseUnitDescription": (candidate.get("tier") or {}).get("base_unit_description"),
        "startUsageAmount": (candidate.get("tier") or {}).get("start_usage_amount"),
        "pricePerUnit": candidate.get("raw_price"),
        "currency": candidate.get("currency"),
        "pricing_expression": pricing_expression,
        "tiered_rate": tiered_rate,
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
        return [f"Multiple GCP candidates matched {intent_id}"]
    if status == MISSING:
        return [f"No GCP candidate matched {intent_id}"]
    if status == CHANGED:
        return [f"Stable GCP candidate identity changed for {intent_id}"]
    return [f"GCP evidence match failed for {intent_id}: {status}"]
