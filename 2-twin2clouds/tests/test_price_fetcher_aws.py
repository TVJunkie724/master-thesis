import pytest
import json
from unittest.mock import patch, MagicMock
from backend.cloud_price_fetcher_aws import fetch_aws_price, _parse_price_dimensions

def test_parse_price_dimensions_basic():
    """Test basic price dimension parsing"""
    
    # Mock price list response - must be JSON strings
    price_list = [
        json.dumps({
            "product": {
                "attributes": {
                    "description": "IoT Core message pricing"
                }
            },
            "terms": {
                "OnDemand": {
                    "term1": {
                        "priceDimensions": {
                            "dim1": {
                                "pricePerUnit": {"USD": "0.000001"},
                                "description": "Per 1 million messages"
                            }
                        }
                    }
                }
            }
        })
    ]
    
    field_map = {
        "pricePerMessage": ["message", "per 1 million"]
    }
    
    # Execute
    result = _parse_price_dimensions(
        price_list, 
        field_map, 
        include_keywords=["iot", "message"],
        debug=False
    )
    
    # Verify
    assert "pricePerMessage" in result
    assert result["pricePerMessage"] == 0.000001

def test_parse_price_dimensions_with_exclusion():
    """Test that exclusion keywords filter out unwanted results"""
    
    price_list = [
        json.dumps({
            "product": {
                "attributes": {
                    "description": "LoRaWAN message pricing"  # Should be excluded
                }
            },
            "terms": {
                "OnDemand": {
                    "term1": {
                        "priceDimensions": {
                            "dim1": {
                                "pricePerUnit": {"USD": "0.999"},
                                "description": "LoRaWAN messages"
                            }
                        }
                    }
                }
            }
        })
    ]
    
    field_map = {
        "pricePerMessage": ["message"]
    }
    
    result = _parse_price_dimensions(
        price_list,
        field_map,
        include_keywords=["iot", "message"],
        exclude_keywords=["lorawan"],
        debug=False
    )
    
    # Should not find a match due to exclusion
    assert "pricePerMessage" not in result

@patch('backend.cloud_price_fetcher_aws.config_loader.load_aws_credentials')
@patch('backend.cloud_price_fetcher_aws.boto3.client')
@patch('backend.cloud_price_fetcher_aws._fetch_pricing_response')
def test_fetch_aws_price_iot(mock_fetch_response, mock_boto_client, mock_load_creds):
    """Test fetching AWS IoT Core pricing"""
    
    # Mock credentials
    mock_load_creds.return_value = {"region_name": "us-east-1"}
    
    # Mock pricing response - must be JSON strings
    mock_fetch_response.return_value = [
        json.dumps({
            "product": {
                "attributes": {
                    "description": "AWS IoT Core message pricing"
                }
            },
            "terms": {
                "OnDemand": {
                    "term1": {
                        "priceDimensions": {
                            "dim1": {
                                "pricePerUnit": {"USD": "0.000001"},
                                "description": "per 1 million messages"
                            }
                        }
                    }
                }
            }
        })
    ]
    
    # Execute
    result = fetch_aws_price("iot", "us-east-1", debug=False)
    
    # Verify
    assert result is not None
    assert "pricePerMessage" in result or "pricePerDeviceAndMonth" in result

@patch('backend.cloud_price_fetcher_aws.config_loader.load_aws_credentials')
@patch('backend.cloud_price_fetcher_aws.boto3.client')
@patch('backend.cloud_price_fetcher_aws._fetch_pricing_response')
def test_fetch_aws_price_lambda(mock_fetch_response, mock_boto_client, mock_load_creds):
    """Test fetching AWS Lambda pricing"""
    
    # Mock credentials
    mock_load_creds.return_value = {"region_name": "us-east-1"}
    
    mock_fetch_response.return_value = [
        json.dumps({
            "product": {
                "attributes": {
                    "description": "AWS Lambda request pricing"
                }
            },
            "terms": {
                "OnDemand": {
                    "term1": {
                        "priceDimensions": {
                            "dim1": {
                                "pricePerUnit": {"USD": "0.0000002"},
                                "description": "per request"
                            }
                        }
                    }
                }
            }
        })
    ]
    
    result = fetch_aws_price("functions", "us-east-1", debug=False)
    
    assert result is not None
    # Lambda should have free tier defaults even if not fetched dynamically
    assert "freeRequests" in result
    assert "freeComputeTime" in result

def test_parse_price_dimensions_empty_list():
    """Test parsing with empty price list"""
    
    result = _parse_price_dimensions(
        [],
        {"pricePerMessage": ["message"]},
        include_keywords=["iot"],
        debug=False
    )
    
    # Should return empty dict or defaults
    assert isinstance(result, dict)
