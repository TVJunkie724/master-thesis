"""Metric provider contracts for optimization."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from backend.optimization.context import OptimizationMetricContext


ALLOWED_EVIDENCE_LEVELS = {
    "api_backed",
    "official_documentation",
    "static_file",
    "benchmark_file",
    "model_assumption",
    "tbd",
}


@dataclass(frozen=True)
class MetricProviderDeclaration:
    metric_id: str
    enabled: bool
    evidence_level: str
    required_inputs: tuple[str, ...]
    status: str = "ready"
    description: str = ""


@dataclass(frozen=True)
class MetricResult:
    metric_id: str
    value: float
    unit: str
    evidence_level: str
    evidence_references: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.evidence_level not in ALLOWED_EVIDENCE_LEVELS:
            raise ValueError(f"Unsupported evidence level: {self.evidence_level}")
        if not isinstance(self.value, (int, float)):
            raise ValueError("Metric value must be numeric")

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric_id": self.metric_id,
            "value": self.value,
            "unit": self.unit,
            "evidence_level": self.evidence_level,
            "evidence_references": list(self.evidence_references),
            "metadata": dict(self.metadata),
        }


class MetricProvider(Protocol):
    metric_id: str
    enabled: bool
    evidence_level: str
    required_inputs: tuple[str, ...]

    def compute(self, context: OptimizationMetricContext) -> MetricResult:
        ...


@dataclass(frozen=True)
class CostMetricProvider:
    """Enabled cost metric provider used by the thesis optimizer."""

    metric_id: str = "cost"
    enabled: bool = True
    evidence_level: str = "api_backed"
    required_inputs: tuple[str, ...] = ("cost",)

    def compute(self, context: OptimizationMetricContext) -> MetricResult:
        missing = [key for key in self.required_inputs if key not in context.metric_inputs]
        if missing:
            raise ValueError(
                f"Missing metric inputs for {self.metric_id}: {', '.join(missing)}"
            )
        value = context.metric_inputs["cost"]
        if not isinstance(value, (int, float)):
            raise ValueError("Cost metric input must be numeric")
        return MetricResult(
            metric_id=self.metric_id,
            value=float(value),
            unit="USD/month",
            evidence_level=self.evidence_level,
            evidence_references=context.evidence_references,
            metadata=dict(context.metadata),
        )


DEFAULT_METRIC_DECLARATIONS: dict[str, MetricProviderDeclaration] = {
    "cost": MetricProviderDeclaration(
        metric_id="cost",
        enabled=True,
        evidence_level="api_backed",
        required_inputs=("cost",),
        description="Monthly cost derived from evidence-backed provider pricing.",
    ),
    "latency": MetricProviderDeclaration(
        metric_id="latency",
        enabled=False,
        evidence_level="tbd",
        required_inputs=("latency_ms",),
        status="tbd",
        description="Future latency objective. Declarative only in this thesis slice.",
    ),
    "sustainability": MetricProviderDeclaration(
        metric_id="sustainability",
        enabled=False,
        evidence_level="tbd",
        required_inputs=("carbon_score",),
        status="tbd",
        description="Future sustainability objective. Declarative only in this thesis slice.",
    ),
}


DEFAULT_METRIC_PROVIDERS: dict[str, MetricProvider] = {
    "cost": CostMetricProvider(),
}

# TODO(future-optimization-entrypoint): Register concrete non-cost
# MetricProvider implementations here after they can produce evidence-backed,
# numeric MetricResult values. Keep declarations disabled until the provider is
# implemented and profile validation proves it belongs to an enabled profile.
