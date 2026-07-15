"""Tests for scene GLB file service boundary."""

from __future__ import annotations

import struct

import pytest

from src.config import settings
from src.models.deployer_config import DeployerConfiguration
from src.models.twin import DigitalTwin
from src.models.user import User
from src.repositories.twin_repository import TwinRepository
from src.services.scene_glb_service import SceneGlbService
from src.services.service_errors import EntityNotFoundError, ValidationError
from tests.conftest import create_test_twin


def _glb_bytes() -> bytes:
    json_chunk = b"{}  "
    total_length = 12 + 8 + len(json_chunk)
    return (
        struct.pack("<4sII", b"glTF", 2, total_length)
        + struct.pack("<I4s", len(json_chunk), b"JSON")
        + json_chunk
    )


def _create_user(db) -> User:
    user = User(
        email="scene-glb-service@example.test", name="Scene GLB", auth_provider="google"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _create_twin(db, user: User) -> DigitalTwin:
    twin = DigitalTwin(name="Scene Twin", user_id=user.id)
    db.add(twin)
    db.commit()
    db.refresh(twin)
    return twin


def _service(db, tmp_path, max_size_mb: int = 1) -> SceneGlbService:
    return SceneGlbService(
        db=db,
        twin_repository=TwinRepository(db),
        upload_dir=tmp_path,
        max_size_mb=max_size_mb,
    )


def test_upload_scene_glb_writes_file_and_marks_config_uploaded(db_session, tmp_path):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user)

    content = _glb_bytes()
    result = _service(db_session, tmp_path).upload_scene_glb(
        twin.id,
        user.id,
        content,
    )

    db_session.refresh(twin)
    assert result == {"message": "GLB file uploaded successfully", "size_mb": 0.0}
    assert (tmp_path / twin.id / "scene.glb").read_bytes() == content
    assert twin.deployer_config.scene_glb_uploaded is True


def test_upload_scene_glb_rejects_oversized_file_without_writing(db_session, tmp_path):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user)

    with pytest.raises(ValidationError, match="File exceeds 1MB limit"):
        _service(db_session, tmp_path, max_size_mb=1).upload_scene_glb(
            twin.id,
            user.id,
            b"x" * (1024 * 1024 + 1),
        )

    assert not (tmp_path / twin.id / "scene.glb").exists()


def test_upload_scene_glb_rejects_invalid_container_without_writing(
    db_session,
    tmp_path,
):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user)

    with pytest.raises(ValidationError, match="valid GLB 2.0"):
        _service(db_session, tmp_path).upload_scene_glb(
            twin.id,
            user.id,
            b"not-a-glb",
        )

    assert not (tmp_path / twin.id / "scene.glb").exists()


def test_delete_scene_glb_removes_file_and_clears_uploaded_flag(db_session, tmp_path):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user)
    twin_dir = tmp_path / twin.id
    twin_dir.mkdir(parents=True)
    (twin_dir / "scene.glb").write_bytes(b"glb-bytes")
    db_session.add(DeployerConfiguration(twin_id=twin.id, scene_glb_uploaded=True))
    db_session.commit()
    db_session.refresh(twin)

    result = _service(db_session, tmp_path).delete_scene_glb(twin.id, user.id)

    db_session.refresh(twin)
    assert result == {"message": "GLB file deleted"}
    assert not (twin_dir / "scene.glb").exists()
    assert twin.deployer_config.scene_glb_uploaded is False


def test_upload_scene_glb_rejects_missing_twin(db_session, tmp_path):
    user = _create_user(db_session)

    with pytest.raises(EntityNotFoundError, match="Twin not found"):
        _service(db_session, tmp_path).upload_scene_glb(
            "missing", user.id, b"glb-bytes"
        )


def test_upload_scene_glb_route_uses_temp_storage(
    authenticated_client, monkeypatch, tmp_path
):
    client, headers = authenticated_client
    twin_id = create_test_twin(client, headers)
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))

    response = client.post(
        f"/twins/{twin_id}/deployer/upload-glb",
        files={"file": ("scene.glb", _glb_bytes(), "model/gltf-binary")},
        headers=headers,
    )

    config_response = client.get(f"/twins/{twin_id}/deployer/config", headers=headers)
    assert response.status_code == 200
    assert response.json()["message"] == "GLB file uploaded successfully"
    assert (tmp_path / twin_id / "scene.glb").read_bytes() == _glb_bytes()
    assert config_response.json()["scene_glb_uploaded"] is True


def test_delete_scene_glb_route_clears_uploaded_flag(
    authenticated_client, monkeypatch, tmp_path
):
    client, headers = authenticated_client
    twin_id = create_test_twin(client, headers)
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    client.post(
        f"/twins/{twin_id}/deployer/upload-glb",
        files={"file": ("scene.glb", _glb_bytes(), "model/gltf-binary")},
        headers=headers,
    )

    response = client.delete(f"/twins/{twin_id}/deployer/upload-glb", headers=headers)

    config_response = client.get(f"/twins/{twin_id}/deployer/config", headers=headers)
    assert response.status_code == 200
    assert response.json() == {"message": "GLB file deleted"}
    assert not (tmp_path / twin_id / "scene.glb").exists()
    assert config_response.json()["scene_glb_uploaded"] is False
