"""Project immutable Optimizer catalog status into the Management review contract."""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from src.schemas.pricing_catalog import PricingCatalogReference
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
UNAVAILABLE = "unavailable"


def build_pricing_review_state_response(
    optimizer_statuses: dict[str, dict[str, Any]],
) -> PricingReviewStateResponse:
    """Build review state exclusively from active immutable catalog metadata."""

    return PricingReviewStateResponse(
        providers={
            provider: build_provider_pricing_review_state(
                provider,
                optimizer_statuses.get(provider) or {},
            )
            for provider in PROVIDERS
        }
    )


def build_provider_pricing_review_state(
    provider: str,
    optimizer_status: dict[str, Any],
) -> ProviderPricingReviewState:
    """Convert one provider-region catalog status into typed UI state."""

    raw_status = optimizer_status.get("status")
    missing_keys = _string_list(optimizer_status.get("missing_keys"))
    fallback_fields = _string_list(optimizer_status.get("fallback_fields"))
    unsupported_fields = _string_list(optimizer_status.get("unsupported_fields"))
    is_fresh = optimizer_status.get("is_fresh") is True
    reference, reference_error = _active_reference(optimizer_status)

    if optimizer_status.get("error") or raw_status == "error":
        state = FAILED
        reasons = [
            _reason(
                "failed",
                str(optimizer_status.get("error") or "Optimizer pricing status failed."),
            )
        ]
    elif reference_error:
        state = FAILED
        reasons = [_reason("failed", reference_error)]
    elif raw_status == "missing" or reference is None:
        state = MISSING
        reasons = [_reason("missing", "No published pricing catalog is available.")]
    elif raw_status == "incomplete":
        state = REVIEW_REQUIRED
        reasons = [
            _reason(
                "incomplete",
                "Published pricing is missing required calculation keys.",
                missing_keys=missing_keys,
            )
        ]
    elif raw_status == "valid" and (fallback_fields or unsupported_fields):
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

    can_calculate = (
        reference is not None
        and raw_status == "valid"
        and is_fresh
    )
    calculation_source = (
        reference.calculation_source
        if can_calculate and reference is not None
        else UNAVAILABLE
    )
    pricing_freshness = (
        FRESH
        if can_calculate
        else STALE
        if reference is not None and not is_fresh
        else UNAVAILABLE
    )

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
        actions=["refresh"],
        last_known_good_updated_at=(
            reference.fetched_at.isoformat() if reference is not None else None
        ),
        optimizer=_safe_optimizer_status(optimizer_status),
    )


def _active_reference(
    status: dict[str, Any],
) -> tuple[PricingCatalogReference | None, str | None]:
    raw_reference = status.get("active_reference")
    if raw_reference is None:
        return None, None
    try:
        return PricingCatalogReference.model_validate(raw_reference), None
    except ValidationError:
        return None, "Optimizer returned an invalid active pricing reference."


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
                "Published pricing contains emergency fallback values.",
                missing_keys=fallback_fields,
            )
        )
    if unsupported_fields:
        reasons.append(
            _reason(
                "unsupported",
                "Published pricing contains unsupported calculation fields.",
                missing_keys=unsupported_fields,
            )
        )
    return reasons or [
        _reason("review_required", "Optimizer marked published pricing for review.")
    ]


def _string_list(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]


def _safe_optimizer_status(status: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in status.items()
        if key not in {"pricing", "raw_payload", "credentials"}
    }
