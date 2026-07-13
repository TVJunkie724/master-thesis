"""Dashboard-oriented pricing health read model."""

from __future__ import annotations

from src.schemas.cloud_access import CloudAccessInventoryResponse, CloudAccessProvider
from src.schemas.pricing_health import (
    PricingCredentialSummary,
    PricingHealthResponse,
    PricingHealthSeverity,
    ProviderPricingHealth,
)
from src.schemas.pricing_review import PricingReviewStateResponse, ProviderPricingReviewState


PROVIDERS: tuple[CloudAccessProvider, ...] = ("aws", "azure", "gcp")


def build_pricing_health_response(
    review_state: PricingReviewStateResponse,
    cloud_access: CloudAccessInventoryResponse,
) -> PricingHealthResponse:
    return PricingHealthResponse(
        providers={
            provider: _provider_health(
                provider,
                review_state.providers[provider],
                cloud_access.providers[provider].pricing,
            )
            for provider in PROVIDERS
        }
    )


def _provider_health(
    provider: CloudAccessProvider,
    review: ProviderPricingReviewState,
    pricing_access,
) -> ProviderPricingHealth:
    credential_summary = PricingCredentialSummary(
        connection_id=pricing_access.connection_id,
        provider=provider,
        purpose="pricing",
        scope=pricing_access.scope,
        identity_label=pricing_access.identity_label,
        status=pricing_access.status,
        provider_account_id=pricing_access.provider_account_id,
        provider_project_id=pricing_access.provider_project_id,
        provider_subscription_id=pricing_access.provider_subscription_id,
    )
    source_label = _source_label(provider, credential_summary)
    missing_credential = pricing_access.status == "missing"
    state = review.state
    severity = _severity(state, missing_credential)

    return ProviderPricingHealth(
        provider=provider,
        state=state,
        severity=severity,
        review_required=review.review_required or missing_credential,
        can_calculate=review.can_calculate,
        calculation_source=review.calculation_source,
        pricing_freshness=review.pricing_freshness,
        age=review.age,
        last_fetched_at=review.last_known_good_updated_at,
        source_label=source_label,
        credential_summary=credential_summary,
        primary_message=_primary_message(review, missing_credential, source_label),
        actions=_actions(review.actions, missing_credential),
    )


def _severity(state: str, missing_credential: bool) -> PricingHealthSeverity:
    if state in {"failed", "missing"}:
        return "error"
    if missing_credential:
        return "warning"
    if state in {"stale", "review_required"}:
        return "warning"
    if state == "fresh":
        return "success"
    return "info"


def _source_label(
    provider: CloudAccessProvider,
    credential: PricingCredentialSummary,
) -> str:
    if credential.scope == "public":
        return credential.identity_label
    if provider == "aws" and credential.provider_account_id:
        return f"Account {credential.provider_account_id}"
    if provider == "gcp" and credential.provider_project_id:
        return f"Project {credential.provider_project_id}"
    if provider == "azure" and credential.provider_subscription_id:
        return f"Subscription {credential.provider_subscription_id}"
    return credential.identity_label


def _primary_message(
    review: ProviderPricingReviewState,
    missing_credential: bool,
    source_label: str,
) -> str:
    if missing_credential:
        return "Pricing refresh requires a user-scoped pricing credential."
    if review.review_reasons:
        return review.review_reasons[0].reason
    if review.state == "fresh":
        return f"Pricing data is fresh from {source_label}."
    if review.state == "stale":
        return f"Pricing data is stale; refresh from {source_label} is recommended."
    if review.state == "review_required":
        return "Pricing data requires review before publishing new decisions."
    if review.state == "missing":
        return "Pricing data is missing."
    return "Pricing status failed."


def _actions(review_actions: list[str], missing_credential: bool) -> list[str]:
    actions = list(dict.fromkeys(review_actions))
    if missing_credential and "configure_pricing_connection" not in actions:
        actions.append("configure_pricing_connection")
    if "open_pricing_review" not in actions:
        actions.append("open_pricing_review")
    return actions
