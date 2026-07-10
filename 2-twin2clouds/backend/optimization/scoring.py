"""Scoring strategy contracts for optimization candidates."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from backend.optimization.metrics import MetricResult


@dataclass(frozen=True)
class OptimizationCandidate:
    candidate_id: str
    metrics: dict[str, MetricResult]
    dimensions: dict[str, str] = field(default_factory=dict)

    def metric_value(self, metric_id: str) -> float:
        try:
            return self.metrics[metric_id].value
        except KeyError as exc:
            raise ValueError(
                f"Candidate {self.candidate_id!r} has no metric {metric_id!r}"
            ) from exc

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "dimensions": dict(self.dimensions),
            "metrics": {
                metric_id: result.to_dict()
                for metric_id, result in self.metrics.items()
            },
        }


class ScoringStrategy(Protocol):
    strategy_id: str
    enabled: bool
    compatible_metric_provider_ids: tuple[str, ...]
    primary_metric_id: str

    def rank(self, candidates: list[OptimizationCandidate]) -> list[OptimizationCandidate]:
        ...

    def select_best(self, candidates: list[OptimizationCandidate]) -> OptimizationCandidate:
        ...


@dataclass(frozen=True)
class CostOnlyScoringStrategy:
    """Ranks candidates by the enabled cost metric only."""

    strategy_id: str = "min_total_cost_v1"
    enabled: bool = True
    compatible_metric_provider_ids: tuple[str, ...] = ("cost",)
    primary_metric_id: str = "cost"

    def rank(self, candidates: list[OptimizationCandidate]) -> list[OptimizationCandidate]:
        if not candidates:
            raise ValueError("At least one optimization candidate is required")
        return sorted(candidates, key=lambda candidate: candidate.metric_value(self.primary_metric_id))

    def select_best(self, candidates: list[OptimizationCandidate]) -> OptimizationCandidate:
        return self.rank(candidates)[0]


@dataclass(frozen=True)
class ScoringStrategyDeclaration:
    strategy_id: str
    enabled: bool
    compatible_metric_provider_ids: tuple[str, ...]
    status: str = "ready"
    description: str = ""


DEFAULT_SCORING_STRATEGY_DECLARATIONS: dict[str, ScoringStrategyDeclaration] = {
    "min_total_cost_v1": ScoringStrategyDeclaration(
        strategy_id="min_total_cost_v1",
        enabled=True,
        compatible_metric_provider_ids=("cost",),
        description="Selects the candidate with the lowest monthly cost.",
    ),
    "weighted_sum_v1": ScoringStrategyDeclaration(
        strategy_id="weighted_sum_v1",
        enabled=False,
        compatible_metric_provider_ids=("cost", "latency"),
        status="tbd",
        description="Future multi-objective weighted score. Declarative only.",
    ),
}


DEFAULT_SCORING_STRATEGIES: dict[str, ScoringStrategy] = {
    "min_total_cost_v1": CostOnlyScoringStrategy(),
}

# TODO(future-optimization-entrypoint): Add concrete ScoringStrategy instances
# here only when all compatible metric providers and calculation models are
# implemented. Multi-objective scoring must document weights and remain tied to
# an explicit OptimizationProfile.
