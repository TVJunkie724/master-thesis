import pytest
from unittest.mock import MagicMock, patch
from backend.calculation import decision, engine

def test_build_graph_for_storage():
    # Mock data for costs
    aws_hot = {"totalMonthlyCost": 100}
    azure_hot = {"totalMonthlyCost": 80}
    gcp_hot = {"totalMonthlyCost": 120}
    
    aws_cool = {"totalMonthlyCost": 50}
    azure_cool = {"totalMonthlyCost": 40}
    gcp_cool = {"totalMonthlyCost": 60}
    
    aws_archive = {"totalMonthlyCost": 10}
    azure_archive = {"totalMonthlyCost": 8}
    gcp_archive = {"totalMonthlyCost": 12}

    transfer_costs = {
        "AWS_Hot_to_AWS_Cool": 1,
        "AWS_Hot_to_Azure_Cool": 2,
        "AWS_Hot_to_GCP_Cool": 3,
        "Azure_Hot_to_AWS_Cool": 4,
        "Azure_Hot_to_Azure_Cool": 5,
        "Azure_Hot_to_GCP_Cool": 6,
        "GCP_Hot_to_AWS_Cool": 7,
        "GCP_Hot_to_Azure_Cool": 8,
        "GCP_Hot_to_GCP_Cool": 9,
        
        "AWS_Cool_to_AWS_Archive": 1,
        "AWS_Cool_to_Azure_Archive": 2,
        "AWS_Cool_to_GCP_Archive": 3,
        "Azure_Cool_to_AWS_Archive": 4,
        "Azure_Cool_to_Azure_Archive": 5,
        "Azure_Cool_to_GCP_Archive": 6,
        "GCP_Cool_to_AWS_Archive": 7,
        "GCP_Cool_to_Azure_Archive": 8,
        "GCP_Cool_to_GCP_Archive": 9,
    }

    graph = decision.build_graph_for_storage(
        aws_hot, azure_hot, gcp_hot,
        aws_cool, azure_cool, gcp_cool,
        aws_archive, azure_archive, gcp_archive,
        transfer_costs
    )

    assert "AWS_Hot" in graph
    assert graph["AWS_Hot"]["costs"] == 100
    assert graph["AWS_Hot"]["edges"]["AWS_Cool"] == 1
    assert graph["Azure_Cool"]["costs"] == 40
    assert graph["GCP_Archive"]["costs"] == 12

def test_find_cheapest_storage_path_simple():
    # A -> B -> C
    graph = {
        "A": {"costs": 10, "edges": {"B": 5}},
        "B": {"costs": 20, "edges": {"C": 5}},
        "C": {"costs": 30, "edges": {}}
    }
    
    result = decision.find_cheapest_storage_path(graph, ["A"], ["C"])
    
    # Cost = A(10) + edge(5) + B(20) + edge(5) + C(30) = 70
    assert result["cost"] == 70
    assert result["path"] == ["A", "B", "C"]

def test_find_cheapest_storage_path_branching():
    # Start -> A (10) -> End (10) = 20 + transfer
    # Start -> B (5) -> End (10) = 15 + transfer
    graph = {
        "Start": {"costs": 0, "edges": {"A": 1, "B": 1}},
        "A": {"costs": 10, "edges": {"End": 1}},
        "B": {"costs": 5, "edges": {"End": 1}},
        "End": {"costs": 10, "edges": {}}
    }
    
    result = decision.find_cheapest_storage_path(graph, ["Start"], ["End"])
    
    # Path 1: Start(0) + 1 + A(10) + 1 + End(10) = 22
    # Path 2: Start(0) + 1 + B(5) + 1 + End(10) = 17
    
    assert result["cost"] == 17
    assert result["path"] == ["Start", "B", "End"]

@patch('backend.calculation.engine._aws_calc')
@patch('backend.calculation.engine._azure_calc')
@patch('backend.calculation.engine._gcp_calc')
@patch('backend.calculation.engine.transfer')
@patch('backend.calculation.engine.load_json_file')
@patch('backend.calculation.engine.validate_pricing_schema')
def test_calculate_cheapest_costs_mocked(mock_validate, mock_load_json, mock_transfer, mock_gcp_calc, mock_azure_calc, mock_aws_calc):
    # Mock validation to pass
    mock_validate.return_value = {"status": "valid", "missing_keys": []}
    # Setup Mock Data
    mock_params = {
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
    mock_pricing = {
        "aws": {"enabled": True, "transfer": {"egressPrice": 0.09}},
        "azure": {"enabled": True, "transfer": {"pricing_tiers": {"tier1": {"price": 0.087}}}},
        "gcp": {"enabled": True, "transfer": {"egressPrice": 0.12}}
    }
    mock_load_json.return_value = mock_pricing

    # Helper to create a standard cost result
    def create_cost_result(cost, provider="TestProvider"):
        return {
            "provider": provider,
            "totalMonthlyCost": cost,
            "dataSizeInGB": 1.0,
            "totalMessagesPerMonth": 1000,
            "transferCostFromCosmosDB": 0.0,
            "transferCostFromDynamoDB": 0.0
        }

    # --- AWS Mocks ---
    mock_aws_calc.calculate_data_acquisition.return_value = create_cost_result(100, "AWS")
    mock_aws_calc.calculate_data_processing.return_value = create_cost_result(100, "AWS")
    mock_aws_calc.calculate_storage_hot.return_value = create_cost_result(100, "AWS") # Hot
    mock_aws_calc.calculate_storage_cool.return_value = create_cost_result(50, "AWS") # Cool
    mock_aws_calc.calculate_storage_archive.return_value = create_cost_result(10, "AWS") # Archive
    mock_aws_calc.calculate_twin_management.return_value = create_cost_result(100, "AWS") # L4
    mock_aws_calc.calculate_visualization.return_value = create_cost_result(100, "AWS") # L5

    # --- Azure Mocks ---
    mock_azure_calc.calculate_data_acquisition.return_value = create_cost_result(80, "Azure")
    mock_azure_calc.calculate_data_processing.return_value = create_cost_result(80, "Azure")
    mock_azure_calc.calculate_storage_hot.return_value = create_cost_result(80, "Azure") # Hot
    mock_azure_calc.calculate_storage_cool.return_value = create_cost_result(40, "Azure") # Cool
    mock_azure_calc.calculate_storage_archive.return_value = create_cost_result(8, "Azure") # Archive
    mock_azure_calc.calculate_twin_management.return_value = create_cost_result(80, "Azure") # L4
    mock_azure_calc.calculate_visualization.return_value = create_cost_result(80, "Azure") # L5

    # --- GCP Mocks ---
    mock_gcp_calc.calculate_data_acquisition.return_value = create_cost_result(120, "GCP")
    mock_gcp_calc.calculate_data_processing.return_value = create_cost_result(120, "GCP")
    mock_gcp_calc.calculate_storage_hot.return_value = create_cost_result(120, "GCP") # Hot
    mock_gcp_calc.calculate_storage_cool.return_value = create_cost_result(60, "GCP") # Cool
    mock_gcp_calc.calculate_storage_archive.return_value = create_cost_result(12, "GCP") # Archive
    mock_gcp_calc.calculate_twin_management.return_value = create_cost_result(120, "GCP") # L4
    mock_gcp_calc.calculate_visualization.return_value = create_cost_result(120, "GCP") # L5

    # --- Glue Function Mocks ---
    mock_aws_calc.calculate_connector_function_cost.return_value = 1.0
    mock_aws_calc.calculate_ingestion_function_cost.return_value = 1.0
    
    mock_azure_calc.calculate_connector_function_cost.return_value = 1.0
    mock_azure_calc.calculate_ingestion_function_cost.return_value = 1.0
    
    mock_gcp_calc.calculate_connector_function_cost.return_value = 1.0
    mock_gcp_calc.calculate_ingestion_function_cost.return_value = 1.0

    mock_gcp_calc.calculate_connector_function_cost.return_value = 1.0
    mock_gcp_calc.calculate_ingestion_function_cost.return_value = 1.0

    # --- Glue Function Mocks (L3 -> L4) ---
    mock_aws_calc.calculate_api_gateway_cost.return_value = 1.0
    mock_aws_calc.calculate_reader_function_cost.return_value = 1.0
    
    mock_azure_calc.calculate_api_gateway_cost.return_value = 1.0
    mock_azure_calc.calculate_reader_function_cost.return_value = 1.0
    
    mock_gcp_calc.calculate_api_gateway_cost.return_value = 1.0
    mock_gcp_calc.calculate_reader_function_cost.return_value = 1.0

    # --- Transfer Mocks ---
    # Helper to set return value on mock_transfer
    def set_transfer_cost(name, value=0.0):
        if hasattr(mock_transfer, name):
            getattr(mock_transfer, name).return_value = value
        else:
            # If it doesn't exist yet (MagicMock), creating it is fine
            getattr(mock_transfer, name).return_value = value

    # L2 -> Hot
    set_transfer_cost("calculate_transfer_cost_from_l2_aws_to_aws_hot")
    set_transfer_cost("calculate_transfer_cost_from_l2_aws_to_azure_hot")
    set_transfer_cost("calculate_transfer_cost_from_l2_aws_to_gcp_hot")
    set_transfer_cost("calculate_transfer_cost_from_l2_azure_to_aws_hot")
    set_transfer_cost("calculate_transfer_cost_from_l2_azure_to_azure_hot")
    set_transfer_cost("calculate_transfer_cost_from_l2_azure_to_gcp_hot")
    set_transfer_cost("calculate_transfer_cost_from_l2_gcp_to_aws_hot")
    set_transfer_cost("calculate_transfer_cost_from_l2_gcp_to_azure_hot")
    set_transfer_cost("calculate_transfer_cost_from_l2_gcp_to_gcp_hot")

    # Hot -> Cool
    set_transfer_cost("calculate_transfer_cost_from_aws_hot_to_aws_cool")
    set_transfer_cost("calculate_transfer_cost_from_aws_hot_to_azure_cool")
    set_transfer_cost("calculate_transfer_cost_from_aws_hot_to_gcp_cool")
    
    # Note: The inconsistent naming found earlier!
    set_transfer_cost("calculate_transfer_costs_from_azure_hot_to_aws_cool") 
    set_transfer_cost("calculate_transfer_cost_from_azure_hot_to_azure_cool")
    set_transfer_cost("calculate_transfer_cost_from_azure_hot_to_gcp_cool")
    
    set_transfer_cost("calculate_transfer_cost_from_gcp_hot_to_aws_cool")
    set_transfer_cost("calculate_transfer_cost_from_gcp_hot_to_azure_cool")
    set_transfer_cost("calculate_transfer_cost_from_gcp_hot_to_gcp_cool")

    # Cool -> Archive
    set_transfer_cost("calculate_transfer_cost_from_aws_cool_to_aws_archive")
    set_transfer_cost("calculate_transfer_cost_from_aws_cool_to_azure_archive")
    set_transfer_cost("calculate_transfer_cost_from_aws_cool_to_gcp_archive")
    set_transfer_cost("calculate_transfer_cost_from_azure_cool_to_aws_archive")
    set_transfer_cost("calculate_transfer_cost_from_azure_cool_to_azure_archive")
    set_transfer_cost("calculate_transfer_cost_from_azure_cool_to_gcp_archive")
    set_transfer_cost("calculate_transfer_cost_from_gcp_cool_to_aws_archive")
    set_transfer_cost("calculate_transfer_cost_from_gcp_cool_to_azure_archive")
    set_transfer_cost("calculate_transfer_cost_from_gcp_cool_to_gcp_archive")

    # Execute
    result = engine.calculate_cheapest_costs(mock_params, mock_pricing)

    # Assertions
    # Based on our mocks:
    # Azure Hot (80) < AWS Hot (100) < GCP Hot (120)
    # Azure Cool (40) < AWS Cool (50) < GCP Cool (60)
    # Azure Archive (8) < AWS Archive (10) < GCP Archive (12)
    # Transfer costs are 0.
    # Cheapest path should be Azure -> Azure -> Azure
    
    # Check structure
    # Check structure
    assert "calculationResult" in result
    
    # Check L2 selection (Storage Path)
    # Note: The result stores just the provider name (e.g. "Azure") not "Azure_Hot"
    assert result["calculationResult"]["L2"]["Hot"] == "Azure"
    assert result["calculationResult"]["L2"]["Cool"] == "Azure"
    assert result["calculationResult"]["L2"]["Archive"] == "Azure"
    
    # Check L1 selection
    assert result["calculationResult"]["L1"] == "Azure"
    
    # Check L3 selection
    assert result["calculationResult"]["L3"] == "Azure"
    
    # Check L5 selection
    assert result["calculationResult"]["L5"] == "Azure"
