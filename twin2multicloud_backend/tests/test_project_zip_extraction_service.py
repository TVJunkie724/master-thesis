"""Tests for project ZIP extraction service boundary."""

from __future__ import annotations

import base64
import json

import pytest

from src.config import settings
from src.models.optimizer_config import OptimizerConfiguration
from src.models.twin import DigitalTwin
from src.models.user import User
from src.repositories.twin_repository import TwinRepository
from src.services.errors import ExternalServiceError
from src.services.project_zip_extraction_service import ProjectZipExtractionService
from src.services.scene_glb_service import SceneGlbService
from src.services.service_errors import EntityNotFoundError, ValidationError
from tests.conftest import create_test_twin


def _create_user(db) -> User:
    user = User(email="project-zip-service@example.test", name="Project ZIP", auth_provider="google")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _create_twin(db, user: User) -> DigitalTwin:
    twin = DigitalTwin(name="Project ZIP Twin", user_id=user.id)
    db.add(twin)
    db.commit()
    db.refresh(twin)
    return twin


class _FakeDeployerClient:
    def __init__(self, response=None, exc=None):
        self.response = response or {"success": True, "assets": {"scene_glb": None}}
        self.exc = exc
        self.calls = []

    async def extract_project_zip(self, content, validation_context):
        self.calls.append((content, validation_context))
        if self.exc:
            raise self.exc
        return self.response


def _service(db, tmp_path, deployer_client=None) -> ProjectZipExtractionService:
    twin_repository = TwinRepository(db)
    return ProjectZipExtractionService(
        db=db,
        twin_repository=twin_repository,
        scene_glb_service=SceneGlbService(db=db, twin_repository=twin_repository, upload_dir=tmp_path),
        deployer_client=deployer_client,
    )


@pytest.mark.asyncio
async def test_upload_project_zip_sends_validation_context_from_optimizer_columns(db_session, tmp_path):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user)
    db_session.add(OptimizerConfiguration(twin_id=twin.id, cheapest_l2="AWS", cheapest_l4="Azure"))
    db_session.commit()
    db_session.refresh(twin)

    fake = _FakeDeployerClient()
    result = await _service(db_session, tmp_path, fake).upload_project_zip(twin.id, user.id, b"zip-bytes")

    validation_context = fake.calls[0][1]
    assert result["success"] is True
    assert validation_context == {
        "skip_credentials": True,
        "skip_config_files": [],
        "l2_provider": "aws",
        "l4_provider": "azure",
    }


@pytest.mark.asyncio
async def test_upload_project_zip_uses_result_json_provider_fallback(db_session, tmp_path):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user)
    db_session.add(
        OptimizerConfiguration(
            twin_id=twin.id,
            result_json=json.dumps({"calculationResult": {"L2": "GCP", "L4": "AWS"}}),
        )
    )
    db_session.commit()
    db_session.refresh(twin)

    fake = _FakeDeployerClient()
    await _service(db_session, tmp_path, fake).upload_project_zip(twin.id, user.id, b"zip-bytes")

    validation_context = fake.calls[0][1]
    assert validation_context["l2_provider"] == "gcp"
    assert validation_context["l4_provider"] == "aws"


@pytest.mark.asyncio
async def test_upload_project_zip_saves_embedded_glb_and_strips_content(db_session, tmp_path):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user)
    encoded_glb = base64.b64encode(b"embedded-glb").decode()
    payload = {
        "success": True,
        "assets": {"scene_glb": {"exists": True, "is_binary": True, "content": encoded_glb}},
        "warnings": [],
    }

    result = await _service(
        db_session,
        tmp_path,
        _FakeDeployerClient(response=payload),
    ).upload_project_zip(twin.id, user.id, b"zip-bytes")

    db_session.refresh(twin)
    assert (tmp_path / twin.id / "scene.glb").read_bytes() == b"embedded-glb"
    assert twin.deployer_config.scene_glb_uploaded is True
    assert result["assets"]["scene_glb"] == {
        "exists": True,
        "saved": True,
        "is_binary": True,
        "content": None,
    }


@pytest.mark.asyncio
async def test_upload_project_zip_returns_stable_error_shape_on_deployer_error(db_session, tmp_path):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user)

    result = await _service(
        db_session,
        tmp_path,
        _FakeDeployerClient(exc=ExternalServiceError("boom", upstream_status_code=500, public_detail="boom")),
    ).upload_project_zip(twin.id, user.id, b"zip-bytes")

    assert result == {
        "success": False,
        "validation_errors": ["Deployer error: boom"],
        "files": {},
        "functions": {"processors": {}, "event_actions": {}, "event_feedback": None},
        "assets": {"scene_glb": None},
        "warnings": [],
    }


@pytest.mark.asyncio
async def test_upload_project_zip_redacts_deployer_error_text(db_session, tmp_path):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user)

    result = await _service(
        db_session,
        tmp_path,
        _FakeDeployerClient(
            exc=ExternalServiceError(
                "client_secret=ZIP-SECRET-123",
                upstream_status_code=500,
                public_detail="client_secret=ZIP-SECRET-123",
            )
        ),
    ).upload_project_zip(twin.id, user.id, b"zip-bytes")

    assert result["validation_errors"] == ["Deployer error: client_secret=[REDACTED]"]


@pytest.mark.asyncio
async def test_upload_project_zip_rejects_oversized_zip_before_downstream_call(db_session, tmp_path):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user)

    fake = _FakeDeployerClient()
    with pytest.raises(ValidationError, match="File too large"):
        await _service(db_session, tmp_path, fake).upload_project_zip(
            twin.id,
            user.id,
            b"x" * (100 * 1024 * 1024 + 1),
        )

    assert fake.calls == []


@pytest.mark.asyncio
async def test_upload_project_zip_rejects_missing_twin(db_session, tmp_path):
    user = _create_user(db_session)

    with pytest.raises(EntityNotFoundError, match="Twin not found"):
        await _service(db_session, tmp_path).upload_project_zip("missing", user.id, b"zip-bytes")


def test_upload_project_zip_route_delegates_and_preserves_response(authenticated_client, monkeypatch, tmp_path):
    client, headers = authenticated_client
    twin_id = create_test_twin(client, headers)
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))

    class FakeRouteService:
        async def upload_project_zip(self, twin_id, user_id, zip_content):
            return {"success": True, "assets": {"scene_glb": None}, "warnings": []}

    import src.api.routes.deployer as deployer_routes

    monkeypatch.setattr(
        deployer_routes,
        "_project_zip_extraction_service",
        lambda db: FakeRouteService(),
    )

    response = client.post(
        f"/twins/{twin_id}/deployer/upload-zip",
        files={"file": ("project.zip", b"zip-route", "application/zip")},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json() == {"success": True, "assets": {"scene_glb": None}, "warnings": []}
