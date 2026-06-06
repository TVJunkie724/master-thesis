from typing import Any, Literal

from pydantic import BaseModel, Field


PricingReviewStateValue = Literal[
    "fresh",
    "stale",
    "review_required",
    "missing",
    "failed",
]

PricingCalculationSource = Literal[
    "fresh",
    "stale",
    "last_known_good",
    "fallback_static",
    "unavailable",
]

PricingFreshness = Literal[
    "fresh",
    "stale",
    "last_known_good",
    "unavailable",
]


class PricingReviewReason(BaseModel):
    status: str
    reason: str
    intent_id: str | None = None
    errors: list[str] = Field(default_factory=list)
    missing_keys: list[str] = Field(default_factory=list)


class ProviderPricingReviewState(BaseModel):
    provider: Literal["aws", "azure", "gcp"]
    state: PricingReviewStateValue
    review_required: bool
    can_calculate: bool
    calculation_source: PricingCalculationSource
    pricing_freshness: PricingFreshness
    age: str | None = None
    status: str | None = None
    is_fresh: bool = False
    threshold_days: int | None = None
    missing_keys: list[str] = Field(default_factory=list)
    review_reasons: list[PricingReviewReason] = Field(default_factory=list)
    actions: list[str] = Field(default_factory=list)
    last_known_good_updated_at: str | None = None
    optimizer: dict[str, Any] = Field(default_factory=dict)


class PricingReviewStateResponse(BaseModel):
    schema_version: str = "pricing-review-state.v1"
    providers: dict[str, ProviderPricingReviewState]
