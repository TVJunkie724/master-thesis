"""Closed Management API contracts for Six-layer telemetry evidence."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

Provider = Literal["aws", "azure", "gcp"]
VerificationStatus = Literal["running", "pass", "fail", "not_run"]


class TelemetryPhaseEvidence(BaseModel):
    """One allowlisted, secret-free successful phase observation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    phase: Literal[1, 2, 3]
    kind: Literal[
        "message_accepted",
        "trace_correlated_hot_record",
        "twinmaker_property_projection",
        "azure_twin_projection",
        "gcp_twin_projection",
    ]
    provider: Provider
    record_count: int | None = Field(default=None, ge=1, le=100)
    correlation: Literal["source_sequence"] | None = None

    @model_validator(mode="after")
    def validate_phase_shape(self) -> Self:
        expected_kinds = {
            1: {"message_accepted"},
            2: {"trace_correlated_hot_record"},
            3: {
                "twinmaker_property_projection",
                "azure_twin_projection",
                "gcp_twin_projection",
            },
        }
        if self.kind not in expected_kinds[self.phase]:
            raise ValueError("Telemetry evidence kind does not match its phase")
        if self.phase == 2 and self.record_count is None:
            raise ValueError("L3 evidence requires a positive record count")
        if self.phase != 2 and self.record_count is not None:
            raise ValueError("Only L3 evidence may contain a record count")
        if self.phase == 3 and self.correlation != "source_sequence":
            raise ValueError("L4 evidence requires source-sequence correlation")
        if self.phase != 3 and self.correlation is not None:
            raise ValueError("Only L4 evidence may contain correlation metadata")
        provider_kind = {
            "twinmaker_property_projection": "aws",
            "azure_twin_projection": "azure",
            "gcp_twin_projection": "gcp",
        }
        expected_provider = provider_kind.get(self.kind)
        if expected_provider is not None and self.provider != expected_provider:
            raise ValueError("L4 evidence kind does not match its provider")
        return self


class TelemetryVerificationEvidence(BaseModel):
    """Authoritative terminal result accepted from the Deployer."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["telemetry-verification.v1"]
    trace_id: str = Field(pattern=r"^VERIFY-[0-9A-F]{8}$")
    status: Literal["pass", "fail"]
    pass_count: int = Field(ge=0, le=3)
    fail_count: int = Field(ge=0, le=1)
    skip_count: int = Field(ge=0, le=2)
    total_time: float = Field(ge=0, le=900)
    failed_phase: (
        Literal[
            "Phase 1 - Message Delivery",
            "Phase 2 - Pipeline to Hot Storage",
            "Phase 3 - Twin Projection",
            "Verification runtime",
        ]
        | None
    ) = None
    evidence: list[TelemetryPhaseEvidence] = Field(max_length=3)

    @model_validator(mode="after")
    def validate_terminal_consistency(self) -> Self:
        if self.pass_count + self.fail_count + self.skip_count != 3:
            raise ValueError(
                "Telemetry terminal counts must cover exactly three phases"
            )
        if (self.status == "pass") != (self.fail_count == 0):
            raise ValueError("Telemetry status and failure count disagree")
        if (self.status == "fail") != (self.failed_phase is not None):
            raise ValueError("Failed telemetry evidence requires a failed phase")
        phases = [item.phase for item in self.evidence]
        if len(phases) != len(set(phases)) or len(phases) > self.pass_count:
            raise ValueError(
                "Telemetry evidence phases must be unique successful phases"
            )
        return self


class TelemetryVerificationStartResponse(BaseModel):
    schema_version: Literal["telemetry-verification-session.v1"] = (
        "telemetry-verification-session.v1"
    )
    verification_id: str
    session_id: str
    sse_url: str
    status_url: str
    status: VerificationStatus


class TelemetryVerificationRecordResponse(BaseModel):
    id: str
    twin_id: str
    deployment_id: str | None
    session_id: str
    device_id: str
    status: VerificationStatus
    trace_id: str | None
    result: TelemetryVerificationEvidence | None
    error_code: str | None
    error_message: str | None
    requested_at: datetime
    completed_at: datetime | None


class TelemetryVerificationHistoryResponse(BaseModel):
    schema_version: Literal["telemetry-verification-history.v1"] = (
        "telemetry-verification-history.v1"
    )
    verifications: list[TelemetryVerificationRecordResponse]
