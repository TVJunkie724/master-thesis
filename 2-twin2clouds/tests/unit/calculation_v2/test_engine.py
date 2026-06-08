"""
Test Engine Integration
========================

Integration tests for the new calculation engine.
"""

import json
import pytest
from unittest.mock import patch, MagicMock
from types import SimpleNamespace


class TestEngineIntegration:
    """Test the new engine with mock pricing data."""
    
    @pytest.fixture
    def sample_params(self):
        """Standard test parameters."""
        return {
            "numberOfDevices": 100,
            "deviceSendingIntervalInMinutes": 2.0,
            "averageSizeOfMessageInKb": 0.25,
            "hotStorageDurationInMonths": 1,
            "coolStorageDurationInMonths": 3,
            "archiveStorageDurationInMonths": 12,
            "needs3DModel": False,
            "entityCount": 1,
            "amountOfActiveEditors": 2,
            "amountOfActiveViewers": 5,
            "dashboardRefreshesPerHour": 4,
            "dashboardActiveHoursPerDay": 8,
            "currency": "USD",
            "useEventChecking": True,
            "triggerNotificationWorkflow": True,
            "integrateErrorHandling": False,
            "orchestrationActionsPerMessage": 3,
            "eventsPerMessage": 1,
            "apiCallsPerDashboardRefresh": 1,
            "allowGcpSelfHostedL4": True,
            "allowGcpSelfHostedL5": True,
        }
    
    @pytest.fixture
    def sample_pricing(self):
        """Minimal pricing data for testing."""
        return {
            "aws": {
                "iotCore": {
                    "pricePerDeviceAndMonth": 0.25,
                    "priceRulesTriggered": 0.000001,
                },
                "lambda": {
                    "requestPrice": 0.0000002,
                    "durationPrice": 0.0000166667,
                    "freeRequests": 1000000,
                    "freeComputeTime": 400000,
                },
                "stepFunctions": {"pricePerStateTransition": 0.000025},
                "eventBridge": {"pricePerMillionEvents": 1.0},
                "dynamoDB": {
                    "writePrice": 0.0000125,
                    "readPrice": 0.00000025,
                    "storagePrice": 0.25,
                    "freeStorage": 25,
                },
                "s3InfrequentAccess": {"storagePrice": 0.0125},
                "s3GlacierDeepArchive": {"storagePrice": 0.00099},
                "iotTwinMaker": {"queryPrice": 0.001},
                "awsManagedGrafana": {"editorPrice": 9.0, "viewerPrice": 5.0},
                "egress": {"pricePerGB": 0.09},
            },
            "azure": {
                "iotHub": {
                    "pricePerUnit": 25.0,
                    "messagesPerUnit": 400000,
                    "additionalMessagePrice": 0.000004,
                },
                "functions": {
                    "requestPrice": 0.0000002,
                    "durationPrice": 0.000016,
                    "freeRequests": 1000000,
                    "freeComputeTime": 400000,
                },
                "logicApps": {"pricePerAction": 0.000025},
                "eventGrid": {"pricePerMillionOperations": 0.60},
                "cosmosDB": {
                    "requestUnitPrice": 0.25,
                    "storagePrice": 0.25,
                },
                "blobStorageCool": {"storagePrice": 0.01},
                "blobStorageArchive": {"storagePrice": 0.002},
                "azureDigitalTwins": {
                    "operationPrice": 0.0025,
                    "queryPrice": 0.0005,
                    "messagePrice": 0.001,
                },
                "azureManagedGrafana": {"editorPrice": 9.0, "viewerPrice": 5.0},
                "egress": {"pricePerGB": 0.087},
            },
            "gcp": {
                "iot": {"pricePerGiB": 0.04},
                "functions": {
                    "invocationPrice": 0.0000004,
                    "gbSecondPrice": 0.0000025,
                    "freeInvocations": 2000000,
                    "freeGBSeconds": 400000,
                },
                "cloudWorkflows": {"pricePerStep": 0.00001},
                "storage_hot": {
                    "writePrice": 0.18,
                    "readPrice": 0.06,
                    "storagePrice": 0.026,
                },
                "storage_cool": {"storagePrice": 0.01, "writePrice": 0.01},
                "storage_archive": {"storagePrice": 0.004, "writePrice": 0.05},
                "twinmaker": {"e2MediumPrice": 0.0335, "storagePrice": 0.04},
                "grafana": {"e2MediumPrice": 0.0335, "storagePrice": 0.04},
                "egress": {"pricePerGB": 0.12},
            },
        }
    
    def test_calculate_aws_costs(self, sample_params, sample_pricing):
        """Test AWS cost calculation returns expected structure."""
        from backend.calculation_v2.engine import calculate_aws_costs
        
        result = calculate_aws_costs(sample_params, sample_pricing)
        
        # Verify structure
        assert "L1" in result
        assert "L2" in result
        assert "L3_hot" in result
        assert "L3_cool" in result
        assert "L3_archive" in result
        assert "L4" in result
        assert "L5" in result
        
        # Verify costs are numeric
        for layer in ["L1", "L2", "L3_hot", "L3_cool", "L3_archive", "L4", "L5"]:
            assert isinstance(result[layer]["cost"], (int, float))
            assert result[layer]["cost"] >= 0
    
    def test_calculate_cheapest_costs(self, sample_params, sample_pricing):
        """Test full calculation returns expected structure."""
        from backend.calculation_v2.engine import calculate_cheapest_costs
        
        result = calculate_cheapest_costs(sample_params, sample_pricing)
        
        # Verify structure
        assert "calculationResult" in result
        assert "awsCosts" in result
        assert "azureCosts" in result
        assert "gcpCosts" in result
        assert "cheapestPath" in result
        assert "totalCost" in result
        assert result["optimization_profile_id"] == "cost_minimization_v1"
        assert result["result_schema_version"] == "cost-result.v1"
        assert result["optimizationProfile"]["metric_provider_ids"] == ["cost"]
        assert result["optimizationProfile"]["scoring_strategy_id"] == "min_total_cost_v1"
        
        # Verify calculationResult has all layers
        calc_result = result["calculationResult"]
        assert "L1" in calc_result
        assert "L2" in calc_result
        assert "L3" in calc_result
        assert "L4" in calc_result
        assert "L5" in calc_result
        
        # Verify provider choices are valid
        valid_providers = ["AWS", "Azure", "GCP"]
        assert calc_result["L1"] in valid_providers
        assert calc_result["L2"] in valid_providers
        assert calc_result["L4"] in valid_providers
        assert calc_result["L5"] in valid_providers
        
        # L3 should have Hot, Cool, Archive
        assert "Hot" in calc_result["L3"]
        assert "Cool" in calc_result["L3"]
        assert "Archive" in calc_result["L3"]

    def test_disabled_optimization_profile_is_rejected(self, sample_params, sample_pricing):
        """Only enabled profiles may execute."""
        from backend.calculation_v2.engine import calculate_cheapest_costs
        from backend.optimization.profiles import OptimizationConfigError

        with pytest.raises(OptimizationConfigError):
            calculate_cheapest_costs(
                sample_params,
                sample_pricing,
                optimization_profile_id="latency_minimization_v1",
            )

    def test_cost_profile_preserves_min_cost_provider_selection(self, sample_params, sample_pricing):
        """Selected providers must match the minimum cost for each executable layer."""
        from backend.calculation_v2.engine import calculate_cheapest_costs

        result = calculate_cheapest_costs(sample_params, sample_pricing)

        layer_to_result_key = {
            "L1": result["calculationResult"]["L1"],
            "L2": result["calculationResult"]["L2"],
            "L3_hot": result["calculationResult"]["L3"]["Hot"],
            "L3_cool": result["calculationResult"]["L3"]["Cool"],
            "L3_archive": result["calculationResult"]["L3"]["Archive"],
            "L4": result["calculationResult"]["L4"],
            "L5": result["calculationResult"]["L5"],
        }
        provider_cost_key = {
            "AWS": "awsCosts",
            "Azure": "azureCosts",
            "GCP": "gcpCosts",
        }

        for layer, selected_provider in layer_to_result_key.items():
            options = {
                provider: result[cost_key][layer]["cost"]
                for provider, cost_key in provider_cost_key.items()
            }
            assert selected_provider == min(options, key=options.get)

    def test_scoring_strategy_does_not_receive_provider_pricing_payload(
        self,
        sample_params,
        sample_pricing,
        monkeypatch,
    ):
        """Provider-specific raw pricing fields stay outside the scoring boundary."""
        from backend.calculation_v2 import engine
        from backend.optimization.metrics import CostMetricProvider

        class InspectingStrategy:
            def __init__(self):
                self.seen_payloads = []

            def select_best(self, candidates):
                for candidate in candidates:
                    payload = json.dumps(candidate.to_dict())
                    assert "pricePerDeviceAndMonth" not in payload
                    assert "pricePerGB" not in payload
                    assert "durationPrice" not in payload
                    assert "storagePrice" not in payload
                    assert set(candidate.metrics) == {"cost"}
                    self.seen_payloads.append(payload)
                return min(candidates, key=lambda candidate: candidate.metric_value("cost"))

        strategy = InspectingStrategy()

        class FakeProfileRegistry:
            def select_profile(self, profile_id=None):
                return SimpleNamespace(
                    profile_id="cost_minimization_v1",
                    scoring_strategy_id="min_total_cost_v1",
                    result_schema_version="cost-result.v1",
                )

            def get_metric_provider(self, metric_id):
                assert metric_id == "cost"
                return CostMetricProvider()

            def get_scoring_strategy(self, strategy_id):
                assert strategy_id == "min_total_cost_v1"
                return strategy

            def build_result_metadata(self, profile_id):
                assert profile_id == "cost_minimization_v1"
                return {
                    "config_version": "optimization-config.v1",
                    "pricing_registry_version": "test-registry.v1",
                    "profile_id": "cost_minimization_v1",
                    "profile_version": "2026.06.08",
                    "enabled": True,
                    "status": "ready",
                    "metric_provider_ids": ["cost"],
                    "calculation_model_ids": ["cost_model_v1"],
                    "scoring_strategy_id": "min_total_cost_v1",
                    "intent_group_ids": ["cost"],
                    "evidence_requirements": {"pricing": "evidence_backed"},
                    "result_schema_version": "cost-result.v1",
                    "description": "test",
                }

        monkeypatch.setattr(
            engine,
            "build_default_profile_registry",
            lambda: FakeProfileRegistry(),
        )

        result = engine.calculate_cheapest_costs(sample_params, sample_pricing)

        assert result["optimization_profile_id"] == "cost_minimization_v1"
        assert len(strategy.seen_payloads) >= 7
    
    def test_total_cost_is_positive(self, sample_params, sample_pricing):
        """Total cost should be positive for non-zero usage."""
        from backend.calculation_v2.engine import calculate_cheapest_costs
        
        result = calculate_cheapest_costs(sample_params, sample_pricing)
        assert result["totalCost"] > 0
