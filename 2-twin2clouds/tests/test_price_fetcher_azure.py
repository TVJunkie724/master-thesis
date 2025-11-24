import pytest
from unittest.mock import patch, MagicMock
from backend.cloud_price_fetcher_azure import fetch_azure_price, _find_matching_row, _get_unit_price

def test_find_matching_row_basic():
    """Test finding a matching row with meter and unit keywords - uses real service config"""
    
    rows = [
        {
            "productName": "Functions",
            "serviceName": "Functions", 
            "meterName": "Total Executions",
            "unitOfMeasure": "1 Million",
            "unitPrice": 0.20,
            "currencyCode": "USD",
            "skuName": "Standard"
        },
        {
            "productName": "Functions",
            "serviceName": "Functions",
            "meterName": "Data Stored",
            "unitOfMeasure": "1 GB/Month",
            "unitPrice": 0.02,
            "currencyCode": "USD",
            "skuName": "Standard"
        }
    ]
    
    # Find execution pricing - returns the row, not the price
    result_row = _find_matching_row(
        rows,
        meter_kw="Total Executions",
        unit_kw="1 Million",
        neutral="functions",  # Uses AZURE_SERVICE_KEYWORDS["functions"]
        key="requestPrice",
        debug=False
    )
    
    assert result_row is not None
    assert _get_unit_price(result_row) == 0.20

def test_find_matching_row_case_insensitive():
    """Test that matching is case-insensitive"""
    
    rows = [
        {
            "productName": "Azure Cosmos DB",
            "serviceName": "Azure Cosmos DB",
            "meterName": "Standard Data Stored",
            "unitOfMeasure": "1 GB/Month",
            "unitPrice": 0.25,
            "currencyCode": "USD",
            "skuName": "Standard"
        }
    ]
    
    result_row = _find_matching_row(
        rows,
        meter_kw="Standard Data Stored",
        unit_kw="1 GB/Month",
        neutral="storage_hot",  # Uses AZURE_SERVICE_KEYWORDS["storage_hot"]
        key="storagePrice",
        debug=False
    )
    
    assert result_row is not None
    assert _get_unit_price(result_row) == 0.25

def test_find_matching_row_no_match():
    """Test behavior when no match is found"""
    
    rows = [
        {
            "productName": "Something",
            "serviceName": "Something",
            "meterName": "Something Else",
            "unitOfMeasure": "1 Unit",
            "unitPrice": 99.99,
            "currencyCode": "USD",
            "skuName": "Standard"
        }
    ]
    
    result = _find_matching_row(
        rows,
        meter_kw="not found",
        unit_kw="not found",
        neutral="functions",
        key="testPrice",
        debug=False
    )
    
    assert result is None

@patch('backend.cloud_price_fetcher_azure.requests.get')
def test_fetch_azure_price_functions(mock_get):
    """Test fetching Azure Functions pricing"""
    
    # Mock response
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "Items": [
            {
                "serviceName": "Functions",
                "meterName": "Total Executions",
                "unitOfMeasure": "1 Million",
                "unitPrice": 0.20,
                "armRegionName": "westeurope",
                "currencyCode": "USD",
                "productName": "Azure Functions"
            },
            {
                "serviceName": "Functions",
                "meterName": "Execution Time",
                "unitOfMeasure": "1 GB-s",
                "unitPrice": 0.000016,
                "armRegionName": "westeurope",
                "currencyCode": "USD",
                "productName": "Azure Functions"
            }
        ],
        "NextPageLink": None
    }
    mock_response.status_code = 200
    mock_get.return_value = mock_response
    
    # Execute
    result = fetch_azure_price("functions", "westeurope", debug=False)
    
    # Verify
    assert result is not None
    assert "freeRequests" in result
    assert "freeComputeTime" in result

@patch('backend.cloud_price_fetcher_azure.requests.get')
def test_fetch_azure_price_iot(mock_get):
    """Test fetching Azure IoT Hub pricing"""
    
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "Items": [
            {
                "serviceName": "IoT Hub",
                "meterName": "S1 IoT Hub Unit",
                "unitOfMeasure": "1/Month",
                "unitPrice": 25.00,
                "armRegionName": "westeurope",
                "currencyCode": "USD",
                "productName": "IoT Hub"
            }
        ],
        "NextPageLink": None
    }
    mock_response.status_code = 200
    mock_get.return_value = mock_response
    
    result = fetch_azure_price("iot", "westeurope", debug=False)
    
    assert result is not None
    assert "pricing_tiers" in result

@patch('backend.cloud_price_fetcher_azure.requests.get')
def test_fetch_azure_price_with_pagination(mock_get):
    """Test handling of paginated Azure API responses"""
    
    # First page
    mock_response_1 = MagicMock()
    mock_response_1.json.return_value = {
        "Items": [
            {
                "serviceName": "Storage",
                "meterName": "Cool LRS Data Stored",
                "unitOfMeasure": "1 GB/Month",
                "unitPrice": 0.01,
                "armRegionName": "westeurope",
                "currencyCode": "USD",
                "productName": "Storage"
            }
        ],
        "NextPageLink": "https://next-page-url"
    }
    mock_response_1.status_code = 200
    
    # Second page
    mock_response_2 = MagicMock()
    mock_response_2.json.return_value = {
        "Items": [
            {
                "serviceName": "Storage",
                "meterName": "Cool Write Operations",
                "unitOfMeasure": "10K",
                "unitPrice": 0.10,
                "armRegionName": "westeurope",
                "currencyCode": "USD",
                "productName": "Storage"
            }
        ],
        "NextPageLink": None
    }
    mock_response_2.status_code = 200
    
    # Setup mock to return different responses
    mock_get.side_effect = [mock_response_1, mock_response_2]
    
    result = fetch_azure_price("storage_cool", "westeurope", debug=False)
    
    assert result is not None
    # Verify pagination was handled (both pages were fetched)
    assert mock_get.call_count == 2

@patch('backend.cloud_price_fetcher_azure._retail_query_items')
def test_fetch_azure_price_api_error(mock_query):
    """Test handling of API errors - mock at the query level to avoid exception"""
    
    # Mock failed query to return empty list (simulating error fallback)
    mock_query.return_value = []
    
    result = fetch_azure_price("functions", "westeurope", debug=False)
    
    # Should fall back to static defaults
    assert result is not None
    assert "freeRequests" in result
    assert result["freeRequests"] == 1_000_000
