"""Portable Twin duplicate/import/export contract tests."""

from __future__ import annotations

import io
import json
import struct
import zipfile
from datetime import datetime, timezone

import pytest

from src.models.deployer_config import DeployerConfiguration
from src.models.optimizer_config import OptimizerConfiguration
from src.models.twin import DigitalTwin, TwinState
from src.models.twin_config import TwinConfiguration
from src.models.user import User
from src.services.service_errors import EntityNotFoundError, ValidationError
from src.services.twin_export_service import (
    DEFINITION_PATH,
    MANIFEST_PATH,
    SCENE_PATH,
    TwinExportService,
)


def _create_user(db, email: str) -> User:
    user = User(email=email, name="Twin Transfer")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _valid_glb() -> bytes:
    document = b'{"asset":{"version":"2.0"}}'
    document += b" " * (-len(document) % 4)
    total_length = 12 + 8 + len(document)
    return (
        struct.pack("<4sII", b"glTF", 2, total_length)
        + struct.pack("<I4s", len(document), b"JSON")
        + document
    )


def _source_twin(db, user: User, upload_dir) -> DigitalTwin:
    twin = DigitalTwin(
        name="Portable Factory",
        user_id=user.id,
        state=TwinState.DEPLOYED,
        deployed_at=datetime.now(timezone.utc),
    )
    db.add(twin)
    db.flush()
    db.add(
        TwinConfiguration(
            twin_id=twin.id,
            debug_mode=True,
            aws_access_key_id="AKIA-DO-NOT-EXPORT",
            aws_secret_access_key="AWS-DO-NOT-EXPORT",
            aws_region="eu-central-1",
            aws_sso_region="eu-west-1",
            azure_client_secret="AZURE-DO-NOT-EXPORT",
            azure_region="westeurope",
            azure_region_iothub="northeurope",
            gcp_project_id="portable-target-project",
            gcp_service_account_json="GCP-DO-NOT-EXPORT",
            gcp_region="europe-west1",
        )
    )
    db.add(
        OptimizerConfiguration(
            twin_id=twin.id,
            params=json.dumps({"numberOfDevices": 2, "eventsPerMessage": 3}),
            result_json='{"derived":"must-not-copy"}',
        )
    )
    db.add(
        DeployerConfiguration(
            twin_id=twin.id,
            deployer_digital_twin_name="portable",
            config_iot_devices_json='{"devices":[{"id":"device-1"}]}',
            payloads_json='[{"temperature":21}]',
            state_machine_content='{"StartAt":"Done"}',
            event_feedback_content="def handler(event):\n    return event\n",
            config_iot_devices_validated=True,
            scene_glb_uploaded=True,
        )
    )
    scene_dir = upload_dir / twin.id
    scene_dir.mkdir(parents=True)
    (scene_dir / "scene.glb").write_bytes(_valid_glb())
    db.commit()
    db.refresh(twin)
    return twin


def test_export_is_deterministic_portable_and_contains_no_credentials(
    db_session,
    tmp_path,
):
    user = _create_user(db_session, "export@example.test")
    source = _source_twin(db_session, user, tmp_path)
    service = TwinExportService(db_session, upload_dir=tmp_path)

    first = service.export_twin(source.id, user.id)
    second = service.export_twin(source.id, user.id)

    assert first.filename == "portable-factory.twin.zip"
    assert first.content.getvalue() == second.content.getvalue()
    raw = first.content.getvalue()
    for secret in (
        b"AKIA-DO-NOT-EXPORT",
        b"AWS-DO-NOT-EXPORT",
        b"AZURE-DO-NOT-EXPORT",
        b"GCP-DO-NOT-EXPORT",
        b"derived",
    ):
        assert secret not in raw

    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        assert set(archive.namelist()) == {
            MANIFEST_PATH,
            DEFINITION_PATH,
            SCENE_PATH,
        }
        definition = json.loads(archive.read(DEFINITION_PATH))
        assert definition["schema_version"] == "twin-definition.v1"
        assert definition["optimizer_params"] == {
            "eventsPerMessage": 3,
            "numberOfDevices": 2,
        }
        assert definition["deployer"]["state_machine_content"] == '{"StartAt":"Done"}'
        assert "config_iot_devices_validated" not in definition["deployer"]


def test_duplicate_of_deployed_twin_is_new_mutable_draft_without_derived_state(
    db_session,
    tmp_path,
):
    user = _create_user(db_session, "duplicate@example.test")
    source = _source_twin(db_session, user, tmp_path)
    service = TwinExportService(db_session, upload_dir=tmp_path)

    duplicate = service.duplicate_twin(source.id, user.id, "Portable Copy")

    assert duplicate.id != source.id
    assert duplicate.name == "Portable Copy"
    assert duplicate.state == TwinState.DRAFT
    assert duplicate.deployed_at is None
    assert duplicate.optimizer_config.params is not None
    assert duplicate.optimizer_config.result_json is None
    assert duplicate.deployer_config.config_iot_devices_validated is False
    assert duplicate.deployer_config.scene_glb_uploaded is True
    assert (tmp_path / duplicate.id / "scene.glb").read_bytes() == _valid_glb()
    db_session.refresh(source)
    assert source.state == TwinState.DEPLOYED
    assert source.name == "Portable Factory"


def test_import_creates_credential_unbound_draft_for_another_user(
    db_session,
    tmp_path,
):
    owner = _create_user(db_session, "owner@example.test")
    recipient = _create_user(db_session, "recipient@example.test")
    source = _source_twin(db_session, owner, tmp_path)
    service = TwinExportService(db_session, upload_dir=tmp_path)
    archive = service.export_twin(source.id, owner.id).content.getvalue()

    imported = service.import_twin(archive, recipient.id, "Received Factory")

    assert imported.state == TwinState.DRAFT
    assert imported.user_id == recipient.id
    assert imported.configuration.aws_cloud_connection_id is None
    assert imported.configuration.azure_cloud_connection_id is None
    assert imported.configuration.gcp_cloud_connection_id is None
    assert imported.configuration.aws_access_key_id is None
    assert imported.configuration.azure_client_secret is None
    assert imported.configuration.gcp_service_account_json is None
    assert imported.optimizer_config.result_json is None


def test_import_rejects_manifest_digest_tampering(db_session, tmp_path):
    owner = _create_user(db_session, "tamper@example.test")
    source = _source_twin(db_session, owner, tmp_path)
    service = TwinExportService(db_session, upload_dir=tmp_path)
    original = service.export_twin(source.id, owner.id).content.getvalue()
    tampered = io.BytesIO()
    with (
        zipfile.ZipFile(io.BytesIO(original)) as source_zip,
        zipfile.ZipFile(
            tampered,
            "w",
            zipfile.ZIP_DEFLATED,
        ) as target_zip,
    ):
        for name in source_zip.namelist():
            value = source_zip.read(name)
            if name == DEFINITION_PATH:
                value += b" "
            target_zip.writestr(name, value)

    with pytest.raises(ValidationError, match="digest mismatch"):
        service.import_twin(tampered.getvalue(), owner.id, "Tampered")


def test_export_rejects_missing_or_inactive_twin(db_session, tmp_path):
    user = _create_user(db_session, "missing@example.test")
    service = TwinExportService(db_session, upload_dir=tmp_path)

    with pytest.raises(EntityNotFoundError):
        service.export_twin("missing", user.id)

    inactive = DigitalTwin(
        name="Inactive",
        user_id=user.id,
        state=TwinState.INACTIVE,
    )
    db_session.add(inactive)
    db_session.commit()
    with pytest.raises(EntityNotFoundError):
        service.export_twin(inactive.id, user.id)
