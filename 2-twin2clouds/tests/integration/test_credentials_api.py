from unittest.mock import patch

from fastapi.testclient import TestClient

from rest_api import app


client = TestClient(app)


def test_aws_config_credential_check_disabled_by_default():
    response = client.get("/permissions/verify/aws")

    assert response.status_code == 403
    assert response.json()["detail"]["error_code"] == "LOCAL_CREDENTIAL_FILE_CHECKS_DISABLED"


def test_gcp_config_credential_check_disabled_by_default():
    response = client.get("/permissions/verify/gcp")

    assert response.status_code == 403
    assert response.json()["detail"]["error_code"] == "LOCAL_CREDENTIAL_FILE_CHECKS_DISABLED"


def test_azure_config_credential_check_disabled_by_default():
    response = client.get("/permissions/verify/azure")

    assert response.status_code == 403
    assert response.json()["detail"]["error_code"] == "LOCAL_CREDENTIAL_FILE_CHECKS_DISABLED"


@patch("backend.credentials_checker.check_aws_credentials_from_config")
def test_aws_config_credential_check_requires_explicit_local_cloud_mode(mock_check, monkeypatch):
    monkeypatch.setenv("ENABLE_LOCAL_CREDENTIAL_FILE_CHECKS", "true")
    mock_check.return_value = {
        "provider": "aws",
        "status": "valid",
        "message": "ok",
        "config_present": True,
        "credentials_valid": True,
        "can_fetch_pricing": True,
        "identity": None,
        "required_permissions": [],
    }

    response = client.get("/permissions/verify/aws")

    assert response.status_code == 200
    assert response.json()["status"] == "valid"


@patch("backend.credentials_checker.check_aws_credentials")
def test_aws_body_credential_check_stays_available_without_local_file_mode(mock_check):
    mock_check.return_value = {
        "provider": "aws",
        "status": "valid",
        "message": "ok",
        "config_present": True,
        "credentials_valid": True,
        "can_fetch_pricing": True,
        "identity": None,
        "required_permissions": [],
    }

    response = client.post("/permissions/verify/aws", json={
        "aws_access_key_id": "AKIATEST",
        "aws_secret_access_key": "secret",
        "aws_region": "eu-central-1",
    })

    assert response.status_code == 200
    assert response.json()["status"] == "valid"
