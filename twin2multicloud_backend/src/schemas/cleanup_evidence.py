"""Closed Management API contract for post-destroy cleanup evidence."""

from __future__ import annotations

from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

ProviderId = Literal["aws", "azure", "gcp"]
InventoryStatus = Literal["empty", "residual", "inspection_failed", "not_run"]
ResourceKind = Annotated[
    str,
    Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9 /._()-]+$"),
]


class TerraformCleanupEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    destroy_status: Literal["completed", "failed", "dry_run"]
    observed_before_resource_count: int | None = Field(default=None, ge=0)
    post_destroy_inventory: InventoryStatus
    residual_resource_count: int | None = Field(default=None, ge=0)


class ProviderCleanupEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: ProviderId
    cleanup_status: Literal["completed", "failed", "not_run"]
    discovered_during_cleanup_count: int | None = Field(default=None, ge=0)
    discovered_resource_kinds: list[ResourceKind] = Field(
        default_factory=list,
        max_length=32,
    )
    post_destroy_inventory: InventoryStatus
    residual_resource_count: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_inventory_shape(self) -> Self:
        if self.cleanup_status == "completed" and (
            self.discovered_during_cleanup_count is None
        ):
            raise ValueError("Completed provider cleanup requires a discovery count")
        if self.post_destroy_inventory == "empty" and self.residual_resource_count != 0:
            raise ValueError("Empty provider inventory requires a zero residual count")
        if self.post_destroy_inventory == "residual" and not (
            self.residual_resource_count and self.residual_resource_count > 0
        ):
            raise ValueError("Residual provider inventory requires a positive count")
        if self.post_destroy_inventory in {"inspection_failed", "not_run"} and (
            self.residual_resource_count is not None
        ):
            raise ValueError("Unobserved provider inventory cannot contain a count")
        return self


class RetainedSharedPrerequisite(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: Literal["azure", "gcp"]
    requirement_type: Literal["resource_provider", "api"]
    capability_id: str = Field(
        min_length=1,
        max_length=255,
        pattern=r"^[A-Za-z0-9._/-]+$",
    )
    scope: Literal["subscription", "project"]
    reason: Literal["persistent_account_prerequisite"]


class CleanupResidualFailure(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    scope: Literal["terraform_state", "provider_cleanup", "provider_inventory"]
    provider: ProviderId | None = None
    reason: Literal[
        "resources_remain",
        "inspection_failed",
        "cleanup_failed",
        "context_unavailable",
    ]


class CleanupEvidence(BaseModel):
    """Authoritative terminal result accepted from the Deployer."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["cleanup-evidence.v1"]
    status: Literal["complete", "incomplete", "dry_run"]
    terraform: TerraformCleanupEvidence
    providers: list[ProviderCleanupEvidence] = Field(default_factory=list, max_length=3)
    retained_shared_prerequisites: list[RetainedSharedPrerequisite] = Field(
        default_factory=list,
        max_length=100,
    )
    residual_failures: list[CleanupResidualFailure] = Field(
        default_factory=list,
        max_length=8,
    )

    @model_validator(mode="after")
    def validate_terminal_consistency(self) -> Self:
        provider_ids = [item.provider for item in self.providers]
        if len(provider_ids) != len(set(provider_ids)):
            raise ValueError("Cleanup evidence providers must be unique")
        if self.status == "complete":
            if self.residual_failures or not self.providers:
                raise ValueError(
                    "Complete cleanup requires provider evidence without residuals"
                )
            if (
                self.terraform.destroy_status != "completed"
                or self.terraform.post_destroy_inventory != "empty"
                or self.terraform.residual_resource_count != 0
            ):
                raise ValueError("Complete cleanup requires an empty Terraform state")
            if any(
                item.cleanup_status != "completed"
                or item.post_destroy_inventory != "empty"
                or item.residual_resource_count != 0
                for item in self.providers
            ):
                raise ValueError("Complete cleanup requires empty provider inventories")
        elif self.status == "incomplete" and not self.residual_failures:
            raise ValueError("Incomplete cleanup requires residual failure evidence")
        return self


def validate_cleanup_evidence(value: object) -> dict:
    """Validate and normalize one secret-free Deployer result."""
    return CleanupEvidence.model_validate(value).model_dump(mode="json")


__all__ = ["CleanupEvidence", "validate_cleanup_evidence"]
