"""Profile-specific Management contracts for Optimizer calculation inputs."""

from functools import lru_cache
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic_core import PydanticCustomError

from src.contracts.executable_topology import (
    ERROR_HANDLING_FIELD,
    UNSUPPORTED_ERROR_HANDLING_MESSAGE,
    UNSUPPORTED_ERROR_HANDLING_TOPOLOGY,
    ensure_executable_error_handling_topology,
)


COMPATIBILITY_ASSUMPTION_FIELDS = (
    "averageDigitalTwinQueryUnitsPerQuery",
    "averageDigitalTwinQueryResponseSizeInKb",
)
FIVE_LAYER_V2_WORKLOAD_ROOT = (
    Path(__file__).resolve().parents[1]
    / "contracts"
    / "generated"
    / "five-layer-workload"
    / "v2"
)


@lru_cache(maxsize=1)
def _five_layer_v2_scenarios() -> tuple[dict, ...]:
    try:
        return tuple(
            json.loads(
                (
                    FIVE_LAYER_V2_WORKLOAD_ROOT
                    / "fixtures"
                    / "valid"
                    / f"core-{size}.json"
                ).read_text(encoding="utf-8")
            )
            for size in ("small", "medium", "large")
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("Five-layer v2 workload fixtures are unavailable") from exc


class OptimizerCalculationParams(BaseModel):
    """Validated calculation inputs shared by every Management write path."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    numberOfDevices: int = Field(..., gt=0)
    deviceSendingIntervalInMinutes: float = Field(..., gt=0)
    averageSizeOfMessageInKb: float = Field(..., gt=0)

    hotStorageDurationInMonths: int = Field(..., ge=1)
    coolStorageDurationInMonths: int = Field(..., ge=1)
    archiveStorageDurationInMonths: int = Field(..., ge=6)

    needs3DModel: bool
    entityCount: int = Field(..., ge=0)
    average3DModelSizeInMB: float = Field(default=100.0, gt=0)
    averageDigitalTwinQueryUnitsPerQuery: float = Field(
        default=1.0,
        gt=0,
        strict=True,
    )
    averageDigitalTwinQueryResponseSizeInKb: float = Field(
        default=1.0,
        gt=0,
        strict=True,
    )

    amountOfActiveEditors: int = Field(..., ge=0)
    amountOfActiveViewers: int = Field(..., ge=0)
    dashboardRefreshesPerHour: int = Field(..., ge=0)
    dashboardActiveHoursPerDay: int = Field(..., ge=0, le=24)

    useEventChecking: bool = False
    triggerNotificationWorkflow: bool = False
    returnFeedbackToDevice: bool = False
    integrateErrorHandling: bool = Field(
        default=False,
        strict=True,
        description=(
            "Legacy compatibility field. The executable five-layer baseline "
            "accepts only false or omission."
        ),
        json_schema_extra={"const": False},
    )

    orchestrationActionsPerMessage: int = Field(default=3, ge=1)
    eventsPerMessage: int = Field(default=1, ge=1)
    apiCallsPerDashboardRefresh: int = Field(default=1, ge=1)

    numberOfDeviceTypes: int = Field(default=1, ge=1)
    numberOfEventActions: int = Field(default=0, ge=0)
    eventTriggerRate: float = Field(default=0.1, ge=0.0, le=1.0)

    allowGcpSelfHostedL4: bool = False
    allowGcpSelfHostedL5: bool = False
    currency: Literal["USD", "EUR"] = "USD"
    optimizationProfileId: str = "cost_minimization_v1"

    @field_validator(ERROR_HANDLING_FIELD)
    @classmethod
    def validate_error_handling_topology(cls, value: bool) -> bool:
        try:
            ensure_executable_error_handling_topology(value)
        except ValueError as exc:
            raise PydanticCustomError(
                UNSUPPORTED_ERROR_HANDLING_TOPOLOGY,
                UNSUPPORTED_ERROR_HANDLING_MESSAGE,
            ) from exc
        return value

    @model_validator(mode="after")
    def validate_executable_contract(self) -> "OptimizerCalculationParams":
        if self.hotStorageDurationInMonths > self.coolStorageDurationInMonths:
            raise ValueError("Hot storage duration must be <= cool storage duration")
        if self.coolStorageDurationInMonths > self.archiveStorageDurationInMonths:
            raise ValueError("Cool storage duration must be <= archive storage duration")
        if self.allowGcpSelfHostedL4 or self.allowGcpSelfHostedL5:
            raise ValueError(
                "GCP self-hosted L4/L5 cannot be enabled until the Deployer "
                "implements and verifies those deployment paths"
            )
        return self

    def to_optimizer_payload(self) -> dict:
        """Preserve omission of additive defaults for downstream provenance."""
        payload = self.model_dump()
        for field in COMPATIBILITY_ASSUMPTION_FIELDS:
            if field not in self.model_fields_set:
                payload.pop(field, None)
        return payload

    def to_persisted_payload(self) -> dict:
        """Return the complete canonical representation used for persistence."""
        return self.model_dump()


class FiveLayerV2OptimizerCalculationParams(BaseModel):
    """Closed S/M/L workload accepted only with ``five-layer-baseline@2``."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    schemaVersion: Literal["five-layer-workload.v2"]
    numberOfDevices: int = Field(gt=0, strict=True)
    deviceSendingIntervalInMinutes: float = Field(gt=0, strict=True)
    averageSizeOfMessageInKb: float = Field(gt=0, strict=True)
    numberOfDeviceTypes: int = Field(ge=1, strict=True)
    hotStorageDurationInMonths: int = Field(ge=1, strict=True)
    coolStorageDurationInMonths: int = Field(ge=1, strict=True)
    archiveStorageDurationInMonths: int = Field(ge=6, strict=True)
    twinEntityCount: int = Field(ge=1, strict=True)
    aggregateDashboardRefreshesPerHour: int = Field(ge=0, strict=True)
    apiCallsPerAggregateDashboardRefresh: int = Field(ge=1, strict=True)
    dashboardActiveHoursPerDay: int = Field(ge=0, le=24, strict=True)
    monthlyEditorSeats: int = Field(ge=0, strict=True)
    monthlyViewerSeats: int = Field(ge=0, strict=True)
    twinStateMaterializationsPerSecond: float = Field(ge=0, strict=True)
    twinGraphUpdatesPerSecond: float = Field(ge=0, strict=True)
    eventingScenarioId: Literal[
        "eventing-small-v1",
        "eventing-medium-v1",
        "eventing-large-v1",
    ]
    currency: Literal["USD", "EUR"] = "USD"
    optimizationProfileId: Literal["cost-minimization-v2"] = (
        "cost-minimization-v2"
    )

    @model_validator(mode="after")
    def validate_frozen_scenario(self) -> "FiveLayerV2OptimizerCalculationParams":
        payload = self.model_dump(
            exclude={"optimizationProfileId", "currency"}
        )
        scenarios = [
            {
                key: value
                for key, value in scenario.items()
                if key != "currency"
            }
            for scenario in _five_layer_v2_scenarios()
        ]
        if payload not in scenarios:
            raise ValueError(
                "Five-layer v2 accepts only the immutable Small, Medium, or "
                "Large Core scenario"
            )
        return self

    def to_optimizer_payload(self) -> dict:
        return self.model_dump()

    def to_persisted_payload(self) -> dict:
        return self.model_dump()
