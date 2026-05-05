import json
from types import SimpleNamespace

import pytest

from src.services.credential_resolution_service import CredentialResolutionService
from src.services.errors import CredentialResolutionFailed
from src.utils.crypto import encrypt, encrypt_scoped


USER_ID = "user-1"
TWIN_ID = "twin-1"


def _optimizer_config(**overrides):
    values = {
        "cheapest_l1": None,
        "cheapest_l2": None,
        "cheapest_l3_hot": None,
        "cheapest_l3_cool": None,
        "cheapest_l3_archive": None,
        "cheapest_l4": None,
        "cheapest_l5": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _configuration(**overrides):
    values = {
        "aws_cloud_connection_id": None,
        "aws_cloud_connection": None,
        "aws_access_key_id": None,
        "aws_secret_access_key": None,
        "aws_session_token": None,
        "aws_region": "eu-central-1",
        "aws_sso_region": None,
        "azure_cloud_connection_id": None,
        "azure_cloud_connection": None,
        "azure_subscription_id": None,
        "azure_tenant_id": None,
        "azure_client_id": None,
        "azure_client_secret": None,
        "azure_region": "westeurope",
        "azure_region_iothub": None,
        "azure_region_digital_twin": None,
        "gcp_cloud_connection_id": None,
        "gcp_cloud_connection": None,
        "gcp_project_id": None,
        "gcp_billing_account": None,
        "gcp_region": "europe-west1",
        "gcp_service_account_json": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _twin(configuration=None, optimizer_config=None):
    return SimpleNamespace(
        id=TWIN_ID,
        user_id=USER_ID,
        configuration=configuration,
        optimizer_config=optimizer_config,
    )


def _cloud_connection(connection_id, provider, payload):
    return SimpleNamespace(
        id=connection_id,
        provider=provider,
        encrypted_payload=encrypt_scoped(json.dumps(payload), USER_ID, connection_id),
    )


def test_cloud_connection_takes_precedence_over_legacy_credentials():
    payload = {
        "aws_access_key_id": "AKIAIOSFODNN7EXAMPLE",
        "aws_secret_access_key": "cloud-connection-secret",
        "aws_region": "eu-central-1",
    }
    legacy_secret = encrypt("legacy-secret", USER_ID, TWIN_ID)
    twin = _twin(
        configuration=_configuration(
            aws_cloud_connection_id="connection-aws",
            aws_cloud_connection=_cloud_connection("connection-aws", "aws", payload),
            aws_access_key_id=encrypt("legacy-key", USER_ID, TWIN_ID),
            aws_secret_access_key=legacy_secret,
        ),
        optimizer_config=_optimizer_config(cheapest_l1="AWS"),
    )

    resolved = CredentialResolutionService().resolve_deployment_credentials(twin, USER_ID)

    assert resolved.providers == ("aws",)
    assert resolved.sources == {"aws": "cloud_connection"}
    assert resolved.config_credentials["aws"] == payload
    assert "legacy-secret" not in str(resolved.config_credentials)


def test_gcp_deployment_credentials_use_service_account_file_boundary():
    service_account = {
        "type": "service_account",
        "project_id": "service-account-project",
        "client_email": "deployer@service-account-project.iam.gserviceaccount.com",
        "private_key": "-----BEGIN PRIVATE KEY-----\nsecret\n-----END PRIVATE KEY-----\n",
    }
    payload = {
        "gcp_region": "europe-west1",
        "gcp_credentials_file": json.dumps(service_account),
    }
    twin = _twin(
        configuration=_configuration(
            gcp_cloud_connection_id="connection-gcp",
            gcp_cloud_connection=_cloud_connection("connection-gcp", "gcp", payload),
        ),
        optimizer_config=_optimizer_config(cheapest_l1="GCP"),
    )

    resolved = CredentialResolutionService().resolve_deployment_credentials(twin, USER_ID)

    assert resolved.config_credentials["gcp"] == {
        "gcp_project_id": "service-account-project",
        "gcp_region": "europe-west1",
        "gcp_credentials_file": "gcp_credentials.json",
    }
    assert resolved.gcp_credentials_json == service_account
    assert "private_key" not in str(resolved.config_credentials)


def test_optimizer_selected_provider_without_credentials_fails_closed():
    twin = _twin(
        configuration=_configuration(
            aws_access_key_id=encrypt("AKIAIOSFODNN7EXAMPLE", USER_ID, TWIN_ID),
            aws_secret_access_key=encrypt("secret", USER_ID, TWIN_ID),
        ),
        optimizer_config=_optimizer_config(cheapest_l1="AWS", cheapest_l2="AZURE"),
    )

    with pytest.raises(CredentialResolutionFailed) as exc_info:
        CredentialResolutionService().resolve_deployment_credentials(twin, USER_ID)

    assert {
        "provider": "azure",
        "code": "MISSING_CREDENTIALS",
        "field": "credentials",
        "message": "No credentials configured for provider",
    } in exc_info.value.errors


def test_dangling_cloud_connection_fails_closed_with_secret_safe_error():
    twin = _twin(
        configuration=_configuration(
            aws_cloud_connection_id="missing-connection",
            aws_cloud_connection=None,
            aws_access_key_id=encrypt("legacy-key", USER_ID, TWIN_ID),
            aws_secret_access_key=encrypt("legacy-secret", USER_ID, TWIN_ID),
        ),
        optimizer_config=_optimizer_config(cheapest_l1="AWS"),
    )

    with pytest.raises(CredentialResolutionFailed) as exc_info:
        CredentialResolutionService().resolve_deployment_credentials(twin, USER_ID)

    assert exc_info.value.errors == [
        {
            "provider": "aws",
            "code": "DANGLING_CLOUD_CONNECTION",
            "field": "credentials",
            "message": "Configured Cloud Connection is no longer available",
            "source_id": "missing-connection",
        }
    ]
    assert "legacy-secret" not in str(exc_info.value.errors)


def test_invalid_gcp_service_account_json_returns_structured_error():
    payload = {
        "gcp_project_id": "demo-project",
        "gcp_region": "europe-west1",
        "gcp_credentials_file": "{not-json",
    }
    twin = _twin(
        configuration=_configuration(
            gcp_cloud_connection_id="connection-gcp",
            gcp_cloud_connection=_cloud_connection("connection-gcp", "gcp", payload),
        ),
        optimizer_config=_optimizer_config(cheapest_l1="GCP"),
    )

    with pytest.raises(CredentialResolutionFailed) as exc_info:
        CredentialResolutionService().resolve_deployment_credentials(twin, USER_ID)

    assert exc_info.value.errors == [
        {
            "provider": "gcp",
            "code": "INVALID_GCP_SERVICE_ACCOUNT_JSON",
            "field": "credentials",
            "message": "GCP service account JSON is invalid",
        }
    ]


def test_plaintext_azure_credentials_use_canonical_region_fallbacks():
    credentials = SimpleNamespace(
        subscription_id="sub-1",
        client_id="client-1",
        client_secret="secret-1",
        tenant_id="tenant-1",
        region="westeurope",
        region_iothub=None,
        region_digital_twin="northeurope",
    )

    resolved = CredentialResolutionService().resolve_plaintext_credentials("azure", credentials)

    assert resolved.source == "plaintext"
    assert resolved.optimizer_payload["azure_region"] == "westeurope"
    assert resolved.deployer_validation_payload["azure_region_iothub"] == "westeurope"
    assert resolved.deployer_validation_payload["azure_region_digital_twin"] == "northeurope"


def test_plaintext_gcp_credentials_extract_project_from_service_account():
    service_account = {
        "type": "service_account",
        "project_id": "service-account-project",
        "client_email": "deployer@service-account-project.iam.gserviceaccount.com",
        "private_key": "-----BEGIN PRIVATE KEY-----\nsecret\n-----END PRIVATE KEY-----\n",
    }
    credentials = SimpleNamespace(
        project_id=None,
        billing_account="012345-6789AB-CDEF01",
        service_account_json=json.dumps(service_account),
        region="europe-west1",
    )

    resolved = CredentialResolutionService().resolve_plaintext_credentials("gcp", credentials)

    assert resolved.optimizer_payload["gcp_project_id"] == "service-account-project"
    assert resolved.deployer_validation_payload["gcp_project_id"] == "service-account-project"
    assert "private_key" not in str(resolved.deployer_config_payload)


def test_plaintext_gcp_credentials_require_service_account_json():
    credentials = SimpleNamespace(
        project_id="demo-project",
        billing_account=None,
        service_account_json=None,
        region="europe-west1",
    )

    with pytest.raises(CredentialResolutionFailed) as exc_info:
        CredentialResolutionService().resolve_plaintext_credentials("gcp", credentials)

    assert {
        "provider": "gcp",
        "code": "MISSING_CREDENTIAL_FIELD",
        "field": "gcp_credentials_file",
        "message": "Missing required credential field: gcp_credentials_file",
    } in exc_info.value.errors
