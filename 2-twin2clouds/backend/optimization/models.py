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


COST_CALCULATION_MODEL = CalculationModel(
    model_id="cost_model_v1",
    enabled=True,
    compatible_metric_provider_ids=("cost",),
    compatible_intent_group_ids=("cost",),
    result_schema_version="cost-result.v1",
    description="Current monthly cost calculation model.",
)
