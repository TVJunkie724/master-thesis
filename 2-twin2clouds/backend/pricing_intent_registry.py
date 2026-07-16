"""
Versioned pricing intent registry and deterministic candidate matcher.

The matcher is intentionally strict: it returns typed outcomes and never picks
one candidate silently when multiple provider rows match a pricing intent.
"""
from typing import Any


REGISTRY_SCHEMA_VERSION = "pricing-intent-registry.v1"
MAPPING_SCHEMA_VERSION = "pricing-intent-mapping.v1"

MATCHED = "matched"
MISSING = "missing"
AMBIGUOUS = "ambiguous"
CHANGED = "changed"
FAILED = "failed"

MATCH_STATUSES = (MATCHED, MISSING, AMBIGUOUS, CHANGED, FAILED)
SUPPORTED_SELECTION_MODES = {"single", "tier_series"}

CANONICAL_PRICING_INTENTS = (
    "transfer.egress_gb",
    "iot.message_ingest",
    "functions.request",
    "functions.compute_gb_second",
    "storage.hot.storage_gb_month",
    "storage.hot.read_request",
    "storage.hot.write_request",
    "storage.cool.storage_gb_month",
    "storage.archive.storage_gb_month",
    "storage.archive.write_request",
    "api.request_million",
    "orchestration.state_transition",
    "event_bus.event_million",
    "digital_twin.query_unit",
    "grafana.editor_user_month",
    "grafana.viewer_user_month",
)

REQUIRED_MAPPING_FIELDS = (
    "schema_version",
    "mapping_version",
    "intent_id",
    "provider",
    "review_status",
    "match",
)


def match_pricing_intent(
    candidates: list[dict[str, Any]],
    mapping: dict[str, Any],
) -> dict[str, Any]:
    """Match canonical pricing candidates against one versioned provider mapping."""
    validation_errors = validate_mapping(mapping)
    if validation_errors:
        return _result(FAILED, mapping, errors=validation_errors)

    provider = mapping["provider"]
    rules = mapping["match"]
    provider_candidates = [
        candidate for candidate in candidates if candidate.get("provider") == provider
    ]
    ordered_candidates = sorted(provider_candidates, key=_candidate_sort_key)

    matches: list[dict[str, Any]] = []
    rejections: list[dict[str, Any]] = []
    changed_candidates: list[dict[str, Any]] = []

    for candidate in ordered_candidates:
        candidate_matches, reasons = _candidate_matches(candidate, rules)
        if candidate_matches:
            matches.append(candidate)
            continue

        if _stable_identity_matches(candidate, rules) or _drift_marker_matches(
            candidate,
            mapping.get("drift_markers", {}),
        ):
            changed_candidates.append(candidate)
        rejections.append(
            {
                "candidate_id": candidate.get("candidate_id"),
                "reasons": reasons,
            }
        )

    selection_mode = mapping.get("selection_mode", "single")
    if selection_mode == "tier_series" and matches:
        tier_errors = _validate_tier_series(matches)
        if tier_errors:
            return _result(
                FAILED,
                mapping,
                candidates=matches,
                rejections=rejections,
                normalization=mapping.get("normalization"),
                errors=tier_errors,
            )
        ordered_tiers = sorted(matches, key=_tier_threshold)
        return _result(
            MATCHED,
            mapping,
            selected_candidates=ordered_tiers,
            candidates=ordered_tiers,
            rejections=rejections,
            normalization=mapping.get("normalization"),
        )

    if len(matches) == 1:
        return _result(
            MATCHED,
            mapping,
            selected_candidate=matches[0],
            candidates=matches,
            rejections=rejections,
            normalization=mapping.get("normalization"),
        )
    if len(matches) > 1:
        return _result(
            AMBIGUOUS,
            mapping,
            candidates=matches,
            rejections=rejections,
            normalization=mapping.get("normalization"),
        )
    if changed_candidates:
        return _result(
            CHANGED,
            mapping,
            candidates=changed_candidates,
            rejections=rejections,
            normalization=mapping.get("normalization"),
        )
    return _result(MISSING, mapping, rejections=rejections)


def validate_mapping(mapping: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for field in REQUIRED_MAPPING_FIELDS:
        if not mapping.get(field):
            errors.append(f"Missing mapping field: {field}")

    if mapping.get("schema_version") and mapping["schema_version"] != MAPPING_SCHEMA_VERSION:
        errors.append(
            f"Unsupported mapping schema_version: {mapping['schema_version']}"
        )

    intent_id = mapping.get("intent_id")
    if intent_id and intent_id not in CANONICAL_PRICING_INTENTS:
        errors.append(f"Unknown pricing intent: {intent_id}")

    provider = mapping.get("provider")
    if provider and provider not in {"aws", "azure", "gcp"}:
        errors.append(f"Unsupported provider: {provider}")

    if mapping.get("match") and not isinstance(mapping["match"], dict):
        errors.append("Mapping field 'match' must be an object")

    selection_mode = mapping.get("selection_mode", "single")
    if selection_mode not in SUPPORTED_SELECTION_MODES:
        errors.append(f"Unsupported selection_mode: {selection_mode}")

    return errors


def _candidate_matches(
    candidate: dict[str, Any],
    rules: dict[str, Any],
) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    for field, expected in rules.items():
        if field in {"provider_identifiers", "tier", "evidence"}:
            actual_values = candidate.get("provider_identifiers", {})
            if field != "provider_identifiers":
                actual_values = candidate.get(field, {})
            reasons.extend(_nested_mismatch_reasons(field, actual_values, expected))
        else:
            actual = candidate.get(field)
            if not _matches_expected(actual, expected):
                reasons.append(f"{field}: expected {expected!r}, got {actual!r}")
    return not reasons, reasons


def _nested_mismatch_reasons(
    field: str,
    actual_values: dict[str, Any],
    expected_values: dict[str, Any],
) -> list[str]:
    reasons: list[str] = []
    for key, expected in expected_values.items():
        actual = actual_values.get(key)
        if not _matches_expected(actual, expected):
            reasons.append(f"{field}.{key}: expected {expected!r}, got {actual!r}")
    return reasons


def _stable_identity_matches(candidate: dict[str, Any], rules: dict[str, Any]) -> bool:
    expected_identifiers = rules.get("provider_identifiers", {})
    if not expected_identifiers:
        return False
    actual_identifiers = candidate.get("provider_identifiers", {})
    return all(
        _matches_expected(actual_identifiers.get(key), expected)
        for key, expected in expected_identifiers.items()
    )


def _drift_marker_matches(
    candidate: dict[str, Any],
    drift_markers: dict[str, Any],
) -> bool:
    if not drift_markers:
        return False
    matches, _ = _candidate_matches(candidate, drift_markers)
    return matches


def _matches_expected(actual: Any, expected: Any) -> bool:
    if isinstance(expected, list):
        return actual in expected
    return actual == expected


def _candidate_sort_key(candidate: dict[str, Any]) -> str:
    return str(candidate.get("candidate_id") or "")


def _tier_threshold(candidate: dict[str, Any]) -> float:
    return float((candidate.get("tier") or {}).get("tier_minimum_units"))


def _validate_tier_series(candidates: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    thresholds: dict[float, float] = {}
    for candidate in candidates:
        candidate_id = candidate.get("candidate_id")
        threshold = (candidate.get("tier") or {}).get("tier_minimum_units")
        price = candidate.get("raw_price")
        if not isinstance(threshold, (int, float)) or isinstance(threshold, bool):
            errors.append(f"{candidate_id}: tierMinimumUnits must be numeric")
            continue
        if float(threshold) < 0:
            errors.append(f"{candidate_id}: tierMinimumUnits must be non-negative")
        if not isinstance(price, (int, float)) or isinstance(price, bool):
            errors.append(f"{candidate_id}: raw_price must be numeric")
            continue
        if float(price) < 0:
            errors.append(f"{candidate_id}: raw_price must be non-negative")
        normalized_threshold = float(threshold)
        normalized_price = float(price)
        if normalized_threshold in thresholds:
            previous = thresholds[normalized_threshold]
            qualifier = "conflicting" if previous != normalized_price else "duplicate"
            errors.append(
                f"{candidate_id}: {qualifier} tierMinimumUnits {normalized_threshold:g}"
            )
        thresholds[normalized_threshold] = normalized_price

    if thresholds and 0.0 not in thresholds:
        errors.append("tier series must contain tierMinimumUnits 0")
    return errors


def _result(
    status: str,
    mapping: dict[str, Any],
    *,
    selected_candidate: dict[str, Any] | None = None,
    selected_candidates: list[dict[str, Any]] | None = None,
    candidates: list[dict[str, Any]] | None = None,
    rejections: list[dict[str, Any]] | None = None,
    normalization: dict[str, Any] | None = None,
    errors: list[str] | None = None,
) -> dict[str, Any]:
    candidate_list = candidates or []
    return {
        "status": status,
        "intent_id": mapping.get("intent_id"),
        "provider": mapping.get("provider"),
        "mapping_version": mapping.get("mapping_version"),
        "review_status": mapping.get("review_status"),
        "selected_candidate": _candidate_summary(selected_candidate)
        if selected_candidate
        else None,
        "selected_candidates": [
            _candidate_summary(candidate) for candidate in (selected_candidates or [])
        ],
        "selection_mode": mapping.get("selection_mode", "single"),
        "candidates": [_candidate_summary(candidate) for candidate in candidate_list],
        "candidate_count": len(candidate_list),
        "rejections": sorted(rejections or [], key=lambda item: item.get("candidate_id") or ""),
        "normalization": normalization,
        "errors": errors or [],
    }


def _candidate_summary(candidate: dict[str, Any] | None) -> dict[str, Any] | None:
    if candidate is None:
        return None
    return {
        "candidate_id": candidate.get("candidate_id"),
        "provider_identifiers": candidate.get("provider_identifiers", {}),
        "provider_service": candidate.get("provider_service"),
        "service_name": candidate.get("service_name"),
        "product_name": candidate.get("product_name"),
        "sku_name": candidate.get("sku_name"),
        "meter_name": candidate.get("meter_name"),
        "region": candidate.get("region"),
        "unit": candidate.get("unit"),
        "price_type": candidate.get("price_type"),
        "currency": candidate.get("currency"),
        "raw_price": candidate.get("raw_price"),
        "tier": candidate.get("tier", {}),
        "evidence": candidate.get("evidence", {}),
    }
