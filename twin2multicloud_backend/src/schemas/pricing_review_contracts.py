from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from src.schemas.cloud_access import CloudAccessProvider


PricingCandidateReviewState = Literal[
    "ready",
    "needs_review",
    "evidence_unavailable",
]
PricingReviewDecisionKind = Literal["approve", "select_alternative", "reject", "defer"]


class PricingCandidateSelection(BaseModel):
    candidate_id: str | None = None
    selectable: bool
    confidence_label: str


class PricingReviewCandidate(BaseModel):
    candidate_id: str
    source_type: str
    field_path: str
    service: str | None = None
    field: str | None = None
    value: object | None = None
    currency: str | None = None
    unit: str | None = None
    source_label: str
    evidence_status: str
    selected_row: dict | None = None


class PricingRejectedCandidate(BaseModel):
    candidate_id: str
    reasons: list[str] = Field(default_factory=list)
    selected_row: dict | None = None


class PricingAiSuggestion(BaseModel):
    enabled: bool = False
    candidate_id: str | None = None
    rationale: str = "AI review is disabled for this environment."


class PricingCandidateReportResponse(BaseModel):
    schema_version: str = "pricing-candidate-report.v1"
    report_id: str
    provider: CloudAccessProvider
    refresh_run_id: str
    intent_id: str
    expected_model: str | None = None
    expected_unit: str | None = None
    deterministic_selection: PricingCandidateSelection
    ai_suggestion: PricingAiSuggestion = Field(default_factory=PricingAiSuggestion)
    candidates: list[PricingReviewCandidate] = Field(default_factory=list)
    rejected_candidates: list[PricingRejectedCandidate] = Field(default_factory=list)
    review_state: PricingCandidateReviewState
    source_status: str
    source_warning: str | None = None
    created_at: datetime


class PricingCandidateReportListResponse(BaseModel):
    schema_version: str = "pricing-candidate-report-list.v1"
    provider: CloudAccessProvider
    refresh_run_id: str
    reports: list[PricingCandidateReportResponse]


class PricingTraceSanitization(BaseModel):
    bounded: bool
    secret_free: bool
    omitted_raw_rows: int


class PricingTraceResponse(BaseModel):
    schema_version: str = "pricing-trace.v1"
    report_id: str
    provider: CloudAccessProvider
    intent: dict
    query_scope: dict
    selected_candidate: dict | None = None
    close_candidates: list[dict] = Field(default_factory=list)
    rejected_candidates: list[dict] = Field(default_factory=list)
    hard_checks: list[dict] = Field(default_factory=list)
    normalization: dict = Field(default_factory=dict)
    formula_ref: str | None = None
    sanitization: PricingTraceSanitization


class PricingReviewDecisionCreate(BaseModel):
    report_id: str
    decision: PricingReviewDecisionKind
    selected_candidate_id: str | None = None
    rationale: str | None = Field(default=None, max_length=2000)


class PricingReviewDecisionResponse(BaseModel):
    schema_version: str = "pricing-review-decision.v1"
    decision_id: str
    report_id: str
    provider: CloudAccessProvider
    intent_id: str
    decision: PricingReviewDecisionKind
    selected_candidate_id: str | None = None
    rationale: str | None = None
    created_at: datetime


class PricingReviewDecisionListResponse(BaseModel):
    schema_version: str = "pricing-review-decision-list.v1"
    decisions: list[PricingReviewDecisionResponse]
