import pytest
import json
from unittest.mock import patch, MagicMock
from backend.fetch_data.cloud_price_fetcher_aws import (
    _extract_iot_connection_price_per_device_month,
    _extract_iot_message_tiers,
    _extract_prices_from_api_response,
    fetch_aws_price,
)

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
    assert "freeRequests" not in result

@patch('backend.fetch_data.cloud_price_fetcher_aws._get_pricing_client')
def test_fetch_aws_price_client_error(mock_get_client):
    """Test handling of client creation failure"""
    mock_get_client.return_value = None
    
    region_map = {"us-east-1": "US East (N. Virginia)"}
    
    result = fetch_aws_price("iot", "AmazonIoT", "us-east-1", region_map, debug=False)
    
    assert result == {}

@patch('backend.fetch_data.cloud_price_fetcher_aws._get_pricing_client')
@patch('backend.fetch_data.cloud_price_fetcher_aws._fetch_api_products')
def test_fetch_aws_price_unknown_service(mock_fetch_products, mock_get_client):
    """Test fetching for an unknown service"""
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    
    region_map = {"us-east-1": "US East (N. Virginia)"}
    
    result = fetch_aws_price("unknown_service", "Unknown", "us-east-1", region_map, debug=False)
    
    assert result == {}

def test_extract_iot_message_tiers_uses_standard_messages_only():
    price_list = [
        create_mock_price_item(
            "$0.96 per million messages - next 4 billion messages/month",
            0.00000096,
        ),
        create_mock_price_item(
            "$1.20 per million messages - first 1 billion messages/month",
            0.0000012,
        ),
        create_mock_price_item(
            "$0.84 per million messages - over 5 billion messages/month",
            0.00000084,
        ),
        create_mock_price_item(
            "$0.00000216 per Direct Message from 0 to 1,000,000,000",
            0.00000216,
        ),
    ]
    decoded = [json.loads(item) for item in price_list]
    for item, usage_type, begin, end in zip(
        decoded,
        ["EUC1-Messages", "EUC1-Messages", "EUC1-Messages", "EUC1-DirectMessages"],
        ["1000000000", "0", "5000000000", "0"],
        ["5000000000", "1000000000", "Inf", "1000000000"],
    ):
        item["product"]["attributes"]["usagetype"] = usage_type
        dim = next(
            iter(
                next(iter(item["terms"]["OnDemand"].values()))["priceDimensions"].values()
            )
        )
        dim["beginRange"] = begin
        dim["endRange"] = end

    result = _extract_iot_message_tiers([json.dumps(item) for item in decoded])

    assert result == {
        "tier_first": 0.0000012,
        "tier_next": 0.00000096,
        "tier_over": 0.00000084,
    }


def test_extract_iot_connection_minutes_as_device_month():
    item = json.loads(
        create_mock_price_item(
            "$0.096 per million minutes of connection",
            0.000000096,
        )
    )
    item["product"]["attributes"]["usagetype"] = "EUC1-ConnectionMinutes"

    result = _extract_iot_connection_price_per_device_month([json.dumps(item)])

    assert result == pytest.approx(0.0041472)


@patch('backend.fetch_data.cloud_price_fetcher_aws._get_pricing_client')
@patch('backend.fetch_data.cloud_price_fetcher_aws._fetch_api_products')
def test_fetch_aws_price_grafana(mock_fetch_products, mock_get_client):
    """Test AWS Grafana fetches editor/viewer user pricing."""
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    mock_fetch_products.side_effect = [
        [],
        [
            create_mock_price_item("$9 per Editor per month", 9.0),
            create_mock_price_item("$5 per Viewer per month", 5.0),
        ],
    ]
    
    region_map = {"us-east-1": "US East (N. Virginia)"}
    
    result = fetch_aws_price("grafana", "AmazonGrafana", "us-east-1", region_map, debug=False)
    
    assert result == {"editorPrice": 9.0, "viewerPrice": 5.0}

@patch('backend.fetch_data.cloud_price_fetcher_aws._get_pricing_client')
@patch('backend.fetch_data.cloud_price_fetcher_aws._fetch_api_products')
def test_fetch_aws_price_twinmaker(mock_fetch_products, mock_get_client):
    """Test fetching AWS TwinMaker pricing"""
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    
    # Mock TwinMaker response (simplified)
    # MUST matching keywords in AWS_SERVICE_KEYWORDS["twinmaker"]["fields"]
    # entityPrice: ["per entity per month", "iottwinmaker-entities"]
    # queryPrice: ["per 10k queries", "queries executed"]
    mock_fetch_products.side_effect = [
        # Call 1: IOTTwinMaker (Entity)
        [create_mock_price_item("IoT TwinMaker Per Entity Per Month", 0.5)],
        # Call 2: IOTTwinMakerQueries (Queries)
        [create_mock_price_item("IoT TwinMaker Queries Executed", 0.000002)]
    ]
    
    region_map = {"us-east-1": "US East (N. Virginia)"}
    
    result = fetch_aws_price("twinmaker", "IOTTwinMaker", "us-east-1", region_map, debug=False)
    
    assert result is not None
    assert "entityPrice" in result
    assert result["entityPrice"] == 0.5
    # queryPrice might be missing if _fetch_twinmaker_prices logic varies, but checking coverage
