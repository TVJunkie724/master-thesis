import pytest
from unittest.mock import patch, MagicMock
from backend.fetch_data.cloud_price_fetcher_azure import fetch_azure_price, _find_best_match

def test_find_best_match_basic():
    """Test finding a matching row with meter and unit keywords"""
    
    rows = [
        {
            "productName": "Functions",
            "meterName": "Total Executions",
            "unitOfMeasure": "1 Million",
            "unitPrice": 0.20,
            "currencyCode": "USD",
            "skuName": "Standard"
        },
        {
            "productName": "Functions",
            "meterName": "Data Stored",
            "unitOfMeasure": "1 GB/Month",
            "unitPrice": 0.02,
            "currencyCode": "USD",
            "skuName": "Standard"
        }
    ]
    
    result_row = _find_best_match(
        rows,
        meter_kw="Total Executions",
        unit_kw="1 Million",
        include_kw=[],
        debug=False
    )
    
    assert result_row is not None
    assert result_row["unitPrice"] == 0.20

def test_find_best_match_case_insensitive():
    """Test that matching is case-insensitive"""
    
    rows = [
        {
            "productName": "Azure Cosmos DB",
            "meterName": "Standard Data Stored",
            "unitOfMeasure": "1 GB/Month",
            "unitPrice": 0.25,
            "currencyCode": "USD",
            "skuName": "Standard"
        }
    ]
    
    result_row = _find_best_match(
        rows,
        meter_kw="Standard Data Stored",
        unit_kw="1 GB/Month",
        include_kw=[],
        debug=False
    )
    
    assert result_row is not None
    assert result_row["unitPrice"] == 0.25

def test_find_best_match_no_match():
    """Test behavior when no match is found"""
    
    rows = [
        {
            "productName": "Something",
            "meterName": "Something Else",
            "unitOfMeasure": "1 Unit",
            "unitPrice": 99.99,
        }
    ]
    
    result = _find_best_match(
        rows,
        meter_kw="not found",
        unit_kw="not found",
        include_kw=[],
        debug=False
    )
    
    assert result is None

@patch('backend.fetch_data.cloud_price_fetcher_azure._retail_query_items')
def test_fetch_azure_price_functions(mock_query):
    """Test fetching Azure Functions pricing"""
    import logging
    from backend.logger import logger
    logger.setLevel(logging.DEBUG)
    for h in logger.handlers:
        h.setLevel(logging.DEBUG)
    
    # Mock response rows
    mock_query.return_value = [
        {
            "serviceName": "Functions",
            "meterName": "Standard Total Executions",
            "unitOfMeasure": "1 Million",
            "unitPrice": 0.20,
            "armRegionName": "westeurope",
            "productName": "Azure Functions"
        },
        {
            "serviceName": "Functions",
            "meterName": "Always Ready Execution Time",
            "unitOfMeasure": "1 GB-s",
            "unitPrice": 0.000016,
            "armRegionName": "westeurope",
            "productName": "Azure Functions"
        }
    ]
    
    region_map = {"westeurope": "westeurope"}
    service_mapping = {"functions": {"azure": "Functions"}}
    
    result = fetch_azure_price("functions", "westeurope", region_map, service_mapping, debug=False)
    
    assert result is not None
    assert "requestPrice" in result
    assert "durationPrice" in result
    # Defaults
    assert "freeRequests" in result

@patch('backend.fetch_data.cloud_price_fetcher_azure._retail_query_items')
def test_fetch_azure_price_iot(mock_query):
    """Test fetching Azure IoT Hub pricing"""
    
    mock_query.return_value = [
        {
            "serviceName": "IoT Hub",
            "meterName": "S1 IoT Hub Unit",
            "unitOfMeasure": "1/Month",
            "unitPrice": 25.00,
            "skuName": "S1",
            "productName": "IoT Hub"
        }
    ]
    
    region_map = {"westeurope": "westeurope"}
    service_mapping = {"iot": {"azure": "IoT Hub"}}
    
    result = fetch_azure_price("iot", "westeurope", region_map, service_mapping, debug=False)
    
    assert result is not None
    assert "pricing_tiers" in result
    assert "tier1" in result["pricing_tiers"]
    assert result["pricing_tiers"]["tier1"]["price"] == 25.00

@patch('backend.fetch_data.cloud_price_fetcher_azure._retail_query_items')
def test_fetch_azure_price_api_error(mock_query):
    """Test handling of API errors (empty return)"""
    
    mock_query.return_value = []
    
    region_map = {"westeurope": "westeurope"}
    service_mapping = {"functions": {"azure": "Functions"}}
    
    result = fetch_azure_price("functions", "westeurope", region_map, service_mapping, debug=False)
    
    # Should fall back to static defaults
    assert result is not None
    assert "freeRequests" in result
    assert result["freeRequests"] == 1_000_000
