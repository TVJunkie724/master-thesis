import json
from dataclasses import replace
from decimal import Decimal

import pytest
from backend.optimization.context import OptimizationMetricContext
from backend.optimization.cost_runtime import (
    CostOptimizationConfigError,
    CostOptimizationDefinition,
    CostOptimizationRuntime,
    build_default_cost_runtime,
)
from backend.optimization.metrics import CostMetricProvider, MetricResult
from backend.optimization.models import COST_CALCULATION_MODEL
from backend.optimization.scoring import (
    CostOnlyScoringStrategy,
    OptimizationCandidate,
)


class FakePricingRegistryService:
    def __init__(self):
        self.intent_group_calls = 0
        self.version_calls = 0

    def list_intent_groups(self):
        self.intent_group_calls += 1
        return {"cost": {"metric": "cost", "enabled": True}}

    def get_registry_version(self):
        self.version_calls += 1
        return "test-registry.v1"

    def get_optimization_bundle(self, bundle_id):
        if bundle_id != "cost_minimization_v1":
            raise KeyError(bundle_id)
        return {
            "id": "cost_minimization_v1",
            "enabled": True,
            "status": "ready",
            "profile_id": "cost_minimization_v1",
            "metric_provider_id": "cost",
            "calculation_strategy_id": "cost_calculation_v2",
            "formula_set_id": "cost_formula_set_v1",
            "workload_contract_id": "digital_twin_workload_v1",
            "pricing_contract_group": "cost_provider_pricing_contracts_v1",
            "provider_pricing_contract_ids": [
                "aws.iot_message_ingest.pricing_contract.v1"
            ],
            "scoring_strategy_id": "min_total_cost_v1",
            "result_schema_version": "cost-result.v1",
        }

    def get_calculation_strategy(self, strategy_id):
        if strategy_id != "cost_calculation_v2":
            raise KeyError(strategy_id)
        return {
            "id": "cost_calculation_v2",
            "enabled": True,
            "calculation_model_id": "cost_model_v1",
            "formula_set_id": "cost_formula_set_v1",
            "workload_contract_id": "digital_twin_workload_v1",
        }


def test_default_runtime_has_one_fixed_cost_collaborator_per_boundary():
    runtime = build_default_cost_runtime(FakePricingRegistryService())

    assert runtime.definition.optimization_id == "cost_minimization_v1"
    assert runtime.metric_provider.metric_id == "cost"
    assert runtime.calculation_model.model_id == "cost_model_v1"
    assert runtime.scoring_strategy.strategy_id == "min_total_cost_v1"
    assert not hasattr(runtime, "select_profile")
    assert not hasattr(runtime, "list_profiles")


def test_cost_runtime_rejects_a_non_cost_metric_provider():
    with pytest.raises(CostOptimizationConfigError, match="metric provider id"):
        CostOptimizationRuntime(
            pricing_registry_service=FakePricingRegistryService(),
            metric_provider=CostMetricProvider(metric_id="latency"),
        )


def test_cost_runtime_rejects_an_incompatible_calculation_model():
    model = replace(
        COST_CALCULATION_MODEL,
        compatible_metric_provider_ids=("latency",),
    )

    with pytest.raises(
        CostOptimizationConfigError, match="incompatible with the cost metric"
    ):
        CostOptimizationRuntime(
            pricing_registry_service=FakePricingRegistryService(),
            calculation_model=model,
        )


def test_cost_runtime_rejects_a_non_cost_scoring_boundary():
    strategy = CostOnlyScoringStrategy(primary_metric_id="latency")

    with pytest.raises(
        CostOptimizationConfigError, match="primary metric must be cost"
    ):
        CostOptimizationRuntime(
            pricing_registry_service=FakePricingRegistryService(),
            scoring_strategy=strategy,
        )


def test_cost_runtime_rejects_an_unknown_intent_group():
    definition = replace(
        CostOptimizationDefinition(),
        intent_group_id="latency",
    )

    with pytest.raises(
        CostOptimizationConfigError, match="missing intent group latency"
    ):
        CostOptimizationRuntime(
            pricing_registry_service=FakePricingRegistryService(),
            definition=definition,
        )


def test_cost_runtime_metadata_contains_no_future_objectives():
    runtime = build_default_cost_runtime(FakePricingRegistryService())

    metadata = runtime.build_result_metadata()

    assert metadata["profile_id"] == "cost_minimization_v1"
    assert metadata["metric_provider_ids"] == ["cost"]
    assert metadata["calculation_model_ids"] == ["cost_model_v1"]
    assert metadata["optimization_bundle_id"] == "cost_minimization_v1"
    assert metadata["optimization_bundle"] == {
        "id": "cost_minimization_v1",
        "calculation_strategy_id": "cost_calculation_v2",
        "formula_set_id": "cost_formula_set_v1",
        "workload_contract_id": "digital_twin_workload_v1",
        "pricing_contract_group": "cost_provider_pricing_contracts_v1",
        "provider_pricing_contract_count": 1,
        "status": "ready",
        "enabled": True,
    }
    assert "latency" not in metadata["metric_provider_ids"]
    assert "weighted_sum_v1" != metadata["scoring_strategy_id"]


def test_cost_metric_result_contains_evidence_metadata():
    result = CostMetricProvider().compute(
        OptimizationMetricContext(
            candidate_id="AWS",
            metric_inputs={"cost": 12.34},
            evidence_references=(
                "pricing_registry:test",
                "aws.iot.message_ingest",
            ),
            metadata={"layer": "L1", "provider": "AWS"},
        )
    )

    assert result.metric_id == "cost"
    assert result.evidence_level == "api_backed"
    assert result.evidence_references == (
        "pricing_registry:test",
        "aws.iot.message_ingest",
    )
    assert result.metadata == {"layer": "L1", "provider": "AWS"}


def test_cost_only_strategy_ranks_without_provider_pricing_payload():
    strategy = CostOnlyScoringStrategy()
    expensive = OptimizationCandidate(
        candidate_id="Azure",
        dimensions={"layer": "L1", "provider": "Azure"},
        metrics={"cost": MetricResult("cost", 20.0, "USD/month", "api_backed")},
    )
    cheap = OptimizationCandidate(
        candidate_id="AWS",
        dimensions={"layer": "L1", "provider": "AWS"},
        metrics={"cost": MetricResult("cost", 10.0, "USD/month", "api_backed")},
    )

    selected = strategy.select_best([expensive, cheap])

    assert selected.candidate_id == "AWS"
    assert "pricing" not in selected.to_dict()
    assert "pricePerGB" not in json.dumps(selected.to_dict())


def test_cost_only_strategy_uses_candidate_id_as_deterministic_tie_break():
    strategy = CostOnlyScoringStrategy()
    tied = [
        OptimizationCandidate(
            candidate_id=candidate_id,
            metrics={
                "cost": MetricResult(
                    "cost",
                    10.0,
                    "USD/month",
                    "api_backed",
                )
            },
        )
        for candidate_id in ("gcp|aws", "azure|aws", "aws|aws")
    ]

    assert [candidate.candidate_id for candidate in strategy.rank(tied)] == [
        "aws|aws",
        "azure|aws",
        "gcp|aws",
    ]


def test_cost_only_strategy_prefers_architecture_assignment_tie_break():
    metric = MetricResult("cost", 10.0, "USD/month", "api_backed")
    legacy_first = OptimizationCandidate(
        candidate_id="aws|aws",
        metrics={"cost": metric},
        canonical_tie_break_key=("component.ingestion", "azure", "deployment.z"),
    )
    architecture_first = OptimizationCandidate(
        candidate_id="azure|azure",
        metrics={"cost": metric},
        canonical_tie_break_key=("component.ingestion", "aws", "deployment.a"),
    )

    assert (
        CostOnlyScoringStrategy().select_best([legacy_first, architecture_first])
        is architecture_first
    )


def test_cost_only_strategy_ranks_by_exact_decimal_before_tie_break():
    metric = MetricResult("cost", 1.0, "USD/month", "api_backed")
    lexicographically_first_but_more_expensive = OptimizationCandidate(
        candidate_id="a",
        metrics={"cost": metric},
        exact_metric_values={"cost": Decimal("1.0000000000000000002")},
    )
    lexicographically_last_but_cheaper = OptimizationCandidate(
        candidate_id="z",
        metrics={"cost": metric},
        exact_metric_values={"cost": Decimal("1.0000000000000000001")},
    )

    assert (
        CostOnlyScoringStrategy().select_best(
            [
                lexicographically_first_but_more_expensive,
                lexicographically_last_but_cheaper,
            ]
        )
        is lexicographically_last_but_cheaper
    )


def test_result_metadata_is_serializable_and_uses_pricing_service():
    service = FakePricingRegistryService()
    runtime = build_default_cost_runtime(service)

    metadata = runtime.build_result_metadata()

    assert service.intent_group_calls == 1
    assert service.version_calls == 1
    assert metadata["result_schema_version"] == "cost-result.v1"
    assert metadata["intent_group_ids"] == ["cost"]
    assert (
        metadata["optimization_bundle"]["calculation_strategy_id"]
        == "cost_calculation_v2"
    )
    json.dumps(metadata)
