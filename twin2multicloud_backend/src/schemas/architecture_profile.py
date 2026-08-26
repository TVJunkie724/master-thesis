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


class ProviderProfileReference(PinnedArchitectureReference):
    provider: Literal["aws", "azure", "gcp"]


class VersionedArchitectureReference(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    version: str


class OptimizationBundleReference(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    optimization_strategy_id: str
    optimization_strategy_version: str
    calculation_strategy_id: str
    calculation_strategy_version: str
    formula_set_id: str
    formula_set_version: str
    scoring_strategy_id: str
    scoring_strategy_version: str
    compatibility_digest: str


class PricingEvidenceReference(PinnedArchitectureReference):
    provider: Literal["aws", "azure", "gcp"]
    currency: Literal["USD", "EUR"]


class CostContribution(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    currency: Literal["USD", "EUR"]
    monthly_amount: str


class ResolvedComponentAssignment(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    assignment_id: str
    responsibility_id: str
    logical_component_id: str
    provider: Literal["aws", "azure", "gcp"]
    provider_implementation_profile_ref: PinnedArchitectureReference
    deployment_component_id: str
    deployment_component_version: str
    service_id: str
    region: str
    capability_evidence: list[str]
    pricing_model_refs: list[str]
    formula_refs: list[str]
    deployment_specification_component_ids: list[str]
    cost_contribution: CostContribution
    required: Literal[True]


class ResolvedEdgeDeliverySemantics(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    mode: Literal["synchronous", "asynchronous"]
    timeout_policy: Literal["bounded", "not_applicable"]
    retry_policy: Literal["bounded_backoff", "provider_managed_bounded", "none"]
    dead_letter_policy: Literal["required", "provider_managed", "not_applicable"]
    idempotency: Literal["required", "consumer_deduplicated", "not_required"]
    ordering: Literal["per_entity", "best_effort", "not_required"]
    replay: Literal["required", "bounded", "not_supported"]


class ResolvedArchitectureEdgeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    resolved_edge_id: str
    edge_id: str
    source_assignment_id: str
    source_port_id: str
    destination_assignment_id: str
    destination_port_id: str
    edge_implementation_id: str
    mechanism: Literal[
        "provider_native_trigger",
        "source_owned_transition_runtime",
        "typed_synchronous_api",
        "cross_provider_adapter",
    ]
    delivery_semantics: ResolvedEdgeDeliverySemantics
    transfer_route_class: Literal[
        "same_provider_same_region",
        "same_provider_cross_region",
        "cross_provider",
    ]
    transfer_evidence_refs: list[str]
    formula_refs: list[str]
    cost_contribution: CostContribution
    trust_contract_ref: VersionedArchitectureReference
    observability_contract_ref: VersionedArchitectureReference
    deployment_input_binding_ids: list[str]
    deployment_output_binding_ids: list[str]


class ResolvedExtensionBinding(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    slot_id: str
    slot_version: str
    artifact_id: str
    artifact_digest: str
    logical_component_id: str
    configuration_digest: str
    validation_contract_version: str


class ResolvedDeploymentSpecificationReference(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["resolved-deployment-specification.v2"]
    calculation_run_id: str
    digest: str


class ResolvedCostItem(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    item_id: str
    monthly_amount: str


class ResolvedCostSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    currency: Literal["USD", "EUR"]
    responsibility_totals: list[ResolvedCostItem]
    component_totals: list[ResolvedCostItem]
    edge_totals: list[ResolvedCostItem]
    monthly_total: str


class FunctionalCompletenessResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["complete"]
    required_capability_ids: list[str]
    provided_capability_ids: list[str]
    provider_extra_capability_ids: list[str]
    missing_capability_ids: list[str]
    validator_version: str
    validation_digest: str


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


class ResolvedTwinArchitectureContractV2(BaseModel):
    """Strict public v2 resolution including typed component and edge data."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["resolved-twin-architecture.v2"]
    resolution_status: Literal["offline_contract_fixture", "publishable"]
    resolution_id: str
    calculation_run_id: str
    architecture_profile_ref: PinnedArchitectureReference
    optimization_bundle_ref: OptimizationBundleReference
    provider_profile_refs: list[ProviderProfileReference]
    workload_contract_ref: PinnedArchitectureReference
    pricing_evidence_refs: list[PricingEvidenceReference]
    component_assignments: list[ResolvedComponentAssignment]
    resolved_edges: list[ResolvedArchitectureEdgeResponse]
    extension_bindings: list[ResolvedExtensionBinding]
    deployment_specification_ref: ResolvedDeploymentSpecificationReference
    cost_summary: ResolvedCostSummary
    functional_completeness: FunctionalCompletenessResponse
    content_digest: str


ResolvedTwinArchitectureDocument = ResolvedTwinArchitectureContractV2


class ResolvedArchitectureReadResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    twin_id: str
    calculation_run_id: str
    selected_for_deployment_at: datetime | None
    architecture_compatibility_status: Literal["ready"]
    origin: Literal["native_v2"]
    architecture: ResolvedTwinArchitectureDocument


class ArchitectureErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error_code: str
    message: str
    fix_suggestion: str
    http_status: int
    request_id: str
