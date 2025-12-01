import pytest
import json
from unittest.mock import patch, MagicMock
from backend.fetch_data.cloud_price_fetcher_aws import fetch_aws_price, _extract_prices_from_api_response

# Mock data for AWS Pricing API response
def create_mock_price_item(description, price_per_unit, unit="USD"):
    return json.dumps({
        "product": {
            "attributes": {
                "description": description
            }
        },
        "terms": {
            "OnDemand": {
                "term1": {
                    "priceDimensions": {
                        "dim1": {
                            "description": description,
                            "pricePerUnit": {unit: str(price_per_unit)}
                        }
                    }
                }
            }
        }
    })

def test_extract_prices_from_api_response_basic():
    """Test basic price extraction"""
    price_list = [
        create_mock_price_item("IoT Core message pricing", 0.000001)
    ]
    
    field_map = {
        "pricePerMessage": ["message"]
    }
    
    result = _extract_prices_from_api_response(
        price_list, 
        field_map, 
        include_keywords=["iot", "message"],
        debug=False
    )
    
    assert "pricePerMessage" in result
    assert result["pricePerMessage"] == 0.000001

def test_extract_prices_from_api_response_with_exclusion():
    """Test that exclusion keywords filter out unwanted results"""
    price_list = [
        create_mock_price_item("LoRaWAN message pricing", 0.999)
    ]
    
    field_map = {
        "pricePerMessage": ["message"]
    }
    
    result = _extract_prices_from_api_response(
        price_list,
        field_map,
        include_keywords=["iot", "message"],
        exclude_keywords=["lorawan"],
        debug=False
    )
    
    assert "pricePerMessage" not in result

@patch('backend.fetch_data.cloud_price_fetcher_aws._get_pricing_client')
@patch('backend.fetch_data.cloud_price_fetcher_aws._fetch_api_products')
def test_fetch_aws_price_iot(mock_fetch_products, mock_get_client):
    """Test fetching AWS IoT Core pricing"""
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    
    # Mock product list
    mock_fetch_products.return_value = [
        create_mock_price_item("AWS IoT Core message pricing", 0.000001)
    ]
    
    region_map = {"us-east-1": "US East (N. Virginia)"}
    
    result = fetch_aws_price("iot", "AmazonIoT", "us-east-1", region_map, debug=False)
    
    assert result is not None
    assert "pricePerMessage" in result
    assert result["pricePerMessage"] == 0.000001

@patch('backend.fetch_data.cloud_price_fetcher_aws._get_pricing_client')
@patch('backend.fetch_data.cloud_price_fetcher_aws._fetch_api_products')
def test_fetch_aws_price_lambda(mock_fetch_products, mock_get_client):
    """Test fetching AWS Lambda pricing"""
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    
    mock_fetch_products.return_value = [
        create_mock_price_item("AWS Lambda total requests pricing", 0.0000002)
    ]
    
    region_map = {"us-east-1": "US East (N. Virginia)"}
    
    result = fetch_aws_price("functions", "AWSLambda", "us-east-1", region_map, debug=False)
    
    assert result is not None
    assert "requestPrice" in result
    # Defaults should be merged
    assert "freeRequests" in result
    assert result["freeRequests"] == 1_000_000

@patch('backend.fetch_data.cloud_price_fetcher_aws._get_pricing_client')
def test_fetch_aws_price_client_error(mock_get_client):
    """Test handling of client creation failure"""
    mock_get_client.return_value = None
    
    region_map = {"us-east-1": "US East (N. Virginia)"}
    
    result = fetch_aws_price("iot", "AmazonIoT", "us-east-1", region_map, debug=False)
    
    # Should return static defaults
    assert result is not None
    assert "pricePerDeviceAndMonth" in result

@patch('backend.fetch_data.cloud_price_fetcher_aws._get_pricing_client')
@patch('backend.fetch_data.cloud_price_fetcher_aws._fetch_api_products')
def test_fetch_aws_price_unknown_service(mock_fetch_products, mock_get_client):
    """Test fetching for an unknown service"""
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    
    region_map = {"us-east-1": "US East (N. Virginia)"}
    
    result = fetch_aws_price("unknown_service", "Unknown", "us-east-1", region_map, debug=False)
    
    assert result == {}
