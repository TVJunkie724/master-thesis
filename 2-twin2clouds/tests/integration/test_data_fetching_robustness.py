
import pytest
import json
from unittest.mock import MagicMock, patch
from backend.fetch_data import cloud_price_fetcher_aws, cloud_price_fetcher_azure, cloud_price_fetcher_google

# -----------------------------------------------------------------------------
# 1. API Schema Changes (Drift)
# -----------------------------------------------------------------------------

def test_aws_fetch_api_schema_change():
    """Test AWS parser behavior when API returns unexpected keys/structure."""
    # Mock boto3 client via _get_pricing_client to avoid credential errors
    with patch("backend.fetch_data.cloud_price_fetcher_aws._get_pricing_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        
        # Scenario: AWS changes "terms" structure
        # Normal structure: PriceList[i] -> terms -> OnDemand -> ... -> priceDimensions -> pricePerUnit -> USD
        # Broken structure: "terms" is missing
        
        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator
        
        broken_product = json.dumps({
            "product": {"sku": "123"},
            "serviceCode": "AmazonEC2",
            # Missing "terms"
        })
        
        mock_paginator.paginate.return_value = [{"PriceList": [broken_product]}]
        
        # Test fetching 'storage_hot' (DynamoDB usually, but logic allows any service code)
        # Using a valid service to trigger extraction
        prices = cloud_price_fetcher_aws.fetch_aws_price(
            "storage_hot", "AmazonDynamoDB", "eu-central-1", {"eu-central-1": "EU (Frankfurt)"}
        )
        
        # Should gracefully return raw fetched prices only, not crash.
        # Fallback defaults are applied by the canonical schema builder.
        assert isinstance(prices, dict)
        assert prices == {}

def test_aws_fetch_zero_results_for_filters():
    """Test behavior when API returns valid but empty list (e.g. filter mismatch)."""
    with patch("backend.fetch_data.cloud_price_fetcher_aws._get_pricing_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        
        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [] # Empty pages
        
        prices = cloud_price_fetcher_aws.fetch_aws_price(
            "storage_hot", "AmazonDynamoDB", "eu-central-1", {"eu-central-1": "EU (Frankfurt)"}
        )
        
        # Static defaults are applied by the canonical schema builder, not the fetcher.
        assert prices == {}

# -----------------------------------------------------------------------------
# 2. Unexpected Data Types
# -----------------------------------------------------------------------------

def test_aws_fetch_string_prices():
    """Test parser when price is a string number (JSON allows both, sometimes API drifts)."""
    with patch("backend.fetch_data.cloud_price_fetcher_aws._get_pricing_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        
        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator
        
        # Description containing keywords: "DDB-ReadUnits" matching "read request"???
        # AWS keywords: "per million read request"
        
        product_json = json.dumps({
            "version": "1.0",
            "terms": {
                "OnDemand": {
                    "imp1": {
                        "priceDimensions": {
                            "dim1": {
                                "description": "$0.25 per million read request units", # Matched keyword
                                "pricePerUnit": {"USD": "0.25"} # String!
                            }
                        }
                    }
                }
            }
        })
        
        mock_paginator.paginate.return_value = [{"PriceList": [product_json]}]
        
        prices = cloud_price_fetcher_aws.fetch_aws_price(
            "storage_hot", "AmazonDynamoDB", "eu-central-1", {"eu-central-1": "EU (Frankfurt)"}
        )
        
        # The parser does `float(dim.get("pricePerUnit", {}).get("USD", 0))`
        # float("0.25") works.
        assert prices.get("readPrice") == 0.25
