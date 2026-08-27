"""Fixed cost-optimization runtime for the thesis PoC.

The runtime keeps explicit metric, calculation-model, and scoring boundaries so
the implementation pattern remains testable. It deliberately exposes no profile
registry or runtime selection: monetary cost is the only executable objective.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from backend.optimization.config import (
    COST_CALCULATION_MODEL_ID,
    COST_INTENT_GROUP_ID,
    COST_METRIC_ID,
    COST_OPTIMIZATION_BUNDLE_ID,
    COST_OPTIMIZATION_ID,
    COST_OPTIMIZATION_VERSION,
    COST_RESULT_SCHEMA_VERSION,
    COST_SCORING_STRATEGY_ID,
    OPTIMIZATION_CONFIG_VERSION,
)
from backend.optimization.metrics import (
    ALLOWED_EVIDENCE_LEVELS,
    CostMetricProvider,
    MetricProvider,
)
from backend.optimization.models import COST_CALCULATION_MODEL, CalculationModel
from backend.optimization.scoring import CostOnlyScoringStrategy, ScoringStrategy
from backend.pricing_registry_service import PricingRegistryService


class CostOptimizationConfigError(ValueError):
    """Raised when the fixed cost runtime is inconsistent with its evidence."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("Invalid cost optimization runtime: " + "; ".join(errors))


@dataclass(frozen=True)
class CostOptimizationDefinition:
    """Stable trace definition for the only executable optimization objective."""

    optimization_id: str = COST_OPTIMIZATION_ID
    version: str = COST_OPTIMIZATION_VERSION
    metric_provider_id: str = COST_METRIC_ID
    calculation_model_id: str = COST_CALCULATION_MODEL_ID
    scoring_strategy_id: str = COST_SCORING_STRATEGY_ID
    optimization_bundle_id: str = COST_OPTIMIZATION_BUNDLE_ID
    intent_group_id: str = COST_INTENT_GROUP_ID
    result_schema_version: str = COST_RESULT_SCHEMA_VERSION
    evidence_requirements: dict[str, str] = field(
        default_factory=lambda: {"pricing": "evidence_backed"}
    )
    description: str = "Cost-only thesis optimization runtime."

    def to_metadata(self) -> dict[str, Any]:
        """Serialize using the established result keys used by stored runs."""

        return {
            "profile_id": self.optimization_id,
            "profile_version": self.version,
            "enabled": True,
            "status": "ready",
            "metric_provider_ids": [self.metric_provider_id],
            "calculation_model_ids": [self.calculation_model_id],
            "scoring_strategy_id": self.scoring_strategy_id,
            "optimization_bundle_id": self.optimization_bundle_id,
            "intent_group_ids": [self.intent_group_id],
            "evidence_requirements": dict(self.evidence_requirements),
            "result_schema_version": self.result_schema_version,
            "description": self.description,
        }


class CostOptimizationRuntime:
    """Validated collaborators and evidence for cost-only optimization."""

    def __init__(
        self,
        *,
        pricing_registry_service: PricingRegistryService | None = None,
        definition: CostOptimizationDefinition | None = None,
        metric_provider: MetricProvider | None = None,
        calculation_model: CalculationModel | None = None,
        scoring_strategy: ScoringStrategy | None = None,
    ) -> None:
        self.pricing_registry_service = (
            pricing_registry_service or PricingRegistryService()
        )
        self.definition = definition or CostOptimizationDefinition()
        self.metric_provider = metric_provider or CostMetricProvider()
        self.calculation_model = calculation_model or COST_CALCULATION_MODEL
        self.scoring_strategy = scoring_strategy or CostOnlyScoringStrategy()
        self.validate()

    def validate(self) -> None:
        errors: list[str] = []
        definition = self.definition

        try:
            intent_groups = self.pricing_registry_service.list_intent_groups()
        except Exception as exc:  # pragma: no cover - defensive error shaping
            errors.append(f"Unable to load pricing registry intent groups: {exc}")
            intent_groups = {}

        metric = self.metric_provider
        if metric.metric_id != definition.metric_provider_id:
            errors.append(
                "Cost metric provider id does not match the runtime definition"
            )
        if not metric.enabled:
            errors.append("Cost metric provider is disabled")
        if metric.evidence_level not in ALLOWED_EVIDENCE_LEVELS:
            errors.append(
                f"Cost metric provider has unsupported evidence level "
                f"{metric.evidence_level!r}"
            )
        if COST_METRIC_ID not in metric.required_inputs:
            errors.append("Cost metric provider must require the cost input")

        model = self.calculation_model
        if model.model_id != definition.calculation_model_id:
            errors.append(
                "Cost calculation model id does not match the runtime definition"
            )
        if not model.enabled:
            errors.append("Cost calculation model is disabled")
        if definition.metric_provider_id not in model.compatible_metric_provider_ids:
            errors.append("Cost calculation model is incompatible with the cost metric")
        if definition.intent_group_id not in model.compatible_intent_group_ids:
            errors.append(
                "Cost calculation model is incompatible with the cost intent group"
            )
        if model.result_schema_version != definition.result_schema_version:
            errors.append(
                "Cost calculation model result schema does not match the runtime"
            )

        strategy = self.scoring_strategy
        if strategy.strategy_id != definition.scoring_strategy_id:
            errors.append(
                "Cost scoring strategy id does not match the runtime definition"
            )
        if not strategy.enabled:
            errors.append("Cost scoring strategy is disabled")
        if definition.metric_provider_id not in strategy.compatible_metric_provider_ids:
            errors.append("Cost scoring strategy is incompatible with the cost metric")
        if strategy.primary_metric_id != definition.metric_provider_id:
            errors.append("Cost scoring strategy primary metric must be cost")

        if definition.intent_group_id not in intent_groups:
            errors.append(
                f"Pricing registry is missing intent group {definition.intent_group_id}"
            )

        self._validate_bundle(errors)
        if errors:
            raise CostOptimizationConfigError(sorted(errors))

    def build_result_metadata(self) -> dict[str, Any]:
        return {
            "config_version": OPTIMIZATION_CONFIG_VERSION,
            "pricing_registry_version": (
                self.pricing_registry_service.get_registry_version()
            ),
            "optimization_bundle": self._build_bundle_metadata(),
            **self.definition.to_metadata(),
        }

    def _validate_bundle(self, errors: list[str]) -> None:
        definition = self.definition
        try:
            bundle = self.pricing_registry_service.get_optimization_bundle(
                definition.optimization_bundle_id
            )
        except Exception as exc:
            errors.append(
                f"Invalid cost optimization bundle "
                f"{definition.optimization_bundle_id!r}: {exc}"
            )
            return

        expected = {
            "profile_id": definition.optimization_id,
            "metric_provider_id": definition.metric_provider_id,
            "scoring_strategy_id": definition.scoring_strategy_id,
            "result_schema_version": definition.result_schema_version,
        }
        for name, expected_value in expected.items():
            if bundle.get(name) != expected_value:
                errors.append(f"Cost optimization bundle has mismatched {name}")
        if bundle.get("enabled") is not True:
            errors.append("Cost optimization bundle is disabled")
        if bundle.get("status") != "ready":
            errors.append("Cost optimization bundle is not ready")

        strategy_id = bundle.get("calculation_strategy_id")
        try:
            strategy = self.pricing_registry_service.get_calculation_strategy(
                strategy_id
            )
        except Exception as exc:
            errors.append(
                f"Cost optimization bundle references invalid calculation strategy "
                f"{strategy_id!r}: {exc}"
            )
            return
        if strategy.get("calculation_model_id") != definition.calculation_model_id:
            errors.append(
                "Cost optimization bundle strategy has an incompatible calculation model"
            )
        if strategy.get("enabled") is not True:
            errors.append("Cost optimization bundle strategy is disabled")

    def _build_bundle_metadata(self) -> dict[str, Any]:
        bundle = self.pricing_registry_service.get_optimization_bundle(
            self.definition.optimization_bundle_id
        )
        return {
            "id": bundle["id"],
            "calculation_strategy_id": bundle["calculation_strategy_id"],
            "formula_set_id": bundle["formula_set_id"],
            "workload_contract_id": bundle["workload_contract_id"],
            "pricing_contract_group": bundle["pricing_contract_group"],
            "provider_pricing_contract_count": len(
                bundle.get("provider_pricing_contract_ids") or []
            ),
            "status": bundle["status"],
            "enabled": bundle["enabled"],
        }


def build_default_cost_runtime(
    pricing_registry_service: PricingRegistryService | None = None,
) -> CostOptimizationRuntime:
    return CostOptimizationRuntime(
        pricing_registry_service=pricing_registry_service,
    )
