"""Closed, secret-free evidence contract for one destroy operation."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


ProviderId = Literal["aws", "azure", "gcp"]
InventoryStatus = Literal["empty", "residual", "inspection_failed", "not_run"]


class TerraformCleanupEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    destroy_status: Literal["completed", "failed", "dry_run"]
    observed_before_resource_count: int | None = Field(default=None, ge=0)
    post_destroy_inventory: InventoryStatus
    residual_resource_count: int | None = Field(default=None, ge=0)


class ProviderCleanupEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: ProviderId
    cleanup_status: Literal["completed", "failed", "not_run"]
    discovered_during_cleanup_count: int | None = Field(default=None, ge=0)
    discovered_resource_kinds: list[str] = Field(default_factory=list)
    post_destroy_inventory: InventoryStatus
    residual_resource_count: int | None = Field(default=None, ge=0)


class RetainedSharedPrerequisite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: Literal["azure", "gcp"]
    requirement_type: Literal["resource_provider", "api"]
    capability_id: str = Field(
        min_length=1,
        max_length=255,
        pattern=r"^[A-Za-z0-9._/-]+$",
    )
    scope: Literal["subscription", "project"]
    reason: Literal["persistent_account_prerequisite"] = (
        "persistent_account_prerequisite"
    )


class CleanupResidualFailure(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scope: Literal["terraform_state", "provider_cleanup", "provider_inventory"]
    provider: ProviderId | None = None
    reason: Literal[
        "resources_remain",
        "inspection_failed",
        "cleanup_failed",
        "context_unavailable",
    ]


class CleanupEvidence(BaseModel):
    """Final cleanup classification consumed by Management and the UI."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["cleanup-evidence.v1"] = "cleanup-evidence.v1"
    status: Literal["complete", "incomplete", "dry_run"]
    terraform: TerraformCleanupEvidence
    providers: list[ProviderCleanupEvidence] = Field(default_factory=list)
    retained_shared_prerequisites: list[RetainedSharedPrerequisite] = Field(
        default_factory=list
    )
    residual_failures: list[CleanupResidualFailure] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_status(self) -> "CleanupEvidence":
        has_residuals = bool(self.residual_failures)
        if self.status == "complete" and has_residuals:
            raise ValueError(
                "Complete cleanup evidence cannot contain residual failures"
            )
        if self.status == "complete" and not self.providers:
            raise ValueError("Complete cleanup evidence requires provider inventory")
        if self.status == "incomplete" and not has_residuals:
            raise ValueError("Incomplete cleanup evidence requires residual failures")
        return self


def validate_cleanup_evidence(value: dict) -> dict:
    """Validate and normalize evidence at service boundaries."""
    return CleanupEvidence.model_validate(value).model_dump(mode="json")


__all__ = ["CleanupEvidence", "validate_cleanup_evidence"]
