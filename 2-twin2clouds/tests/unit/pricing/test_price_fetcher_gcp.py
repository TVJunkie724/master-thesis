from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from backend.fetch_data.cloud_price_fetcher_google import (
    fetch_gcp_price,
    STATIC_DEFAULTS_GCP,
    _select_gcp_sku_with_evidence,
)
from backend.fetch_data.fetch_evidence import MatchStatus

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


def create_transfer_sku(
    *,
    sku_id="5B70-B2D6-B4FC",
    description="Network Internet Data Transfer Out from EMEA to EMEA",
    unit_description="gibibyte",
    tiers=((0, 0.12), (1024, 0.11), (10240, 0.085)),
    currency_code="USD",
    usage_unit="GiBy",
    base_unit_conversion_factor=1_073_741_824,
    display_quantity=1,
    aggregation_level=1,
    aggregation_interval=2,
    aggregation_count=1,
):
    rates = []
    for start, price in tiers:
        units = int(price)
        nanos = round((price - units) * 1_000_000_000)
        rates.append(
            SimpleNamespace(
                start_usage_amount=start,
                unit_price=SimpleNamespace(
                    currency_code=currency_code,
                    units=units,
                    nanos=nanos,
                ),
            )
        )
    expression = SimpleNamespace(
        usage_unit=usage_unit,
        usage_unit_description=unit_description,
        base_unit="By",
        base_unit_description="byte",
        base_unit_conversion_factor=base_unit_conversion_factor,
        display_quantity=display_quantity,
        aggregation_info=SimpleNamespace(
            aggregation_level=aggregation_level,
            aggregation_interval=aggregation_interval,
            aggregation_count=aggregation_count,
        ),
        tiered_rates=rates,
    )
    return SimpleNamespace(
        sku_id=sku_id,
        name=f"services/6F81-5844-456A/skus/{sku_id}",
        description=description,
        category=SimpleNamespace(
            resource_family="Network",
            resource_group="PremiumInternetEgress",
            usage_type="OnDemand",
        ),
        service_regions=["europe-west1"],
        pricing_info=[SimpleNamespace(pricing_expression=expression)],
    )

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
        "iot", "functions", "storage_hot",
        "storage_cool", "storage_archive", "twinmaker", "grafana",
        "scheduler",
    ]
    
    for service in expected_services:
        assert service in STATIC_DEFAULTS_GCP
        assert isinstance(STATIC_DEFAULTS_GCP[service], dict)

    assert STATIC_DEFAULTS_GCP["scheduler"]["jobPrice"] == 0.10


def test_fetch_gcp_transfer_builds_exact_canonical_gib_catalog():
    client = MagicMock()
    service = SimpleNamespace(
        display_name="Compute Engine",
        service_id="6F81-5844-456A",
    )
    client.list_services.return_value = [service]
    client.list_skus.return_value = [create_transfer_sku()]

    result = fetch_gcp_price(
        client,
        "transfer",
        "europe-west1",
        {"europe-west1": "Belgium"},
    )

    assert "egressPrice" not in result
    assert result["billing_unit"] == "gib"
    assert result["bytes_per_billing_unit"] == 1_073_741_824
    assert result["network_tier"] == "premium"
    assert [
        (
            tier["start_quantity"],
            tier["end_quantity"],
            tier["unit_price"],
        )
        for tier in result["pricing_tiers"]
    ] == [
        (0, 1, 0),
        (1, 1024, 0.12),
        (1024, 10240, 0.11),
        (10240, None, 0.085),
    ]
    assert result["__evidence__"]["evidence_id"] == result["evidence_id"]
    selected = result["__intent_evidence__"]["selected_rows"]
    assert {row["skuId"] for row in selected} == {"5B70-B2D6-B4FC"}
    assert selected[0]["pricing_expression"]["aggregationInfo"] == {
        "level": "ACCOUNT",
        "interval": "MONTHLY",
        "count": 1,
    }


@pytest.mark.parametrize(
    "sku, expected",
    [
        (
            create_transfer_sku(sku_id="CHANGED-SKU"),
            "incomplete or requires review",
        ),
        (
            create_transfer_sku(unit_description="gigabyte"),
            "incomplete or requires review",
        ),
        (
            create_transfer_sku(tiers=((0, 0.12), (0, 0.11))),
            "incomplete or requires review",
        ),
        (
            create_transfer_sku(base_unit_conversion_factor=1_000_000_000),
            "incomplete or requires review",
        ),
        (
            create_transfer_sku(aggregation_level=2),
            "incomplete or requires review",
        ),
        (
            create_transfer_sku(aggregation_interval=1),
            "incomplete or requires review",
        ),
    ],
)
def test_fetch_gcp_transfer_fails_closed_for_catalog_drift(sku, expected):
    client = MagicMock()
    client.list_services.return_value = [
        SimpleNamespace(
            display_name="Compute Engine",
            service_id="6F81-5844-456A",
        )
    ]
    client.list_skus.return_value = [sku]

    with pytest.raises(ValueError, match=expected):
        fetch_gcp_price(
            client,
            "transfer",
            "europe-west1",
            {"europe-west1": "Belgium"},
        )


def test_fetch_gcp_transfer_rejects_missing_provider_currency():
    client = MagicMock()
    client.list_services.return_value = [
        SimpleNamespace(
            display_name="Compute Engine",
            service_id="6F81-5844-456A",
        )
    ]
    client.list_skus.return_value = [create_transfer_sku(currency_code=None)]

    with pytest.raises(ValueError, match="currencyCode is missing"):
        fetch_gcp_price(
            client,
            "transfer",
            "europe-west1",
            {"europe-west1": "Belgium"},
        )


def test_select_gcp_sku_with_evidence_selected():
    sku = create_mock_sku(["us-central1"], "Message Delivery", "gibibyte", 0.0000004)
    meter_conf = {
        "desc_keywords": ["Message Delivery"],
        "unit_keywords": ["gibibyte"],
    }

    evidence = _select_gcp_sku_with_evidence(
        [sku],
        meter_conf,
        "us-central1",
        service_name="iot",
        field_key="pricePerGiB",
    )

    assert evidence.status == MatchStatus.SELECTED
    assert evidence.selected_price == 0.0000004
    assert evidence.normalized_price == 0.0000004
    assert evidence.requires_review is False

def test_select_gcp_sku_with_evidence_ambiguous_distinct_prices():
    sku_a = create_mock_sku(["us-central1"], "Message Delivery", "gibibyte", 0.0000004)
    sku_b = create_mock_sku(["us-central1"], "Message Delivery Premium", "gibibyte", 0.0000006)
    meter_conf = {
        "desc_keywords": ["Message Delivery"],
        "unit_keywords": ["gibibyte"],
    }

    evidence = _select_gcp_sku_with_evidence(
        [sku_a, sku_b],
        meter_conf,
        "us-central1",
        service_name="iot",
        field_key="pricePerGiB",
    )

    assert evidence.status == MatchStatus.AMBIGUOUS
    assert evidence.selected_row is None
    assert evidence.requires_review is True
    assert "distinct prices" in evidence.reason
