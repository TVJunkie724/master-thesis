"""Tests for the Deployer-owned credential validation boundary."""

from __future__ import annotations

import pytest

from src.models.twin import DigitalTwin, TwinState
from src.models.twin_config import TwinConfiguration
from src.models.user import User
from src.repositories.twin_repository import TwinRepository
from src.schemas.cloud_connection import CloudConnectionCreate
from src.schemas.twin_config import (
    AWSCredentials,
    GCPCredentials,
    InlineValidationRequest,
)
from src.services.cloud_connection_service import CloudConnectionService
from src.services.credential_validation_service import CredentialValidationService
from src.services.secret_redaction import (
    redact_secret_like_text,
    redact_validation_message,
    redact_validation_payload,
)
from src.services.service_errors import EntityNotFoundError, ValidationError


def _create_user(db) -> User:
    user = User(
        email="credential-validation-service@example.test",
        name="Credential Validation",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _create_twin(db, user: User) -> DigitalTwin:
    twin = DigitalTwin(
        name="Credential Validation Twin",
        user_id=user.id,
        state=TwinState.DRAFT,
    )
    db.add(twin)
    db.commit()
    db.refresh(twin)
    return twin


def _service(db, *, deployer_validator=None, deployer_client=None):
    return CredentialValidationService(
        db=db,
        twin_repository=TwinRepository(db),
        deployer_validator=deployer_validator,
        deployer_client=deployer_client,
    )


def _bind_aws_connection(
    db,
    twin: DigitalTwin,
    user: User,
    *,
    secret: str = "AWS-SECRET-VALUE",
) -> TwinConfiguration:
    connection = CloudConnectionService(db).create_connection(
        user.id,
        CloudConnectionCreate.model_validate(
            {
                "provider": "aws",
                "display_name": "AWS deployment",
                "aws": {
                    "access_key_id": "AKIAIOSFODNN7EXAMPLE",
                    "secret_access_key": secret,
                    "region": "eu-central-1",
                },
            }
        ),
    )
    config = TwinConfiguration(
        twin_id=twin.id,
        aws_cloud_connection_id=connection.id,
    )
    db.add(config)
    db.commit()
    db.refresh(config)
    return config


class _FakePermissionClient:
    def __init__(self, result):
        self.result = result
        self.calls = []

    async def verify_permissions(self, provider, credentials):
        self.calls.append((provider, credentials))
        return self.result


@pytest.mark.asyncio
async def test_validate_stored_with_deployer_decrypts_connection_and_persists_flag(
    db_session,
):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user)
    config = _bind_aws_connection(db_session, twin, user)
    calls = []

    async def deployer(provider, credentials):
        calls.append((provider, credentials))
        return {
            "valid": True,
            "message": f"accepted {credentials['aws_secret_access_key']}",
            "missing_permissions": [f"needs {credentials['aws_secret_access_key']}"],
        }

    result = await _service(
        db_session,
        deployer_validator=deployer,
    ).validate_stored_with_deployer(twin.id, user.id, "aws")

    db_session.refresh(config)
    assert result.valid is True
    assert result.message == "accepted [REDACTED]"
    assert result.permissions == ["needs [REDACTED]"]
    assert config.aws_validated is True
    assert calls == [
        (
            "aws",
            {
                "aws_access_key_id": "AKIAIOSFODNN7EXAMPLE",
                "aws_secret_access_key": "AWS-SECRET-VALUE",
                "aws_region": "eu-central-1",
            },
        )
    ]


@pytest.mark.asyncio
async def test_validate_inline_with_deployer_redacts_message_and_permissions(
    db_session,
):
    secret = "INLINE-SECRET-VALUE"

    async def deployer(_provider, credentials):
        return {
            "valid": False,
            "message": f"failure echoed {credentials['aws_secret_access_key']}",
            "permissions": [f"secret seen: {credentials['aws_secret_access_key']}"],
        }

    result = await _service(
        db_session,
        deployer_validator=deployer,
    ).validate_inline_with_deployer(
        InlineValidationRequest(
            provider="aws",
            aws=AWSCredentials(
                access_key_id="AKIAIOSFODNN7EXAMPLE",
                secret_access_key=secret,
                region="eu-central-1",
            ),
        )
    )

    assert result.valid is False
    assert result.message == "failure echoed [REDACTED]"
    assert result.permissions == ["secret seen: [REDACTED]"]


@pytest.mark.asyncio
async def test_inline_default_path_uses_only_typed_deployer_client(db_session):
    deployer_client = _FakePermissionClient(
        {"valid": True, "message": "deployer ok", "missing_permissions": []}
    )

    result = await _service(
        db_session,
        deployer_client=deployer_client,
    ).validate_inline_with_deployer(
        InlineValidationRequest(
            provider="aws",
            aws=AWSCredentials(
                access_key_id="AKIAIOSFODNN7EXAMPLE",
                secret_access_key="DEFAULT-PATH-SECRET",
                region="eu-central-1",
            ),
        )
    )

    assert result.valid is True
    assert deployer_client.calls[0][0] == "aws"
    assert deployer_client.calls[0][1]["aws_secret_access_key"] == "DEFAULT-PATH-SECRET"


@pytest.mark.asyncio
async def test_inline_google_alias_normalizes_for_deployer(db_session):
    calls = []

    async def deployer(provider, credentials):
        calls.append((provider, credentials))
        return {"valid": True, "message": "ok"}

    result = await _service(
        db_session,
        deployer_validator=deployer,
    ).validate_inline_with_deployer(
        InlineValidationRequest(
            provider="Google",
            gcp=GCPCredentials(
                project_id="deployment-project",
                service_account_json='{"private_key": "GCP-PRIVATE-KEY"}',
                region="europe-west1",
            ),
        )
    )

    assert result.valid is True
    assert calls[0][0] == "gcp"
    assert calls[0][1]["gcp_project_id"] == "deployment-project"


@pytest.mark.asyncio
async def test_validate_stored_rejects_missing_twin(db_session):
    user = _create_user(db_session)

    with pytest.raises(EntityNotFoundError):
        await _service(db_session).validate_stored_with_deployer(
            "missing", user.id, "aws"
        )


@pytest.mark.asyncio
async def test_validate_stored_rejects_missing_config(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user)

    with pytest.raises(ValidationError):
        await _service(db_session).validate_stored_with_deployer(
            twin.id, user.id, "aws"
        )


def test_redact_validation_helpers_handle_nested_payloads():
    credentials = {"aws_secret_access_key": "NESTED-SECRET"}

    assert (
        redact_validation_message("leak NESTED-SECRET", credentials)
        == "leak [REDACTED]"
    )
    assert redact_validation_payload({"items": ["NESTED-SECRET"]}, credentials) == {
        "items": ["[REDACTED]"]
    }


def test_redact_secret_like_text_handles_common_secret_shapes():
    message = (
        'client_secret=CLIENT-SECRET-123 {"private_key_id": "gcp-key-id"} '
        "Authorization: Bearer abcdefghijklmnop "
        "-----BEGIN PRIVATE KEY-----abc-----END PRIVATE KEY-----"
    )

    redacted = redact_secret_like_text(message)

    assert "CLIENT-SECRET-123" not in redacted
    assert "gcp-key-id" not in redacted
    assert "abcdefghijklmnop" not in redacted
    assert "PRIVATE KEY-----abc" not in redacted
    assert redacted.count("[REDACTED]") >= 4
