from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from src.schemas.cloud_access import CloudAccessProvider


PricingRefreshStatus = Literal["running", "succeeded", "failed"]
PricingRefreshCredentialScope = Literal["user", "public"]


class PricingRefreshStartRequest(BaseModel):
    pricing_connection_id: str | None = Field(
        default=None,
        description=(
            "User-owned CloudConnection explicitly confirmed for this refresh. "
            "Required for AWS/GCP until dedicated pricing-purpose credentials exist."
        ),
    )
    force: bool = Field(
        default=True,
        description="When true, request a fresh provider fetch instead of using cached pricing.",
    )


class PricingRefreshCredentialSummary(BaseModel):
    connection_id: str | None = None
    identity_label: str
    scope: PricingRefreshCredentialScope
    provider_account_id: str | None = None
    provider_project_id: str | None = None
    provider_subscription_id: str | None = None


class PricingRefreshRunResponse(BaseModel):
    schema_version: str = "pricing-refresh-run.v1"
    refresh_run_id: str
    provider: CloudAccessProvider
    status: PricingRefreshStatus
    credential_summary: PricingRefreshCredentialSummary
    force: bool
    sse_url: str
    result_summary: dict | None = None
    error_code: str | None = None
    error_message: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
