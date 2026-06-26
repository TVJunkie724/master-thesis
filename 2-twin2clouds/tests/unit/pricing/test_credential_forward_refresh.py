from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError as PydanticValidationError

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


def test_credential_request_accepts_management_api_gcp_context_fields():
    request = CredentialRequest(
        gcp_service_account_json='{"type":"service_account"}',
        gcp_project_id="thesis-demo",
        gcp_billing_account="012345-6789AB-CDEF01",
        gcp_region="europe-west1",
    )

    assert request.model_dump() == {
        "aws_access_key_id": None,
        "aws_secret_access_key": None,
        "aws_session_token": None,
        "aws_region": "eu-central-1",
        "gcp_service_account_json": '{"type":"service_account"}',
        "gcp_project_id": "thesis-demo",
        "gcp_billing_account": "012345-6789AB-CDEF01",
        "gcp_region": "europe-west1",
    }


def test_credential_request_rejects_unknown_fields():
    with pytest.raises(PydanticValidationError):
        CredentialRequest(unexpected_secret="should-not-be-silently-ignored")


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


@patch(
    "backend.fetch_data.calculate_up_to_date_pricing."
    "calculate_up_to_date_pricing_with_credentials"
)
def test_fetch_pricing_with_credentials_redacts_secret_value_errors(mock_refresh, caplog):
    mock_refresh.side_effect = ValueError("provider echoed secret-key in validation")

    with caplog.at_level("WARNING", logger="digital_twin"):
        response = client.post(
            "/fetch_pricing_with_credentials/aws",
            json={
                "aws_access_key_id": "access-key",
                "aws_secret_access_key": "secret-key",
                "aws_region": "eu-central-1",
            },
        )

    assert response.status_code == 400
    assert response.json()["detail"]["message"] == "provider echoed [REDACTED] in validation"
    assert "secret-key" not in caplog.text


@patch(
    "backend.fetch_data.calculate_up_to_date_pricing."
    "calculate_up_to_date_pricing_with_credentials"
)
def test_fetch_pricing_with_credentials_preserves_gcp_context_fields(mock_refresh):
    mock_refresh.return_value = {"pubsub": {"price": 1.0}}

    response = client.post(
        "/fetch_pricing_with_credentials/gcp",
        json={
            "gcp_service_account_json": '{"type":"service_account"}',
            "gcp_project_id": "thesis-demo",
            "gcp_billing_account": "012345-6789AB-CDEF01",
            "gcp_region": "europe-west1",
        },
    )

    assert response.status_code == 200
    assert mock_refresh.call_args.args[0] == "gcp"
    assert mock_refresh.call_args.args[1] == {
        "aws_access_key_id": None,
        "aws_secret_access_key": None,
        "aws_session_token": None,
        "aws_region": "eu-central-1",
        "gcp_service_account_json": '{"type":"service_account"}',
        "gcp_project_id": "thesis-demo",
        "gcp_billing_account": "012345-6789AB-CDEF01",
        "gcp_region": "europe-west1",
    }


def test_fetch_pricing_with_credentials_rejects_unknown_fields():
    response = client.post(
        "/fetch_pricing_with_credentials/aws",
        json={"aws_access_key_id": "access-key", "unexpected": "value"},
    )

    assert response.status_code == 422


@patch(
    "backend.fetch_data.calculate_up_to_date_pricing."
    "calculate_up_to_date_pricing_with_credentials"
)
def test_stream_fetch_pricing_preserves_gcp_context_fields(mock_refresh):
    mock_refresh.return_value = {"pubsub": {"price": 1.0}}

    with client.stream(
        "POST",
        "/stream/fetch_pricing/gcp",
        json={
            "gcp_service_account_json": '{"type":"service_account"}',
            "gcp_project_id": "thesis-demo",
            "gcp_billing_account": "012345-6789AB-CDEF01",
            "gcp_region": "europe-west1",
        },
    ) as response:
        body = "\n".join(response.iter_lines())

    assert response.status_code == 200
    assert "complete" in body
    assert mock_refresh.call_args.args[0] == "gcp"
    assert mock_refresh.call_args.args[1]["gcp_project_id"] == "thesis-demo"
    assert mock_refresh.call_args.args[1]["gcp_billing_account"] == "012345-6789AB-CDEF01"


@patch(
    "backend.fetch_data.calculate_up_to_date_pricing."
    "calculate_up_to_date_pricing_with_credentials"
)
def test_stream_fetch_pricing_does_not_echo_secret_exception_text(mock_refresh, caplog):
    mock_refresh.side_effect = Exception("provider echoed secret-key in an error")

    with caplog.at_level("ERROR", logger="digital_twin"):
        with client.stream(
            "POST",
            "/stream/fetch_pricing/aws",
            json={
                "aws_access_key_id": "access-key",
                "aws_secret_access_key": "secret-key",
                "aws_region": "eu-central-1",
            },
        ) as response:
            body = "\n".join(response.iter_lines())

    assert response.status_code == 200
    assert "event: error" in body
    assert "AWS pricing fetch failed" in body
    assert "secret-key" not in body
    assert "secret-key" not in caplog.text


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
