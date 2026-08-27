"""Bounded Twin user-function validation, persistence, and packaging coverage."""

from __future__ import annotations

import json
from pathlib import Path
import sqlite3
from types import SimpleNamespace

import pytest

from migrations.add_twin_user_functions import LEGACY_TABLES, migrate
from src.models.twin import DigitalTwin, TwinState
from src.models.user import User
from src.models.user_function_extension import TwinUserFunction
from src.services.deployment_service import _materialize_twin_user_functions
from src.services.errors import DeploymentPackageBuildFailed
from src.services.user_function_extension_service import runtime

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
    artifact = json.loads(
        (CONTRACT_ROOT / "examples" / "valid-artifact.json").read_text(encoding="utf-8")
    )
    metadata = {
        "slot_id": artifact["slot_id"],
        "slot_version": artifact["slot_version"],
        "runtime_id": artifact["runtime_id"],
        "configuration": artifact["configuration"],
        "declared_capabilities": artifact["declared_capabilities"],
    }
    metadata.update(updates)
    return metadata


def _source_files() -> dict[str, str]:
    return {
        path.relative_to(SOURCE_ROOT).as_posix(): path.read_text(encoding="utf-8")
        for path in SOURCE_ROOT.iterdir()
        if path.is_file()
    }


def _multipart(metadata: dict | None = None, files: dict[str, str] | None = None):
    return {
        "metadata": (
            "metadata.json",
            runtime.canonical_json(metadata or _metadata()).encode("utf-8"),
            "application/json",
        ),
        "source_archive": (
            "source.zip",
            runtime.deterministic_source_zip(files or _source_files()),
            "application/zip",
        ),
    }


def test_api_validates_and_keeps_only_the_current_twin_function(
    authenticated_client,
    db_session,
):
    client, headers = authenticated_client
    twin = client.post(
        "/twins/", json={"name": "Function Twin"}, headers=headers
    ).json()
    slot = "processor.telemetry"

    slots = client.get("/architecture/extension-slots", headers=headers)
    assert slots.status_code == 200
    assert [item["slot_id"] for item in slots.json()["slots"]] == [slot]

    validated = client.post(
        f"/twins/{twin['id']}/user-functions/{slot}/validate",
        files=_multipart(),
        headers=headers,
    )
    assert validated.status_code == 200
    assert validated.json()["valid"] is True

    created = client.put(
        f"/twins/{twin['id']}/user-functions/{slot}",
        files=_multipart(),
        headers=headers,
    )
    assert created.status_code == 200
    original = created.json()
    assert original["schema_version"] == "twin-user-function.v1"
    assert "def process" not in created.text

    replaced = client.put(
        f"/twins/{twin['id']}/user-functions/{slot}",
        files=_multipart(_metadata(configuration={"scale_factor": 2})),
        headers=headers,
    )
    assert replaced.status_code == 200
    assert replaced.json()["function_id"] == original["function_id"]
    assert replaced.json()["artifact_digest"] != original["artifact_digest"]
    assert db_session.query(TwinUserFunction).count() == 1

    listed = client.get(
        f"/twins/{twin['id']}/user-functions",
        headers=headers,
    )
    assert listed.status_code == 200
    assert [item["function_id"] for item in listed.json()["items"]] == [
        original["function_id"]
    ]

    removed = client.delete(
        f"/twins/{twin['id']}/user-functions/{slot}",
        params={"slot_version": "1"},
        headers=headers,
    )
    assert removed.status_code == 204
    assert db_session.query(TwinUserFunction).count() == 0


def test_function_routes_are_owner_scoped_and_deployed_twins_are_immutable(
    authenticated_client,
    db_session,
):
    client, headers = authenticated_client
    owner = db_session.query(User).first()
    foreign = User(email="foreign-function@example.test")
    db_session.add(foreign)
    db_session.flush()
    foreign_twin = DigitalTwin(
        id="foreign-function-twin",
        user_id=foreign.id,
        name="Foreign Function Twin",
    )
    db_session.add(foreign_twin)
    db_session.commit()

    hidden = client.get(
        f"/twins/{foreign_twin.id}/user-functions",
        headers=headers,
    )
    assert hidden.status_code == 409

    own_twin = DigitalTwin(
        id="immutable-function-twin",
        user_id=owner.id,
        name="Immutable Function Twin",
        state=TwinState.DEPLOYED,
    )
    db_session.add(own_twin)
    db_session.commit()
    rejected = client.put(
        f"/twins/{own_twin.id}/user-functions/processor.telemetry",
        files=_multipart(),
        headers=headers,
    )
    assert rejected.status_code == 409


def test_validation_rejects_slot_mismatch_and_secret_source(authenticated_client):
    client, headers = authenticated_client
    twin = client.post(
        "/twins/", json={"name": "Invalid Function"}, headers=headers
    ).json()

    mismatch = client.post(
        f"/twins/{twin['id']}/user-functions/another.slot/validate",
        files=_multipart(),
        headers=headers,
    )
    assert mismatch.status_code == 422

    secret_files = _source_files()
    secret_files["process.py"] += "\nTOKEN = 'AKIAIOSFODNN7EXAMPLE'\n"
    rejected = client.post(
        f"/twins/{twin['id']}/user-functions/processor.telemetry/validate",
        files=_multipart(files=secret_files),
        headers=headers,
    )
    assert rejected.status_code == 400
    assert "AKIAIOSFODNN7EXAMPLE" not in rejected.text


def test_deployment_materializes_the_current_validated_twin_function():
    manifest = json.loads(
        (CONTRACT_ROOT / "examples" / "valid-artifact.json").read_text(encoding="utf-8")
    )
    twin_id = "00000000-0000-4000-8000-000000000099"
    user_function = SimpleNamespace(
        id=manifest["artifact_id"],
        twin_id=twin_id,
        slot_id=manifest["slot_id"],
        slot_version=manifest["slot_version"],
        artifact_digest=manifest["artifact_digest"],
        manifest_json=runtime.canonical_json(manifest),
        files=[
            SimpleNamespace(relative_path=path, content_text=content)
            for path, content in _source_files().items()
        ],
    )
    twin = SimpleNamespace(
        id=twin_id,
        user_id=manifest["created_by"],
        state=TwinState.DRAFT,
        user_functions=[user_function],
    )

    files = _materialize_twin_user_functions(twin)
    paths = {item.path for item in files}
    assert ".twin2multicloud/extensions/bindings.json" in paths
    assert any(path.endswith("/source/process.py") for path in paths)

    user_function.artifact_digest = "sha256:" + "0" * 64
    with pytest.raises(DeploymentPackageBuildFailed):
        _materialize_twin_user_functions(twin)


def test_openapi_exposes_twin_sources_but_no_artifact_catalog(client):
    schema = client.get("/openapi.json").json()
    paths = set(schema["paths"])
    assert not any(path.startswith("/user-function-artifacts") for path in paths)
    assert "/twins/{twin_id}/user-functions" in paths
    response = schema["components"]["schemas"]["TwinUserFunctionResponse"]
    assert response["additionalProperties"] is False
    assert "content_text" not in response["properties"]


def test_migration_drops_catalog_tables_and_creates_bounded_twin_tables(tmp_path):
    database = tmp_path / "functions.db"
    with sqlite3.connect(database) as connection:
        connection.executescript(
            """
            CREATE TABLE digital_twins (id VARCHAR PRIMARY KEY);
            CREATE TABLE user_function_artifacts (id VARCHAR PRIMARY KEY);
            CREATE TABLE user_function_artifact_files (id VARCHAR PRIMARY KEY);
            CREATE TABLE user_function_artifact_dependencies (id VARCHAR PRIMARY KEY);
            CREATE TABLE twin_extension_bindings (id VARCHAR PRIMARY KEY);
            CREATE TABLE user_function_audit_events (id VARCHAR PRIMARY KEY);
            """
        )

    database_url = f"sqlite:///{database}"
    migrate(database_url)
    migrate(database_url)

    with sqlite3.connect(database) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
    assert not set(LEGACY_TABLES) & tables
    assert {
        "twin_user_functions",
        "twin_user_function_files",
        "twin_user_function_dependencies",
    }.issubset(tables)
