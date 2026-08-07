"""Typed read models for resolved deployment specifications."""

from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictFloat,
    StrictInt,
    StrictStr,
    model_serializer,
)


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
        "transition_runtime",
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


class ResolvedDeploymentPinnedReference(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(
        pattern=r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$",
        max_length=256,
    )
    version: str = Field(pattern=r"^[1-9][0-9]*$")
    digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class ResolvedDeploymentPricingReference(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: Literal["aws", "azure", "gcp"]
    digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class ResolvedDeploymentOptimizationContextV2(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    service_decision_ref: ResolvedDeploymentPinnedReference
    component_catalog_ref: ResolvedDeploymentPinnedReference
    workload_ref: ResolvedDeploymentPinnedReference
    eventing_scenario_ref: ResolvedDeploymentPinnedReference
    formula_set_ref: ResolvedDeploymentPinnedReference
    pricing_evidence_refs: list[ResolvedDeploymentPricingReference] = Field(
        min_length=1,
        max_length=3,
    )


class ResolvedDeploymentReadinessV2(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["offline_contract_fixture", "deployment_ready"]
    blocking_gate_ids: list[str] = Field(max_length=16)


class ResolvedDeploymentFixedDimensionsV2(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    l4_inspection_sessions_per_month: Literal[12]
    l4_reads_per_inspection_session: Literal[20]
    visualized_numeric_metrics_per_record: Literal[1]
    rollup_bucket_seconds: Literal[3600]
    reader_timeout_seconds: Literal[10]
    reader_maximum_points: Literal[1000]
    storage_batch_interval_minutes: Literal[5]
    storage_task_max_input_mib: Literal[512]
    storage_object_max_uncompressed_mib: Literal[64]
    storage_transfer_retry_horizon_hours: Literal[24]
    storage_source_expiry_grace_hours: Literal[48]
    azure_mover_max_device_partitions_per_task: Literal[1000]
    gcp_grafana_persistent_disk_gib: Literal[10]


ResolvedDeploymentScalarV2 = Union[
    StrictStr,
    StrictInt,
    StrictFloat,
    StrictBool,
]


class ResolvedDeploymentDimensionV2(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    dimension_id: str
    classification: Literal[
        "deployable_selection",
        "capacity",
        "usage",
        "fixed_poc",
        "account_scope",
    ]
    value: ResolvedDeploymentScalarV2
    unit: str = Field(min_length=1, max_length=64)
    formula_reference: str
    evidence_reference: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    terraform_target: str | None = Field(
        default=None,
        pattern=r"^[a-z][a-z0-9_]{2,127}$",
    )

    @model_serializer(mode="wrap")
    def serialize_without_absent_target(self, handler):
        serialized = handler(self)
        if serialized.get("terraform_target") is None:
            serialized.pop("terraform_target", None)
        return serialized


class ResolvedDeploymentComponentSelectionV2(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    selection_id: str
    architecture_assignment_id: str
    logical_component_id: str
    implementation_component_id: str
    implementation_component_digest: str = Field(
        pattern=r"^sha256:[0-9a-f]{64}$"
    )
    provider: Literal["aws", "azure", "gcp"]
    region: str = Field(min_length=2, max_length=64)
    required: Literal[True]
    dimensions: list[ResolvedDeploymentDimensionV2] = Field(
        min_length=1,
        max_length=64,
    )


class ResolvedDeploymentBindingV2(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    binding_id: str
    source_kind: Literal[
        "catalog_constant",
        "deployment_dimension",
        "component_output",
        "platform_configuration",
        "extension_artifact",
        "platform_runtime_secret_reference",
    ]
    source_ref: str
    destination_selection_id: str
    destination_input_id: str
    value_type: Literal[
        "string",
        "integer",
        "number",
        "boolean",
        "json_document",
    ]
    sensitivity: Literal["public", "internal", "sensitive_reference"]
    resolution_stage: Literal["package", "preplan", "terraform", "postapply"]
    validator_id: str
    compatibility_version: Literal["1"]


class ResolvedDeploymentSpecificationV2(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["resolved-deployment-specification.v2"]
    calculation_run_id: str
    architecture_profile_ref: ResolvedDeploymentPinnedReference
    optimization_context: ResolvedDeploymentOptimizationContextV2
    readiness: ResolvedDeploymentReadinessV2
    currency: Literal["USD", "EUR"]
    fixed_dimensions: ResolvedDeploymentFixedDimensionsV2
    component_selections: list[ResolvedDeploymentComponentSelectionV2] = Field(
        min_length=7,
        max_length=128,
    )
    bindings: list[ResolvedDeploymentBindingV2] = Field(
        min_length=7,
        max_length=256,
    )
    digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


ResolvedDeploymentSpecificationDocument = Annotated[
    Union[
        ResolvedDeploymentSpecification,
        ResolvedDeploymentSpecificationV2,
    ],
    Field(discriminator="schema_version"),
]
