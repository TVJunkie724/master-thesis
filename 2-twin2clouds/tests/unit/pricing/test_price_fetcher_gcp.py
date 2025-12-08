import pytest
from unittest.mock import MagicMock, patch
from backend.fetch_data.cloud_price_fetcher_google import fetch_gcp_price, STATIC_DEFAULTS_GCP

# Helper to create mock SKU
def create_mock_sku(service_regions, description, unit_description, unit_price_currency):
    sku = MagicMock()
    sku.service_regions = service_regions
    sku.description = description
    
    pricing_info = MagicMock()
    pricing_expression = MagicMock()
    pricing_expression.usage_unit_description = unit_description
    
    rate = MagicMock()
    rate.unit_price.units = int(unit_price_currency)
    rate.unit_price.nanos = int((unit_price_currency - int(unit_price_currency)) * 1_000_000_000)
    
    pricing_expression.tiered_rates = [rate]
    pricing_info.pricing_expression = pricing_expression
    
    sku.pricing_info = [pricing_info]
    return sku

@patch('backend.fetch_data.cloud_price_fetcher_google.billing_v1.CloudCatalogClient')
def test_fetch_gcp_price_iot(mock_client_cls):
    """Test fetching GCP IoT (Pub/Sub) pricing"""
    mock_client = mock_client_cls.return_value
    
    # Mock list_services
    service_mock = MagicMock()
    service_mock.display_name = "Cloud Pub/Sub"
    service_mock.service_id = "pubsub-id"
    mock_client.list_services.return_value = [service_mock]
    
    # Mock list_skus
    sku = create_mock_sku(["us-central1"], "Message Delivery", "gibibyte", 0.0000004)
    mock_client.list_skus.return_value = [sku]
    
    region_map = {"us-central1": "us-central1"}
    
    result = fetch_gcp_price(mock_client, "iot", "us-central1", region_map, debug=False)
    
    assert result is not None
    assert "pricePerGiB" in result
    assert result["pricePerGiB"] == 0.0000004

@patch('backend.fetch_data.cloud_price_fetcher_google.billing_v1.CloudCatalogClient')
def test_fetch_gcp_price_functions(mock_client_cls):
    """Test fetching GCP Functions pricing"""
    mock_client = mock_client_cls.return_value
    
    service_mock = MagicMock()
    service_mock.display_name = "Cloud Run Functions"
    service_mock.service_id = "functions-id"
    mock_client.list_services.return_value = [service_mock]
    
    sku1 = create_mock_sku(["us-central1"], "Invocations", "1/1000000 count", 0.0000004)
    sku2 = create_mock_sku(["us-central1"], "Memory", "gibibyte second", 0.0000025)
    mock_client.list_skus.return_value = [sku1, sku2]
    
    region_map = {"us-central1": "us-central1"}
    
    result = fetch_gcp_price(mock_client, "functions", "us-central1", region_map, debug=False)
    
    assert result is not None
    assert "requestPrice" in result
    assert "durationPrice" in result

@patch('backend.fetch_data.cloud_price_fetcher_google.billing_v1.CloudCatalogClient')
def test_fetch_gcp_price_storage_hot(mock_client_cls):
    """Test fetching GCP Firestore (hot storage) pricing"""
    mock_client = mock_client_cls.return_value
    
    service_mock = MagicMock()
    service_mock.display_name = "Cloud Firestore"
    mock_client.list_services.return_value = [service_mock]
    
    sku = create_mock_sku(["us-central1"], "Storage", "gibibyte", 0.18)
    mock_client.list_skus.return_value = [sku]
    
    region_map = {"us-central1": "us-central1"}
    
    result = fetch_gcp_price(mock_client, "storage_hot", "us-central1", region_map, debug=False)
    
    assert result is not None
    assert "storagePrice" in result
    assert result["storagePrice"] == 0.18

@patch('backend.fetch_data.cloud_price_fetcher_google.billing_v1.CloudCatalogClient')
def test_fetch_gcp_price_unknown_service(mock_client_cls):
    """Test fetching pricing for an unknown service"""
    mock_client = mock_client_cls.return_value
    
    region_map = {"us-central1": "us-central1"}
    
    result = fetch_gcp_price(mock_client, "unknown_service", "us-central1", region_map, debug=False)
    
    assert result == {}

def test_static_defaults_structure():
    """Test that static defaults have the expected structure"""
    
    expected_services = [
        "transfer", "iot", "functions", "storage_hot", 
        "storage_cool", "storage_archive", "twinmaker", "grafana"
    ]
    
    for service in expected_services:
        assert service in STATIC_DEFAULTS_GCP
        assert isinstance(STATIC_DEFAULTS_GCP[service], dict)
