from datetime import datetime, timezone
from typing import Any

from src.schemas.pricing_review import (
    PricingReviewReason,
    PricingReviewStateResponse,
    ProviderPricingReviewState,
)


PROVIDERS = ("aws", "azure", "gcp")
FRESH = "fresh"
STALE = "stale"
REVIEW_REQUIRED = "review_required"
MISSING = "missing"
FAILED = "failed"
LAST_KNOWN_GOOD = "last_known_good"
FALLBACK_STATIC = "fallback_static"
UNAVAILABLE = "unavailable"
CALCULATION_SOURCES = {FRESH, STALE, LAST_KNOWN_GOOD, FALLBACK_STATIC, UNAVAILABLE}
PRICING_FRESHNESS_VALUES = {FRESH, STALE, LAST_KNOWN_GOOD, UNAVAILABLE}


def build_pricing_review_state_response(
    optimizer_statuses: dict[str, dict[str, Any]],
    *,
    saved_snapshots: dict[str, dict[str, Any] | None] | None = None,
    saved_timestamps: dict[str, datetime | str | None] | None = None,
) -> PricingReviewStateResponse:
    snapshots = saved_snapshots or {}
    timestamps = saved_timestamps or {}
    return PricingReviewStateResponse(
        providers={
            provider: build_provider_pricing_review_state(
                provider,
                optimizer_statuses.get(provider) or {},
                saved_snapshot=snapshots.get(provider),
                saved_timestamp=timestamps.get(provider),
            )
            for provider in PROVIDERS
        }
    )


def build_provider_pricing_review_state(
    provider: str,
    optimizer_status: dict[str, Any],
    *,
    saved_snapshot: dict[str, Any] | None = None,
    saved_timestamp: datetime | str | None = None,
) -> ProviderPricingReviewState:
    """Convert Optimizer status into the typed Management API review contract."""
    if _is_publication_decision(optimizer_status):
        return _from_publication_decision(
            provider,
            optimizer_status,
            saved_snapshot=saved_snapshot,
            saved_timestamp=saved_timestamp,
        )

    has_last_known_good = saved_snapshot is not None or saved_timestamp is not None
    raw_status = optimizer_status.get("status")
    missing_keys = _string_list(optimizer_status.get("missing_keys"))
    fallback_fields = _string_list(optimizer_status.get("fallback_fields"))
    unsupported_fields = _string_list(optimizer_status.get("unsupported_fields"))
    optimizer_requires_review = bool(
        optimizer_status.get("review_required") or fallback_fields or unsupported_fields
    )
    is_fresh = bool(optimizer_status.get("is_fresh", False))

    if optimizer_status.get("error") or raw_status == "error":
        state = FAILED
        reasons = [
            _reason(
                "failed",
                str(optimizer_status.get("error") or "Optimizer pricing status failed."),
            )
        ]
    elif raw_status == "missing":
        state = MISSING
        reasons = [_reason("missing", "No cached pricing file is available.")]
    elif raw_status == "incomplete":
        state = REVIEW_REQUIRED
        reasons = [
            _reason(
                "incomplete",
                "Cached pricing is missing required calculation keys.",
                missing_keys=missing_keys,
            )
        ]
    elif raw_status == "valid" and optimizer_requires_review:
        state = REVIEW_REQUIRED
        reasons = _quality_reasons(
            fallback_fields=fallback_fields,
            unsupported_fields=unsupported_fields,
        )
    elif raw_status == "valid" and is_fresh:
        state = FRESH
        reasons = []
    elif raw_status == "valid":
        state = STALE
        reasons = []
    else:
        state = FAILED
        reasons = [_reason("failed", "Optimizer pricing status is unknown.")]

    uses_reviewable_fallback = raw_status == "valid" and bool(fallback_fields)
    can_calculate = (
        state in {FRESH, STALE}
        or raw_status == "valid"
        or has_last_known_good
    )
    calculation_source = _calculation_source(
        state,
        has_last_known_good,
        uses_reviewable_fallback=uses_reviewable_fallback,
    )
    pricing_freshness = _pricing_freshness(state, has_last_known_good)

    return ProviderPricingReviewState(
        provider=provider,
        state=state,
        review_required=state in {REVIEW_REQUIRED, MISSING, FAILED},
        can_calculate=can_calculate,
        calculation_source=calculation_source,
        pricing_freshness=pricing_freshness,
        age=optimizer_status.get("age"),
        status=raw_status,
        is_fresh=is_fresh,
        threshold_days=optimizer_status.get("threshold_days"),
        missing_keys=missing_keys,
        review_reasons=reasons,
        actions=_actions(state, has_last_known_good),
        last_known_good_updated_at=_iso_timestamp(saved_timestamp),
        optimizer=_safe_optimizer_status(optimizer_status),
    )


def _from_publication_decision(
    provider: str,
    decision: dict[str, Any],
    *,
    saved_snapshot: dict[str, Any] | None,
    saved_timestamp: datetime | str | None,
) -> ProviderPricingReviewState:
    state = FRESH if not decision.get("review_required") else REVIEW_REQUIRED
    has_last_known_good = (
        saved_snapshot is not None
        or saved_timestamp is not None
        or decision.get("calculation_source") == LAST_KNOWN_GOOD
    )
    calculation_source = _allowed_value(
        decision.get("calculation_source"),
        CALCULATION_SOURCES,
        _calculation_source(state, has_last_known_good),
    )
    pricing_freshness = _allowed_value(
        decision.get("pricing_freshness"),
        PRICING_FRESHNESS_VALUES,
        _pricing_freshness(state, has_last_known_good),
    )
    review_reasons = [
        PricingReviewReason(
            status=str(reason.get("status") or REVIEW_REQUIRED),
            intent_id=reason.get("intent_id"),
            reason=str(reason.get("reason") or "Pricing review is required."),
            errors=_string_list(reason.get("errors")),
            missing_keys=_string_list(reason.get("missing_keys")),
        )
        for reason in decision.get("review_reasons", [])
    ]

    return ProviderPricingReviewState(
        provider=provider,
        state=state,
        review_required=bool(decision.get("review_required", False)),
        can_calculate=bool(decision.get("can_calculate", False)),
        calculation_source=calculation_source,
        pricing_freshness=pricing_freshness,
        age=decision.get("age"),
        status=decision.get("status"),
        is_fresh=pricing_freshness == FRESH,
        threshold_days=decision.get("threshold_days"),
        missing_keys=_string_list(decision.get("missing_keys")),
        review_reasons=review_reasons,
        actions=_actions(state, has_last_known_good),
        last_known_good_updated_at=_iso_timestamp(saved_timestamp),
        optimizer=_safe_optimizer_status(decision),
    )


def _is_publication_decision(status: dict[str, Any]) -> bool:
    return status.get("schema_version") == "pricing-publication-decision.v1"


def _calculation_source(
    state: str,
    has_last_known_good: bool,
    *,
    uses_reviewable_fallback: bool = False,
) -> str:
    if state == FRESH:
        return FRESH
    if state == STALE:
        return STALE
    if has_last_known_good:
        return LAST_KNOWN_GOOD
    if uses_reviewable_fallback:
        return FALLBACK_STATIC
    return UNAVAILABLE


def _pricing_freshness(state: str, has_last_known_good: bool) -> str:
    if state == FRESH:
        return FRESH
    if state == STALE:
        return STALE
    if has_last_known_good:
        return LAST_KNOWN_GOOD
    return UNAVAILABLE


def _actions(state: str, has_last_known_good: bool) -> list[str]:
    actions = ["refresh"]
    if state in {REVIEW_REQUIRED, MISSING, FAILED} and has_last_known_good:
        actions.append("keep_last_known_good")
    return actions


def _reason(
    status: str,
    reason: str,
    *,
    missing_keys: list[str] | None = None,
) -> PricingReviewReason:
    return PricingReviewReason(
        status=status,
        reason=reason,
        missing_keys=missing_keys or [],
    )


def _quality_reasons(
    *,
    fallback_fields: list[str],
    unsupported_fields: list[str],
) -> list[PricingReviewReason]:
    reasons: list[PricingReviewReason] = []
    if fallback_fields:
        reasons.append(
            _reason(
                "fallback_static",
                "Cached pricing contains emergency fallback values and must be reviewed.",
                missing_keys=fallback_fields,
            )
        )
    if unsupported_fields:
        reasons.append(
            _reason(
                "unsupported",
                "Cached pricing contains fields that could not be fetched or derived from the provider contract.",
                missing_keys=unsupported_fields,
            )
        )
    if not reasons:
        reasons.append(
            _reason("review_required", "Optimizer marked cached pricing for review.")
        )
    return reasons


def _string_list(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]


def _allowed_value(value: Any, allowed: set[str], fallback: str) -> str:
    if isinstance(value, str) and value in allowed:
        return value
    return fallback


def _safe_optimizer_status(status: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in status.items()
        if key not in {"pricing", "raw_payload", "credentials"}
    }


def _iso_timestamp(value: datetime | str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc).isoformat()
    return value.isoformat()
