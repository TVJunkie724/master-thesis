"""Typed read models for ResolvedDeploymentSpecification v1."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_serializer


DeploymentCompatibilityStatus = Literal["ready", "legacy_not_deployable"]
DeploymentScalar = str | int | bool


class ResolvedDeploymentCatalogReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snapshot_id: str
    pricing_region: str
    content_digest: str


class ResolvedDeploymentOptimizationContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    optimization_profile_id: str
    optimization_profile_version: str
    calculation_strategy_id: str
    formula_set_id: str
    workload_contract_id: str
    pricing_registry_version: str
    catalog_references: dict[str, ResolvedDeploymentCatalogReference]


class ResolvedDeploymentArchitectureProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_id: Literal["five-layer-baseline"]
    profile_version: Literal["1"]


class ResolvedDeploymentDimension(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dimension_id: str
    classification: Literal[
        "deployable_selection",
        "usage_tier",
        "account_scope",
        "non_deployable_assumption",
    ]
    value: DeploymentScalar
    formula_reference: str
    evidence_reference: str
    unit: str | None = None
    terraform_target: str | None = None

    @model_serializer(mode="wrap")
    def serialize_without_absent_metadata(self, handler):
        serialized = handler(self)
        return {
            field: value
            for field, value in serialized.items()
            if value is not None
        }


class ResolvedDeploymentComponent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    component_id: str
    slot_id: Literal[
        "l1_ingestion",
        "l2_processing",
        "l3_hot_storage",
        "l3_cool_storage",
        "l3_archive_storage",
        "l4_twin_state",
        "l5_visualization",
        "cross_cloud_glue",
    ]
    provider: Literal["aws", "azure", "gcp"]
    service_id: str
    required: Literal[True]
    dimensions: list[ResolvedDeploymentDimension] = Field(
        min_length=1,
        max_length=16,
    )


class ResolvedDeploymentSpecification(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["resolved-deployment-specification.v1"]
    calculation_run_id: str
    architecture_profile: ResolvedDeploymentArchitectureProfile
    optimization_context: ResolvedDeploymentOptimizationContext
    currency: Literal["USD"]
    components: list[ResolvedDeploymentComponent] = Field(
        min_length=7,
        max_length=64,
    )
    digest: str
