from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.fetch_data.calculate_up_to_date_pricing import (
    build_aws_pricing_client_credentials,
    calculate_up_to_date_pricing,
    calculate_up_to_date_pricing_with_credentials,
    fetch_aws_data,
)
from api.pricing import CredentialRequest
from rest_api import app


client = TestClient(app)


def test_aws_pricing_client_credentials_include_session_token():
    credentials = build_aws_pricing_client_credentials(
        {
            "aws_access_key_id": "access-key",
            "aws_secret_access_key": "secret-key",
            "aws_session_token": "session-token",
            "aws_region": "eu-central-1",
        }
    )

    assert credentials == {
        "aws_access_key_id": "access-key",
        "aws_secret_access_key": "secret-key",
        "aws_session_token": "session-token",
        "region_name": "us-east-1",
    }


def test_credential_request_accepts_aws_session_token():
    request = CredentialRequest(
        aws_access_key_id="access-key",
        aws_secret_access_key="secret-key",
        aws_session_token="session-token",
    )

    assert request.model_dump()["aws_session_token"] == "session-token"


def test_fetch_pricing_with_credentials_invalid_provider_returns_structured_error():
    response = client.post("/fetch_pricing_with_credentials/invalid", json={})

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["error_code"] == "INVALID_PROVIDER"
    assert detail["http_status"] == 400


@patch(
    "backend.fetch_data.calculate_up_to_date_pricing."
    "calculate_up_to_date_pricing_with_credentials"
)
def test_fetch_pricing_with_credentials_value_error_returns_structured_400(
    mock_refresh,
):
    mock_refresh.side_effect = ValueError("Missing AWS credential fields: aws_secret_access_key")

    response = client.post(
        "/fetch_pricing_with_credentials/aws",
        json={"aws_access_key_id": "access-key"},
    )

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["error_code"] == "PRICING_CREDENTIAL_REQUEST_INVALID"
    assert detail["http_status"] == 400
    assert "aws_secret_access_key" in detail["message"]


@patch("backend.pricing_utils.validate_pricing_schema")
@patch("pathlib.Path.write_text")
@patch("backend.fetch_data.calculate_up_to_date_pricing.fetch_aws_data")
@patch("backend.fetch_data.calculate_up_to_date_pricing.config_loader.load_json_file")
@patch("backend.fetch_data.calculate_up_to_date_pricing.config_loader.load_service_mapping")
@patch("backend.fetch_data.calculate_up_to_date_pricing.config_loader.load_aws_credentials")
def test_aws_credential_forward_refresh_passes_request_credentials_without_local_load(
    mock_load_aws_credentials,
    mock_load_service_mapping,
    mock_load_json_file,
    mock_fetch_aws_data,
    mock_write_text,
    mock_validate_schema,
):
    mock_load_service_mapping.return_value = {"iot": {"aws": "IoTCore"}}
    mock_load_json_file.return_value = {"eu-central-1": "EU (Frankfurt)"}
    mock_fetch_aws_data.return_value = {"iot": {"price": 1.0}}
    mock_validate_schema.return_value = {"status": "valid", "missing_keys": []}

    calculate_up_to_date_pricing_with_credentials(
        "aws",
        {
            "aws_access_key_id": "access-key",
            "aws_secret_access_key": "secret-key",
            "aws_session_token": "session-token",
            "aws_region": "eu-central-1",
        },
    )

    mock_load_aws_credentials.assert_not_called()
    mock_fetch_aws_data.assert_called_once()
    assert mock_fetch_aws_data.call_args.kwargs["aws_client_credentials"] == {
        "aws_access_key_id": "access-key",
        "aws_secret_access_key": "secret-key",
        "aws_session_token": "session-token",
        "region_name": "us-east-1",
    }
    assert mock_fetch_aws_data.call_args.args[0] == {"aws_region": "eu-central-1"}


@patch("backend.fetch_data.calculate_up_to_date_pricing.PriceFetcherFactory.create")
@patch("backend.fetch_data.calculate_up_to_date_pricing.config_loader.load_aws_credentials")
def test_fetch_aws_data_uses_explicit_client_credentials_without_local_fallback(
    mock_load_aws_credentials,
    mock_factory_create,
):
    fetcher = MagicMock()
    fetcher.fetch_price.return_value = {}
    mock_factory_create.return_value = fetcher

    fetch_aws_data(
        {"aws_region": "eu-central-1"},
        {"iot": {"aws": "IoTCore"}},
        {"eu-central-1": "EU (Frankfurt)"},
        aws_client_credentials={
            "aws_access_key_id": "access-key",
            "aws_secret_access_key": "secret-key",
            "region_name": "us-east-1",
        },
    )

    mock_load_aws_credentials.assert_not_called()
    assert fetcher.fetch_price.call_args.kwargs["aws_credentials"] == {
        "aws_access_key_id": "access-key",
        "aws_secret_access_key": "secret-key",
        "region_name": "us-east-1",
    }


@patch("backend.pricing_utils.validate_pricing_schema")
@patch("pathlib.Path.write_text")
@patch("backend.fetch_data.calculate_up_to_date_pricing.fetch_azure_data")
@patch("backend.fetch_data.calculate_up_to_date_pricing.config_loader.load_json_file")
@patch("backend.fetch_data.calculate_up_to_date_pricing.config_loader.load_service_mapping")
@patch("backend.fetch_data.calculate_up_to_date_pricing.config_loader.load_credentials_file")
def test_azure_public_pricing_refresh_does_not_load_credentials_file(
    mock_load_credentials_file,
    mock_load_service_mapping,
    mock_load_json_file,
    mock_fetch_azure_data,
    mock_write_text,
    mock_validate_schema,
):
    mock_load_service_mapping.return_value = {"iot": {"azure": "IoTHub"}}
    mock_load_json_file.return_value = {"westeurope": "West Europe"}
    mock_fetch_azure_data.return_value = {"iot": {"price": 1.0}}
    mock_validate_schema.return_value = {"status": "valid", "missing_keys": []}

    calculate_up_to_date_pricing("azure")

    mock_load_credentials_file.assert_not_called()
    mock_fetch_azure_data.assert_called_once_with(
        {},
        {"iot": {"azure": "IoTHub"}},
        {"westeurope": "West Europe"},
        False,
    )


@patch("backend.fetch_data.calculate_up_to_date_pricing.load_gcp_credentials")
@patch("backend.fetch_data.calculate_up_to_date_pricing.config_loader.load_json_file")
@patch("backend.fetch_data.calculate_up_to_date_pricing.config_loader.load_service_mapping")
def test_gcp_credential_forward_invalid_json_does_not_fallback_to_local_credentials(
    mock_load_service_mapping,
    mock_load_json_file,
    mock_load_gcp_credentials,
):
    mock_load_service_mapping.return_value = {"iot": {"gcp": "pubsub"}}
    mock_load_json_file.return_value = {"europe-west1": "europe-west1"}

    with pytest.raises(ValueError, match="Invalid GCP service account JSON"):
        calculate_up_to_date_pricing_with_credentials(
            "gcp",
            {"gcp_service_account_json": "not-json", "gcp_region": "europe-west1"},
        )

    mock_load_gcp_credentials.assert_not_called()
