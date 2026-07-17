from unittest.mock import MagicMock, patch

import pytest

from backend.fetch_data.calculate_up_to_date_pricing import (
    calculate_up_to_date_pricing,
    fetch_aws_data,
    fetch_azure_data,
    fetch_google_data,
    _require_transfer_catalog,
    _get_or_warn
)
from tests.unit.pricing.transfer_fixtures import canonical_transfer_fetch

@patch('backend.fetch_data.calculate_up_to_date_pricing.config_loader.load_credentials_file')
@patch('backend.fetch_data.calculate_up_to_date_pricing.config_loader.load_json_file')
@patch('backend.fetch_data.cloud_price_fetcher_aws.fetch_aws_price')
@patch('backend.fetch_data.cloud_price_fetcher_azure.fetch_azure_price')
@patch('backend.fetch_data.cloud_price_fetcher_google.fetch_gcp_price')
@patch('backend.fetch_data.calculate_up_to_date_pricing.billing_v1.CloudCatalogClient')
@patch('backend.fetch_data.calculate_up_to_date_pricing.load_gcp_credentials')
@patch(
    "backend.fetch_data.calculate_up_to_date_pricing."
    "PricingCatalogRefreshService.persist_refresh"
)
@patch(
    "backend.fetch_data.calculate_up_to_date_pricing."
    "get_pricing_catalog_repository"
)
def test_calculate_up_to_date_pricing_integration(
    mock_repository,
    mock_persist_refresh,
    mock_load_gcp_credentials,
    mock_cloud_catalog_client,
    mock_gcp_price,
    mock_azure_price,
    mock_aws_price,
    mock_load_json,
    mock_load_creds
):
    """Test the full orchestration flow"""

    # Mock GCP regions to avoid file loading issue
    # mock_gcp_regions.return_value = {"us-central1": "us-central1"}

    # Mock configuration
    mock_load_creds.return_value = {
        "aws": {
            "aws_access_key_id": "test-access-key",
            "aws_secret_access_key": "test-secret-key",
            "aws_region": "eu-central-1",
        },
        "azure": {},
        "gcp": {}
    }

    # Mock load_json_file
    def load_json_side_effect(path):
        if "service_mapping" in str(path):
            return {
                "iot": {"aws": "iotCore", "azure": "iotHub", "gcp": "iot"},
                "transfer": {
                    "aws": "AWSDataTransfer",
                    "azure": "Bandwidth",
                    "gcp": "ComputeEngine",
                },
            }
        elif "regions" in str(path):
            return {
                "eu-central-1": "EU (Frankfurt)",
                "us-central1": "us-central1",
            }
        else:
            return {
                "aws": {"services": {"iot": {"region": "us-east-1"}}},
                "azure": {"services": {"iot": {"region": "westeurope"}}},
                "gcp": {"services": {"iot": {"region": "us-central1"}}}
            }

    mock_load_json.side_effect = load_json_side_effect

    # Mock price fetcher responses
    mock_aws_price.side_effect = lambda **kwargs: (
        canonical_transfer_fetch("aws")
        if kwargs["service_name"] == "transfer"
        else {"pricePerMessage": 0.001}
    )
    mock_azure_price.side_effect = lambda **kwargs: (
        canonical_transfer_fetch("azure")
        if kwargs["service_name"] == "transfer"
        else {"pricePerMessage": 0.0009}
    )
    mock_gcp_price.side_effect = lambda **kwargs: (
        canonical_transfer_fetch("gcp")
        if kwargs["service_name"] == "transfer"
        else {"pricePerMessage": 0.0011}
    )
    mock_load_gcp_credentials.return_value = object()
    mock_cloud_catalog_client.return_value = object()
    mock_persist_refresh.side_effect = (
        {"provider": "aws", "status": "review_required"},
        {"provider": "azure", "status": "review_required"},
        {"provider": "gcp", "status": "review_required"},
    )

    # Execute for AWS
    with (
        patch(
            "backend.fetch_data.calculate_up_to_date_pricing.build_aws_session",
            return_value=object(),
        ),
        patch(
            "backend.fetch_data.calculate_up_to_date_pricing."
            "observe_aws_twinmaker_pricing_plan",
            return_value={"schema_version": "test-context.v1"},
        ),
    ):
        result_aws = calculate_up_to_date_pricing(
            "aws",
            additional_debug=False,
        )

    # Verify AWS
    assert result_aws == {"provider": "aws", "status": "review_required"}

    # Execute for Azure
    result_azure = calculate_up_to_date_pricing("azure", additional_debug=False)
    assert result_azure == {"provider": "azure", "status": "review_required"}

    # Execute for GCP
    result_gcp = calculate_up_to_date_pricing("gcp", additional_debug=False)
    assert result_gcp == {"provider": "gcp", "status": "review_required"}
    assert mock_persist_refresh.call_count == 3
    assert mock_repository.return_value.refresh_guard.call_count == 3

def test_get_or_warn_with_fetched_value():
    """Test _get_or_warn when value is successfully fetched"""

    fetched = {"pricePerMessage": 0.001}
    static = {"pricePerMessage": 0.002}

    result = _get_or_warn(
        "AWS",
        "iot",
        "iot",
        "pricePerMessage",
        fetched,
        0.002,
        static
    )

    # Should return fetched value
    assert result == 0.001

def test_get_or_warn_fallback_to_default():
    """Test _get_or_warn when fetching fails and falls back to default"""

    fetched = {}  # Empty - no value fetched
    static = {}  # Not in static either
    default = 0.003

    result = _get_or_warn(
        "AWS",
        "iot",
        "iot",
        "pricePerMessage",
        fetched,
        default,
        static
    )

    # Should return default value
    assert result == default

def test_get_or_warn_with_static_value():
    """Test _get_or_warn when value comes from static defaults"""

    fetched = {}
    static = {"pricePerMessage": 0.002}

    result = _get_or_warn(
        "AWS",
        "iot",
        "iot",
        "pricePerMessage",
        fetched,
        0.002,
        static
    )

    # Should return static value (same as default in this case)
    assert result == 0.002


def test_require_transfer_catalog_rejects_unknown_provider_fields():
    transfer = canonical_transfer_fetch("aws")
    transfer["egressPrice"] = 0.09

    with pytest.raises(ValueError, match="unsupported fields: egressPrice"):
        _require_transfer_catalog(
            "aws",
            "eu-central-1",
            {"transfer": transfer},
        )

@patch(
    "backend.fetch_data.calculate_up_to_date_pricing.PriceFetcherFactory.create"
)
def test_fetch_aws_data_structure(mock_factory):
    """Test that fetch_aws_data returns correct structure"""

    fetcher = MagicMock()
    fetcher.fetch_price.side_effect = lambda **kwargs: (
        canonical_transfer_fetch("aws")
        if kwargs["service_name"] == "transfer"
        else {"pricePerMessage": 0.001}
    )
    mock_factory.return_value = fetcher

    aws_creds = {
        "aws_access_key_id": "test-access-key",
        "aws_secret_access_key": "test-secret-key",
        "aws_region": "eu-central-1",
    }
    service_mapping = {
        "iot": {"aws": "iotCore"},
        "transfer": {"aws": "AWSDataTransfer"},
    }
    aws_services = {"eu-central-1": "EU (Frankfurt)"}

    result = fetch_aws_data(aws_creds, service_mapping, aws_services, additional_debug=False)

    # Verify structure
    assert "iotCore" in result or "iot" in result
    assert isinstance(result, dict)

@patch(
    "backend.fetch_data.calculate_up_to_date_pricing.PriceFetcherFactory.create"
)
def test_fetch_azure_data_structure(mock_factory):
    """Test that fetch_azure_data returns correct structure"""

    fetcher = MagicMock()
    fetcher.fetch_price.side_effect = lambda **kwargs: (
        canonical_transfer_fetch("azure")
        if kwargs["service_name"] == "transfer"
        else {"pricePerMessage": 0.001}
    )
    mock_factory.return_value = fetcher

    azure_creds = {}
    service_mapping = {
        "iot": {"azure": "iotHub"},
        "transfer": {"azure": "Bandwidth"},
    }
    azure_services = {"westeurope": "West Europe"}

    result = fetch_azure_data(azure_creds, service_mapping, azure_services, additional_debug=False)

    assert "iotHub" in result or "iot" in result
    assert isinstance(result, dict)

@patch(
    "backend.fetch_data.calculate_up_to_date_pricing.PriceFetcherFactory.create"
)
def test_fetch_google_data_structure(mock_factory):
    """Test that fetch_google_data returns correct structure"""

    fetcher = MagicMock()
    fetcher.fetch_price.side_effect = lambda **kwargs: (
        canonical_transfer_fetch("gcp")
        if kwargs["service_name"] == "transfer"
        else {"pricePerMessage": 0.001}
    )
    mock_factory.return_value = fetcher

    gcp_creds = {}
    service_mapping = {
        "iot": {"gcp": "iot"},
        "transfer": {"gcp": "ComputeEngine"},
    }
    gcp_services = {"europe-west1": "Belgium"}

    result = fetch_google_data(
        gcp_creds,
        service_mapping,
        gcp_services,
        additional_debug=False,
        billing_client=object(),
    )

    assert "iot" in result
    assert isinstance(result, dict)

@patch('backend.fetch_data.calculate_up_to_date_pricing.config_loader.load_credentials_file')
@patch('backend.fetch_data.calculate_up_to_date_pricing.config_loader.load_json_file')
@patch('backend.fetch_data.cloud_price_fetcher_aws.fetch_aws_price')
@patch(
    "backend.fetch_data.calculate_up_to_date_pricing."
    "PricingCatalogRefreshService.persist_refresh",
    return_value={"provider": "aws", "status": "review_required"},
)
@patch(
    "backend.fetch_data.calculate_up_to_date_pricing."
    "get_pricing_catalog_repository"
)
def test_calculate_up_to_date_pricing_handles_errors(
    mock_repository,
    mock_persist_refresh,
    mock_aws_price,
    mock_load_json,
    mock_load_creds
):
    """Test that orchestration handles fetcher errors gracefully"""

    mock_load_creds.return_value = {
        "aws": {
            "aws_access_key_id": "test-access-key",
            "aws_secret_access_key": "test-secret-key",
            "aws_region": "eu-central-1",
        }
    }

    def load_json_side_effect(path):
        if "service_mapping" in str(path):
            return {
                "iot": {"aws": "iotCore", "azure": "iotHub", "gcp": "iot"},
                "transfer": {"aws": "AWSDataTransfer"},
            }
        elif "regions" in str(path):
            return {
                "eu-central-1": "EU (Frankfurt)",
                "us-central1": "us-central1",
            }
        else:
            return {"aws": {"services": {"iot": {"region": "us-east-1"}}}}

    mock_load_json.side_effect = load_json_side_effect

    # Simulate fetcher error
    mock_aws_price.side_effect = Exception("API Error")

    # A required transfer catalog may not silently fall back after an API error.
    with (
        patch(
            "backend.fetch_data.calculate_up_to_date_pricing.build_aws_session",
            return_value=object(),
        ),
        patch(
            "backend.fetch_data.calculate_up_to_date_pricing."
            "observe_aws_twinmaker_pricing_plan",
            return_value={"schema_version": "test-context.v1"},
        ),
    ):
        with pytest.raises(ValueError, match="transfer pricing catalog"):
            calculate_up_to_date_pricing(
                "aws",
                additional_debug=False,
            )

    mock_persist_refresh.assert_not_called()
    mock_repository.return_value.refresh_guard.assert_called_once()
