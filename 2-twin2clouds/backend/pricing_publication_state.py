"""
Pricing publication decisions for fresh, review-required, and last-known-good data.

Provider catalog refreshes are evidence, not automatically calculation pricing.
This module decides whether fresh matched evidence can become the calculation
snapshot or whether consumers must keep using the last reviewed snapshot.
"""
from datetime import datetime, timezone
from typing import Any

from backend.pricing_intent_registry import (
    AMBIGUOUS,
    CHANGED,
    FAILED,
    MATCH_STATUSES,
    MATCHED,
    MISSING,
)


PUBLICATION_SCHEMA_VERSION = "pricing-publication-decision.v1"

PUBLISHABLE = "publishable"
REVIEW_REQUIRED = "review_required"
UNAVAILABLE = "unavailable"

FRESH = "fresh"
LAST_KNOWN_GOOD = "last_known_good"
FALLBACK_STATIC = "fallback_static"
NO_PRICING_AVAILABLE = "unavailable"
STALE = "stale"

FALLBACK_STATIC_STATUS = "fallback_static"
REVIEW_REQUIRED_MATCH_STATUSES = {
    AMBIGUOUS,
    MISSING,
    CHANGED,
    FAILED,
    FALLBACK_STATIC_STATUS,
}


def build_pricing_publication_decision(
    provider: str,
    match_results: list[dict[str, Any]],
    *,
    fresh_snapshot: dict[str, Any] | None = None,
    last_known_good_snapshot: dict[str, Any] | None = None,
    evaluated_at: datetime | str | None = None,
) -> dict[str, Any]:
    """Build a provider-scoped publication decision from intent match results."""
    normalized_results = [_normalize_match_result(result) for result in match_results]
    now = _iso_timestamp(evaluated_at)
    summary = _summarize_results(normalized_results)
    review_reasons = _review_reasons(normalized_results)

    if not normalized_results:
        review_reasons.append(
            {
                "status": FAILED,
                "intent_id": None,
                "reason": "No pricing intent match results were provided.",
            }
        )
    elif not review_reasons and fresh_snapshot is None:
        review_reasons.append(
            {
                "status": FAILED,
                "intent_id": None,
                "reason": "Fresh pricing snapshot is missing.",
            }
        )

    if not review_reasons and fresh_snapshot is not None:
        return {
            "schema_version": PUBLICATION_SCHEMA_VERSION,
            "provider": provider,
            "status": PUBLISHABLE,
            "calculation_source": FRESH,
            "pricing_freshness": FRESH,
            "can_calculate": True,
            "review_required": False,
            "evaluated_at": now,
            "published_snapshot": _snapshot_metadata(fresh_snapshot),
            "last_known_good_snapshot": _snapshot_metadata(last_known_good_snapshot),
            "match_summary": summary,
            "review_reasons": [],
            "intent_results": normalized_results,
        }

    calculation_source = NO_PRICING_AVAILABLE
    pricing_freshness = NO_PRICING_AVAILABLE
    can_calculate = False
    published_snapshot = None
    if last_known_good_snapshot is not None:
        calculation_source = _last_known_good_calculation_source(last_known_good_snapshot)
        pricing_freshness = (
            STALE if last_known_good_snapshot.get("is_stale") else LAST_KNOWN_GOOD
        )
        can_calculate = True
        published_snapshot = _snapshot_metadata(last_known_good_snapshot)

    return {
        "schema_version": PUBLICATION_SCHEMA_VERSION,
        "provider": provider,
        "status": REVIEW_REQUIRED if can_calculate else UNAVAILABLE,
        "calculation_source": calculation_source,
        "pricing_freshness": pricing_freshness,
        "can_calculate": can_calculate,
        "review_required": True,
        "evaluated_at": now,
        "published_snapshot": published_snapshot,
        "last_known_good_snapshot": _snapshot_metadata(last_known_good_snapshot),
        "fresh_snapshot": _snapshot_metadata(fresh_snapshot),
        "match_summary": summary,
        "review_reasons": review_reasons,
        "intent_results": normalized_results,
    }


def select_calculation_snapshot(
    decision: dict[str, Any],
    *,
    fresh_snapshot: dict[str, Any] | None = None,
    last_known_good_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Select the snapshot that calculation code is allowed to use."""
    source = decision.get("calculation_source")
    if source == FRESH:
        return fresh_snapshot
    if source in {LAST_KNOWN_GOOD, FALLBACK_STATIC}:
        return last_known_good_snapshot
    return None


def _normalize_match_result(result: dict[str, Any]) -> dict[str, Any]:
    status = result.get("status") or FAILED
    if status not in MATCH_STATUSES and status != FALLBACK_STATIC_STATUS:
        status = FAILED
    return {
        "intent_id": result.get("intent_id"),
        "provider": result.get("provider"),
        "mapping_version": result.get("mapping_version"),
        "status": status,
        "selected_candidate": result.get("selected_candidate"),
        "candidate_count": result.get("candidate_count", 0),
        "errors": list(result.get("errors") or []),
    }


def _summarize_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    status_counts: dict[str, int] = {}
    intent_statuses: dict[str, str] = {}
    for result in results:
        status = result["status"]
        status_counts[status] = status_counts.get(status, 0) + 1
        intent_id = result.get("intent_id")
        if intent_id:
            intent_statuses[intent_id] = status

    return {
        "total_intents": len(results),
        "status_counts": dict(sorted(status_counts.items())),
        "intent_statuses": dict(sorted(intent_statuses.items())),
    }


def _review_reasons(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    reasons: list[dict[str, Any]] = []
    for result in results:
        status = result["status"]
        if status == MATCHED:
            continue
        if status not in REVIEW_REQUIRED_MATCH_STATUSES:
            status = FAILED
        reasons.append(
            {
                "status": status,
                "intent_id": result.get("intent_id"),
                "reason": _review_reason_for_status(status),
                "errors": result.get("errors", []),
            }
        )
    return reasons


def _review_reason_for_status(status: str) -> str:
    reasons = {
        AMBIGUOUS: "Multiple provider pricing candidates match this intent.",
        MISSING: "No provider pricing candidate matches this intent.",
        CHANGED: "Stable pricing identifiers or drift markers changed.",
        FAILED: "Pricing refresh or mapping validation failed.",
        FALLBACK_STATIC_STATUS: "A static fallback price was used and requires review.",
    }
    return reasons.get(status, "Pricing status is not publishable.")


def _snapshot_metadata(snapshot: dict[str, Any] | None) -> dict[str, Any] | None:
    if snapshot is None:
        return None
    return {
        "snapshot_id": snapshot.get("snapshot_id"),
        "schema_version": snapshot.get("schema_version"),
        "provider": snapshot.get("provider"),
        "source_api": snapshot.get("source_api"),
        "fetched_at": snapshot.get("fetched_at"),
        "published_at": snapshot.get("published_at"),
        "mapping_version": snapshot.get("mapping_version"),
        "candidate_count": snapshot.get("candidate_count"),
        "raw_item_count": snapshot.get("raw_item_count"),
        "is_stale": bool(snapshot.get("is_stale", False)),
        "stale_reason": snapshot.get("stale_reason"),
    }


def _last_known_good_calculation_source(snapshot: dict[str, Any]) -> str:
    if snapshot.get("calculation_source") == FALLBACK_STATIC:
        return FALLBACK_STATIC
    if snapshot.get("source_api") == FALLBACK_STATIC:
        return FALLBACK_STATIC
    return LAST_KNOWN_GOOD


def _iso_timestamp(value: datetime | str | None) -> str:
    if value is None:
        value = datetime.now(timezone.utc)
    if isinstance(value, str):
        return value
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()
