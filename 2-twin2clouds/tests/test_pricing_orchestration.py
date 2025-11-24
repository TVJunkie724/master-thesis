import pytest
import json
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open
from backend.calculate_up_to_date_pricing import (
    calculate_up_to_date_pricing,
    fetch_aws_data,
    fetch_azure_data,
    fetch_google_data,
    _get_or_warn
)
from backend.logger import logger

@patch('backend.calculate_up_to_date_pricing.config_loader.load_credentials_file')
@patch('backend.calculate_up_to_date_pricing.config_loader.load_json_file')
@patch('backend.calculate_up_to_date_pricing.fetch_aws_price')
@patch('backend.calculate_up_to_date_pricing.fetch_azure_price')
@patch('backend.cloud_price_fetcher_google.fetch_gcp_price')
@patch('builtins.open', new_callable=mock_open)
def test_calculate_up_to_date_pricing_integration(
    mock_file,
    mock_gcp_price,
    mock_azure_price,
    mock_aws_price,
    mock_load_json,
    mock_load_creds
):
    """Test the full orchestration flow"""
    
    # Mock GCP regions to avoid file loading issue
    mock_gcp_regions.return_value = {"us-central1": "us-central1"}
    
    # Mock configuration
    mock_load_creds.return_value = {
        "aws": {"access_key": "test"},
        "azure": {},
        "gcp": {}
    }
    
    # Mock load_json_file
    def load_json_side_effect(path):
        if "service_mapping" in str(path):
            return {"iot": "iotCore"}
        else:
            return {
                "aws": {"services": {"iot": {"region": "us-east-1"}}},
                "azure": {"services": {"iot": {"region": "westeurope"}}},
                "gcp": {"services": {"iot": {"region": "us-central1"}}}
            }
    
    mock_load_json.side_effect = load_json_side_effect
    
    # Mock price fetcher responses
    mock_aws_price.return_value = {"pricePerMessage": 0.001}
    mock_azure_price.return_value = {"pricePerMessage": 0.0009}
    mock_gcp_price.return_value = {"pricePerMessage": 0.0011}
    
    # Execute
    result = calculate_up_to_date_pricing(additional_debug=False)
    
    # Verify
    assert result is not None
    assert "aws" in result
    assert "azure" in result
    assert "gcp" in result
    
    # Verify file was written
    mock_file.assert_called()

def test_get_or_warn_with_fetched_value():
    """Test _get_or_warn when value is successfully fetched"""
    
    fetched = {"pricePerMessage": 0.001}
    static = {"pricePerMessage": 0.002}
    
    result = _get_or_warn(
        "AWS",
        "iot",
        "iot",
        "pricePerMessage",
        fetched,
        0.002,
        static
    )
    
    # Should return fetched value
    assert result == 0.001

def test_get_or_warn_fallback_to_default():
    """Test _get_or_warn when fetching fails and falls back to default"""
    
    fetched = {}  # Empty - no value fetched
    static = {}  # Not in static either
    default = 0.003
    
    result = _get_or_warn(
        "AWS",
        "iot",
        "iot",
        "pricePerMessage",
        fetched,
        default,
        static
    )
    
    # Should return default value
    assert result == default

def test_get_or_warn_with_static_value():
    """Test _get_or_warn when value comes from static defaults"""
    
    fetched = {}
    static = {"pricePerMessage": 0.002}
    
    result = _get_or_warn(
        "AWS",
        "iot",
        "iot",
        "pricePerMessage",
        fetched,
        0.002,
        static
    )
    
    # Should return static value (same as default in this case)
    assert result == 0.002

@patch('backend.calculate_up_to_date_pricing.fetch_aws_price')
def test_fetch_aws_data_structure(mock_fetch):
    """Test that fetch_aws_data returns correct structure"""
    
    mock_fetch.return_value = {"pricePerMessage": 0.001}
    
    aws_creds = {"access_key": "test"}
    service_mapping = {"iot": "iotCore"}
    aws_services = {
        "iot": {"region": "us-east-1"}
    }
    
    result = fetch_aws_data(aws_creds, service_mapping, aws_services, additional_debug=False)
    
    # Verify structure
    assert "iotCore" in result or "iot" in result
    assert isinstance(result, dict)

@patch('backend.calculate_up_to_date_pricing.fetch_azure_price')
def test_fetch_azure_data_structure(mock_fetch):
    """Test that fetch_azure_data returns correct structure"""
    
    mock_fetch.return_value = {"pricePerMessage": 0.001}
    
    azure_creds = {}
    service_mapping = {"iot": "iotHub"}
    azure_services = {
        "iot": {"region": "westeurope"}
    }
    
    result = fetch_azure_data(azure_creds, service_mapping, azure_services, additional_debug=False)
    
    assert "iotHub" in result or "iot" in result
    assert isinstance(result, dict)

@patch('backend.cloud_price_fetcher_google.fetch_gcp_price')
def test_fetch_google_data_structure(mock_fetch):
    """Test that fetch_google_data returns correct structure"""
    
    mock_fetch.return_value = {"pricePerMessage": 0.001}
    
    gcp_creds = {}
    service_mapping = {"iot": "iot"}
    gcp_services = {
        "iot": {"region": "us-central1"}
    }
    
    result = fetch_google_data(gcp_creds, service_mapping, gcp_services, additional_debug=False)
    
    assert "iot" in result
    assert isinstance(result, dict)

@patch('backend.calculate_up_to_date_pricing.config_loader.load_credentials_file')
@patch('backend.calculate_up_to_date_pricing.config_loader.load_json_file')
@patch('backend.calculate_up_to_date_pricing.fetch_aws_price')
@patch('builtins.open', new_callable=mock_open)
def test_calculate_up_to_date_pricing_handles_errors(
    mock_file,
    mock_aws_price,
    mock_load_json,
    mock_load_creds
):
    """Test that orchestration handles fetcher errors gracefully"""
    
    mock_load_creds.return_value = {
        "aws": {"access_key": "test"}
    }
    
    def load_json_side_effect(path):
        if "service_mapping" in str(path):
            return {"iot": "iotCore"}
        else:
            return {"aws": {"services": {"iot": {"region": "us-east-1"}}}}
    
    mock_load_json.side_effect = load_json_side_effect
    
    # Simulate fetcher error
    mock_aws_price.side_effect = Exception("API Error")
    
    # Should not crash, should fall back to static defaults
    result = calculate_up_to_date_pricing(additional_debug=False)
    
    assert result is not None
    assert "aws" in result
