"""Tests for deployer config validation service boundary."""

from __future__ import annotations

import pytest

from src.models.deployer_config import DeployerConfiguration
from src.models.twin import DigitalTwin
from src.models.user import User
from src.repositories.twin_repository import TwinRepository
from src.schemas.deployer_config import ConfigValidationRequest
from src.services.errors import ExternalServiceError, ExternalServiceUnavailable
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


class _FakeDeployerClient:
    def __init__(self, response=None, exc=None):
        self.response = response or {"message": "Valid"}
        self.exc = exc
        self.calls = []

    async def validate_config_file(self, endpoint, files, *, provider=None):
        self.calls.append({"endpoint": endpoint, "files": files, "provider": provider})
        if self.exc:
            raise self.exc
        return self.response


def _service(db, deployer_client=None) -> DeployerConfigValidationService:
    return DeployerConfigValidationService(
        db=db,
        twin_repository=TwinRepository(db),
        deployer_client=deployer_client,
    )


@pytest.mark.asyncio
async def test_validate_section_two_persists_success_flag(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user)
    deployer_client = _FakeDeployerClient()

    result = await _service(db_session, deployer_client).validate_config(
        twin.id,
        user.id,
        "events",
        ConfigValidationRequest(content="{}"),
    )

    db_session.refresh(twin)
    assert result.valid is True
    assert result.message == "Valid"
    assert twin.deployer_config.config_events_validated is True
    assert deployer_client.calls[0]["endpoint"] == "config/events"


@pytest.mark.asyncio
async def test_validate_l2_does_not_persist_validation_state(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user)
    deployer_client = _FakeDeployerClient(response={"message": "Code is valid for aws."})

    result = await _service(db_session, deployer_client).validate_config(
        twin.id,
        user.id,
        "function-code",
        ConfigValidationRequest(content="def handler(event, context): return {}", provider="aws"),
    )

    db_session.refresh(twin)
    assert result.valid is True
    assert twin.deployer_config is None
    assert deployer_client.calls[0]["provider"] == "aws"


@pytest.mark.asyncio
async def test_validate_state_machine_uses_yaml_upload_for_yaml_content(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user)
    deployer_client = _FakeDeployerClient()

    await _service(db_session, deployer_client).validate_config(
        twin.id,
        user.id,
        "state-machine",
        ConfigValidationRequest(content="StartAt: Start", provider="aws"),
    )

    files = deployer_client.calls[0]["files"]
    assert files["file"][0] == "code.yaml"


@pytest.mark.asyncio
async def test_validate_scene_config_includes_existing_hierarchy(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user)
    db_session.add(DeployerConfiguration(twin_id=twin.id, hierarchy_content='{"root": []}'))
    db_session.commit()
    db_session.refresh(twin)
    deployer_client = _FakeDeployerClient()

    await _service(db_session, deployer_client).validate_config(
        twin.id,
        user.id,
        "scene-config",
        ConfigValidationRequest(content='{"scenes": []}', provider="azure"),
    )

    files = deployer_client.calls[0]["files"]
    assert files["scene_file"][0] == "scene.json"
    assert files["hierarchy_file"][1] == b'{"root": []}'


@pytest.mark.asyncio
async def test_validate_downstream_error_returns_safe_invalid_result(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user)
    deployer_client = _FakeDeployerClient(
        exc=ExternalServiceError(
            "Deployer API returned 400: SyntaxError: invalid syntax",
            upstream_status_code=400,
            public_detail="SyntaxError: invalid syntax",
        )
    )

    result = await _service(db_session, deployer_client).validate_config(
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
    deployer_client = _FakeDeployerClient(
        exc=ExternalServiceError(
            "Deployer API returned 400: private_key=VALIDATION-PRIVATE-KEY-123",
            upstream_status_code=400,
            public_detail="private_key=VALIDATION-PRIVATE-KEY-123",
        )
    )

    result = await _service(db_session, deployer_client).validate_config(
        twin.id,
        user.id,
        "function-code",
        ConfigValidationRequest(content="def broken(", provider="aws"),
    )

    assert result.valid is False
    assert "VALIDATION-PRIVATE-KEY-123" not in result.message
    assert "private_key=[REDACTED]" in result.message


@pytest.mark.asyncio
async def test_validate_unavailable_returns_generic_message_without_secret(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user)
    deployer_client = _FakeDeployerClient(
        exc=ExternalServiceUnavailable("client_secret=VALIDATION-SECRET-123")
    )

    result = await _service(db_session, deployer_client).validate_config(
        twin.id,
        user.id,
        "events",
        ConfigValidationRequest(content="{}"),
    )

    assert result.valid is False
    assert "VALIDATION-SECRET-123" not in result.message
    assert result.message == "Cannot connect to Deployer API. Is it running on port 5004?"


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
