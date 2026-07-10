"""Calculation model declarations for optimization profiles."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CalculationModel:
    model_id: str
    enabled: bool
    compatible_metric_provider_ids: tuple[str, ...]
    compatible_intent_group_ids: tuple[str, ...]
    result_schema_version: str
    status: str = "ready"
    description: str = ""


DEFAULT_CALCULATION_MODELS: dict[str, CalculationModel] = {
    "cost_model_v1": CalculationModel(
        model_id="cost_model_v1",
        enabled=True,
        compatible_metric_provider_ids=("cost",),
        compatible_intent_group_ids=("cost",),
        result_schema_version="cost-result.v1",
        description="Current monthly cost calculation model.",
    ),
    # TODO(future-optimization-entrypoint): Add new calculation models here only
    # with compatible metric provider ids, intent groups, result schema version,
    # formula/trace tests, and an enabled profile that binds the model.
    "latency_model_v1": CalculationModel(
        model_id="latency_model_v1",
        enabled=False,
        compatible_metric_provider_ids=("latency",),
        compatible_intent_group_ids=("latency",),
        result_schema_version="latency-result.v1",
        status="tbd",
        description="Future latency model declaration; no implementation in this thesis slice.",
    ),
}
