"""Public, secret-free Management API contracts for architecture profiles."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class PinnedArchitectureReference(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    version: str
    digest: str


class ArchitectureResponsibilitySummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    responsibility_id: str
    display_name: str
    required: bool
    capability_ids: list[str]
    workload_field_ids: list[str]


class ArchitectureProviderSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: Literal["aws", "azure", "gcp"]
    supported: bool
    profile_id: str
    profile_version: str
    reason_codes: list[str]


class ArchitectureExtensionSlotSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    slot_id: str
    slot_version: str
    logical_component_id: str


class ArchitectureProfileSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    profile_id: str
    profile_version: str
    profile_digest: str
    display_name: str
    description: str
    lifecycle_status: Literal["active"]
    responsibilities: list[ArchitectureResponsibilitySummary]
    capability_ids: list[str]
    workload_contract_ref: PinnedArchitectureReference
    available_providers: list[ArchitectureProviderSummary]
    unsupported_providers: list[ArchitectureProviderSummary]
    extension_slots: list[ArchitectureExtensionSlotSummary]


class ArchitectureVisualizationNode(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    label: str
    responsibility_id: str


class ArchitectureVisualizationEdge(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    source: str
    destination: str


class ArchitectureVisualization(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    nodes: list[ArchitectureVisualizationNode]
    edges: list[ArchitectureVisualizationEdge]


class ArchitectureProfileDetailResponse(ArchitectureProfileSummaryResponse):
    logical_components: list[dict[str, Any]]
    logical_edges: list[dict[str, Any]]
    visualization: ArchitectureVisualization


class TwinArchitectureSelectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    twin_id: str
    profile_id: str
    profile_version: str
    profile_digest: str
    revision: int
    selected_at: datetime
    updated_at: datetime
    selected_by_user_id: str


class ArchitectureProfileChangeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_id: str = Field(
        pattern=r"^[a-z][a-z0-9]*(?:[.-][a-z0-9]+)*$",
        max_length=128,
    )
    profile_version: str = Field(pattern=r"^[1-9][0-9]*$", max_length=32)
    expected_revision: int = Field(ge=1)


class ArchitectureProfileSelectionRequest(ArchitectureProfileChangeRequest):
    invalidation_digest: str = Field(
        pattern=r"^sha256:[0-9a-f]{64}$",
    )


class IncompatibleWorkloadField(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    field_id: str
    display_label: str


class IncompatibleExtensionBinding(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    slot_id: str
    slot_version: str
    artifact_id: str


class ArchitectureProfileChangePreviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    current: PinnedArchitectureReference
    target: PinnedArchitectureReference
    expected_revision: int
    incompatible_workload_fields: list[IncompatibleWorkloadField]
    incompatible_extension_bindings: list[IncompatibleExtensionBinding]
    selected_calculation_run_id: str | None
    deployment_readiness_sections: list[str]
    invalidation_digest: str


class ArchitectureProfileSelectionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selection: TwinArchitectureSelectionResponse
    revision: int
    invalidated_calculation_run_id: str | None
    unbound_extension_slot_ids: list[str]
    cleared_workload_field_ids: list[str]
    deployment_readiness_state: Literal["unchanged", "invalidated"]


class ResolvedTwinArchitectureContract(BaseModel):
    """Typed top-level v1 resolution; nested data stays contract-owned."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["resolved-twin-architecture.v1"]
    resolution_id: str
    calculation_run_id: str
    architecture_profile_ref: PinnedArchitectureReference
    optimization_bundle_ref: dict[str, Any]
    provider_profile_refs: list[dict[str, Any]]
    workload_contract_ref: PinnedArchitectureReference
    pricing_evidence_refs: list[dict[str, Any]]
    component_assignments: list[dict[str, Any]]
    resolved_edges: list[dict[str, Any]]
    extension_bindings: list[dict[str, Any]]
    deployment_specification_ref: dict[str, Any]
    cost_summary: dict[str, Any]
    functional_completeness: dict[str, Any]
    content_digest: str


class ResolvedArchitectureReadResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    twin_id: str
    calculation_run_id: str
    selected_for_deployment_at: datetime | None
    architecture_compatibility_status: Literal[
        "ready",
        "legacy_not_resolvable",
    ]
    origin: Literal["native_v1", "reconstructed_v1"]
    architecture: ResolvedTwinArchitectureContract


class ArchitectureErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error_code: str
    message: str
    fix_suggestion: str
    http_status: int
    request_id: str
