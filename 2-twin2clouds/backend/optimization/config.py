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
}

# Future objectives can implement the same metric/model/scoring boundaries, but
# inactive declarations are intentionally absent from the thesis runtime.
