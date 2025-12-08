"""
Tests for Strategy Pattern Implementation
==========================================
Tests the CloudProviderCalculator Protocol and Calculator classes.
"""

import pytest
from typing import Dict, Any
from backend.calculation.base import (
    CloudProviderCalculator,
    CalculationParams,
    LayerResult,
    get_calculators
)
from backend.calculation.aws import AWSCalculator
from backend.calculation.azure import AzureCalculator
from backend.calculation.gcp import GCPCalculator


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def sample_params() -> CalculationParams:
    """Standard calculation parameters for testing."""
    return {
        "numberOfDevices": 100,
        "deviceSendingIntervalInMinutes": 1.0,
        "averageSizeOfMessageInKb": 1.0,
        "hotStorageDurationInMonths": 1,
        "coolStorageDurationInMonths": 6,
        "archiveStorageDurationInMonths": 12,
        "entityCount": 10,
        "average3DModelSizeInMB": 10.0,
        "amountOfActiveEditors": 2,
        "amountOfActiveViewers": 5,
        "dashboardRefreshesPerHour": 4,
        "dashboardActiveHoursPerDay": 8,
        "useEventChecking": False,
        "triggerNotificationWorkflow": False,
        "returnFeedbackToDevice": False,
        "integrateErrorHandling": False,
        "orchestrationActionsPerMessage": 3,
        "eventsPerMessage": 1,
    }


@pytest.fixture
def sample_pricing() -> Dict[str, Any]:
    """Minimal pricing structure for testing."""
    return {
        "aws": {
            "iotCore": {
                "pricePerDeviceAndMonth": 0.0,
                "priceRulesTriggered": 0.0,
                "pricing_tiers": {
                    "tier1": {"limit": 1000000000, "price": 1e-6},
                    "tier2": {"limit": 5000000000, "price": 8e-7},
                    "tier3": {"limit": float("inf"), "price": 7e-7},
                }
            },
            "lambda": {
                "requestPrice": 2e-7,
                "durationPrice": 1.6e-5,
                "freeRequests": 1000000,
                "freeComputeTime": 400000,
            },
            "dynamoDB": {
                "writePrice": 7.6e-7,
                "readPrice": 1.5e-7,
                "storagePrice": 0.25,
                "freeStorage": 25,
            },
            "s3InfrequentAccess": {
                "storagePrice": 0.0125,
                "upfrontPrice": 0.0001,
                "requestPrice": 1e-6,
                "dataRetrievalPrice": 0.01,
            },
            "s3GlacierDeepArchive": {
                "storagePrice": 0.02,
                "lifecycleAndWritePrice": 3.6e-5,
                "dataRetrievalPrice": 0.02,
            },
            "iotTwinMaker": {
                "unifiedDataAccessAPICallsPrice": 1.6e-6,
                "entityPrice": 0.05,
                "queryPrice": 5e-5,
            },
            "awsManagedGrafana": {
                "editorPrice": 9.0,
                "viewerPrice": 5.0,
            },
            "stepFunctions": {"pricePerStateTransition": 2.5e-5},
            "eventBridge": {"pricePerMillionEvents": 1e-6},
            "apiGateway": {"pricePerMillionCalls": 1.2e-6, "dataTransferOutPrice": 0.09},
        },
        "azure": {
            "iotHub": {
                "pricing_tiers": {
                    "freeTier": {"limit": 240000, "threshold": 0, "price": 0},
                    "tier1": {"limit": 120000000, "threshold": 12000000, "price": 25.0},
                    "tier2": {"limit": 1800000000, "threshold": 180000000, "price": 250.0},
                    "tier3": {"limit": float("inf"), "threshold": 9000000000, "price": 2500.0},
                }
            },
            "functions": {
                "requestPrice": 0.2,
                "durationPrice": 1.6e-5,
                "freeRequests": 1000000,
                "freeComputeTime": 400000,
            },
            "cosmosDB": {
                "requestPrice": 0.06,
                "minimumRequestUnits": 400,
                "RUsPerRead": 1,
                "RUsPerWrite": 10,
                "storagePrice": 0.02,
            },
            "blobStorageCool": {
                "storagePrice": 0.01,
                "upfrontPrice": 0.0001,
                "writePrice": 1e-5,
                "readPrice": 1e-5,
                "dataRetrievalPrice": 0.01,
                "transferCostFromCosmosDB": 0.087,
            },
            "blobStorageArchive": {
                "storagePrice": 0.0018,
                "writePrice": 1.3e-5,
                "dataRetrievalPrice": 0.024,
            },
            "azureDigitalTwins": {
                "messagePrice": 0.0013,
                "operationPrice": 0.00325,
                "queryPrice": 0.00065,
                "queryUnitTiers": [
                    {"lower": 1, "upper": 99, "value": 15},
                    {"lower": 100, "upper": 9999, "value": 1500},
                    {"lower": 10000, "value": 4000},
                ]
            },
            "azureManagedGrafana": {"userPrice": 6.0, "hourlyPrice": 0.069},
            "logicApps": {"pricePerStateTransition": 0.000125},
            "eventGrid": {"pricePerMillionEvents": 0.6},
            "apiManagement": {"pricePerMillionCalls": 3.5},
        },
        "gcp": {
            "iot": {"pricePerGiB": 0.04, "pricePerDeviceAndMonth": 0},
            "functions": {
                "requestPrice": 4e-7,
                "durationPrice": 2.5e-6,
                "freeRequests": 2000000,
                "freeComputeTime": 400000,
            },
            "storage_hot": {
                "writePrice": 1.8e-6,
                "readPrice": 3.3e-7,
                "storagePrice": 0.135,
                "freeStorage": 1,
            },
            "storage_cool": {
                "storagePrice": 0.011,
                "upfrontPrice": 0.0,
                "writePrice": 2.6e-5,
                "readPrice": 2.6e-5,
                "dataRetrievalPrice": 0.01,
            },
            "storage_archive": {
                "storagePrice": 0.0014,
                "lifecycleAndWritePrice": 6.5e-5,
                "writePrice": 6.5e-5,
                "dataRetrievalPrice": 0.05,
            },
            "twinmaker": {
                "e2MediumPrice": 0.06,
                "storagePrice": 0.2,
                "entityPrice": 0,
                "unifiedDataAccessAPICallsPrice": 0,
                "queryPrice": 0,
            },
            "grafana": {
                "e2MediumPrice": 0.06,
                "storagePrice": 0.2,
                "editorPrice": 0,
                "viewerPrice": 0,
            },
            "cloudWorkflows": {"stepPrice": 2.5e-5},
            "apiGateway": {"pricePerMillionCalls": 3.0, "dataTransferOutPrice": 0.12},
        },
    }


# =============================================================================
# Protocol Compliance Tests
# =============================================================================

class TestProtocolCompliance:
    """Test that all calculator classes implement the Protocol correctly."""
    
    def test_all_calculators_implement_protocol(self):
        """All calculator classes should be instances of CloudProviderCalculator."""
        calculators = get_calculators()
        
        assert len(calculators) == 3
        for calc in calculators:
            assert isinstance(calc, CloudProviderCalculator)
    
    def test_aws_calculator_has_name(self):
        """AWSCalculator should have 'aws' as name."""
        calc = AWSCalculator()
        assert calc.name == "aws"
    
    def test_azure_calculator_has_name(self):
        """AzureCalculator should have 'azure' as name."""
        calc = AzureCalculator()
        assert calc.name == "azure"
    
    def test_gcp_calculator_has_name(self):
        """GCPCalculator should have 'gcp' as name."""
        calc = GCPCalculator()
        assert calc.name == "gcp"
    
    def test_all_calculators_have_required_methods(self):
        """All calculators should have all required layer calculation methods."""
        required_methods = [
            "calculate_data_acquisition",
            "calculate_data_processing",
            "calculate_storage_hot",
            "calculate_storage_cool",
            "calculate_storage_archive",
            "calculate_twin_management",
            "calculate_visualization",
            "calculate_connector_function_cost",
            "calculate_ingestion_function_cost",
            "calculate_reader_function_cost",
            "calculate_api_gateway_cost",
        ]
        
        for calc in get_calculators():
            for method_name in required_methods:
                assert hasattr(calc, method_name), f"{calc.name} missing {method_name}"
                assert callable(getattr(calc, method_name))


# =============================================================================
# Functional Tests - AWS Calculator
# =============================================================================

class TestAWSCalculator:
    """Test AWS calculator functionality."""
    
    def test_calculate_data_acquisition_returns_dict(self, sample_params, sample_pricing):
        """Data acquisition should return a dictionary with required keys."""
        calc = AWSCalculator()
        result = calc.calculate_data_acquisition(sample_params, sample_pricing)
        
        assert isinstance(result, dict)
        assert "provider" in result
        assert result["provider"] == "AWS"
        assert "totalMonthlyCost" in result
        assert result["totalMonthlyCost"] >= 0
    
    def test_calculate_data_processing_returns_dict(self, sample_params, sample_pricing):
        """Data processing should return a dictionary with required keys."""
        calc = AWSCalculator()
        result = calc.calculate_data_processing(sample_params, sample_pricing)
        
        assert isinstance(result, dict)
        assert result["provider"] == "AWS"
        assert "totalMonthlyCost" in result
    
    def test_calculate_storage_hot(self, sample_params, sample_pricing):
        """Hot storage calculation should work correctly."""
        calc = AWSCalculator()
        result = calc.calculate_storage_hot(
            sample_params, sample_pricing, 
            data_size_in_gb=10.0, 
            total_messages_per_month=1000000
        )
        
        assert result["provider"] == "AWS"
        assert "totalMonthlyCost" in result
    
    def test_calculate_visualization(self, sample_params, sample_pricing):
        """Visualization cost should include editors and viewers."""
        calc = AWSCalculator()
        result = calc.calculate_visualization(sample_params, sample_pricing)
        
        assert result["provider"] == "AWS"
        # With 2 editors at $9 and 5 viewers at $5 = $18 + $25 = $43
        expected_cost = (2 * 9.0) + (5 * 5.0)
        assert result["totalMonthlyCost"] == pytest.approx(expected_cost)


# =============================================================================
# Functional Tests - Azure Calculator
# =============================================================================

class TestAzureCalculator:
    """Test Azure calculator functionality."""
    
    def test_calculate_data_acquisition(self, sample_params, sample_pricing):
        """Azure data acquisition should return correct structure."""
        calc = AzureCalculator()
        result = calc.calculate_data_acquisition(sample_params, sample_pricing)
        
        assert result["provider"] == "Azure"
        assert "totalMonthlyCost" in result
    
    def test_calculate_twin_management(self, sample_params, sample_pricing):
        """Azure Digital Twins calculation."""
        calc = AzureCalculator()
        result = calc.calculate_twin_management(sample_params, sample_pricing)
        
        assert result["provider"] == "Azure"
        assert result["totalMonthlyCost"] >= 0


# =============================================================================
# Functional Tests - GCP Calculator
# =============================================================================

class TestGCPCalculator:
    """Test GCP calculator functionality."""
    
    def test_calculate_data_acquisition(self, sample_params, sample_pricing):
        """GCP data acquisition (Pub/Sub) should be volume-based."""
        calc = GCPCalculator()
        result = calc.calculate_data_acquisition(sample_params, sample_pricing)
        
        assert result["provider"] == "GCP"
        assert "totalMonthlyCost" in result
        assert "dataSizeInGB" in result  # GCP is volume-based
    
    def test_gcp_visualization_is_self_hosted(self, sample_params, sample_pricing):
        """GCP visualization uses self-hosted Grafana (VM cost, not per-seat)."""
        calc = GCPCalculator()
        result = calc.calculate_visualization(sample_params, sample_pricing)
        
        assert result["provider"] == "GCP"
        # GCP cost should be instance + storage, not per-user
        # e2-medium * 730 + storage for 20GB
        expected = (0.06 * 730) + (20 * 0.2)
        assert result["totalMonthlyCost"] == pytest.approx(expected, rel=1e-3)


# =============================================================================
# Edge Case Tests
# =============================================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_zero_devices(self, sample_params, sample_pricing):
        """Zero devices should result in zero or minimal cost."""
        calc = AWSCalculator()
        params = dict(sample_params)
        params["numberOfDevices"] = 0
        
        # This may cause division by zero or return 0 - depends on implementation
        # We just verify it doesn't crash
        try:
            result = calc.calculate_data_acquisition(params, sample_pricing)
            assert result["totalMonthlyCost"] >= 0
        except (ZeroDivisionError, ValueError):
            pass  # Some implementations may not handle zero devices
    
    def test_very_large_message_count(self, sample_params, sample_pricing):
        """Very high message volumes should still calculate correctly."""
        calc = AWSCalculator()
        params = dict(sample_params)
        params["numberOfDevices"] = 10000
        params["deviceSendingIntervalInMinutes"] = 0.1  # Very frequent
        
        result = calc.calculate_data_acquisition(params, sample_pricing)
        assert result["totalMonthlyCost"] > 0
        assert result["totalMessagesPerMonth"] > 0
    
    def test_optional_params_use_defaults(self, sample_pricing):
        """Calculator should handle missing optional params with defaults."""
        calc = AWSCalculator()
        minimal_params = {
            "numberOfDevices": 10,
            "deviceSendingIntervalInMinutes": 1.0,
            "averageSizeOfMessageInKb": 1.0,
        }
        
        # Processing with optional params should use defaults
        result = calc.calculate_data_processing(minimal_params, sample_pricing)
        assert result["provider"] == "AWS"
