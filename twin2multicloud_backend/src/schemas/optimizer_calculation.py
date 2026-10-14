"""Profile-specific Management contracts for Optimizer calculation inputs."""

from functools import lru_cache
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

SIX_LAYER_WORKLOAD_ROOT = (
    Path(__file__).resolve().parents[1]
    / "contracts"
    / "generated"
    / "six-layer-workload"
    / "v1"
)


@lru_cache(maxsize=1)
def _six_layer_scenarios() -> tuple[dict, ...]:
    try:
        return tuple(
            json.loads(
                (
                    SIX_LAYER_WORKLOAD_ROOT / "fixtures" / "valid" / f"core-{size}.json"
                ).read_text(encoding="utf-8")
            )
            for size in ("small", "medium", "large")
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("Six-layer workload fixtures are unavailable") from exc


class OptimizerCalculationParams(BaseModel):
    """Closed S/M/L workload for the active Six-layer profile."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    schemaVersion: Literal["six-layer-workload.v1"]
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

    @model_validator(mode="after")
    def validate_frozen_scenario(self) -> "OptimizerCalculationParams":
        payload = self.model_dump(exclude={"currency"})
        scenarios = [
            {key: value for key, value in scenario.items() if key != "currency"}
            for scenario in _six_layer_scenarios()
        ]
        if payload not in scenarios:
            raise ValueError(
                "Six-layer workload v1 accepts only the immutable Small, Medium, or "
                "Large Core scenario"
            )
        return self

    def to_optimizer_payload(self) -> dict:
        return self.model_dump()

    def to_persisted_payload(self) -> dict:
        return self.model_dump()
