"""Default optimization profile configuration."""
from __future__ import annotations


OPTIMIZATION_CONFIG_VERSION = "optimization-config.v1"
DEFAULT_ACTIVE_PROFILE_ID = "cost_minimization_v1"
OPTIMIZATION_PROFILE_VERSION = "2026.06.08"


DEFAULT_OPTIMIZATION_PROFILES: dict[str, dict] = {
    "cost_minimization_v1": {
        "enabled": True,
        "status": "ready",
        "metric_provider_ids": ["cost"],
        "calculation_model_ids": ["cost_model_v1"],
        "scoring_strategy_id": "min_total_cost_v1",
        "optimization_bundle_id": "cost_minimization_v1",
        "intent_group_ids": ["cost"],
        "evidence_requirements": {"pricing": "evidence_backed"},
        "result_schema_version": "cost-result.v1",
        "description": "Cost-only thesis optimization profile.",
    },
    # TODO(future-optimization-entrypoint): Add new executable optimizer types here
    # only after their MetricProvider, CalculationModel, ScoringStrategy, intent
    # group, result schema, trace schema, and regression tests exist. Profiles
    # are the compatibility bundle; do not let callers mix strategies ad hoc.
    "latency_minimization_v1": {
        "enabled": False,
        "status": "tbd",
        "metric_provider_ids": ["latency"],
        "calculation_model_ids": ["latency_model_v1"],
        "scoring_strategy_id": "min_latency_v1",
        "optimization_bundle_id": "",
        "intent_group_ids": ["latency"],
        "evidence_requirements": {"latency": "tbd"},
        "result_schema_version": "latency-result.v1",
        "description": "Future latency profile declaration; not executable.",
    },
    "cost_latency_weighted_v1": {
        "enabled": False,
        "status": "tbd",
        "metric_provider_ids": ["cost", "latency"],
        "calculation_model_ids": ["cost_model_v1", "latency_model_v1"],
        "scoring_strategy_id": "weighted_sum_v1",
        "optimization_bundle_id": "",
        "intent_group_ids": ["cost", "latency"],
        "evidence_requirements": {"pricing": "evidence_backed", "latency": "tbd"},
        "result_schema_version": "weighted-result.v1",
        "description": "Future weighted multi-objective profile declaration.",
    },
}
