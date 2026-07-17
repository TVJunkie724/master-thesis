import pytest
import json
from unittest.mock import patch, MagicMock
from backend.fetch_data.cloud_price_fetcher_aws import (
    TwinMakerPricingContractError,
    TwinMakerPricingFetchError,
    _extract_twinmaker_pricing,
    fetch_aws_price,
    _extract_prices_from_api_response,
    _extract_prices_with_evidence,
)
from backend.fetch_data.fetch_evidence import MatchStatus

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


def create_twinmaker_price_item(
    usage_type,
    price,
    *,
    begin_range="0",
    location="EU (Frankfurt)",
):
    return json.dumps(
        {
            "product": {
                "sku": f"sku-{usage_type}",
                "attributes": {
                    "usagetype": f"EUC1-{usage_type}",
                    "location": location,
                },
            },
            "terms": {
                "OnDemand": {
                    "term": {
                        "priceDimensions": {
                            "dimension": {
                                "description": f"{usage_type} provider description",
                                "beginRange": begin_range,
                                "endRange": "Inf",
                                "unit": "Unit",
                                "pricePerUnit": {"USD": str(price)},
                            }
                        }
                    }
                }
            },
        }
    )


def complete_twinmaker_price_list():
    rows = [
        create_twinmaker_price_item("IoTTwinMaker-Entities", 0.0525),
        create_twinmaker_price_item("IoTTwinMaker-Queries", 0.0000525),
        create_twinmaker_price_item(
            "IoTTwinMaker-UnifiedDataAccess",
            0.00000165,
        ),
    ]
    limits = {
        1: (3_800_000, 25_000_000, 231.0),
        2: (9_000_000, 60_000_000, 682.5),
        3: (14_300_000, 95_000_000, 1_155.0),
        4: (24_000_000, 160_000_000, 2_047.5),
    }
    for tier, (queries, api_calls, base_price) in limits.items():
        rows.extend(
            [
                create_twinmaker_price_item(
                    f"IoTTwinMaker-BaseTier{tier}-Entities",
                    base_price,
                ),
                create_twinmaker_price_item(
                    f"IoTTwinMaker-BaseTier{tier}-Queries",
                    0.0000525,
                    begin_range=str(queries),
                ),
                create_twinmaker_price_item(
                    f"IoTTwinMaker-BaseTier{tier}-UnifiedDataAccess",
                    0.00000165,
                    begin_range=str(api_calls),
                ),
            ]
        )
    return rows

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

def test_extract_prices_with_evidence_marks_distinct_paid_candidates_ambiguous():
    price_list = [
        create_mock_price_item("AWS Lambda total requests pricing", 0.0000002),
        create_mock_price_item("AWS Lambda total requests pricing alternate", 0.0000003),
    ]
    field_map = {"requestPrice": ["requests"]}

    evidence = _extract_prices_with_evidence(
        price_list,
        field_map,
        include_keywords=["lambda", "requests"],
        debug=False,
        service_name="functions",
    )

    assert evidence["requestPrice"].status == MatchStatus.AMBIGUOUS
    assert evidence["requestPrice"].selected_row is None
    assert evidence["requestPrice"].requires_review is True

def test_extract_prices_legacy_wrapper_omits_ambiguous_fields():
    price_list = [
        create_mock_price_item("AWS Lambda total requests pricing", 0.0000002),
        create_mock_price_item("AWS Lambda total requests pricing alternate", 0.0000003),
    ]
    field_map = {"requestPrice": ["requests"]}

    result = _extract_prices_from_api_response(
        price_list,
        field_map,
        include_keywords=["lambda", "requests"],
        debug=False,
    )

    assert "requestPrice" not in result

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

@patch('backend.fetch_data.cloud_price_fetcher_aws._get_pricing_client')
def test_fetch_aws_price_grafana(mock_get_client):
    """Test AWS Grafana leaves static fallback handling to the schema builder."""
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    
    region_map = {"us-east-1": "US East (N. Virginia)"}
    
    result = fetch_aws_price("grafana", "AmazonGrafana", "us-east-1", region_map, debug=False)
    
    assert result == {}

@patch('backend.fetch_data.cloud_price_fetcher_aws._get_pricing_client')
@patch('backend.fetch_data.cloud_price_fetcher_aws._fetch_api_products')
def test_fetch_aws_price_twinmaker(mock_fetch_products, mock_get_client):
    """TwinMaker fetches one exact regional catalog contract."""
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    mock_fetch_products.return_value = complete_twinmaker_price_list()
    
    region_map = {"eu-central-1": "EU (Frankfurt)"}
    
    result = fetch_aws_price(
        "twinmaker",
        "IOTTwinMaker",
        "eu-central-1",
        region_map,
        debug=False,
    )
    
    assert result["usageRates"] == {
        "entityPricePerMonth": 0.0525,
        "queryPrice": 0.0000525,
        "unifiedDataAccessApiCallPrice": 0.00000165,
    }
    assert [tier["tierId"] for tier in result["tieredBundle"]["tiers"]] == [
        "TIER_1",
        "TIER_2",
        "TIER_3",
        "TIER_4",
    ]
    assert result["tieredBundle"]["tiers"][0]["includedQueries"] == 3_800_000
    assert mock_fetch_products.call_count == 1


def test_twinmaker_extractor_rejects_missing_dimension():
    rows = complete_twinmaker_price_list()
    rows.pop()

    with pytest.raises(TwinMakerPricingContractError, match="incomplete"):
        _extract_twinmaker_pricing(rows, "EU (Frankfurt)")


def test_twinmaker_extractor_rejects_duplicate_positive_dimension():
    rows = complete_twinmaker_price_list()
    rows.append(
        create_twinmaker_price_item("IoTTwinMaker-Queries", 0.0000525)
    )

    with pytest.raises(TwinMakerPricingContractError, match="duplicated"):
        _extract_twinmaker_pricing(rows, "EU (Frankfurt)")


def test_twinmaker_extractor_rejects_other_region_matching_row():
    rows = complete_twinmaker_price_list()
    rows[0] = create_twinmaker_price_item(
        "IoTTwinMaker-Entities",
        0.0525,
        location="US East (N. Virginia)",
    )

    with pytest.raises(TwinMakerPricingContractError, match="different location"):
        _extract_twinmaker_pricing(rows, "EU (Frankfurt)")


def test_twinmaker_extractor_rejects_non_monotonic_included_usage():
    rows = complete_twinmaker_price_list()
    for index, row in enumerate(rows):
        if "BaseTier2-Queries" in row:
            rows[index] = create_twinmaker_price_item(
                "IoTTwinMaker-BaseTier2-Queries",
                0.0000525,
                begin_range="100",
            )
            break

    with pytest.raises(TwinMakerPricingContractError, match="increasing"):
        _extract_twinmaker_pricing(rows, "EU (Frankfurt)")


@patch("backend.fetch_data.cloud_price_fetcher_aws._get_pricing_client")
def test_twinmaker_fetch_surfaces_price_list_api_failure(mock_get_client):
    client = MagicMock()
    client.get_paginator.side_effect = RuntimeError("provider transport detail")
    mock_get_client.return_value = client

    with pytest.raises(TwinMakerPricingFetchError) as raised:
        fetch_aws_price(
            "twinmaker",
            "IOTTwinMaker",
            "eu-central-1",
            {"eu-central-1": "EU (Frankfurt)"},
        )

    assert raised.value.code == "AWS_TWINMAKER_CATALOG_FETCH_FAILED"
    assert "provider transport detail" not in raised.value.public_message
