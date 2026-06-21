"""Tests for deployer config validation service boundary."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.models.deployer_config import DeployerConfiguration
from src.models.twin import DigitalTwin
from src.models.user import User
from src.repositories.twin_repository import TwinRepository
from src.schemas.deployer_config import ConfigValidationRequest
from src.services.deployer_config_validation_service import DeployerConfigValidationService
from src.services.service_errors import EntityNotFoundError, ValidationError


def _create_user(db) -> User:
    user = User(email="deployer-validation-service@example.test", name="Deployer Validation", auth_provider="google")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _create_twin(db, user: User) -> DigitalTwin:
    twin = DigitalTwin(name="Validation Twin", user_id=user.id)
    db.add(twin)
    db.commit()
    db.refresh(twin)
    return twin


def _service(db) -> DeployerConfigValidationService:
    return DeployerConfigValidationService(db=db, twin_repository=TwinRepository(db))


def _mock_response(status_code: int, payload: dict, text: str = "") -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = payload
    response.text = text
    return response


@pytest.mark.asyncio
async def test_validate_section_two_persists_success_flag(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user)

    with patch("src.services.deployer_config_validation_service.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(
            return_value=_mock_response(200, {"message": "Valid"})
        )

        result = await _service(db_session).validate_config(
            twin.id,
            user.id,
            "events",
            ConfigValidationRequest(content="{}"),
        )

    db_session.refresh(twin)
    assert result.valid is True
    assert result.message == "Valid"
    assert twin.deployer_config.config_events_validated is True


@pytest.mark.asyncio
async def test_validate_l2_does_not_persist_validation_state(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user)

    with patch("src.services.deployer_config_validation_service.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(
            return_value=_mock_response(200, {"message": "Code is valid for aws."})
        )

        result = await _service(db_session).validate_config(
            twin.id,
            user.id,
            "function-code",
            ConfigValidationRequest(content="def handler(event, context): return {}", provider="aws"),
        )

    db_session.refresh(twin)
    assert result.valid is True
    assert twin.deployer_config is None


@pytest.mark.asyncio
async def test_validate_state_machine_uses_yaml_upload_for_yaml_content(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user)

    with patch("src.services.deployer_config_validation_service.httpx.AsyncClient") as mock_client:
        post = AsyncMock(return_value=_mock_response(200, {"message": "Valid"}))
        mock_client.return_value.__aenter__.return_value.post = post

        await _service(db_session).validate_config(
            twin.id,
            user.id,
            "state-machine",
            ConfigValidationRequest(content="StartAt: Start", provider="aws"),
        )

    files = post.call_args.kwargs["files"]
    assert files["file"][0] == "code.yaml"


@pytest.mark.asyncio
async def test_validate_scene_config_includes_existing_hierarchy(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user)
    db_session.add(DeployerConfiguration(twin_id=twin.id, hierarchy_content='{"root": []}'))
    db_session.commit()
    db_session.refresh(twin)

    with patch("src.services.deployer_config_validation_service.httpx.AsyncClient") as mock_client:
        post = AsyncMock(return_value=_mock_response(200, {"message": "Valid"}))
        mock_client.return_value.__aenter__.return_value.post = post

        await _service(db_session).validate_config(
            twin.id,
            user.id,
            "scene-config",
            ConfigValidationRequest(content='{"scenes": []}', provider="azure"),
        )

    files = post.call_args.kwargs["files"]
    assert files["scene_file"][0] == "scene.json"
    assert files["hierarchy_file"][1] == b'{"root": []}'


@pytest.mark.asyncio
async def test_validate_downstream_error_returns_safe_invalid_result(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user)

    with patch("src.services.deployer_config_validation_service.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(
            return_value=_mock_response(400, {"detail": "SyntaxError: invalid syntax"}, "bad request")
        )

        result = await _service(db_session).validate_config(
            twin.id,
            user.id,
            "function-code",
            ConfigValidationRequest(content="def broken(", provider="aws"),
        )

    assert result.valid is False
    assert "SyntaxError" in result.message


@pytest.mark.asyncio
async def test_validate_downstream_error_redacts_secret_fragments(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user)

    with patch("src.services.deployer_config_validation_service.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(
            return_value=_mock_response(
                400,
                {"detail": "private_key=VALIDATION-PRIVATE-KEY-123"},
                "bad request",
            )
        )

        result = await _service(db_session).validate_config(
            twin.id,
            user.id,
            "function-code",
            ConfigValidationRequest(content="def broken(", provider="aws"),
        )

    assert result.valid is False
    assert "VALIDATION-PRIVATE-KEY-123" not in result.message
    assert "private_key=[REDACTED]" in result.message


@pytest.mark.asyncio
async def test_validate_request_error_redacts_secret_fragments(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user)

    with patch("src.services.deployer_config_validation_service.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(
            side_effect=httpx.RequestError("client_secret=VALIDATION-SECRET-123")
        )

        result = await _service(db_session).validate_config(
            twin.id,
            user.id,
            "events",
            ConfigValidationRequest(content="{}"),
        )

    assert result.valid is False
    assert "VALIDATION-SECRET-123" not in result.message
    assert "client_secret=[REDACTED]" in result.message


@pytest.mark.asyncio
async def test_validate_rejects_missing_provider_before_downstream_call(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user)

    with pytest.raises(ValidationError, match="provider is required"):
        await _service(db_session).validate_config(
            twin.id,
            user.id,
            "function-code",
            ConfigValidationRequest(content="def handler(): pass"),
        )


@pytest.mark.asyncio
async def test_validate_rejects_missing_twin(db_session):
    user = _create_user(db_session)

    with pytest.raises(EntityNotFoundError, match="Twin not found"):
        await _service(db_session).validate_config(
            "missing",
            user.id,
            "events",
            ConfigValidationRequest(content="{}"),
        )
