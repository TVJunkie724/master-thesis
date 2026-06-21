"""Tests for optimizer pricing stream service boundary."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.models.twin import DigitalTwin
from src.models.twin_config import TwinConfiguration
from src.models.user import User
from src.repositories.twin_repository import TwinRepository
from src.services.optimizer_pricing_stream_service import OptimizerPricingStreamService
from src.services.service_errors import ValidationError
from src.utils.crypto import encrypt


class MockSSEStream:
    def __init__(self, chunks=None, status_code=200):
        self.status_code = status_code
        self.chunks = chunks or []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def aiter_text(self):
        for chunk in self.chunks:
            yield chunk


def _create_user(db) -> User:
    user = User(email="optimizer-stream-service@example.test", name="Optimizer Stream", auth_provider="google")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _create_twin(db, user: User) -> DigitalTwin:
    twin = DigitalTwin(name="Stream Twin", user_id=user.id)
    db.add(twin)
    db.commit()
    db.refresh(twin)
    return twin


def _service(db) -> OptimizerPricingStreamService:
    return OptimizerPricingStreamService(db=db, twin_repository=TwinRepository(db), sleep_seconds=0)


async def _collect(generator):
    return "".join([event async for event in generator])


def test_build_refresh_stream_rejects_invalid_provider(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user)

    with pytest.raises(ValidationError, match="Invalid provider: invalid"):
        _service(db_session).build_refresh_stream("invalid", twin.id, user.id)


@pytest.mark.asyncio
async def test_stream_aws_decrypts_credentials_and_relays_optimizer_events(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user)
    db_session.add(
        TwinConfiguration(
            twin_id=twin.id,
            aws_access_key_id=encrypt("AKIA_TEST", user.id, twin.id),
            aws_secret_access_key=encrypt("secret-test", user.id, twin.id),
            aws_region="eu-west-1",
        )
    )
    db_session.commit()
    stream = MockSSEStream(['event: complete\ndata: {"message": "Done!"}\n\n'])

    with patch("src.services.optimizer_pricing_stream_service.httpx.AsyncClient") as mock_client:
        mock_instance = MagicMock()
        mock_instance.stream = MagicMock(return_value=stream)
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=None)
        mock_client.return_value = mock_instance

        body = await _collect(_service(db_session).build_refresh_stream("aws", twin.id, user.id))

    assert "Starting AWS pricing refresh" in body
    assert 'event: complete\ndata: {"message": "Done!"}' in body
    assert mock_instance.stream.call_args.kwargs["json"] == {
        "aws_access_key_id": "AKIA_TEST",
        "aws_secret_access_key": "secret-test",
        "aws_region": "eu-west-1",
    }


@pytest.mark.asyncio
async def test_stream_missing_credentials_emits_error_event(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user)

    body = await _collect(_service(db_session).build_refresh_stream("aws", twin.id, user.id))

    assert "event: error" in body
    assert "Twin has no configuration" in body
