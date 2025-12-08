import pytest
from unittest.mock import MagicMock, patch
from backend.calculation import engine

@patch('backend.calculation.engine._aws_calc')
@patch('backend.calculation.engine._azure_calc')
@patch('backend.calculation.engine._gcp_calc')
@patch('backend.calculation.engine.transfer')
@patch('backend.calculation.engine.load_json_file')
@patch('backend.calculation.engine.validate_pricing_schema')
def test_l4_glue_code_costs(mock_validate, mock_load_json, mock_transfer, mock_gcp_calc, mock_azure_calc, mock_aws_calc):
    # Mock validation and pricing
    mock_validate.return_value = {"status": "valid", "missing_keys": []}
    mock_pricing = {
        "aws": {"enabled": True, "transfer": {"egressPrice": 0.09}},
        "azure": {"enabled": True, "transfer": {"pricing_tiers": {"tier1": {"price": 0.087}}}},
        "gcp": {"enabled": True, "transfer": {"egressPrice": 0.12}}
    }
    mock_load_json.return_value = mock_pricing

    # Standard params including the new required 3D model param
    params = {
        "numberOfDevices": 100,
        "deviceSendingIntervalInMinutes": 5,
        "averageSizeOfMessageInKb": 1,
        "hotStorageDurationInMonths": 12,
        "coolStorageDurationInMonths": 12,
        "archiveStorageDurationInMonths": 12,
        "amountOfActiveEditors": 1,
        "amountOfActiveViewers": 10,
        "dashboardRefreshesPerHour": 1,
        "dashboardActiveHoursPerDay": 8,
        "entityCount": 10,
        "needs3DModel": False,
        "average3DModelSizeInMB": 50
    }

    # --- Setup Mocks to FORCE AWS as the L3 Provider ---
    # We do this by making AWS L3 data processing very cheap and others expensive.
    
    # Helper for cost result
    def create_result(cost, provider):
        return {
            "provider": provider,
            "totalMonthlyCost": cost,
            "dataSizeInGB": 1.0,
            "totalMessagesPerMonth": 1000,
            "glueCodeCost": 0 # Default
        }

    # Data Acquisition (L1) & Hot (L2) - Make them equal or valid so proper path is chosen
    # We want AWS Hot to be chosen to keep things simple for L3 choice (Data Gravity)
    mock_aws_calc.calculate_data_acquisition.return_value = create_result(10, "AWS")
    mock_azure_calc.calculate_data_acquisition.return_value = create_result(100, "Azure")
    mock_gcp_calc.calculate_data_acquisition.return_value = create_result(100, "GCP")

    # L2 Hot Storage
    mock_aws_calc.calculate_storage_hot.return_value = create_result(10, "AWS")
    mock_azure_calc.calculate_storage_hot.return_value = create_result(100, "Azure")
    mock_gcp_calc.calculate_storage_hot.return_value = create_result(100, "GCP")
    # This should make AWS_Hot the storage provider.

    # L3 Data Processing
    mock_aws_calc.calculate_data_processing.return_value = create_result(10, "AWS") # Cheapest L3
    mock_azure_calc.calculate_data_processing.return_value = create_result(100, "Azure") # Expensive
    mock_gcp_calc.calculate_data_processing.return_value = create_result(100, "GCP") # Expensive

    # L4 Twin Management - Return valid structure
    mock_aws_calc.calculate_twin_management.return_value = create_result(50, "AWS")
    mock_azure_calc.calculate_twin_management.return_value = create_result(50, "Azure")
    mock_gcp_calc.calculate_twin_management.return_value = create_result(50, "GCP")

    # L5 - Irrelevant but needed
    mock_aws_calc.calculate_visualization.return_value = create_result(10, "AWS")
    mock_azure_calc.calculate_visualization.return_value = create_result(10, "Azure")
    mock_gcp_calc.calculate_visualization.return_value = create_result(10, "GCP")

    # Other required mocks
    mock_aws_calc.calculate_storage_cool.return_value = create_result(1, "AWS")
    mock_aws_calc.calculate_storage_archive.return_value = create_result(1, "AWS")
    
    mock_azure_calc.calculate_storage_cool.return_value = create_result(1, "Azure")
    mock_azure_calc.calculate_storage_archive.return_value = create_result(1, "Azure")

    mock_gcp_calc.calculate_storage_cool.return_value = create_result(1, "GCP")
    mock_gcp_calc.calculate_storage_archive.return_value = create_result(1, "GCP")

    # Transfer Mocks - Return 0.0 to avoid TypeError in sorting
    # We must configure the mock to return a float, otherwise it returns a MagicMock
    # which cannot be compared with floats/ints.
    mock_transfer.calculate_transfer_cost_from_l2_aws_to_aws_hot.return_value = 0.0
    mock_transfer.calculate_transfer_cost_from_l2_aws_to_azure_hot.return_value = 0.0
    mock_transfer.calculate_transfer_cost_from_l2_aws_to_gcp_hot.return_value = 0.0
    mock_transfer.calculate_transfer_cost_from_l2_azure_to_aws_hot.return_value = 0.0
    mock_transfer.calculate_transfer_cost_from_l2_azure_to_azure_hot.return_value = 0.0
    mock_transfer.calculate_transfer_cost_from_l2_azure_to_gcp_hot.return_value = 0.0
    mock_transfer.calculate_transfer_cost_from_l2_gcp_to_aws_hot.return_value = 0.0
    mock_transfer.calculate_transfer_cost_from_l2_gcp_to_azure_hot.return_value = 0.0
    mock_transfer.calculate_transfer_cost_from_l2_gcp_to_gcp_hot.return_value = 0.0
    
    mock_transfer.calculate_transfer_cost_from_aws_hot_to_aws_cool.return_value = 0.0
    mock_transfer.calculate_transfer_cost_from_aws_hot_to_azure_cool.return_value = 0.0
    mock_transfer.calculate_transfer_cost_from_aws_hot_to_gcp_cool.return_value = 0.0
    mock_transfer.calculate_transfer_costs_from_azure_hot_to_aws_cool.return_value = 0.0
    mock_transfer.calculate_transfer_cost_from_azure_hot_to_azure_cool.return_value = 0.0
    mock_transfer.calculate_transfer_cost_from_azure_hot_to_gcp_cool.return_value = 0.0
    mock_transfer.calculate_transfer_cost_from_gcp_hot_to_aws_cool.return_value = 0.0
    mock_transfer.calculate_transfer_cost_from_gcp_hot_to_azure_cool.return_value = 0.0
    mock_transfer.calculate_transfer_cost_from_gcp_hot_to_gcp_cool.return_value = 0.0

    mock_transfer.calculate_transfer_cost_from_aws_cool_to_aws_archive.return_value = 0.0
    mock_transfer.calculate_transfer_cost_from_aws_cool_to_azure_archive.return_value = 0.0
    mock_transfer.calculate_transfer_cost_from_aws_cool_to_gcp_archive.return_value = 0.0
    mock_transfer.calculate_transfer_cost_from_azure_cool_to_aws_archive.return_value = 0.0
    mock_transfer.calculate_transfer_cost_from_azure_cool_to_azure_archive.return_value = 0.0
    mock_transfer.calculate_transfer_cost_from_azure_cool_to_gcp_archive.return_value = 0.0
    mock_transfer.calculate_transfer_cost_from_gcp_cool_to_aws_archive.return_value = 0.0
    mock_transfer.calculate_transfer_cost_from_gcp_cool_to_azure_archive.return_value = 0.0
    mock_transfer.calculate_transfer_cost_from_gcp_cool_to_gcp_archive.return_value = 0.0

    # Glue Code functions - Mock return values to be non-zero so we can verify them
    GLUE_COST = 5.55
    mock_aws_calc.calculate_api_gateway_cost.return_value = GLUE_COST / 2
    mock_aws_calc.calculate_reader_function_cost.return_value = GLUE_COST / 2
    mock_azure_calc.calculate_api_gateway_cost.return_value = GLUE_COST / 2
    mock_azure_calc.calculate_reader_function_cost.return_value = GLUE_COST / 2
    mock_gcp_calc.calculate_api_gateway_cost.return_value = GLUE_COST / 2
    mock_gcp_calc.calculate_reader_function_cost.return_value = GLUE_COST / 2

    # L1 -> L2 Glue Code Mocks (Connector/Ingestion)
    mock_aws_calc.calculate_connector_function_cost.return_value = 1.0
    mock_aws_calc.calculate_ingestion_function_cost.return_value = 1.0
    mock_azure_calc.calculate_connector_function_cost.return_value = 1.0
    mock_azure_calc.calculate_ingestion_function_cost.return_value = 1.0
    mock_gcp_calc.calculate_connector_function_cost.return_value = 1.0
    mock_gcp_calc.calculate_ingestion_function_cost.return_value = 1.0
    
    # We expect L3 to be AWS.
    # So:
    # L4 AWS (Same cloud) -> Glue Cost should be 0.
    # L4 Azure (Cross cloud) -> Glue Cost should be GLUE_COST (from AWS L3 components).
    # L4 GCP (Cross cloud) -> Glue Cost should be GLUE_COST.

    # Execute
    result = engine.calculate_cheapest_costs(params, mock_pricing)

    # Verification
    # 1. Verify L3 is AWS
    # result["calculationResult"]["L3"] depends on the 'cheapestPath' logic
    # But we can check the costs dictionary directly.
    
    aws_l4_result = result["awsCosts"]["resultL4"]
    azure_l4_result = result["azureCosts"]["resultL4"]
    gcp_l4_result = result["gcpCosts"]["resultL4"]

    # AWS L4 (Same as L3) - Should have 0 glue cost
    assert aws_l4_result["glueCodeCost"] == 0
    assert aws_l4_result["totalMonthlyCost"] == 50 # Base cost only

    # Azure L4 (Different from L3) - Should have glue cost
    # Warning: engine.py 706-714 logic adds glue cost to existing dictionary
    assert azure_l4_result["glueCodeCost"] == GLUE_COST
    assert azure_l4_result["totalMonthlyCost"] == 50 + GLUE_COST

    # GCP L4 (Different)
    assert gcp_l4_result["glueCodeCost"] == GLUE_COST
    assert gcp_l4_result["totalMonthlyCost"] == 50 + GLUE_COST

    print("L4 Glue Code Logic Verified!")
