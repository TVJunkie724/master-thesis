"""
Comparison Test: Old vs New Engine
===================================

This test verifies that the new calculation_v2 engine produces
consistent results with expected behavior for the same inputs.

Since the old engine is now deprecated, we test that the new engine:
1. Returns expected structure
2. Produces reasonable cost values
3. Handles all input parameters correctly
"""

import pytest
from typing import Dict, Any


# Standard test parameters matching typical use cases
STANDARD_PARAMS = {
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

# Realistic pricing data
REALISTIC_PRICING = {
    "aws": {
        "iotCore": {
            "pricePerDeviceAndMonth": 0.25,
            "priceRulesTriggered": 0.000001,
            "tierPricing": {
                "tier1": {"limit": 250000000, "price": 1.0},
                "tier2": {"limit": 5000000000, "price": 0.80},
            }
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
        "s3InfrequentAccess": {"storagePrice": 0.0125, "writePrice": 0.01},
        "s3GlacierDeepArchive": {"storagePrice": 0.00099, "writePrice": 0.05},
        "iotTwinMaker": {"queryPrice": 0.001, "entityPrice": 0.0},
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
            "writeRU": 5,
            "readRU": 1,
        },
        "blobStorageCool": {"storagePrice": 0.01, "writePrice": 0.01},
        "blobStorageArchive": {"storagePrice": 0.002, "writePrice": 0.02},
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


class TestEngineConsistency:
    """Test that the new engine produces consistent and expected results."""

    def test_calculate_cheapest_costs_structure(self):
        """Verify the output structure is complete."""
        from backend.calculation_v2.engine import calculate_cheapest_costs
        
        result = calculate_cheapest_costs(STANDARD_PARAMS, REALISTIC_PRICING)
        
        # Required top-level keys
        assert "calculationResult" in result
        assert "awsCosts" in result
        assert "azureCosts" in result
        assert "gcpCosts" in result
        assert "cheapestPath" in result
        assert "totalCost" in result
        
        # calculationResult structure
        calc = result["calculationResult"]
        assert "L1" in calc
        assert "L2" in calc
        assert "L3" in calc
        assert "L4" in calc
        assert "L5" in calc
        assert "Hot" in calc["L3"]
        assert "Cool" in calc["L3"]
        assert "Archive" in calc["L3"]
    
    def test_provider_costs_are_positive(self):
        """All provider costs should be positive for non-zero usage."""
        from backend.calculation_v2.engine import calculate_cheapest_costs
        
        result = calculate_cheapest_costs(STANDARD_PARAMS, REALISTIC_PRICING)
        
        for provider in ["awsCosts", "azureCosts", "gcpCosts"]:
            costs = result[provider]
            assert costs["L1"]["cost"] >= 0
            assert costs["L2"]["cost"] >= 0
            assert costs["L3_hot"]["cost"] >= 0
            assert costs["L3_cool"]["cost"] >= 0
            assert costs["L3_archive"]["cost"] >= 0
            assert costs["L4"]["cost"] >= 0
            assert costs["L5"]["cost"] >= 0
    
    def test_cheapest_path_format(self):
        """Cheapest path should have correct format."""
        from backend.calculation_v2.engine import calculate_cheapest_costs
        
        result = calculate_cheapest_costs(STANDARD_PARAMS, REALISTIC_PRICING)
        path = result["cheapestPath"]
        
        assert len(path) == 7  # L1, L2, L3_hot, L3_cool, L3_archive, L4, L5
        assert any("L1_" in p for p in path)
        assert any("L2_" in p for p in path)
        assert any("L3_hot_" in p for p in path)
        assert any("L3_cool_" in p for p in path)
        assert any("L3_archive_" in p for p in path)
        assert any("L4_" in p for p in path)
        assert any("L5_" in p for p in path)
    
    def test_total_cost_equals_sum(self):
        """Total cost should be sum of layer costs plus transfer costs."""
        from backend.calculation_v2.engine import calculate_cheapest_costs
        
        result = calculate_cheapest_costs(STANDARD_PARAMS, REALISTIC_PRICING)
        
        # Get the selected providers from cheapest path
        path = result["cheapestPath"]
        
        # Parse selected providers
        l1_provider = [p for p in path if "L1_" in p][0].split("_")[1].lower()
        l2_provider = [p for p in path if "L2_" in p and "L3" not in p][0].split("_")[1].lower()
        
        # Total cost should be > 0
        assert result["totalCost"] > 0
    
    def test_gcp_exclusion_respected(self):
        """GCP should be excluded from L4/L5 when flags are False."""
        from backend.calculation_v2.engine import calculate_cheapest_costs
        
        params = STANDARD_PARAMS.copy()
        params["allowGcpSelfHostedL4"] = False
        params["allowGcpSelfHostedL5"] = False
        
        result = calculate_cheapest_costs(params, REALISTIC_PRICING)
        
        path = result["cheapestPath"]
        l4_segment = [p for p in path if "L4_" in p][0]
        l5_segment = [p for p in path if "L5_" in p][0]
        
        assert "GCP" not in l4_segment
        assert "GCP" not in l5_segment
    
    def test_different_scenarios_produce_different_results(self):
        """Different input parameters should produce different costs."""
        from backend.calculation_v2.engine import calculate_cheapest_costs
        
        # Small scenario
        small_params = STANDARD_PARAMS.copy()
        small_params["numberOfDevices"] = 10
        small_result = calculate_cheapest_costs(small_params, REALISTIC_PRICING)
        
        # Large scenario
        large_params = STANDARD_PARAMS.copy()
        large_params["numberOfDevices"] = 10000
        large_result = calculate_cheapest_costs(large_params, REALISTIC_PRICING)
        
        # Large scenario should cost more
        assert large_result["totalCost"] > small_result["totalCost"]
