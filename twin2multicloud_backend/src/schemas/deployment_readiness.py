"""Versioned Twin deployment readiness and preflight contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

CloudProvider = Literal["aws", "azure", "gcp"]
CheckStatus = Literal["passed", "failed"]
ProviderReadinessStatus = Literal[
    "ready",
    "review_required",
    "not_checked",
    "stale",
]
SafePermission = Annotated[str, Field(min_length=1, max_length=300)]
ContentDigest = Annotated[
    str,
    Field(pattern=r"^sha256:[0-9a-f]{64}$"),
]
RequirementReadinessStatus = Literal[
    "ready",
    "preparable",
    "manual_action",
    "replace_connection",
    "transient",
    "unsupported",
]


class DeploymentRequirementReadiness(BaseModel):
    requirement_id: str = Field(min_length=1, max_length=300)
    requirement_type: str = Field(min_length=1, max_length=80)
    provider: CloudProvider
    capability_id: str = Field(min_length=1, max_length=300)
    preparation_mode: Literal[
        "none",
        "confirmed_account",
        "manual_external",
        "terraform",
    ]
    mandatory: bool = True
    status: RequirementReadinessStatus
    message: str = Field(min_length=1, max_length=2_000)
    action: str = Field(min_length=1, max_length=2_000)
    source_node_ids: list[str] = Field(default_factory=list, max_length=512)
    source_edge_ids: list[str] = Field(default_factory=list, max_length=512)


class AccountPreparationAction(BaseModel):
    action_id: str = Field(min_length=1, max_length=500)
    provider: Literal["azure", "gcp"]
    action_type: Literal["register_resource_provider", "enable_project_api"]
    capability_id: str = Field(min_length=1, max_length=300)
    scope: str = Field(min_length=1, max_length=80)
    requirement_ids: list[str] = Field(min_length=1, max_length=64)
    reason: str = Field(min_length=1, max_length=2_000)
    persistent_after_destroy: Literal[True]
    destructive: Literal[False]


class ManualPreparationRequirement(BaseModel):
    requirement_id: str = Field(min_length=1, max_length=300)
    provider: CloudProvider
    capability_id: str = Field(min_length=1, max_length=300)
    reason: str = Field(min_length=1, max_length=2_000)


class DeploymentPreparationPlan(BaseModel):
    schema_version: Literal["graph-account-preparation.v1"]
    graph_digest: ContentDigest
    requirements_digest: ContentDigest
    plan_digest: ContentDigest
    actions: list[AccountPreparationAction] = Field(max_length=4096)
    manual_requirements: list[ManualPreparationRequirement] = Field(max_length=4096)

    @model_validator(mode="after")
    def validate_ordering(self) -> Self:
        if [item.action_id for item in self.actions] != sorted(
            item.action_id for item in self.actions
        ):
            raise ValueError("preparation actions must be sorted")
        if [item.requirement_id for item in self.manual_requirements] != sorted(
            item.requirement_id for item in self.manual_requirements
        ):
            raise ValueError("manual requirements must be sorted")
        return self


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
    connection_display_name: str | None = Field(
        default=None, min_length=1, max_length=120
    )
    ready: bool
    status: ProviderReadinessStatus
    summary: str = Field(min_length=1, max_length=2_000)
    checked_at: datetime | None = None
    graph_digest: ContentDigest | None = None
    requirements_digest: ContentDigest | None = None
    checks: list[DeploymentReadinessCheck] = Field(min_length=1, max_length=32)
    requirements: list[DeploymentRequirementReadiness] = Field(
        default_factory=list,
        max_length=4096,
    )

    @model_validator(mode="after")
    def validate_consistency(self) -> Self:
        if self.ready != (self.status == "ready"):
            raise ValueError("ready and status must be consistent")
        if self.ready and (self.connection_id is None or self.checked_at is None):
            raise ValueError("ready providers require a connection and checked_at")
        if self.ready and (
            self.graph_digest is None or self.requirements_digest is None
        ):
            raise ValueError("ready providers require graph-bound evidence")
        if self.ready and (
            not self.requirements
            or any(item.status != "ready" for item in self.requirements)
        ):
            raise ValueError("ready providers require ready graph requirements")
        if any(item.provider != self.provider for item in self.requirements):
            raise ValueError("provider requirements must share provider ownership")
        expected_ready = (
            all(check.status == "passed" for check in self.checks)
            and bool(self.requirements)
            and all(item.status == "ready" for item in self.requirements)
        )
        if self.ready != expected_ready:
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
    graph_digest: ContentDigest | None = None
    requirements_digest: ContentDigest | None = None
    preparation_plan: DeploymentPreparationPlan | None = None
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
    graph_digest: ContentDigest | None = None
    requirements_digest: ContentDigest | None = None
    preparation_plan: DeploymentPreparationPlan | None = None
    issues: list[DeploymentReadinessCheck] = Field(default_factory=list, max_length=16)

    @model_validator(mode="after")
    def validate_consistency(self) -> Self:
        _validate_aggregate_consistency(self)
        return self


class DeploymentPreparationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_digest: ContentDigest
    requirements_digest: ContentDigest
    confirmed: Literal[True]
    manual_requirement_ids: list[str] = Field(default_factory=list, max_length=4096)

    @model_validator(mode="after")
    def validate_manual_ids(self) -> Self:
        if self.manual_requirement_ids != sorted(set(self.manual_requirement_ids)):
            raise ValueError("manual requirement confirmations must be sorted and unique")
        return self


class PreparationActionResult(BaseModel):
    action_id: str = Field(min_length=1, max_length=500)
    provider: CloudProvider
    capability_id: str = Field(min_length=1, max_length=300)
    status: Literal["ready", "failed"]
    message: str = Field(min_length=1, max_length=2_000)


class DeploymentPreparationResponse(BaseModel):
    schema_version: Literal["deployment-preparation.v1"] = "deployment-preparation.v1"
    twin_id: str = Field(min_length=1, max_length=160)
    plan_digest: ContentDigest
    requirements_digest: ContentDigest
    status: Literal["ready", "partial", "failed", "manual_action"]
    completed_actions: list[PreparationActionResult] = Field(max_length=4096)
    failed_actions: list[PreparationActionResult] = Field(max_length=4096)
    remaining_action_ids: list[str] = Field(max_length=4096)
    acknowledged_manual_requirement_ids: list[str] = Field(max_length=4096)
    pending_manual_requirement_ids: list[str] = Field(max_length=4096)
    retry_safe: Literal[True]
    readiness: DeploymentPreflightResponse


def _validate_aggregate_consistency(
    response: DeploymentReadinessResponse | DeploymentPreflightResponse,
) -> None:
    if len(set(response.required_providers)) != len(response.required_providers):
        raise ValueError("required_providers must not contain duplicates")
    if [
        provider.provider for provider in response.providers
    ] != response.required_providers:
        raise ValueError("providers must match required_providers in order")
    aggregate_ready = (
        bool(response.required_providers)
        and not response.issues
        and all(provider.ready for provider in response.providers)
    )
    if response.ready != aggregate_ready:
        raise ValueError("aggregate readiness is inconsistent")
    if response.ready and response.checked_at is None:
        raise ValueError("ready responses require checked_at")
    provider_graph_digests = {
        provider.graph_digest for provider in response.providers if provider.graph_digest
    }
    provider_requirements_digests = {
        provider.requirements_digest
        for provider in response.providers
        if provider.requirements_digest
    }
    if len(provider_graph_digests) > 1 or len(provider_requirements_digests) > 1:
        raise ValueError("providers must share one requirement inspection")
    if response.graph_digest != next(iter(provider_graph_digests), None):
        raise ValueError("aggregate graph digest is inconsistent")
    if response.requirements_digest != next(
        iter(provider_requirements_digests), None
    ):
        raise ValueError("aggregate requirements digest is inconsistent")
    if response.ready and (
        response.graph_digest is None or response.requirements_digest is None
    ):
        raise ValueError("ready responses require graph-bound evidence")
