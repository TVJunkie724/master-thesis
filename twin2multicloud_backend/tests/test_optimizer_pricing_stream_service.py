"""Tests for optimizer pricing stream service boundary."""

from __future__ import annotations

import pytest

from src.models.twin import DigitalTwin
from src.models.twin_config import TwinConfiguration
from src.models.user import User
from src.repositories.twin_repository import TwinRepository
from src.services.errors import ExternalServiceUnavailable
from src.services.optimizer_pricing_stream_service import OptimizerPricingStreamService
from src.services.service_errors import ValidationError
from src.utils.crypto import encrypt


class FakeOptimizerClient:
    def __init__(self, chunks=None, exc=None):
        self.chunks = chunks or []
        self.exc = exc
        self.calls = []

    async def stream_pricing_refresh(self, provider, credentials):
        self.calls.append((provider, credentials))
        if self.exc:
            raise self.exc
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


def _service(db, optimizer_client=None) -> OptimizerPricingStreamService:
    return OptimizerPricingStreamService(
        db=db,
        twin_repository=TwinRepository(db),
        optimizer_client=optimizer_client,
        sleep_seconds=0,
    )


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
    fake = FakeOptimizerClient(['event: complete\ndata: {"message": "Done!"}\n\n'])

    body = await _collect(_service(db_session, fake).build_refresh_stream("aws", twin.id, user.id))

    assert "Starting AWS pricing refresh" in body
    assert 'event: complete\ndata: {"message": "Done!"}' in body
    assert fake.calls == [
        (
            "aws",
            {
                "aws_access_key_id": "AKIA_TEST",
                "aws_secret_access_key": "secret-test",
                "aws_region": "eu-west-1",
            },
        )
    ]


@pytest.mark.asyncio
async def test_stream_missing_credentials_emits_error_event(db_session):
    user = _create_user(db_session)
    twin = _create_twin(db_session, user)

    body = await _collect(_service(db_session).build_refresh_stream("aws", twin.id, user.id))

    assert "event: error" in body
    assert "Twin has no configuration" in body


@pytest.mark.asyncio
async def test_stream_optimizer_unavailable_emits_safe_error_event(db_session):
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
    fake = FakeOptimizerClient(exc=ExternalServiceUnavailable("Optimizer API unavailable"))

    body = await _collect(_service(db_session, fake).build_refresh_stream("aws", twin.id, user.id))

    assert "event: error" in body
    assert "Cannot connect to Optimizer service" in body
