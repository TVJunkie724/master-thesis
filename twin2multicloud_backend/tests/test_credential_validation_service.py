"""Tests for credential validation service boundaries."""

from __future__ import annotations

import pytest

from src.models.twin import DigitalTwin, TwinState
from src.models.twin_config import TwinConfiguration
from src.models.user import User
from src.repositories.twin_repository import TwinRepository
from src.schemas.twin_config import AWSCredentials, GCPCredentials, InlineValidationRequest
from src.services.credential_validation_service import CredentialValidationService
from src.services.secret_redaction import redact_secret_like_text, redact_validation_message, redact_validation_payload
from src.services.service_errors import EntityNotFoundError, ValidationError
from src.utils.crypto import encrypt


def _create_user(db) -> User:
    user = User(email="credential-validation-service@example.test", name="Credential Validation", auth_provider="google")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _create_twin(db, user: User) -> DigitalTwin:
    twin = DigitalTwin(name="Credential Validation Twin", user_id=user.id, state=TwinState.DRAFT)
    db.add(twin)
    db.commit()
    db.refresh(twin)
    return twin


def _service(db, *, optimizer_validator=None, deployer_validator=None) -> CredentialValidationService:
    return CredentialValidationService(
        db=db,
        twin_repository=TwinRepository(db),
        optimizer_validator=optimizer_validator,
        deployer_validator=deployer_validator,
    )


def _add_aws_config(db, twin: DigitalTwin, user: User, *, secret: str = "AWS-SECRET-VALUE") -> TwinConfiguration:
    config = TwinConfiguration(
        twin_id=twin.id,
        aws_access_key_id=encrypt("AKIAIOSFODNN7EXAMPLE", user.id, twin.id),
        aws_secret_access_key=encrypt(secret, user.id, twin.id),
        aws_region="eu-central-1",
    )
    db.add(config)
    db.commit()
    db.refresh(config)
    return config


@pytest.mark.asyncio
async def test_validate_stored_with_deployer_decrypts_and_persists_flag(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user)
    config = _add_aws_config(db_session, twin, user)
    calls = []

    async def deployer(provider, credentials):
        calls.append((provider, credentials))
        return {
            "valid": True,
            "message": f"accepted {credentials['aws_secret_access_key']}",
            "missing_permissions": [f"needs {credentials['aws_secret_access_key']}"],
        }

    result = await _service(db_session, deployer_validator=deployer).validate_stored_with_deployer(
        twin_id=twin.id,
        user_id=user.id,
        provider="aws",
    )

    db_session.refresh(config)
    assert result.valid is True
    assert result.message == "accepted [REDACTED]"
    assert result.permissions == ["needs [REDACTED]"]
    assert config.aws_validated is True
    assert calls[0][0] == "aws"
    assert calls[0][1]["aws_secret_access_key"] == "AWS-SECRET-VALUE"


@pytest.mark.asyncio
async def test_validate_inline_with_deployer_redacts_message_and_permissions(db_session):
    secret = "INLINE-SECRET-VALUE"

    async def deployer(_provider, credentials):
        return {
            "valid": False,
            "message": f"failure echoed {credentials['aws_secret_access_key']}",
            "permissions": [f"secret seen: {credentials['aws_secret_access_key']}"],
        }

    result = await _service(db_session, deployer_validator=deployer).validate_inline_with_deployer(
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
    assert secret not in result.message
    assert result.message == "failure echoed [REDACTED]"
    assert result.permissions == ["secret seen: [REDACTED]"]


@pytest.mark.asyncio
async def test_validate_inline_dual_combines_results_and_redacts(db_session):
    secret = "DUAL-SECRET-VALUE"

    async def optimizer(_provider, credentials):
        return {"valid": True, "message": f"optimizer ok {credentials['aws_secret_access_key']}"}

    async def deployer(_provider, credentials):
        return {"valid": False, "message": f"deployer denied {credentials['aws_secret_access_key']}"}

    result = await _service(
        db_session,
        optimizer_validator=optimizer,
        deployer_validator=deployer,
    ).validate_inline_dual(
        InlineValidationRequest(
            provider="aws",
            aws=AWSCredentials(
                access_key_id="AKIAIOSFODNN7EXAMPLE",
                secret_access_key=secret,
                region="eu-central-1",
            ),
        )
    )

    assert result["valid"] is False
    assert result["optimizer"]["valid"] is True
    assert result["deployer"]["valid"] is False
    assert secret not in str(result)
    assert result["optimizer"]["message"] == "optimizer ok [REDACTED]"
    assert result["deployer"]["message"] == "deployer denied [REDACTED]"


@pytest.mark.asyncio
async def test_validate_stored_dual_persists_combined_validity(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user)
    config = _add_aws_config(db_session, twin, user)

    async def valid(_provider, _credentials):
        return {"valid": True, "message": "ok"}

    result = await _service(
        db_session,
        optimizer_validator=valid,
        deployer_validator=valid,
    ).validate_stored_dual(twin_id=twin.id, user_id=user.id, provider="aws")

    db_session.refresh(config)
    assert result["valid"] is True
    assert config.aws_validated is True


@pytest.mark.asyncio
async def test_validate_stored_rejects_missing_twin(db_session):
    user = _create_user(db_session)

    with pytest.raises(EntityNotFoundError):
        await _service(db_session).validate_stored_dual("missing", user.id, "aws")


@pytest.mark.asyncio
async def test_validate_stored_rejects_missing_config(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user)

    with pytest.raises(ValidationError):
        await _service(db_session).validate_stored_dual(twin.id, user.id, "aws")


@pytest.mark.asyncio
async def test_validate_inline_gcp_dual_uses_placeholder_project_for_optimizer(db_session):
    calls = []

    async def optimizer(provider, credentials):
        calls.append(("optimizer", provider, credentials))
        return {"valid": True, "message": "ok"}

    async def deployer(provider, credentials):
        calls.append(("deployer", provider, credentials))
        return {"valid": True, "message": "ok"}

    result = await _service(
        db_session,
        optimizer_validator=optimizer,
        deployer_validator=deployer,
    ).validate_inline_dual(
        InlineValidationRequest(
            provider="gcp",
            gcp=GCPCredentials(
                billing_account="billing-account",
                service_account_json='{"private_key": "GCP-PRIVATE-KEY"}',
                region="europe-west1",
            ),
        )
    )

    assert result["valid"] is True
    assert "gcp_project_id" not in calls[0][2]
    assert calls[1][2]["gcp_billing_account"] == "billing-account"


def test_redact_validation_helpers_handle_nested_payloads():
    credentials = {"aws_secret_access_key": "NESTED-SECRET"}

    assert redact_validation_message("leak NESTED-SECRET", credentials) == "leak [REDACTED]"
    assert redact_validation_payload({"items": ["NESTED-SECRET"]}, credentials) == {"items": ["[REDACTED]"]}


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
