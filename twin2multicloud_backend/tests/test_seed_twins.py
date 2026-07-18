import json

import pytest

from scripts import seed_twins
from src.models.cloud_connection import CloudConnection
from src.models.twin import DigitalTwin, TwinState
from src.models.twin_config import TwinConfiguration
from src.models.user import User
from src.services.deployment_service import (
    DeploymentPackageBuildFailed,
    build_deployment_package,
)


def _write_seed_files(tmp_path, *, include_gcp_service_account=True):
    credentials_path = tmp_path / "config_credentials.json"
    gcp_path = tmp_path / "gcp_credentials.json"
    service_account = {
        "type": "service_account",
        "project_id": "seed-project",
        "client_email": "seed@seed-project.iam.gserviceaccount.com",
        "private_key": "-----BEGIN PRIVATE KEY-----\\nexample\\n-----END PRIVATE KEY-----\\n",
    }
    credentials_path.write_text(json.dumps({
        "aws": {
            "aws_access_key_id": "AKIASEED",
            "aws_secret_access_key": "aws-secret",
            "aws_region": "eu-central-1",
        },
        "azure": {
            "azure_subscription_id": "subscription-id",
            "azure_client_id": "client-id",
            "azure_client_secret": "client-secret",
            "azure_tenant_id": "tenant-id",
            "azure_region": "westeurope",
        },
        "gcp": {
            "gcp_project_id": "seed-project",
            "gcp_billing_account": "000000-111111-222222",
            "gcp_region": "europe-west1",
        },
    }))
    if include_gcp_service_account:
        gcp_path.write_text(json.dumps(service_account))
    return credentials_path, gcp_path


@pytest.mark.asyncio
async def test_seed_twins_use_cloud_connections_without_legacy_secret_duplication(
    db_session,
    monkeypatch,
    tmp_path,
):
    credentials_path, gcp_path = _write_seed_files(tmp_path)

    async def fake_validate_provider(provider, creds):
        return True, "Valid"

    monkeypatch.setattr(seed_twins, "SessionLocal", lambda: db_session)
    monkeypatch.setattr(seed_twins, "_validate_provider", fake_validate_provider)
    monkeypatch.setattr(seed_twins.settings, "SEED_CREDENTIALS_FILE", str(credentials_path))
    monkeypatch.setattr(seed_twins.settings, "SEED_GCP_CREDENTIALS_FILE", str(gcp_path))
    monkeypatch.setattr(seed_twins.settings, "SEED_LEGACY_TWIN_CREDENTIALS", False)

    await seed_twins.seed_if_needed()

    seed_user = db_session.query(User).filter_by(email=seed_twins.SEED_USER_EMAIL).one()
    connections = db_session.query(CloudConnection).filter_by(user_id=seed_user.id).all()
    assert {connection.provider for connection in connections} == {"aws", "azure", "gcp"}
    assert all(connection.validation_status == "valid" for connection in connections)

    connection_ids = {connection.provider: connection.id for connection in connections}
    twins = db_session.query(DigitalTwin).filter_by(user_id=seed_user.id).all()
    assert len(twins) == len(seed_twins.TWIN_DEFINITIONS)
    assert {twin.state for twin in twins} == {TwinState.CONFIGURED}

    configs = db_session.query(TwinConfiguration).all()
    assert len(configs) == len(seed_twins.TWIN_DEFINITIONS)
    for config in configs:
        assert config.aws_cloud_connection_id == connection_ids["aws"]
        assert config.azure_cloud_connection_id == connection_ids["azure"]
        assert config.gcp_cloud_connection_id == connection_ids["gcp"]

        assert config.aws_access_key_id is None
        assert config.aws_secret_access_key is None
        assert config.aws_session_token is None
        assert config.azure_subscription_id is None
        assert config.azure_client_id is None
        assert config.azure_client_secret is None
        assert config.azure_tenant_id is None
        assert config.gcp_billing_account is None
        assert config.gcp_service_account_json is None

    for twin in twins:
        with pytest.raises(
            DeploymentPackageBuildFailed,
            match="optimizer run must be selected",
        ):
            build_deployment_package(twin, seed_user.id)


@pytest.mark.asyncio
async def test_seed_twins_do_not_create_invalid_gcp_connection_without_service_account(
    db_session,
    monkeypatch,
    tmp_path,
):
    credentials_path, gcp_path = _write_seed_files(tmp_path, include_gcp_service_account=False)

    async def fake_validate_provider(provider, creds):
        return True, "Valid"

    monkeypatch.setattr(seed_twins, "SessionLocal", lambda: db_session)
    monkeypatch.setattr(seed_twins, "_validate_provider", fake_validate_provider)
    monkeypatch.setattr(seed_twins.settings, "SEED_CREDENTIALS_FILE", str(credentials_path))
    monkeypatch.setattr(seed_twins.settings, "SEED_GCP_CREDENTIALS_FILE", str(gcp_path))
    monkeypatch.setattr(seed_twins.settings, "SEED_LEGACY_TWIN_CREDENTIALS", False)

    await seed_twins.seed_if_needed()

    seed_user = db_session.query(User).filter_by(email=seed_twins.SEED_USER_EMAIL).one()
    connections = db_session.query(CloudConnection).filter_by(user_id=seed_user.id).all()
    assert {connection.provider for connection in connections} == {"aws", "azure"}

    configs = db_session.query(TwinConfiguration).all()
    assert configs
    assert all(config.gcp_cloud_connection_id is None for config in configs)
    assert all(config.gcp_service_account_json is None for config in configs)


@pytest.mark.asyncio
async def test_seed_twins_reject_legacy_per_twin_credential_duplication(
    db_session,
    monkeypatch,
    tmp_path,
):
    credentials_path, gcp_path = _write_seed_files(tmp_path)

    async def fake_validate_provider(provider, creds):
        return True, "Valid"

    monkeypatch.setattr(seed_twins, "SessionLocal", lambda: db_session)
    monkeypatch.setattr(seed_twins, "_validate_provider", fake_validate_provider)
    monkeypatch.setattr(seed_twins.settings, "SEED_CREDENTIALS_FILE", str(credentials_path))
    monkeypatch.setattr(seed_twins.settings, "SEED_GCP_CREDENTIALS_FILE", str(gcp_path))
    monkeypatch.setattr(seed_twins.settings, "SEED_LEGACY_TWIN_CREDENTIALS", True)

    await seed_twins.seed_if_needed()

    assert db_session.query(DigitalTwin).count() == 0
    assert db_session.query(TwinConfiguration).count() == 0
