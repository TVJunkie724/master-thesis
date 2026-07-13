import json
from dataclasses import replace

import pytest

from backend.optimization.config import DEFAULT_OPTIMIZATION_PROFILES
from backend.optimization.context import OptimizationMetricContext
from backend.optimization.metrics import (
    DEFAULT_METRIC_DECLARATIONS,
    CostMetricProvider,
    MetricProviderDeclaration,
)
from backend.optimization.models import DEFAULT_CALCULATION_MODELS
from backend.optimization.profiles import (
    OptimizationConfigError,
    OptimizationProfileRegistry,
    build_default_profile_registry,
)
from backend.optimization.scoring import (
    DEFAULT_SCORING_STRATEGY_DECLARATIONS,
    CostOnlyScoringStrategy,
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
            "provider_pricing_contract_ids": ["aws.iot_message_ingest.pricing_contract.v1"],
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


def _profiles_with(**overrides):
    profiles = {
        profile_id: dict(profile)
        for profile_id, profile in DEFAULT_OPTIMIZATION_PROFILES.items()
    }
    profiles["cost_minimization_v1"].update(overrides)
    return profiles


def test_default_registry_enables_only_cost_profile_and_metric():
    registry = build_default_profile_registry(FakePricingRegistryService())

    enabled_profiles = [
        profile.profile_id
        for profile in registry.list_profiles().values()
        if profile.enabled
    ]
    enabled_metrics = [
        metric_id
        for metric_id, declaration in registry.metric_declarations.items()
        if declaration.enabled
    ]

    assert enabled_profiles == ["cost_minimization_v1"]
    assert enabled_metrics == ["cost"]
    assert "latency" not in registry.metric_providers
    assert "sustainability" not in registry.metric_providers


def test_disabled_profile_cannot_be_selected_for_execution():
    registry = build_default_profile_registry(FakePricingRegistryService())

    with pytest.raises(OptimizationConfigError) as exc:
        registry.select_profile("latency_minimization_v1")

    assert "disabled" in str(exc.value)


def test_unknown_active_profile_fails_validation():
    with pytest.raises(OptimizationConfigError) as exc:
        OptimizationProfileRegistry(
            pricing_registry_service=FakePricingRegistryService(),
            active_profile_id="does_not_exist",
        )

    assert "Unknown active optimization profile" in str(exc.value)


def test_unknown_enabled_metric_fails_validation():
    declarations = dict(DEFAULT_METRIC_DECLARATIONS)
    declarations["risk"] = MetricProviderDeclaration(
        metric_id="risk",
        enabled=True,
        evidence_level="model_assumption",
        required_inputs=("risk_score",),
    )

    with pytest.raises(OptimizationConfigError) as exc:
        OptimizationProfileRegistry(
            pricing_registry_service=FakePricingRegistryService(),
            metric_declarations=declarations,
        )

    assert "Enabled metric has no executable provider: risk" in str(exc.value)


def test_unknown_enabled_scoring_strategy_fails_validation():
    profiles = _profiles_with(scoring_strategy_id="does_not_exist")

    with pytest.raises(OptimizationConfigError) as exc:
        OptimizationProfileRegistry(
            pricing_registry_service=FakePricingRegistryService(),
            profiles=profiles,
        )

    assert "unknown scoring strategy does_not_exist" in str(exc.value)


def test_unknown_enabled_calculation_model_fails_validation():
    profiles = _profiles_with(calculation_model_ids=["does_not_exist"])

    with pytest.raises(OptimizationConfigError) as exc:
        OptimizationProfileRegistry(
            pricing_registry_service=FakePricingRegistryService(),
            profiles=profiles,
        )

    assert "unknown calculation model does_not_exist" in str(exc.value)


def test_incompatible_profile_bundle_fails_validation():
    models = dict(DEFAULT_CALCULATION_MODELS)
    models["cost_model_v1"] = replace(
        models["cost_model_v1"],
        compatible_metric_provider_ids=("latency",),
    )

    with pytest.raises(OptimizationConfigError) as exc:
        OptimizationProfileRegistry(
            pricing_registry_service=FakePricingRegistryService(),
            calculation_models=models,
        )

    assert "incompatible with metrics ['cost']" in str(exc.value)


def test_unknown_enabled_intent_group_fails_validation():
    profiles = _profiles_with(intent_group_ids=["cost", "latency"])

    with pytest.raises(OptimizationConfigError) as exc:
        OptimizationProfileRegistry(
            pricing_registry_service=FakePricingRegistryService(),
            profiles=profiles,
        )

    assert "unknown registry intent group latency" in str(exc.value)


def test_disabled_metric_declarations_do_not_produce_result_objects():
    registry = build_default_profile_registry(FakePricingRegistryService())

    assert registry.metric_declarations["latency"].enabled is False
    with pytest.raises(OptimizationConfigError):
        registry.get_metric_provider("latency")


def test_disabled_tbd_profiles_do_not_affect_active_profile_metadata():
    registry = build_default_profile_registry(FakePricingRegistryService())

    metadata = registry.build_result_metadata()

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
    provider = CostMetricProvider()

    result = provider.compute(
        OptimizationMetricContext(
            candidate_id="AWS",
            metric_inputs={"cost": 12.34},
            evidence_references=("pricing_registry:test", "aws.iot.message_ingest"),
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


def test_cost_only_strategy_ranks_by_metric_result_without_pricing_payload():
    from backend.optimization.metrics import MetricResult
    from backend.optimization.scoring import OptimizationCandidate

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


def test_result_metadata_is_management_api_serializable_and_uses_pricing_service():
    service = FakePricingRegistryService()
    registry = build_default_profile_registry(service)

    metadata = registry.build_result_metadata()

    assert service.intent_group_calls == 1
    assert service.version_calls == 1
    assert metadata["profile_id"] == "cost_minimization_v1"
    assert metadata["result_schema_version"] == "cost-result.v1"
    assert metadata["metric_provider_ids"] == ["cost"]
    assert metadata["calculation_model_ids"] == ["cost_model_v1"]
    assert metadata["scoring_strategy_id"] == "min_total_cost_v1"
    assert metadata["intent_group_ids"] == ["cost"]
    assert metadata["optimization_bundle"]["calculation_strategy_id"] == "cost_calculation_v2"
    json.dumps(metadata)


def test_enabled_strategy_without_implementation_fails_validation():
    declarations = dict(DEFAULT_SCORING_STRATEGY_DECLARATIONS)

    with pytest.raises(OptimizationConfigError) as exc:
        OptimizationProfileRegistry(
            pricing_registry_service=FakePricingRegistryService(),
            scoring_strategy_declarations=declarations,
            scoring_strategies={},
        )

    assert "Enabled scoring strategy has no implementation: min_total_cost_v1" in str(exc.value)
