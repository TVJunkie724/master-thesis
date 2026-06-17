from typing import Literal

from pydantic import BaseModel, Field

from src.schemas.cloud_access import CloudAccessProvider
from src.schemas.pricing_review import PricingCalculationSource, PricingFreshness


PricingHealthState = Literal[
    "fresh",
    "stale",
    "review_required",
    "missing",
    "failed",
]
PricingHealthSeverity = Literal["success", "warning", "error", "info"]


class PricingCredentialSummary(BaseModel):
    connection_id: str | None = None
    provider: CloudAccessProvider
    purpose: Literal["pricing"]
    scope: Literal["user", "public"]
    identity_label: str
    status: str
    provider_account_id: str | None = None
    provider_project_id: str | None = None
    provider_subscription_id: str | None = None


class ProviderPricingHealth(BaseModel):
    provider: CloudAccessProvider
    state: PricingHealthState
    severity: PricingHealthSeverity
    review_required: bool
    can_calculate: bool
    calculation_source: PricingCalculationSource
    pricing_freshness: PricingFreshness
    age: str | None = None
    last_fetched_at: str | None = None
    source_label: str
    credential_summary: PricingCredentialSummary
    primary_message: str
    actions: list[str] = Field(default_factory=list)


class PricingHealthResponse(BaseModel):
    schema_version: str = "pricing-health.v1"
    providers: dict[CloudAccessProvider, ProviderPricingHealth]
