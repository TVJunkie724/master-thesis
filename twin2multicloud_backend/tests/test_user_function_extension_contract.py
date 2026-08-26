"""Contract, API, persistence, migration, and package coverage for #113."""

from __future__ import annotations

import json
from pathlib import Path
import sqlite3
from types import SimpleNamespace
import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from migrations.add_user_function_extension_contract import migrate
from src.models.deployer_config import DeployerConfiguration
from src.models.twin import TwinState
from src.models.user import User
from src.models.user_function_extension import (
    TwinExtensionBinding,
    UserFunctionArtifact,
    UserFunctionAuditEvent,
)
from src.services.credential_resolution_service import DeploymentCredentials
from src.services.deployment_service import (
    _materialize_deployment_files,
    _materialize_extension_bindings,
)
from src.services.errors import DeploymentPackageBuildFailed
from src.services.user_function_extension_service import (
    ExtensionContractError,
    UserFunctionExtensionService,
    runtime,
)


CONTRACT_ROOT = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "contracts"
    / "generated"
    / "user-function-extension"
    / "v1"
)
SOURCE_ROOT = CONTRACT_ROOT / "examples" / "source" / "valid"


def _metadata(**updates) -> dict:
    document = json.loads(
        (CONTRACT_ROOT / "examples" / "valid-artifact.json").read_text(encoding="utf-8")
    )
    metadata = {
        "slot_id": document["slot_id"],
        "slot_version": document["slot_version"],
        "runtime_id": document["runtime_id"],
        "configuration": document["configuration"],
        "declared_capabilities": document["declared_capabilities"],
    }
    metadata.update(updates)
    return metadata


def _source_files() -> dict[str, str]:
    return {
        path.relative_to(SOURCE_ROOT).as_posix(): path.read_text(encoding="utf-8")
        for path in SOURCE_ROOT.iterdir()
        if path.is_file()
    }


def _multipart(metadata: dict | None = None) -> dict:
    return {
        "metadata": (
            "metadata.json",
            runtime.canonical_json(metadata or _metadata()).encode("utf-8"),
            "application/json",
        ),
        "source_archive": (
            "source.zip",
            runtime.deterministic_source_zip(_source_files()),
            "application/zip",
        ),
    }


def test_api_validates_persists_binds_and_redacts_source(
    authenticated_client,
    db_session,
):
    client, headers = authenticated_client
    twin = client.post(
        "/twins/",
        json={"name": "Extension Twin"},
        headers=headers,
    ).json()

    slots = client.get("/architecture/extension-slots", headers=headers)
    assert slots.status_code == 200
    assert [item["slot_id"] for item in slots.json()["slots"]] == [
        "processor.telemetry"
    ]

    validated = client.post(
        "/user-function-artifacts/validate",
        files=_multipart(),
        headers=headers,
    )
    assert validated.status_code == 200
    assert validated.json()["valid"] is True

    created = client.post(
        "/user-function-artifacts",
        files=_multipart(),
        headers=headers,
    )
    assert created.status_code == 201
    artifact = created.json()
    assert artifact["artifact_state"] == "valid"
    assert "def process" not in created.text

    idempotent = client.post(
        "/user-function-artifacts",
        files=_multipart(),
        headers=headers,
    )
    assert idempotent.status_code == 201
    assert idempotent.json()["artifact_id"] == artifact["artifact_id"]

    bound = client.put(
        f"/twins/{twin['id']}/extension-bindings/processor.telemetry",
        json={"artifact_id": artifact["artifact_id"], "slot_version": "1"},
        headers=headers,
    )
    assert bound.status_code == 200
    assert bound.json()["artifact_digest"] == artifact["artifact_digest"]

    bindings = client.get(
        f"/twins/{twin['id']}/extension-bindings",
        headers=headers,
    )
    assert bindings.status_code == 200
    assert len(bindings.json()["items"]) == 1

    replacement = client.post(
        "/user-function-artifacts",
        files=_multipart(_metadata(configuration={"scale_factor": 2})),
        headers=headers,
    ).json()
    rebound = client.put(
        f"/twins/{twin['id']}/extension-bindings/processor.telemetry",
        json={
            "artifact_id": replacement["artifact_id"],
            "slot_version": "1",
            "expected_revision": 1,
        },
        headers=headers,
    )
    assert rebound.status_code == 200
    assert rebound.json()["revision"] == 2
    history = (
        db_session.query(TwinExtensionBinding)
        .filter(TwinExtensionBinding.twin_id == twin["id"])
        .order_by(TwinExtensionBinding.revision)
        .all()
    )
    assert [(item.revision, bool(item.active)) for item in history] == [
        (1, False),
        (2, True),
    ]
    unbound = client.delete(
        f"/twins/{twin['id']}/extension-bindings/processor.telemetry",
        params={"slot_version": "1", "expected_revision": 2},
        headers=headers,
    )
    assert unbound.status_code == 204
    assert (
        client.get(
            f"/twins/{twin['id']}/extension-bindings",
            headers=headers,
        ).json()["items"]
        == []
    )

    source = client.get(
        f"/user-function-artifacts/{artifact['artifact_id']}/source",
        headers=headers,
    )
    assert source.status_code == 200
    assert source.headers["cache-control"] == "no-store"

    audit_json = json.dumps(
        [
            {
                "action": event.action,
                "outcome": event.outcome,
                "error_code": event.error_code,
            }
            for event in db_session.query(UserFunctionAuditEvent).all()
        ]
    )
    assert "def process" not in audit_json
    assert "secret" not in audit_json.lower()
    assert "artifact.upload" in audit_json


def test_api_rejects_platform_fields_secrets_and_stale_binding(
    authenticated_client,
):
    client, headers = authenticated_client
    platform_field = client.post(
        "/user-function-artifacts/validate",
        files=_multipart(_metadata(artifact_digest="sha256:" + "0" * 64)),
        headers=headers,
    )
    assert platform_field.status_code == 422
    assert platform_field.json()["detail"]["error_code"] == "EXTENSION_SCHEMA_INVALID"

    secret = client.post(
        "/user-function-artifacts/validate",
        files=_multipart(
            _metadata(configuration={"scale_factor": 1, "api_key": "not-allowed"})
        ),
        headers=headers,
    )
    assert secret.status_code in {400, 422}
    assert "not-allowed" not in secret.text


def test_binding_integrity_race_returns_stable_contract_error(
    db_session,
    monkeypatch,
):
    owner = User(email="binding-race@example.test", name="Binding Race")
    db_session.add(owner)
    db_session.commit()
    service = UserFunctionExtensionService(db_session)
    monkeypatch.setattr(
        service,
        "_bind",
        lambda **_kwargs: (_ for _ in ()).throw(
            IntegrityError("binding race", {}, RuntimeError("unique"))
        ),
    )

    with pytest.raises(ExtensionContractError) as caught:
        service.bind(
            user_id=owner.id,
            twin_id=str(uuid.uuid4()),
            slot_id="processor.telemetry",
            update=SimpleNamespace(
                artifact_id=str(uuid.uuid4()),
                slot_version="1",
                expected_revision=1,
            ),
            correlation_id="race-correlation",
        )

    assert caught.value.code == "EXTENSION_BINDING_UNRESOLVED"
    assert caught.value.field == "expected_revision"
    assert caught.value.correlation_id == "race-correlation"
    event = db_session.query(UserFunctionAuditEvent).one()
    assert event.outcome == "rejected"
    assert event.error_code == "EXTENSION_BINDING_UNRESOLVED"


def test_api_enforces_upload_bounds_source_rate_limit_and_owner_isolation(
    authenticated_client,
    db_session,
):
    client, headers = authenticated_client
    oversized = client.post(
        "/user-function-artifacts/validate",
        files={
            **_multipart(),
            "metadata": (
                "metadata.json",
                b"x" * (64 * 1024 + 1),
                "application/json",
            ),
        },
        headers=headers,
    )
    assert oversized.status_code == 413
    assert "x" * 64 not in oversized.text
    assert (
        db_session.query(UserFunctionAuditEvent)
        .filter(
            UserFunctionAuditEvent.action == "artifact.upload",
            UserFunctionAuditEvent.outcome == "rejected",
        )
        .count()
        == 1
    )

    created = client.post(
        "/user-function-artifacts",
        files=_multipart(),
        headers=headers,
    ).json()
    other = User(email="extension-other@example.test", name="Other")
    db_session.add(other)
    db_session.commit()
    with pytest.raises(ExtensionContractError):
        UserFunctionExtensionService(db_session).get_artifact(
            other.id,
            created["artifact_id"],
        )
    with pytest.raises(ExtensionContractError) as denied_source:
        UserFunctionExtensionService(db_session).get_source_zip(
            user_id=other.id,
            artifact_id=created["artifact_id"],
            correlation_id="owner-isolation",
        )
    assert denied_source.value.correlation_id == "owner-isolation"
    assert (
        db_session.query(UserFunctionAuditEvent)
        .filter(
            UserFunctionAuditEvent.user_id == other.id,
            UserFunctionAuditEvent.action == "artifact.source.download",
            UserFunctionAuditEvent.outcome == "rejected",
        )
        .count()
        == 1
    )

    source_path = f"/user-function-artifacts/{created['artifact_id']}/source"
    for _ in range(5):
        download = client.get(source_path, headers=headers)
        assert download.status_code == 200
        assert download.headers["ratelimit-limit"] == "5"
    limited = client.get(source_path, headers=headers)
    assert limited.status_code == 429
    assert limited.headers["retry-after"]
    assert (
        db_session.query(UserFunctionAuditEvent)
        .filter(
            UserFunctionAuditEvent.action == "artifact.source.download",
            UserFunctionAuditEvent.outcome == "rate_limited",
        )
        .count()
        == 1
    )


def test_explicit_legacy_import_creates_v1_without_mutating_legacy(
    authenticated_client,
    db_session,
):
    client, headers = authenticated_client
    owner = db_session.query(User).first()
    legacy = UserFunctionArtifact(
        id=str(uuid.uuid4()),
        user_id=owner.id,
        schema_version="legacy-user-function-artifact.v0",
        artifact_state="legacy_unvalidated",
        artifact_digest="sha256:" + "1" * 64,
        slot_id="legacy.processor.device",
        slot_version="0",
        runtime_id="legacy-python",
        manifest_json=None,
        configuration_json="{}",
        declared_capabilities_json="[]",
        validator_version=None,
        created_by=owner.id,
    )
    db_session.add(legacy)
    db_session.commit()

    imported = client.post(
        f"/user-function-artifacts/{legacy.id}/import",
        files=_multipart(),
        headers=headers,
    )
    assert imported.status_code == 201
    assert imported.json()["artifact_state"] == "valid"
    assert imported.json()["artifact_id"] != legacy.id
    db_session.expire_all()
    assert db_session.get(UserFunctionArtifact, legacy.id).artifact_state == (
        "legacy_unvalidated"
    )


def test_openapi_does_not_expose_stored_source_fields(client):
    schema = client.get("/openapi.json").json()
    artifact_schema = schema["components"]["schemas"]["UserFunctionArtifactResponse"]
    properties = set(artifact_schema["properties"])
    assert "content_text" not in properties
    assert "source" not in properties
    assert {"source_files", "artifact_digest"}.issubset(properties)
    assert artifact_schema["additionalProperties"] is False
    binding_update = schema["components"]["schemas"]["TwinExtensionBindingUpdate"]
    assert binding_update["additionalProperties"] is False
    assert set(binding_update["properties"]) == {
        "artifact_id",
        "slot_version",
        "expected_revision",
    }
    assert "/user-function-artifacts/{legacy_artifact_id}/import" in schema["paths"]


def test_deployment_materializes_only_valid_owner_scoped_bindings():
    manifest = json.loads(
        (CONTRACT_ROOT / "examples" / "valid-artifact.json").read_text(encoding="utf-8")
    )
    artifact = SimpleNamespace(
        id=manifest["artifact_id"],
        user_id=manifest["created_by"],
        artifact_state="valid",
        artifact_digest=manifest["artifact_digest"],
        manifest_json=runtime.canonical_json(manifest),
        files=[
            SimpleNamespace(relative_path=path, content_text=content)
            for path, content in _source_files().items()
        ],
    )
    twin_id = "00000000-0000-4000-8000-000000000099"
    binding = SimpleNamespace(
        user_id=artifact.user_id,
        twin_id=twin_id,
        slot_id=manifest["slot_id"],
        slot_version=manifest["slot_version"],
        artifact=artifact,
        binding_digest=runtime.binding_digest(
            twin_id=twin_id,
            slot_id=manifest["slot_id"],
            slot_version=manifest["slot_version"],
            artifact_id=manifest["artifact_id"],
            artifact_digest=manifest["artifact_digest"],
        ),
        active=True,
    )
    twin = SimpleNamespace(
        id=twin_id,
        user_id=artifact.user_id,
        state=TwinState.DRAFT,
        extension_bindings=[binding],
    )

    files = _materialize_extension_bindings(twin)
    paths = {item.path for item in files}
    assert ".twin2multicloud/extensions/bindings.json" in paths
    assert any(path.endswith("/source/process.py") for path in paths)
    assert all("handler" not in item.content for item in files)

    binding.binding_digest = "sha256:" + "0" * 64
    with pytest.raises(DeploymentPackageBuildFailed):
        _materialize_extension_bindings(twin)


def test_new_deployment_blocks_legacy_source_and_omits_it_when_v1_is_bound(
    sample_calc_params,
):
    dc = DeployerConfiguration(
        processor_contents=json.dumps(
            {"device": "def legacy(payload):\n    return payload\n"}
        ),
        processor_requirements=json.dumps({"device": "demo==1.0"}),
    )
    twin = SimpleNamespace(
        id="00000000-0000-4000-8000-000000000099",
        name="Legacy Twin",
        user_id="00000000-0000-4000-8000-000000000001",
        state=TwinState.DRAFT,
        deployer_config=dc,
        optimizer_config=None,
        configuration=None,
        extension_bindings=[],
    )
    credentials = DeploymentCredentials(providers=(), config_credentials={})
    with pytest.raises(DeploymentPackageBuildFailed) as exc:
        _materialize_deployment_files(
            twin,
            {},
            credentials,
            optimizer_params=sample_calc_params,
        )
    assert "EXTENSION_BINDING_UNRESOLVED" in str(exc.value.errors)

    manifest = json.loads(
        (CONTRACT_ROOT / "examples" / "valid-artifact.json").read_text(encoding="utf-8")
    )
    artifact = SimpleNamespace(
        id=manifest["artifact_id"],
        user_id=twin.user_id,
        artifact_state="valid",
        artifact_digest=manifest["artifact_digest"],
        manifest_json=runtime.canonical_json(manifest),
        files=[
            SimpleNamespace(relative_path=path, content_text=content)
            for path, content in _source_files().items()
        ],
    )
    binding = SimpleNamespace(
        user_id=twin.user_id,
        twin_id=twin.id,
        slot_id=manifest["slot_id"],
        slot_version=manifest["slot_version"],
        artifact=artifact,
        binding_digest=runtime.binding_digest(
            twin_id=twin.id,
            slot_id=manifest["slot_id"],
            slot_version=manifest["slot_version"],
            artifact_id=artifact.id,
            artifact_digest=artifact.artifact_digest,
        ),
        active=True,
    )
    twin.extension_bindings = [binding]
    files = _materialize_deployment_files(
        twin,
        {},
        credentials,
        optimizer_params=sample_calc_params,
    )
    paths = {item.path for item in files}
    assert ".twin2multicloud/extensions/bindings.json" in paths
    assert not any("/processors/" in path for path in paths)
    assert not any(path.endswith("requirements.txt") for path in paths)


def test_migration_from_empty_database_is_idempotent(tmp_path):
    database = tmp_path / "empty.db"
    actions = migrate(f"sqlite:///{database}")
    repeated = migrate(f"sqlite:///{database}")
    assert actions == repeated
    with sqlite3.connect(database) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
    assert {
        "user_function_artifacts",
        "user_function_artifact_files",
        "user_function_artifact_dependencies",
        "twin_extension_bindings",
        "user_function_audit_events",
    }.issubset(tables)


def test_migration_imports_legacy_as_unvalidated_and_is_idempotent(tmp_path):
    database = tmp_path / "legacy.db"
    with sqlite3.connect(database) as connection:
        connection.executescript(
            """
            CREATE TABLE users (id VARCHAR PRIMARY KEY);
            CREATE TABLE digital_twins (
                id VARCHAR PRIMARY KEY,
                user_id VARCHAR NOT NULL REFERENCES users(id)
            );
            CREATE TABLE deployer_configurations (
                id VARCHAR PRIMARY KEY,
                twin_id VARCHAR NOT NULL REFERENCES digital_twins(id),
                processor_contents TEXT,
                processor_requirements TEXT,
                event_feedback_content TEXT,
                event_feedback_requirements TEXT,
                event_action_contents TEXT,
                event_action_requirements TEXT,
                created_at DATETIME
            );
            INSERT INTO users(id) VALUES ('owner-1');
            INSERT INTO digital_twins(id, user_id) VALUES ('twin-1', 'owner-1');
            """
        )
        connection.execute(
            """
            INSERT INTO deployer_configurations(
                id, twin_id, processor_contents, processor_requirements
            ) VALUES (?, ?, ?, ?)
            """,
            (
                "config-1",
                "twin-1",
                json.dumps({"processor": "def legacy():\n    return 1\n"}),
                json.dumps({"processor": "demo==1.0"}),
            ),
        )

    database_url = f"sqlite:///{database}"
    migrate(database_url)
    migrate(database_url)

    with sqlite3.connect(database) as connection:
        rows = connection.execute(
            """
            SELECT artifact_state, schema_version, manifest_json
            FROM user_function_artifacts
            """
        ).fetchall()
        assert rows == [
            ("legacy_unvalidated", "legacy-user-function-artifact.v0", None)
        ]
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM twin_extension_bindings"
            ).fetchone()[0]
            == 0
        )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE user_function_artifacts SET artifact_state='valid'"
            )
