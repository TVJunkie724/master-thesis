import pytest
import json
from unittest.mock import patch, MagicMock
from backend.fetch_data.calculate_up_to_date_pricing import calculate_up_to_date_pricing
import backend.constants as CONSTANTS

@patch('backend.fetch_data.calculate_up_to_date_pricing.config_loader.load_credentials_file')
@patch('backend.fetch_data.calculate_up_to_date_pricing.config_loader.load_service_mapping')
@patch('backend.fetch_data.calculate_up_to_date_pricing.config_loader.load_json_file')
@patch('backend.fetch_data.calculate_up_to_date_pricing.fetch_aws_data')
@patch('pathlib.Path.write_text')
def test_calculate_pricing_aws_centralized_loading(
    mock_write_text,
    mock_fetch_aws,
    mock_load_json,
    mock_load_mapping,
    mock_load_creds
):
    """
    Verify that calculate_up_to_date_pricing loads the AWS region map 
    and passes it to fetch_aws_data.
    """
    # Mock Credentials
    mock_load_creds.return_value = {"aws": {"access_key": "test"}}
    
    # Mock Service Mapping
    mock_load_mapping.return_value = {"iot": {"aws": "iotCore"}}
    
    # Mock Region Map Loading
    # We expect load_json_file to be called with AWS_REGIONS_FILE_PATH
    expected_region_map = {"us-east-1": "US East (N. Virginia)"}
    
    def load_json_side_effect(path):
        if path == CONSTANTS.AWS_REGIONS_FILE_PATH:
            return expected_region_map
        return {}
        
    mock_load_json.side_effect = load_json_side_effect
    
    # Mock Fetcher
    mock_fetch_aws.return_value = {"service": "data"}
    
    # Execute
    calculate_up_to_date_pricing("aws")
    
    # Verify
    # 1. Check that region map was loaded
    mock_load_json.assert_any_call(CONSTANTS.AWS_REGIONS_FILE_PATH)
    
    # 2. Check that fetch_aws_data was called with the region map
    args, kwargs = mock_fetch_aws.call_args
    # Signature: fetch_aws_data(aws_credentials, service_mapping, region_map, additional_debug)
    # region_map is the 3rd positional argument (index 2)
    assert args[2] == expected_region_map

@patch('backend.fetch_data.calculate_up_to_date_pricing.config_loader.load_credentials_file')
@patch('backend.fetch_data.calculate_up_to_date_pricing.config_loader.load_service_mapping')
@patch('backend.fetch_data.calculate_up_to_date_pricing.config_loader.load_json_file')
@patch('backend.fetch_data.calculate_up_to_date_pricing.fetch_azure_data')
@patch('pathlib.Path.write_text')
def test_calculate_pricing_azure_centralized_loading(
    mock_write_text,
    mock_fetch_azure,
    mock_load_json,
    mock_load_mapping,
    mock_load_creds
):
    """
    Verify that calculate_up_to_date_pricing loads the Azure region map 
    and passes it to fetch_azure_data.
    """
    mock_load_creds.return_value = {"azure": {"client_id": "test"}}
    mock_load_mapping.return_value = {"iot": {"azure": "iotHub"}}
    
    expected_region_map = {"westeurope": "West Europe"}
    
    def load_json_side_effect(path):
        if path == CONSTANTS.AZURE_REGIONS_FILE_PATH:
            return expected_region_map
        return {}
        
    mock_load_json.side_effect = load_json_side_effect
    mock_fetch_azure.return_value = {"service": "data"}
    
    calculate_up_to_date_pricing("azure")
    
    mock_load_json.assert_any_call(CONSTANTS.AZURE_REGIONS_FILE_PATH)
    
    args, kwargs = mock_fetch_azure.call_args
    # Signature: fetch_azure_data(azure_credentials, service_mapping, region_map, additional_debug)
    assert args[2] == expected_region_map
