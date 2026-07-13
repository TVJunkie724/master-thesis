"""Versioned Twin deployment readiness and preflight contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, Self

from pydantic import BaseModel, Field, model_validator


CloudProvider = Literal["aws", "azure", "gcp"]
CheckStatus = Literal["passed", "failed"]
ProviderReadinessStatus = Literal[
    "ready",
    "review_required",
    "not_checked",
    "stale",
]
PermissionSetStatus = Literal["matched", "missing", "outdated"]
SafePermission = Annotated[str, Field(min_length=1, max_length=300)]


class DeploymentReadinessCheck(BaseModel):
    component: str = Field(min_length=1, max_length=80)
    status: CheckStatus
    code: str = Field(min_length=1, max_length=120)
    message: str = Field(min_length=1, max_length=2_000)
    action: str = Field(min_length=1, max_length=2_000)
    permissions: list[SafePermission] = Field(default_factory=list, max_length=250)


class ProviderDeploymentReadiness(BaseModel):
    provider: CloudProvider
    connection_id: str | None = Field(default=None, min_length=1, max_length=160)
    connection_display_name: str | None = Field(default=None, min_length=1, max_length=120)
    ready: bool
    status: ProviderReadinessStatus
    summary: str = Field(min_length=1, max_length=2_000)
    expected_permission_set_version: str = Field(min_length=1, max_length=80)
    supplied_permission_set_version: str | None = Field(default=None, max_length=80)
    permission_set_status: PermissionSetStatus
    checked_at: datetime | None = None
    checks: list[DeploymentReadinessCheck] = Field(min_length=1, max_length=32)

    @model_validator(mode="after")
    def validate_consistency(self) -> Self:
        if self.ready != (self.status == "ready"):
            raise ValueError("ready and status must be consistent")
        if self.ready and self.permission_set_status != "matched":
            raise ValueError("ready providers require a matched permission set")
        if self.ready and (self.connection_id is None or self.checked_at is None):
            raise ValueError("ready providers require a connection and checked_at")
        if self.ready != all(check.status == "passed" for check in self.checks):
            raise ValueError("ready and checks must be consistent")
        return self


class DeploymentReadinessResponse(BaseModel):
    schema_version: Literal["deployment-readiness.v1"] = "deployment-readiness.v1"
    twin_id: str = Field(min_length=1, max_length=160)
    ready: bool
    summary: str = Field(min_length=1, max_length=2_000)
    required_providers: list[CloudProvider] = Field(max_length=3)
    providers: list[ProviderDeploymentReadiness] = Field(max_length=3)
    checked_at: datetime | None = None
    issues: list[DeploymentReadinessCheck] = Field(default_factory=list, max_length=16)

    @model_validator(mode="after")
    def validate_consistency(self) -> Self:
        _validate_aggregate_consistency(self)
        return self


class DeploymentPreflightResponse(BaseModel):
    schema_version: Literal["deployment-preflight.v1"] = "deployment-preflight.v1"
    twin_id: str = Field(min_length=1, max_length=160)
    ready: bool
    summary: str = Field(min_length=1, max_length=2_000)
    required_providers: list[CloudProvider] = Field(max_length=3)
    providers: list[ProviderDeploymentReadiness] = Field(max_length=3)
    checked_at: datetime | None = None
    issues: list[DeploymentReadinessCheck] = Field(default_factory=list, max_length=16)

    @model_validator(mode="after")
    def validate_consistency(self) -> Self:
        _validate_aggregate_consistency(self)
        return self


def _validate_aggregate_consistency(
    response: DeploymentReadinessResponse | DeploymentPreflightResponse,
) -> None:
    if len(set(response.required_providers)) != len(response.required_providers):
        raise ValueError("required_providers must not contain duplicates")
    if [provider.provider for provider in response.providers] != response.required_providers:
        raise ValueError("providers must match required_providers in order")
    aggregate_ready = bool(response.required_providers) and not response.issues and all(
        provider.ready for provider in response.providers
    )
    if response.ready != aggregate_ready:
        raise ValueError("aggregate readiness is inconsistent")
    if response.ready and response.checked_at is None:
        raise ValueError("ready responses require checked_at")
