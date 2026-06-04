"""Tests for normalized provider preflight endpoints."""

from fastapi.testclient import TestClient
from unittest.mock import patch

import rest_api

client = TestClient(rest_api.app)


AWS_PAYLOAD = {
    "aws_access_key_id": "AKIATESTTEST",
    "aws_secret_access_key": "secretkey123456789",
    "aws_region": "eu-central-1",
    "permission_set_version": "thesis-demo-v1",
}

AZURE_PAYLOAD = {
    "azure_subscription_id": "sub-123",
    "azure_tenant_id": "tenant-123",
    "azure_client_id": "client-123",
    "azure_client_secret": "secret-value-123456",
    "azure_region": "westeurope",
    "azure_region_iothub": "westeurope",
    "azure_region_digital_twin": "westeurope",
    "permission_set_version": "thesis-demo-v1",
}

GCP_PAYLOAD = {
    "gcp_project_id": "demo-project",
    "gcp_credentials_file": '{"type":"service_account","client_email":"deployer@demo-project.iam.gserviceaccount.com","private_key":"super-secret-key"}',
    "gcp_region": "europe-west1",
    "permission_set_version": "thesis-demo-v1",
}


@patch("src.api.credentials.check_aws_credentials")
def test_aws_preflight_passes_when_checker_is_valid(mock_check):
    mock_check.return_value = {
        "status": "valid",
        "message": "All required permissions are present.",
        "summary": {"total_required": 1, "valid": 1, "missing": 0},
        "by_service": {},
    }

    response = client.post("/permissions/preflight/aws", json=AWS_PAYLOAD)

    assert response.status_code == 200
    data = response.json()
    assert data["provider"] == "aws"
    assert data["expected_permission_set_version"] == "thesis-demo-v1"
    assert data["supplied_permission_set_version"] == "thesis-demo-v1"
    assert data["permission_set_status"] == "matched"
    assert data["ready"] is True
    assert data["status"] == "passed"
    assert data["checks"][0]["code"] == "AWS_READY"


@patch("src.api.credentials.check_aws_credentials")
def test_preflight_fails_missing_permission_set_version(mock_check):
    mock_check.return_value = {
        "status": "valid",
        "message": "All required permissions are present.",
        "summary": {"total_required": 1, "valid": 1, "missing": 0},
        "by_service": {},
    }
    payload = dict(AWS_PAYLOAD)
    payload.pop("permission_set_version")

    response = client.post("/permissions/preflight/aws", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["ready"] is False
    assert data["permission_set_status"] == "missing"
    assert data["checks"][0]["code"] == "OUTDATED_PERMISSION_SET"
    assert data["checks"][0]["details"] == {
        "expected_permission_set_version": "thesis-demo-v1",
        "supplied_permission_set_version": None,
        "permission_set_status": "missing",
    }


@patch("src.api.credentials.check_aws_credentials")
def test_aws_preflight_maps_missing_permissions_and_redacts_secret_echo(mock_check):
    mock_check.return_value = {
        "status": "partial",
        "message": "Some permissions are missing for secretkey123456789",
        "by_service": {
            "lambda": {
                "missing": ["lambda:CreateFunction"],
                "valid": [],
            }
        },
        "summary": {"total_required": 2, "valid": 1, "missing": 1},
    }

    response = client.post("/permissions/preflight/aws", json=AWS_PAYLOAD)

    assert response.status_code == 200
    data = response.json()
    assert data["ready"] is False
    assert data["checks"][0]["code"] == "MISSING_PERMISSIONS"
    assert data["checks"][0]["permissions"] == ["lambda:CreateFunction"]
    assert "secretkey123456789" not in response.text
    assert "[REDACTED]" in response.text


@patch("src.api.credentials.check_aws_credentials")
def test_aws_preflight_maps_self_check_failure(mock_check):
    mock_check.return_value = {
        "status": "check_failed",
        "message": "Cannot determine permissions",
        "missing_check_permission": "iam:ListUserPolicies",
        "by_service": {},
        "summary": {"total_required": 0, "valid": 0, "missing": 0},
    }

    response = client.post("/permissions/preflight/aws", json=AWS_PAYLOAD)

    assert response.status_code == 200
    check = response.json()["checks"][0]
    assert check["code"] == "SELF_CHECK_PERMISSION_MISSING"
    assert check["permissions"] == ["iam:ListUserPolicies"]


@patch("src.api.credentials.check_azure_credentials")
def test_azure_preflight_keeps_expiring_secret_as_warning(mock_check):
    mock_check.return_value = {
        "status": "valid",
        "message": "All required permissions are present.",
        "sp_credential_expiration": {
            "status": "expiring_soon",
            "message": "Azure Service Principal credentials expire in 10 days.",
            "days_until_expiration": 10,
        },
        "by_layer": {},
        "summary": {"total_layers": 1, "valid_layers": 1, "partial_layers": 0, "invalid_layers": 0},
    }

    response = client.post("/permissions/preflight/azure", json=AZURE_PAYLOAD)

    assert response.status_code == 200
    data = response.json()
    assert data["ready"] is True
    assert [check["code"] for check in data["checks"]] == ["AZURE_READY", "CREDENTIAL_EXPIRING_SOON"]
    assert data["checks"][1]["status"] == "warning"


@patch("src.api.credentials.check_azure_credentials")
def test_azure_preflight_maps_missing_actions(mock_check):
    mock_check.return_value = {
        "status": "partial",
        "message": "Some layers have missing permissions.",
        "by_layer": {
            "layer_1": {
                "status": "partial",
                "missing_actions": ["Microsoft.Authorization/roleAssignments/write"],
            }
        },
        "summary": {"total_layers": 1, "valid_layers": 0, "partial_layers": 1, "invalid_layers": 0},
    }

    response = client.post("/permissions/preflight/azure", json=AZURE_PAYLOAD)

    assert response.status_code == 200
    data = response.json()
    assert data["ready"] is False
    assert data["checks"][0]["code"] == "MISSING_PERMISSIONS"
    assert data["checks"][0]["permissions"] == ["Microsoft.Authorization/roleAssignments/write"]


@patch("src.api.credentials.check_gcp_credentials")
def test_gcp_preflight_maps_missing_apis(mock_check):
    mock_check.return_value = {
        "status": "partial",
        "message": "Some required APIs are not enabled.",
        "api_status": {
            "status": "checked",
            "by_layer": {
                "layer_2": {
                    "status": "partial",
                    "missing_apis": ["cloudfunctions.googleapis.com"],
                }
            },
        },
        "required_roles": [],
    }

    response = client.post("/permissions/preflight/gcp", json=GCP_PAYLOAD)

    assert response.status_code == 200
    data = response.json()
    assert data["ready"] is False
    assert data["checks"][0]["code"] == "MISSING_APIS"
    assert data["checks"][0]["apis"] == ["cloudfunctions.googleapis.com"]


@patch("src.api.credentials.check_gcp_credentials")
def test_gcp_preflight_maps_billing_failure(mock_check):
    mock_check.return_value = {
        "status": "invalid",
        "message": "GCP project does not have billing enabled.",
        "billing_status": {
            "status": "checked",
            "billing_enabled": False,
        },
        "api_status": None,
        "required_roles": [],
    }

    response = client.post("/permissions/preflight/gcp", json=GCP_PAYLOAD)

    assert response.status_code == 200
    data = response.json()
    assert data["ready"] is False
    assert data["checks"][0]["code"] == "BILLING_NOT_ENABLED"


@patch("src.api.credentials.check_gcp_credentials")
def test_gcp_preflight_maps_inactive_project(mock_check):
    mock_check.return_value = {
        "status": "invalid",
        "message": "GCP project is 'DELETE_REQUESTED'.",
        "project_access": {
            "status": "accessible",
            "state": "DELETE_REQUESTED",
        },
        "api_status": None,
        "required_roles": [],
    }

    response = client.post("/permissions/preflight/gcp", json=GCP_PAYLOAD)

    assert response.status_code == 200
    data = response.json()
    assert data["ready"] is False
    assert data["checks"][0]["code"] == "PROJECT_NOT_ACTIVE"
    assert data["checks"][0]["details"] == {"state": "DELETE_REQUESTED"}


@patch("src.api.credentials.check_gcp_credentials")
def test_gcp_preflight_redacts_nested_service_account_secret_echo(mock_check):
    mock_check.return_value = {
        "status": "invalid",
        "message": "bad private key super-secret-key",
        "api_status": None,
        "required_roles": [],
    }

    response = client.post("/permissions/preflight/gcp", json=GCP_PAYLOAD)

    assert response.status_code == 200
    assert "super-secret-key" not in response.text
    assert "[REDACTED]" in response.text
