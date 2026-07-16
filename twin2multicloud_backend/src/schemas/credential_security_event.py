from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class CredentialSecurityAction(StrEnum):
    CONNECTION_CREATE = "cloud_connection.create"
    CONNECTION_UPDATE = "cloud_connection.update"
    CONNECTION_DELETE = "cloud_connection.delete"
    CONNECTION_VALIDATE = "cloud_connection.validate"
    CONNECTION_PREFLIGHT = "cloud_connection.preflight"
    BOOTSTRAP_PLAN = "cloud_bootstrap.plan"
    BOOTSTRAP_IMPORT = "cloud_bootstrap.import"
    INLINE_VALIDATE = "credentials.validate_inline"
    STORED_VALIDATE = "credentials.validate_stored"


class CredentialSecurityOutcome(StrEnum):
    SUCCEEDED = "succeeded"
    REJECTED = "rejected"
    RATE_LIMITED = "rate_limited"
    CONTROL_UNAVAILABLE = "control_unavailable"


class CredentialSecurityEventDraft(BaseModel):
    """Allowlisted audit payload; arbitrary request metadata is forbidden."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    user_id: str
    action: CredentialSecurityAction
    outcome: CredentialSecurityOutcome
    resource_type: str = Field(min_length=1, max_length=64)
    resource_id: str | None = Field(default=None, max_length=128)
    provider: str | None = Field(default=None, pattern="^(aws|azure|gcp)$")
    purpose: str | None = Field(default=None, pattern="^(deployment|pricing|bootstrap)$")
    http_status: int = Field(ge=100, le=599)
    request_id: str = Field(min_length=1, max_length=64)


class CredentialSecurityEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    action: CredentialSecurityAction
    outcome: CredentialSecurityOutcome
    resource_type: str
    resource_id: str | None
    provider: str | None
    purpose: str | None
    http_status: int
    request_id: str
    occurred_at: datetime


class CredentialSecurityEventPage(BaseModel):
    items: list[CredentialSecurityEventResponse]
    total: int
    limit: int
    offset: int
