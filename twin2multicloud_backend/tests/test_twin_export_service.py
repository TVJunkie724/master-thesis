"""Tests for redacted twin export service."""

from __future__ import annotations

import json
import zipfile

import pytest

from src.models.deployer_config import DeployerConfiguration
from src.models.optimizer_config import OptimizerConfiguration
from src.models.twin import DigitalTwin, TwinState
from src.models.twin_config import TwinConfiguration
from src.models.user import User
from src.services.service_errors import EntityNotFoundError
from src.services.twin_export_service import REDACTED, TwinExportService


def _create_user(db) -> User:
    user = User(email="twin-export-service@example.test", name="Twin Export", auth_provider="google")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _create_twin(db, user: User, state: TwinState = TwinState.CONFIGURED) -> DigitalTwin:
    twin = DigitalTwin(name="Export Twin", user_id=user.id, state=state)
    db.add(twin)
    db.commit()
    db.refresh(twin)
    return twin


def test_export_twin_redacts_credentials_and_preserves_config_shape(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user)
    db_session.add(OptimizerConfiguration(twin_id=twin.id, cheapest_l1="AWS", cheapest_l2="AZURE"))
    db_session.add(
        DeployerConfiguration(
            twin_id=twin.id,
            deployer_digital_twin_name="export-project",
            config_iot_devices_json='{"devices": []}',
            payloads_json='[{"temperature": 21}]',
        )
    )
    db_session.add(
        TwinConfiguration(
            twin_id=twin.id,
            aws_access_key_id="AKIA-SECRET-IN-DB",
            aws_secret_access_key="AWS-SECRET-IN-DB",
            aws_session_token="AWS-TOKEN-IN-DB",
            aws_region="eu-central-1",
            azure_subscription_id="AZ-SUB-SECRET-IN-DB",
            azure_tenant_id="AZ-TENANT-SECRET-IN-DB",
            azure_client_id="AZ-CLIENT-SECRET-IN-DB",
            azure_client_secret="AZ-CLIENT-SECRET-IN-DB",
            azure_region="westeurope",
            gcp_project_id="public-project-id",
            gcp_billing_account="GCP-BILLING-SECRET-IN-DB",
            gcp_service_account_json='{"private_key": "GCP-PRIVATE-KEY-IN-DB"}',
            gcp_region="europe-west1",
        )
    )
    db_session.commit()

    archive = TwinExportService(db_session).export_twin(twin_id=twin.id, user_id=user.id)

    assert archive.filename == "export-twin_config.zip"
    zip_bytes = archive.content.getvalue()
    for secret in [
        b"AKIA-SECRET-IN-DB",
        b"AWS-SECRET-IN-DB",
        b"AWS-TOKEN-IN-DB",
        b"AZ-SUB-SECRET-IN-DB",
        b"AZ-TENANT-SECRET-IN-DB",
        b"AZ-CLIENT-SECRET-IN-DB",
        b"GCP-BILLING-SECRET-IN-DB",
        b"GCP-PRIVATE-KEY-IN-DB",
    ]:
        assert secret not in zip_bytes

    with zipfile.ZipFile(archive.content) as zip_file:
        names = set(zip_file.namelist())
        assert "config_credentials.json" in names
        assert "gcp_credentials.json" not in names
        assert "config.json" in names
        assert "config_providers.json" in names
        assert "config_iot_devices.json" in names
        assert "iot_device_simulator/payloads.json" in names

        credentials = json.loads(zip_file.read("config_credentials.json"))
        assert credentials["aws"]["aws_access_key_id"] == REDACTED
        assert credentials["aws"]["aws_secret_access_key"] == REDACTED
        assert credentials["aws"]["aws_session_token"] == REDACTED
        assert credentials["azure"]["azure_client_secret"] == REDACTED
        assert credentials["gcp"]["gcp_project_id"] == "public-project-id"
        assert credentials["gcp"]["gcp_service_account_json"] == REDACTED


def test_export_twin_rejects_missing_twin(db_session):
    user = _create_user(db_session)

    with pytest.raises(EntityNotFoundError):
        TwinExportService(db_session).export_twin(twin_id="missing", user_id=user.id)


def test_export_twin_rejects_inactive_twin(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user, TwinState.INACTIVE)

    with pytest.raises(EntityNotFoundError):
        TwinExportService(db_session).export_twin(twin_id=twin.id, user_id=user.id)
