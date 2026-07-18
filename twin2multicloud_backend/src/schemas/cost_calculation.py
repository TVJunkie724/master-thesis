from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from src.schemas.optimizer_calculation import OptimizerCalculationParams
from src.schemas.pricing_catalog import PricingCatalogContext
from src.schemas.resolved_deployment_specification import (
    DeploymentCompatibilityStatus,
    ResolvedDeploymentSpecification,
)


class CostCalculationRunCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    params: OptimizerCalculationParams = Field(
        ...,
        description="Optimizer calculation parameters",
    )
    pricing_evidence_version: Optional[str] = None


class CostCalculationResultItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    run_id: str
    layer: str
    component: Optional[str] = None
    provider: Optional[str] = None
    service_intent_id: Optional[str] = None
    cost_amount: Optional[float] = None
    currency: str
    unit: Optional[str] = None
    quantity: Optional[float] = None
    unit_price: Optional[float] = None
    evidence_id: Optional[str] = None
    service_model_id: Optional[str] = None
    calculation_notes: Optional[dict] = None
    review_status: Optional[str] = None
    created_at: datetime


class CostCalculationRunSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    twin_id: str
    user_id: str
    optimizer_config_id: Optional[str] = None
    status: str
    cheapest_path: Optional[dict] = None
    total_monthly_cost: Optional[float] = None
    currency: str
    optimization_profile_id: str
    optimization_profile_version: Optional[str] = None
    scoring_strategy_id: str
    calculation_model_version: Optional[str] = None
    pricing_registry_version: Optional[str] = None
    pricing_evidence_version: Optional[str] = None
    pricing_run_reference: Optional[str] = None
    pricing_catalog_context: Optional[PricingCatalogContext] = None
    deployment_specification_digest: Optional[str] = None
    deployment_specification_version: Optional[str] = None
    deployment_compatibility_status: DeploymentCompatibilityStatus
    created_at: datetime
    completed_at: Optional[datetime] = None
    selected_for_deployment_at: Optional[datetime] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None


class CostCalculationRunDetailResponse(CostCalculationRunSummaryResponse):
    params: dict
    result_summary: Optional[dict] = None
    resolved_deployment_specification: (
        Optional[ResolvedDeploymentSpecification]
    ) = None
    result_items: list[CostCalculationResultItemResponse] = Field(default_factory=list)


class CostCalculationRunSelectResponse(BaseModel):
    run: CostCalculationRunSummaryResponse
    selected_for_deployment_at: datetime
    resolved_deployment_specification: ResolvedDeploymentSpecification


class PricingEvidenceDetailResponse(BaseModel):
    run_id: str
    twin_id: str
    trace_schema_version: Optional[str] = None
    trace_available: bool
    profile: dict = Field(default_factory=dict)
    workload: dict = Field(default_factory=dict)
    selected_path: list[dict] = Field(default_factory=list)
    records: list[dict] = Field(default_factory=list)
    transfer_trace: list[dict] = Field(default_factory=list)
    summary: dict = Field(default_factory=dict)
    field_trace_schema_version: Optional[str] = None
    field_trace_available: bool
    field_trace_records: list[dict] = Field(default_factory=list)
    transfer_pricing_context_available: bool = False
    transfer_pricing_context: dict = Field(default_factory=dict)
    optimization_diagnostics: dict = Field(default_factory=dict)
    pricing_catalog_context: Optional[PricingCatalogContext] = None
    result_metadata: dict = Field(default_factory=dict)
    result_items: list[CostCalculationResultItemResponse] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
