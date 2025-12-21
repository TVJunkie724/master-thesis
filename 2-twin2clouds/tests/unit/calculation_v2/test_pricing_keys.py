"""
Test Pricing Key Fallbacks
===========================

Tests to ensure pricing calculators correctly read dynamic pricing keys
and don't fall back to zero when pricing data is available.

These tests verify the fixes for:
- Logic Apps: pricePerAction -> pricePerStateTransition
- Cosmos DB: requestUnitPrice -> requestPrice  
- S3 IA: writePrice -> requestPrice
- GCS Nearline: writePrice -> requestPrice
"""

import pytest


class TestPricingKeyFallbacks:
    """Test that pricing calculators correctly use dynamic pricing keys."""

    @pytest.fixture
    def dynamic_azure_pricing(self):
        """Azure pricing matching pricing_dynamic_azure.json format."""
        return {
            "azure": {
                "logicApps": {
                    "pricePer1kStateTransitions": 0.125,
                    "pricePerStateTransition": 0.000125,
                    # Note: NO pricePerAction key!
                },
                "cosmosDB": {
                    "requestPrice": 0.0584,  # NOT requestUnitPrice
                    "minimumRequestUnits": 400,
                    "RUsPerRead": 1,
                    "RUsPerWrite": 10,
                    "storagePrice": 0.02,
                },
                "functions": {
                    "requestPrice": 0.2,
                    "durationPrice": 1.6e-05,
                    "freeRequests": 1000000,
                    "freeComputeTime": 400000,
                },
                "eventGrid": {
                    "pricePerMillionEvents": 0.6,
                    # Note: NO pricePerMillionOperations key!
                },
            }
        }

    @pytest.fixture
    def dynamic_aws_pricing(self):
        """AWS pricing matching pricing_dynamic_aws.json format."""
        return {
            "aws": {
                "s3InfrequentAccess": {
                    "storagePrice": 0.0135,
                    "upfrontPrice": 0.0001,
                    "requestPrice": 1e-06,  # NOT writePrice
                    "dataRetrievalPrice": 0.012,
                    "transferCostFromDynamoDB": 0.099,
                    "transferCostFromCosmosDB": 0.0495,
                },
            }
        }

    @pytest.fixture
    def dynamic_gcp_pricing(self):
        """GCP pricing matching pricing_dynamic_gcp.json format."""
        return {
            "gcp": {
                "storage_cool": {
                    "storagePrice": 0.011,
                    "upfrontPrice": 0.0,
                    "requestPrice": 2.6e-05,  # NOT writePrice
                    "dataRetrievalPrice": 0.01,
                },
            }
        }

    def test_logic_apps_uses_pricePerStateTransition(self, dynamic_azure_pricing):
        """
        Logic Apps must use pricePerStateTransition when pricePerAction is missing.
        This was returning $0 before the fix.
        """
        from backend.calculation_v2.components.azure.logic_apps import AzureLogicAppsCalculator
        
        calc = AzureLogicAppsCalculator()
        cost = calc.calculate_cost(
            executions=1_000_000,  # 1M executions
            pricing=dynamic_azure_pricing,
            actions_per_execution=3
        )
        
        # Expected: 1M * 3 actions * $0.000125 = $375
        expected = 1_000_000 * 3 * 0.000125
        assert cost == pytest.approx(expected, rel=0.01)
        assert cost > 0, "Logic Apps cost should not be zero!"

    def test_cosmos_db_uses_requestPrice(self, dynamic_azure_pricing):
        """
        Cosmos DB must use requestPrice when requestUnitPrice is missing.
        This was returning $0 for RU cost before the fix.
        """
        from backend.calculation_v2.components.azure.cosmos_db import AzureCosmosDBCalculator
        
        calc = AzureCosmosDBCalculator()
        cost = calc.calculate_cost(
            writes_per_month=1_000_000,
            reads_per_month=5_000_000,
            storage_gb=10,
            pricing=dynamic_azure_pricing
        )
        
        # Cost should include RU cost + storage cost
        # RU cost should NOT be zero
        assert cost > 0, "Cosmos DB cost should not be zero!"
        # Storage alone would be 10 * 0.02 = $0.20
        # With RU cost, total should be significantly higher
        assert cost > 0.20, "Cosmos DB cost should include RU cost, not just storage!"

    def test_s3_ia_uses_requestPrice(self, dynamic_aws_pricing):
        """
        S3 Infrequent Access must use requestPrice when writePrice is missing.
        """
        from backend.calculation_v2.components.aws.s3 import AWSS3IACalculator
        
        calc = AWSS3IACalculator()
        cost = calc.calculate_cost(
            storage_gb=100,
            writes_per_month=1_000_000,  # 1M writes
            pricing=dynamic_aws_pricing,
            retrievals_gb=10
        )
        
        # Storage: 100 * 0.0135 = $1.35
        # Writes: 1M * 1e-06 = $1.00
        # Retrieval: 10 * 0.012 = $0.12
        # Total should be around $2.47
        assert cost > 1.35, "S3 IA cost should include write cost, not just storage!"
        
    def test_gcs_nearline_uses_requestPrice(self, dynamic_gcp_pricing):
        """
        GCS Nearline must use requestPrice when writePrice is missing.
        """
        from backend.calculation_v2.components.gcp.cloud_storage import GCSNearlineCalculator
        
        calc = GCSNearlineCalculator()
        cost = calc.calculate_cost(
            storage_gb=100,
            writes_per_month=1_000_000,  # 1M writes
            pricing=dynamic_gcp_pricing,
            retrievals_gb=10
        )
        
        # Storage: 100 * 0.011 = $1.10
        # Writes: 1M * 2.6e-05 = $26.00
        # Retrieval: 10 * 0.01 = $0.10
        # Total should be around $27.20
        assert cost > 1.10, "GCS Nearline cost should include write cost, not just storage!"
        assert cost > 20, "GCS Nearline write cost should be significant with 1M operations!"

    def test_event_grid_uses_pricePerMillionEvents(self, dynamic_azure_pricing):
        """
        Event Grid must use pricePerMillionEvents as fallback.
        This already had a fallback but verify it works.
        """
        from backend.calculation_v2.components.azure.event_grid import AzureEventGridCalculator
        
        calc = AzureEventGridCalculator()
        cost = calc.calculate_cost(
            events=10_000_000,  # 10M events
            pricing=dynamic_azure_pricing
        )
        
        # Expected: 10M * (0.6 / 1M) = $6.00
        expected = 10_000_000 * (0.6 / 1_000_000)
        assert cost == pytest.approx(expected, rel=0.01)
        assert cost > 0, "Event Grid cost should not be zero!"


class TestPricingKeysNotZero:
    """Ensure no calculator returns zero when valid pricing is provided."""

    @pytest.fixture
    def full_dynamic_pricing(self):
        """Combined pricing from all dynamic JSON files."""
        return {
            "aws": {
                "iotCore": {
                    "pricePerDeviceAndMonth": 1.5e-06,
                    "priceRulesTriggered": 1.8e-07,
                    "pricing_tiers": {
                        "tier1": {"limit": 1000000000, "price": 1e-06},
                        "tier2": {"limit": 5000000000, "price": 8e-07},
                        "tier3": {"limit": "Infinity", "price": 7e-07},
                    },
                },
                "lambda": {
                    "requestPrice": 2e-07,
                    "durationPrice": 1.66667e-05,
                    "freeRequests": 1000000,
                    "freeComputeTime": 400000,
                },
                "stepFunctions": {
                    "pricePer1kStateTransitions": 0.025,
                    "pricePerStateTransition": 2.5e-05,
                },
                "eventBridge": {"pricePerMillionEvents": 1.15e-06},
                "dynamoDB": {
                    "writePrice": 7.625e-07,
                    "readPrice": 1.525e-07,
                    "storagePrice": 0.306,
                    "freeStorage": 25,
                },
                "s3InfrequentAccess": {
                    "storagePrice": 0.0135,
                    "requestPrice": 1e-06,
                    "dataRetrievalPrice": 0.012,
                },
                "s3GlacierDeepArchive": {
                    "storagePrice": 0.0225,
                    "lifecycleAndWritePrice": 3.6e-05,
                    "dataRetrievalPrice": 0.024,
                },
                "iotTwinMaker": {
                    "unifiedDataAccessAPICallsPrice": 1.65e-06,
                    "entityPrice": 0.0525,
                    "queryPrice": 5.25e-05,
                },
                "awsManagedGrafana": {"editorPrice": 9.0, "viewerPrice": 5.0},
            },
            "azure": {
                "iotHub": {
                    "pricing_tiers": {
                        "freeTier": {"limit": 240000, "threshold": 0, "price": 0},
                        "tier1": {"limit": 120000000, "threshold": 12000000, "price": 25.0},
                    },
                },
                "functions": {
                    "requestPrice": 0.2,
                    "durationPrice": 1.6e-05,
                    "freeRequests": 1000000,
                    "freeComputeTime": 400000,
                },
                "logicApps": {
                    "pricePer1kStateTransitions": 0.125,
                    "pricePerStateTransition": 0.000125,
                },
                "eventGrid": {"pricePerMillionEvents": 0.6},
                "cosmosDB": {
                    "requestPrice": 0.0584,
                    "minimumRequestUnits": 400,
                    "RUsPerRead": 1,
                    "RUsPerWrite": 10,
                    "storagePrice": 0.02,
                },
                "blobStorageCool": {
                    "storagePrice": 0.01,
                    "writePrice": 1e-05,
                    "readPrice": 1e-05,
                    "dataRetrievalPrice": 0.01,
                },
                "blobStorageArchive": {
                    "storagePrice": 0.0018,
                    "writePrice": 1.3e-05,
                    "dataRetrievalPrice": 0.024,
                },
                "azureDigitalTwins": {
                    "messagePrice": 0.0013,
                    "operationPrice": 0.00325,
                    "queryPrice": 0.00065,
                },
                "azureManagedGrafana": {"userPrice": 6.0, "hourlyPrice": 0.069},
            },
            "gcp": {
                "iot": {"pricePerGiB": 0.0390625, "pricePerDeviceAndMonth": 0},
                "functions": {
                    "requestPrice": 4e-07,
                    "durationPrice": 2.5e-06,
                    "freeRequests": 2000000,
                    "freeComputeTime": 400000,
                },
                "storage_hot": {
                    "writePrice": 1.8e-06,
                    "readPrice": 3.3e-07,
                    "storagePrice": 0.135,
                    "freeStorage": 1,
                },
                "storage_cool": {
                    "storagePrice": 0.011,
                    "requestPrice": 2.6e-05,
                    "dataRetrievalPrice": 0.01,
                },
                "storage_archive": {
                    "storagePrice": 0.0014,
                    "lifecycleAndWritePrice": 6.5e-05,
                    "dataRetrievalPrice": 0.05,
                },
                "twinmaker": {
                    "e2MediumPrice": 0.0608511,
                    "storagePrice": 0.2,
                    "entityPrice": 0,
                },
                "grafana": {
                    "e2MediumPrice": 0.0608511,
                    "storagePrice": 0.2,
                },
                "cloudWorkflows": {"stepPrice": 2.5e-05},
            },
        }

    def test_all_azure_l2_components_nonzero(self, full_dynamic_pricing):
        """
        With orchestration enabled, Azure L2 should include Logic Apps cost.
        This is the main bug that was causing $0 L2.
        """
        from backend.calculation_v2.layers.azure_layers import AzureLayerCalculators
        
        calc = AzureLayerCalculators()
        result = calc.calculate_l2_cost(
            executions_per_month=10_000_000,  # 10M messages (above free tier)
            pricing=full_dynamic_pricing,
            number_of_device_types=3,
            use_event_checking=True,
            use_orchestration=True,  # This should trigger Logic Apps
            return_feedback_to_device=True,
            use_error_handling=False,
            num_event_actions=2,
            event_trigger_rate=0.1,
        )
        
        assert result.total_cost > 0, "Azure L2 total cost should not be zero!"
        assert "logic_apps" in result.components, "Logic Apps should be in L2 components!"
        assert result.components["logic_apps"] > 0, "Logic Apps cost should not be zero!"
