"""Allowlisted Cloud Connection credential-file import tests."""

from __future__ import annotations

import json

import pytest

from src.models.cloud_connection import CloudConnection
from src.schemas.cloud_connection import CloudConnectionImportMetadata
from src.services.cloud_connection_import_service import parse_cloud_connection_import
from src.services.cloud_connection_service import CloudConnectionService


def _metadata(provider: str, **updates) -> CloudConnectionImportMetadata:
    value = {
        "provider": provider,
        "display_name": f"{provider.upper()} imported",
        "region": {
            "aws": "eu-central-1",
            "azure": "westeurope",
            "gcp": "europe-west1",
        }[provider],
    }
    if provider == "azure":
        value["target_scope_id"] = "subscription-1"
    elif provider == "gcp":
        value["target_scope_id"] = "deployment-project"
    value.update(updates)
    return CloudConnectionImportMetadata.model_validate(value)


def test_aws_console_csv_parses_one_credential_without_user_metadata():
    request = parse_cloud_connection_import(
        _metadata("aws", account_id="123456789012", sso_region="eu-west-1"),
        (
            b"User name,Access key ID,Secret access key\n"
            b"researcher,AKIAIOSFODNN7EXAMPLE,secret-value-with-enough-length\n"
        ),
    )

    assert request.aws.access_key_id == "AKIAIOSFODNN7EXAMPLE"
    assert request.aws.sso_region == "eu-west-1"
    assert request.cloud_scope == {
        "account_id": "123456789012",
        "region": "eu-central-1",
    }
    assert "researcher" not in request.model_dump_json()


def test_azure_cli_json_uses_explicit_subscription_scope():
    request = parse_cloud_connection_import(
        _metadata("azure"),
        json.dumps(
            {
                "appId": "client-1",
                "password": "client-secret-1",
                "tenant": "tenant-1",
            }
        ).encode(),
    )

    assert request.azure.subscription_id == "subscription-1"
    assert request.azure.client_id == "client-1"
    assert request.azure.tenant_id == "tenant-1"


def test_gcp_import_keeps_existing_target_project_separate_from_key_project():
    request = parse_cloud_connection_import(
        _metadata("gcp"),
        json.dumps(
            {
                "type": "service_account",
                "project_id": "identity-project",
                "private_key_id": "key-1",
                "private_key": "private-key-material",
                "client_email": "deployer@identity-project.iam.gserviceaccount.com",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        ).encode(),
    )

    assert request.gcp.project_id == "deployment-project"
    parsed_key = json.loads(request.gcp.service_account_json)
    assert parsed_key["project_id"] == "identity-project"


@pytest.mark.parametrize(
    ("provider", "content"),
    [
        (
            "aws",
            (
                b"Access key ID,Secret access key,Arbitrary command\n"
                b"AKIAIOSFODNN7EXAMPLE,secret-value-with-enough-length,rm\n"
            ),
        ),
        (
            "azure",
            b'{"appId":"a","password":"b","tenant":"c","script":"x"}',
        ),
        (
            "gcp",
            (
                b'{"type":"service_account","project_id":"p","client_email":"e",'
                b'"private_key":"k","executable":"x"}'
            ),
        ),
    ],
)
def test_import_rejects_non_allowlisted_fields(provider, content):
    with pytest.raises(ValueError, match="unsupported"):
        parse_cloud_connection_import(_metadata(provider), content)


def test_import_route_encrypts_parsed_secret_and_returns_only_summary(
    authenticated_client,
    db_session,
):
    client, headers = authenticated_client
    secret = "secret-value-with-enough-length"
    metadata = _metadata("aws", account_id="123456789012").model_dump_json()

    response = client.post(
        "/cloud-connections/import",
        data={"metadata": metadata},
        files={
            "file": (
                "credentials.csv",
                (
                    "User name,Access key ID,Secret access key\n"
                    f"researcher,AKIAIOSFODNN7EXAMPLE,{secret}\n"
                ).encode(),
                "text/csv",
            )
        },
        headers=headers,
    )

    assert response.status_code == 200
    assert secret not in response.text
    assert "researcher" not in response.text
    connection = db_session.query(CloudConnection).filter_by(
        id=response.json()["id"]
    ).one()
    payload = CloudConnectionService(db_session).decrypt_payload(
        connection,
        connection.user_id,
    )
    assert payload["aws_secret_access_key"] == secret
    assert set(payload) == {
        "aws_access_key_id",
        "aws_secret_access_key",
        "aws_region",
    }
