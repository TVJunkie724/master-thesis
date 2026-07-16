from __future__ import annotations

from datetime import datetime
from enum import StrEnum
import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AuthProviderName(StrEnum):
    GOOGLE = "google"
    UIBK = "uibk"


class AuthProviderCapability(BaseModel):
    provider: AuthProviderName
    display_name: str
    enabled: bool
    unavailable_reason: str | None = None


class AuthProvidersResponse(BaseModel):
    providers: list[AuthProviderCapability]


class AuthStartResponse(BaseModel):
    auth_url: str
    transaction_id: str
    poll_verifier: str = Field(
        json_schema_extra={"format": "password", "x-sensitive": True}
    )
    expires_at: datetime
    poll_interval_ms: int


class AuthSessionCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transaction_id: str = Field(min_length=36, max_length=36)
    poll_verifier: str = Field(
        min_length=32,
        max_length=256,
        json_schema_extra={"writeOnly": True},
    )

    @field_validator("transaction_id", "poll_verifier")
    @classmethod
    def reject_control_characters(cls, value: str) -> str:
        if value != value.strip() or any(ord(char) < 33 or ord(char) == 127 for char in value):
            raise ValueError("must be an opaque value without whitespace")
        return value

    @field_validator("transaction_id")
    @classmethod
    def require_uuid_transaction_id(cls, value: str) -> str:
        try:
            parsed = uuid.UUID(value)
        except ValueError as exc:
            raise ValueError("must be a UUID") from exc
        if str(parsed) != value.lower():
            raise ValueError("must use canonical UUID syntax")
        return value


class CurrentUserResponse(BaseModel):
    id: str
    email: str
    name: str | None = None
    picture_url: str | None = None
    auth_provider: str
    theme_preference: str
    uibk_linked: bool
    google_linked: bool


class AuthExchangeStatus(StrEnum):
    PENDING = "pending"
    AUTHENTICATED = "authenticated"


class AuthSessionExchangeResponse(BaseModel):
    status: AuthExchangeStatus
    access_token: str | None = Field(
        default=None,
        json_schema_extra={"format": "password", "x-sensitive": True},
    )
    token_type: str | None = None
    expires_in: int | None = None
    user: CurrentUserResponse | None = None
