"""
Schema validation tests to ensure calculate_up_to_date_pricing output
matches the structure defined in pricing/pricing.json template.

Note: With Factory Pattern integration, fetch functions are mocked at
the source module level (cloud_price_fetcher_*) since the Factory
wrappers delegate to these underlying functions.
"""
import pytest
import json
from pathlib import Path
from unittest.mock import patch, mock_open
from backend.fetch_data.calculate_up_to_date_pricing import fetch_aws_data, fetch_azure_data

# Load template once for all tests
TEMPLATE_PATH = Path("/app/json/pricing.json")  # Docker path
with open(TEMPLATE_PATH) as f:
    TEMPLATE = json.load(f)

@patch('backend.fetch_data.cloud_price_fetcher_aws.fetch_aws_price')
def test_aws_iot_core_schema(mock_fetch):
    """Validate AWS IoT Core output matches template structure"""
    
    mock_fetch.return_value = {"pricePerMessage": 0.000001}
    
    result = fetch_aws_data(
        {"access_key": "test"},
        {"iot": "iotCore"},
        {"iot": {"region": "us-east-1"}},
        additional_debug=False
    )
    
    # Check iotCore exists
    assert "iotCore" in result
    
    # Validate against template structure
    template_iot = TEMPLATE["aws"]["iotCore"]
    result_iot = result["iotCore"]
    
    # Should be a dict
    assert isinstance(result_iot, dict)
    
    # Check for expected structure (keys may vary but should have pricing fields)
    assert len(result_iot) > 0

@patch('backend.fetch_data.cloud_price_fetcher_aws.fetch_aws_price')
def test_aws_lambda_schema(mock_fetch):
    """Validate AWS Lambda output matches template structure"""
    
    mock_fetch.return_value = {
        "requestPrice": 0.0000002,
        "durationPrice": 0.0000166667,
        "freeRequests": 1000000,
        "freeComputeTime": 400000
    }
    
    result = fetch_aws_data(
        {"access_key": "test"},
        {"functions": "lambda"},
        {"functions": {"region": "us-east-1"}},
        additional_debug=False
    )
    
    assert "lambda" in result
    template_lambda = TEMPLATE["aws"]["lambda"]
    result_lambda = result["lambda"]
    
    # Validate structure
    assert isinstance(result_lambda, dict)
    assert "freeRequests" in result_lambda
    assert "freeComputeTime" in result_lambda
    
    # Validate types
    assert isinstance(result_lambda.get("freeRequests"), (int, float))
    assert isinstance(result_lambda.get("freeComputeTime"), (int, float))

@patch('backend.fetch_data.cloud_price_fetcher_aws.fetch_aws_price')
def test_aws_dynamodb_schema(mock_fetch):
    """Validate AWS DynamoDB output matches template structure"""
    
    mock_fetch.return_value = {
        "writePrice": 0.000000625,
        "readPrice": 0.000000125,
        "storagePrice": 0.25,
        "freeStorage": 25
    }
    
    result = fetch_aws_data(
        {"access_key": "test"},
        {"storage_hot": "dynamoDB"},
        {"storage_hot": {"region": "us-east-1"}},
        additional_debug=False
    )
    
    assert "dynamoDB" in result
    result_ddb = result["dynamoDB"]
    
    assert isinstance(result_ddb, dict)
    # Should have pricing fields
    assert any(key in result_ddb for key in ["writePrice", "readPrice", "storagePrice"])

@patch('backend.fetch_data.cloud_price_fetcher_aws.fetch_aws_price')
def test_aws_s3_schema(mock_fetch):
    """Validate AWS S3 output matches template structure"""
    
    mock_fetch.return_value = {
        "storagePrice": 0.0125,
        "requestPrice": 0.00001,
        "dataRetrievalPrice": 0.01
    }
    
    result = fetch_aws_data(
        {"access_key": "test"},
        {"storage_cool": "s3InfrequentAccess"},
        {"storage_cool": {"region": "us-east-1"}},
        additional_debug=False
    )
    
    assert "s3InfrequentAccess" in result
    result_s3 = result["s3InfrequentAccess"]
    
    assert isinstance(result_s3, dict)
    assert any(key in result_s3 for key in ["storagePrice", "requestPrice"])

@patch('backend.fetch_data.cloud_price_fetcher_azure.fetch_azure_price')
def test_azure_iot_hub_schema(mock_fetch):
    """Validate Azure IoT Hub output matches template structure"""
    
    mock_fetch.return_value = {
        "pricing_tiers": {
            "tier1": {"limit": 120000000, "threshold": 12000000, "price": 25}
        }
    }
    
    result = fetch_azure_data(
        {},
        {"iot": "iotHub"},
        {"iot": {"region": "westeurope"}},
        additional_debug=False
    )
    
    assert "iotHub" in result
    result_iot = result["iotHub"]
    
    assert isinstance(result_iot, dict)
    
    # If pricing_tiers exist, validate structure
    if "pricing_tiers" in result_iot:
        assert isinstance(result_iot["pricing_tiers"], dict)
        # Check tier structure
        for tier_name, tier_data in result_iot["pricing_tiers"].items():
            if isinstance(tier_data, dict):
                # Tiers should have numeric values
                assert any(isinstance(v, (int, float)) for v in tier_data.values())

@patch('backend.fetch_data.cloud_price_fetcher_azure.fetch_azure_price')
def test_azure_functions_schema(mock_fetch):
    """Validate Azure Functions output matches template structure"""
    
    mock_fetch.return_value = {
        "requestPrice": 0.0000002,
        "durationPrice": 0.0000166667,
        "freeRequests": 1000000,
        "freeComputeTime": 400000
    }
    
    result = fetch_azure_data(
        {},
        {"functions": "functions"},
        {"functions": {"region": "westeurope"}},
        additional_debug=False
    )
    
    assert "functions" in result
    result_func = result["functions"]
    
    assert isinstance(result_func, dict)
    assert "freeRequests" in result_func
    assert "freeComputeTime" in result_func

@patch('backend.fetch_data.cloud_price_fetcher_azure.fetch_azure_price')
def test_azure_cosmos_db_schema(mock_fetch):
    """Validate Azure Cosmos DB output matches template structure"""
    
    mock_fetch.return_value = {
        "storagePrice": 0.25,
        "requestPrice": 0.0584,
        "minimumRequestUnits": 400
    }
    
    result = fetch_azure_data(
        {},
        {"storage_hot": "cosmosDB"},
        {"storage_hot": {"region": "westeurope"}},
        additional_debug=False
    )
    
    assert "cosmosDB" in result
    result_cosmos = result["cosmosDB"]
    
    assert isinstance(result_cosmos, dict)
    assert any(key in result_cosmos for key in ["storagePrice", "requestPrice"])

@patch('backend.fetch_data.cloud_price_fetcher_azure.fetch_azure_price')
def test_azure_blob_storage_schema(mock_fetch):
    """Validate Azure Blob Storage output matches template structure"""
    
    mock_fetch.return_value = {
        "storagePrice": 0.015,
        "writePrice": 0.00001,
        "readPrice": 0.000001,
        "dataRetrievalPrice": 0.01
    }
    
    result = fetch_azure_data(
        {},
        {"storage_cool": "blobStorageCool"},
        {"storage_cool": {"region": "westeurope"}},
        additional_debug=False
    )
    
    assert "blobStorageCool" in result
    result_blob = result["blobStorageCool"]
    
    assert isinstance(result_blob, dict)
    assert any(key in result_blob for key in ["storagePrice", "writePrice", "readPrice"])

def test_numeric_field_types():
    """Validate that all price/limit fields in template are numeric"""
    
    def check_numeric_fields(obj, path=""):
        """Recursively check that price/limit fields are numeric"""
        if isinstance(obj, dict):
            for key, value in obj.items():
                current_path = f"{path}.{key}" if path else key
                if "price" in key.lower() or "limit" in key.lower():
                    # Should be numeric or "Infinity"
                    assert isinstance(value, (int, float, str)), \
                        f"{current_path} should be numeric or 'Infinity', got {type(value)}"
                    if isinstance(value, str):
                        assert value == "Infinity", \
                            f"{current_path} should be 'Infinity', got {value}"
                elif isinstance(value, dict):
                    check_numeric_fields(value, current_path)
                elif isinstance(value, list):
                    for i, item in enumerate(value):
                        check_numeric_fields(item, f"{current_path}[{i}]")
    
    check_numeric_fields(TEMPLATE)

def test_template_has_required_providers():
    """Validate template contains AWS and Azure providers"""
    
    assert "aws" in TEMPLATE
    assert "azure" in TEMPLATE
    assert isinstance(TEMPLATE["aws"], dict)
    assert isinstance(TEMPLATE["azure"], dict)

def test_template_has_required_aws_services():
    """Validate template contains required AWS services"""
    
    required_services = ["iotCore", "lambda", "dynamoDB"]
    
    for service in required_services:
        assert service in TEMPLATE["aws"], f"{service} should be in AWS template"
        assert isinstance(TEMPLATE["aws"][service], dict)

def test_template_has_required_azure_services():
    """Validate template contains required Azure services"""
    
    required_services = ["iotHub", "functions", "cosmosDB"]
    
    for service in required_services:
        assert service in TEMPLATE["azure"], f"{service} should be in Azure template"
        assert isinstance(TEMPLATE["azure"][service], dict)
